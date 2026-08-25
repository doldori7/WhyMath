"""개인정보 처리 권한 판정 — Policy Enforcement Point(PEP) v0.

EOS Privacy & Consent Platform 검토(§81~§83)의 핵심 요구를 구현: 다른 서비스가 직접
consent table을 조회하지 않고, "이 사용자 데이터를 이 목적으로 처리할 수 있는가?"를
단일 함수/엔드포인트에 묻는다.

현재 v0는 `ConsentScope` 기반의 동의 여부만 판정. 추후 `ProcessingPurposeRegistry`,
`DataCategoryRegistry`, `ProcessorRegistry`가 생기면 판정 입력에 데이터 카테고리·처리자·
보존 정책을 추가할 수 있도록 인터페이스를 열어둔다.

법적 경계: 본 모듈은 기술적 게이트. 동의 문안·법적 처리근거·보존 연한은 변호사 자문
(MGMT-02) 후 확정되어야 한다.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from whymath_backend.api._auth import has_scope_consent
from whymath_backend.db.models.user import UserProfile
from whymath_backend.schema.enums import ConsentScope

__all__ = [
    "AuthorizationDecision",
    "authorize_processing",
    "reason_for",
]


@dataclass(frozen=True, slots=True)
class AuthorizationDecision:
    """개인정보 처리 권한 판정 결과."""

    allowed: bool
    reason: str | None = None
    scope: ConsentScope | None = None


def reason_for(allowed: bool) -> str:
    """allowed 여부에 따른 기본 사유."""
    return "VALID_CONSENT" if allowed else "NO_VALID_CONSENT"


async def authorize_processing(
    session: AsyncSession,
    user: UserProfile,
    *,
    scope: ConsentScope,
) -> AuthorizationDecision:
    """사용자 `user`의 데이터를 `scope` 목적으로 처리할 수 있는지 판정.

    Args:
        session: 데이터베이스 세션.
        user: 처리 대상 사용자(또는 데이터 주체).
        scope: 처리 목적(`ConsentScope`).

    Returns:
        AuthorizationDecision — `allowed`와 거부 시 사유.
    """
    allowed = await has_scope_consent(user, session, scope)
    return AuthorizationDecision(
        allowed=allowed,
        reason=reason_for(allowed),
        scope=scope,
    )


async def authorize_processing_by_id(
    session: AsyncSession,
    user_id: uuid.UUID,
    *,
    scope: ConsentScope,
) -> AuthorizationDecision | None:
    """UserProfile을 먼저 조회한 뒤 `authorize_processing`을 수행.

    사용자가 없으면 None을 반환(호출자가 404 처리).
    """
    user = await session.get(UserProfile, user_id)
    if user is None:
        return None
    return await authorize_processing(session, user, scope=scope)
