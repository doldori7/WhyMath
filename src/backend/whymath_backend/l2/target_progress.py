"""L2 학습자 모델 — 목표(수능 D-day·목표 등급/점수·성취기준 커버리지) 조회 좌석.

`UserProfile.target_exam_date`/`target_grade`/`target_score`는 `PATCH /v1/users/me`로 *쓰기*만
되어 왔고, 지금까지 학생에게 다시 읽혀준 적이 없었다(이 모듈이 그 **첫 reader**). `target_grade`
(수능 등급 1~9, 학년이 아님)·`target_score`(목표 표준점수)는 학생이 입력한 값을 **그대로
echo**할 뿐이며, 이 값들로부터 예상 등급·예상 점수를 *예측*하는 로직은 이 모듈에 없다 —
CLAUDE.md "학습 시간·정답률만으로 우열을 매기는 게임화 금지"·"부정적 피드백을 정서적으로
강화하는 표현 금지"의 연장선에서, 점수·등급 *예측* 필드 자체를 만들지 않는다(과공학·성급한
확신 방지). `TargetProgress.model_fields`가 예측 필드 부재를 테스트로 동결한다.

성취기준 커버리지 스코프는 v0 정책이다 — MVP 페르소나 A(고3)만 지원하는 현 상태를 반영해,
`UserProfile.school_type`(고교 하위유형 8종만 존재하는 enum — 초·중학 값이 아예 없음)이
None이 아니면 **학교유형을 세분하지 않고** '2022 개정' × '고등학교' 성취기준 전체를 단일
스코프로 쓴다. `school_type`이 None이면(신규 학생 등) 스코프 계산 자체가 불가능하므로
`standard_coverage_*` 세 필드를 전부 None으로 정직하게 비운다(0%로 위장하지 않음).
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from whymath_backend.db.models.achievement_standard import AchievementStandard
from whymath_backend.db.models.assessment import ConceptMasteryHistory
from whymath_backend.db.models.concept import Concept
from whymath_backend.db.models.concept_standard_link import ConceptStandardLink
from whymath_backend.db.models.user import UserProfile

# v0 스코프 정책 — 학교유형 세분화 없이 전체 '고등학교' 성취기준(2022 개정)을 단일 스코프로 사용.
_SCOPE_CURRICULUM_REVISION = "2022 개정"
_SCOPE_SCHOOL_TYPE = "고등학교"


class TargetProgress(BaseModel):
    """학생 목표 대비 진행 상황 — D-day·목표(echo)·성취기준 커버리지(예측 필드 없음)."""

    target_exam_date: date | None = Field(default=None, description="목표 시험일(echo).")
    days_until_exam: int | None = Field(
        default=None,
        description=(
            "목표일까지 남은 일수(`target_exam_date - as_of`). 목표일이 없으면 null. "
            "과거 날짜여도 클램프하지 않고 음수 그대로(정직 표기)."
        ),
    )
    target_grade: int | None = Field(
        default=None, description="목표 등급(수능 1~9등급, echo — 예측 아님)."
    )
    target_score: int | None = Field(default=None, description="목표 표준점수(echo — 예측 아님).")
    standard_coverage_percent: float | None = Field(
        default=None,
        description=(
            "스코프 성취기준 중 관측(측정 이력 있는 개념 연결) 비율(%). 스코프 계산 불가 시 null."
        ),
    )
    standard_coverage_observed: int | None = Field(
        default=None, description="관측된(연결된 개념에 측정 이력 1건 이상) 성취기준 수."
    )
    standard_coverage_scope: int | None = Field(
        default=None, description="스코프('2022 개정' × '고등학교') 성취기준 총수."
    )


async def get_target_progress(
    session: AsyncSession,
    user_id: uuid.UUID,
    *,
    as_of: date | None = None,
) -> TargetProgress:
    """학생 1인의 목표 진행 상황 조립 — 프로필 부재도 예외 없이 빈 값 반환.

    호출 순서(테스트 가시성을 위해 고정): ① `session.get(UserProfile, user_id)` ② (school_type이
    있을 때만) 스코프 SELECT ③ (스코프가 0보다 클 때만) 관측 SELECT. ORM select만 사용(원시 SQL 0).
    """
    resolved_as_of = as_of if as_of is not None else datetime.now(UTC).date()

    profile = await session.get(UserProfile, user_id)
    if profile is None:
        return TargetProgress()

    days_until_exam: int | None = None
    if profile.target_exam_date is not None:
        days_until_exam = (profile.target_exam_date - resolved_as_of).days

    coverage_percent: float | None = None
    coverage_observed: int | None = None
    coverage_scope: int | None = None

    if profile.school_type is not None:
        scope_stmt = select(AchievementStandard.norm_id).where(
            AchievementStandard.curriculum_revision == _SCOPE_CURRICULUM_REVISION,
            AchievementStandard.school_type == _SCOPE_SCHOOL_TYPE,
        )
        scope_norm_ids = [row[0] for row in (await session.execute(scope_stmt)).all()]
        coverage_scope = len(scope_norm_ids)

        if coverage_scope > 0:
            observed_stmt = (
                select(ConceptStandardLink.norm_id)
                .distinct()
                .join(Concept, Concept.code == ConceptStandardLink.concept_code)
                .where(
                    ConceptStandardLink.norm_id.in_(scope_norm_ids),
                    Concept.concept_id.in_(
                        select(ConceptMasteryHistory.concept_id).where(
                            ConceptMasteryHistory.user_id == user_id
                        )
                    ),
                )
            )
            observed_rows = (await session.execute(observed_stmt)).all()
            coverage_observed = len(observed_rows)
            coverage_percent = coverage_observed / coverage_scope * 100.0
        else:
            # 스코프 0건 — 0으로 나누기 회피이자 "스코프 없음"과 "0% 커버"를 구분(정직 표기).
            coverage_observed = 0
            coverage_percent = None

    return TargetProgress(
        target_exam_date=profile.target_exam_date,
        days_until_exam=days_until_exam,
        target_grade=profile.target_grade,
        target_score=profile.target_score,
        standard_coverage_percent=coverage_percent,
        standard_coverage_observed=coverage_observed,
        standard_coverage_scope=coverage_scope,
    )


__all__ = ["TargetProgress", "get_target_progress"]
