"""Rights Gateway — 콘텐츠 ↔ 권리/출처 조회 + Policy Engine 연동 (LIC-01).

AI 파이프라인·RAG·학생 UI 등 모든 소비자가 사용하는 통합 진입점.
DB 세션 하나로 content-source-rights-holder를 조인/조회하고,
Policy Engine 판정 + 출처 문구 자동 생성까지 수행한다.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from whymath_backend.db.models.rights import ContentRightsLink
from whymath_backend.db.models.rights import RightsEntity as ORMRightsEntity
from whymath_backend.db.models.rights import RightsHolderEntity as ORMRightsHolderEntity
from whymath_backend.db.models.rights import SourceEntity as ORMSourceEntity
from whymath_backend.l1.rights.attribution import build_attribution
from whymath_backend.l1.rights.policy_engine import check_content_rights
from whymath_backend.schema.enums import PermissionAction
from whymath_backend.schema.rights import (
    RightsCheckRequest,
    RightsCheckResponse,
    RightsEntity,
    RightsHolderEntity,
    SourceEntity,
)

__all__ = ["RightsGateway"]


class RightsGateway:
    """콘텐츠 권리 판정 게이트웨이."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def check(self, request: RightsCheckRequest) -> RightsCheckResponse:
        """요청에 따라 콘텐츠 권리를 판정한다."""
        rights_list = await self._load_rights(request.content_type, request.content_id)
        sources = await self._load_sources(request.content_type, request.content_id)
        holders = await self._load_holders(rights_list)

        request_context: dict[str, Any] = {}
        if request.user_type:
            request_context["user_type"] = request.user_type
        if request.country:
            request_context["country"] = request.country
        if request.subscription_tier:
            request_context["subscription_tier"] = request.subscription_tier

        response = check_content_rights(
            content_type=request.content_type,
            content_id=request.content_id,
            rights_list=rights_list,
            action=request.action,
            sources=sources,
            holders=holders,
            request_context=request_context,
        )

        # 출처 표시가 필요한 결정이면 attribution 자동 생성
        if response.decision in (
            "ALLOW_WITH_ATTRIBUTION",
            "ALLOW_WITH_RESTRICTIONS",
        ):
            primary_source = sources[0] if sources else None
            primary_rights = rights_list[0] if rights_list else None
            holder: RightsHolderEntity | None = None
            if primary_rights and primary_rights.holder_id is not None:
                holder = holders.get(primary_rights.holder_id)
            response.attribution = build_attribution(primary_source, primary_rights, holder)

        return response

    async def can_display(
        self,
        content_type: str,
        content_id: uuid.UUID,
        user_type: str | None = None,
        country: str | None = None,
        subscription_tier: str | None = None,
    ) -> bool:
        """학생/교사 UI 표시 가능 여부."""
        request = RightsCheckRequest(
            content_type=content_type,
            content_id=content_id,
            action=PermissionAction.DISPLAY,
            user_type=user_type,
            country=country,
            subscription_tier=subscription_tier,
        )
        response = await self.check(request)
        return response.decision in (
            "ALLOW",
            "ALLOW_WITH_ATTRIBUTION",
            "ALLOW_WITH_RESTRICTIONS",
        )

    async def can_use_for_ai(
        self,
        content_type: str,
        content_id: uuid.UUID,
        action: PermissionAction,
        user_type: str | None = None,
        country: str | None = None,
        subscription_tier: str | None = None,
    ) -> bool:
        """AI 파이프라인/RAG/임베딩 등 AI 용도 사용 가능 여부.

        `action`은 PermissionAction.AI_TRAINING, AI_CONTEXT, RAG_INDEX 등.
        """
        request = RightsCheckRequest(
            content_type=content_type,
            content_id=content_id,
            action=action,
            user_type=user_type,
            country=country,
            subscription_tier=subscription_tier,
        )
        response = await self.check(request)
        return response.decision in (
            "ALLOW",
            "ALLOW_WITH_ATTRIBUTION",
            "ALLOW_WITH_RESTRICTIONS",
        )

    async def _load_rights(
        self,
        content_type: str,
        content_id: uuid.UUID,
    ) -> list[RightsEntity]:
        """콘텐츠에 연결된 RightsEntity 목록을 조회한다."""
        result = await self._session.execute(
            select(ORMRightsEntity)
            .join(
                ContentRightsLink,
                (ContentRightsLink.rights_id == ORMRightsEntity.rights_id),
            )
            .where(
                ContentRightsLink.content_type == content_type,
                ContentRightsLink.content_id == content_id,
            )
        )
        return [row.to_schema() for row in result.scalars()]

    async def _load_sources(
        self,
        content_type: str,
        content_id: uuid.UUID,
    ) -> list[SourceEntity]:
        """콘텐츠에 연결된 SourceEntity 목록을 조회한다."""
        from whymath_backend.db.models.rights import ContentSourceLink

        result = await self._session.execute(
            select(ORMSourceEntity)
            .join(
                ContentSourceLink,
                ContentSourceLink.source_id == ORMSourceEntity.source_id,
            )
            .where(
                ContentSourceLink.content_type == content_type,
                ContentSourceLink.content_id == content_id,
            )
        )
        return [row.to_schema() for row in result.scalars()]

    async def _load_holders(
        self,
        rights_list: list[RightsEntity],
    ) -> dict[uuid.UUID, RightsHolderEntity]:
        """RightsEntity에 연결된 RightsHolder를 조회한다."""
        holder_ids = [r.holder_id for r in rights_list if r.holder_id is not None]
        if not holder_ids:
            return {}
        result = await self._session.execute(
            select(ORMRightsHolderEntity).where(ORMRightsHolderEntity.holder_id.in_(holder_ids))
        )
        return {row.holder_id: row.to_schema() for row in result.scalars()}
