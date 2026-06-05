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
from whymath_backend.db.models.assessment import Assessment, ConceptMasteryHistory
from whymath_backend.db.models.audit import DeletionAudit
from whymath_backend.db.models.dialogue import Dialogue
from whymath_backend.db.session import get_session
from whymath_backend.l2.mastery_tracking import record_problem_attempt_mastery
from whymath_backend.schema.activity import LearningSession as LearningSessionSchema
from whymath_backend.schema.assessment import Assessment as AssessmentSchema
from whymath_backend.schema.assessment import (
    ConceptMasteryHistory as ConceptMasteryHistorySchema,
)
from whymath_backend.schema.audit import DeletionAudit as DeletionAuditSchema
from whymath_backend.schema.dialogue import Dialogue as DialogueSchema
from whymath_backend.schema.enums import AuditResourceType

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
    bool, Query(description="true면 `X-Total-Count` 헤더에 필터 적용 총 건수(limit/offset 무시).")
]
_TOTAL_HEADER = "X-Total-Count"
# slice L2-5: 학습곡선 조회의 개념 필터 — 특정 개념 1개의 측정 시계열(학습 곡선)만.
ConceptIdFilter = Annotated[
    uuid.UUID | None,
    Query(description="특정 개념의 학습 곡선만(선택). 생략 시 전 개념 측정 인터리브."),
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
        AuditResourceType.assessment,
        "진단을 찾을 수 없습니다.",
    )
