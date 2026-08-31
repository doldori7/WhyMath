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
`standard_coverage_*` 필드를 전부 None으로 정직하게 비운다(0%로 위장하지 않음).

────────────────────────────────────────────────────────────────────────────
CUR-04 — 관측 조인 축을 원자 축으로 전환 (구 축은 구조적으로 0행)
────────────────────────────────────────────────────────────────────────────
관측(`coverage_observed`) 조인은 과거 `concept_standard_link.concept_code == concept.code`
(구 437 code 공간)를 썼으나, S2-03(문항↔개념 원자 재연결) 이후 이 학생의 관측 개념
(`ConceptMasteryHistory.concept_id`)은 **원자 백본 행**을 가리킨다. 원자 행은 `concept.source_id`를
설정하지 않는다(`l1/atom_graph/atom_backend_concept.py::upsert` — `code`·`name_ko`·`level`·
`intrinsic_difficulty`만 SET). `concept_standard_link` 로더(`l1/standards/standard_loader.py::
ConceptStandardLinkStore._load_source_id_to_code`)는 `concept.source_id IS NOT NULL`인 행만
`{source_id: code}` 맵에 넣으므로, 원자 행의 `code`는 그 맵에 **절대** 나타날 수 없다 — 즉
`concept_standard_link.concept_code`는 구조적으로 legacy(구 437) code만 담을 수 있다
(`docs/handoff/atom_backbone_next_session.md:19`가 이미 이 사실을 기록: "atom concept source_id
미설정 → concept_standard_link 해석은 orphan skip"). `concept.code`는 `UNIQUE`라 legacy code와
원자 code는 겹칠 수 없는 별개 공간이다. 따라서 구 축 조인은 원자 축 개념에 대해 **항상 0행**을
낸다 — CUR-04 acceptance①이 이 구조적 증거로 주장을 확인했다(라이브 DB 부재로 정적 근거 채택).

새 조인은 `api/gating.py::_fetch_achievement_codes`(원자 축 단일 IN 쿼리·N+1 0·배열 평탄화)와
`harness/standard_attainment_report.py`(`Concept.code → AtomNode.code → AtomNode.standard_codes`)의
패턴을 재사용한다. `atom_node.standard_codes`는 NCIC 고시코드 배열(`official_code`와 동일 형식)이라
스코프 매칭을 위해 `achievement_standard`에서 `(norm_id, official_code)`를 함께 읽어 역인덱싱한다
(`official_code`는 개정 간 비유일이라 이 역인덱스가 없으면 스코프 밖 개정과 혼동될 수 있다).

**작동 신호**(CLAUDE.md "작동한 비율" 원칙 — 침묵 실패 금지): `standard_coverage_measured_concepts`
(측정 이력이 있어 원자 축 조인을 시도한 개념 수)와 `standard_coverage_matched_concepts`(그중 원자
축에 실제로 매핑된 개념 수)를 함께 반환한다. `measured>0`인데 `matched==0`이면 "미도달"이 아니라
"조인 실패"라는 뜻이다 — 두 값이 응답에 없으면 0%가 둘 중 무엇인지 학생도 운영자도 구분할 수
없다(D4 문제의 재발 방지). 신규 쿼리 0(기존 스코프·관측 2쿼리 구조 그대로 재사용).
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, date, datetime

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from whymath_backend.db.models.achievement_standard import AchievementStandard
from whymath_backend.db.models.assessment import ConceptMasteryHistory
from whymath_backend.db.models.user import UserProfile
from whymath_backend.l1.standards.alignment_query import (
    AlignmentAxis,
    get_alignments,
    log_join_stats,
)

_logger = logging.getLogger(__name__)

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
    standard_coverage_measured_concepts: int | None = Field(
        default=None,
        description=(
            "측정 이력(개념 숙달 이력 1건 이상)이 있어 원자 축 조인을 시도한 개념 수"
            "(작동 신호 분모 — CUR-04). 스코프 계산 불가 시 null."
        ),
    )
    standard_coverage_matched_concepts: int | None = Field(
        default=None,
        description=(
            "측정 이력이 있는 개념 중 원자 축(atom_node)에 실제로 매핑된 개념 수"
            "(작동 신호 분자 — CUR-04). 이 값이 measured_concepts보다 작으면 그 차이만큼 원자 축"
            " 조인이 실패한 개념이 있다는 뜻이다 — 0%가 '미도달'인지 '조인 실패'인지 이 두 필드로"
            " 구분한다(CLAUDE.md '작동한 비율' 원칙). 스코프 계산 불가 시 null."
        ),
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

    **CUR-04**: 관측 SELECT(③)는 원자 축(`Concept.code == AtomNode.code` → `AtomNode.
    standard_codes`)으로 조인한다(모듈 docstring "구 축은 구조적으로 0행" 참조) — 구 축
    (`concept_standard_link`)은 더 이상 조회하지 않는다. 쿼리 수는 그대로 최대 2회(N+1 0 유지).
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
    coverage_measured_concepts: int | None = None
    coverage_matched_concepts: int | None = None

    if profile.school_type is not None:
        # (norm_id, official_code) 함께 조회 — official_code는 개정 간 비유일이라, 원자 축이 주는
        # official_code를 스코프의 norm_id로 되돌리려면 이 역인덱스가 필요하다(모듈 docstring).
        scope_stmt = select(AchievementStandard.norm_id, AchievementStandard.official_code).where(
            AchievementStandard.curriculum_revision == _SCOPE_CURRICULUM_REVISION,
            AchievementStandard.school_type == _SCOPE_SCHOOL_TYPE,
        )
        scope_rows = (await session.execute(scope_stmt)).all()
        coverage_scope = len(scope_rows)

        if coverage_scope > 0:
            norm_ids_by_official_code: dict[str, set[str]] = {}
            for norm_id, official_code in scope_rows:
                norm_ids_by_official_code.setdefault(official_code, set()).add(norm_id)

            # 원자 축 조인(CUR-04) — **CUR-12 통합 경유**: 조인을 여기서 다시 쓰지 않고
            # `l1/standards/alignment_query.get_alignments`를 축 1개(ATOM_NODE)로 부른다.
            # concept_ids에 **서브쿼리를 그대로** 넘겨 쿼리 수 불변(최대 2회·N+1 0)을 지킨다.
            # 그 축은 LEFT OUTER JOIN이라 원자 축 미매핑 개념도 probed로 남는다(matched 계수용).
            alignment = await get_alignments(
                session,
                concept_ids=select(ConceptMasteryHistory.concept_id).where(
                    ConceptMasteryHistory.user_id == user_id
                ),
                axes={AlignmentAxis.ATOM_NODE},
            )

            # 작동 신호(모듈 docstring) — measured(조인 시도 대상) vs matched(원자 축 히트).
            coverage_measured_concepts = alignment.stats.probed
            coverage_matched_concepts = alignment.stats.matched

            observed_norm_ids: set[str] = set()
            for code in alignment.standard_refs():
                observed_norm_ids.update(norm_ids_by_official_code.get(code, ()))
            coverage_observed = len(observed_norm_ids)
            coverage_percent = coverage_observed / coverage_scope * 100.0

            _logger.debug(
                "target_progress 원자 축 조인 작동 신호: user_id=%s measured_concepts=%d "
                "matched_concepts=%d scope=%d observed=%d",
                user_id,
                coverage_measured_concepts,
                coverage_matched_concepts,
                coverage_scope,
                coverage_observed,
            )
            # 전건 미매칭 경고는 통합 함수가 낸다(`log_join_stats` — probed>0·matched==0이면
            # warning 승격). 여기서 다시 쓰지 않는다: 같은 판정을 두 곳에 두면 갈라진다.
            log_join_stats(
                alignment.stats,
                logger=_logger,
                context=f"target_progress/user={user_id}",
            )
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
        standard_coverage_measured_concepts=coverage_measured_concepts,
        standard_coverage_matched_concepts=coverage_matched_concepts,
    )


__all__ = ["TargetProgress", "get_target_progress"]
