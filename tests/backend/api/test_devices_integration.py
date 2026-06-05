"""devices 라우터·PgDeviceStore 통합테스트 — 실 PostgreSQL (기본 SKIP).

`WHYMATH_RUN_INTEGRATION=1` + 살아있는 PG에서만. 슬라이스 23 `PgDeviceStore`가 실제 PG와
end-to-end 동작하는지(테이블 생성·register INSERT·verify SELECT·revoke UPDATE) 검증한다.

세 시나리오:
1. **PgDeviceStore 단위 라운드트립** — sessionmaker 직접 주입, register → verify True →
   revoke True → verify False → revoke(미존재) False.
2. **HTTP 라우터 + PgDeviceStore** — `/v1/devices/register` 201 → register 응답의 secret으로
   서명 만들어 store.verify True → `/v1/devices/{id}/revoke` 200 → verify False.
3. **다중 워커 의미 시뮬레이션** — 한 store 인스턴스에서 register, *다른* 인스턴스(같은
   sessionmaker) verify True. 인메모리 한계(워커별 상태 분리) 해소 확인.
"""

from __future__ import annotations

import asyncio
import hmac
import os
import uuid
from hashlib import sha256

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from whymath_backend.api._crypto import SecretCipher
from whymath_backend.api._device_store import (
    CachedDeviceStore,
    PgDeviceStore,
    ping_device_store_health,
    set_device_store,
)
from whymath_backend.app import create_app
from whymath_backend.config import Settings, get_settings
from whymath_backend.db.models.device import DeviceCredential
from whymath_backend.db.models.user import UserProfile
from whymath_backend.schema.enums import Persona
from whymath_backend.schema.user import UserProfile as UserProfileSchema
from whymath_backend.security import create_access_token

pytestmark = pytest.mark.integration

_SECRET = "integration-jwt-secret-0123456789abcdef"


def _settings() -> Settings:
    return Settings(jwt_secret_key=SecretStr(_SECRET))


async def _pg_reachable() -> bool:
    engine = create_async_engine(_settings().database_url, poolclass=NullPool)
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
    finally:
        await engine.dispose()


async def _insert_user(user_id: uuid.UUID) -> None:
    engine = create_async_engine(_settings().database_url, poolclass=NullPool)
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            user = UserProfile.from_schema(
                UserProfileSchema(
                    user_id=user_id,
                    persona_primary=Persona.A_일반고고3,
                    nickname="device통합",
                )
            )
            session.add(user)
            await session.commit()
    finally:
        await engine.dispose()


async def _cleanup(user_id: uuid.UUID) -> None:
    engine = create_async_engine(_settings().database_url, poolclass=NullPool)
    try:
        async with engine.begin() as conn:
            await conn.execute(
                text("DELETE FROM device_credential WHERE user_id = :uid"),
                {"uid": str(user_id)},
            )
            await conn.execute(
                text("DELETE FROM user_profile WHERE user_id = :uid"),
                {"uid": str(user_id)},
            )
    finally:
        await engine.dispose()


def _sign(secret: str, device_id: str) -> str:
    return hmac.new(
        secret.encode("utf-8"), device_id.encode("utf-8"), sha256
    ).hexdigest()


