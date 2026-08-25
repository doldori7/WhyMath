"""privacy/authorize.py Policy Enforcement Point(PEP) 단위테스트.

EOS Privacy & Consent Platform(§81~§83)의 핵심 판정 함수 `authorize_processing`이
`ConsentScope`별 동의 상태를 올바르게 반영하는지 검증한다. 다른 서비스가 consent table을
직접 조회하지 않고 PEP에 묻는 구조의 계약을 고정한다.
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.dialects import postgresql

from whymath_backend.db.models.parental_consent import ParentalConsent
from whymath_backend.db.models.user import UserProfile
from whymath_backend.privacy.authorize import authorize_processing
from whymath_backend.schema.enums import ConsentScope


class _FakeSession:
    """PEP 테스트용 최소 가짜 세션 — `session.get(UserProfile)` + 동의 원장 1건 조회."""

    def __init__(
        self,
        user: UserProfile | None = None,
        consent: ParentalConsent | None = None,
    ) -> None:
        self._user = user
        self._consent = consent

    async def get(self, model: Any, pk: uuid.UUID) -> UserProfile | None:
        if self._user is not None and self._user.user_id == pk:
            return self._user
        return None

    async def scalar(self, stmt: Any) -> ParentalConsent | None:
        # 받은 statement를 실제 PG 방언으로 컴파일해 select()의 유효성도 함께 검증한다.
        # literal_binds=True로 실제 바인딩 값이 SQL 문자열에 노출되도록 해 scope을 추출한다.
        compiled = str(
            stmt.compile(
                dialect=postgresql.dialect(),
                compile_kwargs={"literal_binds": True},
            )
        )
        # where 절에서 조회하려는 consent_scope 값을 추출한다(실제 필터링 모사).
        # 단일 equality(`=`)와 core scope용 IN(`IN ('service_core', 'ai_inference')`)를
        # 모두 지원한다.
        eq_match = re.search(r"consent_scope = '([^']+)'", compiled)
        if eq_match is not None:
            expected_scopes = {eq_match.group(1)}
        else:
            in_match = re.search(r"consent_scope IN \(([^)]+)\)", compiled)
            if in_match is not None:
                expected_scopes = set(re.findall(r"'([^']+)'", in_match.group(1)))
            else:
                expected_scopes = set()
        # 동의 원장은 주어진 user의 것이어야 하고, 요청 scope과도 일치해야 한다.
        if self._consent is None or self._user is None:
            return None
        if self._consent.user_id != self._user.user_id:
            return None
        if expected_scopes and self._consent.consent_scope not in expected_scopes:
            return None
        return self._consent


def _adult_user() -> UserProfile:
    return UserProfile(user_id=uuid.uuid4(), is_minor=False)


def _minor_user(*, consent_at: datetime | None = None) -> UserProfile:
    return UserProfile(
        user_id=uuid.uuid4(),
        is_minor=True,
        parent_consent_at=consent_at,
    )


def _consent(
    scope: str,
    user_id: uuid.UUID | None = None,
    *,
    revoked: bool = False,
    expired: bool = False,
) -> ParentalConsent:
    now = datetime.now(tz=timezone.utc)
    return ParentalConsent(
        consent_id=uuid.uuid4(),
        user_id=user_id or uuid.uuid4(),
        consent_scope=scope,
        consent_signed_at=now,
        revoked_at=now if revoked else None,
        expires_at=(now if expired else None),
    )


class TestAuthorizeProcessing:
    async def test_adult_service_core_allowed(self) -> None:
        """성인은 서비스 본 기능(service_core/ai_inference) 처리가 허용된다."""
        user = _adult_user()
        decision = await authorize_processing(
            _FakeSession(user), user, scope=ConsentScope.service_core
        )
        assert decision.allowed is True
        assert decision.scope is ConsentScope.service_core

    async def test_adult_ai_training_denied_by_default(self) -> None:
        """성인도 별도 성인 동의 저장소가 없으면 ai_training은 기본 거부(privacy-by-default)."""
        user = _adult_user()
        decision = await authorize_processing(
            _FakeSession(user), user, scope=ConsentScope.ai_training
        )
        assert decision.allowed is False
        assert decision.reason == "NO_VALID_CONSENT"

    async def test_minor_without_consent_denied(self) -> None:
        """미성년자가 동의 없으면 service_core도 거부된다."""
        user = _minor_user()
        decision = await authorize_processing(
            _FakeSession(user), user, scope=ConsentScope.service_core
        )
        assert decision.allowed is False

    async def test_minor_with_service_core_consent_allowed(self) -> None:
        """미성년자가 service_core 동의를 받으면 해당 scope은 허용된다."""
        user = _minor_user(consent_at=datetime.now(tz=timezone.utc))
        consent = _consent("service_core", user_id=user.user_id)
        decision = await authorize_processing(
            _FakeSession(user, consent), user, scope=ConsentScope.service_core
        )
        assert decision.allowed is True

    async def test_minor_ai_inference_consent_satisfies_service_core(self) -> None:
        """`ai_inference` 동의는 서비스 본 기능(core) 처리에 대해서도 허용된다."""
        user = _minor_user(consent_at=datetime.now(tz=timezone.utc))
        consent = _consent("ai_inference", user_id=user.user_id)
        decision = await authorize_processing(
            _FakeSession(user, consent), user, scope=ConsentScope.service_core
        )
        assert decision.allowed is True

    async def test_minor_ai_training_requires_separate_consent(self) -> None:
        """service_core 동의만으로 ai_training은 허용되지 않는다(EOS §48 분리 원칙)."""
        user = _minor_user(consent_at=datetime.now(tz=timezone.utc))
        service_consent = _consent("service_core", user_id=user.user_id)
        decision = await authorize_processing(
            _FakeSession(user, service_consent), user, scope=ConsentScope.ai_training
        )
        assert decision.allowed is False

    async def test_minor_with_ai_training_consent_allowed(self) -> None:
        """미성년자가 ai_training 동의를 별도로 받으면 허용된다."""
        user = _minor_user(consent_at=datetime.now(tz=timezone.utc))
        consent = _consent("ai_training", user_id=user.user_id)
        decision = await authorize_processing(
            _FakeSession(user, consent), user, scope=ConsentScope.ai_training
        )
        assert decision.allowed is True

    async def test_revoked_ai_training_consent_denied(self) -> None:
        """ai_training 동의가 철회되면 해당 처리는 거부된다."""
        user = _minor_user(consent_at=datetime.now(tz=timezone.utc))
        consent = _consent("ai_training", user_id=user.user_id, revoked=True)
        decision = await authorize_processing(
            _FakeSession(user, consent), user, scope=ConsentScope.ai_training
        )
        assert decision.allowed is False

    async def test_authorize_by_id_returns_none_for_missing_user(self) -> None:
        """UserProfile 조회 실패 시 authorize_processing_by_id는 None을 반환한다."""
        from whymath_backend.privacy.authorize import authorize_processing_by_id

        result = await authorize_processing_by_id(
            _FakeSession(), uuid.uuid4(), scope=ConsentScope.ai_training
        )
        assert result is None
