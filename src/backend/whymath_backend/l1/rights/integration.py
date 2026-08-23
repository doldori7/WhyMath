"""Rights Gateway와 외부 파이프라인의 연동 헬퍼 (LIC-01).

AI 문항 생성, RAG, 임베딩, 학생 노출 등 다양한 진입점에서
`RightsGateway.can_use_for_ai()` / `can_display()`를 쉽게 호출할 수 있게 한다.
"""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from whymath_backend.l1.rights.gateway import RightsGateway
from whymath_backend.schema.enums import PermissionAction
from whymath_backend.schema.problem import Problem

__all__ = [
    "can_problem_be_displayed",
    "can_problem_be_used_for_rag",
    "can_problem_be_used_for_ai_context",
    "can_problem_be_used_for_ai_training",
]


def _problem_key(problem: Problem) -> tuple[str, uuid.UUID]:
    """Rights Gateway가 사용하는 content_type/content_id 키."""
    return ("problem", problem.problem_id)


async def can_problem_be_displayed(
    session: AsyncSession,
    problem: Problem,
    user_type: str | None = None,
    country: str | None = None,
) -> bool:
    """학생/교사에게 해당 문항을 표시할 수 있는지 판정한다."""
    content_type, content_id = _problem_key(problem)
    gateway = RightsGateway(session)
    return await gateway.can_display(
        content_type=content_type,
        content_id=content_id,
        user_type=user_type,
        country=country,
    )


async def can_problem_be_used_for_rag(
    session: AsyncSession,
    problem: Problem,
    user_type: str | None = None,
    country: str | None = None,
) -> bool:
    """해당 문항을 RAG 인덱스/검색에 사용할 수 있는지 판정한다."""
    content_type, content_id = _problem_key(problem)
    gateway = RightsGateway(session)
    return await gateway.can_use_for_ai(
        content_type=content_type,
        content_id=content_id,
        action=PermissionAction.RAG_INDEX,
        user_type=user_type,
        country=country,
    )


async def can_problem_be_used_for_ai_context(
    session: AsyncSession,
    problem: Problem,
    user_type: str | None = None,
    country: str | None = None,
) -> bool:
    """해당 문항을 LLM 프롬프트 컨텍스트로 사용할 수 있는지 판정한다."""
    content_type, content_id = _problem_key(problem)
    gateway = RightsGateway(session)
    return await gateway.can_use_for_ai(
        content_type=content_type,
        content_id=content_id,
        action=PermissionAction.AI_CONTEXT,
        user_type=user_type,
        country=country,
    )


async def can_problem_be_used_for_ai_training(
    session: AsyncSession,
    problem: Problem,
    user_type: str | None = None,
    country: str | None = None,
) -> bool:
    """해당 문항을 LLM 학습/파인튜닝 데이터로 사용할 수 있는지 판정한다."""
    content_type, content_id = _problem_key(problem)
    gateway = RightsGateway(session)
    return await gateway.can_use_for_ai(
        content_type=content_type,
        content_id=content_id,
        action=PermissionAction.AI_TRAINING,
        user_type=user_type,
        country=country,
    )