def test_pg_device_store_roundtrip_on_live_pg() -> None:
    """PgDeviceStore 단위 라운드트립 — register → verify → revoke → verify False."""
    if not asyncio.run(_pg_reachable()):
        pytest.skip("PostgreSQL 미도달 — 통합 테스트 건너뜀")

    uid = uuid.uuid4()

    async def _run() -> None:
        await _insert_user(uid)
        try:
            engine = create_async_engine(_settings().database_url, poolclass=NullPool)
            try:
                sm = async_sessionmaker(engine, expire_on_commit=False)
                store = PgDeviceStore(sm)
                # register
                device_id, secret_plain = await store.register(uid)
                uuid.UUID(device_id)  # UUID4 형식
                assert len(secret_plain) >= 40
                # verify True
                sig = _sign(secret_plain, device_id)
                assert await store.verify(device_id, sig) is True
                # verify wrong sig False
                assert await store.verify(device_id, "0" * 64) is False
                # slice 24: 타인 owner_id 폐기 시도 → False(404 등가·정보 비누설)
                other_uid = uuid.uuid4()
                assert await store.revoke(device_id, other_uid) is False
                # 원 소유자는 여전히 가능
                assert await store.revoke(device_id, uid) is True
                # 폐기 후 verify False
                assert await store.verify(device_id, sig) is False
                # 미존재 revoke False (idempotent)
                assert await store.revoke("never-registered", uid) is False
            finally:
                await engine.dispose()
        finally:
            await _cleanup(uid)

    asyncio.run(_run())


def test_devices_router_with_pg_store_on_live_pg() -> None:
    """HTTP 라우터 + PgDeviceStore end-to-end — /register 201 → /revoke 200."""
    if not asyncio.run(_pg_reachable()):
        pytest.skip("PostgreSQL 미도달 — 통합 테스트 건너뜀")

    uid = uuid.uuid4()

    async def _setup() -> None:
        await _insert_user(uid)

    asyncio.run(_setup())

    try:
        engine = create_async_engine(_settings().database_url, poolclass=NullPool)
        try:
            sm = async_sessionmaker(engine, expire_on_commit=False)
            store = PgDeviceStore(sm)
            set_device_store(store)
            try:
                app = create_app()
                app.dependency_overrides[get_settings] = _settings
                client = TestClient(app)

                token = create_access_token(uid, settings=_settings())
                auth = {"Authorization": f"Bearer {token}"}

                # register
                reg = client.post("/v1/devices/register", headers=auth)
                assert reg.status_code == 201, reg.text
                body = reg.json()
                device_id = body["device_id"]
                secret_plain = body["secret_plain"]

                # store가 정말 갖고 있는지 — 별도 verify로 확인
                sig = _sign(secret_plain, device_id)
                assert asyncio.run(store.verify(device_id, sig)) is True

                # revoke
                rev = client.post(f"/v1/devices/{device_id}/revoke", headers=auth)
                assert rev.status_code == 200
                assert rev.json() == {"revoked": True}

                # 폐기 후 verify False
                assert asyncio.run(store.verify(device_id, sig)) is False

                # idempotent
                rev2 = client.post(f"/v1/devices/{device_id}/revoke", headers=auth)
                # device 행은 존재(폐기됨) — UPDATE 매치 1, 그래도 revoked=true는 그대로
                # revoke가 rowcount>0면 True. 한 번 더 revoke 매치도 True(idempotent).
                assert rev2.status_code == 200
                assert rev2.json() == {"revoked": True}
            finally:
                set_device_store(None)
        finally:
            asyncio.run(engine.dispose())
    finally:
        asyncio.run(_cleanup(uid))


def test_pg_store_persists_across_instances_on_live_pg() -> None:
    """다중 워커 의미 — 한 store에서 register → 다른 store(같은 sessionmaker) verify 가능.

    인메모리는 워커별 상태 분리되지만 PG-backed는 모든 워커가 같은 DB를 본다(HA·다중 워커
    핵심 invariant).
    """
    if not asyncio.run(_pg_reachable()):
        pytest.skip("PostgreSQL 미도달 — 통합 테스트 건너뜀")

    uid = uuid.uuid4()

    async def _run() -> None:
        await _insert_user(uid)
        try:
            engine = create_async_engine(_settings().database_url, poolclass=NullPool)
            try:
                sm = async_sessionmaker(engine, expire_on_commit=False)
                store_a = PgDeviceStore(sm)  # "워커 A"
                store_b = PgDeviceStore(sm)  # "워커 B" — 별 인스턴스, 같은 PG

                device_id, secret_plain = await store_a.register(uid)
                sig = _sign(secret_plain, device_id)
                # 워커 B가 verify True (HA 핵심)
                assert await store_b.verify(device_id, sig) is True
                # 워커 B가 revoke (본인 uid로)
                assert await store_b.revoke(device_id, uid) is True
                # 워커 A에서도 폐기 반영(같은 PG)
                assert await store_a.verify(device_id, sig) is False
            finally:
                await engine.dispose()
        finally:
            await _cleanup(uid)

    asyncio.run(_run())


