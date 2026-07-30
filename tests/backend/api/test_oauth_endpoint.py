"""POST /v1/auth/{provider}/callback·/refresh·/logout 단위테스트 — JWT 발급·allowlist·취소.

라이브 provider·DB 없음: 가짜 OAuthProvider 주입(create_app oauth_providers) + resolve_user
monkeypatch + dependency_overrides(get_session·get_settings)로 글루를 hermetic 검증. `/refresh`·
`/logout`의 서버측 취소(OAuth-a3b)는 `_FakeSession`이 RefreshTokenSession 행을 add/get/commit으로
추적해 검증한다(실 PG 왕복은 test_refresh_session_integration.py).
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from whymath_backend.api._rate_limit import reset_store
from whymath_backend.api.auth import OAuthIdentity, OAuthProviderError, issue_oauth_state
from whymath_backend.app import create_app
from whymath_backend.config import Settings, get_settings
from whymath_backend.db.models.refresh_token_session import RefreshTokenSession
from whymath_backend.db.models.user import UserProfile
from whymath_backend.db.session import get_session
from whymath_backend.schema.enums import Persona
from whymath_backend.security import (
    create_access_token,
    create_refresh_token,
    decode_access_token,
    decode_refresh_token,
)

_PATH = "/v1/auth/kakao/callback"
_STATE_PATH = "/v1/auth/kakao/state"
_REFRESH_PATH = "/v1/auth/refresh"
_LOGOUT_PATH = "/v1/auth/logout"
_RESOLVE_FN = "whymath_backend.api.auth.resolve_user"
_REDIRECT_URI = "https://app/cb"


class _FakeProvider:
    """OAuthProvider 구현(구조적) — 정해진 신원 반환 또는 OAuthProviderError."""

    def __init__(self, *, identity: OAuthIdentity | None = None, raises: bool = False) -> None:
        self._identity = identity
        self._raises = raises

    async def fetch_identity(self, code: str, redirect_uri: str) -> OAuthIdentity:
        if self._raises:
            raise OAuthProviderError("bad code")
        assert self._identity is not None
        return self._identity


class _FakeSession:
    """get_session 오버라이드용 — user 조회 + RefreshTokenSession 행 저장/조회(add/get/commit).

    콜백은 resolve_user monkeypatch라 user 쿼리는 안 나지만 세션 행 add/commit은 탄다. `/refresh`·
    `/logout`은 jti로 세션 행을 PK lookup 하므로 사전 시드(`seed`)한 행을 돌려준다.
    """

    def __init__(self, user: UserProfile | None = None) -> None:
        self._user = user
        self._sessions: dict[uuid.UUID, RefreshTokenSession] = {}

    def seed(self, row: RefreshTokenSession) -> None:
        self._sessions[row.token_session_id] = row

    def stored_rows(self) -> list[RefreshTokenSession]:
        return list(self._sessions.values())

    def add(self, obj: object) -> None:
        if isinstance(obj, RefreshTokenSession):
            self._sessions[obj.token_session_id] = obj

    async def get(self, model: object, pk: uuid.UUID) -> object | None:
        if model is UserProfile:
            if self._user is not None and self._user.user_id == pk:
                return self._user
            return None
        if model is RefreshTokenSession:
            return self._sessions.get(pk)
        return None

    async def commit(self) -> None:
        return None

    async def execute(self, statement: object) -> None:
        # 핸들러가 호출하는 유일한 execute는 재사용-패닉의 전체 활성 세션 취소(update).
        now = datetime.now(tz=timezone.utc)
        for row in self._sessions.values():
            if not row.revoked:
                row.revoked = True
                row.revoked_at = now
        return None


def _settings() -> Settings:
    """기본 설정 — allowlist에 `_REDIRECT_URI` 등록·인증 표면 rate limit은 기본 비활성(0).

    한도(`auth_rate_limit_ip_*`)를 0으로 두는 이유는 test_coach.py `_settings_override` 선례와
    동일 — 이 모듈의 기존 테스트가 반복 호출로 우연히 429를 맞지 않게 하고, rate limit 자체는
    `test_auth_callback_rate_limit_429`가 *전용* 설정(limit=1)으로 검증한다.
    """
    return Settings(
        jwt_secret_key=SecretStr("test-secret-0123456789abcdef"),
        oauth_redirect_uri_allowlist=_REDIRECT_URI,
        auth_rate_limit_ip_per_minute=0,
        auth_rate_limit_ip_refresh_per_minute=0,
    )


def _body(provider: str = "kakao", redirect_uri: str = _REDIRECT_URI) -> dict[str, str]:
    """유효한 state(해당 provider로 서명)를 포함한 콜백 요청 바디."""
    return {
        "code": "auth-code",
        "redirect_uri": redirect_uri,
        "state": issue_oauth_state(provider, settings=_settings()),
    }


_BODY = _body()


def _user(uid: uuid.UUID) -> UserProfile:
    return UserProfile(user_id=uid, email_hash="h", persona_primary=Persona.A_일반고고3)


def _session_row(uid: uuid.UUID, jti: uuid.UUID, *, revoked: bool = False) -> RefreshTokenSession:
    return RefreshTokenSession(
        token_session_id=jti,
        user_id=uid,
        expires_at=datetime.now(tz=timezone.utc) + timedelta(days=30),
        revoked=revoked,
    )


def _refresh_for(uid: uuid.UUID) -> tuple[uuid.UUID, str]:
    """(jti, 리프레시 토큰) — jti는 세션 행 PK와 일치시켜 시드한다."""
    jti = uuid.uuid4()
    return jti, create_refresh_token(uid, settings=_settings(), jti=jti)


def _client(
    providers: dict[str, object],
    *,
    session: _FakeSession | None = None,
    settings_factory: Callable[[], Settings] = _settings,
) -> TestClient:
    app = create_app(oauth_providers=providers)  # type: ignore[arg-type]
    app.dependency_overrides[get_settings] = settings_factory
    fake = session if session is not None else _FakeSession()

    async def _sess() -> AsyncIterator[_FakeSession]:
        yield fake

    app.dependency_overrides[get_session] = _sess
    return TestClient(app)


@pytest.fixture(autouse=True)
def _reset_rate_limit_store() -> None:
    """매 테스트 격리 — sliding window 카운트 리셋(test_coach.py `_reset_rate_limit_store` 미러).

    `_BACKEND`는 모듈 전역이라 이 파일의 테스트가 다른 테스트 모듈과도 카운트를 공유할 수
    있다 — 매 테스트 전 리셋해 순서 의존을 차단한다.
    """
    import asyncio

    asyncio.run(reset_store())


def _resolve_to(user: UserProfile) -> Callable[..., Awaitable[UserProfile]]:
    # resolve_user는 이제 keyword-only `settings`를 받는다(서버측 is_minor 파생) — 가짜도 흡수.
    async def _fake(session: object, identity: object, *, settings: object) -> UserProfile:
        return user

    return _fake


def test_callback_issues_token_for_resolved_user(monkeypatch: pytest.MonkeyPatch) -> None:
    """등록 provider + 정상 code → 200 + 발급 토큰의 sub가 해소된 사용자 id."""
    uid = uuid.uuid4()
    monkeypatch.setattr(_RESOLVE_FN, _resolve_to(_user(uid)))
    identity = OAuthIdentity(provider="kakao", subject="s", email="a@b.com")
    resp = _client({"kakao": _FakeProvider(identity=identity)}).post(_PATH, json=_BODY)
    assert resp.status_code == 200
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert decode_access_token(body["access_token"], settings=_settings()) == str(uid)


def test_unknown_provider_404() -> None:
    """등록되지 않은 provider → 404(state·redirect_uri는 `_BODY`가 이미 유효 — 검증 순서 확인)."""
    assert _client({}).post(_PATH, json=_BODY).status_code == 404


def test_provider_error_502(monkeypatch: pytest.MonkeyPatch) -> None:
    """provider code 교환 실패(OAuthProviderError) → 502."""
    monkeypatch.setattr(_RESOLVE_FN, _resolve_to(_user(uuid.uuid4())))
    resp = _client({"kakao": _FakeProvider(raises=True)}).post(_PATH, json=_BODY)
    assert resp.status_code == 502


def test_callback_issues_refresh_token(monkeypatch: pytest.MonkeyPatch) -> None:
    """콜백은 액세스와 함께 리프레시 토큰도 발급(sub=해소된 사용자 id)."""
    uid = uuid.uuid4()
    monkeypatch.setattr(_RESOLVE_FN, _resolve_to(_user(uid)))
    identity = OAuthIdentity(provider="kakao", subject="s", email="a@b.com")
    resp = _client({"kakao": _FakeProvider(identity=identity)}).post(_PATH, json=_BODY)
    assert resp.status_code == 200
    claims = decode_refresh_token(resp.json()["refresh_token"], settings=_settings())
    assert claims.subject == str(uid)


def test_callback_persists_session_row(monkeypatch: pytest.MonkeyPatch) -> None:
    """콜백이 리프레시 토큰의 jti로 세션 행(allowlist)을 영속 — 토큰↔행 jti 일치."""
    uid = uuid.uuid4()
    monkeypatch.setattr(_RESOLVE_FN, _resolve_to(_user(uid)))
    identity = OAuthIdentity(provider="kakao", subject="s", email="a@b.com")
    session = _FakeSession()
    resp = _client({"kakao": _FakeProvider(identity=identity)}, session=session).post(
        _PATH, json=_BODY
    )
    assert resp.status_code == 200
    rows = session.stored_rows()
    assert len(rows) == 1
    assert rows[0].user_id == uid
    claims = decode_refresh_token(resp.json()["refresh_token"], settings=_settings())
    assert claims.jti == str(rows[0].token_session_id)


def test_refresh_rotates_tokens() -> None:
    """유효 리프레시 회전 → 200·새 액세스+리프레시(새 jti≠원본)·기존 세션 취소·새 세션 추가."""
    uid = uuid.uuid4()
    jti, refresh = _refresh_for(uid)
    session = _FakeSession(_user(uid))
    row = _session_row(uid, jti)
    session.seed(row)
    resp = _client({}, session=session).post(_REFRESH_PATH, json={"refresh_token": refresh})
    assert resp.status_code == 200
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert decode_access_token(body["access_token"], settings=_settings()) == str(uid)
    new_claims = decode_refresh_token(body["refresh_token"], settings=_settings())
    assert new_claims.subject == str(uid)
    assert new_claims.jti != str(jti)  # 회전: 새 jti
    assert row.revoked is True  # 기존 세션 취소
    rows = session.stored_rows()
    assert len(rows) == 2
    assert any(r.token_session_id == uuid.UUID(new_claims.jti) and not r.revoked for r in rows)


def test_refresh_rejects_access_token_401() -> None:
    """액세스 토큰을 리프레시로 제출 → 401(typ 불일치)."""
    uid = uuid.uuid4()
    access = create_access_token(uid, settings=_settings())
    resp = _client({}, session=_FakeSession(_user(uid))).post(
        _REFRESH_PATH, json={"refresh_token": access}
    )
    assert resp.status_code == 401


def test_refresh_invalid_token_401() -> None:
    """불량 리프레시 토큰 → 401."""
    resp = _client({}, session=_FakeSession(_user(uuid.uuid4()))).post(
        _REFRESH_PATH, json={"refresh_token": "not-a-jwt"}
    )
    assert resp.status_code == 401


def test_refresh_unknown_session_401() -> None:
    """서명·jti는 유효하지만 세션 행이 없으면(미인식·로그아웃됨) → 401(allowlist 미스)."""
    uid = uuid.uuid4()
    _, refresh = _refresh_for(uid)  # 행 시드 안 함
    resp = _client({}, session=_FakeSession(_user(uid))).post(
        _REFRESH_PATH, json={"refresh_token": refresh}
    )
    assert resp.status_code == 401


def test_refresh_reuse_revoked_panics_401() -> None:
    """이미 취소된(회전/로그아웃) 토큰 재제출 → 재사용 탐지: 전체 활성 세션 패닉 취소 + 401."""
    uid = uuid.uuid4()
    jti, refresh = _refresh_for(uid)
    session = _FakeSession(_user(uid))
    session.seed(_session_row(uid, jti, revoked=True))  # 재사용되는 취소 토큰
    other = _session_row(uid, uuid.uuid4())  # 같은 사용자의 다른 활성 세션
    session.seed(other)
    resp = _client({}, session=session).post(_REFRESH_PATH, json={"refresh_token": refresh})
    assert resp.status_code == 401
    assert other.revoked is True  # 패닉: 다른 활성 세션도 취소됨


def test_refresh_unknown_user_401() -> None:
    """세션 행은 유효하지만 사용자가 없으면(삭제) → 401."""
    uid = uuid.uuid4()
    jti, refresh = _refresh_for(uid)
    session = _FakeSession()  # 사용자 없음
    session.seed(_session_row(uid, jti))
    resp = _client({}, session=session).post(_REFRESH_PATH, json={"refresh_token": refresh})
    assert resp.status_code == 401


def test_logout_revokes_session_204() -> None:
    """로그아웃 → 204 + 세션 행 revoked=True(즉시 무효화)."""
    uid = uuid.uuid4()
    jti, refresh = _refresh_for(uid)
    row = _session_row(uid, jti)
    session = _FakeSession(_user(uid))
    session.seed(row)
    resp = _client({}, session=session).post(_LOGOUT_PATH, json={"refresh_token": refresh})
    assert resp.status_code == 204
    assert row.revoked is True


def test_logout_then_refresh_401() -> None:
    """로그아웃한 리프레시 토큰은 이후 /refresh에서 거부(401) — 서버측 취소 e2e."""
    uid = uuid.uuid4()
    jti, refresh = _refresh_for(uid)
    session = _FakeSession(_user(uid))
    session.seed(_session_row(uid, jti))
    client = _client({}, session=session)
    assert client.post(_LOGOUT_PATH, json={"refresh_token": refresh}).status_code == 204
    assert client.post(_REFRESH_PATH, json={"refresh_token": refresh}).status_code == 401


def test_logout_invalid_token_401() -> None:
    """디코드 불가 토큰 로그아웃 → 401."""
    resp = _client({}, session=_FakeSession()).post(
        _LOGOUT_PATH, json={"refresh_token": "not-a-jwt"}
    )
    assert resp.status_code == 401


def test_logout_missing_row_idempotent_204() -> None:
    """유효 리프레시지만 세션 행이 없어도 멱등하게 204(취소할 게 없음)."""
    uid = uuid.uuid4()
    _, refresh = _refresh_for(uid)
    resp = _client({}, session=_FakeSession(_user(uid))).post(
        _LOGOUT_PATH, json={"refresh_token": refresh}
    )
    assert resp.status_code == 204


# ──────────────────────────────────────────────────────────────────────────
# SEC-08 — OAuth state 발급·검증 + redirect_uri allowlist + IP rate limit.
# ──────────────────────────────────────────────────────────────────────────


def test_issue_state_endpoint_returns_verifiable_state(monkeypatch: pytest.MonkeyPatch) -> None:
    """`GET /{provider}/state` → 200 + 그 provider 콜백에 그대로 써도 통과하는 state."""
    resp = _client({}).get(_STATE_PATH)
    assert resp.status_code == 200
    state = resp.json()["state"]
    assert isinstance(state, str) and state

    uid = uuid.uuid4()
    monkeypatch.setattr(_RESOLVE_FN, _resolve_to(_user(uid)))
    identity = OAuthIdentity(provider="kakao", subject="s", email="a@b.com")
    body = {"code": "auth-code", "redirect_uri": _REDIRECT_URI, "state": state}
    callback_resp = _client({"kakao": _FakeProvider(identity=identity)}).post(_PATH, json=body)
    assert callback_resp.status_code == 200


def test_callback_missing_state_field_422() -> None:
    """`state` 필드 누락 → 422(스키마 required — breaking 계약 변경 회귀)."""
    resp = _client({"kakao": _FakeProvider()}).post(
        _PATH, json={"code": "auth-code", "redirect_uri": _REDIRECT_URI}
    )
    assert resp.status_code == 422


def test_callback_state_mismatch_400() -> None:
    """state 불일치(다른 provider로 서명된 state) → 400."""
    wrong_provider_state = issue_oauth_state("naver", settings=_settings())
    body = {"code": "auth-code", "redirect_uri": _REDIRECT_URI, "state": wrong_provider_state}
    resp = _client({"kakao": _FakeProvider()}).post(_PATH, json=body)
    assert resp.status_code == 400


def test_callback_state_forged_signature_400() -> None:
    """서명이 다른(비밀키 불일치) 위조 state → 400."""
    body = {
        "code": "auth-code",
        "redirect_uri": _REDIRECT_URI,
        "state": "kakao:nonce:9999999999.deadbeef",
    }
    resp = _client({"kakao": _FakeProvider()}).post(_PATH, json=body)
    assert resp.status_code == 400


def test_callback_redirect_uri_not_allowlisted_400() -> None:
    """allowlist에 없는 redirect_uri → 400(open redirect 방지) — state는 유효해도 거부."""
    body = _body(redirect_uri="https://evil.example/cb")
    resp = _client({"kakao": _FakeProvider()}).post(_PATH, json=body)
    assert resp.status_code == 400


def test_callback_empty_allowlist_denies_by_default() -> None:
    """allowlist 미설정(빈 문자열) → 등록된 redirect_uri도 전부 거부(deny-by-default)."""

    def _settings_no_allowlist() -> Settings:
        return Settings(jwt_secret_key=SecretStr("test-secret-0123456789abcdef"))

    resp = _client({"kakao": _FakeProvider()}, settings_factory=_settings_no_allowlist).post(
        _PATH, json=_BODY
    )
    assert resp.status_code == 400


class TestOAuthStateRoundtrip:
    """`issue_oauth_state`/`verify_oauth_state` 단위 — 만료·위조·provider 불일치."""

    def test_roundtrip_valid(self) -> None:
        from whymath_backend.api.auth import verify_oauth_state

        settings = _settings()
        state = issue_oauth_state("kakao", settings=settings)
        assert verify_oauth_state("kakao", state, settings=settings) is True

    def test_provider_mismatch_false(self) -> None:
        from whymath_backend.api.auth import verify_oauth_state

        settings = _settings()
        state = issue_oauth_state("kakao", settings=settings)
        assert verify_oauth_state("naver", state, settings=settings) is False

    def test_expired_false(self) -> None:
        """만료된 payload(과거 expiry)를 *동일 시크릿*으로 직접 서명해 만료 판정만 분리 검증."""
        import hashlib
        import hmac as _hmac

        from whymath_backend.api.auth import verify_oauth_state

        settings = _settings()
        payload = "kakao:deadbeefdeadbeefdeadbeefdeadbeef:1"  # expiry=1(1970년 — 항상 과거)
        secret = settings.jwt_secret_key.get_secret_value().encode("utf-8")
        sig = _hmac.new(secret, payload.encode("utf-8"), hashlib.sha256).hexdigest()
        expired_state = f"{payload}.{sig}"
        assert verify_oauth_state("kakao", expired_state, settings=settings) is False

    def test_malformed_false(self) -> None:
        from whymath_backend.api.auth import verify_oauth_state

        settings = _settings()
        assert verify_oauth_state("kakao", "not-a-valid-state-token", settings=settings) is False

    def test_tampered_signature_false(self) -> None:
        from whymath_backend.api.auth import verify_oauth_state

        settings = _settings()
        state = issue_oauth_state("kakao", settings=settings)
        payload, _sig = state.rsplit(".", 1)
        tampered = f"{payload}.{'0' * 64}"
        assert verify_oauth_state("kakao", tampered, settings=settings) is False


def test_auth_callback_rate_limit_429() -> None:
    """`auth_rate_limit_ip_per_minute=1` — 같은 IP에서 콜백 2회 연속 시 두 번째는 429.

    TestClient는 기본적으로 매 요청 같은 IP(테스트 클라이언트 host)를 쓰므로 별도 IP 조작이
    필요 없다(task 설계 메모 그대로). `_rate_limit.hit_by_ip`(기존 인프라)만 호출하는
    `RateLimitedAuthCallback` 의존성이 실제로 걸리는지 확인 — 재구현 0.
    """

    def _limited_settings() -> Settings:
        return Settings(
            jwt_secret_key=SecretStr("test-secret-0123456789abcdef"),
            oauth_redirect_uri_allowlist=_REDIRECT_URI,
            auth_rate_limit_ip_per_minute=1,
        )

    client = _client({"kakao": _FakeProvider(raises=True)}, settings_factory=_limited_settings)
    body = _body()
    first = client.post(_PATH, json=body)
    second = client.post(_PATH, json=body)
    # 첫 요청은 rate limit을 통과해 provider까지 도달(raises=True → 502). 두 번째는 429.
    assert first.status_code == 502
    assert second.status_code == 429
    assert "Retry-After" in second.headers


def test_refresh_rate_limit_429() -> None:
    """`auth_rate_limit_ip_refresh_per_minute=1` — 같은 IP `/refresh` 2회 연속 시 두 번째 429."""

    def _limited_settings() -> Settings:
        return Settings(
            jwt_secret_key=SecretStr("test-secret-0123456789abcdef"),
            auth_rate_limit_ip_refresh_per_minute=1,
        )

    client = _client({}, session=_FakeSession(), settings_factory=_limited_settings)
    bad_body = {"refresh_token": "not-a-jwt"}
    first = client.post(_REFRESH_PATH, json=bad_body)
    second = client.post(_REFRESH_PATH, json=bad_body)
    # 첫 요청은 rate limit 통과 후 401(불량 토큰). 두 번째는 429(rate limit이 먼저 걸림).
    assert first.status_code == 401
    assert second.status_code == 429


def test_redis_unavailable_falls_back_to_in_memory_for_auth_category() -> None:
    """Redis 백엔드 장애 시 인증 표면도 기존 OPS-06 인메모리 폴백을 그대로 상속(재구현 0).

    `RedisBackend.hit_by_ip`가 예외를 만나면 `InMemoryBackend`로 강등하는 것은 `_rate_limit.py`
    기존 로직(`_degrade_to_fallback`)이고, 이 테스트는 그 상속 경로가 `category="auth"`에서도
    똑같이 동작하는지만 확인한다(별도 분기 0 — `_enforce_by_ip`가 카테고리를 그대로 전달).
    """
    import asyncio

    from whymath_backend.api._rate_limit import InMemoryBackend, RedisBackend

    class _BrokenClient:
        async def evalsha(self, *args: object, **kwargs: object) -> object:
            raise ConnectionError("redis down(test)")

        async def script_load(self, *args: object, **kwargs: object) -> object:
            raise ConnectionError("redis down(test)")

    backend = RedisBackend(client=_BrokenClient())  # type: ignore[arg-type]
    result = asyncio.run(backend.hit_by_ip("203.0.113.5", category="auth", limit=1, now=0.0))
    assert result.allowed is True  # 폴백된 InMemoryBackend가 첫 히트는 통과시킨다
    assert isinstance(backend._fallback, InMemoryBackend)  # noqa: SLF001 — 폴백 상속 확인
