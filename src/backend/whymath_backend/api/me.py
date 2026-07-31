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

import logging
import math
import uuid
from datetime import UTC, datetime
from typing import Annotated, Any, Literal, TypeVar

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from whymath_backend.api._auth import ConsentedUser, CurrentUser
from whymath_backend.api._query_filters import (
    _validate_time_window,
    _validate_tz_aware,
    time_window_conditions,
)
from whymath_backend.api._rate_limit import _client_ip
from whymath_backend.config import Settings, get_settings
from whymath_backend.db.models.activity import LearningSession, ProblemAttempt
from whymath_backend.db.models.assessment import (
    AbilitySnapshot,
    Assessment,
    ConceptMasteryHistory,
    SkillMasteryHistory,
)
from whymath_backend.db.models.audit import DeletionAudit, PrivacyAudit
from whymath_backend.db.models.concept import Concept, ProblemConcept
from whymath_backend.db.models.dialogue import Dialogue
from whymath_backend.db.models.problem import Problem
from whymath_backend.db.session import get_session
from whymath_backend.harness.wh1_evaluation import (
    SurrogateMetrics,
    compute_wh1_surrogate_metrics,
)
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
from whymath_backend.l2.learning_path import (
    LearningPath,
    build_learning_path,
)
from whymath_backend.l2.mastery_tracking import record_problem_attempt_mastery
from whymath_backend.l2.prerequisite_recommendation import (
    MAX_PREREQUISITE_DEPTH,
    PrerequisiteGap,
    recommend_prerequisite_gaps,
)
from whymath_backend.l2.skill_mastery_tracking import (
    record_problem_attempt_skill_mastery,
)
from whymath_backend.l2.weak_concept_recommendation import (
    WeakConceptRecommendation,
    recommend_weak_concepts,
)
from whymath_backend.l4.calibration_coaching import recommend_calibration_coaching
from whymath_backend.l4.metacognitive_trigger import CoachingTrigger, recommend_coaching
from whymath_backend.l4.prerequisite_coaching import recommend_prerequisite_coaching
from whymath_backend.l6.suneung import (
    METADATA_ONLY_SOURCES,
    SUNEUNG_EXAM_TYPES,
    recommend_suneung_index,
)
from whymath_backend.privacy import (
    UserDataExport,
    erase_user,
    export_user_data,
    external_export_pending,
    record_export_audit,
)
from whymath_backend.schema.activity import LearningSession as LearningSessionSchema
from whymath_backend.schema.assessment import AbilitySnapshot as AbilitySnapshotSchema
from whymath_backend.schema.assessment import Assessment as AssessmentSchema
from whymath_backend.schema.assessment import (
    ConceptMasteryHistory as ConceptMasteryHistorySchema,
)
from whymath_backend.schema.assessment import (
    SkillMasteryHistory as SkillMasteryHistorySchema,
)
from whymath_backend.schema.audit import DeletionAudit as DeletionAuditSchema
from whymath_backend.schema.audit import PrivacyAudit as PrivacyAuditSchema
from whymath_backend.schema.dialogue import Dialogue as DialogueSchema
from whymath_backend.schema.enums import (
    ASSESSED_ROLES,
    AuditEventKind,
    AuditResourceType,
    Persona,
    Resolution,
)

router = APIRouter(prefix="/v1/me", tags=["me"])

_logger = logging.getLogger("whymath.api.me")