def test_cross_user_revoke_isolation_on_live_pg() -> None:
    """slice 24: 사용자 A가 등록한 device를 사용자 B는 폐기 못 함.

    실 PG에서 두 사용자 행 + A의 device 1개 → B 토큰으로 `/revoke` → 200 `{revoked: false}`
    → A의 secret으로 verify는 *여전히 True*(폐기 안 됨).
    """
    if not asyncio.run(_pg_reachable()):
        pytest.skip("PostgreSQL 미도달 — 통합 테스트 건너뜀")

    uid_a = uuid.uuid4()
    uid_b = uuid.uuid4()

    async def _setup() -> None:
        await _insert_user(uid_a)
        await _insert_user(uid_b)

    asyncio.run(_setup())

    try:
        engine = create_async_engine(_settings().database_url, poolclass=NullPool)
        try:
            sm = async_sessionmaker(engine, expire_on_commit=False)
            store = PgDeviceStore(sm)
            set_device_store(store)
            try:
                app = create_app()
                app.dependency_overrides[get_settings] = _settings
                client = TestClient(app)

                # A가 토큰 + device 등록
                token_a = create_access_token(uid_a, settings=_settings())
                reg = client.post(
                    "/v1/devices/register",
                    headers={"Authorization": f"Bearer {token_a}"},
                )
                assert reg.status_code == 201
                device_id = reg.json()["device_id"]
                secret_plain = reg.json()["secret_plain"]
                sig = _sign(secret_plain, device_id)
                assert asyncio.run(store.verify(device_id, sig)) is True

                # B가 토큰으로 A의 device 폐기 시도 → 200 {revoked: false}
                token_b = create_access_token(uid_b, settings=_settings())
                rev = client.post(
                    f"/v1/devices/{device_id}/revoke",
                    headers={"Authorization": f"Bearer {token_b}"},
                )
                assert rev.status_code == 200
                assert rev.json() == {"revoked": False}
                # device는 폐기 *안 됨* — A의 서명 여전히 유효
                assert asyncio.run(store.verify(device_id, sig)) is True

                # A 본인은 정상적으로 폐기 가능
                rev_a = client.post(
                    f"/v1/devices/{device_id}/revoke",
                    headers={"Authorization": f"Bearer {token_a}"},
                )
                assert rev_a.status_code == 200
                assert rev_a.json() == {"revoked": True}
                assert asyncio.run(store.verify(device_id, sig)) is False
            finally:
                set_device_store(None)
        finally:
            asyncio.run(engine.dispose())
    finally:
        asyncio.run(_cleanup(uid_a))
        asyncio.run(_cleanup(uid_b))


