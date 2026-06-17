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

from whymath_backend.api.auth import OAuthIdentity, OAuthProviderError
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
_REFRESH_PATH = "/v1/auth/refresh"
_LOGOUT_PATH = "/v1/auth/logout"
_RESOLVE_FN = "whymath_backend.api.auth.resolve_user"
_BODY = {"code": "auth-code", "redirect_uri": "https://app/cb"}


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
    return Settings(jwt_secret_key=SecretStr("test-secret-0123456789abcdef"))


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


def _client(providers: dict[str, object], *, session: _FakeSession | None = None) -> TestClient:
    app = create_app(oauth_providers=providers)  # type: ignore[arg-type]
    app.dependency_overrides[get_settings] = _settings
    fake = session if session is not None else _FakeSession()

    async def _sess() -> AsyncIterator[_FakeSession]:
        yield fake

    app.dependency_overrides[get_session] = _sess
    return TestClient(app)


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
    """등록되지 않은 provider → 404."""
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
