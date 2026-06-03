"""슬라이스 22-23 — 디바이스별 고유 secret + 등록 플로우(OAuth-style) hermetic 테스트.

세 표면:
1. `InMemoryDeviceStore` 단위(register/verify/revoke·상수시간 비교·secret 1회 노출).
2. `/v1/devices/register`·`/v1/devices/{id}/revoke` HTTP 결선(201·503·401·idempotent).
3. `_client_device_id`의 store 모드 우선순위 — 등록된 device만 통과·미등록/폐기/잘못된 sig는
   None(fail-safe), store 미설정 시 slice 21 공유 secret 폴백.

슬라이스 23: Protocol·InMemoryDeviceStore·_client_device_id가 모두 async — 본 파일은
pytest-asyncio `auto` 모드 가정(`asyncio_mode = "auto"` in pyproject.toml).
"""

from __future__ import annotations

import hmac
import uuid
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from typing import Any
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from whymath_backend.api._auth import get_consented_user
from whymath_backend.api._device_store import (
    CachedDeviceStore,
    DeviceCredentialStore,
    InMemoryDeviceStore,
    PgDeviceStore,
    _compute_signature,
    build_device_store_from_settings,
    get_device_store,
    set_device_store,
)
from whymath_backend.api._device_metrics import (
    get_device_sig_failures,
    reset_device_sig_failures,
)
from whymath_backend.api._rate_limit import (
    _client_device_id,
    _expected_device_signature,
    reset_store,
)
from whymath_backend.app import create_app
from whymath_backend.config import Settings, get_settings
from whymath_backend.db.models.user import UserProfile
from whymath_backend.db.session import get_session
from whymath_backend.schema.enums import Persona
from whymath_backend.schema.user import UserProfile as UserProfileSchema

_UID = uuid.uuid4()


@pytest.fixture(autouse=True)
def _reset_device_store() -> Iterator[None]:
    """매 테스트 격리 — 모듈 전역 `_DEVICE_STORE`를 None으로 복원해 누수 차단."""
    set_device_store(None)
    yield
    set_device_store(None)


@pytest.fixture(autouse=True)
def _reset_rate_limit_store() -> None:
    """매 테스트 격리 — rate limit 카운터 리셋(슬라이스 25에서 register dep 사용)."""
    import asyncio

    asyncio.run(reset_store())


@pytest.fixture(autouse=True)
def _reset_device_metrics() -> None:
    """매 테스트 격리 — 슬라이스 28 device sig 실패 카운터 리셋(누수 차단)."""
    reset_device_sig_failures()


def _user() -> UserProfile:
    return UserProfile.from_schema(
        UserProfileSchema(user_id=_UID, persona_primary=Persona.A_일반고고3)
    )


def _settings_override(
    device_hmac_secret: str = "",
    register_user_limit: int = 0,
    register_ip_limit: int = 0,
) -> Settings:
    """기본은 register rate limit *비활성*(0) — 기존 테스트 영향 0. slice 25 테스트만 활성."""
    return Settings(
        jwt_secret_key=SecretStr("test-secret-0123456789abcdef"),
        coach_device_hmac_secret=SecretStr(device_hmac_secret),
        device_register_rate_limit_per_minute=register_user_limit,
        device_register_rate_limit_ip_per_minute=register_ip_limit,
    )


class _FakeSession:
    """devices 라우터는 DB 미사용 — 호출 시 AssertionError."""

    async def execute(self, stmt: Any) -> None:
        raise AssertionError("devices 라우터는 DB 쿼리하지 않아야 한다.")


def _client(store: DeviceCredentialStore | None) -> TestClient:
    """인증된 사용자 + 옵션 store. store=None이면 503 케이스 검증용."""
    set_device_store(store)
    app = create_app()
    app.dependency_overrides[get_consented_user] = _user
    app.dependency_overrides[get_settings] = lambda: _settings_override()

    async def _sess() -> AsyncIterator[_FakeSession]:
        yield _FakeSession()

    app.dependency_overrides[get_session] = _sess
    return TestClient(app)


def _no_auth_client(store: DeviceCredentialStore | None) -> TestClient:
    """미인증 — Bearer 토큰 없이 호출(401 검증)."""
    set_device_store(store)
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: _settings_override()

    async def _sess() -> AsyncIterator[_FakeSession]:
        yield _FakeSession()

    app.dependency_overrides[get_session] = _sess
    return TestClient(app)


def _sign(secret: str, device_id: str) -> str:
    """HMAC-SHA256(secret, device_id) hex digest — store가 verify에서 재계산하는 식."""
    return hmac.new(
        secret.encode("utf-8"), device_id.encode("utf-8"), sha256
    ).hexdigest()


# ─────────────────────────────────────────────────────────────────────────────
# 1) InMemoryDeviceStore 단위
# ─────────────────────────────────────────────────────────────────────────────


class TestInMemoryDeviceStoreRegister:
    """register — UUID4 device_id + URL-safe 32B 시크릿 발급."""

    async def test_register_returns_uuid_device_id_and_high_entropy_secret(
        self,
    ) -> None:
        store = InMemoryDeviceStore()
        device_id, secret_plain = await store.register(_UID)
        parsed = uuid.UUID(device_id)
        assert parsed.version == 4
        assert len(secret_plain) >= 40
        assert all(c.isalnum() or c in "-_" for c in secret_plain)

    async def test_register_yields_distinct_credentials_per_call(self) -> None:
        store = InMemoryDeviceStore()
        d1, s1 = await store.register(_UID)
        d2, s2 = await store.register(_UID)
        assert d1 != d2
        assert s1 != s2


class TestInMemoryDeviceStoreVerify:
    """verify — HMAC-SHA256 재계산·상수시간 비교."""

    async def test_verify_accepts_valid_signature(self) -> None:
        store = InMemoryDeviceStore()
        device_id, secret_plain = await store.register(_UID)
        sig = _sign(secret_plain, device_id)
        assert await store.verify(device_id, sig) is True

    async def test_verify_rejects_unknown_device_id(self) -> None:
        store = InMemoryDeviceStore()
        assert await store.verify("unknown-device-id", "0" * 64) is False

    async def test_verify_rejects_wrong_signature(self) -> None:
        store = InMemoryDeviceStore()
        device_id, _ = await store.register(_UID)
        bad_sig = _sign("wrong-secret", device_id)
        assert await store.verify(device_id, bad_sig) is False

    async def test_verify_rejects_signature_for_other_device(self) -> None:
        store = InMemoryDeviceStore()
        d1, s1 = await store.register(_UID)
        d2, _s2 = await store.register(_UID)
        sig_for_d1 = _sign(s1, d1)
        assert await store.verify(d2, sig_for_d1) is False

    async def test_verify_accepts_uppercase_signature(self) -> None:
        store = InMemoryDeviceStore()
        device_id, secret_plain = await store.register(_UID)
        sig_upper = _sign(secret_plain, device_id).upper()
        assert await store.verify(device_id, sig_upper) is True

    async def test_verify_returns_false_after_revoke(self) -> None:
        store = InMemoryDeviceStore()
        device_id, secret_plain = await store.register(_UID)
        sig = _sign(secret_plain, device_id)
        assert await store.verify(device_id, sig) is True
        await store.revoke(device_id, _UID)
        assert await store.verify(device_id, sig) is False


class TestInMemoryDeviceStoreRevoke:
    """revoke — 존재하면 True·미존재 False·재폐기는 True(idempotent)·타인 소유면 False(slice 24)."""

    async def test_revoke_existing_owner_returns_true(self) -> None:
        store = InMemoryDeviceStore()
        device_id, _ = await store.register(_UID)
        assert await store.revoke(device_id, _UID) is True

    async def test_revoke_unknown_returns_false(self) -> None:
        store = InMemoryDeviceStore()
        assert await store.revoke("never-registered", _UID) is False

    async def test_revoke_is_idempotent(self) -> None:
        store = InMemoryDeviceStore()
        device_id, _ = await store.register(_UID)
        assert await store.revoke(device_id, _UID) is True
        assert await store.revoke(device_id, _UID) is True

    async def test_revoke_other_owner_returns_false(self) -> None:
        """slice 24: 타인 device 폐기 시도 → False(404 등가·정보 비누설)."""
        store = InMemoryDeviceStore()
        device_id, _ = await store.register(_UID)
        other_uid = uuid.uuid4()
        # 다른 사용자가 폐기 시도 → False
        assert await store.revoke(device_id, other_uid) is False
        # 원 소유자는 여전히 폐기 가능(앞 시도가 상태 변경 0)
        assert await store.revoke(device_id, _UID) is True


class TestInMemoryDeviceStoreReset:
    async def test_reset_clears_all_credentials(self) -> None:
        store = InMemoryDeviceStore()
        device_id, secret_plain = await store.register(_UID)
        sig = _sign(secret_plain, device_id)
        assert await store.verify(device_id, sig) is True
        store.reset()  # sync 헬퍼
        assert await store.verify(device_id, sig) is False


class TestDeviceStoreProtocolConformance:
    def test_inmemory_satisfies_protocol(self) -> None:
        assert isinstance(InMemoryDeviceStore(), DeviceCredentialStore)


class TestModuleGlobals:
    def test_default_is_none(self) -> None:
        assert get_device_store() is None

    def test_set_then_get_roundtrip(self) -> None:
        store = InMemoryDeviceStore()
        set_device_store(store)
        assert get_device_store() is store
        set_device_store(None)
        assert get_device_store() is None


# ─────────────────────────────────────────────────────────────────────────────
# 2) HTTP 표면 — /v1/devices/register · /v1/devices/{id}/revoke
# ─────────────────────────────────────────────────────────────────────────────


class TestRegisterEndpoint:
    def test_returns_201_with_device_id_and_secret_plain(self) -> None:
        store = InMemoryDeviceStore()
        resp = _client(store).post("/v1/devices/register")
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert "device_id" in body
        assert "secret_plain" in body
        uuid.UUID(body["device_id"])
        assert len(body["secret_plain"]) >= 40

    async def test_registered_device_verifies_in_store(self) -> None:
        """등록 응답의 (device_id, secret_plain)으로 verify 가능한지 라운드트립."""
        store = InMemoryDeviceStore()
        resp = _client(store).post("/v1/devices/register")
        body = resp.json()
        sig = _sign(body["secret_plain"], body["device_id"])
        assert await store.verify(body["device_id"], sig) is True

    def test_returns_503_when_store_not_configured(self) -> None:
        resp = _client(None).post("/v1/devices/register")
        assert resp.status_code == 503
        assert "저장소" in resp.json()["detail"]

    def test_returns_401_without_auth(self) -> None:
        store = InMemoryDeviceStore()
        resp = _no_auth_client(store).post("/v1/devices/register")
        assert resp.status_code == 401
        assert "WWW-Authenticate" in resp.headers


class TestRegisterRateLimit:
    """슬라이스 25 — `/v1/devices/register`에 user+IP 한도 적용 검증.

    별 keying(`category=device_register`)으로 coach `write`와 키 공간 분리 — 한쪽이 다른
    쪽을 잠식하지 않는다. 기본 fixture가 limit 0(비활성)이라 기존 테스트 영향 0.
    """

    def _client_with_limits(
        self,
        store: DeviceCredentialStore,
        user_limit: int = 0,
        ip_limit: int = 0,
    ) -> TestClient:
        set_device_store(store)
        app = create_app()
        app.dependency_overrides[get_consented_user] = _user
        app.dependency_overrides[get_settings] = lambda: _settings_override(
            register_user_limit=user_limit, register_ip_limit=ip_limit
        )

        async def _sess() -> AsyncIterator[_FakeSession]:
            yield _FakeSession()

        app.dependency_overrides[get_session] = _sess
        return TestClient(app)

    def test_user_limit_enforced(self) -> None:
        """사용자 한도 2 — 첫 2회 201, 3회는 429."""
        store = InMemoryDeviceStore()
        client = self._client_with_limits(store, user_limit=2, ip_limit=0)
        r1 = client.post("/v1/devices/register")
        r2 = client.post("/v1/devices/register")
        r3 = client.post("/v1/devices/register")
        assert r1.status_code == 201
        assert r2.status_code == 201
        assert r3.status_code == 429
        # blocker는 user 차원
        assert "Retry-After" in r3.headers
        assert r3.headers.get("X-RateLimit-User-Limit") == "2"

    def test_ip_limit_enforced(self) -> None:
        """IP 한도 1 — 첫 1회 201, 2회는 429."""
        store = InMemoryDeviceStore()
        client = self._client_with_limits(store, user_limit=0, ip_limit=1)
        r1 = client.post("/v1/devices/register")
        r2 = client.post("/v1/devices/register")
        assert r1.status_code == 201
        assert r2.status_code == 429
        assert r2.headers.get("X-RateLimit-Ip-Limit") == "1"

    def test_disabled_when_limit_zero(self) -> None:
        """기본(=0) — 비활성·기존 테스트 동작 보존."""
        store = InMemoryDeviceStore()
        client = self._client_with_limits(store, user_limit=0, ip_limit=0)
        # 10회 호출해도 모두 201(한도 0 = 비활성)
        for _ in range(10):
            assert client.post("/v1/devices/register").status_code == 201

    def test_register_bucket_isolated_from_coach_write(self) -> None:
        """device_register category가 coach write와 *분리* — 한쪽이 다른 쪽 잠식 안 함.

        register limit=1 + 첫 register 200 → 2회는 429. *그 사이* coach POST는 영향 0
        (별 키 공간). 본 테스트는 coach 엔드포인트 호출 안 하나, 별 category 결선만 확인.
        """
        store = InMemoryDeviceStore()
        client = self._client_with_limits(store, user_limit=1, ip_limit=0)
        r1 = client.post("/v1/devices/register")
        r2 = client.post("/v1/devices/register")
        assert r1.status_code == 201
        assert r2.status_code == 429
        # 429 응답 헤더 — Retry-After 포함
        assert int(r2.headers["Retry-After"]) > 0