def test_list_devices_endpoint_on_live_pg() -> None:
    """slice 29: `GET /v1/devices`가 본인 활성 device만 created_at DESC로 반환."""
    if not asyncio.run(_pg_reachable()):
        pytest.skip("PostgreSQL 미도달 — 통합 테스트 건너뜀")

    uid_a = uuid.uuid4()
    uid_b = uuid.uuid4()

    async def _setup() -> None:
        await _insert_user(uid_a)
        await _insert_user(uid_b)

    asyncio.run(_setup())

    try:
        engine = create_async_engine(_settings().database_url, poolclass=NullPool)
        try:
            sm = async_sessionmaker(engine, expire_on_commit=False)
            store = PgDeviceStore(sm)
            set_device_store(store)
            try:
                app = create_app()
                app.dependency_overrides[get_settings] = _settings
                client = TestClient(app)

                token_a = create_access_token(uid_a, settings=_settings())
                token_b = create_access_token(uid_b, settings=_settings())
                auth_a = {"Authorization": f"Bearer {token_a}"}
                auth_b = {"Authorization": f"Bearer {token_b}"}

                # A가 2 device 등록, B가 1 device 등록, A의 1번째 폐기
                r1 = client.post("/v1/devices/register", headers=auth_a)
                r2 = client.post("/v1/devices/register", headers=auth_a)
                client.post("/v1/devices/register", headers=auth_b)
                d1 = r1.json()["device_id"]
                d2 = r2.json()["device_id"]
                client.post(f"/v1/devices/{d1}/revoke", headers=auth_a)

                # A의 GET — d2 1개만(d1 폐기·B의 device 미노출)
                resp = client.get("/v1/devices", headers=auth_a)
                assert resp.status_code == 200
                devices = resp.json()["devices"]
                assert [d["device_id"] for d in devices] == [d2]
                # DeviceListItem 스키마(slice 29 + 32 last_used_at + 37 revoked/revoked_at).
                assert set(devices[0].keys()) == {
                    "device_id",
                    "created_at",
                    "last_used_at",
                    "revoked",
                    "revoked_at",
                }

                # 401 무토큰
                assert client.get("/v1/devices").status_code == 401
            finally:
                set_device_store(None)
        finally:
            asyncio.run(engine.dispose())
    finally:
        asyncio.run(_cleanup(uid_a))
        asyncio.run(_cleanup(uid_b))


def test_ping_health_succeeds_on_live_pg_and_redis() -> None:
    """slice 30: 라이브 PG + Redis 모두 도달 시 ping_device_store_health가 예외 없이 통과.

    pg 모드(PG ping만)·pg_cached 모드(PG + Redis ping) 둘 다 검증.
    """
    if not asyncio.run(_pg_reachable()):
        pytest.skip("PostgreSQL 미도달 — 통합 테스트 건너뜀")

    settings_pg = Settings(jwt_secret_key=SecretStr(_SECRET), device_store_mode="pg")
    settings_cached = Settings(
        jwt_secret_key=SecretStr(_SECRET), device_store_mode="pg_cached"
    )

    # pg 모드 — PG ping만
    asyncio.run(ping_device_store_health(settings_pg))

    # pg_cached 모드 — Redis ping도. 미도달 시 skip
    try:
        from redis.asyncio import Redis

        async def _redis_check() -> bool:
            client = Redis.from_url(settings_cached.redis_url, decode_responses=True)
            try:
                await client.ping()
                return True
            except Exception:
                return False
            finally:
                await client.aclose()

        if not asyncio.run(_redis_check()):
            pytest.skip("Redis 미도달 — pg_cached 통합 건너뜀")
    except ImportError:
        pytest.skip("redis 라이브러리 미설치")

    asyncio.run(ping_device_store_health(settings_cached))


