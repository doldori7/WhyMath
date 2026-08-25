"""개인정보 처리 권한 API — Policy Enforcement Point(PEP) HTTP 표면.

다른 서비스/프론트가 "이 사용자 데이터를 이 목적으로 처리해도 되는가?"를 묻는 엔드포인트.
v0는 `ConsentScope` 기반 동의 판정만 수행. 추후 데이터 카테고리·처리자·보존 정책을
확장할 수 있도록 인터페이스를 열어둔다.

법적 경계: 본 API는 기술적 판정. 동의 문안·법적 처리근거는 변호사 자문(MGMT-02) 후 확정.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from whymath_backend.api._auth import get_current_user
from whymath_backend.db.models.user import UserProfile
from whymath_backend.db.session import get_session
from whymath_backend.privacy.authorize import authorize_processing
from whymath_backend.schema.enums import ConsentScope

router = APIRouter(prefix="/v1/privacy", tags=["privacy"])


class PrivacyAuthorizeRequest(BaseModel):
    """`POST /v1/privacy/authorize` 요청."""

    model_config = ConfigDict(extra="forbid", use_enum_values=True)

    scope: ConsentScope = Field(description="처리 목적(ConsentScope).")


class PrivacyAuthorizeResponse(BaseModel):
    """`POST /v1/privacy/authorize` 응답."""

    model_config = ConfigDict(extra="forbid")

    allowed: bool = Field(description="처리 허용 여부.")
    reason: str = Field(description="판정 사유(예: VALID_CONSENT / NO_VALID_CONSENT).")
    scope: str = Field(description="요청된 처리 목적.")


@router.post(
    "/authorize",
    response_model=PrivacyAuthorizeResponse,
    summary="개인정보 처리 권한 판정 — ConsentScope 기반",
)
async def privacy_authorize(
    body: PrivacyAuthorizeRequest,
    user: Annotated[UserProfile, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> PrivacyAuthorizeResponse:
    """현재 사용자의 데이터를 `scope` 목적으로 처리할 수 있는지 판정."""
    decision = await authorize_processing(session, user, scope=body.scope)
    return PrivacyAuthorizeResponse(
        allowed=decision.allowed,
        reason=decision.reason or "UNKNOWN",
        scope=decision.scope.value if decision.scope else body.scope.value,
    )
