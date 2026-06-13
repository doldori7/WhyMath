"""순수 `verify_step` 3상태 검증 단위테스트 — WH-1 1단계 슬라이스 2(§3.1·hermetic).

correct(심볼릭 동치)·incorrect(거짓 증명)·unverifiable(비대수 step_type·파싱 불가·빈 입력·
판정 불가)·evidence_weight·step_type 전파·결정론·`VerifyStepResult` 필드셋·convert_xor 확인.

PRM 점수·step 파싱·coach 결선은 *후속*이라 여기 없다(본 슬라이스는 도구 primitive만).
"""

from __future__ import annotations

from whymath_backend.l3.verify_step import (
    VerifyStepResult,
    VerifyStepState,
    verify_step,
)
from whymath_backend.schema.enums import StepType


class TestCorrect:
    """대수 동치 → correct(evidence_weight 1.0·reason None)."""

    def test_distributive_law_is_correct(self) -> None:
        # 2(x+1) ≡ 2x+2 — 자유변수 OK(심볼릭 동치). 기존 numeric-only 검증과 차별점.
        result = verify_step("2*(x+1)", "2*x+2")
        assert result.state == VerifyStepState.correct
        assert result.evidence_weight == 1.0
        assert result.reason is None

    def test_numeric_identity_is_correct(self) -> None:
        result = verify_step("2+3", "5")
        assert result.state == VerifyStepState.correct
        assert result.evidence_weight == 1.0

    def test_convert_xor_caret_is_power(self) -> None:
        # convert_xor=True이므로 `^`는 거듭제곱(XOR 아님): x^2 ≡ x*x.
        result = verify_step("x^2", "x*x")
        assert result.state == VerifyStepState.correct

    def test_implicit_symbolic_equivalence(self) -> None:
        # (x+1)^2 ≡ x^2+2x+1 — 전개 동치.
        result = verify_step("(x+1)^2", "x^2+2*x+1")
        assert result.state == VerifyStepState.correct


class TestIncorrect:
    """대수 거짓 증명 → incorrect(evidence_weight 1.0·reason 채워짐).

    incorrect 조건: ⓐ 차이가 *0이 아님 확정*(is_zero is False·상수 차 등) 또는 ⓑ *같은 자유변수*의
    0-아닌 다항식(예: freshman's dream (a+b)²≠a²+b²). 변수 집합이 다른 치환은 unverifiable(오판 회피).
    """

    def test_symbolic_constant_diff_is_incorrect(self) -> None:
        # 2x+1 vs 2x+3 — 차이가 상수 -2(0이 아님 확정) → 거짓 변형.
        result = verify_step("2*x+1", "2*x+3")
        assert result.state == VerifyStepState.incorrect
        assert result.evidence_weight == 1.0
        assert result.reason is not None
        assert "동치 아님" in result.reason

    def test_linear_constant_diff_is_incorrect(self) -> None:
        result = verify_step("x+1", "x+2")
        assert result.state == VerifyStepState.incorrect

    def test_numeric_false_is_incorrect(self) -> None:
        result = verify_step("2+3", "6")
        assert result.state == VerifyStepState.incorrect
        assert result.evidence_weight == 1.0

    def test_freshman_dream_is_incorrect(self) -> None:
        # (a+b)² vs a²+b² — 차이 2ab는 *같은 자유변수 {a,b}*의 0-아닌 다항식이라 항등식 아님이
        # 증명된다(a=b=1에서 4≠2). 가장 흔한 대수 오류 → incorrect(unverifiable로 약하게 넘기지 않음).
        result = verify_step("(a+b)^2", "a^2+b^2")
        assert result.state == VerifyStepState.incorrect
        assert result.evidence_weight == 1.0
        assert result.reason is not None

    def test_substitution_different_symbols_is_unverifiable(self) -> None:
        # a vs b+1 — before{a}·after{b}로 변수 집합이 달라(치환·a가 b+1로 정의됐을 수 있음) 맥락을
        # 모른다 → 거짓 incorrect를 *회피*하고 보수적 unverifiable(정확성 #1 — 올바른 단계 오판 금지).
        result = verify_step("a", "b+1")
        assert result.state == VerifyStepState.unverifiable
        assert result.evidence_weight == 0.5