class TestRevokeEndpoint:
    def test_revokes_existing_device(self) -> None:
        store = InMemoryDeviceStore()
        client = _client(store)
        reg = client.post("/v1/devices/register").json()
        revoke = client.post(f"/v1/devices/{reg['device_id']}/revoke")
        assert revoke.status_code == 200, revoke.text
        assert revoke.json() == {"revoked": True}

    def test_unknown_device_returns_revoked_false_not_404(self) -> None:
        store = InMemoryDeviceStore()
        resp = _client(store).post("/v1/devices/never-registered/revoke")
        assert resp.status_code == 200
        assert resp.json() == {"revoked": False}

    async def test_revoked_device_fails_verify(self) -> None:
        """revoke 후 같은 secret으로도 store.verify가 False."""
        store = InMemoryDeviceStore()
        client = _client(store)
        reg = client.post("/v1/devices/register").json()
        sig = _sign(reg["secret_plain"], reg["device_id"])
        assert await store.verify(reg["device_id"], sig) is True
        client.post(f"/v1/devices/{reg['device_id']}/revoke")
        assert await store.verify(reg["device_id"], sig) is False

    def test_returns_503_when_store_not_configured(self) -> None:
        resp = _client(None).post("/v1/devices/some-id/revoke")
        assert resp.status_code == 503

    def test_returns_401_without_auth(self) -> None:
        store = InMemoryDeviceStore()
        resp = _no_auth_client(store).post("/v1/devices/some-id/revoke")
        assert resp.status_code == 401

    async def test_other_users_device_returns_revoked_false_not_404(self) -> None:
        """slice 24: 인증된 다른 사용자가 타인 device 폐기 시도 → `{revoked: false}`(404 등가).

        device가 실제 존재해도 응답은 *미존재와 동일* — 존재 여부 노출 차단(device_id 열거
        공격 방어). 실제 폐기는 안 일어남(store에서 직접 verify로 확인).
        """
        store = InMemoryDeviceStore()
        # *다른* 사용자(other_uid)가 등록한 device — _UID(라우터 인증된 사용자)는 폐기 권한 없음
        other_uid = uuid.uuid4()
        device_id, secret_plain = await store.register(other_uid)
        client = _client(store)  # 인증 사용자는 _UID
        resp = client.post(f"/v1/devices/{device_id}/revoke")
        assert resp.status_code == 200
        assert resp.json() == {"revoked": False}
        # device는 실제로 폐기되지 *않음* — 원 소유자의 서명 여전히 유효
        sig = _sign(secret_plain, device_id)
        assert await store.verify(device_id, sig) is True


# ─────────────────────────────────────────────────────────────────────────────
# 2b) 슬라이스 29 — `GET /v1/devices` 본인 목록
# ─────────────────────────────────────────────────────────────────────────────


class TestListDevicesEndpoint:
    """`GET /v1/devices` — 본인 활성 디바이스 목록(created_at DESC)."""

    async def test_empty_list_when_no_registrations(self) -> None:
        store = InMemoryDeviceStore()
        resp = _client(store).get("/v1/devices")
        assert resp.status_code == 200
        # slice 39: total=None(기본 false·include_total 미요청)
        assert resp.json() == {"devices": [], "total": None}

    async def test_returns_only_own_active_devices(self) -> None:
        """본인 + 타인 등록·본인 일부 폐기 → 본인 활성만 반환."""
        store = InMemoryDeviceStore()
        # 본인 2개 + 타인 1개 등록
        d1, _ = await store.register(_UID)
        d2, _ = await store.register(_UID)
        other_uid = uuid.uuid4()
        d_other, _ = await store.register(other_uid)
        # 본인 1개 폐기
        await store.revoke(d1, _UID)
        # GET 호출 — 본인 *활성* 1개만
        resp = _client(store).get("/v1/devices")
        assert resp.status_code == 200
        body = resp.json()
        device_ids = [d["device_id"] for d in body["devices"]]
        assert device_ids == [d2]  # 폐기된 d1·타인 d_other 제외
        # secret_plain·user_id PII 미노출
        # slice 32: last_used_at·slice 37: revoked/revoked_at 추가
        assert set(body["devices"][0].keys()) == {
            "device_id",
            "created_at",
            "last_used_at",
            "revoked",
            "revoked_at",
        }
        # 활성만 응답이므로 revoked=False·revoked_at=None
        assert body["devices"][0]["revoked"] is False
        assert body["devices"][0]["revoked_at"] is None

    async def test_ordered_by_created_at_desc(self) -> None:
        """여러 device 등록 시 최신 등록순(created_at DESC)."""
        store = InMemoryDeviceStore()
        d1, _ = await store.register(_UID)
        d2, _ = await store.register(_UID)
        d3, _ = await store.register(_UID)
        resp = _client(store).get("/v1/devices")
        device_ids = [d["device_id"] for d in resp.json()["devices"]]
        # 등록 역순 — d3가 가장 최신, d1이 가장 오래됨
        assert device_ids == [d3, d2, d1]

    def test_returns_503_when_store_not_configured(self) -> None:
        resp = _client(None).get("/v1/devices")
        assert resp.status_code == 503

    def test_returns_401_without_auth(self) -> None:
        store = InMemoryDeviceStore()
        resp = _no_auth_client(store).get("/v1/devices")
        assert resp.status_code == 401

    async def test_include_revoked_returns_revoked_devices(self) -> None:
        """slice 37: `?include_revoked=true` → 폐기 이력 포함·revoked/revoked_at 노출."""
        store = InMemoryDeviceStore()
        d_active, _ = await store.register(_UID)
        d_revoked, _ = await store.register(_UID)
        await store.revoke(d_revoked, _UID)
        # 기본: 활성 1개만
        resp_default = _client(store).get("/v1/devices")
        assert [d["device_id"] for d in resp_default.json()["devices"]] == [d_active]
        # include_revoked=true: 둘 다(DESC)
        resp_all = _client(store).get("/v1/devices?include_revoked=true")
        body = resp_all.json()
        device_ids = [d["device_id"] for d in body["devices"]]
        assert sorted(device_ids) == sorted([d_active, d_revoked])
        # 폐기된 device는 revoked=true·revoked_at 채워짐
        revoked_entry = next(d for d in body["devices"] if d["device_id"] == d_revoked)
        assert revoked_entry["revoked"] is True
        assert revoked_entry["revoked_at"] is not None
        # 활성 device는 revoked=false·revoked_at=null
        active_entry = next(d for d in body["devices"] if d["device_id"] == d_active)
        assert active_entry["revoked"] is False
        assert active_entry["revoked_at"] is None

    async def test_pagination_limit_offset(self) -> None:
        """slice 38: ?limit=2&offset=1 → DESC 정렬에서 2번째부터 2개."""
        store = InMemoryDeviceStore()
        ids = [(await store.register(_UID))[0] for _ in range(5)]
        client = _client(store)
        # 기본 호출 — 5개 모두(limit=50 기본 ≫ 5)
        all_resp = client.get("/v1/devices")
        assert len(all_resp.json()["devices"]) == 5
        # limit=2, offset=0 → 첫 2개(DESC: 가장 최근 등록 2개)
        page1 = client.get("/v1/devices?limit=2&offset=0")
        assert len(page1.json()["devices"]) == 2
        # limit=2, offset=2 → 다음 2개
        page2 = client.get("/v1/devices?limit=2&offset=2")
        assert len(page2.json()["devices"]) == 2
        # limit=2, offset=4 → 마지막 1개(len < limit → 마지막 페이지 시그널)
        page3 = client.get("/v1/devices?limit=2&offset=4")
        assert len(page3.json()["devices"]) == 1
        # offset이 total 초과 → 빈 리스트
        page4 = client.get("/v1/devices?limit=2&offset=10")
        assert page4.json()["devices"] == []
        # 모든 페이지 device_id 합집합 = 전체
        collected = (
            [d["device_id"] for d in page1.json()["devices"]]
            + [d["device_id"] for d in page2.json()["devices"]]
            + [d["device_id"] for d in page3.json()["devices"]]
        )
        assert sorted(collected) == sorted(ids)

    def test_limit_validation_rejects_zero_and_too_large(self) -> None:
        """limit는 1~200 — FastAPI Query validation."""
        store = InMemoryDeviceStore()
        client = _client(store)
        assert client.get("/v1/devices?limit=0").status_code == 422
        assert client.get("/v1/devices?limit=201").status_code == 422
        # offset 음수 거부
        assert client.get("/v1/devices?offset=-1").status_code == 422

    async def test_include_total_returns_filtered_count(self) -> None:
        """slice 39: ?include_total=true → total 채움(필터 조건 적용)."""
        store = InMemoryDeviceStore()
        # 3 활성 + 2 폐기
        for _ in range(3):
            await store.register(_UID)
        for _ in range(2):
            d, _ = await store.register(_UID)
            await store.revoke(d, _UID)
        client = _client(store)
        # 기본(활성만)·include_total=true → total=3
        resp = client.get("/v1/devices?include_total=true")
        body = resp.json()
        assert body["total"] == 3
        assert len(body["devices"]) == 3
        # include_revoked=true + include_total → total=5(폐기 포함)
        resp_all = client.get("/v1/devices?include_revoked=true&include_total=true")
        body_all = resp_all.json()
        assert body_all["total"] == 5
        assert len(body_all["devices"]) == 5
        # 페이지네이션과 결합 — limit=2면 devices=2개·total=5 그대로
        resp_paged = client.get(
            "/v1/devices?include_revoked=true&include_total=true&limit=2"
        )
        paged_body = resp_paged.json()
        assert paged_body["total"] == 5
        assert len(paged_body["devices"]) == 2

    async def test_since_until_query_params_filter_response(self) -> None:
        """slice 41: ?since/?until ISO8601 → 시간창 필터.

        URL의 `+`는 공백으로 파싱되므로 `params=` dict로 안전 전달(httpx 자동 인코딩).
        """
        store = InMemoryDeviceStore()
        d1, _ = await store.register(_UID)
        d2, _ = await store.register(_UID)
        now = datetime.now(UTC)
        store._creds[d2] = store._creds[d2]._replace(
            created_at=now - timedelta(days=365)
        )
        client = _client(store)
        since_iso = (now - timedelta(days=30)).isoformat()
        # since=30일 전 → d1만
        resp = client.get("/v1/devices", params={"since": since_iso})
        assert resp.status_code == 200, resp.text
        ids = [d["device_id"] for d in resp.json()["devices"]]
        assert ids == [d1]
        # since + include_total → 필터 적용 count(우회 캐시 경로)
        resp_total = client.get(
            "/v1/devices", params={"since": since_iso, "include_total": True}
        )
        assert resp_total.json()["total"] == 1

    def test_naive_datetime_since_rejected_422(self) -> None:
        """slice 42: timezone 정보 없는 ISO8601(naive) → 422."""
        store = InMemoryDeviceStore()
        client = _client(store)
        # naive ISO — Z나 ±HH:MM 없음
        resp = client.get("/v1/devices", params={"since": "2024-01-01T00:00:00"})
        assert resp.status_code == 422
        assert "timezone" in resp.json()["detail"].lower()

    def test_naive_datetime_until_rejected_422(self) -> None:
        store = InMemoryDeviceStore()
        client = _client(store)
        resp = client.get("/v1/devices", params={"until": "2024-12-31T23:59:59"})
        assert resp.status_code == 422

    def test_tz_aware_with_z_accepted(self) -> None:
        """`Z`(UTC 약식) 포함 → 정상 200."""
        store = InMemoryDeviceStore()
        client = _client(store)
        resp = client.get("/v1/devices", params={"since": "2024-01-01T00:00:00Z"})
        assert resp.status_code == 200

    async def test_revoked_since_filter_via_http(self) -> None:
        """slice 43: `?revoked_since` → revoked_at 시간창 필터·HTTP 라운드트립."""
        store = InMemoryDeviceStore()
        d1, _ = await store.register(_UID)
        d2, _ = await store.register(_UID)
        await store.revoke(d1, _UID)
        await store.revoke(d2, _UID)
        now = datetime.now(UTC)
        # d1은 1년 전 폐기·d2는 어제 폐기
        store._creds[d1] = store._creds[d1]._replace(
            revoked_at=now - timedelta(days=365)
        )
        store._creds[d2] = store._creds[d2]._replace(revoked_at=now - timedelta(days=1))
        client = _client(store)
        # ?include_revoked=true&revoked_since=30일전 → d2만
        resp = client.get(
            "/v1/devices",
            params={
                "include_revoked": "true",
                "revoked_since": (now - timedelta(days=30)).isoformat(),
            },
        )
        assert resp.status_code == 200
        ids = [d["device_id"] for d in resp.json()["devices"]]
        assert ids == [d2]

    def test_naive_revoked_since_rejected_422(self) -> None:
        """slice 42 검증을 slice 43 필드(revoked_since)에도 적용."""
        store = InMemoryDeviceStore()
        client = _client(store)
        resp = client.get(
            "/v1/devices", params={"revoked_since": "2024-01-01T00:00:00"}
        )
        assert resp.status_code == 422
        assert "revoked_since" in resp.json()["detail"]

    def test_tz_aware_with_offset_accepted(self) -> None:
        """`+09:00` 등 offset 포함 → 정상 200."""
        store = InMemoryDeviceStore()
        client = _client(store)
        resp = client.get("/v1/devices", params={"since": "2024-01-01T00:00:00+09:00"})
        assert resp.status_code == 200

    async def test_include_total_false_default_returns_none(self) -> None:
        """기본 `?include_total` 미지정 → total=None(추가 COUNT 회피)."""
        store = InMemoryDeviceStore()
        await store.register(_UID)
        resp = _client(store).get("/v1/devices")
        assert resp.json()["total"] is None


