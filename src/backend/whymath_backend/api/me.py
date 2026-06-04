"""현재 사용자 본인 학습 데이터 — `/v1/me/{sessions,assessments,dialogues}`.

`ConsentedUser`(인증 + 미성년 동의 게이트) 후 **`WHERE user_id == current_user.user_id`로만**
조회한다 — 본인 데이터 스코핑(타인 데이터 차단, CLAUDE.md 미성년 PII·식별 분석 외부 노출 금지).
읽기 전용·최신순(started_at desc, PK로 안정 정렬)·limit/offset. 쓰기·자식(turn 등) 상세·관리자
(타인) 조회는 범위 밖.

slice 50: `PATCH /v1/me/sessions/{id}/end` — 본인 학습 세션 종료(ended_at 채움). idempotent
(이미 종료된 세션은 ended_at 보존하고 200). 미존재·타인 소유 모두 404(정보 비누설·slice 24 패턴).

slice 51: `DELETE /v1/me/sessions/{id}` — GDPR 본인 학습 세션 영구 삭제. 204 No Content.
미존재·타인 소유 모두 404(슬라이스 50과 동일 비누설). 자식 cascade는 slice 56 참조.

slice 52: `PATCH /v1/me/dialogues/{id}/end` + `DELETE /v1/me/dialogues/{id}` — Dialogue
도메인에 슬라이스 50/51 패턴 답습. 본인 소유 검증·404 비누설·idempotent end·204 delete 동형.

slice 53: `PATCH /v1/me/assessments/{id}/complete` + `DELETE /v1/me/assessments/{id}` —
Assessment 도메인 lifecycle. *명칭은 `/complete`*(진단은 "종료"가 아니라 "완료"라 모델 컬럼
`completed_at`을 따라간다 — slice 50/52의 `ended_at`과 의미 분리). idempotent complete·
204 delete·404 비누설은 50/51/52와 동일 패턴. 세 도메인(LearningSession·Dialogue·Assessment)
lifecycle 완비 — 이식 비용 minimization 4회차 검증.

slice 55: 슬라이스 50~53의 end/complete·delete 6 라우터가 *동형 반복*(fetch→소유검증→404→
commit)하던 중복을 제네릭 헬퍼 `_close_owned_resource`·`_delete_owned_resource`(공통
`_get_owned_or_404`)로 추출 — 라우터는 헬퍼 1줄 호출로 축소. 동작·응답 불변(순수 리팩터).
mypy strict 정합은 *제약 TypeVar*로 해소(아래 헬퍼 주석 참조).

slice 56: GDPR 삭제 cascade 정책 — DB FK `ON DELETE CASCADE`로 직속 자식 자동 제거
(learning_session→problem_attempt·dialogue→dialogue_turn), attempt를 참조하던
dialogue.attempt_id는 `SET NULL`(대화 보존). 슬라이스 51/52의 RESTRICT FK 한계 해소
(라우터 코드 무변경 — DB 레벨 정책·alembic c3d4e5f6a7b8). attempt_event(loose ref)는 고아 잔존.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated, TypeVar

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


# ── slice 55: 본인 소유 리소스 lifecycle 제네릭 헬퍼 ──────────────────────────
# 슬라이스 50~53이 LearningSession·Dialogue·Assessment 세 도메인에 end/complete·delete를
# *동형 반복*(fetch→소유검증→404→commit)했다(4회차 답습). 그 중복을 헬퍼로 압축한다.
# **mypy strict 정합**(slice 53이 짚은 dispatch 위험 해소): 제약(constrained) TypeVar로
# 세 ORM만 허용 → `row.user_id`(셋 다 보유)·반환 `row.to_schema()`(호출자에서 구체 타입
# 추론)가 타입 안전. close 컬럼은 도메인마다 달라(ended_at vs completed_at) 필드명을 인자로
# 받아 get/setattr로 동적 접근(인자 변수라 ruff B009/B010 미해당).
_LifecycleRow = TypeVar("_LifecycleRow", LearningSession, Dialogue, Assessment)


async def _get_owned_or_404(
    session: AsyncSession,
    model: type[_LifecycleRow],
    pk: uuid.UUID,
    owner_id: uuid.UUID,
    not_found_detail: str,
) -> _LifecycleRow:
    """PK 조회 후 본인 소유 검증 — 미존재·타인 소유 모두 404(정보 비누설·slice 24 패턴)."""
    row = await session.get(model, pk)
    if row is None or row.user_id != owner_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=not_found_detail)
    return row


async def _close_owned_resource(
    session: AsyncSession,
    model: type[_LifecycleRow],
    pk: uuid.UUID,
    owner_id: uuid.UUID,
    close_field: str,
    not_found_detail: str,
) -> _LifecycleRow:
    """본인 소유 리소스 lifecycle 종료 — `close_field`(ended_at/completed_at)를 now로.

    *idempotent*: 이미 채워졌으면 보존하고 commit 안 함(현 상태 반환). slice 50/52/53 동형.
    """
    row = await _get_owned_or_404(session, model, pk, owner_id, not_found_detail)
    if getattr(row, close_field) is None:
        setattr(row, close_field, datetime.now(UTC))
        await session.commit()
    return row


async def _delete_owned_resource(
    session: AsyncSession,
    model: type[_LifecycleRow],
    pk: uuid.UUID,
    owner_id: uuid.UUID,
    not_found_detail: str,
) -> None:
    """본인 소유 리소스 영구 삭제(GDPR) — 204. slice 51/52/53 동형. slice 56: 직속 자식은
    ON DELETE CASCADE로 자동 제거(session→attempt·dialogue→turn)·dialogue.attempt_id는
    SET NULL. attempt_event(loose ref·FK 아님)는 고아 잔존(설계 한계)."""
    row = await _get_owned_or_404(session, model, pk, owner_id, not_found_detail)
    await session.delete(row)
    await session.commit()


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
    """slice 50 (slice 55 리팩터): 본인 학습 세션 종료(`ended_at`=now)·idempotent·404 비누설."""
    row = await _close_owned_resource(
        session,
        LearningSession,
        session_id,
        user.user_id,
        "ended_at",
        "학습 세션을 찾을 수 없습니다.",
    )
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
    """slice 51 (slice 55 리팩터): 본인 학습 세션 영구 삭제(GDPR)·204·404 비누설.

    slice 56: 자식 problem_attempt는 ON DELETE CASCADE로 함께 삭제(그 attempt를 참조하던
    dialogue.attempt_id는 SET NULL — 대화 자체는 보존). attempt_event(loose ref)는 고아 잔존.
    """
    await _delete_owned_resource(
        session,
        LearningSession,
        session_id,
        user.user_id,
        "학습 세션을 찾을 수 없습니다.",
    )


@router.patch(
    "/dialogues/{dialogue_id}/end",
    response_model=DialogueSchema,
    summary="내 Socratic 대화 종료(ended_at 채움)",
)
async def end_my_dialogue(
    dialogue_id: uuid.UUID,
    user: ConsentedUser,
    session: SessionDep,
) -> DialogueSchema:
    """slice 52 (slice 55 리팩터): 본인 Dialogue 종료(`ended_at`=now)·idempotent·404 비누설."""
    row = await _close_owned_resource(
        session,
        Dialogue,
        dialogue_id,
        user.user_id,
        "ended_at",
        "대화를 찾을 수 없습니다.",
    )
    return row.to_schema()


@router.delete(
    "/dialogues/{dialogue_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="내 Socratic 대화 영구 삭제(GDPR)",
)
async def delete_my_dialogue(
    dialogue_id: uuid.UUID,
    user: ConsentedUser,
    session: SessionDep,
) -> None:
    """slice 52 (slice 55 리팩터): 본인 Dialogue 영구 삭제·204·404 비누설. slice 56: 자식
    dialogue_turn은 ON DELETE CASCADE로 함께 삭제."""
    await _delete_owned_resource(
        session,
        Dialogue,
        dialogue_id,
        user.user_id,
        "대화를 찾을 수 없습니다.",
    )


@router.patch(
    "/assessments/{assessment_id}/complete",
    response_model=AssessmentSchema,
    summary="내 진단 완료(completed_at 채움)",
)
async def complete_my_assessment(
    assessment_id: uuid.UUID,
    user: ConsentedUser,
    session: SessionDep,
) -> AssessmentSchema:
    """slice 53 (slice 55 리팩터): 본인 Assessment 완료(`completed_at`=now). 컬럼은
    `completed_at`(ended_at 아님). idempotent·404 비누설."""
    row = await _close_owned_resource(
        session,
        Assessment,
        assessment_id,
        user.user_id,
        "completed_at",
        "진단을 찾을 수 없습니다.",
    )
    return row.to_schema()


@router.delete(
    "/assessments/{assessment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="내 진단 영구 삭제(GDPR)",
)
async def delete_my_assessment(
    assessment_id: uuid.UUID,
    user: ConsentedUser,
    session: SessionDep,
) -> None:
    """slice 53 (slice 55 리팩터): 본인 Assessment 영구 삭제·204·404 비누설. Assessment는
    자식 테이블이 없어 FK 위반 우려 없음(cascade 한계 무관)."""
    await _delete_owned_resource(
        session,
        Assessment,
        assessment_id,
        user.user_id,
        "진단을 찾을 수 없습니다.",
    )
