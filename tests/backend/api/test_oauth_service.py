"""OAuth 사용자 upsert·이메일 해시 단위테스트 — resolve_user/email_hash. OAuth-a.

라이브 DB 없음: 가짜 session(.scalar/.add/.flush)으로 upsert 분기(신규 생성·기존 반환)를 검증.
"""

from __future__ import annotations

import uuid

import pytest

from whymath_backend.api.auth import OAuthIdentity, email_hash, resolve_user
from whymath_backend.db.models.user import UserProfile
from whymath_backend.schema.enums import Persona


class _FakeSession:
    """session.scalar(select)·add·flush만 모사 — scalar는 보유 사용자(없으면 None) 반환."""

    def __init__(self, existing: UserProfile | None = None) -> None:
        self._existing = existing
        self.added: list[UserProfile] = []

    async def scalar(self, statement: object) -> UserProfile | None:
        return self._existing

    def add(self, obj: UserProfile) -> None:
        self.added.append(obj)

    async def flush(self) -> None:
        pass


def _identity(email: str = "a@b.com") -> OAuthIdentity:
    return OAuthIdentity(provider="kakao", subject="123", email=email)


def test_email_hash_normalized_and_64_hex() -> None:
    """이메일 해시는 정규화(소문자·trim) + 64자 hex(결정론)."""
    assert email_hash("A@B.com") == email_hash("  a@b.com  ")
    assert len(email_hash("a@b.com")) == 64


@pytest.mark.asyncio
async def test_resolve_creates_new_user_with_default_persona() -> None:
    """기존 사용자 없음 → 신규 생성(기본 페르소나 A·이메일 해시 키·session.add)."""
    session = _FakeSession(existing=None)
    user = await resolve_user(session, _identity())  # type: ignore[arg-type]
    assert isinstance(user, UserProfile)
    assert user.persona_primary == Persona.A_일반고고3
    assert user.email_hash == email_hash("a@b.com")
    assert user.user_id is not None
    assert len(session.added) == 1


@pytest.mark.asyncio
async def test_resolve_returns_existing_user() -> None:
    """같은 이메일 해시의 기존 사용자 → 그대로 반환(신규 생성 없음)."""
    existing = UserProfile(
        user_id=uuid.uuid4(),
        email_hash=email_hash("a@b.com"),
        persona_primary=Persona.A_일반고고3,
    )
    session = _FakeSession(existing=existing)
    user = await resolve_user(session, _identity())  # type: ignore[arg-type]
    assert user is existing
    assert session.added == []