class TestInMemoryDeviceStoreListForUser:
    """`list_for_user` 단위 — owner_id 스코프·revoked 제외·DESC 정렬."""

    async def test_empty_returns_empty_list(self) -> None:
        store = InMemoryDeviceStore()
        assert await store.list_for_user(_UID) == []

    async def test_scoped_to_owner(self) -> None:
        store = InMemoryDeviceStore()
        d_mine, _ = await store.register(_UID)
        other_uid = uuid.uuid4()
        await store.register(other_uid)  # 다른 사용자의 device
        infos = await store.list_for_user(_UID)
        assert [i.device_id for i in infos] == [d_mine]

    async def test_revoked_excluded(self) -> None:
        store = InMemoryDeviceStore()
        d1, _ = await store.register(_UID)
        d2, _ = await store.register(_UID)
        await store.revoke(d1, _UID)
        infos = await store.list_for_user(_UID)
        assert [i.device_id for i in infos] == [d2]

    async def test_include_revoked_includes_polished(self) -> None:
        """slice 37: include_revoked=True → 폐기 device도 포함·revoked/revoked_at 채움."""
        store = InMemoryDeviceStore()
        d1, _ = await store.register(_UID)
        d2, _ = await store.register(_UID)
        await store.revoke(d1, _UID)
        infos = await store.list_for_user(_UID, include_revoked=True)
        ids = [i.device_id for i in infos]
        assert sorted(ids) == sorted([d1, d2])
        # d1은 revoked·revoked_at 채워짐, d2는 활성
        d1_info = next(i for i in infos if i.device_id == d1)
        d2_info = next(i for i in infos if i.device_id == d2)
        assert d1_info.revoked is True
        assert d1_info.revoked_at is not None
        assert d2_info.revoked is False
        assert d2_info.revoked_at is None

    async def test_pagination_slices_sorted_result(self) -> None:
        """slice 38: limit/offset이 created_at DESC 정렬 후 슬라이스."""
        store = InMemoryDeviceStore()
        ids = [(await store.register(_UID))[0] for _ in range(4)]
        # 첫 페이지: limit=2, offset=0 — DESC라 가장 최근 등록 ids[-1], ids[-2]
        page1 = await store.list_for_user(_UID, limit=2, offset=0)
        assert [i.device_id for i in page1] == [ids[3], ids[2]]
        # 두 번째: offset=2 — ids[1], ids[0]
        page2 = await store.list_for_user(_UID, limit=2, offset=2)
        assert [i.device_id for i in page2] == [ids[1], ids[0]]
        # offset 초과 → 빈
        assert await store.list_for_user(_UID, limit=2, offset=10) == []

    async def test_since_until_filters_created_at(self) -> None:
        """slice 41: created_at 시간창 필터 — since/until 적용."""
        store = InMemoryDeviceStore()
        d1, _ = await store.register(_UID)
        d2, _ = await store.register(_UID)
        d3, _ = await store.register(_UID)
        # d2의 created_at을 1년 전·d3은 1주 전·d1은 현재
        now = datetime.now(UTC)
        creds = store._creds
        creds[d2] = creds[d2]._replace(created_at=now - timedelta(days=365))
        creds[d3] = creds[d3]._replace(created_at=now - timedelta(days=7))
        # since=30일 전 → d1 + d3
        infos = await store.list_for_user(_UID, since=now - timedelta(days=30))
        assert sorted(i.device_id for i in infos) == sorted([d1, d3])
        # until=14일 전 → d2만(365일 전)
        infos2 = await store.list_for_user(_UID, until=now - timedelta(days=14))
        assert [i.device_id for i in infos2] == [d2]
        # 시간창 [60일 전, 1일 전] → d3
        infos3 = await store.list_for_user(
            _UID,
            since=now - timedelta(days=60),
            until=now - timedelta(days=1),
        )
        assert [i.device_id for i in infos3] == [d3]
        # count도 동일 필터
        assert await store.count_for_user(_UID, since=now - timedelta(days=30)) == 2

    async def test_revoked_since_until_filters_revoked_at(self) -> None:
        """slice 43: revoked_since/until은 revoked_at 시간창 — 미폐기는 자동 제외."""
        store = InMemoryDeviceStore()
        d_active, _ = await store.register(_UID)
        d_old_revoked, _ = await store.register(_UID)
        d_recent_revoked, _ = await store.register(_UID)
        # d_old_revoked는 1년 전 폐기·d_recent_revoked는 어제 폐기·d_active는 미폐기
        await store.revoke(d_old_revoked, _UID)
        await store.revoke(d_recent_revoked, _UID)
        now = datetime.now(UTC)
        store._creds[d_old_revoked] = store._creds[d_old_revoked]._replace(
            revoked_at=now - timedelta(days=365)
        )
        store._creds[d_recent_revoked] = store._creds[d_recent_revoked]._replace(
            revoked_at=now - timedelta(days=1)
        )
        # include_revoked=True + revoked_since=30일전 → recent만(미폐기 d_active는
        # revoked_at=None이라 자동 제외)
        infos = await store.list_for_user(
            _UID, include_revoked=True, revoked_since=now - timedelta(days=30)
        )
        assert [i.device_id for i in infos] == [d_recent_revoked]
        # 시간창 [400일전, 100일전] → old만
        infos2 = await store.list_for_user(
            _UID,
            include_revoked=True,
            revoked_since=now - timedelta(days=400),
            revoked_until=now - timedelta(days=100),
        )
        assert [i.device_id for i in infos2] == [d_old_revoked]
        # count도 동일
        assert (
            await store.count_for_user(
                _UID, include_revoked=True, revoked_since=now - timedelta(days=30)
            )
            == 1
        )

    async def test_count_for_user_matches_list_filter(self) -> None:
        """slice 39: count_for_user는 list_for_user와 같은 필터(owner scope·include_revoked)."""
        store = InMemoryDeviceStore()
        for _ in range(3):
            await store.register(_UID)
        d_revoke, _ = await store.register(_UID)
        await store.revoke(d_revoke, _UID)
        other = uuid.uuid4()
        await store.register(other)
        # 본인 활성만 → 3
        assert await store.count_for_user(_UID) == 3
        # 본인 폐기 포함 → 4(other 제외)
        assert await store.count_for_user(_UID, include_revoked=True) == 4
        # 타인 user는 본인 활성 1
        assert await store.count_for_user(other) == 1


class TestInMemoryDeviceStoreLastUsedAt:
    """slice 32: verify 성공 시 last_used_at 갱신·revoke·실패는 갱신 안 함."""

    async def test_register_sets_last_used_at_none(self) -> None:
        """등록 직후엔 last_used_at=None(아직 verify 안 됨)."""
        store = InMemoryDeviceStore()
        await store.register(_UID)
        infos = await store.list_for_user(_UID)
        assert infos[0].last_used_at is None

    async def test_verify_success_updates_last_used_at(self) -> None:
        store = InMemoryDeviceStore()
        device_id, secret_plain = await store.register(_UID)
        sig = _sign(secret_plain, device_id)
        assert (await store.list_for_user(_UID))[0].last_used_at is None
        assert await store.verify(device_id, sig) is True
        # verify 성공 → last_used_at 채워짐
        infos = await store.list_for_user(_UID)
        assert infos[0].last_used_at is not None

    async def test_verify_failure_does_not_update_last_used_at(self) -> None:
        store = InMemoryDeviceStore()
        device_id, _secret = await store.register(_UID)
        assert await store.verify(device_id, "0" * 64) is False
        infos = await store.list_for_user(_UID)
        # 잘못된 sig → 갱신 안 됨(None 유지)
        assert infos[0].last_used_at is None

    async def test_verify_after_revoke_does_not_update(self) -> None:
        store = InMemoryDeviceStore()
        device_id, secret_plain = await store.register(_UID)
        sig = _sign(secret_plain, device_id)
        await store.verify(device_id, sig)  # 첫 갱신
        first = (await store.list_for_user(_UID))[0].last_used_at
        await store.revoke(device_id, _UID)
        # revoke 후 verify는 False → last_used_at 갱신 0(list는 빈 — revoked 제외)
        assert await store.verify(device_id, sig) is False
        assert await store.list_for_user(_UID) == []
        # 직접 dict 확인 — revoke가 last_used_at 건드리지 않음
        assert store._creds[device_id].last_used_at == first


class TestInMemoryDeviceStoreCleanupStale:
    """slice 33-34: N일 미사용 device 자동 폐기 — last_used_at(없으면 created_at) 기준.

    slice 34 시그너처: `cleanup_stale(max_age_days, *, dry_run=False) -> list[str]` —
    폐기된(또는 폐기될) device_id 목록 반환. `len(result)`로 건수 확인.
    """

    async def test_empty_returns_empty_list(self) -> None:
        store = InMemoryDeviceStore()
        assert await store.cleanup_stale(max_age_days=30) == []

    async def test_fresh_device_not_revoked(self) -> None:
        """방금 등록·verify → cleanup_stale은 빈 목록(최근 활동)."""
        store = InMemoryDeviceStore()
        device_id, secret_plain = await store.register(_UID)
        await store.verify(device_id, _sign(secret_plain, device_id))
        assert await store.cleanup_stale(max_age_days=30) == []
        # 활성 그대로
        assert not store._creds[device_id].revoked

    async def test_stale_by_last_used_at_revoked(self) -> None:
        """last_used_at이 임계 초과 → 폐기·반환 목록에 포함."""
        store = InMemoryDeviceStore()
        device_id, secret_plain = await store.register(_UID)
        await store.verify(device_id, _sign(secret_plain, device_id))
        # last_used_at을 *과거*로 강제(31일 전)
        cred = store._creds[device_id]
        store._creds[device_id] = cred._replace(
            last_used_at=datetime.now(UTC) - timedelta(days=31)
        )
        assert await store.cleanup_stale(max_age_days=30) == [device_id]
        assert store._creds[device_id].revoked is True

    async def test_stale_by_created_at_when_never_used(self) -> None:
        """한 번도 verify 안 됐고 created_at이 임계 초과 → 폐기(등록만 한 방치 device 차단)."""
        store = InMemoryDeviceStore()
        device_id, _ = await store.register(_UID)
        # created_at을 강제로 31일 전
        cred = store._creds[device_id]
        store._creds[device_id] = cred._replace(
            created_at=datetime.now(UTC) - timedelta(days=31)
        )
        assert await store.cleanup_stale(max_age_days=30) == [device_id]
        assert store._creds[device_id].revoked is True

    async def test_already_revoked_skipped(self) -> None:
        """이미 폐기된 device는 빈 목록(중복 폐기 안 함)."""
        store = InMemoryDeviceStore()
        device_id, _ = await store.register(_UID)
        await store.revoke(device_id, _UID)
        # created_at을 과거로 강제
        cred = store._creds[device_id]
        store._creds[device_id] = cred._replace(
            created_at=datetime.now(UTC) - timedelta(days=100)
        )
        assert await store.cleanup_stale(max_age_days=30) == []

    async def test_mixed_only_stale_revoked(self) -> None:
        store = InMemoryDeviceStore()
        d_fresh, secret_fresh = await store.register(_UID)
        await store.verify(d_fresh, _sign(secret_fresh, d_fresh))
        d_stale, _ = await store.register(_UID)
        cred_stale = store._creds[d_stale]
        store._creds[d_stale] = cred_stale._replace(
            created_at=datetime.now(UTC) - timedelta(days=31)
        )
        affected = await store.cleanup_stale(max_age_days=30)
        assert affected == [d_stale]
        assert store._creds[d_fresh].revoked is False
        assert store._creds[d_stale].revoked is True

    async def test_dry_run_returns_list_without_revoking(self) -> None:
        """slice 34: dry_run=True → 식별만·상태 변경 0(preview 패턴)."""
        store = InMemoryDeviceStore()
        device_id, _ = await store.register(_UID)
        cred = store._creds[device_id]
        store._creds[device_id] = cred._replace(
            created_at=datetime.now(UTC) - timedelta(days=31)
        )
        # 미리보기 → 목록 반환·실제 폐기 안 됨
        preview = await store.cleanup_stale(max_age_days=30, dry_run=True)
        assert preview == [device_id]
        assert store._creds[device_id].revoked is False
        # 실 실행 → 같은 device 폐기
        actual = await store.cleanup_stale(max_age_days=30, dry_run=False)
        assert actual == [device_id]
        assert store._creds[device_id].revoked is True


# ─────────────────────────────────────────────────────────────────────────────
# 3) _client_device_id store 모드 우선순위
# ─────────────────────────────────────────────────────────────────────────────


class TestClientDeviceIdStoreMode:
    """store 모드 우선 — 공유 secret 폴백·미설정·fail-safe 동작."""

    def _make_request(self, headers: dict[str, str]) -> Any:
        request = MagicMock()
        request.headers = headers
        return request

    async def test_store_registered_valid_sig_accepts(self) -> None:
        store = InMemoryDeviceStore()
        set_device_store(store)
        device_id, secret_plain = await store.register(_UID)
        sig = _sign(secret_plain, device_id)
        request = self._make_request({"x-device-id": device_id, "x-device-sig": sig})
        settings = _settings_override(device_hmac_secret="totally-different-secret")
        assert await _client_device_id(request, settings) == device_id

    async def test_store_unregistered_device_returns_none(self) -> None:
        store = InMemoryDeviceStore()
        set_device_store(store)
        request = self._make_request(
            {"x-device-id": "unregistered-id", "x-device-sig": "0" * 64}
        )
        settings = _settings_override()
        assert await _client_device_id(request, settings) is None

    async def test_store_invalid_sig_returns_none(self) -> None:
        store = InMemoryDeviceStore()
        set_device_store(store)
        device_id, _secret = await store.register(_UID)
        request = self._make_request(
            {"x-device-id": device_id, "x-device-sig": "0" * 64}
        )
        settings = _settings_override()
        assert await _client_device_id(request, settings) is None

    async def test_store_missing_sig_returns_none(self) -> None:
        store = InMemoryDeviceStore()
        set_device_store(store)
        device_id, _secret = await store.register(_UID)
        request = self._make_request({"x-device-id": device_id})
        settings = _settings_override()
        assert await _client_device_id(request, settings) is None

    async def test_store_revoked_device_returns_none(self) -> None:
        store = InMemoryDeviceStore()
        set_device_store(store)
        device_id, secret_plain = await store.register(_UID)
        sig = _sign(secret_plain, device_id)
        await store.revoke(device_id, _UID)
        request = self._make_request({"x-device-id": device_id, "x-device-sig": sig})
        settings = _settings_override()
        assert await _client_device_id(request, settings) is None

    async def test_store_takes_priority_over_shared_secret(self) -> None:
        """store + 공유 secret 둘 다 설정 → store 모드만 사용(공유 secret 분기 안 탐).

        검증: 공유 secret로 만든 *유효* 서명을 보내도, 그 device_id가 store에 등록 안 됐으면
        None(store 모드가 공유 secret 분기를 차단).
        """
        store = InMemoryDeviceStore()
        set_device_store(store)
        shared_secret = "shared-fallback-secret"
        device_id = "not-in-store"
        valid_for_shared = _expected_device_signature(shared_secret, device_id)
        request = self._make_request(
            {"x-device-id": device_id, "x-device-sig": valid_for_shared}
        )
        settings = _settings_override(device_hmac_secret=shared_secret)
        assert await _client_device_id(request, settings) is None

    async def test_store_none_falls_back_to_shared_secret(self) -> None:
        """store 미설정 시 slice 21 공유 secret 분기로 폴백."""
        set_device_store(None)
        shared_secret = "shared-fallback-secret"
        device_id = "any-device"
        valid_sig = _expected_device_signature(shared_secret, device_id)
        request = self._make_request(
            {"x-device-id": device_id, "x-device-sig": valid_sig}
        )
        settings = _settings_override(device_hmac_secret=shared_secret)
        assert await _client_device_id(request, settings) == device_id

    async def test_store_none_no_secret_falls_back_to_no_verify(self) -> None:
        """store·공유 secret 모두 없음 → slice 20 동작(검증 생략)."""
        set_device_store(None)
        request = self._make_request({"x-device-id": "any-device"})
        settings = _settings_override(device_hmac_secret="")
        assert await _client_device_id(request, settings) == "any-device"

    async def test_empty_device_id_header_returns_none(self) -> None:
        """X-Device-Id 공백 → None(스트립 후 빈 문자열은 비활성)."""
        store = InMemoryDeviceStore()
        set_device_store(store)
        request = self._make_request({"x-device-id": "   ", "x-device-sig": "abc"})
        settings = _settings_override()
        assert await _client_device_id(request, settings) is None

    async def test_missing_device_id_header_returns_none(self) -> None:
        store = InMemoryDeviceStore()
        set_device_store(store)
        request = self._make_request({})
        settings = _settings_override()
        assert await _client_device_id(request, settings) is None


