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
    DeviceCredentialStore,
    InMemoryDeviceStore,
    PgDeviceStore,
    _compute_signature,
    get_device_store,
    set_device_store,
)
from whymath_backend.api._rate_limit import (
    _client_device_id,
    _expected_device_signature,
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


def _user() -> UserProfile:
    return UserProfile.from_schema(
        UserProfileSchema(user_id=_UID, persona_primary=Persona.A_일반고고3)
    )


def _settings_override(device_hmac_secret: str = "") -> Settings:
    return Settings(
        jwt_secret_key=SecretStr("test-secret-0123456789abcdef"),
        coach_device_hmac_secret=SecretStr(device_hmac_secret),
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
        await store.revoke(device_id)
        assert await store.verify(device_id, sig) is False


class TestInMemoryDeviceStoreRevoke:
    """revoke — 존재하면 True·미존재 False·재폐기는 True(idempotent)."""

    async def test_revoke_existing_returns_true(self) -> None:
        store = InMemoryDeviceStore()
        device_id, _ = await store.register(_UID)
        assert await store.revoke(device_id) is True

    async def test_revoke_unknown_returns_false(self) -> None:
        store = InMemoryDeviceStore()
        assert await store.revoke("never-registered") is False

    async def test_revoke_is_idempotent(self) -> None:
        store = InMemoryDeviceStore()
        device_id, _ = await store.register(_UID)
        assert await store.revoke(device_id) is True
        assert await store.revoke(device_id) is True


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
        await store.revoke(device_id)
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
        """update(DeviceCredential).where(device_id == X).values(...) 적용 + 가짜 result.

        stmt.compile(compile_kwargs={"literal_binds": True})의 SQL을 *해석하지 않고*, stmt의
        `_where_criteria` + `_values`를 직접 들춘다. SQLAlchemy 2.0 update 객체 구조.
        """
        # update(DeviceCredential).where(DeviceCredential.device_id == "X").values(...)
        # whereclause는 BinaryExpression(device_id == X) — right operand의 value를 꺼낸다.
        where = stmt.whereclause
        target_device_id = where.right.value
        # stmt._values 의 값은 BindParameter — .value로 raw Python 값을 꺼낸다.
        values_to_set: dict[Any, Any] = dict(stmt._values)  # type: ignore[attr-defined]
        existing = self._store.get(target_device_id)
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
    async def test_revoke_existing_returns_true_and_marks_row(self) -> None:
        store_dict: dict[str, Any] = {}
        store = PgDeviceStore(_fake_sessionmaker_for(store_dict))
        device_id, _secret = await store.register(_UID)
        assert await store.revoke(device_id) is True
        # 행이 폐기됐고 revoked_at이 채워졌는지
        row = store_dict[device_id]
        assert row.revoked is True
        assert row.revoked_at is not None

    async def test_revoke_unknown_returns_false(self) -> None:
        store_dict: dict[str, Any] = {}
        store = PgDeviceStore(_fake_sessionmaker_for(store_dict))
        # update WHERE device_id = ... 가 0행 매치 → rowcount 0 → False
        assert await store.revoke("never-registered") is False

    async def test_verify_after_revoke_returns_false(self) -> None:
        """revoke 후 같은 secret/서명이라도 verify는 False(slice 22 invariant 그대로)."""
        store_dict: dict[str, Any] = {}
        store = PgDeviceStore(_fake_sessionmaker_for(store_dict))
        device_id, secret_plain = await store.register(_UID)
        sig = _compute_signature(secret_plain, device_id)
        assert await store.verify(device_id, sig) is True
        await store.revoke(device_id)
        assert await store.verify(device_id, sig) is False