def test_cleanup_stale_devices_on_live_pg() -> None:
    """slice 33: 실 PG에서 cleanup_stale이 N일 미사용 device를 일괄 폐기."""
    if not asyncio.run(_pg_reachable()):
        pytest.skip("PostgreSQL 미도달 — 통합 테스트 건너뜀")

    import datetime as _dt

    uid = uuid.uuid4()

    async def _run() -> None:
        await _insert_user(uid)
        try:
            engine = create_async_engine(_settings().database_url, poolclass=NullPool)
            try:
                sm = async_sessionmaker(engine, expire_on_commit=False)
                store = PgDeviceStore(sm)

                # 1 fresh + 1 stale 등록
                d_fresh, _ = await store.register(uid)
                d_stale, _ = await store.register(uid)

                # d_stale의 created_at을 직접 SQL로 31일 전으로 강제
                async with engine.begin() as conn:
                    await conn.execute(
                        text(
                            "UPDATE device_credential "
                            "SET created_at = :ts "
                            "WHERE device_id = :did"
                        ),
                        {
                            "ts": _dt.datetime.now(_dt.UTC) - _dt.timedelta(days=31),
                            "did": d_stale,
                        },
                    )

                # slice 34: dry_run으로 미리보기 → 같은 stale id 반환·실제 폐기 0
                preview = await store.cleanup_stale(max_age_days=30, dry_run=True)
                assert preview == [d_stale]
                # cleanup → 1건 폐기·반환 목록에 d_stale 포함
                affected = await store.cleanup_stale(max_age_days=30)
                assert affected == [d_stale]

                # fresh는 활성·stale은 폐기
                async with sm() as session:
                    from whymath_backend.db.models.device import DeviceCredential

                    fresh_row = await session.get(DeviceCredential, d_fresh)
                    stale_row = await session.get(DeviceCredential, d_stale)
                    assert fresh_row is not None and fresh_row.revoked is False
                    assert stale_row is not None and stale_row.revoked is True
                    assert stale_row.revoked_at is not None
            finally:
                await engine.dispose()
        finally:
            await _cleanup(uid)

    asyncio.run(_run())


def test_cached_device_store_on_live_pg_and_redis() -> None:
    """슬라이스 26: CachedDeviceStore(PgDeviceStore) + 실 Redis e2e.

    register → verify(첫 회) → verify(두 번째 cache hit) → revoke → verify False(DEL 됨).
    캐시 hit을 어떻게 *외부에서* 검증할까: counting wrapper로 inner.verify 호출 횟수를 세는
    대신, Redis 키 직접 확인(EXISTS device_verify:{X}).
    """
    if not asyncio.run(_pg_reachable()):
        pytest.skip("PostgreSQL 미도달 — 통합 테스트 건너뜀")

    try:
        from redis.asyncio import Redis
    except ImportError:
        pytest.skip("redis 라이브러리 미설치")

    uid = uuid.uuid4()

    async def _run() -> None:
        # Redis 도달성 확인 — 미도달시 skip
        redis_client = Redis.from_url(_settings().redis_url, decode_responses=True)
        try:
            await redis_client.ping()
        except Exception:
            await redis_client.aclose()
            pytest.skip("Redis 미도달 — 통합 테스트 건너뜀")

        await _insert_user(uid)
        try:
            engine = create_async_engine(_settings().database_url, poolclass=NullPool)
            try:
                sm = async_sessionmaker(engine, expire_on_commit=False)
                inner = PgDeviceStore(sm)
                store = CachedDeviceStore(inner, redis_client, ttl_seconds=60)

                device_id, secret_plain = await store.register(uid)
                cache_key = "device_verify:" + device_id

                # 초기: 캐시 비어있음
                assert await redis_client.exists(cache_key) == 0

                # 첫 verify — cache miss → DB 라운드트립 → 성공 → SETEX
                sig = _sign(secret_plain, device_id)
                assert await store.verify(device_id, sig) is True
                # 캐시 채워졌고 sig 저장됨
                cached_sig = await redis_client.get(cache_key)
                assert cached_sig == sig.lower()
                # TTL 설정됨(60s)
                ttl = await redis_client.ttl(cache_key)
                assert 0 < ttl <= 60

                # revoke → 캐시 DEL
                assert await store.revoke(device_id, uid) is True
                assert await redis_client.exists(cache_key) == 0

                # 폐기 후 verify → cache miss + DB False
                assert await store.verify(device_id, sig) is False
                # 실패는 캐시 안 함
                assert await redis_client.exists(cache_key) == 0
            finally:
                await engine.dispose()
        finally:
            await _cleanup(uid)
            # 캐시 잔여물 청소
            await redis_client.delete("device_verify:" + str(uid))
            await redis_client.aclose()

    asyncio.run(_run())


