"""Rights & Provenance HTTP API — `/v1/rights`.

엔드포인트:
  - POST /v1/rights/check            — 단건 권리 판정.
  - POST /v1/rights/batch-check        — 다건 권리 판정.
  - GET  /v1/rights/{content_type}/{content_id} — 콘텐츠 DISPLAY 기준 판정.

인가:
  - check/batch-check: 인증된 사용자(학생/교사/관리자).
  - 쓰기(생성/수정)는 MVP 범위 밖 — 관리자 UI/CMS에서 별도 관리 예정.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from whymath_backend.api._auth import CurrentUser
from whymath_backend.db.session import get_session
from whymath_backend.l1.rights.gateway import RightsGateway
from whymath_backend.schema.rights import (
    RightsCheckRequest,
    RightsCheckResponse,
)

router = APIRouter(prefix="/v1/rights", tags=["rights"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]


@router.post(
    "/check",
    response_model=RightsCheckResponse,
    summary="단건 권리 판정",
)
async def check_rights(
    body: RightsCheckRequest,
    session: SessionDep,
    _user: CurrentUser,
) -> RightsCheckResponse:
    """content_type/content_id/action에 대한 권리 판정을 반환한다."""
    gateway = RightsGateway(session)
    return await gateway.check(body)


@router.post(
    "/batch-check",
    response_model=list[RightsCheckResponse],
    summary="다건 권리 판정",
)
async def batch_check_rights(
    body: list[RightsCheckRequest],
    session: SessionDep,
    _user: CurrentUser,
) -> list[RightsCheckResponse]:
    """여러 콘텐츠·행위에 대한 권리 판정을 일괄 반환한다."""
    gateway = RightsGateway(session)
    return [await gateway.check(req) for req in body]


@router.get(
    "/{content_type}/{content_id}",
    response_model=RightsCheckResponse,
    summary="콘텐츠 DISPLAY 판정",
)
async def get_content_rights(
    content_type: str,
    content_id: uuid.UUID,
    session: SessionDep,
    _user: CurrentUser,
) -> RightsCheckResponse:
    """content_type/content_id에 대해 DISPLAY 행위 기준으로 판정한다."""
    from whymath_backend.schema.enums import PermissionAction

    request = RightsCheckRequest(
        content_type=content_type,
        content_id=content_id,
        action=PermissionAction.DISPLAY,
    )
    gateway = RightsGateway(session)
    return await gateway.check(request)
