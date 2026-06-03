"""오개념 개입 결정트리·프롬프트 어셈블리 단위테스트 — doc L75-79 정본."""

from __future__ import annotations

from whymath_backend.l4.misconception import (
    CATALOG_BY_ID,
    InterventionPattern,
    MisconceptionMatch,
    select_intervention,
)


def _match(
    confidence: float, misconception_id: str = "distribution-over-power"
) -> MisconceptionMatch:
    m = CATALOG_BY_ID[misconception_id]
    return MisconceptionMatch(misconception=m, confidence=confidence)


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