def test_pg_list_for_user_seq_tiebreak_parity_on_live_pg() -> None:
    """slice 63: 같은 created_at이면 seq(등록순)로 tie-break — InMemory(slice 54) parity.

    desc=나중 등록 먼저·asc=먼저 등록 먼저. null 그룹(last_used_at 전부 NULL)은 방향 무관
    등록순(seq ASC) — InMemory dict 삽입순 보존과 동형.
    """
    if not asyncio.run(_pg_reachable()):
        pytest.skip("PostgreSQL 미도달 — 통합 테스트 건너뜀")

    uid = uuid.uuid4()
    try:
        asyncio.run(_insert_user(uid))

        async def _run() -> None:
            engine = create_async_engine(_settings().database_url, poolclass=NullPool)
            try:
                sm = async_sessionmaker(engine, expire_on_commit=False)
                store = PgDeviceStore(sm)
                # 등록 순서대로 seq 증가(d1<d2<d3). register는 created_at=now()라 서로 다름.
                d1, _ = await store.register(uid)
                d2, _ = await store.register(uid)
                d3, _ = await store.register(uid)
                # 같은 created_at으로 강제 → 동률 시뮬(seq는 등록순 그대로).
                async with sm() as s:
                    await s.execute(
                        text(
                            "UPDATE device_credential "
                            "SET created_at = '2026-01-01T00:00:00+00' WHERE user_id = :u"
                        ),
                        {"u": str(uid)},
                    )
                    await s.commit()
                # created_at 동률 → desc면 seq DESC = 나중 등록(d3) 먼저
                desc_ids = [i.device_id for i in await store.list_for_user(uid)]
                assert desc_ids == [d3, d2, d1], desc_ids
                # asc면 seq ASC = 먼저 등록(d1) 먼저
                asc_ids = [
                    i.device_id for i in await store.list_for_user(uid, order_dir="asc")
                ]
                assert asc_ids == [d1, d2, d3], asc_ids
                # last_used_at 전부 NULL(미verify) → null 그룹은 *방향 무관* 등록순(seq ASC)
                null_ids = [
                    i.device_id
                    for i in await store.list_for_user(
                        uid, order_by="last_used_at", order_dir="desc"
                    )
                ]
                assert null_ids == [d1, d2, d3], null_ids
            finally:
                await engine.dispose()

        asyncio.run(_run())
    finally:
        asyncio.run(_cleanup(uid))


def test_pg_device_store_envelope_encryption_round_trip_on_live_pg() -> None:
    """slice 73: cipher 주입 PgDeviceStore — register는 암호화 저장·verify는 복호.

    ① register 후 DB 행: secret_plain NULL·secret_encrypted/secret_nonce 채워짐·ciphertext에
    평문 secret 미포함(at-rest 노출 0). ② verify True(복호→HMAC). ③ 하위 호환: 평문 행
    (cipher 없이 등록)도 cipher-활성 store가 그대로 verify(dual-read 폴백).
    """
    if not asyncio.run(_pg_reachable()):
        pytest.skip("PostgreSQL 미도달 — 통합 테스트 건너뜀")

    uid = uuid.uuid4()
    cipher = SecretCipher(os.urandom(32))

    async def _run() -> None:
        await _insert_user(uid)
        try:
            engine = create_async_engine(_settings().database_url, poolclass=NullPool)
            try:
                sm = async_sessionmaker(engine, expire_on_commit=False)
                enc_store = PgDeviceStore(sm, cipher)
                # ① 암호화 등록 + verify
                device_id, secret_plain = await enc_store.register(uid)
                sig = _sign(secret_plain, device_id)
                assert await enc_store.verify(device_id, sig) is True
                # ② DB 행 검사: 평문 NULL·암호문 존재·ciphertext에 평문 미포함
                async with sm() as s:
                    row = await s.get(DeviceCredential, device_id)
                    assert row is not None
                    assert row.secret_plain is None
                    assert row.secret_encrypted is not None
                    assert row.secret_nonce is not None
                    assert secret_plain.encode("utf-8") not in row.secret_encrypted
                # ③ 하위 호환: 평문 등록(cipher 없는 store) → cipher 활성 store가 verify
                plain_store = PgDeviceStore(sm)
                pid, psecret = await plain_store.register(uid)
                assert await enc_store.verify(pid, _sign(psecret, pid)) is True
            finally:
                await engine.dispose()
        finally:
            await _cleanup(uid)

    asyncio.run(_run())


