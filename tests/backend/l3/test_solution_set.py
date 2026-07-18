"""`l3/solution_set.py` 단위테스트 — 등호 방정식의 해집합 보존 동치 판정(S3-02·hermetic).

`as_single_equation`(등식 구조 감지)·`equation_solution_set`(단일 등식의 실수 해집합)·
`solution_set_status`(before→after 해집합 보존 4상태)를 검증한다. 순수·결정론·DB 0.

정직성 계약(거짓 incorrect 0): 다변수·비다항·복소·미정·파싱 불가는 항상 undecidable(None)로
떨어져야 하며, 항등 방정식(∅/ℝ 모호)이 오판되지 않아야 한다.
"""

from __future__ import annotations

from whymath_backend.l3.solution_set import (
    EquationSolset,
    as_single_equation,
    equation_solution_set,
    solution_set_status,
)
from whymath_backend.l3.symbolic_equivalence import IdentityVerdict


class TestAsSingleEquation:
    """단일 등식 감지 — 정확히 하나의 `=`일 때만 (lhs, rhs)."""

    def test_single_equation_split(self) -> None:
        assert as_single_equation("2x+3=7") == ("2x+3", "7")

    def test_no_equals_is_none(self) -> None:
        # 등호 없는 표현식 → None(표현식 경로로 감).
        assert as_single_equation("2x+3") is None

    def test_chained_equality_is_none(self) -> None:
        # 연쇄 등식(a=b=c)은 단일 방정식이 아님 → None(보수적).
        assert as_single_equation("2x+3=7=x") is None

    def test_comparison_operator_is_none(self) -> None:
        # 비교/부등 연산 혼입 → 등식 아님 → None(ValueError 흡수).
        assert as_single_equation("x<=2") is None
        assert as_single_equation("x==2") is None

    def test_empty_side_is_none(self) -> None:
        # 빈 항(`2x=`) → None(보수적).
        assert as_single_equation("2x=") is None


class TestEquationSolsetFinite:
    """유한 실근 해집합 — 단변수 다항 방정식."""

    def test_linear_single_root(self) -> None:
        solset = equation_solution_set("2x+3", "7")
        assert solset is not None
        assert solset.all_reals is False
        assert len(solset.values) == 1

    def test_quadratic_two_roots(self) -> None:
        solset = equation_solution_set("x^2", "4")
        assert solset is not None
        assert solset.all_reals is False
        assert len(solset.values) == 2  # {-2, 2}

    def test_unicode_superscript_parses(self) -> None:
        # to_sympy_source 정규화로 위첨자(x²)도 파싱 → {-2, 2}.
        solset = equation_solution_set("x²", "4")
        assert solset is not None
        assert len(solset.values) == 2

    def test_rational_coefficient(self) -> None:
        solset = equation_solution_set("x/2", "3")
        assert solset is not None
        assert len(solset.values) == 1  # {6}


class TestEquationSolsetSpecialSets:
    """모든 실수(ℝ)·해 없음(∅)·판정 불가(None) 특수 해집합."""

    def test_identity_no_vars_is_all_reals(self) -> None:
        # 무변수 참 등식(2+3=5) → 모든 실수.
        solset = equation_solution_set("2+3", "5")
        assert solset == EquationSolset(all_reals=True, values=frozenset())

    def test_false_numeric_is_empty(self) -> None:
        # 무변수 거짓 등식(2+3=6) → 해 없음(∅).
        solset = equation_solution_set("2+3", "6")
        assert solset == EquationSolset(all_reals=False, values=frozenset())

    def test_identity_equation_with_variable_is_all_reals(self) -> None:
        # (x+1)^2 = x^2+2x+1 — 변수가 살아있지만 항등식(모든 실수). solve의 ∅/ℝ 모호성 방어 확인.
        solset = equation_solution_set("(x+1)^2", "x^2+2*x+1")
        assert solset is not None
        assert solset.all_reals is True

    def test_contradiction_with_variable_is_empty(self) -> None:
        # x = x+1 — diff가 상수 -1(무변수로 환원)·거짓 → 해 없음(∅).
        solset = equation_solution_set("x", "x+1")
        assert solset == EquationSolset(all_reals=False, values=frozenset())

    def test_multivariable_is_none(self) -> None:
        # x+y=2 — 다변수는 단변수 해집합 개념 성립 안 함 → None(정직).
        assert equation_solution_set("x+y", "2") is None

    def test_complex_roots_is_none(self) -> None:
        # x^2 = -1 — 실근 없음(복소근)·_common_solution이 None → 판정 불가(정직·거짓 아님).
        assert equation_solution_set("x^2", "-1") is None

    def test_parse_error_is_none(self) -> None:
        # 파싱 불가 → None(보수적).
        assert equation_solution_set("2 +* 3", "5") is None


class TestSolutionSetStatus:
    """before→after 해집합 보존 4상태 판정."""

    def test_preserving_step_is_identity(self) -> None:
        # 2x+3=7 → 2x=4 : 둘 다 해집합 {2} → 보존.
        assert solution_set_status(("2x+3", "7"), ("2x", "4")) is IdentityVerdict.identity

    def test_final_step_is_identity(self) -> None:
        # 2x=4 → x=2 : 둘 다 {2} → 보존.
        assert solution_set_status(("2x", "4"), ("x", "2")) is IdentityVerdict.identity

    def test_changed_solution_is_not_identity(self) -> None:
        # 2x=6 → 2x=8 : {3} vs {4} → 비보존.
        assert solution_set_status(("2x", "6"), ("2x", "8")) is IdentityVerdict.not_identity

    def test_root_added_is_not_identity(self) -> None:
        # x=2 → x^2=2x : {2} vs {0,2}(양변에 x 곱 → 근 추가) → 비보존.
        assert solution_set_status(("x", "2"), ("x^2", "2*x")) is IdentityVerdict.not_identity

    def test_multivariable_is_undecidable(self) -> None:
        # 다변수는 판정 불가(정직) — 실제 보존이어도 correct/incorrect로 위장하지 않는다.
        assert solution_set_status(("x+y", "2"), ("y", "2-x")) is IdentityVerdict.undecidable

    def test_both_empty_is_identity(self) -> None:
        # 해 없음(∅) → 해 없음(∅) : 보존(둘 다 모순이지만 해집합 동일).
        assert solution_set_status(("x", "x+1"), ("2", "3")) is IdentityVerdict.identity

    def test_all_reals_vs_finite_is_not_identity(self) -> None:
        # ℝ vs 유한 → 비보존.
        assert solution_set_status(("2+3", "5"), ("x", "2")) is IdentityVerdict.not_identity

    def test_undecidable_side_is_undecidable(self) -> None:
        # 한쪽이 복소근(판정 불가)이면 undecidable(정직).
        assert solution_set_status(("x^2", "-1"), ("x", "1")) is IdentityVerdict.undecidable
