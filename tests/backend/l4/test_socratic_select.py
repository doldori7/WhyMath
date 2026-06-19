"""Polya 단계 × 전이 → 소크라테스 카테고리 선택 단위테스트.

스펙 L82-87 PRD 정렬표 + L65-70 본문 정합 검증.
"""

from __future__ import annotations

import pytest

from whymath_backend.l4.misconception.hypothesis import MisconceptionHypothesis
from whymath_backend.l4.models import PolyaStage, StageTransition
from whymath_backend.l4.socratic import SocraticCategory, select_category


def _hyp(confidence: float, turns_since_evidence: int) -> MisconceptionHypothesis:
    """테스트용 활성 가설 1건 — confidence·증거 경과 턴만 지정(나머지 기본)."""
    return MisconceptionHypothesis(
        misconception_id="MC-가정오류",
        confidence=confidence,
        turns_since_evidence=turns_since_evidence,
        evidence_count=1,
    )


class TestStageDefaultsOnStay:
    """stay 전이 + 발화 신호 없음 → 단계 기본 카테고리."""

    @pytest.mark.parametrize(
        ("stage", "expected"),
        [
            (PolyaStage.UNDERSTAND, SocraticCategory.CLARIFICATION),
            (PolyaStage.PLAN, SocraticCategory.PERSPECTIVE),
            (PolyaStage.EXECUTE, SocraticCategory.IMPLICATION),
            (PolyaStage.REVIEW, SocraticCategory.META),
        ],
    )
    def test_default_per_stage(self, stage: PolyaStage, expected: SocraticCategory) -> None:
        assert select_category(stage, "stay", "음") == expected


class TestNextAdvancesToNewStageDefault:
    """next 전이 → 다음 단계의 기본 카테고리(단계 진입 발화)."""

    @pytest.mark.parametrize(
        ("from_stage", "expected"),
        [
            # UNDERSTAND→PLAN 진입 = PERSPECTIVE("관점 선택" 마디, 스펙 L84)
            (PolyaStage.UNDERSTAND, SocraticCategory.PERSPECTIVE),
            # PLAN→EXECUTE 진입 = IMPLICATION
            (PolyaStage.PLAN, SocraticCategory.IMPLICATION),
            # EXECUTE→REVIEW 진입 = META
            (PolyaStage.EXECUTE, SocraticCategory.META),
            # REVIEW는 종착 → next도 REVIEW 기본(META)
            (PolyaStage.REVIEW, SocraticCategory.META),
        ],
    )
    def test_next_picks_target_stage_default(
        self, from_stage: PolyaStage, expected: SocraticCategory
    ) -> None:
        assert select_category(from_stage, "next", "함수 최댓값") == expected


class TestInputSignalOverridesOnStay:
    """학생 발화 신호 → 단계 기본보다 우선(stay 한정)."""

    def test_evidence_keyword_overrides(self) -> None:
        # "왜·이유·근거"는 단계 무관 EVIDENCE
        for stage in PolyaStage:
            assert (
                select_category(stage, "stay", "왜 이렇게 되는 건지 모르겠어")
                == SocraticCategory.EVIDENCE
            )
            assert select_category(stage, "stay", "근거가 뭐지") == SocraticCategory.EVIDENCE

    def test_assumption_keyword_overrides(self) -> None:
        # "가정·라고 치"는 단계 무관 ASSUMPTION
        for stage in PolyaStage:
            assert (
                select_category(stage, "stay", "이건 양수라고 가정했어")
                == SocraticCategory.ASSUMPTION
            )
            assert (
                select_category(stage, "stay", "f가 연속이라고 치자") == SocraticCategory.ASSUMPTION
            )

    def test_assumption_precedes_evidence(self) -> None:
        # 둘 다 있으면 가장 구체적 신호(가정 탐색) 우선 — 매핑 순서 보장.
        text = "왜 가정을 그렇게 두는 거야"
        assert select_category(PolyaStage.PLAN, "stay", text) == SocraticCategory.ASSUMPTION


class TestSignalsIgnoredOnNext:
    """next 전이는 발화 신호 무시 — 단계 *진입* 발화는 새 단계 기본 카테고리."""

    def test_evidence_keyword_ignored_on_next(self) -> None:
        # next라 발화에 "왜" 있어도 다음 단계 기본 사용
        assert (
            select_category(PolyaStage.UNDERSTAND, "next", "왜 모르겠어")
            == SocraticCategory.PERSPECTIVE
        )


class TestPreviousTreatedLikeStay:
    """previous 전이는 stay와 동일한 우선순위(현 단계 기본 + 발화 신호 오버라이드)."""

    def test_previous_uses_current_stage_default(self) -> None:
        t: StageTransition = "previous"
        assert select_category(PolyaStage.PLAN, t, "") == SocraticCategory.PERSPECTIVE

    def test_previous_respects_signal(self) -> None:
        t: StageTransition = "previous"
        assert select_category(PolyaStage.PLAN, t, "왜 모르겠어") == SocraticCategory.EVIDENCE


