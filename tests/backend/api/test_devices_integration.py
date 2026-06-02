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
import uuid
from hashlib import sha256

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from whymath_backend.api._device_store import PgDeviceStore, set_device_store
from whymath_backend.app import create_app
from whymath_backend.config import Settings, get_settings
from whymath_backend.db.models.user import UserProfile
from whymath_backend.schema.enums import Persona
from whymath_backend.schema.user import UserProfile as UserProfileSchema
from whymath_backend.security import create_access_token

pytestmark = pytest.mark.integration

_SECRET = "integration-jwt-secret-0123456789abcdef"


def _settings() -> Settings:
    return Settings(jwt_secret_key=SecretStr(_SECRET))


async def _pg_reachable() -> bool:
    engine = create_async_engine(_settings().database_url)
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
    finally:
        await engine.dispose()


async def _insert_user(user_id: uuid.UUID) -> None:
    engine = create_async_engine(_settings().database_url)
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
    engine = create_async_engine(_settings().database_url)
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
            engine = create_async_engine(_settings().database_url)
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
                # revoke True
                assert await store.revoke(device_id) is True
                # 폐기 후 verify False
                assert await store.verify(device_id, sig) is False
                # 미존재 revoke False (idempotent)
                assert await store.revoke("never-registered") is False
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
        engine = create_async_engine(_settings().database_url)
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
            engine = create_async_engine(_settings().database_url)
            try:
                sm = async_sessionmaker(engine, expire_on_commit=False)
                store_a = PgDeviceStore(sm)  # "워커 A"
                store_b = PgDeviceStore(sm)  # "워커 B" — 별 인스턴스, 같은 PG

                device_id, secret_plain = await store_a.register(uid)
                sig = _sign(secret_plain, device_id)
                # 워커 B가 verify True (HA 핵심)
                assert await store_b.verify(device_id, sig) is True
                # 워커 B가 revoke
                assert await store_b.revoke(device_id) is True
                # 워커 A에서도 폐기 반영(같은 PG)
                assert await store_a.verify(device_id, sig) is False
            finally:
                await engine.dispose()
        finally:
            await _cleanup(uid)

    asyncio.run(_run())
