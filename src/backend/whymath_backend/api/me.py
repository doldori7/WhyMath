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

slice 57: GDPR 삭제 감사 — delete 3종이 `_delete_owned_resource`에서 삭제와 *동일 트랜잭션*으로
`DeletionAudit`(누가·무엇·언제, 콘텐츠 미저장) 1행 적재. 부모만 기록(자식 cascade는 DB 비가시).
user_id는 FK 아님(사용자 삭제돼도 잔존). alembic d4e5f6a7b8c9.

slice 58: `GET /v1/me/deletions` — slice 57이 적재한 본인 삭제 감사 이력 조회(GDPR 투명성).
다른 /me GET과 동일: ConsentedUser·user_id 스코핑·최신순(deleted_at desc)·페이지네이션.
스키마 변경 0(읽기 전용·마이그레이션 없음).
"""

from __future__ import annotations

import math
import uuid
from datetime import UTC, datetime
from typing import Annotated, Any, Literal, TypeVar

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from whymath_backend.api._auth import ConsentedUser
from whymath_backend.api._query_filters import time_window_conditions
from whymath_backend.db.models.activity import LearningSession, ProblemAttempt
from whymath_backend.db.models.assessment import (
    AbilitySnapshot,
    Assessment,
    ConceptMasteryHistory,
)
from whymath_backend.db.models.audit import DeletionAudit
from whymath_backend.db.models.concept import Concept, ProblemConcept
from whymath_backend.db.models.dialogue import Dialogue
from whymath_backend.db.models.problem import Problem
from whymath_backend.db.session import get_session
from whymath_backend.l2.ability_estimation import (
    _DIFFICULTY_MIDPOINT,
    ConceptAbilityItem,
    compute_concept_abilities,
    difficulty_to_logit,
    estimate_global_ability,
    resolve_item_difficulty_b,
)
from whymath_backend.l2.concept_diagnosis import Agreement, compute_concept_diagnoses
from whymath_backend.l2.irt import (
    IrtItem,
    ability_standard_error,
    estimate_ability,
    select_weighted_item,
)
from whymath_backend.l2.mastery_tracking import record_problem_attempt_mastery
from whymath_backend.l4.metacognitive_trigger import CoachingTrigger, recommend_coaching
from whymath_backend.schema.activity import LearningSession as LearningSessionSchema
from whymath_backend.schema.assessment import AbilitySnapshot as AbilitySnapshotSchema
from whymath_backend.schema.assessment import Assessment as AssessmentSchema
from whymath_backend.schema.assessment import (
    ConceptMasteryHistory as ConceptMasteryHistorySchema,
)
from whymath_backend.schema.audit import DeletionAudit as DeletionAuditSchema
from whymath_backend.schema.dialogue import Dialogue as DialogueSchema
from whymath_backend.schema.enums import ASSESSED_ROLES, AuditResourceType

router = APIRouter(prefix="/v1/me", tags=["me"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]
Limit = Annotated[int, Query(ge=1, le=200, description="페이지 크기")]
Offset = Annotated[int, Query(ge=0, description="건너뛸 행 수")]
# slice 65: deletions 조회의 선택적 도메인 필터 — None이면 전체(slice 58 동작 보존).
# slice 68: 다중 값 OR 필터 — `?resource_type=dialogue&resource_type=assessment`로 여러
# 도메인 동시 조회(IN). 단일 값도 그대로 수용(하위 호환). enum이라 부정 값은 FastAPI가 422.
ResourceTypeFilter = Annotated[
    list[AuditResourceType] | None,
    Query(
        description=(
            "삭제 도메인 필터(learning_session·dialogue·assessment). 반복 지정 시 OR(IN). "
            "생략 시 전체."
        )
    ),
]
# slice 66/67: /me 리스트 공용 시간창 필터(inclusive·TZ-aware ISO8601). deletions는
# deleted_at, sessions·assessments·dialogues는 started_at 기준. device 목록(slice 41)과
# 동형. naive datetime·since>until은 _query_filters.time_window_conditions가 422.
SinceParam = Annotated[
    datetime | None,
    Query(description="이 시각 *이후* 항목만(inclusive·TZ-aware ISO8601). until과 함께 시간창."),
]
UntilParam = Annotated[
    datetime | None,
    Query(description="이 시각 *이전* 항목만(inclusive·TZ-aware ISO8601). since와 함께 시간창."),
]
# slice 69: lifecycle 종료 시각 시간창 — sessions·dialogues는 ended_at, assessments는
# completed_at 기준(파라미터명으로 구분). started_at(SinceParam)과 *독립* 시간창이라 둘 다
# 지정 시 AND(예: 1월 시작 & 3월 종료). 미종료(NULL) 행은 SQL NULL 비교로 자동 제외.
CloseSince = Annotated[
    datetime | None,
    Query(description="이 시각 *이후* 종료/완료분만(inclusive·TZ-aware ISO8601)."),
]
CloseUntil = Annotated[
    datetime | None,
    Query(description="이 시각 *이전* 종료/완료분만(inclusive·TZ-aware ISO8601)."),
]
# slice 70: 정렬 방향 — desc(최신순·기본·slice 58 동작 보존)·asc(오래된순). device 목록
# (slice 46)과 동형. 1차 정렬 컬럼(started_at/deleted_at)에 적용·PK 2차키는 안정 정렬용 유지.
OrderDir = Literal["asc", "desc"]
OrderParam = Annotated[OrderDir, Query(description="정렬 방향 — desc(최신순·기본)·asc(오래된순).")]
# slice 71: 총 개수 opt-in — true면 *같은 필터*(limit/offset 제외) 적용 후 총 건수를
# `X-Total-Count` 응답 헤더로 노출(페이지네이션 "총 N건"·"Page X of Y"). 기본 false라 추가
# COUNT 쿼리 비용 회피. device 목록(slice 39)은 응답 envelope의 total 필드를 쓰지만 /me는
# bare array 응답이라 *비파괴적* 헤더 방식 채택(REST 관용·기존 클라이언트 무영향).
IncludeTotal = Annotated[
    bool,
    Query(description="true면 `X-Total-Count` 헤더에 필터 적용 총 건수(limit/offset 무시)."),
]
_TOTAL_HEADER = "X-Total-Count"
# slice L2-5: 학습곡선 조회의 개념 필터 — 특정 개념 1개의 측정 시계열(학습 곡선)만.
ConceptIdFilter = Annotated[
    uuid.UUID | None,
    Query(description="특정 개념의 학습 곡선만(선택). 생략 시 전 개념 측정 인터리브."),
]
# slice L2-5c: 현재 숙달 스냅샷 정렬 기준 — concept_id(기본) 또는 mastery(약점/강점 우선).
SnapshotOrderBy = Literal["concept_id", "mastery"]
SnapshotOrderByParam = Annotated[
    SnapshotOrderBy,
    Query(description="스냅샷 정렬 기준 — concept_id(기본) 또는 mastery(order=asc면 약점 우선)."),
]


async def _maybe_set_total(
    session: AsyncSession,
    response: Response,
    include_total: bool,
    count_stmt: Any,
) -> None:
    """slice 71: include_total이면 count_stmt(같은 필터·limit/offset 없음) 실행 후 헤더 설정."""
    if include_total:
        total = (await session.execute(count_stmt)).scalar() or 0
        response.headers[_TOTAL_HEADER] = str(total)


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
    *,
    commit: bool = True,
) -> tuple[_LifecycleRow, bool]:
    """본인 소유 리소스 lifecycle 종료 — `close_field`(ended_at/completed_at)를 now로.

    *idempotent*: 이미 채워졌으면 보존하고 commit 안 함(현 상태 반환). slice 50/52/53 동형.
    `(row, newly_closed)` 반환 — `newly_closed`는 *이번 호출에서 처음 종료*했는지(slice 34
    세션 종료 자동 트리거가 멱등 재호출 시 중복 동작을 피하도록).

    slice 35: `commit=False`면 종료 컬럼만 세팅하고 *커밋은 호출자*에 맡긴다 — 같은
    트랜잭션에 후속 쓰기(세션 종료 + θ 스냅샷)를 묶어 원자성 보장(부분 적용 방지).
    """
    row = await _get_owned_or_404(session, model, pk, owner_id, not_found_detail)
    newly_closed = getattr(row, close_field) is None
    if newly_closed:
        setattr(row, close_field, datetime.now(UTC))
        if commit:
            await session.commit()
    return row, newly_closed


async def _delete_owned_resource(
    session: AsyncSession,
    model: type[_LifecycleRow],
    pk: uuid.UUID,
    owner_id: uuid.UUID,
    resource_type: AuditResourceType,
    not_found_detail: str,
) -> None:
    """본인 소유 리소스 영구 삭제(GDPR) — 204. slice 51/52/53 동형. slice 56: 직속 자식은
    ON DELETE CASCADE로 자동 제거(session→attempt·dialogue→turn)·dialogue.attempt_id는
    SET NULL. attempt_event(loose ref·FK 아님)는 고아 잔존(설계 한계).

    slice 57: 삭제와 *동일 트랜잭션*으로 DeletionAudit 1행 적재(GDPR 삭제 증빙·부모만 기록·
    콘텐츠 미저장). user_id=소유자·resource_type/resource_id=대상. 같은 commit이라 삭제↔감사
    원자적(부분 실패 없음).
    """
    row = await _get_owned_or_404(session, model, pk, owner_id, not_found_detail)
    await session.delete(row)
    session.add(
        DeletionAudit(
            user_id=owner_id,
            resource_type=resource_type.value,
            resource_id=pk,
        )
    )
    await session.commit()


@router.get("/sessions", response_model=list[LearningSessionSchema], summary="내 학습 세션")
async def list_my_sessions(
    user: ConsentedUser,
    session: SessionDep,
    response: Response,
    limit: Limit = 50,
    offset: Offset = 0,
    since: SinceParam = None,
    until: UntilParam = None,
    ended_since: CloseSince = None,
    ended_until: CloseUntil = None,
    order: OrderParam = "desc",
    include_total: IncludeTotal = False,
) -> list[LearningSessionSchema]:
    """본인 학습 세션 — 기본 최신순. 타인 데이터는 조회 불가(user_id 스코핑).

    slice 67: `since`/`until`(선택)로 `started_at` 시간창 필터(inclusive·TZ-aware ISO8601).
    slice 69: `ended_since`/`ended_until`(선택)로 `ended_at` 시간창 — 미종료(NULL)는 제외.
    slice 70: `order`(asc/desc)로 `started_at` 정렬 방향(기본 desc·최신순).
    slice 71: `include_total=true`면 `X-Total-Count` 헤더에 필터 적용 총 건수.
    """
    conds = [
        LearningSession.user_id == user.user_id,
        *time_window_conditions(LearningSession.started_at, since, until),
        *time_window_conditions(
            LearningSession.ended_at,
            ended_since,
            ended_until,
            since_name="ended_since",
            until_name="ended_until",
        ),
    ]
    primary = (
        LearningSession.started_at.asc() if order == "asc" else LearningSession.started_at.desc()
    )
    stmt = (
        select(LearningSession)
        .where(*conds)
        .order_by(primary, LearningSession.session_id)
        .limit(limit)
        .offset(offset)
    )
    result = await session.execute(stmt)
    rows = [row.to_schema() for row in result.scalars().all()]
    await _maybe_set_total(
        session,
        response,
        include_total,
        select(func.count()).select_from(LearningSession).where(*conds),
    )
    return rows


@router.get("/assessments", response_model=list[AssessmentSchema], summary="내 진단 이력")
async def list_my_assessments(
    user: ConsentedUser,
    session: SessionDep,
    response: Response,
    limit: Limit = 50,
    offset: Offset = 0,
    since: SinceParam = None,
    until: UntilParam = None,
    completed_since: CloseSince = None,
    completed_until: CloseUntil = None,
    order: OrderParam = "desc",
    include_total: IncludeTotal = False,
) -> list[AssessmentSchema]:
    """본인 진단(Assessment) 이력 — 기본 최신순. user_id 스코핑.

    slice 67: `since`/`until`(선택)로 `started_at` 시간창 필터(inclusive·TZ-aware ISO8601).
    slice 69: `completed_since`/`completed_until`(선택)로 `completed_at` 시간창 — 미완료는 제외.
    slice 70: `order`(asc/desc)로 `started_at` 정렬 방향(기본 desc·최신순).
    slice 71: `include_total=true`면 `X-Total-Count` 헤더에 필터 적용 총 건수.
    """
    conds = [
        Assessment.user_id == user.user_id,
        *time_window_conditions(Assessment.started_at, since, until),
        *time_window_conditions(
            Assessment.completed_at,
            completed_since,
            completed_until,
            since_name="completed_since",
            until_name="completed_until",
        ),
    ]
    primary = Assessment.started_at.asc() if order == "asc" else Assessment.started_at.desc()
    stmt = (
        select(Assessment)
        .where(*conds)
        .order_by(primary, Assessment.assessment_id)
        .limit(limit)
        .offset(offset)
    )
    result = await session.execute(stmt)
    rows = [row.to_schema() for row in result.scalars().all()]
    await _maybe_set_total(
        session,
        response,
        include_total,
        select(func.count()).select_from(Assessment).where(*conds),
    )
    return rows


@router.get("/dialogues", response_model=list[DialogueSchema], summary="내 대화 이력")
async def list_my_dialogues(
    user: ConsentedUser,
    session: SessionDep,
    response: Response,
    limit: Limit = 50,
    offset: Offset = 0,
    since: SinceParam = None,
    until: UntilParam = None,
    ended_since: CloseSince = None,
    ended_until: CloseUntil = None,
    order: OrderParam = "desc",
    include_total: IncludeTotal = False,
) -> list[DialogueSchema]:
    """본인 Socratic 대화 이력 — 기본 최신순. user_id 스코핑(턴 상세는 범위 밖).

    slice 67: `since`/`until`(선택)로 `started_at` 시간창 필터(inclusive·TZ-aware ISO8601).
    slice 69: `ended_since`/`ended_until`(선택)로 `ended_at` 시간창 — 미종료(NULL)는 제외.
    slice 70: `order`(asc/desc)로 `started_at` 정렬 방향(기본 desc·최신순).
    slice 71: `include_total=true`면 `X-Total-Count` 헤더에 필터 적용 총 건수.
    """
    conds = [
        Dialogue.user_id == user.user_id,
        *time_window_conditions(
            Dialogue.ended_at,
            ended_since,
            ended_until,
            since_name="ended_since",
            until_name="ended_until",
        ),
        *time_window_conditions(Dialogue.started_at, since, until),
    ]
    primary = Dialogue.started_at.asc() if order == "asc" else Dialogue.started_at.desc()
    stmt = (
        select(Dialogue)
        .where(*conds)
        .order_by(primary, Dialogue.dialogue_id)
        .limit(limit)
        .offset(offset)
    )
    result = await session.execute(stmt)
    rows = [row.to_schema() for row in result.scalars().all()]
    await _maybe_set_total(
        session,
        response,
        include_total,
        select(func.count()).select_from(Dialogue).where(*conds),
    )
    return rows


@router.get(
    "/deletions",
    response_model=list[DeletionAuditSchema],
    summary="내 삭제 이력(GDPR 감사)",
)
async def list_my_deletions(
    user: ConsentedUser,
    session: SessionDep,
    response: Response,
    limit: Limit = 50,
    offset: Offset = 0,
    resource_type: ResourceTypeFilter = None,
    since: SinceParam = None,
    until: UntilParam = None,
    order: OrderParam = "desc",
    include_total: IncludeTotal = False,
) -> list[DeletionAuditSchema]:
    """slice 58: 본인 삭제 감사 이력 — 기본 최신순(deleted_at desc·audit_id 안정 정렬).

    slice 57이 적재한 `deletion_audit`를 user_id 스코핑으로 조회(GDPR 투명성 — 학생이 자기
    삭제 이력 확인·타인 것 차단). 메타만 반환(콘텐츠 없음). 본인 user_id의 행이라 타인 삭제는
    노출되지 않음(다른 /me GET과 동일 스코핑).

    slice 65: `resource_type`(선택)로 도메인 필터 — 한 유형(예: 대화)의 삭제 이력만 조회.
    slice 68: `resource_type` 반복 지정 시 OR(IN) — 여러 도메인 동시 조회(단일 값 하위 호환).
    slice 66: `since`/`until`(선택)로 `deleted_at` 시간창 필터(inclusive) — 특정 기간 삭제분만.
    slice 70: `order`(asc/desc)로 `deleted_at` 정렬 방향(기본 desc·최신순).
    slice 71: `include_total=true`면 `X-Total-Count` 헤더에 필터 적용 총 건수.
    모두 생략 시 전체(slice 58 동작 보존). naive datetime·since>until은 422(_query_filters).
    기존 `idx_deletion_audit_user(user_id, deleted_at DESC)`가 user_id prefix + 정렬 + 시간 범위를
    그대로 충족(resource_type만 추가 필터).
    """
    conds = [
        DeletionAudit.user_id == user.user_id,
        *time_window_conditions(DeletionAudit.deleted_at, since, until),
    ]
    if resource_type:
        conds.append(DeletionAudit.resource_type.in_([rt.value for rt in resource_type]))
    primary = DeletionAudit.deleted_at.asc() if order == "asc" else DeletionAudit.deleted_at.desc()
    stmt = (
        select(DeletionAudit)
        .where(*conds)
        .order_by(primary, DeletionAudit.audit_id)
        .limit(limit)
        .offset(offset)
    )
    result = await session.execute(stmt)
    rows = [row.to_schema() for row in result.scalars().all()]
    await _maybe_set_total(
        session,
        response,
        include_total,
        select(func.count()).select_from(DeletionAudit).where(*conds),
    )
    return rows


# ── slice L2-4: 풀이 채점 제출 → ProblemAttempt 적재 + BKT 숙달 자동 전파 ──────────
class AttemptSubmitRequest(BaseModel):
    """본인 풀이 채점 결과 제출 — `POST /v1/me/attempts` 요청 본문.

    v1: `is_correct`는 *클라이언트 보고*(서버측 답안 채점[OCR·answer-check]은 L3/L5 후속).
    `problem_id`는 존재하는 문제를 참조해야 한다(FK — 미존재 시 저장계층 무결성 오류).
    """

    model_config = ConfigDict(extra="forbid")

    problem_id: uuid.UUID = Field(description="채점 대상 문제 FK.")
    is_correct: bool = Field(description="정답 여부(v1 클라이언트 보고).")
    student_answer: str | None = Field(default=None, description="학생 제출 답안(선택).")
    duration_seconds: int | None = Field(default=None, ge=0, description="풀이 소요 시간(초).")
    session_id: uuid.UUID | None = Field(default=None, description="소속 학습 세션(선택).")
    confidence_self_reported: float | None = Field(
        default=None, ge=0.0, le=1.0, description="학생 자기보고 확신도 0~1(선택)."
    )


class ConceptMasteryUpdate(BaseModel):
    """채점으로 갱신된 한 개념의 숙달 측정 — 응답에 포함(학습 곡선 즉시 피드백)."""

    concept_id: uuid.UUID
    mastery: float
    sample_size: int


class AttemptSubmitResponse(BaseModel):
    """`POST /v1/me/attempts` 응답 — 적재된 attempt + 갱신된 개념 숙달 목록."""

    attempt_id: uuid.UUID
    is_correct: bool
    mastery_updates: list[ConceptMasteryUpdate]


@router.post(
    "/attempts",
    response_model=AttemptSubmitResponse,
    status_code=status.HTTP_201_CREATED,
    summary="풀이 채점 제출(ProblemAttempt 적재 + 숙달 자동 갱신)",
)
async def submit_attempt(
    body: AttemptSubmitRequest,
    user: ConsentedUser,
    session: SessionDep,
) -> AttemptSubmitResponse:
    """본인 풀이 채점 1건 제출 — `ProblemAttempt` 적재 후 문제의 평가 개념 BKT 숙달 자동 전파.

    user_id는 인증에서 주입(본문 무시·타인 사칭 차단). attempt를 먼저 commit하고(주된 기록)
    이어서 `record_problem_attempt_mastery`로 평가 개념(PRIMARY·TESTED) 숙달을 시계열에 누적
    (L2 슬라이스 3). 응답에 갱신된 개념별 숙달을 담아 클라이언트가 학습 곡선을 즉시 반영.
    """
    attempt = ProblemAttempt(
        attempt_id=uuid.uuid4(),  # 명시 발급(server_default 의존 X·응답에 즉시 사용)
        user_id=user.user_id,
        problem_id=body.problem_id,
        session_id=body.session_id,
        is_correct=body.is_correct,
        student_answer=body.student_answer,
        duration_seconds=body.duration_seconds,
        confidence_self_reported=body.confidence_self_reported,
        ended_at=datetime.now(UTC),
    )
    session.add(attempt)
    await session.commit()
    # 숙달 전파(평가 개념별 측정 적재·개념 매핑 없으면 빈 리스트)
    records = await record_problem_attempt_mastery(
        session, user.user_id, body.problem_id, body.is_correct
    )
    return AttemptSubmitResponse(
        attempt_id=attempt.attempt_id,
        is_correct=body.is_correct,
        mastery_updates=[
            ConceptMasteryUpdate(
                concept_id=r.concept_id,
                # record_problem_attempt_mastery는 항상 mastery를 채우나 ORM 타입이 float|None.
                mastery=float(r.mastery) if r.mastery is not None else 0.0,
                sample_size=r.sample_size if r.sample_size is not None else 0,
            )
            for r in records
        ],
    )


@router.get(
    "/mastery",
    response_model=list[ConceptMasteryHistorySchema],
    summary="내 개념 숙달 학습 곡선(ConceptMasteryHistory 시계열)",
)
async def list_my_mastery(
    user: ConsentedUser,
    session: SessionDep,
    response: Response,
    limit: Limit = 50,
    offset: Offset = 0,
    concept_id: ConceptIdFilter = None,
    since: SinceParam = None,
    until: UntilParam = None,
    order: OrderParam = "desc",
    include_total: IncludeTotal = False,
) -> list[ConceptMasteryHistorySchema]:
    """본인 개념 숙달 측정 시계열 — 학습 곡선(특성 #16). 풀이 채점(slice L2-4)이 누적한
    `concept_mastery_history`를 user_id 스코핑으로 조회(타인 차단).

    `concept_id`(선택)로 한 개념의 곡선만·`since`/`until`로 `measured_at` 시간창·`order`로
    방향(기본 desc 최신순)·`include_total`로 `X-Total-Count`. 2차 정렬키 concept_id로 동률
    (같은 measured_at·다개념) 안정 정렬.
    """
    conds = [ConceptMasteryHistory.user_id == user.user_id]
    if concept_id is not None:
        conds.append(ConceptMasteryHistory.concept_id == concept_id)
    conds += time_window_conditions(ConceptMasteryHistory.measured_at, since, until)
    primary = (
        ConceptMasteryHistory.measured_at.asc()
        if order == "asc"
        else ConceptMasteryHistory.measured_at.desc()
    )
    stmt = (
        select(ConceptMasteryHistory)
        .where(*conds)
        .order_by(primary, ConceptMasteryHistory.concept_id)
        .limit(limit)
        .offset(offset)
    )
    result = await session.execute(stmt)
    rows = [row.to_schema() for row in result.scalars().all()]
    await _maybe_set_total(
        session,
        response,
        include_total,
        select(func.count()).select_from(ConceptMasteryHistory).where(*conds),
    )
    return rows


class ConceptMasterySnapshotItem(BaseModel):
    """현재 숙달 스냅샷 1개 — 측정값 + 개념 메타(이름·코드). 약점 목록 UI 표시용.

    slice L2-5d: 기존 `ConceptMasteryHistorySchema`(concept_id만)에 concept 테이블의
    `name_ko`·`code`를 조인해 클라이언트가 추가 조회 없이 개념명을 표시한다. 개념이 삭제돼
    조인이 비면(loose ref·orphan) name/code는 null(LEFT JOIN·행 보존).
    """

    model_config = ConfigDict(extra="forbid")

    concept_id: uuid.UUID
    concept_code: str | None = Field(default=None, description="개념 코드(예: CAL-INT-...).")
    concept_name: str | None = Field(default=None, description="개념 한글명(name_ko).")
    mastery: float | None = None
    confidence: float | None = None
    sample_size: int | None = None
    measured_at: datetime


@router.get(
    "/mastery/current",
    response_model=list[ConceptMasterySnapshotItem],
    summary="현재 개념별 숙달 스냅샷(개념마다 최신 측정 1건·개념명 포함)",
)
async def list_my_current_mastery(
    user: ConsentedUser,
    session: SessionDep,
    order_by: SnapshotOrderByParam = "concept_id",
    order: OrderParam = "asc",
) -> list[ConceptMasterySnapshotItem]:
    """본인의 *개념별 최신* 숙달 1건씩 + 개념 메타(이름·코드) — 현재 상태 스냅샷("한눈에").
    `/mastery`는 전 측정 시계열(학습 곡선)이고, 본 엔드포인트는 개념마다 가장 최근 측정만.

    Postgres `DISTINCT ON (concept_id)` + `ORDER BY concept_id, measured_at DESC`로 개념별
    최신 행을 고른다(개념당 1행). 스냅샷이라 페이지네이션·필터 없음(연습한 개념 수로 한정).

    slice L2-5c: `order_by=mastery`로 약점/강점 우선 정렬("다음에 뭘 연습할지"). DISTINCT ON은
    ORDER BY가 concept_id로 시작해야 해(최신 행 선택 불변) 결과(개념당 1행·소규모)를 Python에서
    재정렬한다. mastery NULL은 *항상 끝*(방향 무관). 기본 concept_id asc(기존 동작 보존).
    slice L2-5d: `concept`(name_ko·code) LEFT JOIN — 약점 목록에 개념명 노출(orphan은 null).
    """
    stmt = (
        select(ConceptMasteryHistory, Concept.code, Concept.name_ko)
        .outerjoin(Concept, ConceptMasteryHistory.concept_id == Concept.concept_id)
        .where(ConceptMasteryHistory.user_id == user.user_id)
        .distinct(ConceptMasteryHistory.concept_id)
        .order_by(
            ConceptMasteryHistory.concept_id,
            ConceptMasteryHistory.measured_at.desc(),
        )
    )
    result = await session.execute(stmt)
    items = [
        ConceptMasterySnapshotItem(
            concept_id=cmh.concept_id,
            concept_code=code,
            concept_name=name_ko,
            mastery=float(cmh.mastery) if cmh.mastery is not None else None,
            confidence=float(cmh.confidence) if cmh.confidence is not None else None,
            sample_size=cmh.sample_size,
            measured_at=cmh.measured_at,
        )
        for cmh, code, name_ko in result.all()
    ]
    reverse = order == "desc"
    if order_by == "mastery":
        # NULL 항상 끝(방향 무관) + 나머지는 mastery 기준 정렬(asc=약점 우선)
        present = sorted(
            (i for i in items if i.mastery is not None),
            key=lambda i: i.mastery if i.mastery is not None else 0.0,
            reverse=reverse,
        )
        items = present + [i for i in items if i.mastery is None]
    else:  # concept_id — DISTINCT ON 자연 순(asc)·desc면 역순
        items.sort(key=lambda i: str(i.concept_id), reverse=reverse)
    return items


# ── slice L2-11: GET /v1/me/ability (IRT 능력 θ 추정 — 채점 풀이 이력 기반) ──────
_CI_Z_95 = 1.96  # 95% 신뢰구간 z값(표준정규 양측 0.025)


class AbilityResponse(BaseModel):
    """`GET /v1/me/ability` 응답 — IRT 능력 추정(θ + 측정 정밀도)."""

    theta: float = Field(description="IRT 능력 추정 θ(logit). 채점 응답 없으면 0.")
    response_count: int = Field(description="추정에 쓰인 채점(is_correct 있는) 풀이 수.")
    standard_error: float | None = Field(
        default=None,
        description="θ 추정 표준오차 SE=1/√I(θ)(slice 13). 응답 없으면(측정 불가) null.",
    )
    confidence_interval: list[float] | None = Field(
        default=None,
        description="95% 신뢰구간 [하한, 상한] = θ ± 1.96·SE. SE 없으면 null.",
    )


@router.get(
    "/ability",
    response_model=AbilityResponse,
    summary="내 IRT 능력 추정(θ — 채점 풀이 이력 기반)",
)
async def get_my_ability(
    user: ConsentedUser,
    session: SessionDep,
) -> AbilityResponse:
    """본인의 채점된 풀이 이력에서 IRT 능력 θ를 추정 — 문항 난이도(difficulty_overall)와 정/오답.

    `problem_attempt`(is_correct 있는 것)를 `problem`과 조인해 (난이도→logit b, 정답) 응답을
    만들고 `estimate_ability`(slice 7)로 θ 추정. 난이도 없는(difficulty_overall NULL) 문항은
    제외. 채점 응답이 없으면 θ=0(정보 없음). v1: difficulty_overall(전문가 1~5)을 b 프록시로
    사용(보정 b는 fit_jmle 후속). BKT(개념별 숙달)와 *상보적* 단일 능력 척도.

    측정 정밀도(slice 13): `ability_standard_error`로 표준오차 SE=1/√I(θ)·95% 신뢰구간
    θ±1.96·SE를 함께 노출. 응답 0건(정보 0=SE 무한)이면 둘 다 null(측정 불가). 경계 θ
    (전부 정답/오답)의 SE는 Fisher 정보 기반이라 *낙관적*(실 불확실성 과소·EAP는 후속).
    """
    theta, se, count = await estimate_global_ability(session, user.user_id)
    if se is None:  # 정보 0(응답 없음) → 측정 불가
        return AbilityResponse(theta=theta, response_count=count)
    return AbilityResponse(
        theta=theta,
        response_count=count,
        standard_error=se,
        confidence_interval=[theta - _CI_Z_95 * se, theta + _CI_Z_95 * se],
    )


# ── slice L2-32: θ 시계열 적재 (POST 캡처 + GET 조회 — ability_snapshot) ──────────
# θ 시계열(history·snapshots 공용) 상한 — 최근 N개(끝 N). 생략 시 전체.
AbilityHistoryLimit = Annotated[
    int | None,
    Query(ge=1, le=500, description="최근 N개 지점만(시간 오름차순 중 끝 N). 생략 시 전체."),
]
# slice 33: 캡처 시 전과목 θ뿐 아니라 개념별 θ도 함께 적재(개념 곡선).
IncludeConcepts = Annotated[
    bool,
    Query(description="true면 전과목 θ + *개념별* θ를 함께 적재(개념별 성장 곡선). 기본 false."),
]


@router.post(
    "/ability/snapshots",
    response_model=AbilitySnapshotSchema,
    status_code=status.HTTP_201_CREATED,
    summary="현재 IRT 능력 θ 스냅샷 적재(시계열 캡처)",
)
async def capture_ability_snapshot(
    user: ConsentedUser,
    session: SessionDep,
    include_concepts: IncludeConcepts = False,
) -> AbilitySnapshotSchema:
    """현재 전 과목 θ를 계산해 `ability_snapshot`에 1행 적재 — 성장 곡선 시점 캡처.

    파생(slice 28 `/ability/history`·매 요청 재계산)과 달리 *적재형*: 호출 시점의 θ를 보존한다
    (세션 종료·일/주 주기 등 호출자가 캡처 시점 결정). 전과목 행은 `concept_id`=null. θ 계산은
    `/ability`(slice 11)와 동일 헬퍼. `include_concepts=true`면 개념별 θ(slice 18 계산)도 *같은
    시각*으로 함께 적재(개념별 곡선·`concept_id` 값 보유). 응답은 전과목 스냅샷. user_id 스코핑.
    """
    now = datetime.now(UTC)
    theta, se, count = await estimate_global_ability(session, user.user_id)
    snap = AbilitySnapshotSchema(
        user_id=user.user_id,
        theta=theta,
        standard_error=se,
        response_count=count,
        measured_at=now,
    )
    session.add(AbilitySnapshot.from_schema(snap))
    if include_concepts:
        await _add_concept_ability_snapshots(session, user.user_id, now)
    await session.commit()
    return snap


@router.get(
    "/ability/snapshots",
    response_model=list[AbilitySnapshotSchema],
    summary="내 IRT 능력 θ 스냅샷 시계열(적재된 성장 곡선)",
)
async def list_ability_snapshots(
    user: ConsentedUser,
    session: SessionDep,
    concept_id: ConceptIdFilter = None,
    limit: AbilityHistoryLimit = None,
) -> list[AbilitySnapshotSchema]:
    """적재된 θ 스냅샷을 *시간 오름차순*(성장 곡선)으로 조회. `?limit`이면 최근 N개(끝 N).

    파생 `/ability/history`(이력 재생)와 달리 *적재된* 시점들을 그대로 반환(캡처 당시 θ 보존).
    `?concept_id` 생략 시 *전과목 곡선*(concept_id IS NULL)만·지정 시 그 개념 곡선만(slice 33
    개념별 적재와 결선). 곡선이 섞이지 않게 기본 전과목. user_id 스코핑·읽기.
    """
    conds = [AbilitySnapshot.user_id == user.user_id]
    if concept_id is not None:
        conds.append(AbilitySnapshot.concept_id == concept_id)
    else:
        conds.append(AbilitySnapshot.concept_id.is_(None))  # 기본=전과목 곡선
    stmt = select(AbilitySnapshot).where(*conds).order_by(AbilitySnapshot.measured_at.asc())
    snaps = [row.to_schema() for row in (await session.execute(stmt)).scalars().all()]
    if limit is not None:
        snaps = snaps[-limit:]
    return snaps


# ── slice L2-18: GET /v1/me/ability/by-concept (개념별 IRT 능력 θ 분리) ───────────
@router.get(
    "/ability/by-concept",
    response_model=list[ConceptAbilityItem],
    summary="내 개념별 IRT 능력(θ — 개념마다 분리 추정)",
)
async def get_my_ability_by_concept(
    user: ConsentedUser,
    session: SessionDep,
) -> list[ConceptAbilityItem]:
    """채점 풀이 이력을 *문항의 평가 개념별*로 묶어 개념마다 IRT 능력 θ를 분리 추정.

    단일 전과목 θ(`/me/ability`)를 개념/도메인 축으로 쪼갠다(다차원 진단). `problem_attempt`(채점됨)
    를 `problem`·`problem_concept`(role∈PRIMARY/TESTED)와 조인해 개념별 (난이도→b, 정답) 응답을
    만들고 `estimate_ability`(slice 7)로 θ·`ability_standard_error`(slice 13)로 SE 추정. 개념명은
    `concept` LEFT JOIN(orphan은 null·slice L2-5d 패턴). 난이도 NULL 문항 제외. *능력 낮은(약점)
    개념 먼저* 정렬(asc·동률은 concept_id)로 "무엇을 보완할지" 우선순위 노출. BKT 개념별 숙달과
    *상보적*(BKT=정오답 확률·IRT=난이도 보정 능력). user_id 스코핑·읽기(마이그레이션 불필요).
    """
    items = await compute_concept_abilities(session, user.user_id)
    # 약점(저능력) 개념 먼저 — asc 정렬·동률은 concept_id로 안정화(결정론).
    items.sort(key=lambda i: (i.theta, str(i.concept_id)))
    return items


async def _add_concept_ability_snapshots(
    session: AsyncSession, user_id: uuid.UUID, measured_at: datetime
) -> None:
    """개념별 θ 스냅샷을 세션에 *추가만*(commit은 호출자) — 수동 캡처·세션 종료 공유(slice 75).

    `compute_concept_abilities`(slice 18 산식)의 각 개념 θ를 *주어진 시각*으로 적재(전과목
    스냅샷과 같은 measured_at). `capture_ability_snapshot(include_concepts)`와 세션 종료 자동
    적재(`_add_ability_snapshot_if_attempts`)가 공유해 개념 θ 곡선을 자연 샘플링한다(중복 제거).
    """
    for item in await compute_concept_abilities(session, user_id):
        session.add(
            AbilitySnapshot.from_schema(
                AbilitySnapshotSchema(
                    user_id=user_id,
                    concept_id=item.concept_id,
                    theta=item.theta,
                    standard_error=item.standard_error,
                    response_count=item.response_count,
                    measured_at=measured_at,
                )
            )
        )


# ── slice L2-28: GET /v1/me/ability/history (θ 성장 곡선 — 채점 이력 시간 재생) ─────


class AbilityHistoryPoint(BaseModel):
    """`GET /v1/me/ability/history`의 한 시점 — k번째 채점 직후 누적 θ."""

    as_of: datetime = Field(description="이 지점에 반영된 마지막 채점 시각(created_at).")
    theta: float = Field(description="이 시점까지 누적 응답으로 추정한 θ(logit).")
    standard_error: float | None = Field(
        default=None, description="이 시점 θ의 표준오차. 측정 불가면 null."
    )
    response_count: int = Field(description="이 시점까지 누적된 채점 풀이 수(=k).")


@router.get(
    "/ability/history",
    response_model=list[AbilityHistoryPoint],
    summary="내 IRT 능력 성장 곡선(θ — 채점 이력 시간 재생)",
)
async def get_my_ability_history(
    user: ConsentedUser,
    session: SessionDep,
    limit: AbilityHistoryLimit = None,
) -> list[AbilityHistoryPoint]:
    """채점 풀이 이력을 *시간순 재생*해 매 풀이 직후 누적 θ(성장 곡선)를 산출 — 적재 없이 파생.

    `problem_attempt`(채점됨·난이도 보유)를 `created_at` 오름차순으로 모아, k번째까지의 응답으로
    `estimate_ability`(slice 7)·`ability_standard_error`(slice 13)를 매 단계 계산해 시점 1개씩 방출.
    θ 시계열을 *저장하지 않고* 기존 이력에서 재구성(마이그레이션 0). `?limit`이면 *끝* N개(최근)만.
    전 과목 단일 θ(개념별·저장형 시계열은 후속). user_id 스코핑·읽기.

    v1 한계: 매 단계 θ 전체 재추정(O(n²))·시점=풀이당 1개(다운샘플·증분 추정은 후속).
    """
    stmt = (
        select(
            ProblemAttempt.created_at,
            ProblemAttempt.is_correct,
            Problem.difficulty_overall,
            Problem.irt_difficulty_b,
        )
        .join(Problem, ProblemAttempt.problem_id == Problem.problem_id)
        .where(
            ProblemAttempt.user_id == user.user_id,
            ProblemAttempt.is_correct.isnot(None),
            ProblemAttempt.created_at.isnot(None),
            Problem.irt_difficulty_b.isnot(None) | Problem.difficulty_overall.isnot(None),
        )
        .order_by(ProblemAttempt.created_at.asc())
    )
    responses: list[tuple[IrtItem, bool]] = []
    points: list[AbilityHistoryPoint] = []
    for created_at, is_correct, difficulty, irt_b in (await session.execute(stmt)).all():
        b = resolve_item_difficulty_b(irt_b, difficulty)
        if b is None:
            continue
        responses.append((IrtItem(difficulty=b), bool(is_correct)))
        theta = estimate_ability(responses)
        se = ability_standard_error(theta, [it for it, _ in responses])
        points.append(
            AbilityHistoryPoint(
                as_of=created_at,
                theta=theta,
                standard_error=None if math.isinf(se) else se,
                response_count=len(responses),
            )
        )
    if limit is not None:
        points = points[-limit:]
    return points


# ── slice L2-19: GET /v1/me/diagnosis/concepts (BKT 숙달 ↔ IRT θ 교차검증) ────────
# 진단 계산(BKT+IRT 융합·agreement·약점 정렬)은 L2 `concept_diagnosis`(slice 82 이관). 여기선
# 응답 스키마(+ L4 코칭 후처리)·엔드포인트만 둔다 — coaching은 L5 부착(L2→L4 역의존 회피).


class ConceptDiagnosisItem(BaseModel):
    """개념별 BKT↔IRT 교차검증 — `GET /v1/me/diagnosis/concepts`의 한 개념 항목."""

    concept_id: uuid.UUID = Field(description="개념 id.")
    concept_code: str | None = Field(default=None, description="개념 코드(orphan이면 null).")
    concept_name: str | None = Field(default=None, description="개념명(orphan이면 null).")
    bkt_mastery: float | None = Field(
        default=None, description="BKT 최신 숙달 P(L). 측정 없으면 null."
    )
    irt_theta: float | None = Field(
        default=None, description="개념별 IRT 능력 θ. 채점 풀이 없으면 null."
    )
    irt_mastery_proxy: float | None = Field(
        default=None, description="logistic(θ)∈[0,1] — BKT 숙달과 비교용. θ 없으면 null."
    )
    response_count: int = Field(description="개념별 IRT 추정에 쓰인 채점 풀이 수.")
    agreement: Agreement = Field(
        description="BKT↔IRT 일치 신호(agree·irt_higher·bkt_higher·insufficient)."
    )
    coaching: CoachingTrigger = Field(
        description="L4 메타인지 코칭 처방(focus·rationale·prompt·slice 20)."
    )


# slice 26: 진단 필터·상한 — "주의 필요 개념 대시보드" 질의(전 개념 반환은 페이로드 과대).
# agreement 다중 OR(예: irt_higher·bkt_higher만=불일치 개념)·limit는 *약점 먼저* 정렬 후 상위 N.
AgreementFilter = Annotated[
    list[Agreement] | None,
    Query(
        description=(
            "일치 신호 필터(agree·irt_higher·bkt_higher·insufficient). 반복 지정 시 OR. "
            "생략 시 전체(예: irt_higher·bkt_higher만 = 불일치 개념)."
        )
    ),
]
DiagnosisLimit = Annotated[
    int | None,
    Query(ge=1, le=200, description="약점(저신호) 먼저 정렬 후 상위 N개만. 생략 시 전체."),
]


async def _compute_concept_diagnosis(
    session: AsyncSession, user_id: uuid.UUID
) -> list[ConceptDiagnosisItem]:
    """개념별 BKT↔IRT 교차검증(L2 `compute_concept_diagnoses`)에 L4 코칭을 부착·반환.

    순수 진단(BKT+IRT 융합·agreement·약점 정렬)은 L2(slice 82 이관). 여기선 각 진단 신호에 L4
    메타인지 코칭 처방(`recommend_coaching`)을 부착해 응답 항목(ConceptDiagnosisItem)으로 만든다 —
    L2→L4 역의존 회피(코칭은 L5 후처리). `/diagnosis/concepts`(필터/상한)·`/diagnosis/summary`
    (집계)가 공유. 정렬·합집합은 L2가 수행.
    """
    diagnoses = await compute_concept_diagnoses(session, user_id)
    return [
        ConceptDiagnosisItem(
            **d.model_dump(),
            coaching=recommend_coaching(d.bkt_mastery, d.irt_theta),
        )
        for d in diagnoses
    ]


@router.get(
    "/diagnosis/concepts",
    response_model=list[ConceptDiagnosisItem],
    summary="내 개념별 BKT↔IRT 교차검증(통합 약점 진단)",
)
async def get_my_concept_diagnosis(
    user: ConsentedUser,
    session: SessionDep,
    agreement: AgreementFilter = None,
    limit: DiagnosisLimit = None,
) -> list[ConceptDiagnosisItem]:
    """개념별 BKT 숙달(slice L2-5c)과 IRT 능력 θ(slice 18)를 *한 응답에 합쳐* 교차검증.

    두 학습자 모델(L2)이 같은 개념 축에서 *합의/불일치*를 드러낸다 — `agreement`로 "θ는 높은데
    BKT 숙달은 낮음(irt_higher·추측/BKT 지연)"·"BKT 숙달은 높은데 θ 낮음(bkt_higher·망각/고난도)"을
    표면화(진단 신뢰도·메타인지 코칭 입력). ① BKT 최신 숙달 스냅샷(DISTINCT ON)·② 개념별 채점
    풀이로 IRT θ(`estimate_ability`)·logistic 프록시. 둘 중 하나라도 있는 개념을 합집합으로 모아
    *약점(저신호) 먼저* 정렬. 각 개념에 L4 메타인지 코칭 처방(`recommend_coaching`·slice 20)을
    붙여 *무엇을 할지*(focus·발화)까지 노출 — L2 진단→L4 결정→L5 노출 풀 스택. user_id
    스코핑·읽기(마이그레이션 불필요). `?agreement`(다중 OR·예: 불일치만)·`?limit`(약점 상위 N)으로
    "주의 필요 개념" 질의 가능(slice 26).
    """
    items = await _compute_concept_diagnosis(session, user.user_id)
    # slice 26: agreement OR 필터 → limit(약점 먼저 정렬 후 상위 N). 둘 다 선택적(기본 전체).
    if agreement:
        wanted = set(agreement)
        items = [i for i in items if i.agreement in wanted]
    if limit is not None:
        items = items[:limit]
    return items


# ── slice L2-27: GET /v1/me/diagnosis/summary (진단 집계 — 대시보드 헤더) ──────────
class ConceptDiagnosisSummary(BaseModel):
    """`GET /v1/me/diagnosis/summary` 응답 — 개념 진단 집계."""

    total_concepts: int = Field(description="진단 신호(BKT 또는 IRT)가 있는 개념 수.")
    agree: int = Field(description="BKT↔IRT 합의 개념 수.")
    irt_higher: int = Field(description="θ는 높은데 BKT 낮음(추측/지연) 개념 수.")
    bkt_higher: int = Field(description="BKT는 높은데 θ 낮음(망각/고난도) 개념 수.")
    insufficient: int = Field(description="한쪽 신호만(교차검증 불가) 개념 수.")
    attention_count: int = Field(description="주의 필요(불일치=irt_higher+bkt_higher) 개념 수.")
    weakest_concept_id: uuid.UUID | None = Field(
        default=None, description="가장 약한(저신호) 개념 id. 진단 개념 없으면 null."
    )
    weakest_concept_name: str | None = Field(
        default=None, description="가장 약한 개념명(orphan·미진단이면 null)."
    )


@router.get(
    "/diagnosis/summary",
    response_model=ConceptDiagnosisSummary,
    summary="내 개념 진단 집계(대시보드 헤더 — 주의 필요 수·최약점)",
)
async def get_my_diagnosis_summary(
    user: ConsentedUser,
    session: SessionDep,
) -> ConceptDiagnosisSummary:
    """개념별 진단(`/diagnosis/concepts`)을 *집계* — 대시보드 헤더용 한 줄 요약.

    일치 신호별 개념 수·*주의 필요*(불일치=irt_higher+bkt_higher) 수·*가장 약한* 개념(약점
    정렬 1위)을 반환. 진단 개념이 없으면 모두 0·weakest는 null. 공유 계산(`_compute_concept_
    diagnosis`)을 재사용(개념 리스트와 동일 데이터의 집계 뷰). user_id 스코핑·읽기.
    """
    items = await _compute_concept_diagnosis(session, user.user_id)
    counts = {"agree": 0, "irt_higher": 0, "bkt_higher": 0, "insufficient": 0}
    for i in items:
        counts[i.agreement] += 1
    weakest = items[0] if items else None  # 이미 약점 먼저 정렬됨
    return ConceptDiagnosisSummary(
        total_concepts=len(items),
        agree=counts["agree"],
        irt_higher=counts["irt_higher"],
        bkt_higher=counts["bkt_higher"],
        insufficient=counts["insufficient"],
        attention_count=counts["irt_higher"] + counts["bkt_higher"],
        weakest_concept_id=weakest.concept_id if weakest else None,
        weakest_concept_name=weakest.concept_name if weakest else None,
    )


# ── slice L2-12: GET /v1/me/next-problem (적응형 출제 — IRT 정보량 최대 미응답 문항) ──
_CANDIDATE_POOL_SIZE = 50  # θ 근방 후보 풀 크기(SQL로 거리순 선별 후 파이썬 정보량 비교)
# slice 15: CAT 중단 규칙 목표 표준오차 — 응답한 문항 기준 SE가 이 값 이하로 내려가면
# "충분히 정밀하게 측정됨"으로 보고 적응 검사 중단을 권고(measurement_sufficient=True).
# 0.3은 통상적 CAT 종료 임계(θ ± ~0.6 95% 구간). 추후 모드/설정별 보정은 후속.
_TARGET_SE = 0.3
# slice 16/17: 약점 개념 가중 출제 — BKT 개념별 숙달이 낮을수록(약점) 후보 문항 정보량에
# 곱하는 가중치를 키운다. weight = 1 + BOOST·(1 - 최저숙달). BOOST=1.0이면 완전 미숙달(숙달 0)
# 문항은 가중 2배·완전 숙달(1.0)은 1배. 정책 상수(모드별 차등은 후속).
_WEAK_CONCEPT_BOOST = 1.0
# 약점 가중 개념 역할은 `schema.enums.ASSESSED_ROLES`(PRIMARY/TESTED·BKT·IRT와 동일 집합·단일
# 출처 — slice 84). 문제가 *평가하는* 개념만(SUPPORTING 제외).
# slice 17: ?prioritize_weak_concepts — 기본 false(slice 12~15 동작 보존). true면 BKT 약점
# 개념 우선(개념 숙달 스냅샷·후보 문항 개념 매핑을 추가 조회해 가중).
PrioritizeWeakConcepts = Annotated[
    bool,
    Query(description="true면 BKT 약점 개념(저숙달) 우선 출제(정보량×약점 가중). 기본 false."),
]


def _weak_concept_weights(
    candidate_problem_ids: list[uuid.UUID],
    problem_concepts: dict[uuid.UUID, set[uuid.UUID]],
    mastery: dict[uuid.UUID, float],
) -> list[float]:
    """후보 문항별 약점 가중치 — 문항의 평가 개념 중 *최저 숙달*로 weakness 산출(BKT+IRT 융합).

    각 후보의 평가 개념(`problem_concepts[pid]`) 중 숙달 기록(`mastery`)이 있는 것의 최저 숙달을
    취해 `weight = 1 + _WEAK_CONCEPT_BOOST·(1 - 최저숙달)`. 약할수록 가중↑. 개념 매핑이 없거나
    숙달 기록이 없으면 *중립*(1.0 — 정보 없는 개념을 벌하거나 우대하지 않음). 순수·결정론.
    """
    weights = []
    for pid in candidate_problem_ids:
        relevant = [mastery[c] for c in problem_concepts.get(pid, set()) if c in mastery]
        if relevant:
            weights.append(1.0 + _WEAK_CONCEPT_BOOST * (1.0 - min(relevant)))
        else:
            weights.append(1.0)
    return weights


class NextProblemResponse(BaseModel):
    """`GET /v1/me/next-problem` 응답 — IRT CAT(적응형 출제) 추천 + 측정 정밀도."""

    problem_id: uuid.UUID | None = Field(
        default=None,
        description="추천 문항 id. 후보(미응답·난이도 라벨 보유)가 없으면 null.",
    )
    theta: float = Field(description="추천에 쓰인 현재 능력 추정 θ(logit). 응답 없으면 0.")
    difficulty: float | None = Field(
        default=None,
        description="추천 문항의 difficulty_overall(전문가 1~5). 없으면 null.",
    )
    standard_error: float | None = Field(
        default=None,
        description="현재 θ 추정의 표준오차(응답한 문항 기준·slice 13). 응답 없으면 null.",
    )
    measurement_sufficient: bool = Field(
        default=False,
        description=f"SE가 목표({_TARGET_SE}) 이하면 True — 적응 검사 중단 권고(CAT 중단 규칙).",
    )


@router.get(
    "/next-problem",
    response_model=NextProblemResponse,
    summary="적응형 다음 문항 추천(IRT 정보량 최대 — 미응답 문항)",
)
async def recommend_next_problem(
    user: ConsentedUser,
    session: SessionDep,
    prioritize_weak_concepts: PrioritizeWeakConcepts = False,
) -> NextProblemResponse:
    """본인 능력 θ에 *정보량 최대*인 *미응답* 문항을 추천 — IRT CAT(적응형 출제) 루프.

    ① 채점 풀이 이력으로 θ 추정(slice 11과 동일 로직)·이미 푼 문항 id 수집. ② 난이도 라벨
    (difficulty_overall) 있는 *미응답* 문항을 θ 근방(|b-θ| 최소)으로 SQL 선별(`_CANDIDATE_POOL_SIZE`
    개)·`select_weighted_item`(slice 16)으로 (가중)정보량 최대 1개 선택. 없으면 problem_id=null.
    난이도→b는 보정 b(`irt_difficulty_b`·slice 79 JMLE) 우선·없으면 `difficulty_to_logit`
    휴리스틱 폴백(`resolve_item_difficulty_b`·SQL은 COALESCE).

    CAT 중단 규칙(slice 15): *응답한 문항* 기준 표준오차 SE(slice 13)와 `measurement_sufficient`
    (SE≤`_TARGET_SE`)을 함께 반환 — 호출자는 충분하면 검사를 멈추고 아니면 추천 문항을 출제한다
    (적응 검사 루프 구동). 추천(problem_id)은 중단 권고와 무관히 후보가 있으면 항상 제공.

    BKT+IRT 융합(slice 17·`prioritize_weak_concepts=true`): 후보 풀(θ 근방) 안에서 학생의 BKT
    개념별 숙달 스냅샷(개념당 최신)을 후보 문항의 평가 개념과 대응해, *약점 개념*(저숙달) 문항의
    정보량에 가중(`_weak_concept_weights`)을 줘 선택. 즉 "능력에 맞는 난이도" + "약한 개념 우선"을
    동시 만족(CLAUDE.md 약점 진단). 후보 풀 자체는 여전히 θ 근방이라, 약점이라도 난이도가 θ에서
    멀면 풀 밖일 수 있다(풀 확장은 후속). 기본 false면 균등 가중(slice 12~15 동작 보존).
    """
    attempt_stmt = (
        select(
            ProblemAttempt.problem_id,
            ProblemAttempt.is_correct,
            Problem.difficulty_overall,
            Problem.irt_difficulty_b,
        )
        .join(Problem, ProblemAttempt.problem_id == Problem.problem_id)
        .where(
            ProblemAttempt.user_id == user.user_id,
            ProblemAttempt.is_correct.isnot(None),
        )
    )
    attempt_rows = (await session.execute(attempt_stmt)).all()
    responses: list[tuple[IrtItem, bool]] = []
    for _pid, is_correct, difficulty, irt_b in attempt_rows:
        b = resolve_item_difficulty_b(irt_b, difficulty)
        if b is not None:
            responses.append((IrtItem(difficulty=b), bool(is_correct)))
    theta = estimate_ability(responses)
    attempted_ids = {pid for pid, _ic, _d, _b in attempt_rows}

    # slice 15: 응답한 문항(administered) 기준 측정 정밀도 — CAT 중단 규칙 신호.
    administered_items = [item for item, _ in responses]
    se = ability_standard_error(theta, administered_items)
    standard_error = None if math.isinf(se) else se
    measurement_sufficient = standard_error is not None and standard_error <= _TARGET_SE

    # 후보를 θ 근방(|b-θ| 최소)으로 SQL 정렬 — 보정 b(irt_difficulty_b) 우선·없으면 전문가
    # 난이도→logit(difficulty_overall - 중앙값) 폴백(COALESCE). 응답 difficulty 노출을 위해
    # difficulty_overall 보유 문항만 후보(보정-only 문항 후보화는 후속).
    candidate_stmt = select(
        Problem.problem_id, Problem.difficulty_overall, Problem.irt_difficulty_b
    ).where(Problem.difficulty_overall.isnot(None))
    if attempted_ids:
        candidate_stmt = candidate_stmt.where(Problem.problem_id.notin_(attempted_ids))
    candidate_stmt = candidate_stmt.order_by(
        func.abs(
            func.coalesce(
                Problem.irt_difficulty_b,
                Problem.difficulty_overall - _DIFFICULTY_MIDPOINT,
            )
            - theta
        )
    ).limit(_CANDIDATE_POOL_SIZE)
    candidate_rows = (await session.execute(candidate_stmt)).all()

    # 보정 b 우선·없으면 휴리스틱(difficulty_overall NOT NULL 보장 → 항상 값·candidate_rows와 1:1).
    items = [
        IrtItem(difficulty=irt_b if irt_b is not None else difficulty_to_logit(float(d)))
        for _pid, d, irt_b in candidate_rows
    ]

    # slice 17: 약점 개념 가중(BKT+IRT 융합) — 후보가 있을 때만 추가 2쿼리로 가중치 산출.
    weights: list[float] | None = None
    if prioritize_weak_concepts and candidate_rows:
        candidate_ids = [pid for pid, _d, _b in candidate_rows]
        mastery_stmt = (
            select(ConceptMasteryHistory.concept_id, ConceptMasteryHistory.mastery)
            .where(ConceptMasteryHistory.user_id == user.user_id)
            .distinct(ConceptMasteryHistory.concept_id)
            .order_by(
                ConceptMasteryHistory.concept_id,
                ConceptMasteryHistory.measured_at.desc(),
            )
        )
        mastery = {
            cid: float(m) for cid, m in (await session.execute(mastery_stmt)).all() if m is not None
        }
        pc_stmt = select(ProblemConcept.problem_id, ProblemConcept.concept_id).where(
            ProblemConcept.problem_id.in_(candidate_ids),
            ProblemConcept.role.in_(ASSESSED_ROLES),
        )
        problem_concepts: dict[uuid.UUID, set[uuid.UUID]] = {}
        for pid, cid in (await session.execute(pc_stmt)).all():
            problem_concepts.setdefault(pid, set()).add(cid)
        weights = _weak_concept_weights(candidate_ids, problem_concepts, mastery)

    best = select_weighted_item(theta, items, weights=weights)
    if best is None:
        return NextProblemResponse(
            problem_id=None,
            theta=theta,
            difficulty=None,
            standard_error=standard_error,
            measurement_sufficient=measurement_sufficient,
        )
    chosen_id, chosen_difficulty, _chosen_b = candidate_rows[best]
    return NextProblemResponse(
        problem_id=chosen_id,
        theta=theta,
        difficulty=float(chosen_difficulty),
        standard_error=standard_error,
        measurement_sufficient=measurement_sufficient,
    )


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
    """slice 50 (slice 55 리팩터): 본인 학습 세션 종료(`ended_at`=now)·idempotent·404 비누설.

    slice 34: *처음 종료*될 때 현재 전과목 θ를 `ability_snapshot`에 자동 적재(세션 종료 트리거 —
    수동 POST 불요·성장 곡선 자연 샘플링). 멱등 재호출(이미 종료)이나 채점 이력 0이면 미적재.
    slice 35: 종료 컬럼 세팅·스냅샷 적재를 *한 트랜잭션*(단일 commit)으로 묶어 원자성 보장.
    """
    row, newly_closed = await _close_owned_resource(
        session,
        LearningSession,
        session_id,
        user.user_id,
        "ended_at",
        "학습 세션을 찾을 수 없습니다.",
        commit=False,  # 종료 + 스냅샷을 아래에서 단일 commit으로 원자 적용.
    )
    if newly_closed:
        await _add_ability_snapshot_if_attempts(session, user.user_id)
        await session.commit()  # 종료(ended_at) + (있으면)스냅샷 한 번에.
    return row.to_schema()


async def _add_ability_snapshot_if_attempts(session: AsyncSession, user_id: uuid.UUID) -> None:
    """채점 이력이 있으면 전과목+개념별 θ 스냅샷을 세션에 *추가만*(commit은 호출자)·빈 θ 미적재.

    slice 32 수동 캡처와 동일 산식·전과목 단일 θ(concept_id null). 세션 종료 트리거(slice 34/35).
    slice 75: 전과목 θ에 더해 *개념별* θ도 같은 시각으로 함께 적재(개념 θ 자연 샘플링 → coach
    BKT↔θ 교차검증이 폴백 없이 같은 개념끼리 정밀 비교). 채점 0이면 개념도 0(전과목의 부분집합).
    """
    now = datetime.now(UTC)
    theta, se, count = await estimate_global_ability(session, user_id)
    if count == 0:
        return  # 채점 이력 0 → 전과목·개념 θ 모두 미적재(개념은 전과목의 부분집합)
    session.add(
        AbilitySnapshot.from_schema(
            AbilitySnapshotSchema(
                user_id=user_id,
                theta=theta,
                standard_error=se,
                response_count=count,
                measured_at=now,
            )
        )
    )
    await _add_concept_ability_snapshots(session, user_id, now)


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
        AuditResourceType.learning_session,
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
    row, _ = await _close_owned_resource(
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
        AuditResourceType.dialogue,
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
    row, _ = await _close_owned_resource(
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
        AuditResourceType.assessment,
        "진단을 찾을 수 없습니다.",
    )
