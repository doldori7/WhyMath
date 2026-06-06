"""L3→L4 오케스트레이터 단위테스트 (hermetic·순수 결정).

학생 풀이 텍스트 → L3 결정론 관계 검증(=·<·>·≤·≥·≠) → L4 검산 코칭 결선을 검증한다.
*결선 동작*(신호 유무 → arithmetic_error bool → focus)에 집중하고, 개별 검증기의 망라
검사는 `tests/backend/l3/test_pregenerate.py`가 책임진다.
"""

from __future__ import annotations

from whymath_backend.l3.pregenerate.models import PregenItem, ValidationSignal
from whymath_backend.l4.metacognitive_trigger import recommend_coaching
from whymath_backend.l4.solution_coaching import (
    SolutionCoaching,
    recommend_coaching_for_solution,
)


class _AlwaysFails:
    """SeedValidator 충족 스텁 — 입력 무관 항상 신호 반환(주입 검증용).

    kind는 "other"(비표준 검증기) — 오케스트레이터가 `signal.kind`를 그대로 error_kind로
    노출하므로, 주입 스텁의 종류가 error_kind="other"로 검증된다(slice 59).
    """

    def validate(self, item: PregenItem | None, response: str) -> ValidationSignal | None:
        return ValidationSignal(kind="other", reason="stub: always fails")


class _AlwaysPasses:
    """SeedValidator 충족 스텁 — 입력 무관 항상 통과(주입 검증용)."""

    def validate(self, item: PregenItem | None, response: str) -> ValidationSignal | None:
        return None


