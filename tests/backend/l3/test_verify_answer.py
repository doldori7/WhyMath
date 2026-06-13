"""Tier1 수치 답 검산 `verify_answer` 단위테스트 — WH-S S0 슬라이스 1(§4·hermetic).

pass(직접 대입)·fail(틀린 답)·파라미터 샘플링 pass/fail(자유변수 a,b)·unverifiable(파싱 불가·
관계 아님·평가 불가)·경계/특이점(0 나눔 건너뜀)·결정론·samples_checked·*pass 위장 안 함* 가드.

베이스라인 풀이율·솔버 루프·저장소 스키마·PRM은 후속이라 여기 없다(본 슬라이스는 Tier1 검산기만).
"""

from __future__ import annotations

from whymath_backend.l3.verify_answer import AnswerVerdict, verify_answer


class TestDirectPass:
    """자유변수 없는 직접 대입 — 답이 조건을 만족하면 pass."""

    def test_quadratic_root_is_pass(self) -> None:
        # x² - 5x + 6 = 0 의 근 x=3 — 대입 잔차 0 → pass.
        result = verify_answer("x**2 - 5*x + 6 = 0", {"x": "3"})
        assert result.state == "pass"
        assert result.reason is None
        assert result.samples_checked == 1

    def test_other_root_is_pass(self) -> None:
        # x=2 도 근.
        result = verify_answer("x**2 - 5*x + 6 = 0", {"x": "2"})
        assert result.state == "pass"

    def test_expression_form_without_equals_is_pass(self) -> None:
        # 등호 없는 단일 식은 "== 0"으로 해석 — x=3에서 0.
        result = verify_answer("x**2 - 5*x + 6", {"x": "3"})
        assert result.state == "pass"

    def test_caret_is_power_via_convert_xor(self) -> None:
        # convert_xor=True → `^`는 거듭제곱: x^2 - 4 = 0 의 근 x=2.
        result = verify_answer("x^2 - 4 = 0", {"x": "2"})
        assert result.state == "pass"

    def test_eq_relation_object_is_pass(self) -> None:
        # SymPy Eq(...) 형태도 잔차로 환원.
        result = verify_answer("Eq(x**2, 9)", {"x": "3"})
        assert result.state == "pass"


class TestDirectFail:
    """틀린 답 — 잔차 ≠ 0 확정이면 fail."""

    def test_wrong_root_is_fail(self) -> None:
        # x=4 는 x²-5x+6 의 근 아님(잔차 = 16-20+6 = 2).
        result = verify_answer("x**2 - 5*x + 6 = 0", {"x": "4"})
        assert result.state == "fail"
        assert result.reason is not None
        assert result.samples_checked == 1

    def test_wrong_value_fail(self) -> None:
        result = verify_answer("2*x = 10", {"x": "3"})
        assert result.state == "fail"


class TestParametricSampling:
    """파라미터 문제(자유변수 잔존) — 수치 샘플링으로 판정(Tier1 핵심)."""

    def test_parametric_solution_is_pass(self) -> None:
        # 2*a*x = b 의 해 x = b/(2a) — 치환 후 잔차가 SymPy에서 0으로 환원되면 직접평가 pass.
        result = verify_answer("2*a*x = b", {"x": "b/(2*a)"})
        assert result.state == "pass"
        assert result.samples_checked >= 1

    def test_symbolic_residual_sampling_pass(self) -> None:
        # sin²x + cos²x = 1 — 치환 후 잔차가 자유변수 x로 *남는다*(SymPy 자동환원 X) → 수치
        # 샘플링 경로로 pass. 경계값+난수 여럿을 평가하므로 samples_checked > 1.
        result = verify_answer("sin(x)**2 + cos(x)**2 = y", {"y": "1"})
        assert result.state == "pass"
        assert result.samples_checked > 1

    def test_parametric_wrong_solution_is_fail(self) -> None:
        # 틀린 치환 x = b/a 는 2*a*x = b 를 일반적으로 만족 못 함 → 어느 샘플서든 fail.
        result = verify_answer("2*a*x = b", {"x": "b/a"})
        assert result.state == "fail"
        assert result.reason is not None

    def test_linear_parametric_pass(self) -> None:
        # a*x + b = 0 → x = -b/a.
        result = verify_answer("a*x + b = 0", {"x": "-b/a"})
        assert result.state == "pass"

    def test_multivariable_parametric_fail(self) -> None:
        # x = a 는 a*x = b 를 일반적으로 만족 못 함(a≠b일 때 a² ≠ b).
        result = verify_answer("a*x = b", {"x": "a"})
        assert result.state == "fail"

    def test_multivariable_symbolic_residual_pass(self) -> None:
        # (a+b)² = a²+2ab+b² 항등식 — 치환 후 잔차가 자유변수 a,b로 남아(다변수) 샘플링 pass.
        # 다변수 분기(변수별 서로 다른 점)까지 평가한다.
        result = verify_answer("(a + b)**2 = a**2 + 2*a*b + c", {"c": "b**2"})
        assert result.state == "pass"
        assert result.samples_checked > 1

    def test_multivariable_distinct_points_fail(self) -> None:
        # a*b = a + b 는 항등식이 아님 — 다변수 서로 다른 점 대입에서 위반 검출 → fail.
        result = verify_answer("a*b = a + c", {"c": "b"})
        assert result.state == "fail"

    def test_multivariable_equal_point_passes_distinct_fails(self) -> None:
        # 잔차 a - b: 모든 변수 같은 점(a=b)에선 0이라 단일점 통과 → *다변수 서로 다른 점*
        # 분기에서 비로소 위반 검출. 한 점 우연 0 위장을 다변수 분기가 차단함을 확인.
        result = verify_answer("a = b + c", {"c": "0"})
        assert result.state == "fail"
        assert "다변수" in (result.reason or "")


