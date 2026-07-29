"""OAuth 사용자 upsert·이메일 해시 단위테스트 — resolve_user/email_hash. OAuth-a.

라이브 DB 없음: 가짜 session(.scalar/.add/.flush)으로 upsert 분기(신규 생성·기존 반환)를 검증.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError
from whymath_backend.api.auth import OAuthIdentity, email_hash, resolve_user
from whymath_backend.config import Settings
from whymath_backend.db.models.user import UserProfile
from whymath_backend.schema.enums import Persona

# resolve_user는 서버측 is_minor 파생에 minor_consent_age(기본 14)를 쓴다 — 기본 Settings 주입.
_SETTINGS = Settings()


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


def _identity(email: str = "a@b.com", *, birth_year: int | None = None) -> OAuthIdentity:
    return OAuthIdentity(provider="kakao", subject="123", email=email, birth_year=birth_year)


def test_email_hash_normalized_and_64_hex() -> None:
    """이메일 해시는 정규화(소문자·trim) + 64자 hex(결정론)."""
    assert email_hash("A@B.com") == email_hash("  a@b.com  ")
    assert len(email_hash("a@b.com")) == 64


@pytest.mark.asyncio
async def test_resolve_creates_new_user_with_default_persona() -> None:
    """기존 사용자 없음 → 신규 생성(기본 페르소나 A·이메일 해시 키·session.add)."""
    session = _FakeSession(existing=None)
    user = await resolve_user(session, _identity(), settings=_SETTINGS)  # type: ignore[arg-type]
    assert isinstance(user, UserProfile)
    assert user.persona_primary == Persona.A_일반고고3
    assert user.email_hash == email_hash("a@b.com")
    assert user.user_id is not None
    # birth_year 미제공(OAuthIdentity 기본 None) → is_minor도 None(미상은 게이트 통과 설계).
    assert user.is_minor is None
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
    user = await resolve_user(session, _identity(), settings=_SETTINGS)  # type: ignore[arg-type]
    assert user is existing
    assert session.added == []


# current_year_kst() 실시계 기반이라 출생연도는 *현재 연도 기준 오프셋*으로 잡아 시간 무관하게.
_NOW_YEAR = datetime.now(tz=timezone.utc).year


@pytest.mark.asyncio
async def test_resolve_derives_is_minor_true_for_minor_birth_year() -> None:
    """신규 사용자: identity.birth_year가 명백한 미성년(연나이 8) → is_minor=True 서버 파생."""
    session = _FakeSession(existing=None)
    minor_birth_year = _NOW_YEAR - 8  # 연나이 8 ≤ 14
    user = await resolve_user(
        session, _identity(birth_year=minor_birth_year), settings=_SETTINGS  # type: ignore[arg-type]
    )
    assert user.birth_year == minor_birth_year
    assert user.is_minor is True


@pytest.mark.asyncio
async def test_resolve_derives_is_minor_false_for_adult_birth_year() -> None:
    """신규 사용자: identity.birth_year가 성인(연나이 30) → is_minor=False 서버 파생."""
    session = _FakeSession(existing=None)
    adult_birth_year = _NOW_YEAR - 30  # 연나이 30 > 14
    user = await resolve_user(
        session, _identity(birth_year=adult_birth_year), settings=_SETTINGS  # type: ignore[arg-type]
    )
    assert user.birth_year == adult_birth_year
    assert user.is_minor is False


def test_oauth_identity_ignores_unknown_is_minor_field() -> None:
    """OAuthIdentity는 is_minor 필드가 없다(extra=forbid) — 외부가 is_minor를 주입할 표면 자체 차단.

    is_minor는 birth_year에서 *서버 파생*만 한다(클라/provider 입력 미신뢰). 신원 모델에 is_minor를
    실으려는 시도는 검증 단계에서 거부된다(우회 표면 봉쇄).
    """
    with pytest.raises(ValidationError):
        OAuthIdentity(
            provider="kakao", subject="s", email="a@b.com", is_minor=False  # type: ignore[call-arg]
        )