def test_device_credential_user_index_swapped_on_live_pg() -> None:
    """slice 64: 단일 user_id 인덱스 → 복합 (user_id, created_at DESC, seq DESC) 대체.

    마이그레이션이 ① 복합 `idx_device_credential_user`를 만들고 ② 단일
    `ix_device_credential_user_id`를 제거했는지 pg_indexes로 검증(중복 제거). 복합 인덱스
    정의에 정렬 방향(created_at DESC, seq DESC)이 반영됐는지도 확인 — list_for_user 기본
    정렬을 Sort 없이 충족함을 보장한다.
    """
    if not asyncio.run(_pg_reachable()):
        pytest.skip("PostgreSQL 미도달 — 통합 테스트 건너뜀")

    async def _run() -> None:
        engine = create_async_engine(_settings().database_url, poolclass=NullPool)
        try:
            async with engine.connect() as conn:
                rows = (
                    await conn.execute(
                        text(
                            "SELECT indexname, indexdef FROM pg_indexes "
                            "WHERE tablename = 'device_credential'"
                        )
                    )
                ).all()
            names = {r[0] for r in rows}
            defs = {r[0]: r[1] for r in rows}
            # 복합 인덱스 존재 + 단일 user_id 인덱스 제거(대체)
            assert "idx_device_credential_user" in names, names
            assert "ix_device_credential_user_id" not in names, names
            # 정렬 방향까지 반영(prefix user_id + created_at DESC, seq DESC)
            composite = defs["idx_device_credential_user"]
            assert "user_id, created_at DESC, seq DESC" in composite, composite
        finally:
            await engine.dispose()

    asyncio.run(_run())


def test_pg_device_store_reencrypt_backfill_on_live_pg() -> None:
    """slice 74: 평문 등록(cipher 없이) → cipher store 백필 → 행 암호화·verify 유지·idempotent.

    실 PG에서 ① 평문 행 2개 등록 ② cipher store가 백필(count=2) ③ DB 행 secret_plain NULL·
    secret_encrypted 채워짐 ④ 백필 후에도 verify 성공(복호) ⑤ 재실행 0(idempotent).
    """
    if not asyncio.run(_pg_reachable()):
        pytest.skip("PostgreSQL 미도달 — 통합 테스트 건너뜀")

    uid = uuid.uuid4()
    cipher = SecretCipher(os.urandom(32))

    async def _run() -> None:
        await _insert_user(uid)
        try:
            engine = create_async_engine(_settings().database_url, poolclass=NullPool)
            try:
                sm = async_sessionmaker(engine, expire_on_commit=False)
                # 평문 등록(cipher 없는 store)
                plain_store = PgDeviceStore(sm)
                d1, s1 = await plain_store.register(uid)
                d2, s2 = await plain_store.register(uid)
                # 백필(cipher store)
                enc_store = PgDeviceStore(sm, cipher)
                assert await enc_store.reencrypt_plaintext_secrets() == 2
                # DB 행: 평문 NULL·암호문 존재
                async with sm() as s:
                    row1 = await s.get(DeviceCredential, d1)
                    assert row1 is not None
                    assert row1.secret_plain is None
                    assert row1.secret_encrypted is not None
                # verify 유지(복호→HMAC)
                assert await enc_store.verify(d1, _sign(s1, d1)) is True
                assert await enc_store.verify(d2, _sign(s2, d2)) is True
                # idempotent
                assert await enc_store.reencrypt_plaintext_secrets() == 0
            finally:
                await engine.dispose()
        finally:
            await _cleanup(uid)

    asyncio.run(_run())