class TestActiveHypothesisOverridesOnStay:
    """stay/previous + 명시 신호 없음 + 고신뢰·최근 활성 가설 → ASSUMPTION(가정 표면화)."""

    def test_high_confidence_recent_overrides_to_assumption(self) -> None:
        # 단계 기본(PLAN=PERSPECTIVE)이나 고신뢰·최근 가설 → ASSUMPTION 오버라이드.
        h = [_hyp(0.8, 0)]
        assert select_category(PolyaStage.PLAN, "stay", "음", h) == SocraticCategory.ASSUMPTION

    def test_override_applies_across_all_stages(self) -> None:
        # 단계 무관 — 어떤 단계 기본이든 고신뢰·최근 가설이면 ASSUMPTION으로.
        h = [_hyp(0.8, 0)]
        for stage in PolyaStage:
            assert select_category(stage, "stay", "음", h) == SocraticCategory.ASSUMPTION

    def test_explicit_signal_takes_priority_over_hypothesis(self) -> None:
        # 학생이 "왜"라고 직접 물으면 가설보다 EVIDENCE 우선(명시 신호 최우선).
        h = [_hyp(0.9, 0)]
        assert select_category(PolyaStage.PLAN, "stay", "왜 그래", h) == SocraticCategory.EVIDENCE

    def test_low_confidence_hypothesis_falls_back_to_stage_default(self) -> None:
        # 저신뢰 가설(floor 미달) → 현 동작(단계 기본) 불변.
        h = [_hyp(0.3, 0)]
        assert select_category(PolyaStage.PLAN, "stay", "음", h) == SocraticCategory.PERSPECTIVE

    def test_next_transition_ignores_hypothesis(self) -> None:
        # next 진입 발화는 가설 무시 — 단계 골격 보존(오버라이드 없음).
        h = [_hyp(0.95, 0)]
        out = select_category(PolyaStage.UNDERSTAND, "next", "음", h)
        assert out == SocraticCategory.PERSPECTIVE

    def test_empty_and_none_hypotheses_keep_current_behavior(self) -> None:
        # 빈/None 가설 → 현 동작 완전 불변(하위호환·맞은 학생 영향 0).
        assert select_category(PolyaStage.PLAN, "stay", "음", []) == SocraticCategory.PERSPECTIVE
        assert select_category(PolyaStage.PLAN, "stay", "음", None) == SocraticCategory.PERSPECTIVE

    def test_previous_transition_also_overrides(self) -> None:
        # previous도 stay와 동일 취급 — 고신뢰·최근 가설이면 ASSUMPTION.
        t: StageTransition = "previous"
        h = [_hyp(0.8, 0)]
        assert select_category(PolyaStage.PLAN, t, "음", h) == SocraticCategory.ASSUMPTION


class TestHypothesisThresholdBoundaries:
    """floor/recency 경계 — confidence ge floor·turns le limit(pedagogy-designer 핀)."""

    def test_confidence_at_floor_overrides(self) -> None:
        h = [_hyp(0.65, 0)]  # 정확히 floor — ge라 통과.
        assert select_category(PolyaStage.PLAN, "stay", "음", h) == SocraticCategory.ASSUMPTION

    def test_confidence_just_below_floor_falls_back(self) -> None:
        h = [_hyp(0.64, 0)]  # floor 미달 — 단계 기본.
        assert select_category(PolyaStage.PLAN, "stay", "음", h) == SocraticCategory.PERSPECTIVE

    def test_recency_at_limit_overrides(self) -> None:
        h = [_hyp(0.9, 2)]  # 정확히 limit — le라 통과.
        assert select_category(PolyaStage.PLAN, "stay", "음", h) == SocraticCategory.ASSUMPTION

    def test_recency_just_over_limit_falls_back(self) -> None:
        h = [_hyp(0.9, 3)]  # stale(증거 끊김) — 단계 기본.
        assert select_category(PolyaStage.PLAN, "stay", "음", h) == SocraticCategory.PERSPECTIVE


class TestHypothesisScanSemantics:
    """선두 stale를 건너뛰고 차순위 고신뢰·최근을 찾는다(continue, not break)."""

    def test_stale_top_skipped_recent_second_overrides(self) -> None:
        # 선두 conf 0.9이나 stale(5>2) → 건너뜀; 차순위 conf 0.7·recent(0) → 통과.
        # confidence 내림차순 정렬 계약 유지(0.9 > 0.7).
        h = [_hyp(0.9, 5), _hyp(0.7, 0)]
        assert select_category(PolyaStage.PLAN, "stay", "음", h) == SocraticCategory.ASSUMPTION

    def test_high_conf_but_stale_alone_falls_back(self) -> None:
        # 고신뢰지만 stale 단독 → 단계 기본(현 동작·"지금 작동 중인 가정"만 겨냥).
        h = [_hyp(0.9, 5)]
        assert select_category(PolyaStage.PLAN, "stay", "음", h) == SocraticCategory.PERSPECTIVE

    def test_below_floor_top_breaks_scan(self) -> None:
        # 선두 conf<floor → break(이후 전부 미달 가정) → 단계 기본.
        h = [_hyp(0.5, 0)]
        assert select_category(PolyaStage.PLAN, "stay", "음", h) == SocraticCategory.PERSPECTIVE

    def test_return_is_always_category_enum(self) -> None:
        # 금기 가드: 반환은 카테고리 enum뿐 — 발화·정답·"틀렸다"·misconception_id 미노출(구조적).
        h = [_hyp(0.95, 0)]
        out = select_category(PolyaStage.EXECUTE, "stay", "음", h)
        assert isinstance(out, SocraticCategory)