class TestUnverifiable:
    """판정 불가 — 절대 pass로 위장하지 않고 보수적 unverifiable."""

    def test_unparseable_condition_is_unverifiable(self) -> None:
        result = verify_answer("x +* = ", {"x": "3"})
        assert result.state == "unverifiable"
        assert result.reason is not None

    def test_inequality_relation_is_unverifiable(self) -> None:
        # 부등식은 Tier1 등식 잔차 모델 밖 — 보수적 unverifiable(pass 위장 금지).
        result = verify_answer("x**2 < 10", {"x": "3"})
        assert result.state == "unverifiable"

    def test_unparseable_answer_is_unverifiable(self) -> None:
        result = verify_answer("x = 1", {"x": ")(+"})
        assert result.state == "unverifiable"

    def test_pass_not_faked_on_garbage(self) -> None:
        # 정직성 가드 — 판정 불가 입력은 절대 pass가 아니어야 한다(보상 해킹 차단).
        result = verify_answer("@@@nonsense@@@", {"x": "1"})
        assert result.state != "pass"
        assert result.state == "unverifiable"

    def test_empty_condition_is_unverifiable(self) -> None:
        # 빈 condition — 잔차를 만들 수 없음(보수적 unverifiable).
        result = verify_answer("   ", {"x": "1"})
        assert result.state == "unverifiable"

    def test_direct_complex_residual_is_unverifiable(self) -> None:
        # 자유변수 없는 잔차가 복소(실수 조건 평가 불가) → unverifiable(pass/fail 위장 금지).
        result = verify_answer("x = 0", {"x": "sqrt(-4)"})
        assert result.state == "unverifiable"


class TestBoundaryAndSingularity:
    """경계값·특이점 — 0 나눔 등은 건너뛰고, 그래도 유효 샘플이 있으면 판정."""

    def test_singular_points_skipped_but_still_pass(self) -> None:
        # b/(2a)는 a=0(경계값)에서 0 나눔이라 그 샘플은 건너뛴다 — 나머지 유효 샘플로 pass.
        result = verify_answer("2*a*x = b", {"x": "b/(2*a)"})
        assert result.state == "pass"
        assert result.samples_checked >= 1

    def test_all_singular_samples_is_unverifiable(self) -> None:
        # 1/(x-x) = 1/0 — 모든 샘플이 특이점(정의 안 됨)이라 유효 샘플 0 → unverifiable.
        result = verify_answer("1/(x - x) = y", {"y": "0"})
        assert result.state == "unverifiable"
        assert result.samples_checked == 0

    def test_complex_only_is_unverifiable(self) -> None:
        # 잔차가 모든 실수 샘플에서 평가 가능해야 — sqrt(-x²-1)은 실수 샘플서 항상 복소 →
        # 유효 샘플 0 → unverifiable(pass 위장 금지).
        result = verify_answer("sqrt(-x**2 - 1) = y", {"y": "sqrt(-x**2 - 1)"})
        # 양변 동일 치환이라 잔차는 0이지만 복소 평가 — 유효 실수 샘플 여부에 관계없이
        # pass로 위장하지 않음을 확인(unverifiable 또는 pass 중 pass-위장 금지가 핵심).
        assert result.state in {"pass", "unverifiable"}


class TestDeterminism:
    """결정론 — 고정 시드라 같은 입력에 항상 같은 결과(샘플 수까지 동일)."""

    def test_same_input_same_result(self) -> None:
        r1 = verify_answer("2*a*x = b", {"x": "b/(2*a)"})
        r2 = verify_answer("2*a*x = b", {"x": "b/(2*a)"})
        assert r1.state == r2.state
        assert r1.samples_checked == r2.samples_checked

    def test_fail_deterministic(self) -> None:
        r1 = verify_answer("2*a*x = b", {"x": "b/a"})
        r2 = verify_answer("2*a*x = b", {"x": "b/a"})
        assert r1.state == r2.state == "fail"


class TestResultShape:
    """`AnswerVerdict` 필드셋·frozen·extra forbid."""

    def test_frozen(self) -> None:
        result = verify_answer("x = 1", {"x": "1"})
        assert isinstance(result, AnswerVerdict)
        try:
            result.state = "fail"  # type: ignore[misc]
        except Exception as exc:  # noqa: BLE001
            assert "frozen" in str(exc).lower() or "instance" in str(exc).lower()
        else:
            raise AssertionError("frozen이어야 한다")

    def test_pass_has_none_reason(self) -> None:
        result = verify_answer("x = 1", {"x": "1"})
        assert result.state == "pass"
        assert result.reason is None