class TestRecommendCoachingForSolution:
    def test_arithmetic_slip_routes_verify(self) -> None:
        """거짓 등식("2 + 3 = 6") → arithmetic_error·verify·신호 노출."""
        result = recommend_coaching_for_solution("2 + 3 = 6", 0.9, 2.0)
        assert result.arithmetic_error is True
        assert result.trigger.focus == "verify"
        assert result.validation_signal is not None
        assert "arithmetic error" in result.validation_signal

    def test_inequality_slip_routes_verify(self) -> None:
        """거짓 부등식("5 < 3") → arithmetic_error·verify(검증기 패밀리 결선 확인)."""
        result = recommend_coaching_for_solution("5 < 3", 0.9, 2.0)
        assert result.arithmetic_error is True
        assert result.trigger.focus == "verify"
        assert result.validation_signal is not None
        assert "inequality error" in result.validation_signal

    def test_prose_adjacent_slip_now_detected(self) -> None:
        """slice 54 — 한글 산문에 인접한 계산 슬립도 검출(한글=산문 경계).

        slice 52에서는 `_is_standalone`이 공백 건너뛴 뒤 한글(alnum)을 만나 보수적으로
        건너뛰었으나, slice 54가 한글을 *단어 경계*로 인식해 "따라서 2 + 3 = 6 이다."
        같은 한국어 풀이의 슬립도 verify로 잡는다(한국 학생 실사용 핵심).
        """
        result = recommend_coaching_for_solution("따라서 2 + 3 = 6 이다.", 0.9, 2.0)
        assert result.arithmetic_error is True
        assert result.trigger.focus == "verify"
        assert result.validation_signal is not None
        assert "arithmetic error" in result.validation_signal

    def test_not_equal_slip_routes_verify(self) -> None:
        """거짓 부등("12 / 4 ≠ 3", 유니코드 ≠ 정규화) → arithmetic_error·verify."""
        result = recommend_coaching_for_solution("12 / 4 ≠ 3", 0.9, 2.0)
        assert result.arithmetic_error is True
        assert result.trigger.focus == "verify"
        assert result.validation_signal is not None
        assert "not-equal error" in result.validation_signal

    def test_algebra_solution_slip_routes_verify(self) -> None:
        """slice 56 — 틀린 단변수 해("2x+1=7 이므로 x=5")도 verify로 처방(대수 슬립)."""
        result = recommend_coaching_for_solution("2x + 1 = 7 이므로 x = 5", 0.9, 2.0)
        assert result.arithmetic_error is True
        assert result.trigger.focus == "verify"
        assert result.validation_signal is not None
        assert "solution error" in result.validation_signal

    def test_clean_solution_high_mastery_advance(self) -> None:
        """참 등식("3 × 4 = 12")·고숙달 → arithmetic_error 없이 BKT↔IRT 경로(advance)."""
        result = recommend_coaching_for_solution("3 × 4 = 12 이므로 끝.", 0.9, 2.0)
        assert result.arithmetic_error is False
        assert result.validation_signal is None
        assert result.trigger.focus == "advance"

    def test_clean_solution_low_mastery_foundation(self) -> None:
        """참 계산·저숙달 합의 → foundation(계산오류 없으면 기존 코칭 그대로)."""
        result = recommend_coaching_for_solution("3 × 4 = 12", 0.5, 0.0)
        assert result.arithmetic_error is False
        assert result.trigger.focus == "foundation"

    def test_empty_solution_no_false_positive(self) -> None:
        """빈 풀이 → 위생 검사 없는 검증기라 신호 0(빈 풀이는 슬립이 아님)."""
        result = recommend_coaching_for_solution("", 0.1, 4.0)
        assert result.arithmetic_error is False
        assert result.validation_signal is None
        # 계산오류 없으니 BKT↔IRT 불일치 경로(맞히나 숙달↓) = consolidate.
        assert result.trigger.focus == "consolidate"

    def test_symbolic_solution_no_false_positive(self) -> None:
        """심볼릭 등식("x + 1 = 2") → 자유변수라 판정 불가(통과)·신호 0."""
        result = recommend_coaching_for_solution("x + 1 = 2 에서 x = 1", None, None)
        assert result.arithmetic_error is False
        assert result.validation_signal is None
        # 신호 둘 다 없음 → diagnose(교차검증 불가).
        assert result.trigger.focus == "diagnose"

    def test_slip_priority_over_low_mastery(self) -> None:
        """계산오류는 저숙달보다 우선 — foundation이 아니라 verify(슬립 vs 오개념)."""
        result = recommend_coaching_for_solution("2 + 3 = 6", 0.1, -2.0)
        assert result.arithmetic_error is True
        assert result.trigger.focus == "verify"

    def test_slip_priority_over_missing_signals(self) -> None:
        """신호가 둘 다 없어도 계산오류면 diagnose 아닌 verify(즉시 코칭)."""
        result = recommend_coaching_for_solution("2 + 3 = 6", None, None)
        assert result.arithmetic_error is True
        assert result.trigger.focus == "verify"

    def test_signal_matches_l3_validator_output(self) -> None:
        """노출 신호는 L3 검증기 출력 그대로 — 사유에 구체적 거짓 관계가 담긴다."""
        result = recommend_coaching_for_solution("2 + 3 = 6", 0.9, 2.0)
        assert result.validation_signal is not None
        # 거짓 등식의 좌우항과 SymPy 판정이 사유에 포함(L5가 어디가 어긋났는지 단서로 사용).
        assert "5 != 6" in result.validation_signal

    def test_custom_validator_injection_forces_error(self) -> None:
        """주입 검증기가 사유를 내면(풀이 내용 무관) arithmetic_error·verify."""
        result = recommend_coaching_for_solution(
            "내용 무관", 0.9, 2.0, validator=_AlwaysFails()
        )
        assert result.arithmetic_error is True
        assert result.trigger.focus == "verify"
        assert result.validation_signal == "stub: always fails"

    def test_custom_validator_injection_forces_pass(self) -> None:
        """주입 검증기가 통과시키면 거짓 등식이 있어도 신호 0(주입 우선)."""
        result = recommend_coaching_for_solution(
            "2 + 3 = 6", 0.9, 2.0, validator=_AlwaysPasses()
        )
        assert result.arithmetic_error is False
        assert result.validation_signal is None
        assert result.trigger.focus == "advance"

    def test_forwards_discrepancy_tol(self) -> None:
        """discrepancy_tol을 recommend_coaching에 위임 — 같은 차이도 분류가 바뀐다."""
        # 차 0.382(프록시 0.882 - 0.5): 기본 tol 0.2면 불일치(consolidate).
        assert recommend_coaching_for_solution("끝.", 0.5, 2.0).trigger.focus == "consolidate"
        # tol 0.5면 합의 → 평균 0.69 ≥ 0.6 → advance.
        assert (
            recommend_coaching_for_solution("끝.", 0.5, 2.0, discrepancy_tol=0.5).trigger.focus
            == "advance"
        )

    def test_forwards_mastery_threshold(self) -> None:
        """mastery_threshold 위임 — 합의 시 기초/심화 임계 조정."""
        # 합의(BKT 0.5·θ=0 프록시 0.5)·평균 0.5: 기본 임계 0.6이면 foundation.
        assert recommend_coaching_for_solution("끝.", 0.5, 0.0).trigger.focus == "foundation"
        # 임계 0.4로 낮추면 0.5 ≥ 0.4 → advance.
        assert (
            recommend_coaching_for_solution("끝.", 0.5, 0.0, mastery_threshold=0.4).trigger.focus
            == "advance"
        )

    def test_orchestrator_matches_manual_wiring(self) -> None:
        """오케스트레이터 = L3 신호→bool→recommend_coaching의 *동치* (결선 정합 증명)."""
        clean = recommend_coaching_for_solution("3 × 4 = 12", 0.9, 2.0)
        assert clean.trigger == recommend_coaching(0.9, 2.0, arithmetic_error=False)
        slip = recommend_coaching_for_solution("2 + 3 = 6", 0.9, 2.0)
        assert slip.trigger == recommend_coaching(0.9, 2.0, arithmetic_error=True)

    def test_deterministic(self) -> None:
        """같은 입력 → 같은 결정(순수)."""
        a = recommend_coaching_for_solution("2 + 3 = 6", 0.3, 1.0)
        b = recommend_coaching_for_solution("2 + 3 = 6", 0.3, 1.0)
        assert a == b

    def test_result_is_frozen(self) -> None:
        """SolutionCoaching은 불변(frozen)."""
        result = recommend_coaching_for_solution("2 + 3 = 6", 0.9, 2.0)
        assert isinstance(result, SolutionCoaching)
        try:
            result.arithmetic_error = False  # type: ignore[misc]
        except Exception as exc:  # pydantic ValidationError(frozen)
            assert "frozen" in str(exc).lower() or "instance" in str(exc).lower()
        else:  # pragma: no cover
            raise AssertionError("frozen 모델이 변경을 허용함")