SessionDep = Annotated[AsyncSession, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
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
# SEC-09: privacy-audit 조회의 선택적 이벤트 종류 필터 — resource_type 필터(slice 65/68)와 동형.
EventKindFilter = Annotated[
    list[AuditEventKind] | None,
    Query(
        description=(
            "개인정보 감사 이벤트 종류 필터(export_data·consent_change·admin_access). 반복 지정 "
            "시 OR(IN). 생략 시 전체."
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


@router.get(
    "/privacy-audit",
    response_model=list[PrivacyAuditSchema],
    summary="내 개인정보 감사 이력(반출·동의변경·관리자접근)",
)
async def list_my_privacy_audit(
    user: ConsentedUser,
    session: SessionDep,
    response: Response,
    limit: Limit = 50,
    offset: Offset = 0,
    event_kind: EventKindFilter = None,
    since: SinceParam = None,
    until: UntilParam = None,
    order: OrderParam = "desc",
    include_total: IncludeTotal = False,
) -> list[PrivacyAuditSchema]:
    """SEC-09: 본인 개인정보 감사 이력 — 기본 최신순(occurred_at desc·audit_id 안정 정렬).

    `privacy.audit`의 세 writer(`record_export_audit`·`record_consent_change_audit`·
    `record_admin_access_audit`)가 적재한 `privacy_audit`를 `user_id`(행위자) 스코핑으로
    조회한다(`GET /v1/me/deletions`와 동형 패턴 — `list_my_deletions` 참조). 삭제 이벤트는
    여기 없다(`deletion_audit`가 단일 권위 — 이중 진실원천 금지).

    `event_kind`(선택)로 종류 필터(export_data·consent_change·admin_access), `since`/`until`
    (선택)로 `occurred_at` 시간창(inclusive), `order`로 정렬 방향(기본 desc), `include_total=true`
    면 `X-Total-Count` 헤더. 모두 생략 시 전체.
    """
    conds = [
        PrivacyAudit.user_id == user.user_id,
        *time_window_conditions(PrivacyAudit.occurred_at, since, until),
    ]
    if event_kind:
        conds.append(PrivacyAudit.event_kind.in_([ek.value for ek in event_kind]))
    primary = PrivacyAudit.occurred_at.asc() if order == "asc" else PrivacyAudit.occurred_at.desc()
    stmt = (
        select(PrivacyAudit)
        .where(*conds)
        .order_by(primary, PrivacyAudit.audit_id)
        .limit(limit)
        .offset(offset)
    )
    result = await session.execute(stmt)
    rows = [row.to_schema() for row in result.scalars().all()]
    await _maybe_set_total(
        session,
        response,
        include_total,
        select(func.count()).select_from(PrivacyAudit).where(*conds),
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


class SkillMasteryUpdate(BaseModel):
    """채점으로 갱신된 한 스킬의 숙달 측정 — 응답에 포함(행동 축 학습 곡선 즉시 피드백).

    `ConceptMasteryUpdate`의 스킬 축 짝 — 키가 `concept_id`(UUID)가 아니라 `skill_id`(str)다.
    """

    skill_id: str
    mastery: float
    sample_size: int


class AttemptSubmitResponse(BaseModel):
    """`POST /v1/me/attempts` 응답 — 적재된 attempt + 갱신된 개념·스킬 숙달 목록."""

    attempt_id: uuid.UUID
    is_correct: bool
    mastery_updates: list[ConceptMasteryUpdate]
    skill_mastery_updates: list[SkillMasteryUpdate] = Field(
        default_factory=list,
        description=(
            "채점으로 갱신된 스킬 숙달 목록(Phase 2b-2·행동 축). 정답은 평가 개념 전체의 스킬, "
            "오답은 PRIMARY 개념의 스킬만(모델 B). concept→skill 매핑/해소가 없으면 빈 목록."
        ),
    )
    calibration_coaching: CoachingTrigger | None = Field(
        default=None,
        description=(
            "보정(calibration) 코칭(WH-1 §11.4) — 자기보고 확신도↔정오답 불일치 시 처방. "
            "과신(틀렸으나 확신↑)·과소신(맞았으나 확신↓) 구간에서만 채워지고, 잘 보정됐거나 "
            "확신 미제출(None)이면 null. 적재 로직과 무관한 순수 L4 결정(측정→코칭)."
        ),
    )


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
    이어서 `record_problem_attempt_mastery`로 숙달을 시계열에 누적한다 — **모델 B(역할 비대칭)**:
    정답은 평가 개념(PRIMARY·TESTED) *전체*, 오답은 책임귀속 가능한 PRIMARY만 갱신(L2 슬라이스 3).
    응답 `mastery_updates`엔 *실제 갱신된* 개념만 담긴다(오답 시 PRIMARY).

    이어서 `record_problem_attempt_skill_mastery`로 *스킬 축* 숙달도 같은 모델 B로 전파한다(Phase
    2b-2·행동 축) — 평가 개념을 `Concept.behavior_skills` 브리지로 mastery-estimable 스킬에 해소해
    갱신한다. 응답 `skill_mastery_updates`는 실제 갱신된 스킬만(매핑/해소 없으면 빈 목록).
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
    # 스킬 숙달 전파(Phase 2b-2·행동 축) — 같은 모델 B로 concept→skill 해소 후 스킬별 측정 적재.
    # 개념 전파와 독립 트랜잭션(자체 단일 commit)·concept→skill 매핑/해소 없으면 빈 리스트.
    skill_records = await record_problem_attempt_skill_mastery(
        session, user.user_id, body.problem_id, body.is_correct
    )
    # WH-1 §11.4 보정 루프: 이미 받은 자기보고 확신도↔정오답에서 과신/과소신 코칭 결정.
    # 순수 L4 결정(DB 무접근·적재 로직 불변)·확신 미제출(None)이면 None(자연).
    calibration_coaching = recommend_calibration_coaching(
        body.confidence_self_reported, body.is_correct
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
        skill_mastery_updates=[
            SkillMasteryUpdate(
                skill_id=r.skill_id,
                # 순수 커널이 항상 mastery를 채우나 ORM 타입이 float|None(개념 축 동형).
                mastery=float(r.mastery) if r.mastery is not None else 0.0,
                sample_size=r.sample_size if r.sample_size is not None else 0,
            )
            for r in skill_records
        ],
        calibration_coaching=calibration_coaching,
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


@router.get(
    "/skill-mastery",
    response_model=list[SkillMasteryHistorySchema],
    summary="내 스킬 숙달 학습 곡선(SkillMasteryHistory 시계열·행동 축)",
)
async def list_my_skill_mastery(
    user: ConsentedUser,
    session: SessionDep,
    response: Response,
    limit: Limit = 50,
    offset: Offset = 0,
    skill_id: Annotated[
        str | None, Query(description="한 스킬(`skill.<slug>`)의 곡선만 필터(선택).")
    ] = None,
    since: SinceParam = None,
    until: UntilParam = None,
    order: OrderParam = "desc",
    include_total: IncludeTotal = False,
) -> list[SkillMasteryHistorySchema]:
    """본인 스킬 숙달 측정 시계열 — 행동 축 학습 곡선(Phase 2b-2). 풀이 채점이 누적한
    `skill_mastery_history`를 user_id 스코핑으로 조회(타인 차단·`list_my_mastery` 스킬판).

    `skill_id`(선택)로 한 스킬의 곡선만·`since`/`until`로 시간창·`order`로 방향(기본 desc)·
    `include_total`로 `X-Total-Count`. 2차 정렬키 skill_id로 동률(같은 measured_at) 안정 정렬.
    """
    conds = [SkillMasteryHistory.user_id == user.user_id]
    if skill_id is not None:
        conds.append(SkillMasteryHistory.skill_id == skill_id)
    conds += time_window_conditions(SkillMasteryHistory.measured_at, since, until)
    primary = (
        SkillMasteryHistory.measured_at.asc()
        if order == "asc"
        else SkillMasteryHistory.measured_at.desc()
    )
    stmt = (
        select(SkillMasteryHistory)
        .where(*conds)
        .order_by(primary, SkillMasteryHistory.skill_id)
        .limit(limit)
        .offset(offset)
    )
    result = await session.execute(stmt)
    rows = [row.to_schema() for row in result.scalars().all()]
    await _maybe_set_total(
        session,
        response,
        include_total,
        select(func.count()).select_from(SkillMasteryHistory).where(*conds),
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
    Query(
        ge=1,
        le=500,
        description="최근 N개 지점만(시간 오름차순 중 끝 N). 생략 시 전체.",
    ),
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
        default=None,
        description="logistic(θ)∈[0,1] — BKT 숙달과 비교용. θ 없으면 null.",
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


# ── 원자그래프 소비 슬2: GET /v1/me/weak-concepts (약개념 추천 — 진단 약점 + code 메타 enrich) ──
# L2 약점 진단(`recommend_weak_concepts`·BKT/IRT 융합·약점 정렬·약점 필터)에 `atom_node`(code)
# 안전 그래프 메타(name_ko·subject_area·review_status)를 enrich해 "지금 무엇을 복습할지" 후보를
# 돌려준다(S0-4d·runtime truth=원자·`domain` 응답 필드는 이제 원자 subject_area 값). *학생 직접
# 노출이 아니라* 내부 조회 좌석(소비 슬 노출 계약과 일관 — 안전 필드만·본문 0). 진단·enrich·
# 게이팅 로직은 L2 좌석이 소유(L5는 표면·user_id 스코핑·읽기 전용·마이그레이션 0).
WeakLimit = Annotated[int, Query(ge=1, le=50, description="약점(저신호) 먼저 정렬 후 상위 N개만.")]
WeakThreshold = Annotated[
    float,
    Query(
        ge=0.0,
        le=1.0,
        description="이 숙달 미만(비교 가능한 두 신호 중 최저값 기준)인 개념만 약점으로 추천.",
    ),
]
WeakReviewedOnly = Annotated[
    bool,
    Query(
        description=(
            "검수 게이팅. false(기본)=recall 보존(pending·메타 미적재 개념도 노출). true="
            "review_status='reviewed'인 개념만(메타 없어 확인 불가인 code는 보수적 제외·필터)."
        ),
    ),
]


@router.get(
    "/weak-concepts",
    response_model=list[WeakConceptRecommendation],
    summary="내 약개념 추천(BKT/IRT 약점 + 개념그래프 안전 메타 enrich)",
)
async def get_my_weak_concepts(
    user: ConsentedUser,
    session: SessionDep,
    limit: WeakLimit = 10,
    threshold: WeakThreshold = 0.7,
    reviewed_only: WeakReviewedOnly = False,
) -> list[WeakConceptRecommendation]:
    """학습자 약점(BKT/IRT)을 식별해 원자그래프(`atom_node`·code) 안전 메타를 붙여 추천.

    L2 진단(`compute_concept_diagnoses`·BKT 최신 + IRT θ 융합·*약점 먼저* 정렬)을 재사용해
    약점(비교 가능한 두 신호 중 최저값 < `threshold`)인 개념만 거르고, 그 개념의 `concept_code`
    (=code)로 `atom_node`(PG 프로젝션·원자 메타 좌석) 안전 메타(name_ko·subject_area·review_status)
    를 *단일 IN 조회*로 enrich한다(S0-4d·runtime truth=원자·N+1 0·code 없거나 미적재면 None
    graceful). 응답 `domain` 필드는 계약 안정을 위해 이름을 유지하나 값은 원자 subject_area다.
    `reviewed_only=true`면 검수 안 된 개념을 *필터*(약점 정렬 유지)하고, `limit`로 상위 N만
    돌려준다. 진단·enrich·게이팅은 L2 좌석이 소유(`recommend_weak_concepts`)·user_id 스코핑·읽기
    전용.

    **노출 계약(CLAUDE.md)**: 학생 직접 노출이 아니라 *조회 좌석*(소비 슬과 일관)이다. enrich
    되는 건 안전 표시·게이팅 필드뿐 — **본문(description·formal_definition·core_proposition) 0**
    (atom_node에 본문 컬럼 자체가 없음·redaction). 우열 매기기·정답 빠르게 등 금기 표현 0.
    """
    return await recommend_weak_concepts(
        session,
        user.user_id,
        limit=limit,
        mastery_threshold=threshold,
        reviewed_only=reviewed_only,
    )


# ── 원자그래프 소비 선수 슬1: GET /v1/me/weak-concepts/{concept_id}/prerequisites ──
# 약개념 C의 *막힌 선수개념* 추천 — concept_edge(to==C·PREREQUISITE) traversal로 선수를 찾고,
# 그 중 학습자가 약한(막힌) 것을 mastery·atom_node 안전 메타와 함께 돌려준다(선수 복습 우선·S0-4d).
# 후행 개념이 안 되는 *근본 원인*이 선수 결손일 수 있으므로 "먼저 복습할 선수"를 가린다(LTHC).
# traversal·약점 필터·enrich·게이팅 로직은 L2 좌석이 소유(L5는 표면·user_id 스코핑·읽기 전용).
WeakOnly = Annotated[
    bool,
    Query(
        description=(
            "true(기본)=막힌(약한·숙달 미만) 선수만(측정 없는 선수 제외). false=모든 선수"
            "(약점 무관·미측정 포함)."
        ),
    ),
]
# 다단계(multi-hop) 선수 traversal 깊이 — 1=직접 선수만(기본·후방 호환)·2~상한=선수의 선수…까지.
# 선수 그래프는 DAG 보장(data-pipeline validate.py가 prerequisite_cycle hard error)이라 재귀는
# 자연 종료하나, 비용·노이즈를 막으려 상한으로 bound한다. 상한은 L2 단일 출처
# `MAX_PREREQUISITE_DEPTH`를 공유한다(매직 넘버 중복 제거·Q10-⑧).
MaxDepth = Annotated[
    int,
    Query(
        ge=1,
        le=MAX_PREREQUISITE_DEPTH,
        description=(
            "선수 traversal 최대 깊이 — 1=직접 선수만(기본)·2 이상=다단계 선수(선수의 선수…). "
            f"DAG 보장이라 종료, 비용·노이즈 상한 {MAX_PREREQUISITE_DEPTH}."
        ),
    ),
]


@router.get(
    "/weak-concepts/{concept_id}/prerequisites",
    response_model=list[PrerequisiteGap],
    summary="약개념의 막힌 선수개념 추천(선수 traversal + BKT/IRT 약점 + 안전 메타 enrich)",
)
async def get_my_prerequisite_gaps(
    concept_id: uuid.UUID,
    user: ConsentedUser,
    session: SessionDep,
    threshold: WeakThreshold = 0.7,
    reviewed_only: WeakReviewedOnly = False,
    weak_only: WeakOnly = True,
    max_depth: MaxDepth = 1,
) -> list[PrerequisiteGap]:
    """약개념 C(`concept_id`)의 선수개념 중 *막힌*(약한) 것을 골라 "먼저 복습할 선수"로 추천.

    `concept_edge`에서 `to_concept_id == concept_id AND edge_type == PREREQUISITE`인 행의
    `from_concept_id`(선수)들을 traversal하고(방향: from은 to의 선수), 각 선수의 BKT/IRT 숙달을
    L2 진단(`compute_concept_diagnoses`)으로 lookup해 `weak_only=true`(기본)면 막힌(숙달 <
    `threshold`) 선수만 남긴다. 선수의 `concept_code`(=code)로 `atom_node` 안전 메타(name_ko·
    subject_area·review_status)를 *단일 IN 조회*로 enrich하고(S0-4d·runtime truth=원자·N+1 0·미적재
    None graceful·응답 `domain` 필드는 계약 안정상 이름 유지·값은 원자 subject_area),
    `reviewed_only=true`면 검수 안 된 선수를 *필터*한다.

    **다단계(multi-hop) traversal**: `max_depth=1`(기본)이면 직접 선수만(기존 1-hop·후방 호환)·
    `max_depth=2~5`면 "선수의 선수…"까지 재귀 CTE로 따라간다 — 후행 개념이 안 되는 *근본 결손*이
    여러 단계 아래일 수 있기 때문(LTHC). 응답 각 항목의 `depth`(1=직접 선수·2=선수의 선수…)로
    선수 거리를 노출한다(그래프 구조 메타·안전). 같은 선수가 여러 경로로 닿으면 가장 가까운(MIN)
    거리만 1건. 선수 그래프는 DAG 보장이라 재귀는 종료하며 `max_depth`로 방어적 bound.

    정렬은 weakness 오름차순(가장 약한 선수=root blocker 먼저)·동률은 **depth 오름차순**(가까운
    선수 먼저·더 직접 실행 가능)·그 다음 선수관계 강도(edge_strength) 내림차순. traversal·약점·
    enrich·게이팅은 L2 좌석이 소유(`recommend_prerequisite_gaps`)·user_id 스코핑·읽기 전용.

    **노출 계약(CLAUDE.md)**: 학생 직접 노출이 아니라 *조회 좌석*(약개념 추천과 일관)이다. enrich
    되는 건 안전 표시·게이팅 필드뿐 — **본문(description·formal_definition·core_proposition) 0**
    (atom_node·PrerequisiteGap 스키마에 컬럼/슬롯 자체가 없음·redaction). 우열 매기기·정답 빠르게
    등 금기 0.
    """
    return await recommend_prerequisite_gaps(
        session,
        user.user_id,
        concept_id,
        mastery_threshold=threshold,
        reviewed_only=reviewed_only,
        weak_only=weak_only,
        max_depth=max_depth,
    )


# ── L4 코칭 결선: GET /v1/me/weak-concepts/{concept_id}/coaching (선수 차단 우선 코칭) ──
# 첫 L4→L2 결선이다(L_n→L_{n-1} 허용). L2 선수 추천(막힌 선수)이 있으면 후행을 바로 코칭하지
# 않고 *선수 복습을 먼저 권하는* L4 코칭(prerequisite_review)을 돌려준다(LTHC·기초 우선). 막힌
# 선수가 없으면 일반 메타인지 코칭(`recommend_coaching`·BKT/IRT)으로 fallback한다. 오케스트레이션
# (L2 fetch + L4 decide 배선)은 L5(여기)·순수 결정은 L4가 소유(역방향 의존 0).
@router.get(
    "/weak-concepts/{concept_id}/coaching",
    response_model=CoachingTrigger,
    summary="약개념 코칭 결정(막힌 선수 있으면 선수 복습 우선·없으면 메타인지 코칭)",
)
async def get_my_concept_coaching(
    concept_id: uuid.UUID,
    user: ConsentedUser,
    session: SessionDep,
    threshold: WeakThreshold = 0.7,
    max_depth: MaxDepth = 1,
) -> CoachingTrigger:
    """약개념 C(`concept_id`)에 대한 L4 코칭 결정 — **선수 차단 우선·없으면 메타인지 코칭**.

    첫 L4→L2 결선(L_n→L_{n-1} 허용). 오케스트레이션:
      ① **L2 fetch** — `recommend_prerequisite_gaps(weak_only=True)`로 C의 *막힌 선수개념*을
         조회한다(weakness asc 정렬·`gaps[0]`=top blocker).
      ② **선수 차단 우선** — `recommend_prerequisite_coaching(gaps)`이 *막힌 선수가 있으면*
         `prerequisite_review` 코칭(선수부터 복습 권유)을 돌려준다. 이걸 *최우선*으로 반환한다 —
         후행을 바로 코칭하면 비계가 허공에 뜨기 때문(LTHC·기초 우선·CLAUDE.md 교수학 #1·#3).
      ③ **fallback(막힌 선수 없음)** — `compute_concept_diagnoses`에서 이 개념의 BKT/IRT 진단을
         찾아 일반 메타인지 코칭(`recommend_coaching`)으로 넘어간다(verify/foundation/advance 등).
         진단이 아예 없으면 `recommend_coaching(None, None)`(→ diagnose·추가 진단 권유).

    `threshold`(막힘 판정 숙달 임계)·`max_depth`(다단계 선수 traversal 깊이)는 선수 슬1과 동일
    재사용. user_id 스코핑·읽기 전용(마이그레이션 0). L4 순수 결정은 `recommend_prerequisite_
    coaching`·`recommend_coaching`이 소유하고, 여기(L5)는 L2 fetch + L4 decide *배선*만 한다.

    **노출 계약(CLAUDE.md)**: 학생 직접 노출이 아니라 *조회 좌석*(소비 슬 일관)이다. rationale·
    prompt는 *자체 작성 코칭 문구*이며 개념 *본문(description·formal_definition·evidence)은 0* —
    선수 이름(name_ko·concept_name·안전 표시 필드)만 삽입된다(`PrerequisiteGap`에 본문 슬롯 없음).
    학생 prompt는 격려·메타인지 유도이며 막힌 선수를 *비난하지 않는다*(부정 강화·우열·"정답 빠르게"
    금지·바로 정답 제공 아님).
    """
    # ① L2 fetch — 막힌 선수(weak_only=True·weakness asc 정렬). ② 선수 차단 *최우선*.
    gaps = await recommend_prerequisite_gaps(
        session,
        user.user_id,
        concept_id,
        mastery_threshold=threshold,
        weak_only=True,
        max_depth=max_depth,
    )
    trigger = recommend_prerequisite_coaching(gaps)
    if trigger is not None:
        return trigger  # 막힌 선수 있음 → 선수 복습 우선(후행 코칭 보류).

    # ③ fallback — 막힌 선수 없음 → 이 개념 자체의 BKT/IRT로 일반 메타인지 코칭.
    diagnoses = await compute_concept_diagnoses(session, user.user_id)
    diag = next((d for d in diagnoses if d.concept_id == concept_id), None)
    if diag is None:
        return recommend_coaching(None, None)  # 진단 없음 → diagnose(추가 진단 권유).
    return recommend_coaching(diag.bkt_mastery, diag.irt_theta)


# ── 개념그래프 소비 학습경로 슬: GET /v1/me/weak-concepts/{concept_id}/learning-path ──
# 선수 슬1(prerequisites)이 "어떤 선수가 막혔나"를 weakness 정렬로 *골랐다면*, 이 슬은 그 막힌
# 선수들 *사이의 선수 의존*을 Kahn 위상정렬해 "무엇부터 복습해야 하나 — 근본 선수 먼저, 그 위에
# 쌓이는 말단 나중"의 학습 *순서*를 돌려준다(LTHC 기초 우선의 기계적 구현). prerequisites 미러:
# query 4종·게이팅·user_id 스코핑을 그대로 답습하되, 응답이 *순서화된 학습 경로*다. L2 fetch +
# L2 위상정렬 *배선*만 L5(여기)·순수 정렬·내부엣지 조회는 L2(`build_learning_path`)가 소유.
@router.get(
    "/weak-concepts/{concept_id}/learning-path",
    response_model=LearningPath,
    summary="약개념의 막힌 선수개념 학습 경로(선수 위상정렬·근본→말단 순서)",
)
async def get_my_learning_path(
    concept_id: uuid.UUID,
    user: ConsentedUser,
    session: SessionDep,
    threshold: WeakThreshold = 0.7,
    reviewed_only: WeakReviewedOnly = False,
    weak_only: WeakOnly = True,
    max_depth: MaxDepth = 1,
) -> LearningPath:
    """약개념 C(`concept_id`)의 *막힌 선수개념들*을 위상정렬한 **학습 순서**(근본 먼저)로 반환.

    선수 슬1(`prerequisites`)의 미러다 — 같은 query(`threshold`·`reviewed_only`·`weak_only`·
    `max_depth`)·게이팅·user_id 스코핑으로 막힌 선수를 고르지만, 응답이 *순서화된 경로*다.
    오케스트레이션:
      ① **L2 fetch** — `recommend_prerequisite_gaps`로 C의 막힌 선수개념(weakness asc)을
         조회한다(`prerequisites`와 동일 인자).
      ② **L2 위상정렬** — `build_learning_path(session, gaps)`가 그 막힌 선수 집합 *내부*의
         직접 선수 엣지를 조회해 Kahn 위상정렬한다 — in-degree 0(선수 의존 없는 *근본*)을 먼저
         방출하고 그 위에 쌓이는 선수를 뒤에 둔다. **추천의 depth/strength 정렬과 다르다**:
         두 선수가 둘 다 직접 선수(depth=1)여도 A가 B의 선수면 A를 먼저 다져야 한다(LTHC).
         사이클(부분 적재 방어)은 잔여로 정직하게 표시(`has_cycle`·`is_cycle_residual`).

    L2 fetch + L2 정렬 *배선*만 여기(L5)가 소유하고(신규 로직 0), 순수 위상정렬·내부엣지 조회는
    L2(`build_learning_path`·`order_learning_path`)가 소유한다. user_id 스코핑·읽기 전용·
    마이그레이션 0.

    **노출 계약(CLAUDE.md)**: 학생 직접 노출이 아니라 *조회·순서화 좌석*(소비 슬 일관)이다.
    `LearningStep`은 안전 표시·구조 메타(concept_code·concept_name·weakness·depth·
    edge_strength·position)만 담고 — **본문(description·formal_definition·intuitive_
    explanation) 슬롯 자체가 없다**(frozen 스키마·redaction). 우열 매기기·정답 빠르게 등 금기 0.
    """
    gaps = await recommend_prerequisite_gaps(
        session,
        user.user_id,
        concept_id,
        mastery_threshold=threshold,
        reviewed_only=reviewed_only,
        weak_only=weak_only,
        max_depth=max_depth,
    )
    return await build_learning_path(session, gaps)


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
# S2-06: ?mode=suneung — 수능 적응 추천(L6 게이팅 × L2 IRT CAT). 미지정(None)이면 기존
# 기본 CAT(슬라이스 12~17) 경로 그대로(회귀 0). 값 공간은 Literal로 닫는다(오타 → 422).
NextProblemMode = Annotated[
    Literal["suneung"] | None,
    Query(description="응용 모드. 'suneung'=수능 적응 추천(L6 게이팅×IRT CAT). 미지정=기본 CAT."),
]
# S2-06: 수능 모드 대상 페르소나 — L6 게이팅(`is_suneung_eligible`)의 판정 축. mode=suneung
# 에서만 쓰인다(기본 CAT 경로는 무시). 기본 A_일반고고3(MVP 정시 정면 대상 — L6 기본과 동일).
SuneungPersona = Annotated[
    Persona,
    Query(description="수능 모드 대상 페르소나(mode=suneung에서만 사용). 기본 A_일반고고3."),
]
# S3-03: GET /me/harness-metrics?mode=suneung — 응용 모드 스코프. 설정 시 attempt_event 기반
# 지표(①⑤⑧)를 그 mode 태그가 실린 이벤트만으로 집계(수능 세션 측정). 미지정이면 전 mode 포함
# (기존 동작 불변). 값 공간은 next-problem과 동일 Literal로 닫는다(오타 → 422).
HarnessMetricsMode = Annotated[
    Literal["suneung"] | None,
    Query(
        description=(
            "응용 모드 스코프. 'suneung'이면 attempt_event 기반 지표(verify·도움 감소·도달 깊이)를 "
            "수능 세션 이벤트만으로 필터. 미지정=전 mode(기존 동작). 완전한 mode별 집계는 후속."
        )
    ),
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


async def _load_weak_concept_weights(
    session: AsyncSession,
    user_id: uuid.UUID,
    candidate_ids: list[uuid.UUID],
) -> list[float]:
    """슬라이스 17 약점 가중 *조회 배선* — 숙달 스냅샷·개념 매핑 2쿼리 후 가중치 산출.

    S2-06에서 기존 기본 CAT 경로의 인라인 블록을 헬퍼로 추출했다(동작 무변경) — 기본 CAT과
    수능 모드(mode=suneung) *양 분기*가 같은 약점 가중을 공유하기 위함이다. 조회 2회:
      ① 개념별 BKT 숙달 스냅샷(개념당 최신 — DISTINCT ON), ② 후보 문항의 평가 개념 매핑
      (`ASSESSED_ROLES`만). 순수 산출은 `_weak_concept_weights`에 위임한다.
    """
    mastery_stmt = (
        select(ConceptMasteryHistory.concept_id, ConceptMasteryHistory.mastery)
        .where(ConceptMasteryHistory.user_id == user_id)
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
    return _weak_concept_weights(candidate_ids, problem_concepts, mastery)


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
    mode: NextProblemMode = None,
    persona: SuneungPersona = Persona.A_일반고고3,
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

    수능 적응 추천(S2-06·`?mode=suneung`): θ·SE 계산은 공통, *후보 조회·선택만* 분기한다.
      - SQL 사전필터는 **축소 전용**(저작권 출처 사전배제·수능 신호(기출 유형 ∪ 시그니처 보유)·
        미응답·θ 근방 50개) — 성능 장치일 뿐, **최종 적격 판정은 `recommend_suneung_index`
        내부의 `is_suneung_eligible`(L6 진실 게이트)이 재수행**한다(저작권·페르소나 재검증 —
        사전필터가 느슨해도 부적격이 새지 않는다).
      - persona_fit-only 적격(기출·시그니처 없이 적합도만 충족) 문항은 사전필터에 안 잡히는
        *의도적 축소*다 — 현 코퍼스 persona_fit은 전부 {}라 실손실 0(적합도 적재 시 재검토).
      - 선택은 L6×L2 결합: 수능 우선순위 가중(`suneung_item_weight`) × 약점 가중
        (`prioritize_weak_concepts` — 기본 CAT과 공유하는 `_load_weak_concept_weights`)을
        곱해 가중 정보량 최대 문항(`l2.select_weighted_item`)을 고른다.
      - `persona`는 수능 모드에서만 쓰인다(기본 A_일반고고3). D·E는 게이트에서 전부 차단 →
        problem_id=null. mode 미지정 경로는 코드 무변경(회귀 0)·응답 모델 동일.
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

    # ── S2-06: 수능 적응 추천 분기 — θ·SE는 위 공통, 후보 조회·선택만 다르다. ──
    if mode == "suneung":
        # SQL 사전필터 = *축소 전용*(성능 장치). 최종 판정은 recommend_suneung_index 내부의
        # is_suneung_eligible(진실 게이트)이 재수행한다(핸들러 docstring 참조). 게이팅에
        # source_type·persona_fit·signature_patterns 등 전 필드가 필요해 ORM 전체 행을 뽑는다.
        suneung_stmt = select(Problem).where(
            # 응답 difficulty 노출·b 폴백을 위해 기본 CAT과 동일하게 난이도 라벨 보유만 후보.
            Problem.difficulty_overall.isnot(None),
            # 저작권 사전축소 — 본문 미보유 출처(평가원/EBS/교과서)는 SQL에서 미리 배제
            # (게이트가 어차피 재차단하지만, 차단될 행이 θ 근방 50개 풀을 잠식하지 않게).
            Problem.source_type.notin_([s.value for s in METADATA_ONLY_SOURCES]),
            # 수능 신호 사전축소 — 기출 유형(수능/모평/학평) 또는 시그니처 패턴 보유
            # (signature_patterns는 enum ARRAY — cardinality>0, GIN 인덱스 활용 가능).
            or_(
                Problem.exam_type.in_([e.value for e in SUNEUNG_EXAM_TYPES]),
                func.cardinality(Problem.signature_patterns) > 0,
            ),
        )
        if attempted_ids:
            suneung_stmt = suneung_stmt.where(Problem.problem_id.notin_(attempted_ids))
        # θ 근방 정렬·풀 크기는 기본 CAT과 동일(보정 b 우선·휴리스틱 폴백 COALESCE).
        suneung_stmt = suneung_stmt.order_by(
            func.abs(
                func.coalesce(
                    Problem.irt_difficulty_b,
                    Problem.difficulty_overall - _DIFFICULTY_MIDPOINT,
                )
                - theta
            )
        ).limit(_CANDIDATE_POOL_SIZE)
        candidates = [
            row.to_schema() for row in (await session.execute(suneung_stmt)).scalars().all()
        ]

        # 약점 가중(슬라이스 17)은 기본 CAT과 *같은 헬퍼*를 공유 — extra_weights로 곱 결합.
        extra_weights: list[float] | None = None
        if prioritize_weak_concepts and candidates:
            extra_weights = await _load_weak_concept_weights(
                session, user.user_id, [p.problem_id for p in candidates]
            )
        chosen_index = recommend_suneung_index(
            theta, candidates, persona, extra_weights=extra_weights
        )
        if chosen_index is None:
            # 적격 후보 0(전부 차단·신호 없음·b 없음) — 기본 CAT과 동일한 null 계약.
            return NextProblemResponse(
                problem_id=None,
                theta=theta,
                difficulty=None,
                standard_error=standard_error,
                measurement_sufficient=measurement_sufficient,
            )
        picked = candidates[chosen_index]
        return NextProblemResponse(
            problem_id=picked.problem_id,
            theta=theta,
            # SQL이 difficulty_overall NOT NULL을 보장하나, 스키마 타입(Optional) 정합 방어.
            difficulty=(
                None if picked.difficulty_overall is None else float(picked.difficulty_overall)
            ),
            standard_error=standard_error,
            measurement_sufficient=measurement_sufficient,
        )

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
    # S2-06에서 조회 배선을 `_load_weak_concept_weights`로 추출(수능 분기와 공유·동작 무변경).
    weights: list[float] | None = None
    if prioritize_weak_concepts and candidate_rows:
        weights = await _load_weak_concept_weights(
            session, user.user_id, [pid for pid, _d, _b in candidate_rows]
        )

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


class DialogueEndRequest(BaseModel):
    """대화 종료 시 세션 결말(resolution) 선택 보고 — `PATCH /v1/me/dialogues/{id}/end` 본문.

    `resolution`은 *클라이언트 보고*다(`AttemptSubmitRequest.is_correct` 동형) — 클라이언트가
    LTHC 답 미루기 루프를 구동해 세션 결말(자력해결/유도/힌트/풀이공개/포기)의 자연 권위자다.
    서버는 이를 *영속만* 하고 신호로 판정하지 않는다(정답성·hint_level의 dialogue 귀속·포기
    영속은 후속 슬라이스). 본문 자체가 선택(미제공 시 `ended_at`만 채우는 기존 동작 보존).
    """

    model_config = ConfigDict(extra="forbid")

    resolution: Resolution | None = Field(
        default=None,
        description="세션 결말(클라이언트 보고·선택). 미제공 시 ended_at만 채움(하위호환).",
    )


@router.patch(
    "/dialogues/{dialogue_id}/end",
    response_model=DialogueSchema,
    summary="내 Socratic 대화 종료(ended_at 채움·resolution 선택 보고)",
)
async def end_my_dialogue(
    dialogue_id: uuid.UUID,
    user: ConsentedUser,
    session: SessionDep,
    body: Annotated[DialogueEndRequest | None, Body()] = None,
) -> DialogueSchema:
    """slice 52 (slice 55 리팩터): 본인 Dialogue 종료(`ended_at`=now)·idempotent·404 비누설.

    resolution(세션 결말·**클라이언트 보고**)을 선택 적재한다 — 서버는 영속만 하고 신호로
    판정하지 않는다(정답성·hint_level의 dialogue 귀속·포기 영속은 후속). **첫-종결-우선**:
    이미 resolution이 있으면 보존한다(낙인 방지·`ended_at` idempotency와 동형). resolution은
    ended_at과 *같은 트랜잭션*에 커밋한다(부분 적용 방지). 이 값은 self_solve_rate 대리 지표
    (`harness/wh1_evaluation.py` ⑪)의 원천이 된다.
    """
    row, newly_closed = await _close_owned_resource(
        session,
        Dialogue,
        dialogue_id,
        user.user_id,
        "ended_at",
        "대화를 찾을 수 없습니다.",
        commit=False,  # resolution 쓰기와 같은 트랜잭션에 묶어 원자 커밋(부분 적용 방지).
    )
    # resolution은 클라 보고(선택)·첫 기록 우선 — 이미 있으면 보존(낙인 방지). ended_at 재호출
    # 후에도 처음 제공되면 채울 수 있다(종료 먼저·결말 나중 보고 허용).
    resolution_written = False
    if body is not None and body.resolution is not None and row.resolution is None:
        row.resolution = body.resolution
        resolution_written = True
    if newly_closed or resolution_written:  # 변경이 있을 때만 커밋(완전 idempotent 재호출은 no-op).
        await session.commit()
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


# ── DELETE /v1/me : 계정·전체 데이터 영구 삭제(개인정보 삭제권·R11) ──
# 단일 리소스 삭제(위 sessions/dialogues/assessments)와 달리, 본인 *계정 전체*(17개 테이블 +
# user_profile)를 단일 트랜잭션으로 지운다(privacy.erase_user·#242). 오삭제 방지로 확인 문구를
# 요구하고, **CurrentUser**(동의 게이트 아님)를 쓴다 — 미성년 동의 미설정자도 *삭제*는 가능해야
# 한다(삭제권 우선·수집 동의와 무관). 법정대리인 동의 *흐름*은 후속(여기선 본인 인증 + 확인 문구).
_DELETE_CONFIRMATION = "DELETE_MY_ACCOUNT"


class AccountErasureRequest(BaseModel):
    """계정 삭제 요청 — 오삭제 방지 확인 문구 필수."""

    model_config = ConfigDict(extra="forbid")

    confirmation: str = Field(
        description=f"오삭제 방지 확인 문구 — 정확히 '{_DELETE_CONFIRMATION}'이어야 한다.",
    )


class AccountErasureResponse(BaseModel):
    """계정 삭제 영수증 — 무엇이 지워졌는지의 *요약*(내부 테이블 구조 비노출)."""

    model_config = ConfigDict(extra="forbid")

    user_id: uuid.UUID = Field(description="삭제된 사용자 id.")
    total_rows_deleted: int = Field(ge=0, description="삭제된 총 행수(전 테이블 + user_profile).")


@router.delete(
    "",
    response_model=AccountErasureResponse,
    summary="내 계정·전체 데이터 영구 삭제(개인정보 삭제권·R11)",
)
async def erase_my_account(
    body: AccountErasureRequest,
    user: CurrentUser,
    session: SessionDep,
) -> AccountErasureResponse:
    """삭제권(R11) — 본인 계정의 *모든* 학생-연결 데이터를 단일 트랜잭션으로 영구 삭제.

    인증된 *본인만*(user_id=토큰 subject) 자기 계정을 지운다. 오삭제 방지로 확인 문구
    (`confirmation == '{_DELETE_CONFIRMATION}'`) 불일치 시 **400**. `privacy.erase_user`(#242)
    오케스트레이션을 호출해 17개 테이블 + user_profile을 자식→부모 순서로 지우고, 삭제 *시도*는
    `DeletionAudit`로 잔존한다(GDPR 증빙). 같은 트랜잭션 commit이라 부분 삭제가 없다. 멱등
    (이미 없으면 0행). **동의 게이트 아님**(`CurrentUser`) — 미성년 동의 미설정자도 삭제 가능
    (삭제권 우선). 법정대리인 동의 *흐름*은 후속.

    응답은 *요약 영수증*(user_id·총 삭제 행수)만 — 내부 테이블 구조는 노출하지 않는다. 삭제 후
    본인 토큰/세션도 사라지므로(refresh_token_session 포함) 이후 요청은 재인증이 필요하다.

    RDB 밖 store(ClickHouse·S3·Redis)는 이 트랜잭션이 못 지운다 — `report.pending_external`
    매니페스트를 *ops 로그*로 남겨(store명·user_id만) 별도 삭제가 필요함을 가시화한다(누락 은폐
    금지·GDPR 범위 정직). student-facing 응답엔 인프라 정보를 싣지 않는다(정보 누출 방지).
    """
    if body.confirmation != _DELETE_CONFIRMATION:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"확인 문구가 일치하지 않습니다('{_DELETE_CONFIRMATION}' 필요).",
        )
    # 삭제 후 user 객체 만료(expire_on_commit)에 대비해 user_id를 먼저 포획.
    user_id = user.user_id
    report = await erase_user(session, user_id=user_id)
    await session.commit()
    # ops 가시화 — RDB 밖 store(ClickHouse·S3·Redis)는 이 TX가 못 지운다(report.pending_external).
    # 누락을 조용히 넘기지 않도록 알림(store명·user_id만·키 패턴 미로깅) — 별도 삭제 필요.
    _logger.info(
        "개인정보 삭제권 실행: user=%s · PG %d행 삭제 · 외부 store %d곳 별도 삭제 필요(%s)",
        user_id,
        report.total_rows_deleted,
        len(report.pending_external),
        ", ".join(t.store for t in report.pending_external),
    )
    return AccountErasureResponse(user_id=user_id, total_rows_deleted=report.total_rows_deleted)


@router.get(
    "/export",
    response_model=UserDataExport,
    summary="내 데이터 내보내기(개인정보 열람·이동권·GDPR)",
)
async def export_my_data(
    request: Request,
    user: ConsentedUser,
    session: SessionDep,
    settings: SettingsDep,
) -> UserDataExport:
    """열람·이동권 — 본인의 학습/진단 데이터를 구조화 JSON으로 내려받는다(삭제권의 짝).

    인증된 *본인만*(`user_id=토큰 subject`) 자기 데이터를 받는다(다른 /me GET과 동형·user_id
    스코핑). `privacy.export_user_data`(#264·읽기 전용)가 `_EXPORT_PLAN`의 학습/진단 5종 +
    user_profile을 모아 반환한다. **부분 export**임을 `not_included`로 정직히 고지한다(대화·시계열·
    외부 store 등 미포함·후속). per-user 본인 데이터라 HTTP 노출이 맞다(전역 집계 아님).

    외부 store(ClickHouse·S3·Redis)는 RDB 밖이라 이 export에 못 담는다 — `external_export_pending`
    매니페스트를 *ops 로그*로 남겨(store명·user_id만) 별도 export가 필요함을 가시화한다(누락 은폐
    금지·GDPR 범위 정직). student-facing 응답엔 인프라 정보를 싣지 않는다(정보 누출 방지).

    SEC-09: export payload를 모은 *뒤*(반출 내용이 아니라 "반출이 일어났다"는 사실만) `privacy_
    audit`에 감사 1행을 적재하고 이 요청 안에서 commit한다(반출과 감사가 원자적 — 한쪽만
    성공하는 부분 상태를 만들지 않는다). `export_user_data`는 읽기 전용(commit 0)이라 이 함수가
    이 엔드포인트 최초의 쓰기다.
    """
    export = await export_user_data(session, user_id=user.user_id)
    record_export_audit(session, user_id=user.user_id, ip=_client_ip(request), settings=settings)
    await session.commit()
    # ops 가시화 — RDB 밖 store는 이 export(PG)에 미포함(store명·user_id만·키 패턴 미로깅).
    pending = external_export_pending(user.user_id)
    _logger.info(
        "개인정보 열람·이동권 export: user=%s · 카테고리 %d · 외부 store %d곳 별도 export 필요(%s)",
        user.user_id,
        len(export.data),
        len(pending),
        ", ".join(t.store for t in pending),
    )
    return export


# ── WH-1 0단계: GET /v1/me/harness-metrics (대리 지표 7종 + S3 4종 커버리지 맵 — 본인 스코핑) ──
# 설계안 04a §8.4 "0단계 대리 지표 베이스라인 좌석"의 노출 표면. 이제 대리 지표 7종 모두 계측
# 좌석이 가동(⑦은 근사)이고, S3(status_roadmap §3) 세션 대리 지표 4종(⑧ 답 미루기 도달 깊이·
# ⑨ BKT 숙달 증가율·⑩ 오개념 해소율·⑪ 스스로 풀이 도달율)이 편입됐다. 각 지표는 표본 0/부족이면
# value=None + status(NO_DATA) + note로 갭을 표면화한다(날조 금지·CLAUDE.md "모르면 모른다").
# 코호트 전체 집계(user_id=None)는 ops/스크립트가 직접 호출 — 이 엔드포인트는 *본인 집계 신호만*
# 노출(타 학생 0·admin auth 범위 밖).
@router.get(
    "/harness-metrics",
    response_model=SurrogateMetrics,
    summary="내 WH-1 0단계 대리 지표(7종 + S3 세션 4종 커버리지 맵)",
)
async def get_my_harness_metrics(
    user: ConsentedUser,
    session: SessionDep,
    since: SinceParam = None,
    until: UntilParam = None,
    mode: HarnessMetricsMode = None,
) -> SurrogateMetrics:
    """WH-1 튜터링 하네스 0단계 대리 지표 7종 + S3 세션 4종 — *본인* 집계의 커버리지 맵.

    설계안 04a §8.4 "측정 없는 도입 없음" 0단계 베이스라인. 대리 지표 7종(① verify 통과율·
    ② 진단정확도·③ 세션 완주율·④ 턴당 토큰·⑤ 도움 감소 곡선·⑥ 보정 점수·⑦ 전이 점수[근사])은
    모두 계측 좌석이 살아 있고, S3(status_roadmap §3) 세션 대리 지표 4종(⑧ 답 미루기 도달 깊이·
    ⑨ BKT 숙달 증가율·⑩ 오개념 해소율·⑪ 스스로 풀이 도달율)이 편입됐다. 각 지표는 표본 0/부족이면
    value=None + status + note로 "무엇을 만들면 잴 수 있는지"를 정직하게 드러낸다(가짜 0/stub 금지).
    ⑨는 measured_at·⑩은 updated_at·⑪은 started_at(resolution) 시간창을 쓰고, 나머지는
    started_at/event_at 기준이다. ⑪ resolution은 클라이언트 보고(PATCH .../end 적재·서버 미판정).

    `since`/`until`(선택)로 시간창(inclusive·TZ-aware ISO8601·naive·since>until은
    422). user_id는 인증에서 주입(본인 집계만).

    **노출 계약(CLAUDE.md 미성년 PII·식별 분석 금기)**: 본인 집계 신호(완주율·턴당 토큰 등)만
    반환 — 타 학생 데이터 0·개념 본문 0·정답 0. 코호트 전체 집계는 admin auth 범위라 이
    엔드포인트에 미포함(ops/스크립트가 `compute_wh1_surrogate_metrics(user_id=None)` 직접 호출).
    """
    # 시간창 검증(noexpose 계층): naive·since>until 거부. 검증된 경계를 harness에 그대로 전달.
    since = _validate_tz_aware(since, "since")
    until = _validate_tz_aware(until, "until")
    _validate_time_window(since, until, "since", "until")
    # S3-03: mode 스코프(예: suneung) — 설정 시 attempt_event 기반 지표(①⑤⑧)를 그 mode 태그가
    # 실린 이벤트만으로 집계한다(수능 세션 측정). 미지정이면 전 mode 포함(기존 동작 불변).
    return await compute_wh1_surrogate_metrics(
        session, user_id=user.user_id, since=since, until=until, mode=mode
    )