class TestUnverifiableNonAlgebraic:
    """비대수 step_type → SymPy 시도 없이 unverifiable(0.5)."""

    def test_condition_interpretation_unverifiable(self) -> None:
        result = verify_step("어쩌고", "저쩌고", StepType.조건해석)
        assert result.state == VerifyStepState.unverifiable
        assert result.evidence_weight == 0.5
        assert result.reason is not None
        assert "비대수" in result.reason

    def test_case_analysis_unverifiable(self) -> None:
        result = verify_step("x>0", "x<0", StepType.케이스분류)
        assert result.state == VerifyStepState.unverifiable
        assert result.evidence_weight == 0.5

    def test_graph_sketch_unverifiable(self) -> None:
        result = verify_step("포물선", "위로 볼록", StepType.그래프스케치)
        assert result.state == VerifyStepState.unverifiable

    def test_non_algebraic_skips_sympy_even_if_equivalent(self) -> None:
        # 비대수 step_type이면 *동치여도* SymPy를 시도하지 않고 unverifiable(검증 불가 단원 정직).
        result = verify_step("2+3", "5", StepType.조건해석)
        assert result.state == VerifyStepState.unverifiable


class TestUnverifiableParsing:
    """파싱 불가·빈 입력·판정 불가 → unverifiable(correct 위장 금지·0.5)."""

    def test_sympify_exception_unverifiable(self) -> None:
        # "2 +* 3"는 SymPy가 파싱 못 해 SympifyError를 던진다 → except 경로로 unverifiable
        # (보수적·correct 위장 금지). reason은 "판정 불가/파싱 불가" 표기.
        result = verify_step("2 +* 3", "5")
        assert result.state == VerifyStepState.unverifiable
        assert result.evidence_weight == 0.5
        assert result.reason is not None
        assert "파싱 불가" in result.reason

    def test_prose_treated_as_symbol_is_unverifiable(self) -> None:
        # 한글 산문은 sympify가 *자유 심볼*로 받아(예외 아님) 차이의 is_zero가 None → unverifiable.
        result = verify_step("어쩌고저쩌고", "음음음")
        assert result.state == VerifyStepState.unverifiable
        assert result.evidence_weight == 0.5

    def test_empty_before_unverifiable(self) -> None:
        result = verify_step("", "5")
        assert result.state == VerifyStepState.unverifiable
        assert result.evidence_weight == 0.5
        assert result.reason is not None
        assert "빈 입력" in result.reason

    def test_empty_after_unverifiable(self) -> None:
        result = verify_step("5", "   ")
        assert result.state == VerifyStepState.unverifiable

    def test_both_empty_unverifiable(self) -> None:
        result = verify_step("", "")
        assert result.state == VerifyStepState.unverifiable

    def test_indeterminate_is_zero_none_unverifiable(self) -> None:
        # 판정 불가(is_zero None) 경로 — 미지 함수 차이는 simplify가 None을 낸다(거짓도 참도 아님).
        # f(x) - g(x)는 0인지 SymPy가 단정 못 함 → correct 위장 금지·unverifiable.
        result = verify_step("f(x)", "g(x)")
        assert result.state == VerifyStepState.unverifiable
        assert result.evidence_weight == 0.5
        assert result.reason is not None
        assert "판정 불가" in result.reason


class TestStepTypePropagation:
    """입력 step_type이 결과에 그대로 전파."""

    def test_step_type_propagated_on_correct(self) -> None:
        result = verify_step("2+3", "5", StepType.계산)
        assert result.state == VerifyStepState.correct
        assert result.step_type == StepType.계산

    def test_step_type_propagated_on_verify(self) -> None:
        result = verify_step("2*x+1", "2*x+3", StepType.검산)
        assert result.state == VerifyStepState.incorrect
        assert result.step_type == StepType.검산

    def test_step_type_none_default(self) -> None:
        result = verify_step("2+3", "5")
        assert result.step_type is None

    def test_step_type_propagated_on_unverifiable(self) -> None:
        result = verify_step("어쩌고", "저쩌고", StepType.조건해석)
        assert result.step_type == StepType.조건해석


class TestDeterminismAndFields:
    """결정론·필드셋·계산/검산은 대수 경로."""

    def test_deterministic_repeated_calls(self) -> None:
        first = verify_step("2*(x+1)", "2*x+2")
        second = verify_step("2*(x+1)", "2*x+2")
        assert first == second

    def test_result_field_set(self) -> None:
        result = verify_step("2+3", "5")
        assert isinstance(result, VerifyStepResult)
        # frozen·extra=forbid 모델 — 4필드 정확히.
        assert set(result.model_dump().keys()) == {
            "state",
            "step_type",
            "reason",
            "evidence_weight",
        }

    def test_calc_step_type_uses_algebraic_path(self) -> None:
        # 계산은 비대수 집합에 없으므로 SymPy 동치 경로(correct 판정 가능).
        result = verify_step("3*4", "12", StepType.계산)
        assert result.state == VerifyStepState.correct

    def test_verify_step_type_uses_algebraic_path(self) -> None:
        # 검산도 대수 경로 — 거짓이면 incorrect.
        result = verify_step("3*4", "11", StepType.검산)
        assert result.state == VerifyStepState.incorrect
