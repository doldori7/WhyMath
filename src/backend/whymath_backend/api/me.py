"""현재 사용자 본인 학습 데이터 — `/v1/me/{sessions,assessments,dialogues}`.

`ConsentedUser`(인증 + 미성년 동의 게이트) 후 **`WHERE user_id == current_user.user_id`로만**
조회한다 — 본인 데이터 스코핑(타인 데이터 차단, CLAUDE.md 미성년 PII·식별 분석 외부 노출 금지).
읽기 전용·최신순(started_at desc, PK로 안정 정렬)·limit/offset. 쓰기·자식(turn 등) 상세·관리자
(타인) 조회는 범위 밖.

slice 50: `PATCH /v1/me/sessions/{id}/end` — 본인 학습 세션 종료(ended_at 채움). idempotent
(이미 종료된 세션은 ended_at 보존하고 200). 미존재·타인 소유 모두 404(정보 비누설·slice 24 패턴).

slice 51: `DELETE /v1/me/sessions/{id}` — GDPR 본인 학습 세션 영구 삭제. 204 No Content.
미존재·타인 소유 모두 404(슬라이스 50과 동일 비누설). 자식(attempt·turn) cascade는 DB 레벨
정책(현재 ORM CASCADE 미지정·RESTRICT 기본) — 자식 존재 시 500 FK 위반. v1 한계로 명시.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from whymath_backend.api._auth import ConsentedUser
from whymath_backend.db.models.activity import LearningSession
from whymath_backend.db.models.assessment import Assessment
from whymath_backend.db.models.dialogue import Dialogue
from whymath_backend.db.session import get_session
from whymath_backend.schema.activity import LearningSession as LearningSessionSchema
from whymath_backend.schema.assessment import Assessment as AssessmentSchema
from whymath_backend.schema.dialogue import Dialogue as DialogueSchema

router = APIRouter(prefix="/v1/me", tags=["me"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]
Limit = Annotated[int, Query(ge=1, le=200, description="페이지 크기")]
Offset = Annotated[int, Query(ge=0, description="건너뛸 행 수")]


@router.get("/sessions", response_model=list[LearningSessionSchema], summary="내 학습 세션")
async def list_my_sessions(
    user: ConsentedUser, session: SessionDep, limit: Limit = 50, offset: Offset = 0
) -> list[LearningSessionSchema]:
    """본인 학습 세션 — 최신순. 타인 데이터는 조회 불가(user_id 스코핑)."""
    stmt = (
        select(LearningSession)
        .where(LearningSession.user_id == user.user_id)
        .order_by(LearningSession.started_at.desc(), LearningSession.session_id)
        .limit(limit)
        .offset(offset)
    )
    result = await session.execute(stmt)
    return [row.to_schema() for row in result.scalars().all()]


@router.get("/assessments", response_model=list[AssessmentSchema], summary="내 진단 이력")
async def list_my_assessments(
    user: ConsentedUser, session: SessionDep, limit: Limit = 50, offset: Offset = 0
) -> list[AssessmentSchema]:
    """본인 진단(Assessment) 이력 — 최신순. user_id 스코핑."""
    stmt = (
        select(Assessment)
        .where(Assessment.user_id == user.user_id)
        .order_by(Assessment.started_at.desc(), Assessment.assessment_id)
        .limit(limit)
        .offset(offset)
    )
    result = await session.execute(stmt)
    return [row.to_schema() for row in result.scalars().all()]


@router.get("/dialogues", response_model=list[DialogueSchema], summary="내 대화 이력")
async def list_my_dialogues(
    user: ConsentedUser, session: SessionDep, limit: Limit = 50, offset: Offset = 0
) -> list[DialogueSchema]:
    """본인 Socratic 대화 이력 — 최신순. user_id 스코핑(턴 상세는 범위 밖)."""
    stmt = (
        select(Dialogue)
        .where(Dialogue.user_id == user.user_id)
        .order_by(Dialogue.started_at.desc(), Dialogue.dialogue_id)
        .limit(limit)
        .offset(offset)
    )
    result = await session.execute(stmt)
    return [row.to_schema() for row in result.scalars().all()]


@router.patch(
    "/sessions/{session_id}/end",
    response_model=LearningSessionSchema,
    summary="내 학습 세션 종료(ended_at 채움)",
)
async def end_my_session(
    session_id: uuid.UUID,
    user: ConsentedUser,
    session: SessionDep,
) -> LearningSessionSchema:
    """slice 50: 본인 학습 세션을 종료(`ended_at` = now).

    *idempotent*: 이미 종료된 세션은 기존 `ended_at` 보존·재호출도 200(현 상태 반환).
    미존재·타인 소유 모두 **404**(정보 비누설·slice 24 패턴 — 존재 여부 노출 차단).
    """
    row = await session.get(LearningSession, session_id)
    if row is None or row.user_id != user.user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="학습 세션을 찾을 수 없습니다.",
        )
    if row.ended_at is None:
        row.ended_at = datetime.now(UTC)
        await session.commit()
    return row.to_schema()


@router.delete(
    "/sessions/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="내 학습 세션 영구 삭제(GDPR)",
)
async def delete_my_session(
    session_id: uuid.UUID,
    user: ConsentedUser,
    session: SessionDep,
) -> None:
    """slice 51: 본인 학습 세션을 영구 삭제 — GDPR 데이터 삭제권 결선.

    미존재·타인 소유 모두 **404**(slice 24/50 패턴·정보 비누설). 자식 행(ProblemAttempt·
    AttemptEvent·DialogueTurn)이 RESTRICT FK라 자식 존재 시 *DB가 FK 위반*으로 500 반환할
    수 있음(v1 한계). 자식 cascade·자식 사전 삭제는 후속.
    """
    row = await session.get(LearningSession, session_id)
    if row is None or row.user_id != user.user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="학습 세션을 찾을 수 없습니다.",
        )
    await session.delete(row)
    await session.commit()
