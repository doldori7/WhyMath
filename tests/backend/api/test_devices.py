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
    """`DeviceCredentialStore` 인스턴스 — verify/revoke/register 호출 횟수 기록."""

    def __init__(self, inner: InMemoryDeviceStore) -> None:
        self._inner = inner
        self.verify_calls: int = 0
        self.revoke_calls: int = 0
        self.register_calls: int = 0

    async def register(self, user_id: uuid.UUID) -> tuple[str, str]:
        self.register_calls += 1
        return await self._inner.register(user_id)

    async def verify(self, device_id: str, signature_hex: str) -> bool:
        self.verify_calls += 1
        return await self._inner.verify(device_id, signature_hex)

    async def revoke(self, device_id: str, owner_id: uuid.UUID) -> bool:
        self.revoke_calls += 1
        return await self._inner.revoke(device_id, owner_id)


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
        # revoke → DEL
        assert await store.revoke(device_id, _UID) is True
        assert "device_verify:" + device_id not in cache.store
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
    """register는 캐시 무관 — 그대로 위임."""

    async def test_register_passthrough(self) -> None:
        inner_real = InMemoryDeviceStore()
        counter = _CountingInnerStore(inner_real)
        cache = _FakeCacheClient()
        store = CachedDeviceStore(counter, cache, ttl_seconds=60)
        device_id, secret_plain = await store.register(_UID)
        assert counter.register_calls == 1
        # register는 cache 접근 안 함
        assert cache.get_calls == 0
        assert cache.setex_calls == 0
        assert cache.delete_calls == 0
        # 라운드트립 검증 — 발급된 자격증명으로 verify True
        sig = _sign(secret_plain, device_id)
        assert await store.verify(device_id, sig) is True


class TestCachedDeviceStoreProtocolConformance:
    def test_satisfies_protocol(self) -> None:
        inner = InMemoryDeviceStore()
        cache = _FakeCacheClient()
        store = CachedDeviceStore(inner, cache, ttl_seconds=60)
        assert isinstance(store, DeviceCredentialStore)


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


def _lifespan_settings(mode: str) -> Settings:
    return Settings(
        jwt_secret_key=SecretStr("test-secret-0123456789abcdef"),
        device_store_mode=mode,  # type: ignore[arg-type]
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
        """pg 모드 — startup에서 `_DEVICE_STORE`가 PgDeviceStore, shutdown 후 None."""
        monkeypatch.setattr(
            "whymath_backend.app.get_settings",
            lambda: _lifespan_settings("pg"),
            raising=True,
        )
        with TestClient(create_app()):
            store = get_device_store()
            assert isinstance(store, PgDeviceStore)
        # 종료 후 해제됨
        assert get_device_store() is None


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
        """update(DeviceCredential).where(...).values(...) 적용 + 가짜 result.

        slice 24 — where가 단일 BinaryExpression(device_id == X) 또는 다중 AND 결합
        (device_id == X AND user_id == Y)일 수 있다. `_iter_eq_constraints`로 모든 등식
        제약을 {col_name: value} dict로 추출 → 그 dict로 store에서 매칭 행 검색.
        """
        constraints = self._iter_eq_constraints(stmt.whereclause)
        # stmt._values 의 값은 BindParameter — .value로 raw Python 값을 꺼낸다.
        values_to_set: dict[Any, Any] = dict(stmt._values)  # type: ignore[attr-defined]
        # device_id PK로 빠르게 찾고, 나머지 제약 검증
        target_device_id = constraints.get("device_id")
        existing = (
            self._store.get(target_device_id) if target_device_id is not None else None
        )
        # 제약 추가 검증(user_id 등) — 모두 일치해야 적용
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

    @staticmethod
    def _iter_eq_constraints(where: Any) -> dict[str, Any]:
        """whereclause에서 `col == value` 등식들을 dict로 추출. AND 결합 재귀."""
        result: dict[str, Any] = {}
        # 단일 BinaryExpression (BooleanClauseList가 아닌 경우)
        if hasattr(where, "left") and hasattr(where, "right"):
            col_name = where.left.key if hasattr(where.left, "key") else str(where.left)
            value = where.right.value if hasattr(where.right, "value") else where.right
            result[col_name] = value
            return result
        # BooleanClauseList — children을 순회
        for child in getattr(where, "clauses", []):
            result.update(_FakePgSession._iter_eq_constraints(child))
        return result


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
