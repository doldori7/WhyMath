"""인증 의존성 단위테스트 — get_current_user(401)·get_consented_user(403).

FastAPI 의존성 함수를 *직접* 호출(Depends 메타데이터는 직접 호출 시 무시)하고, AsyncSession은
가짜로 주입한다. 토큰은 `create_access_token` 헬퍼로 mint(HTTP 로그인 엔드포인트 없음).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import SecretStr

from whymath_backend.api._auth import get_consented_user, get_current_user
from whymath_backend.config import Settings
from whymath_backend.db.models.user import UserProfile
from whymath_backend.security import create_access_token

_SECRET = "test-secret-key-0123456789abcdef"


def _settings() -> Settings:
    return Settings(jwt_secret_key=SecretStr(_SECRET))


class _FakeSession:
    """session.get(UserProfile, pk)만 모사 — pk가 보유 user와 같으면 반환, 아니면 None."""

    def __init__(self, user: UserProfile | None = None) -> None:
        self._user = user

    async def get(self, model: Any, pk: uuid.UUID) -> UserProfile | None:
        if self._user is not None and self._user.user_id == pk:
            return self._user
        return None


def _creds(token: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


class TestGetCurrentUser:
    async def test_valid_token_returns_user(self) -> None:
        settings = _settings()
        uid = uuid.uuid4()
        user = UserProfile(user_id=uid)
        token = create_access_token(uid, settings=settings)
        result = await get_current_user(
            credentials=_creds(token), session=_FakeSession(user), settings=settings  # type: ignore[arg-type]
        )
        assert result is user

    async def test_no_credentials_raises_401(self) -> None:
        with pytest.raises(HTTPException) as exc:
            await get_current_user(
                credentials=None, session=_FakeSession(), settings=_settings()  # type: ignore[arg-type]
            )
        assert exc.value.status_code == 401
        assert exc.value.headers is not None and "WWW-Authenticate" in exc.value.headers

    async def test_garbage_token_raises_401(self) -> None:
        with pytest.raises(HTTPException) as exc:
            await get_current_user(
                credentials=_creds("not-a-jwt"), session=_FakeSession(), settings=_settings()  # type: ignore[arg-type]
            )
        assert exc.value.status_code == 401

    async def test_non_uuid_subject_raises_401(self) -> None:
        settings = _settings()
        token = create_access_token("not-a-uuid", settings=settings)
        with pytest.raises(HTTPException) as exc:
            await get_current_user(
                credentials=_creds(token), session=_FakeSession(), settings=settings  # type: ignore[arg-type]
            )
        assert exc.value.status_code == 401

    async def test_user_not_found_raises_401(self) -> None:
        settings = _settings()
        token = create_access_token(uuid.uuid4(), settings=settings)
        with pytest.raises(HTTPException) as exc:
            await get_current_user(
                credentials=_creds(token), session=_FakeSession(None), settings=settings  # type: ignore[arg-type]
            )
        assert exc.value.status_code == 401


class TestConsentGate:
    async def test_minor_without_consent_raises_403(self) -> None:
        user = UserProfile(user_id=uuid.uuid4(), is_minor=True, parent_consent_at=None)
        with pytest.raises(HTTPException) as exc:
            await get_consented_user(user=user)
        assert exc.value.status_code == 403

    async def test_minor_with_consent_passes(self) -> None:
        user = UserProfile(
            user_id=uuid.uuid4(),
            is_minor=True,
            parent_consent_at=datetime.now(tz=timezone.utc),
        )
        assert await get_consented_user(user=user) is user

    async def test_non_minor_passes(self) -> None:
        user = UserProfile(user_id=uuid.uuid4(), is_minor=False)
        assert await get_consented_user(user=user) is user

    async def test_unknown_minor_status_passes(self) -> None:
        """is_minor None(미상)이면 차단하지 않는다 — 알려진 미성년자만 게이트."""
        user = UserProfile(user_id=uuid.uuid4())
        assert await get_consented_user(user=user) is user
