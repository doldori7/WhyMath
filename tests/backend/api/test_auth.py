"""인증 의존성 단위테스트 — get_current_user(401)·get_consented_user(403)·require_role(403).

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
from sqlalchemy.dialects import postgresql

from whymath_backend.api._auth import get_consented_user, get_current_user, require_role
from whymath_backend.config import Settings
from whymath_backend.consent import current_year_kst, derive_is_minor
from whymath_backend.db.models.parental_consent import ParentalConsent
from whymath_backend.db.models.user import UserProfile
from whymath_backend.schema.enums import Role
from whymath_backend.security import create_access_token

_SECRET = "test-secret-key-0123456789abcdef"


def _settings() -> Settings:
    return Settings(jwt_secret_key=SecretStr(_SECRET))


class _FakeSession:
    """session.get(UserProfile, pk) + scalar(최신 동의 행) 모사.

    `scalar`는 SEC-20에서 `get_consented_user`가 최신 `parental_consent` 행을 읽게 되면서
    필요해졌다. 기본 None(= 원장 행 없음 → 판정 근거 부재로 통과)이며, 철회·만료 케이스는
    `consent=` 로 행을 주입한다.
    """

    def __init__(
        self, user: UserProfile | None = None, consent: ParentalConsent | None = None
    ) -> None:
        self._user = user
        self._consent = consent

    async def get(self, model: Any, pk: uuid.UUID) -> UserProfile | None:
        if self._user is not None and self._user.user_id == pk:
            return self._user
        return None

    async def scalar(self, stmt: Any) -> ParentalConsent | None:
        # 받은 statement를 실제 PG 방언으로 **컴파일**한다 — hermetic 테스트에는 실 DB가 없어서
        # 게이트의 select()가 문법·컬럼 수준에서 유효한지 검증할 곳이 여기뿐이다(실 DB 통합
        # 테스트는 WHYMATH_RUN_INTEGRATION 없이는 skip). 잘못된 컬럼·연산자면 여기서 터진다.
        str(stmt.compile(dialect=postgresql.dialect()))
        return self._consent


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


class TestActiveDeletedGate:
    """SEC-07 D1 — 비활성(is_active=False)·삭제됨(is_deleted=True) 계정은 401.

    `is_active`/`is_deleted`는 기존 컬럼이었으나 `get_current_user`가 그 첫 reader였다(그전엔
    탈퇴·비활성 계정의 미만료 토큰이 그대로 통과했다 — account_security_gap_review.md D1).
    """

    async def test_inactive_user_raises_401(self) -> None:
        settings = _settings()
        uid = uuid.uuid4()
        user = UserProfile(user_id=uid, is_active=False)
        token = create_access_token(uid, settings=settings)
        with pytest.raises(HTTPException) as exc:
            await get_current_user(
                credentials=_creds(token), session=_FakeSession(user), settings=settings  # type: ignore[arg-type]
            )
        assert exc.value.status_code == 401

    async def test_deleted_user_raises_401(self) -> None:
        settings = _settings()
        uid = uuid.uuid4()
        user = UserProfile(user_id=uid, is_deleted=True)
        token = create_access_token(uid, settings=settings)
        with pytest.raises(HTTPException) as exc:
            await get_current_user(
                credentials=_creds(token), session=_FakeSession(user), settings=settings  # type: ignore[arg-type]
            )
        assert exc.value.status_code == 401

    async def test_active_non_deleted_user_passes(self) -> None:
        """명시적으로 활성·비삭제인 사용자는 정상 통과(회귀 방지)."""
        settings = _settings()
        uid = uuid.uuid4()
        user = UserProfile(user_id=uid, is_active=True, is_deleted=False)
        token = create_access_token(uid, settings=settings)
        result = await get_current_user(
            credentials=_creds(token), session=_FakeSession(user), settings=settings  # type: ignore[arg-type]
        )
        assert result is user

    async def test_unset_is_active_is_deleted_passes(self) -> None:
        """직접 생성(미영속)해 컬럼이 None(미상)인 사용자는 차단하지 않는다(기존 동작 회귀 방지 —
        `test_valid_token_returns_user`와 동일하게 `UserProfile(user_id=uid)`만으로 생성).
        """
        settings = _settings()
        uid = uuid.uuid4()
        user = UserProfile(user_id=uid)
        assert user.is_active is None
        assert user.is_deleted is None
        token = create_access_token(uid, settings=settings)
        result = await get_current_user(
            credentials=_creds(token), session=_FakeSession(user), settings=settings  # type: ignore[arg-type]
        )
        assert result is user


class TestConsentGate:
    async def test_minor_without_consent_raises_403(self) -> None:
        user = UserProfile(user_id=uuid.uuid4(), is_minor=True, parent_consent_at=None)
        with pytest.raises(HTTPException) as exc:
            await get_consented_user(user=user, session=_FakeSession())  # type: ignore[arg-type]
        assert exc.value.status_code == 403

    async def test_minor_with_consent_passes(self) -> None:
        user = UserProfile(
            user_id=uuid.uuid4(),
            is_minor=True,
            parent_consent_at=datetime.now(tz=timezone.utc),
        )
        assert (
            await get_consented_user(user=user, session=_FakeSession())  # type: ignore[arg-type]
        ) is user

    async def test_non_minor_passes(self) -> None:
        user = UserProfile(user_id=uuid.uuid4(), is_minor=False)
        assert (
            await get_consented_user(user=user, session=_FakeSession())  # type: ignore[arg-type]
        ) is user

    async def test_unknown_minor_status_passes(self) -> None:
        """is_minor None(미상)이면 차단하지 않는다 — 알려진 미성년자만 게이트."""
        user = UserProfile(user_id=uuid.uuid4())
        assert (
            await get_consented_user(user=user, session=_FakeSession())  # type: ignore[arg-type]
        ) is user


class TestConsentRevocationExpiryGate:
    """SEC-20 D9 — 철회·만료된 동의는 게이트를 통과시키지 않는다.

    그전까지 이 게이트는 `parent_consent_at`(설정됐는가) 하나만 읽어 **한 번 받은 동의가 영구히
    유효**했고, `ParentalConsent.revoked_at`·`expires_at`은 reader가 0이었다. 아래 테스트가 그
    두 컬럼의 첫 reader를 계약으로 고정한다.
    """

    @staticmethod
    def _consented_minor() -> UserProfile:
        """게이트를 *통과하던* 상태의 미성년(동의 있음) — 여기서 원장만 바꿔 차이를 만든다."""
        return UserProfile(
            user_id=uuid.uuid4(),
            is_minor=True,
            parent_consent_at=datetime.now(tz=timezone.utc),
        )

    async def test_revoked_consent_raises_403(self) -> None:
        """철회(revoked_at 설정)된 최신 동의 → 403. parent_consent_at만으론 못 잡던 케이스."""
        user = self._consented_minor()
        revoked = ParentalConsent(
            user_id=user.user_id,
            consent_signed_at=datetime.now(tz=timezone.utc),
            revoked_at=datetime.now(tz=timezone.utc),
        )
        with pytest.raises(HTTPException) as exc:
            await get_consented_user(
                user=user, session=_FakeSession(consent=revoked)  # type: ignore[arg-type]
            )
        assert exc.value.status_code == 403
        assert "철회" in exc.value.detail

    async def test_expired_consent_raises_403(self) -> None:
        """만료(expires_at 과거)된 최신 동의 → 403.

        `expires_at`은 아직 writer가 없다(주기 숫자는 MGMT-02 선행) — 이 테스트는 값이 *있을 때*
        게이트가 존중한다는 계약을 미리 고정한다. writer가 붙는 날 이 계약이 즉시 발화한다.
        """
        user = self._consented_minor()
        expired = ParentalConsent(
            user_id=user.user_id,
            consent_signed_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
            expires_at=datetime(2020, 6, 1, tzinfo=timezone.utc),
        )
        with pytest.raises(HTTPException) as exc:
            await get_consented_user(
                user=user, session=_FakeSession(consent=expired)  # type: ignore[arg-type]
            )
        assert exc.value.status_code == 403
        assert "만료" in exc.value.detail

    async def test_future_expiry_passes(self) -> None:
        """만료 시각이 미래면 통과 — 만료 분기가 *유효한* 동의를 잠그지 않는다(과차단 방지)."""
        user = self._consented_minor()
        live = ParentalConsent(
            user_id=user.user_id,
            consent_signed_at=datetime.now(tz=timezone.utc),
            expires_at=datetime(2999, 1, 1, tzinfo=timezone.utc),
        )
        assert (
            await get_consented_user(
                user=user, session=_FakeSession(consent=live)  # type: ignore[arg-type]
            )
        ) is user

    async def test_missing_ledger_row_passes(self) -> None:
        """원장 행이 없으면 차단하지 않는다 — "판정 근거 부재"는 "철회됨"이 아니다.

        원장 도입 이전에 `parent_consent_at`만 설정된 데이터가 조용히 잠기는 것을 막는다
        (`is_minor` None을 미상으로 보고 통과시키는 방침과 동형).
        """
        user = self._consented_minor()
        assert (
            await get_consented_user(user=user, session=_FakeSession())  # type: ignore[arg-type]
        ) is user

    async def test_non_minor_skips_ledger_query(self) -> None:
        """성인·미상은 원장을 아예 조회하지 않는다 — 게이트 비용이 미성년에만 붙는다.

        `scalar`가 호출되면 터지는 세션을 주입해 *쿼리 부재*를 직접 단언한다(성능 계약).
        """

        class _ExplodingSession(_FakeSession):
            async def scalar(self, _stmt: Any) -> ParentalConsent | None:
                raise AssertionError("성인/미상 사용자에게 동의 원장 쿼리가 발생했다")

        for user in (
            UserProfile(user_id=uuid.uuid4(), is_minor=False),
            UserProfile(user_id=uuid.uuid4()),
        ):
            assert (
                await get_consented_user(
                    user=user, session=_ExplodingSession()  # type: ignore[arg-type]
                )
            ) is user


class TestDerivedMinorGateEndToEnd:
    """P4: 서버 파생 is_minor → 동의 게이트가 *실제로* 발화하는지 종단 검증.

    파생(consent.derive_is_minor)과 게이트(get_consented_user)를 한 흐름으로 묶어, 만14세 미만
    birth_year를 가진 사용자가 동의(parent_consent_at) 없이 보호된 엔드포인트에 접근하면 403이
    되는 *전체 사슬*을 확인한다(파생이 없으면 게이트가 무력하던 P4 이전 구멍이 막혔음을 증명).
    """

    async def test_derived_minor_without_consent_raises_403(self) -> None:
        """미성년 birth_year → is_minor=True 파생 → 동의 없음 → 게이트 403(구멍 폐쇄)."""
        minor_birth_year = current_year_kst() - 8  # 연나이 8 ≤ 14
        is_minor = derive_is_minor(minor_birth_year, current_year=current_year_kst(), threshold=14)
        assert is_minor is True
        user = UserProfile(
            user_id=uuid.uuid4(),
            birth_year=minor_birth_year,
            is_minor=is_minor,
            parent_consent_at=None,
        )
        with pytest.raises(HTTPException) as exc:
            await get_consented_user(user=user, session=_FakeSession())  # type: ignore[arg-type]
        assert exc.value.status_code == 403

    async def test_derived_minor_with_consent_passes(self) -> None:
        """미성년 파생이라도 parent_consent_at가 있으면 통과(동의 완료 흐름)."""
        minor_birth_year = current_year_kst() - 8
        is_minor = derive_is_minor(minor_birth_year, current_year=current_year_kst(), threshold=14)
        user = UserProfile(
            user_id=uuid.uuid4(),
            birth_year=minor_birth_year,
            is_minor=is_minor,
            parent_consent_at=datetime.now(tz=timezone.utc),
        )
        assert (
            await get_consented_user(user=user, session=_FakeSession())  # type: ignore[arg-type]
        ) is user

    async def test_derived_adult_passes_without_consent(self) -> None:
        """성인 birth_year → is_minor=False 파생 → 동의 불요로 통과."""
        adult_birth_year = current_year_kst() - 30
        is_minor = derive_is_minor(adult_birth_year, current_year=current_year_kst(), threshold=14)
        assert is_minor is False
        user = UserProfile(
            user_id=uuid.uuid4(),
            birth_year=adult_birth_year,
            is_minor=is_minor,
        )
        assert (
            await get_consented_user(user=user, session=_FakeSession())  # type: ignore[arg-type]
        ) is user


class TestRequireRole:
    """SEC-07 D1 — `require_role(*roles)`: 역할 불일치 403, 일치 시 통과."""

    async def test_matching_role_passes(self) -> None:
        user = UserProfile(user_id=uuid.uuid4(), role=Role.CONTENT_ADMIN)
        dependency = require_role(Role.CONTENT_ADMIN)
        assert await dependency(user=user) is user

    async def test_mismatched_role_raises_403(self) -> None:
        user = UserProfile(user_id=uuid.uuid4(), role=Role.STUDENT)
        dependency = require_role(Role.CONTENT_ADMIN)
        with pytest.raises(HTTPException) as exc:
            await dependency(user=user)
        assert exc.value.status_code == 403

    async def test_multiple_allowed_roles(self) -> None:
        """가변인자로 여러 역할을 허용할 수 있다(범용성 확인 — v0은 실제 2값만 존재)."""
        user = UserProfile(user_id=uuid.uuid4(), role=Role.STUDENT)
        dependency = require_role(Role.STUDENT, Role.CONTENT_ADMIN)
        assert await dependency(user=user) is user

    async def test_unset_role_raises_403(self) -> None:
        """직접 생성(미영속)해 role이 None(미상)이면 관리자 게이트는 기본 거부한다."""
        user = UserProfile(user_id=uuid.uuid4())
        assert user.role is None
        dependency = require_role(Role.CONTENT_ADMIN)
        with pytest.raises(HTTPException) as exc:
            await dependency(user=user)
        assert exc.value.status_code == 403
