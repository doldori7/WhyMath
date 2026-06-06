"""L4 메타인지 코칭 트리거 단위테스트 (hermetic·순수 결정).

L2 두 신호(BKT 숙달·IRT θ)+계산오류 신호에서 코칭 포커스 6종을 결정론적으로 검증한다.
"""

from __future__ import annotations

from whymath_backend.l4.metacognitive_trigger import (
    CoachingTrigger,
    focus_to_socratic_category,
    recommend_coaching,
)
from whymath_backend.l4.socratic.categories import SocraticCategory


class TestRecommendCoaching:
    def test_arithmetic_error_routes_verify(self) -> None:
        """계산 오류 감지 → verify(검산), 다른 신호와 무관."""
        trig = recommend_coaching(0.9, 2.0, arithmetic_error=True)
        assert trig.focus == "verify"
        assert trig.socratic_category == SocraticCategory.EVIDENCE
        assert trig.rationale and trig.prompt

    def test_arithmetic_error_priority_over_missing(self) -> None:
        """신호가 없어도(둘 다 None) 계산 오류면 diagnose 아닌 verify(즉시 코칭)."""
        assert recommend_coaching(None, None, arithmetic_error=True).focus == "verify"

    def test_arithmetic_error_priority_over_mastery_focus(self) -> None:
        """저숙달이라도 계산 오류 신호면 foundation 아닌 verify(슬립 우선)."""
        assert recommend_coaching(0.1, -2.0, arithmetic_error=True).focus == "verify"

    def test_no_arithmetic_error_default_unchanged(self) -> None:
        """arithmetic_error 기본 False → 기존 mastery 기반 동작 불변."""
        assert recommend_coaching(0.9, 2.0).focus == "advance"
        assert recommend_coaching(0.9, 2.0, arithmetic_error=False).focus == "advance"

    def test_verify_steps_uses_step_self_check_prompt(self) -> None:
        """verify_steps=True(다단계 대수 슬립) → verify·단계 자가검산 prompt·EVIDENCE 유지."""
        trig = recommend_coaching(0.9, 2.0, arithmetic_error=True, verify_steps=True)
        assert trig.focus == "verify"
        assert trig.socratic_category == SocraticCategory.EVIDENCE  # 카테고리 불변
        assert "한 줄씩" in trig.prompt  # 단계 자가검산 변형 발화

    def test_verify_steps_default_keeps_generic_prompt(self) -> None:
        """verify_steps 기본 False → 기존 계산 검산 prompt(backward-compat·위치 비변형)."""
        generic = recommend_coaching(0.9, 2.0, arithmetic_error=True)
        assert generic.focus == "verify"
        assert "숫자가 어긋났는지" in generic.prompt and "한 줄씩" not in generic.prompt
        # 명시 False도 동일(기존 verify 테스트와 동치).
        assert recommend_coaching(0.9, 2.0, arithmetic_error=True, verify_steps=False) == generic

    def test_verify_steps_ignored_without_arithmetic_error(self) -> None:
        """arithmetic_error 없으면 verify 분기 미진입 → verify_steps 무효(mastery 경로)."""
        assert recommend_coaching(0.9, 2.0, verify_steps=True).focus == "advance"

    def test_missing_signal_diagnose(self) -> None:
        """한쪽 신호라도 없으면 diagnose(교차검증 불가)."""
        assert recommend_coaching(None, 1.0).focus == "diagnose"
        assert recommend_coaching(0.5, None).focus == "diagnose"
        assert recommend_coaching(None, None).focus == "diagnose"

    def test_irt_higher_consolidate(self) -> None:
        """맞히나(θ=4·프록시≈0.98) 숙달 낮음(0.1) → consolidate."""
        trig = recommend_coaching(0.1, 4.0)
        assert trig.focus == "consolidate"

    def test_bkt_higher_retrieval(self) -> None:
        """숙달 높(0.9)으나 능력 낮음(θ=-4·프록시≈0.02) → retrieval."""
        assert recommend_coaching(0.9, -4.0).focus == "retrieval"

    def test_agree_low_foundation(self) -> None:
        """합의(θ=0·프록시 0.5 = BKT 0.5)·수준<0.6 → foundation."""
        assert recommend_coaching(0.5, 0.0).focus == "foundation"

    def test_agree_high_advance(self) -> None:
        """합의(BKT 0.9·θ=2 프록시≈0.88)·수준≥0.6 → advance."""
        assert recommend_coaching(0.9, 2.0).focus == "advance"

    def test_threshold_boundary_advance(self) -> None:
        """수준이 정확히 임계(0.6)면 advance(>= 분기)."""
        # BKT=0.6·θ=0(프록시 0.5) 차 0.1≤tol → 합의·평균 0.55<0.6 → foundation
        assert recommend_coaching(0.6, 0.0).focus == "foundation"
        # BKT=0.7·θ=0(프록시 0.5) 차 -0.2 = -tol(엄격 < 아님) → 합의·평균 0.6≥0.6 → advance
        assert recommend_coaching(0.7, 0.0).focus == "advance"

    def test_custom_tolerance(self) -> None:
        """discrepancy_tol을 키우면 같은 차이도 합의로 분류."""
        # 차 0.382(프록시 0.882 - 0.5) — 기본 tol 0.2면 consolidate
        assert recommend_coaching(0.5, 2.0).focus == "consolidate"
        # tol 0.5면 합의 → 평균 0.69 ≥ 0.6 → advance
        assert recommend_coaching(0.5, 2.0, discrepancy_tol=0.5).focus == "advance"

    def test_returns_rationale_and_prompt(self) -> None:
        """결정엔 근거·학생 발화가 채워지고 frozen."""
        trig = recommend_coaching(0.1, 4.0)
        assert isinstance(trig, CoachingTrigger)
        assert trig.rationale
        assert trig.prompt
        # frozen
        try:
            trig.focus = "advance"  # type: ignore[misc]
        except Exception as exc:  # pydantic ValidationError(frozen)
            assert "frozen" in str(exc).lower() or "instance" in str(exc).lower()
        else:  # pragma: no cover
            raise AssertionError("frozen 모델이 변경을 허용함")

    def test_deterministic(self) -> None:
        assert recommend_coaching(0.3, 1.0) == recommend_coaching(0.3, 1.0)

    def test_includes_socratic_category(self) -> None:
        """결정에 대화 진입 소크라테스 카테고리가 포함(focus 매핑 일치)."""
        # consolidate(맞히나 숙달↓) → EVIDENCE(근거·추측 검증)
        trig = recommend_coaching(0.1, 4.0)
        assert trig.focus == "consolidate"
        assert trig.socratic_category == SocraticCategory.EVIDENCE


class TestFocusToSocraticCategory:
    def test_all_focus_mapped(self) -> None:
        assert focus_to_socratic_category("verify") == SocraticCategory.EVIDENCE
        assert focus_to_socratic_category("consolidate") == SocraticCategory.EVIDENCE
        assert focus_to_socratic_category("retrieval") == SocraticCategory.META
        assert (
            focus_to_socratic_category("foundation") == SocraticCategory.CLARIFICATION
        )
        assert focus_to_socratic_category("advance") == SocraticCategory.PERSPECTIVE
        assert focus_to_socratic_category("diagnose") == SocraticCategory.CLARIFICATION