# ─────────────────────────────────────────────────────────────────────────────
# 4b) 슬라이스 28 — `_client_device_id` 실패 분기 metric 기록
# ─────────────────────────────────────────────────────────────────────────────


class TestDeviceSigFailureMetrics:
    """`_client_device_id`의 4개 fail-safe 분기가 정확한 카운터 사유로 기록되는지.

    정상 경로(유효 sig)는 카운터 0 — spoofing 시도 시에만 발화.
    """

    def _make_request(self, headers: dict[str, str]) -> Any:
        request = MagicMock()
        request.headers = headers
        return request

    async def test_store_mode_no_sig_records_store_no_sig(self) -> None:
        store = InMemoryDeviceStore()
        set_device_store(store)
        device_id, _ = await store.register(_UID)
        request = self._make_request({"x-device-id": device_id})  # sig 누락
        await _client_device_id(request, _settings_override())
        assert get_device_sig_failures() == {"store_no_sig": 1}

    async def test_store_mode_invalid_sig_records_store_verify_failed(self) -> None:
        store = InMemoryDeviceStore()
        set_device_store(store)
        device_id, _ = await store.register(_UID)
        request = self._make_request(
            {"x-device-id": device_id, "x-device-sig": "0" * 64}
        )
        await _client_device_id(request, _settings_override())
        assert get_device_sig_failures() == {"store_verify_failed": 1}

    async def test_store_mode_unregistered_records_store_verify_failed(self) -> None:
        """미등록 device_id도 verify=False라 같은 사유(store_verify_failed)로 카운팅.

        store 관점에서 미등록·잘못된 sig·폐기는 모두 verify False — 카운터 의미는 *해당 분기*
        도달 여부. 세부 사유 분해는 OTel 후속 슬라이스에서.
        """
        store = InMemoryDeviceStore()
        set_device_store(store)
        request = self._make_request(
            {"x-device-id": "never-registered", "x-device-sig": "0" * 64}
        )
        await _client_device_id(request, _settings_override())
        assert get_device_sig_failures() == {"store_verify_failed": 1}

    async def test_shared_secret_no_sig_records_shared_no_sig(self) -> None:
        set_device_store(None)
        request = self._make_request({"x-device-id": "some-device"})  # sig 누락
        await _client_device_id(
            request, _settings_override(device_hmac_secret="any-secret")
        )
        assert get_device_sig_failures() == {"shared_no_sig": 1}

    async def test_shared_secret_invalid_sig_records_shared_invalid_sig(self) -> None:
        set_device_store(None)
        request = self._make_request(
            {"x-device-id": "some-device", "x-device-sig": "0" * 64}
        )
        await _client_device_id(
            request, _settings_override(device_hmac_secret="some-secret")
        )
        assert get_device_sig_failures() == {"shared_invalid_sig": 1}

    async def test_valid_store_sig_records_no_failure(self) -> None:
        """정상 sig — 카운터 0(spoofing 가시성 invariant: 정상 트래픽 노이즈 0)."""
        store = InMemoryDeviceStore()
        set_device_store(store)
        device_id, secret_plain = await store.register(_UID)
        sig = _sign(secret_plain, device_id)
        request = self._make_request({"x-device-id": device_id, "x-device-sig": sig})
        await _client_device_id(request, _settings_override())
        assert get_device_sig_failures() == {}

    async def test_valid_shared_sig_records_no_failure(self) -> None:
        set_device_store(None)
        secret = "valid-secret"
        device_id = "device-x"
        valid_sig = _expected_device_signature(secret, device_id)
        request = self._make_request(
            {"x-device-id": device_id, "x-device-sig": valid_sig}
        )
        await _client_device_id(request, _settings_override(device_hmac_secret=secret))
        assert get_device_sig_failures() == {}

    async def test_missing_device_id_header_no_failure_recorded(self) -> None:
        """X-Device-Id 누락은 slice 20 의미(비활성) — *공격 시도 아님*·카운터 0."""
        set_device_store(None)
        request = self._make_request({})
        await _client_device_id(request, _settings_override(device_hmac_secret="any"))
        assert get_device_sig_failures() == {}

    async def test_multiple_failures_accumulate_per_reason(self) -> None:
        """같은 사유 반복 시 카운터 누적. 다른 사유는 독립 키."""
        set_device_store(None)
        # 3회 shared_no_sig
        for _ in range(3):
            request = self._make_request({"x-device-id": "x"})
            await _client_device_id(request, _settings_override(device_hmac_secret="s"))
        # 2회 shared_invalid_sig
        for _ in range(2):
            request = self._make_request({"x-device-id": "x", "x-device-sig": "0" * 64})
            await _client_device_id(request, _settings_override(device_hmac_secret="s"))
        assert get_device_sig_failures() == {
            "shared_no_sig": 3,
            "shared_invalid_sig": 2,
        }

    def test_reset_clears_all_counters(self) -> None:
        from whymath_backend.api._device_metrics import (
            record_device_sig_failure as _record,
        )

        _record("store_no_sig")
        _record("shared_invalid_sig")
        assert get_device_sig_failures()["store_no_sig"] == 1
        reset_device_sig_failures()
        assert get_device_sig_failures() == {}


# ─────────────────────────────────────────────────────────────────────────────
# 5) CachedDeviceStore — verify 결과 Redis 캐시(슬라이스 26)
# ─────────────────────────────────────────────────────────────────────────────


class _FakeCacheClient:
    """좁은 Redis 가짜 — GET/SETEX/DEL만 지원. 호출 횟수 기록(검증용)."""

    def __init__(self) -> None:
        self.store: dict[str, str] = {}
        # 키별 마지막 SETEX TTL — 생성자 ttl_seconds 인자 결선 검증용
        self.ttls: dict[str, int] = {}
        self.get_calls: int = 0
        self.setex_calls: int = 0
        self.delete_calls: int = 0

    async def get(self, key: str) -> str | None:
        self.get_calls += 1
        return self.store.get(key)

    async def setex(self, key: str, seconds: int, value: str) -> None:
        self.setex_calls += 1
        self.store[key] = value
        self.ttls[key] = seconds

    async def delete(self, *keys: str) -> int:
        count = 0
        for key in keys:
            if key in self.store:
                del self.store[key]
                self.ttls.pop(key, None)
                count += 1
        self.delete_calls += 1
        return count


