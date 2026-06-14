"""POST /v1/auth/{provider}/callback 단위테스트 — provider 조회·code 교환·JWT 발급. OAuth-a.

라이브 provider·DB 없음: 가짜 OAuthProvider 주입(create_app oauth_providers) + resolve_user
monkeypatch + dependency_overrides(get_session·get_settings)로 콜백 글루를 hermetic 검증.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Awaitable, Callable

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from whymath_backend.api.auth import OAuthIdentity, OAuthProviderError
from whymath_backend.app import create_app
from whymath_backend.config import Settings, get_settings
from whymath_backend.db.models.user import UserProfile
from whymath_backend.db.session import get_session
from whymath_backend.schema.enums import Persona
from whymath_backend.security import decode_access_token

_PATH = "/v1/auth/kakao/callback"
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
    """get_session 오버라이드용 — resolve_user monkeypatch라 쿼리 미발생."""


def _settings() -> Settings:
    return Settings(jwt_secret_key=SecretStr("test-secret-0123456789abcdef"))


def _user(uid: uuid.UUID) -> UserProfile:
    return UserProfile(user_id=uid, email_hash="h", persona_primary=Persona.A_일반고고3)


def _client(providers: dict[str, object]) -> TestClient:
    app = create_app(oauth_providers=providers)  # type: ignore[arg-type]
    app.dependency_overrides[get_settings] = _settings

    async def _sess() -> AsyncIterator[_FakeSession]:
        yield _FakeSession()

    app.dependency_overrides[get_session] = _sess
    return TestClient(app)


def _resolve_to(user: UserProfile) -> Callable[[object, object], Awaitable[UserProfile]]:
    async def _fake(session: object, identity: object) -> UserProfile:
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
