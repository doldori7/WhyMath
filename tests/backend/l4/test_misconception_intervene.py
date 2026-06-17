"""오개념 개입 결정트리·프롬프트 어셈블리 단위테스트 — doc L75-79 정본."""

from __future__ import annotations

import random

from whymath_backend.l4.misconception import (
    CATALOG_BY_ID,
    InterventionPattern,
    MisconceptionMatch,
    select_intervention,
    select_intervention_from_hypotheses,
)
from whymath_backend.l4.misconception.hypothesis import MisconceptionHypothesis


def _match(
    confidence: float, misconception_id: str = "distribution-over-power"
) -> MisconceptionMatch:
    m = CATALOG_BY_ID[misconception_id]
    return MisconceptionMatch(misconception=m, confidence=confidence)


def _hyp(
    confidence: float, misconception_id: str = "distribution-over-power"
) -> MisconceptionHypothesis:
    return MisconceptionHypothesis(
        misconception_id=misconception_id,
        confidence=confidence,
        turns_since_evidence=0,
        evidence_count=1,
    )


class TestDecisionTree:
    def test_high_confidence_picks_counterexample(self) -> None:
        decision = select_intervention(_match(0.9))
        assert decision is not None
        assert decision.pattern is InterventionPattern.COUNTEREXAMPLE

    def test_mid_confidence_picks_reverse(self) -> None:
        # 0.5 ≤ conf ≤ 0.8
        for conf in (0.5, 0.65, 0.8):
            decision = select_intervention(_match(conf))
            assert decision is not None
            assert decision.pattern is InterventionPattern.REVERSE_REASONING, conf

    def test_low_confidence_holds(self) -> None:
        # < 0.5 → 진단 보류(None)
        for conf in (0.0, 0.3, 0.49):
            assert select_intervention(_match(conf)) is None, conf

    def test_boundary_just_above_high(self) -> None:
        # 0.8은 mid(reverse), 0.81은 high(counter)
        assert select_intervention(_match(0.8)).pattern is InterventionPattern.REVERSE_REASONING  # type: ignore[union-attr]
        assert select_intervention(_match(0.81)).pattern is InterventionPattern.COUNTEREXAMPLE  # type: ignore[union-attr]


class TestPromptAssembly:
    def test_counterexample_contains_assumption_and_case(self) -> None:
        decision = select_intervention(_match(0.95, "distribution-over-power"))
        assert decision is not None
        # 학생 가정·반례 둘 다 프롬프트에 등장
        assert "(a+b)² = a² + b²" in decision.prompt
        assert "a=1, b=1" in decision.prompt
        # 자각 유도형 어미("어떻게 돼?") 확인
        assert decision.prompt.endswith("어떻게 돼?")
        assert decision.misconception_id == "distribution-over-power"

    def test_reverse_prompt_template_correct(self) -> None:
        decision = select_intervention(_match(0.6, "sign-flip-in-inequality"))
        assert decision is not None
        # 거꾸로 사고 정본 어미
        assert "거꾸로 확인" in decision.prompt


class TestInterventionFromHypotheses:
    """결선 — 활성 가설 세트 → select_focus → 카탈로그 해소 → 결정 트리(누적 신뢰도)."""

    def test_empty_set_holds(self) -> None:
        """빈 가설 세트 → None(개입 보류)."""
        assert select_intervention_from_hypotheses([]) is None

    def test_top_hypothesis_drives_decision(self) -> None:
        """rng=None → 최상위 가설(활용)의 신뢰도로 결정 트리 구동."""
        hyps = [_hyp(0.9, "distribution-over-power"), _hyp(0.6, "log-distribution")]
        decision = select_intervention_from_hypotheses(hyps)
        assert decision is not None
        assert decision.pattern is InterventionPattern.COUNTEREXAMPLE  # 0.9 > 0.8
        assert decision.misconception_id == "distribution-over-power"

    def test_accumulated_confidence_thresholds(self) -> None:
        """가설 신뢰도가 결정 트리 임계를 그대로 탄다(>0.8 반례·≥0.5 거꾸로·<0.5 보류)."""
        assert (
            select_intervention_from_hypotheses([_hyp(0.85)]).pattern  # type: ignore[union-attr]
            is InterventionPattern.COUNTEREXAMPLE
        )
        assert (
            select_intervention_from_hypotheses([_hyp(0.6)]).pattern  # type: ignore[union-attr]
            is InterventionPattern.REVERSE_REASONING
        )
        # 감쇠해 0.5 미만이 된 가설 → 보류(None·낙인 금지)
        assert select_intervention_from_hypotheses([_hyp(0.3)]) is None

    def test_prompt_assembled_from_catalog(self) -> None:
        """focus의 misconception_id를 카탈로그로 해소해 프롬프트를 어셈블한다."""
        decision = select_intervention_from_hypotheses([_hyp(0.95, "distribution-over-power")])
        assert decision is not None
        assert "(a+b)² = a² + b²" in decision.prompt
        assert "a=1, b=1" in decision.prompt

    def test_unknown_misconception_id_holds(self) -> None:
        """카탈로그에 없는 느슨 id → 어셈블 불가 → None(보류·정직)."""
        assert select_intervention_from_hypotheses([_hyp(0.9, "nonexistent-mc-xyz")]) is None

    def test_rng_none_always_exploits_top(self) -> None:
        """rng=None → 항상 최상위 가설(탐색 안 함·결정론)."""
        hyps = [_hyp(0.9, "distribution-over-power"), _hyp(0.85, "log-distribution")]
        for _ in range(5):
            det = select_intervention_from_hypotheses(hyps, rng=None)
            assert det is not None and det.misconception_id == "distribution-over-power"

    def test_epsilon_one_explores_second_hypothesis(self) -> None:
        """epsilon=1 + 시드 rng → 차순위 가설을 탐색(ε passthrough 결정론·select_focus 위임)."""
        hyps = [_hyp(0.9, "distribution-over-power"), _hyp(0.85, "log-distribution")]
        det = select_intervention_from_hypotheses(hyps, epsilon=1.0, rng=random.Random(0))
        # epsilon=1 → 항상 차순위(top 제외) 탐색 → 두 번째 가설이 focus.
        assert det is not None
        assert det.misconception_id == "log-distribution"


class TestNoForbiddenLabeling:
    """프롬프트가 *직접 교정·학생 라벨링*을 하지 않음 — doc 절대 금지 §."""

    def test_no_direct_correction_phrases(self) -> None:
        for mid in ("distribution-over-power", "log-distribution"):
            for conf in (0.9, 0.7):
                decision = select_intervention(_match(conf, mid))
                assert decision is not None
                # doc L84-86 절대 금지 §
                assert "잘못된" not in decision.prompt
                assert "흔한 오개념" not in decision.prompt
                assert "다시 풀어와" not in decision.prompt
                assert "틀렸" not in decision.prompt