class _CountingInnerStore:
    """`DeviceCredentialStore` 인스턴스 — 호출 횟수 기록."""

    def __init__(self, inner: InMemoryDeviceStore) -> None:
        self._inner = inner
        self.verify_calls: int = 0
        self.revoke_calls: int = 0
        self.register_calls: int = 0
        self.list_calls: int = 0
        self.cleanup_calls: int = 0

    async def register(self, user_id: uuid.UUID) -> tuple[str, str]:
        self.register_calls += 1
        return await self._inner.register(user_id)

    async def verify(self, device_id: str, signature_hex: str) -> bool:
        self.verify_calls += 1
        return await self._inner.verify(device_id, signature_hex)

    async def revoke(self, device_id: str, owner_id: uuid.UUID) -> bool:
        self.revoke_calls += 1
        return await self._inner.revoke(device_id, owner_id)

    async def list_for_user(
        self,
        owner_id: uuid.UUID,
        *,
        include_revoked: bool = False,
        since: datetime | None = None,
        until: datetime | None = None,
        revoked_since: datetime | None = None,
        revoked_until: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Any:
        self.list_calls += 1
        return await self._inner.list_for_user(
            owner_id,
            include_revoked=include_revoked,
            since=since,
            until=until,
            revoked_since=revoked_since,
            revoked_until=revoked_until,
            limit=limit,
            offset=offset,
        )

    async def count_for_user(
        self,
        owner_id: uuid.UUID,
        *,
        include_revoked: bool = False,
        since: datetime | None = None,
        until: datetime | None = None,
        revoked_since: datetime | None = None,
        revoked_until: datetime | None = None,
    ) -> int:
        return await self._inner.count_for_user(
            owner_id,
            include_revoked=include_revoked,
            since=since,
            until=until,
            revoked_since=revoked_since,
            revoked_until=revoked_until,
        )

    async def cleanup_stale(
        self, max_age_days: int, *, dry_run: bool = False
    ) -> list[str]:
        self.cleanup_calls += 1
        return await self._inner.cleanup_stale(max_age_days, dry_run=dry_run)


class TestCachedDeviceStoreVerify:
    """캐시 hit/miss/실패 비캐시 + 상수시간 비교 + TTL 결선."""

    async def test_first_verify_misses_cache_calls_inner_and_sets(self) -> None:
        inner_real = InMemoryDeviceStore()
        device_id, secret_plain = await inner_real.register(_UID)
        sig = _sign(secret_plain, device_id)
        counter = _CountingInnerStore(inner_real)
        cache = _FakeCacheClient()
        store = CachedDeviceStore(counter, cache, ttl_seconds=60)
        # 1) 첫 verify — cache miss → inner 호출 → SETEX
        assert await store.verify(device_id, sig) is True
        assert counter.verify_calls == 1
        assert cache.get_calls == 1
        assert cache.setex_calls == 1
        # 캐시에 sig(lowercase)가 저장됐고 TTL 60
        assert cache.store["device_verify:" + device_id] == sig.lower()
        assert cache.ttls["device_verify:" + device_id] == 60

    async def test_second_verify_hits_cache_skips_inner(self) -> None:
        inner_real = InMemoryDeviceStore()
        device_id, secret_plain = await inner_real.register(_UID)
        sig = _sign(secret_plain, device_id)
        counter = _CountingInnerStore(inner_real)
        cache = _FakeCacheClient()
        store = CachedDeviceStore(counter, cache, ttl_seconds=60)
        await store.verify(device_id, sig)  # warm cache
        # 2) 두 번째 verify — cache hit → inner 호출 0
        before = counter.verify_calls
        assert await store.verify(device_id, sig) is True
        assert counter.verify_calls == before  # inner 호출 안 함

    async def test_invalid_signature_falls_through_to_inner(self) -> None:
        """캐시된 정당 sig와 다른 sig → 캐시 miss 등가(상수시간 비교 후 inner 위임)."""
        inner_real = InMemoryDeviceStore()
        device_id, secret_plain = await inner_real.register(_UID)
        sig = _sign(secret_plain, device_id)
        counter = _CountingInnerStore(inner_real)
        cache = _FakeCacheClient()
        store = CachedDeviceStore(counter, cache, ttl_seconds=60)
        await store.verify(device_id, sig)  # warm
        # 잘못된 sig → inner 호출 + False
        assert await store.verify(device_id, "0" * 64) is False
        assert counter.verify_calls == 2  # warm + 잘못된 시도 둘 다

    async def test_failure_not_cached(self) -> None:
        """잘못된 sig → inner False → SETEX 호출 안 됨(공격자가 캐시 자리 차지 못함)."""
        inner_real = InMemoryDeviceStore()
        device_id, _secret = await inner_real.register(_UID)
        counter = _CountingInnerStore(inner_real)
        cache = _FakeCacheClient()
        store = CachedDeviceStore(counter, cache, ttl_seconds=60)
        assert await store.verify(device_id, "0" * 64) is False
        assert cache.setex_calls == 0  # 실패는 캐시 안 함
        assert "device_verify:" + device_id not in cache.store

    async def test_unknown_device_not_cached(self) -> None:
        inner_real = InMemoryDeviceStore()
        counter = _CountingInnerStore(inner_real)
        cache = _FakeCacheClient()
        store = CachedDeviceStore(counter, cache, ttl_seconds=60)
        assert await store.verify("never-registered", "0" * 64) is False
        assert cache.setex_calls == 0

    async def test_uppercase_signature_cached_as_lowercase(self) -> None:
        """sig 대문자로 와도 inner.verify가 True면 lowercase로 캐시(정규화)."""
        inner_real = InMemoryDeviceStore()
        device_id, secret_plain = await inner_real.register(_UID)
        sig_upper = _sign(secret_plain, device_id).upper()
        counter = _CountingInnerStore(inner_real)
        cache = _FakeCacheClient()
        store = CachedDeviceStore(counter, cache, ttl_seconds=60)
        assert await store.verify(device_id, sig_upper) is True
        assert cache.store["device_verify:" + device_id] == sig_upper.lower()

    async def test_bytes_cached_value_handled(self) -> None:
        """Redis 클라이언트가 bytes 반환(decode_responses=False)해도 처리."""
        inner_real = InMemoryDeviceStore()
        device_id, secret_plain = await inner_real.register(_UID)
        sig = _sign(secret_plain, device_id)
        counter = _CountingInnerStore(inner_real)
        cache = _FakeCacheClient()
        # 캐시에 직접 bytes로 적재(SETEX 우회) — Redis bytes 응답 시뮬레이션
        cache.store["device_verify:" + device_id] = sig.lower()
        # _FakeCacheClient.get가 str을 반환하나, 실코드 분기 검증 위해 bytes 주입
        original_get = cache.get

        async def _get_as_bytes(key: str) -> bytes | None:
            val = await original_get(key)
            return val.encode("utf-8") if val is not None else None

        cache.get = _get_as_bytes  # type: ignore[method-assign]
        store = CachedDeviceStore(counter, cache, ttl_seconds=60)
        # bytes 반환을 decode 후 비교 → cache hit
        assert await store.verify(device_id, sig) is True
        assert counter.verify_calls == 0  # cache hit


class TestCachedDeviceStoreRevoke:
    """revoke는 inner 위임 + 성공 시 캐시 invalidate."""

    async def test_revoke_invalidates_cache(self) -> None:
        inner_real = InMemoryDeviceStore()
        device_id, secret_plain = await inner_real.register(_UID)
        sig = _sign(secret_plain, device_id)
        counter = _CountingInnerStore(inner_real)
        cache = _FakeCacheClient()
        store = CachedDeviceStore(counter, cache, ttl_seconds=60)
        await store.verify(device_id, sig)  # warm cache
        assert "device_verify:" + device_id in cache.store
        # slice 40: count 캐시도 미리 적재 — revoke가 두 키 모두 invalidate해야
        cache.store[f"device_count:{_UID}:active"] = "5"
        cache.store[f"device_count:{_UID}:all"] = "5"
        # revoke → DEL(verify + count active + count all)
        assert await store.revoke(device_id, _UID) is True
        assert "device_verify:" + device_id not in cache.store
        assert f"device_count:{_UID}:active" not in cache.store
        assert f"device_count:{_UID}:all" not in cache.store
        # 후속 verify → cache miss + inner는 False(revoked)
        before_verify = counter.verify_calls
        assert await store.verify(device_id, sig) is False
        assert counter.verify_calls == before_verify + 1

    async def test_revoke_failure_does_not_invalidate(self) -> None:
        """타인 소유 등 revoke False → DEL 호출 안 됨(캐시 보존)."""
        inner_real = InMemoryDeviceStore()
        device_id, secret_plain = await inner_real.register(_UID)
        sig = _sign(secret_plain, device_id)
        counter = _CountingInnerStore(inner_real)
        cache = _FakeCacheClient()
        store = CachedDeviceStore(counter, cache, ttl_seconds=60)
        await store.verify(device_id, sig)  # warm
        # 타인 owner_id로 폐기 시도 → False
        other = uuid.uuid4()
        assert await store.revoke(device_id, other) is False
        # 캐시 보존(여전히 cache hit)
        assert "device_verify:" + device_id in cache.store
        assert cache.delete_calls == 0


class TestCachedDeviceStoreRegister:
    """register는 inner 위임 + slice 40: count 캐시 invalidate(active·all 두 키)."""

    async def test_register_passthrough_invalidates_count_cache(self) -> None:
        inner_real = InMemoryDeviceStore()
        counter = _CountingInnerStore(inner_real)
        cache = _FakeCacheClient()
        store = CachedDeviceStore(counter, cache, ttl_seconds=60)
        # 미리 count 캐시 적재 — register가 invalidate해야 함
        cache.store[f"device_count:{_UID}:active"] = "5"
        cache.store[f"device_count:{_UID}:all"] = "5"
        device_id, secret_plain = await store.register(_UID)
        assert counter.register_calls == 1
        # slice 40: count 캐시 두 키 모두 DEL
        assert f"device_count:{_UID}:active" not in cache.store
        assert f"device_count:{_UID}:all" not in cache.store
        # verify 캐시는 무관(register는 verify 캐시 안 건드림)
        assert cache.get_calls == 0
        assert cache.setex_calls == 0
        # 라운드트립 검증 — 발급된 자격증명으로 verify True
        sig = _sign(secret_plain, device_id)
        assert await store.verify(device_id, sig) is True


class TestCachedDeviceStoreProtocolConformance:
    def test_satisfies_protocol(self) -> None:
        inner = InMemoryDeviceStore()
        cache = _FakeCacheClient()
        store = CachedDeviceStore(inner, cache, ttl_seconds=60)
        assert isinstance(store, DeviceCredentialStore)


class TestCachedDeviceStoreListForUser:
    """list_for_user는 캐시 무관 — 항상 inner 위임(목록 신선도 우선)."""

    async def test_list_passthrough_no_cache_access(self) -> None:
        inner_real = InMemoryDeviceStore()
        await inner_real.register(_UID)
        counter = _CountingInnerStore(inner_real)
        cache = _FakeCacheClient()
        store = CachedDeviceStore(counter, cache, ttl_seconds=60)
        # 두 번 호출 — inner는 두 번 호출됨(캐시 우회), cache는 0회 접근
        await store.list_for_user(_UID)
        await store.list_for_user(_UID)
        assert counter.list_calls == 2
        assert cache.get_calls == 0
        assert cache.setex_calls == 0
        assert cache.delete_calls == 0

    async def test_count_first_call_misses_cache_and_sets(self) -> None:
        """slice 40: 첫 호출 → cache miss → inner.count + SETEX."""
        inner_real = InMemoryDeviceStore()
        await inner_real.register(_UID)
        await inner_real.register(_UID)
        counter = _CountingInnerStore(inner_real)
        cache = _FakeCacheClient()
        store = CachedDeviceStore(counter, cache, ttl_seconds=60)
        assert await store.count_for_user(_UID) == 2
        # cache miss → GET 1회·inner 호출·SETEX 1회
        assert cache.get_calls == 1
        assert counter.cleanup_calls == 0
        assert cache.setex_calls == 1
        # 캐시 키 형식: device_count:{uid}:active
        assert cache.store[f"device_count:{_UID}:active"] == "2"

    async def test_count_second_call_hits_cache_skips_inner(self) -> None:
        """slice 40: 두 번째 호출 → cache hit → inner.count_for_user 호출 안 함."""
        inner_real = InMemoryDeviceStore()
        await inner_real.register(_UID)
        counter = _CountingInnerStore(inner_real)
        cache = _FakeCacheClient()
        store = CachedDeviceStore(counter, cache, ttl_seconds=60)
        # warm
        await store.count_for_user(_UID)
        # 2번째 호출 — inner.count 호출 안 함
        cached_result = await store.count_for_user(_UID)
        assert cached_result == 1
        # SETEX는 첫 호출 1회만(2번째는 캐시 hit)
        assert cache.setex_calls == 1

    async def test_count_include_revoked_uses_separate_key(self) -> None:
        """slice 40: include_revoked=True/False는 별 캐시 키(active/all)."""
        inner_real = InMemoryDeviceStore()
        await inner_real.register(_UID)
        d_revoke, _ = await inner_real.register(_UID)
        await inner_real.revoke(d_revoke, _UID)
        counter = _CountingInnerStore(inner_real)
        cache = _FakeCacheClient()
        store = CachedDeviceStore(counter, cache, ttl_seconds=60)
        # 활성: 1
        assert await store.count_for_user(_UID, include_revoked=False) == 1
        # 폐기 포함: 2 — 별 키
        assert await store.count_for_user(_UID, include_revoked=True) == 2
        # 두 키가 *별도로* 캐시됨
        assert cache.store[f"device_count:{_UID}:active"] == "1"
        assert cache.store[f"device_count:{_UID}:all"] == "2"

    async def test_count_with_since_until_bypasses_cache(self) -> None:
        """slice 41: since/until 필터 있으면 캐시 우회 — 매 호출 inner.count."""
        inner_real = InMemoryDeviceStore()
        await inner_real.register(_UID)
        counter = _CountingInnerStore(inner_real)
        cache = _FakeCacheClient()
        store = CachedDeviceStore(counter, cache, ttl_seconds=60)
        now = datetime.now(UTC)
        await store.count_for_user(_UID, since=now - timedelta(days=30))
        # 캐시 미접근(시간창 시 우회 경로)
        assert cache.get_calls == 0
        assert cache.setex_calls == 0
        # 두 번째 호출도 inner 호출(캐시 안 함)
        await store.count_for_user(_UID, since=now - timedelta(days=30))
        assert cache.get_calls == 0

    async def test_count_cache_bytes_response(self) -> None:
        """slice 40: redis decode_responses=False(bytes 반환)도 처리."""
        inner_real = InMemoryDeviceStore()
        await inner_real.register(_UID)
        counter = _CountingInnerStore(inner_real)
        cache = _FakeCacheClient()
        # bytes로 미리 캐시
        cache.store[f"device_count:{_UID}:active"] = "1"
        # get을 bytes 반환으로 monkey
        original_get = cache.get

        async def _get_bytes(key: str) -> bytes | None:
            val = await original_get(key)
            return val.encode("utf-8") if isinstance(val, str) else val

        cache.get = _get_bytes  # type: ignore[method-assign]
        store = CachedDeviceStore(counter, cache, ttl_seconds=60)
        # bytes → utf-8 decode → int(1)
        assert await store.count_for_user(_UID) == 1


class TestCachedDeviceStoreTTL:
    async def test_ttl_seconds_passed_to_setex(self) -> None:
        """생성자 ttl_seconds 인자가 SETEX 호출의 TTL로 전달되는지."""
        inner_real = InMemoryDeviceStore()
        device_id, secret_plain = await inner_real.register(_UID)
        sig = _sign(secret_plain, device_id)
        counter = _CountingInnerStore(inner_real)
        cache = _FakeCacheClient()
        store = CachedDeviceStore(counter, cache, ttl_seconds=42)
        await store.verify(device_id, sig)
        assert cache.ttls["device_verify:" + device_id] == 42


# ─────────────────────────────────────────────────────────────────────────────
# 6) build_device_store_from_settings — lifespan 결선(슬라이스 27)
# ─────────────────────────────────────────────────────────────────────────────


def _lifespan_settings(
    mode: str,
    timeout_seconds: float = 5.0,
    max_retries: int = 1,
    backoff_seconds: float = 0.001,
    jitter: bool = False,
) -> Settings:
    """slice 35: 테스트 기본은 `max_retries=1`(재시도 비활성·기존 timeout 테스트 ~0s) +
    `backoff=0.001s`(재시도 테스트의 sleep 거의 0). slice 36: jitter 기본 False(결정론적·
    기존 테스트 영향 0)."""
    return Settings(
        jwt_secret_key=SecretStr("test-secret-0123456789abcdef"),
        device_store_mode=mode,  # type: ignore[arg-type]
        device_store_health_check_timeout_seconds=timeout_seconds,
        device_store_health_check_max_retries=max_retries,
        device_store_health_check_retry_backoff_seconds=backoff_seconds,
        device_store_health_check_retry_jitter=jitter,
    )


class TestBuildDeviceStoreFromSettings:
    """모드 3종 × cleanup 책임 — `_DEVICE_STORE` 모듈 전역은 *호출자 책임*(본 함수 순수)."""

    async def test_none_mode_returns_none_and_noop(self) -> None:
        store, cleanup = build_device_store_from_settings(_lifespan_settings("none"))
        assert store is None
        # cleanup은 async no-op — 예외 없이 await 가능
        await cleanup()

    async def test_pg_mode_returns_pg_store_and_noop(self) -> None:
        # PgDeviceStore는 sessionmaker만 받고 *connect 안 함* — 라이브 PG 없어도 안전
        store, cleanup = build_device_store_from_settings(_lifespan_settings("pg"))
        assert isinstance(store, PgDeviceStore)
        await cleanup()  # noop

    async def test_pg_cached_mode_returns_cached_store_and_closes_redis(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """pg_cached: Redis 클라이언트 생성 → CachedDeviceStore 래핑 → cleanup이 aclose 호출."""
        import whymath_backend.api._device_store as ds_mod

        # _build_redis_for_cache을 가짜로 — 실 Redis 의존성 회피
        aclose_called: dict[str, bool] = {"called": False}

        class _FakeAcloseable:
            async def get(self, key: str) -> str | None:
                return None

            async def setex(self, key: str, seconds: int, value: str) -> None:
                pass

            async def delete(self, *keys: str) -> int:
                return 0

            async def aclose(self) -> None:
                aclose_called["called"] = True

        monkeypatch.setattr(
            ds_mod, "_build_redis_for_cache", lambda settings: _FakeAcloseable()
        )

        store, cleanup = build_device_store_from_settings(
            _lifespan_settings("pg_cached")
        )
        assert isinstance(store, CachedDeviceStore)
        await cleanup()
        assert aclose_called["called"] is True

    async def test_pg_cached_cleanup_safe_when_aclose_missing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """aclose 미정의 fake 클라이언트도 cleanup이 예외 없이 통과(고대 redis 라이브러리 호환)."""
        import whymath_backend.api._device_store as ds_mod

        class _NoAcloseClient:
            async def get(self, key: str) -> str | None:
                return None

            async def setex(self, key: str, seconds: int, value: str) -> None:
                pass

            async def delete(self, *keys: str) -> int:
                return 0

        monkeypatch.setattr(
            ds_mod, "_build_redis_for_cache", lambda settings: _NoAcloseClient()
        )

        _store, cleanup = build_device_store_from_settings(
            _lifespan_settings("pg_cached")
        )
        await cleanup()  # 예외 없이 종료


class TestLifespanWiring:
    """`create_app` 라이프스팬이 startup에서 store 활성·shutdown에서 해제."""

    def test_lifespan_with_none_mode_keeps_store_none(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """기본 모드(none) — startup 후에도 `_DEVICE_STORE`는 None."""
        from whymath_backend.config import get_settings as real_get_settings

        monkeypatch.setattr(
            "whymath_backend.app.get_settings",
            lambda: _lifespan_settings("none"),
            raising=True,
        )
        # 라이프스팬 발화 위해 컨텍스트매니저 사용
        with TestClient(create_app()):
            assert get_device_store() is None
        # shutdown 후에도 None
        assert get_device_store() is None
        _ = real_get_settings  # silence unused import

    def test_lifespan_with_pg_mode_activates_pg_store(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """pg 모드 — startup에서 `_DEVICE_STORE`가 PgDeviceStore, shutdown 후 None.

        slice 30: PG ping을 monkeypatch — 본 테스트는 lifespan 결선만 검증·실 PG 무관.
        """
        monkeypatch.setattr(
            "whymath_backend.app.get_settings",
            lambda: _lifespan_settings("pg"),
            raising=True,
        )

        async def _noop_ping(_settings: Any) -> None:
            return None

        monkeypatch.setattr(
            "whymath_backend.app.ping_device_store_health", _noop_ping, raising=True
        )
        with TestClient(create_app()):
            store = get_device_store()
            assert isinstance(store, PgDeviceStore)
        # 종료 후 해제됨
        assert get_device_store() is None


# ─────────────────────────────────────────────────────────────────────────────
# 6b) 슬라이스 30 — ping_device_store_health (startup health check)
# ─────────────────────────────────────────────────────────────────────────────


class TestPingDeviceStoreHealth:
    """모드별 ping 동작 + 실패 시 RuntimeError(메시지에 어느 구성요소·폴백 안내)."""

    async def test_none_mode_skips_ping(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """none 모드 — PG/Redis 미도달이어도 ping 안 함(slice 21 폴백 동작 보존)."""
        from whymath_backend.api import _device_store as ds_mod

        called: dict[str, bool] = {"sm": False, "redis": False}

        def _spy_sm(_s: Any) -> Any:
            called["sm"] = True
            raise AssertionError("none 모드는 sessionmaker 호출 안 해야 함")

        monkeypatch.setattr(
            "whymath_backend.db.session.get_sessionmaker", _spy_sm, raising=True
        )
        monkeypatch.setattr(
            ds_mod,
            "_build_redis_for_cache",
            lambda s: (_ for _ in ()).throw(
                AssertionError("none 모드는 Redis 빌더 호출 안 해야 함")
            ),
        )
        # 예외 없이 통과
        await ds_mod.ping_device_store_health(_lifespan_settings("none"))
        assert called["sm"] is False

    async def test_pg_mode_pings_pg_only(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from whymath_backend.api import _device_store as ds_mod

        execute_called: dict[str, bool] = {"hit": False}

        class _OkSession:
            async def __aenter__(self) -> _OkSession:
                return self

            async def __aexit__(self, *_e: Any) -> None:
                pass

            async def execute(self, _stmt: Any) -> None:
                execute_called["hit"] = True

        def _ok_sm(_s: Any) -> Any:
            return lambda: _OkSession()

        monkeypatch.setattr(
            "whymath_backend.db.session.get_sessionmaker", _ok_sm, raising=True
        )
        # pg 모드는 Redis 빌더 호출 0
        monkeypatch.setattr(
            ds_mod,
            "_build_redis_for_cache",
            lambda s: (_ for _ in ()).throw(
                AssertionError("pg 모드는 Redis 빌더 호출 안 해야 함")
            ),
        )
        await ds_mod.ping_device_store_health(_lifespan_settings("pg"))
        assert execute_called["hit"] is True

    async def test_pg_mode_unreachable_raises_runtime_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from whymath_backend.api import _device_store as ds_mod

        def _bad_sm(_s: Any) -> Any:
            class _BadSession:
                async def __aenter__(self) -> _BadSession:
                    raise ConnectionError("PG down")

                async def __aexit__(self, *_e: Any) -> None:
                    pass

            return lambda: _BadSession()

        monkeypatch.setattr(
            "whymath_backend.db.session.get_sessionmaker", _bad_sm, raising=True
        )
        with pytest.raises(RuntimeError, match="PostgreSQL 미도달"):
            await ds_mod.ping_device_store_health(_lifespan_settings("pg"))

    async def test_pg_cached_mode_pings_both(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from whymath_backend.api import _device_store as ds_mod

        class _OkSession:
            async def __aenter__(self) -> _OkSession:
                return self

            async def __aexit__(self, *_e: Any) -> None:
                pass

            async def execute(self, _stmt: Any) -> None:
                pass

        ping_calls: dict[str, int] = {"count": 0, "aclose": 0}

        class _OkRedis:
            async def ping(self) -> bool:
                ping_calls["count"] += 1
                return True

            async def get(self, _k: str) -> None:
                return None

            async def setex(self, _k: str, _s: int, _v: str) -> None:
                pass

            async def delete(self, *_k: str) -> int:
                return 0

            async def aclose(self) -> None:
                ping_calls["aclose"] += 1

        monkeypatch.setattr(
            "whymath_backend.db.session.get_sessionmaker",
            lambda _s: (lambda: _OkSession()),
            raising=True,
        )
        monkeypatch.setattr(ds_mod, "_build_redis_for_cache", lambda _s: _OkRedis())
        await ds_mod.ping_device_store_health(_lifespan_settings("pg_cached"))
        assert ping_calls["count"] == 1
        # aclose 호출됐는지(연결 leak 0)
        assert ping_calls["aclose"] == 1

    async def test_pg_cached_redis_without_aclose_safe(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """aclose 미정의 Redis 클라이언트(고대 redis-py 호환) — finally가 안전 통과."""
        from whymath_backend.api import _device_store as ds_mod

        class _OkSession:
            async def __aenter__(self) -> _OkSession:
                return self

            async def __aexit__(self, *_e: Any) -> None:
                pass

            async def execute(self, _stmt: Any) -> None:
                pass

        class _NoAcloseRedis:
            async def ping(self) -> bool:
                return True

            async def get(self, _k: str) -> None:
                return None

            async def setex(self, _k: str, _s: int, _v: str) -> None:
                pass

            async def delete(self, *_k: str) -> int:
                return 0

        monkeypatch.setattr(
            "whymath_backend.db.session.get_sessionmaker",
            lambda _s: (lambda: _OkSession()),
            raising=True,
        )
        monkeypatch.setattr(
            ds_mod, "_build_redis_for_cache", lambda _s: _NoAcloseRedis()
        )
        # 예외 없이 통과
        await ds_mod.ping_device_store_health(_lifespan_settings("pg_cached"))

    async def test_pg_cached_mode_redis_unreachable_raises_and_closes(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Redis 미도달 시 RuntimeError·aclose는 *여전히* 호출(연결 leak 0)."""
        from whymath_backend.api import _device_store as ds_mod

        class _OkSession:
            async def __aenter__(self) -> _OkSession:
                return self

            async def __aexit__(self, *_e: Any) -> None:
                pass

            async def execute(self, _stmt: Any) -> None:
                pass

        aclose_called: dict[str, bool] = {"hit": False}

        class _BadRedis:
            async def ping(self) -> None:
                raise ConnectionError("Redis down")

            async def get(self, _k: str) -> None:
                return None

            async def setex(self, _k: str, _s: int, _v: str) -> None:
                pass

            async def delete(self, *_k: str) -> int:
                return 0

            async def aclose(self) -> None:
                aclose_called["hit"] = True

        monkeypatch.setattr(
            "whymath_backend.db.session.get_sessionmaker",
            lambda _s: (lambda: _OkSession()),
            raising=True,
        )
        monkeypatch.setattr(ds_mod, "_build_redis_for_cache", lambda _s: _BadRedis())
        with pytest.raises(RuntimeError, match="Redis 미도달"):
            await ds_mod.ping_device_store_health(_lifespan_settings("pg_cached"))
        # ping 실패에도 cleanup 보장
        assert aclose_called["hit"] is True

    async def test_pg_ping_timeout_raises_runtime_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """slice 31: PG ping이 timeout 초과 시 RuntimeError(timeout 메시지 명시)."""
        import asyncio as _asyncio

        from whymath_backend.api import _device_store as ds_mod

        class _HangingSession:
            async def __aenter__(self) -> _HangingSession:
                return self

            async def __aexit__(self, *_e: Any) -> None:
                pass

            async def execute(self, _stmt: Any) -> None:
                # 무한 대기 — asyncio.timeout이 cancel
                await _asyncio.sleep(60)

        monkeypatch.setattr(
            "whymath_backend.db.session.get_sessionmaker",
            lambda _s: (lambda: _HangingSession()),
            raising=True,
        )
        # timeout 0.01s — 즉시 발화
        with pytest.raises(RuntimeError, match="PostgreSQL ping.*응답 없음"):
            await ds_mod.ping_device_store_health(
                _lifespan_settings("pg", timeout_seconds=0.01)
            )

    async def test_redis_ping_timeout_raises_runtime_error_and_closes(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """slice 31: Redis ping timeout 시 RuntimeError + aclose 여전히 호출."""
        import asyncio as _asyncio

        from whymath_backend.api import _device_store as ds_mod

        class _OkSession:
            async def __aenter__(self) -> _OkSession:
                return self

            async def __aexit__(self, *_e: Any) -> None:
                pass

            async def execute(self, _stmt: Any) -> None:
                pass

        aclose_called: dict[str, bool] = {"hit": False}

        class _HangingRedis:
            async def ping(self) -> None:
                await _asyncio.sleep(60)

            async def get(self, _k: str) -> None:
                return None

            async def setex(self, _k: str, _s: int, _v: str) -> None:
                pass

            async def delete(self, *_k: str) -> int:
                return 0

            async def aclose(self) -> None:
                aclose_called["hit"] = True

        monkeypatch.setattr(
            "whymath_backend.db.session.get_sessionmaker",
            lambda _s: (lambda: _OkSession()),
            raising=True,
        )
        monkeypatch.setattr(
            ds_mod, "_build_redis_for_cache", lambda _s: _HangingRedis()
        )
        with pytest.raises(RuntimeError, match="Redis ping.*응답 없음"):
            await ds_mod.ping_device_store_health(
                _lifespan_settings("pg_cached", timeout_seconds=0.01)
            )
        # timeout 시에도 cleanup 보장(연결 leak 0)
        assert aclose_called["hit"] is True

    async def test_pg_ping_retries_then_succeeds(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """slice 35: PG ping 첫 2회 실패·3회째 성공 → ping_device_store_health 통과."""
        from whymath_backend.api import _device_store as ds_mod

        attempt_count = {"n": 0}

        class _FlakySession:
            async def __aenter__(self) -> _FlakySession:
                return self

            async def __aexit__(self, *_e: Any) -> None:
                pass

            async def execute(self, _stmt: Any) -> None:
                attempt_count["n"] += 1
                if attempt_count["n"] < 3:
                    raise ConnectionError("transient PG flake")
                # 3회째 성공

        monkeypatch.setattr(
            "whymath_backend.db.session.get_sessionmaker",
            lambda _s: (lambda: _FlakySession()),
            raising=True,
        )
        # max_retries=3, backoff=0.001s — 첫 2회 실패 후 3회째 성공
        await ds_mod.ping_device_store_health(
            _lifespan_settings("pg", max_retries=3, backoff_seconds=0.001)
        )
        assert attempt_count["n"] == 3

    async def test_pg_ping_all_retries_fail_raises_runtime_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """slice 35: 모든 재시도 실패 → 메시지에 '재시도 N회' 명시."""
        from whymath_backend.api import _device_store as ds_mod

        attempt_count = {"n": 0}

        class _AlwaysBadSession:
            async def __aenter__(self) -> _AlwaysBadSession:
                return self

            async def __aexit__(self, *_e: Any) -> None:
                pass

            async def execute(self, _stmt: Any) -> None:
                attempt_count["n"] += 1
                raise ConnectionError("PG down")

        monkeypatch.setattr(
            "whymath_backend.db.session.get_sessionmaker",
            lambda _s: (lambda: _AlwaysBadSession()),
            raising=True,
        )
        with pytest.raises(RuntimeError, match="재시도 3회"):
            await ds_mod.ping_device_store_health(
                _lifespan_settings("pg", max_retries=3, backoff_seconds=0.001)
            )
        # 정확히 3회 시도(첫 1회 + 재시도 2회)
        assert attempt_count["n"] == 3

    async def test_redis_ping_retries_then_succeeds(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """slice 35: Redis ping 일시 실패 후 재시도 성공·aclose는 한 번만 호출."""
        from whymath_backend.api import _device_store as ds_mod

        class _OkSession:
            async def __aenter__(self) -> _OkSession:
                return self

            async def __aexit__(self, *_e: Any) -> None:
                pass

            async def execute(self, _stmt: Any) -> None:
                pass

        ping_attempts = {"n": 0}
        aclose_count = {"n": 0}

        class _FlakyRedis:
            async def ping(self) -> bool:
                ping_attempts["n"] += 1
                if ping_attempts["n"] < 2:
                    raise ConnectionError("transient Redis flake")
                return True

            async def get(self, _k: str) -> None:
                return None

            async def setex(self, _k: str, _s: int, _v: str) -> None:
                pass

            async def delete(self, *_k: str) -> int:
                return 0

            async def aclose(self) -> None:
                aclose_count["n"] += 1

        monkeypatch.setattr(
            "whymath_backend.db.session.get_sessionmaker",
            lambda _s: (lambda: _OkSession()),
            raising=True,
        )
        monkeypatch.setattr(ds_mod, "_build_redis_for_cache", lambda _s: _FlakyRedis())
        # 첫 1회 실패·2회째 성공
        await ds_mod.ping_device_store_health(
            _lifespan_settings("pg_cached", max_retries=2, backoff_seconds=0.001)
        )
        assert ping_attempts["n"] == 2
        # aclose는 *최종* finally에서 한 번만 호출(per-attempt 호출 0)
        assert aclose_count["n"] == 1

    async def test_jitter_disabled_uses_deterministic_backoff(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """slice 36: jitter=False(기본) → `random.uniform` 호출 안 함·sleep 인자는 deterministic."""
        from whymath_backend.api import _device_store as ds_mod

        attempt = {"n": 0}

        class _FlakySession:
            async def __aenter__(self) -> _FlakySession:
                return self

            async def __aexit__(self, *_e: Any) -> None:
                pass

            async def execute(self, _stmt: Any) -> None:
                attempt["n"] += 1
                if attempt["n"] < 2:
                    raise ConnectionError("flake")

        sleep_args: list[float] = []

        async def _spy_sleep(delay: float) -> None:
            sleep_args.append(delay)

        uniform_called = {"hit": False}

        def _spy_uniform(_a: float, _b: float) -> float:
            uniform_called["hit"] = True
            return 0.0

        monkeypatch.setattr("asyncio.sleep", _spy_sleep)
        monkeypatch.setattr("random.uniform", _spy_uniform)
        monkeypatch.setattr(
            "whymath_backend.db.session.get_sessionmaker",
            lambda _s: (lambda: _FlakySession()),
            raising=True,
        )
        await ds_mod.ping_device_store_health(
            _lifespan_settings("pg", max_retries=2, backoff_seconds=2.0, jitter=False)
        )
        # jitter=False → uniform 호출 0
        assert uniform_called["hit"] is False
        # sleep은 정확히 backoff * 2^0 = 2.0
        assert sleep_args == [2.0]

    async def test_jitter_enabled_uses_uniform_random(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """slice 36: jitter=True → `random.uniform(0, base)` 호출·sleep 인자는 그 결과."""
        from whymath_backend.api import _device_store as ds_mod

        attempt = {"n": 0}

        class _FlakySession:
            async def __aenter__(self) -> _FlakySession:
                return self

            async def __aexit__(self, *_e: Any) -> None:
                pass

            async def execute(self, _stmt: Any) -> None:
                attempt["n"] += 1
                if attempt["n"] < 3:
                    raise ConnectionError("flake")

        sleep_args: list[float] = []
        uniform_calls: list[tuple[float, float]] = []

        async def _spy_sleep(delay: float) -> None:
            sleep_args.append(delay)

        def _stub_uniform(low: float, high: float) -> float:
            uniform_calls.append((low, high))
            return high * 0.5  # mid-range — 결정론적 테스트

        monkeypatch.setattr("asyncio.sleep", _spy_sleep)
        monkeypatch.setattr("random.uniform", _stub_uniform)
        monkeypatch.setattr(
            "whymath_backend.db.session.get_sessionmaker",
            lambda _s: (lambda: _FlakySession()),
            raising=True,
        )
        await ds_mod.ping_device_store_health(
            _lifespan_settings("pg", max_retries=3, backoff_seconds=2.0, jitter=True)
        )
        # 첫 2회 실패 → uniform 2회 호출(attempt=0,1)
        # base=2.0*2^0=2.0, 2.0*2^1=4.0
        assert uniform_calls == [(0.0, 2.0), (0.0, 4.0)]
        # sleep 인자는 uniform 반환값(mid-range = high*0.5)
        assert sleep_args == [1.0, 2.0]


# ─────────────────────────────────────────────────────────────────────────────
# 4) PgDeviceStore — hermetic(가짜 AsyncSession), 실 PG는 통합 테스트
# ─────────────────────────────────────────────────────────────────────────────


class _FakePgSession:
    """SQLAlchemy AsyncSession 가짜 — PgDeviceStore가 호출하는 메서드만 모사.

    내부 `_store: dict[device_id → DeviceCredential]`로 테이블을 표현. `add`/`get`/`commit`은
    자명. `execute(update(...))`는 stmt의 whereclause·values를 *compile* 결과로 들춰 직접
    dict에 반영(SQLAlchemy 내부 구조를 흉내내지 않고 compile/literal_binds로 안전 추출).
    """

    def __init__(self, store: dict[str, Any]) -> None:
        self._store = store

    async def __aenter__(self) -> _FakePgSession:
        return self

    async def __aexit__(self, *_exc: Any) -> None:
        pass

    def add(self, obj: Any) -> None:
        # DeviceCredential 인스턴스의 PK로 적재
        self._store[obj.device_id] = obj

    async def commit(self) -> None:
        pass

    async def get(self, _model: Any, pk: Any) -> Any:
        return self._store.get(pk)

    async def execute(self, stmt: Any) -> Any:
        """update/select 두 분기 처리 + 가짜 result.

        slice 24 — UPDATE: where(단일 BinaryExpression 또는 AND BooleanClauseList) +
        values 적용. slice 29 — SELECT: where 필터링 + 옵션 ORDER BY → 가짜 `.all()`로
        매칭 행 튜플 반환. select는 컬럼 매니페스트(`stmt._raw_columns`)에서 컬럼명을
        뽑아 매칭 행의 해당 속성을 튜플로 조립.
        """
        if hasattr(stmt, "_values"):  # Update
            return self._exec_update(stmt)
        return self._exec_select(stmt)  # Select

    def _exec_update(self, stmt: Any) -> Any:
        constraints = self._iter_eq_constraints(stmt.whereclause)
        values_to_set: dict[Any, Any] = dict(stmt._values)
        target_device_id = constraints.get("device_id")
        existing = (
            self._store.get(target_device_id) if target_device_id is not None else None
        )
        if existing is not None:
            for col_name, expected_value in constraints.items():
                if col_name == "device_id":
                    continue
                if getattr(existing, col_name, None) != expected_value:
                    existing = None
                    break
        rowcount = 0
        if existing is not None:
            for col, bind in values_to_set.items():
                col_name = col.key if hasattr(col, "key") else str(col)
                raw_value = bind.value if hasattr(bind, "value") else bind
                setattr(existing, col_name, raw_value)
            rowcount = 1

        class _Result:
            def __init__(self, rc: int) -> None:
                self.rowcount = rc

        return _Result(rowcount)

    def _exec_select(self, stmt: Any) -> Any:
        """slice 29 — `select(c1, c2).where(...).order_by(c.desc())` 시뮬.

        slice 38: `.limit(N).offset(M)` 처리 — stmt._limit_clause·_offset_clause의
        BindParameter.value를 추출해 슬라이스 적용.

        slice 41: where 절을 *재귀 row-matcher*로 평가 — eq/is_뿐 아니라 `>=`/`<=`
        연산자도 처리(operator.__name__ dispatch). created_at >= since 등 시간창 필터 호환.
        """
        matched = [
            row
            for row in self._store.values()
            if self._row_matches(row, stmt.whereclause)
        ]
        order_clauses = getattr(stmt, "_order_by_clauses", ())
        if order_clauses:
            matched.sort(key=lambda r: r.created_at, reverse=True)
        # slice 38: LIMIT/OFFSET 적용(BindParameter에서 값 추출)
        limit_clause = getattr(stmt, "_limit_clause", None)
        offset_clause = getattr(stmt, "_offset_clause", None)
        offset_val = (
            getattr(offset_clause, "value", 0) if offset_clause is not None else 0
        )
        limit_val = (
            getattr(limit_clause, "value", None) if limit_clause is not None else None
        )
        if limit_val is not None:
            matched = matched[offset_val : offset_val + limit_val]
        elif offset_val:
            matched = matched[offset_val:]
        # slice 39: COUNT(*) 쿼리 처리 — _raw_columns 중 .key가 None/없는 표현(func.count())
        # 이 있으면 매칭 행 *개수*를 단일 행 [(N,)]로 반환·`result.scalar()` 호환.
        col_names = [c.key for c in stmt._raw_columns if getattr(c, "key", None)]
        has_count = any(not getattr(c, "key", None) for c in stmt._raw_columns)
        if has_count:
            rows: list[Any] = [(len(matched),)]
        else:
            rows = [tuple(getattr(r, n) for n in col_names) for r in matched]

        class _SelectResult:
            def __init__(self, data: list[Any]) -> None:
                self._data = data

            def all(self) -> list[Any]:
                return self._data

            def scalar(self) -> Any:
                if not self._data:
                    return None
                first = self._data[0]
                return first[0] if isinstance(first, tuple) else first

        return _SelectResult(rows)

    @staticmethod
    def _iter_eq_constraints(where: Any) -> dict[str, Any]:
        """whereclause에서 `col == value` 등식들을 dict로 추출. AND 결합 재귀.

        slice 24-40용 — eq/is_만 지원. slice 41은 일반화된 `_row_matches`로 대체.
        """
        result: dict[str, Any] = {}
        if hasattr(where, "left") and hasattr(where, "right"):
            col_name = where.left.key if hasattr(where.left, "key") else str(where.left)
            value = where.right.value if hasattr(where.right, "value") else where.right
            result[col_name] = value
            return result
        for child in getattr(where, "clauses", []):
            result.update(_FakePgSession._iter_eq_constraints(child))
        return result

    @staticmethod
    def _row_matches(row: Any, where: Any) -> bool:
        """slice 41: row를 where 절에 대해 *재귀* 평가 — eq/is_·>=·<= 등 다양한 연산자 처리.

        SQLAlchemy 2.0 `BinaryExpression.operator`는 호출 가능한 비교 함수(operator.eq·
        operator.ge·sqlalchemy.sql.operators.is_ 등). `__name__`으로 dispatch — 알려진
        연산자(`eq`/`ge`/`le`/`lt`/`gt`/`ne`/`is_`)는 Python 비교로 평가·미지원은 안전 True
        (matched로 falsy 안 만들고 후속 슬라이스가 확장).
        """
        from operator import eq, ge, gt, le, lt, ne

        op_dispatch: dict[str, Any] = {
            "eq": eq,
            "ne": ne,
            "ge": ge,
            "le": le,
            "lt": lt,
            "gt": gt,
            "is_": eq,  # is_(False) → eq(actual, False)와 같은 의미(hermetic)
        }

        if where is None:
            return True
        # BooleanClauseList(AND) — children 모두 만족
        if hasattr(where, "clauses"):
            return all(
                _FakePgSession._row_matches(row, child) for child in where.clauses
            )
        # BinaryExpression — left=column·right=BindParameter·operator=callable
        if hasattr(where, "left") and hasattr(where, "right"):
            col_name = where.left.key if hasattr(where.left, "key") else str(where.left)
            actual = getattr(row, col_name, None)
            value = where.right.value if hasattr(where.right, "value") else where.right
            op = getattr(where, "operator", None)
            op_name = getattr(op, "__name__", "eq") if op is not None else "eq"
            handler = op_dispatch.get(op_name, eq)
            try:
                return bool(handler(actual, value))
            except TypeError:
                # None 비교 등 — 매치 실패
                return False
        return True


def _fake_sessionmaker_for(store: dict[str, Any]) -> Any:
    """`async_sessionmaker[AsyncSession]` 호환 — 호출 시 `_FakePgSession`(store 공유) 반환."""

    def factory() -> _FakePgSession:
        return _FakePgSession(store)

    return factory


class TestPgDeviceStoreRegister:
    async def test_register_inserts_row_and_returns_credentials(self) -> None:
        store_dict: dict[str, Any] = {}
        store = PgDeviceStore(_fake_sessionmaker_for(store_dict))
        device_id, secret_plain = await store.register(_UID)
        # 적재 확인
        assert device_id in store_dict
        row = store_dict[device_id]
        assert row.user_id == _UID
        assert row.secret_plain == secret_plain
        assert row.revoked is False
        # 발급 형식
        uuid.UUID(device_id)
        assert len(secret_plain) >= 40

    async def test_register_yields_distinct_credentials(self) -> None:
        store_dict: dict[str, Any] = {}
        store = PgDeviceStore(_fake_sessionmaker_for(store_dict))
        d1, s1 = await store.register(_UID)
        d2, s2 = await store.register(_UID)
        assert d1 != d2
        assert s1 != s2
        assert len(store_dict) == 2


class TestPgDeviceStoreVerify:
    async def test_verify_accepts_valid_signature(self) -> None:
        store_dict: dict[str, Any] = {}
        store = PgDeviceStore(_fake_sessionmaker_for(store_dict))
        device_id, secret_plain = await store.register(_UID)
        sig = _compute_signature(secret_plain, device_id)
        assert await store.verify(device_id, sig) is True

    async def test_verify_unknown_device_id_returns_false(self) -> None:
        store_dict: dict[str, Any] = {}
        store = PgDeviceStore(_fake_sessionmaker_for(store_dict))
        assert await store.verify("never-registered", "0" * 64) is False

    async def test_verify_wrong_signature_returns_false(self) -> None:
        store_dict: dict[str, Any] = {}
        store = PgDeviceStore(_fake_sessionmaker_for(store_dict))
        device_id, _secret = await store.register(_UID)
        bad_sig = _compute_signature("wrong-secret", device_id)
        assert await store.verify(device_id, bad_sig) is False

    async def test_verify_accepts_uppercase_signature(self) -> None:
        # .lower() 정규화 정합
        store_dict: dict[str, Any] = {}
        store = PgDeviceStore(_fake_sessionmaker_for(store_dict))
        device_id, secret_plain = await store.register(_UID)
        sig_upper = _compute_signature(secret_plain, device_id).upper()
        assert await store.verify(device_id, sig_upper) is True


class TestPgDeviceStoreRevoke:
    async def test_revoke_existing_owner_returns_true_and_marks_row(self) -> None:
        store_dict: dict[str, Any] = {}
        store = PgDeviceStore(_fake_sessionmaker_for(store_dict))
        device_id, _secret = await store.register(_UID)
        assert await store.revoke(device_id, _UID) is True
        # 행이 폐기됐고 revoked_at이 채워졌는지
        row = store_dict[device_id]
        assert row.revoked is True
        assert row.revoked_at is not None

    async def test_revoke_unknown_returns_false(self) -> None:
        store_dict: dict[str, Any] = {}
        store = PgDeviceStore(_fake_sessionmaker_for(store_dict))
        # update WHERE device_id = ... AND user_id = ... 가 0행 매치 → rowcount 0 → False
        assert await store.revoke("never-registered", _UID) is False

    async def test_verify_after_revoke_returns_false(self) -> None:
        """revoke 후 같은 secret/서명이라도 verify는 False(slice 22 invariant 그대로)."""
        store_dict: dict[str, Any] = {}
        store = PgDeviceStore(_fake_sessionmaker_for(store_dict))
        device_id, secret_plain = await store.register(_UID)
        sig = _compute_signature(secret_plain, device_id)
        assert await store.verify(device_id, sig) is True
        await store.revoke(device_id, _UID)
        assert await store.verify(device_id, sig) is False

    async def test_revoke_other_owner_returns_false(self) -> None:
        """slice 24: 타인 owner_id로 폐기 시도 → WHERE 매치 0 → False(rowcount 0)."""
        store_dict: dict[str, Any] = {}
        store = PgDeviceStore(_fake_sessionmaker_for(store_dict))
        device_id, _secret = await store.register(_UID)
        other_uid = uuid.uuid4()
        assert await store.revoke(device_id, other_uid) is False
        # 원 행은 *수정 안 됨*(revoked 그대로 False)
        assert store_dict[device_id].revoked is False
        # 원 소유자는 여전히 폐기 가능
        assert await store.revoke(device_id, _UID) is True
        assert store_dict[device_id].revoked is True


class TestPgDeviceStoreListForUser:
    """SELECT WHERE user_id=X AND revoked=False ORDER BY created_at DESC — `_FakePgSession` 처리."""

    async def test_empty_returns_empty_list(self) -> None:
        store_dict: dict[str, Any] = {}
        store = PgDeviceStore(_fake_sessionmaker_for(store_dict))
        assert await store.list_for_user(_UID) == []

    async def test_scoped_to_owner_and_excludes_revoked(self) -> None:
        store_dict: dict[str, Any] = {}
        store = PgDeviceStore(_fake_sessionmaker_for(store_dict))
        d1, _ = await store.register(_UID)
        d2, _ = await store.register(_UID)
        # 다른 사용자의 device
        other_uid = uuid.uuid4()
        await store.register(other_uid)
        # d1 폐기
        await store.revoke(d1, _UID)
        # 본인 활성 1개(d2)만
        infos = await store.list_for_user(_UID)
        assert [i.device_id for i in infos] == [d2]
        # created_at도 함께 반환
        assert infos[0].created_at == store_dict[d2].created_at
        # slice 32: last_used_at은 등록 직후 None(verify 안 됨)
        assert infos[0].last_used_at is None

    async def test_verify_success_updates_last_used_at(self) -> None:
        """slice 32: PgDeviceStore.verify가 last_used_at 컬럼 UPDATE."""
        store_dict: dict[str, Any] = {}
        store = PgDeviceStore(_fake_sessionmaker_for(store_dict))
        device_id, secret_plain = await store.register(_UID)
        assert store_dict[device_id].last_used_at is None
        # verify 성공 → last_used_at 갱신
        sig = _compute_signature(secret_plain, device_id)
        assert await store.verify(device_id, sig) is True
        assert store_dict[device_id].last_used_at is not None
        # list_for_user 응답에도 노출
        infos = await store.list_for_user(_UID)
        assert infos[0].last_used_at == store_dict[device_id].last_used_at

    async def test_verify_failure_does_not_update_last_used_at(self) -> None:
        store_dict: dict[str, Any] = {}
        store = PgDeviceStore(_fake_sessionmaker_for(store_dict))
        device_id, _ = await store.register(_UID)
        # 잘못된 sig → False → last_used_at 갱신 0
        assert await store.verify(device_id, "0" * 64) is False
        assert store_dict[device_id].last_used_at is None

    async def test_include_revoked_returns_revoked_rows(self) -> None:
        """slice 37: include_revoked=True → WHERE revoked=False 절 제거·폐기 행 포함."""
        store_dict: dict[str, Any] = {}
        store = PgDeviceStore(_fake_sessionmaker_for(store_dict))
        d1, _ = await store.register(_UID)
        d2, _ = await store.register(_UID)
        await store.revoke(d1, _UID)
        # 기본: 활성 1개만
        active_only = await store.list_for_user(_UID)
        assert [i.device_id for i in active_only] == [d2]
        # include_revoked=True: 둘 다
        all_infos = await store.list_for_user(_UID, include_revoked=True)
        ids = sorted(i.device_id for i in all_infos)
        assert ids == sorted([d1, d2])
        # 폐기된 d1은 revoked=True·revoked_at 채워짐
        d1_info = next(i for i in all_infos if i.device_id == d1)
        assert d1_info.revoked is True
        assert d1_info.revoked_at is not None

    async def test_pagination_via_sql_limit_offset(self) -> None:
        """slice 38: PgDeviceStore.list_for_user가 SQL LIMIT/OFFSET 발급(`_FakePgSession` 처리)."""
        store_dict: dict[str, Any] = {}
        store = PgDeviceStore(_fake_sessionmaker_for(store_dict))
        ids = [(await store.register(_UID))[0] for _ in range(4)]
        # limit=2 offset=0 → 첫 2개(DESC 정렬·최근 등록 우선)
        page1 = await store.list_for_user(_UID, limit=2, offset=0)
        assert [i.device_id for i in page1] == [ids[3], ids[2]]
        # offset=2 → 다음 2개
        page2 = await store.list_for_user(_UID, limit=2, offset=2)
        assert [i.device_id for i in page2] == [ids[1], ids[0]]
        # offset 초과 → 빈
        assert await store.list_for_user(_UID, limit=2, offset=10) == []

    async def test_count_for_user_via_sql_count(self) -> None:
        """slice 39: PgDeviceStore.count_for_user → SELECT COUNT(*) WHERE ... 발급."""
        store_dict: dict[str, Any] = {}
        store = PgDeviceStore(_fake_sessionmaker_for(store_dict))
        for _ in range(3):
            await store.register(_UID)
        d_revoke, _ = await store.register(_UID)
        await store.revoke(d_revoke, _UID)
        other = uuid.uuid4()
        await store.register(other)
        # 본인 활성만 → 3
        assert await store.count_for_user(_UID) == 3
        # 본인 폐기 포함 → 4
        assert await store.count_for_user(_UID, include_revoked=True) == 4

    async def test_since_until_via_sql_range(self) -> None:
        """slice 41: PgDeviceStore가 created_at >= since / <= until WHERE 발급.

        `_FakePgSession._row_matches`가 ge/le 연산자도 처리하므로 hermetic 검증 가능.
        """
        store_dict: dict[str, Any] = {}
        store = PgDeviceStore(_fake_sessionmaker_for(store_dict))
        d1, _ = await store.register(_UID)
        d2, _ = await store.register(_UID)
        now = datetime.now(UTC)
        # d2의 created_at을 1년 전으로 강제
        store_dict[d2].created_at = now - timedelta(days=365)
        # since=30일 전 → d1만(현재)
        infos = await store.list_for_user(_UID, since=now - timedelta(days=30))
        assert [i.device_id for i in infos] == [d1]
        # until=14일 전 → d2만(1년 전)
        infos2 = await store.list_for_user(_UID, until=now - timedelta(days=14))
        assert [i.device_id for i in infos2] == [d2]
        # count 동일 필터
        assert await store.count_for_user(_UID, since=now - timedelta(days=30)) == 1
        assert await store.count_for_user(_UID, until=now - timedelta(days=14)) == 1

    async def test_revoked_since_until_via_sql_range(self) -> None:
        """slice 43: PgDeviceStore가 revoked_at >= revoked_since / <= revoked_until WHERE 발급."""
        store_dict: dict[str, Any] = {}
        store = PgDeviceStore(_fake_sessionmaker_for(store_dict))
        d1, _ = await store.register(_UID)
        d2, _ = await store.register(_UID)
        await store.revoke(d1, _UID)
        await store.revoke(d2, _UID)
        now = datetime.now(UTC)
        # d1은 1년 전 폐기·d2는 어제 폐기
        store_dict[d1].revoked_at = now - timedelta(days=365)
        store_dict[d2].revoked_at = now - timedelta(days=1)
        # revoked_since=30일전 → d2만(미폐기 행은 revoked_at IS NULL이라 자동 제외)
        infos = await store.list_for_user(
            _UID, include_revoked=True, revoked_since=now - timedelta(days=30)
        )
        assert [i.device_id for i in infos] == [d2]
        # 시간창 [400일전, 100일전] → d1만
        infos2 = await store.list_for_user(
            _UID,
            include_revoked=True,
            revoked_since=now - timedelta(days=400),
            revoked_until=now - timedelta(days=100),
        )
        assert [i.device_id for i in infos2] == [d1]
        # count 동일 (revoked_since·revoked_until 둘 다 분기 cov)
        assert (
            await store.count_for_user(
                _UID,
                include_revoked=True,
                revoked_since=now - timedelta(days=30),
            )
            == 1
        )
        assert (
            await store.count_for_user(
                _UID,
                include_revoked=True,
                revoked_until=now - timedelta(days=100),
            )
            == 1
        )


class TestPgDeviceStoreCleanupStale:
    """slice 33-34: SELECT 활성 → Python 필터 → 옵션 UPDATE 반복."""

    async def test_empty_returns_empty_list(self) -> None:
        store_dict: dict[str, Any] = {}
        store = PgDeviceStore(_fake_sessionmaker_for(store_dict))
        assert await store.cleanup_stale(max_age_days=30) == []

    async def test_fresh_devices_not_revoked(self) -> None:
        store_dict: dict[str, Any] = {}
        store = PgDeviceStore(_fake_sessionmaker_for(store_dict))
        device_id, _ = await store.register(_UID)
        assert await store.cleanup_stale(max_age_days=30) == []
        assert store_dict[device_id].revoked is False

    async def test_stale_by_created_at_revoked(self) -> None:
        """한 번도 verify 안 된 device·created_at > 임계 → 폐기."""
        store_dict: dict[str, Any] = {}
        store = PgDeviceStore(_fake_sessionmaker_for(store_dict))
        device_id, _ = await store.register(_UID)
        # created_at을 강제로 31일 전
        store_dict[device_id].created_at = datetime.now(UTC) - timedelta(days=31)
        affected = await store.cleanup_stale(max_age_days=30)
        assert affected == [device_id]
        assert store_dict[device_id].revoked is True
        assert store_dict[device_id].revoked_at is not None

    async def test_stale_by_last_used_at_revoked(self) -> None:
        store_dict: dict[str, Any] = {}
        store = PgDeviceStore(_fake_sessionmaker_for(store_dict))
        device_id, secret_plain = await store.register(_UID)
        # verify 성공 → last_used_at 채워짐
        sig = _compute_signature(secret_plain, device_id)
        await store.verify(device_id, sig)
        # last_used_at을 강제로 31일 전
        store_dict[device_id].last_used_at = datetime.now(UTC) - timedelta(days=31)
        assert await store.cleanup_stale(max_age_days=30) == [device_id]
        assert store_dict[device_id].revoked is True

    async def test_already_revoked_skipped_in_select(self) -> None:
        """이미 폐기된 device는 SELECT WHERE revoked=False에서 제외."""
        store_dict: dict[str, Any] = {}
        store = PgDeviceStore(_fake_sessionmaker_for(store_dict))
        device_id, _ = await store.register(_UID)
        await store.revoke(device_id, _UID)  # 미리 폐기
        # created_at을 과거로 강제해도 SELECT에서 제외돼 다시 안 폐기
        store_dict[device_id].created_at = datetime.now(UTC) - timedelta(days=100)
        assert await store.cleanup_stale(max_age_days=30) == []

    async def test_dry_run_returns_list_without_revoking(self) -> None:
        """slice 34: dry_run=True → SELECT만·UPDATE 0·preview 패턴."""
        store_dict: dict[str, Any] = {}
        store = PgDeviceStore(_fake_sessionmaker_for(store_dict))
        device_id, _ = await store.register(_UID)
        store_dict[device_id].created_at = datetime.now(UTC) - timedelta(days=31)
        preview = await store.cleanup_stale(max_age_days=30, dry_run=True)
        assert preview == [device_id]
        # 실제 폐기 안 됨
        assert store_dict[device_id].revoked is False
        assert store_dict[device_id].revoked_at is None


class TestCachedDeviceStoreCleanupStale:
    """slice 34: cache 일괄 invalidate — inner가 반환한 device_id 목록으로 정확히 DEL."""

    async def test_passthrough_and_cache_delete_for_each_affected(self) -> None:
        inner_real = InMemoryDeviceStore()
        device_id, secret_plain = await inner_real.register(_UID)
        # 강제 stale
        cred = inner_real._creds[device_id]
        inner_real._creds[device_id] = cred._replace(
            created_at=datetime.now(UTC) - timedelta(days=31)
        )
        counter = _CountingInnerStore(inner_real)
        cache = _FakeCacheClient()
        store = CachedDeviceStore(counter, cache, ttl_seconds=60)
        # 캐시에 미리 적재 — cleanup이 invalidate
        sig = _sign(secret_plain, device_id)
        cache.store["device_verify:" + device_id] = sig.lower()
        # cleanup → inner 호출·cache.delete 호출(폐기된 device의 키만)
        affected = await store.cleanup_stale(max_age_days=30)
        assert affected == [device_id]
        assert counter.cleanup_calls == 1
        # slice 34: 정확히 그 키가 캐시에서 제거됨
        assert cache.delete_calls == 1
        assert "device_verify:" + device_id not in cache.store

    async def test_no_affected_no_cache_delete(self) -> None:
        """폐기된 device 0개면 cache.delete 호출 0(불필요 RTT 회피)."""
        inner_real = InMemoryDeviceStore()
        await inner_real.register(_UID)  # fresh
        counter = _CountingInnerStore(inner_real)
        cache = _FakeCacheClient()
        store = CachedDeviceStore(counter, cache, ttl_seconds=60)
        assert await store.cleanup_stale(max_age_days=30) == []
        assert cache.delete_calls == 0

    async def test_dry_run_does_not_invalidate_cache(self) -> None:
        """slice 34: dry_run=True → cache 미접근(state 변경 0)."""
        inner_real = InMemoryDeviceStore()
        device_id, secret_plain = await inner_real.register(_UID)
        cred = inner_real._creds[device_id]
        inner_real._creds[device_id] = cred._replace(
            created_at=datetime.now(UTC) - timedelta(days=31)
        )
        counter = _CountingInnerStore(inner_real)
        cache = _FakeCacheClient()
        store = CachedDeviceStore(counter, cache, ttl_seconds=60)
        cache.store["device_verify:" + device_id] = _sign(secret_plain, device_id)
        preview = await store.cleanup_stale(max_age_days=30, dry_run=True)
        assert preview == [device_id]
        # 캐시 그대로
        assert cache.delete_calls == 0
        assert "device_verify:" + device_id in cache.store