class TestErrorKindClassification:
    """슬립 종류 분류 — 검증기가 `ValidationSignal.kind`로 직접 선언(slice 58→59). L5/L7용."""

    def test_arithmetic_kind(self) -> None:
        assert recommend_coaching_for_solution("2 + 3 = 6", 0.9, 2.0).error_kind == "arithmetic"

    def test_inequality_kind(self) -> None:
        assert recommend_coaching_for_solution("5 < 3", 0.9, 2.0).error_kind == "inequality"

    def test_not_equal_kind(self) -> None:
        assert recommend_coaching_for_solution("12 / 4 ≠ 3", 0.9, 2.0).error_kind == "not_equal"

    def test_solution_kind(self) -> None:
        result = recommend_coaching_for_solution("2x + 1 = 7 이므로 x = 5", 0.9, 2.0)
        assert result.error_kind == "solution"

    def test_no_error_kind_none(self) -> None:
        # 오류 없음 → error_kind None(arithmetic_error False와 정합).
        result = recommend_coaching_for_solution("3 × 4 = 12", 0.9, 2.0)
        assert result.arithmetic_error is False
        assert result.error_kind is None

    def test_unknown_signal_classified_other(self) -> None:
        # 비표준 검증기(kind="other" 선언) → error_kind="other"(검증기 선언 그대로).
        result = recommend_coaching_for_solution("내용", 0.9, 2.0, validator=_AlwaysFails())
        assert result.arithmetic_error is True
        assert result.error_kind == "other"


class TestErrorSpan:
    """slice 60 — 오류 위치 span 노출(`ValidationSignal.span` → `error_span`·L5 하이라이트)."""

    def test_arithmetic_span_points_at_relation(self) -> None:
        # 한글 산문 속 거짓 관계도 span은 *관계만* 가리킨다.
        text = "따라서 2 + 3 = 6 이다"
        result = recommend_coaching_for_solution(text, 0.9, 2.0)
        assert result.error_span is not None
        s, e = result.error_span
        assert text[s:e] == "2 + 3 = 6"

    def test_solution_span_points_at_claim(self) -> None:
        # 대수 슬립은 틀린 *해 주장*("x = 5")을 가리킨다(방정식 아님).
        text = "2x + 1 = 7 이므로 x = 5"
        result = recommend_coaching_for_solution(text, 0.9, 2.0)
        assert result.error_span is not None
        s, e = result.error_span
        assert text[s:e] == "x = 5"

    def test_no_error_span_none(self) -> None:
        # 오류 없음 → error_span None(arithmetic_error False와 정합).
        result = recommend_coaching_for_solution("3 × 4 = 12", 0.9, 2.0)
        assert result.arithmetic_error is False
        assert result.error_span is None

    def test_unicode_span_none_but_kind_set(self) -> None:
        # 유니코드 ≤는 1→2 정규화라 span=None(가드)이나 error_kind는 정상(slice 59b 계승).
        result = recommend_coaching_for_solution("5 ≤ 3", 0.9, 2.0)
        assert result.error_kind == "inequality"
        assert result.error_span is None


class TestStepVerifyPrompt:
    """slice 61 — solution 슬립(다단계 대수)일 때만 verify 발화가 단계 자가검산으로 변형."""

    def test_solution_slip_uses_step_self_check(self) -> None:
        # 대수 슬립(kind="solution") → 단계 자가검산 prompt(위치 비지목).
        result = recommend_coaching_for_solution("2x + 1 = 7 이므로 x = 5", 0.9, 2.0)
        assert result.error_kind == "solution"
        assert result.trigger.focus == "verify"
        assert "한 줄씩" in result.trigger.prompt

    def test_arithmetic_slip_keeps_generic_verify(self) -> None:
        # 순수 수치 슬립(kind="arithmetic") → 기존 계산 검산 prompt(단계 변형 아님).
        result = recommend_coaching_for_solution("2 + 3 = 6", 0.9, 2.0)
        assert result.error_kind == "arithmetic"
        assert result.trigger.focus == "verify"
        assert "숫자가 어긋났는지" in result.trigger.prompt
        assert "한 줄씩" not in result.trigger.prompt

    def test_inequality_slip_keeps_generic_verify(self) -> None:
        # 부등식 슬립도 단계 변형 아님(solution kind만 변형).
        result = recommend_coaching_for_solution("5 < 3", 0.9, 2.0)
        assert result.error_kind == "inequality"
        assert "한 줄씩" not in result.trigger.prompt
