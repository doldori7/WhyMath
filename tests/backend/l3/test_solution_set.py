"""`l3/solution_set.py` 단위테스트 — 등호 방정식의 해집합 보존 동치 판정(S3-02·S3-06·hermetic).

`as_single_equation`(등식 구조 감지)·`equation_solution_set`(단일 등식의 실수 해집합)·
`solution_set_status`(before→after 해집합 보존 4상태)에 더해 S3-06 자연 표기 primitive —
`roots_enumeration_solset`(근 나열 union)·`read_equation_step`(단일/연쇄/나열 통합 해석)·
`solset_transition_status`(이질 형태 가드)를 검증한다. 순수·결정론·DB 0.

정직성 계약(거짓 incorrect 0): 다변수·비다항·복소·미정·파싱 불가는 항상 undecidable(None)로
떨어져야 하며, 항등 방정식(∅/ℝ 모호)이 오판되지 않아야 한다. S3-06 추가: 이질 형태(ℝ↔유한)
전이는 undecidable·캐럿 없는 지수/수열 의심 심볼(`x2`·`a1`)은 해집합 경로에서 판정 불가.
"""

from __future__ import annotations

from whymath_backend.l3.solution_set import (
    EquationSolset,
    as_single_equation,
    equation_solution_set,
    read_equation_step,
    roots_enumeration_solset,
    solset_transition_status,
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

    def test_all_reals_vs_finite_is_undecidable(self) -> None:
        # ℝ vs 유한 → *이질 형태*(항등 재작성 ↔ 값 선언)라 해집합 보존 전제가 성립하지 않음 →
        # undecidable(S3-06 거짓 incorrect 함정 방어 — S3-02의 not_identity에서 의도적 변경.
        # 예: `x²−4x+3=(x−1)(x−3)`(항등·ℝ) → `x=2`(축 공식 파생)는 옳은 풀이·2026-07-19 실측).
        assert solution_set_status(("2+3", "5"), ("x", "2")) is IdentityVerdict.undecidable

    def test_undecidable_side_is_undecidable(self) -> None:
        # 한쪽이 복소근(판정 불가)이면 undecidable(정직).
        assert solution_set_status(("x^2", "-1"), ("x", "1")) is IdentityVerdict.undecidable


class TestAmbiguousTrailingDigitSymbolGuard:
    """캐럿 없는 지수/수열 의심 심볼(`x2`·`a1`) — 해집합 경로 판정 불가(S3-06 ④·정직)."""

    def test_caretless_exponent_symbol_is_none(self) -> None:
        # `x2`를 미지수로 풀면(Symbol('x2')=4 → {4}) 학생 의도(x²=4 → {−2,2})와 어긋난
        # 거짓 판정이 난다 — 재작성 휴리스틱은 보류(수열 표기 충돌)·해집합은 보수 회피.
        assert equation_solution_set("x2", "4") is None

    def test_sequence_term_symbol_is_none(self) -> None:
        # 수열 항(a1)도 동일 가드 — 판정 불가(정직).
        assert equation_solution_set("a1", "4") is None

    def test_plain_symbol_still_solved(self) -> None:
        # 가드는 영문자+숫자 꼬리만 — 일반 미지수(x)는 기존대로 풀린다(회귀 방지).
        solset = equation_solution_set("x", "4")
        assert solset is not None
        assert len(solset.values) == 1


class TestSolsetTransitionStatus:
    """해집합 전이 4상태 — 이질 형태(ℝ↔유한) 가드(S3-06 거짓 incorrect 함정 방어)."""

    def test_both_none_is_undecidable(self) -> None:
        assert solset_transition_status(None, None) is IdentityVerdict.undecidable

    def test_one_none_is_undecidable(self) -> None:
        finite = EquationSolset(all_reals=False, values=frozenset({2}))
        assert solset_transition_status(finite, None) is IdentityVerdict.undecidable

    def test_all_reals_to_finite_is_undecidable(self) -> None:
        # 항등식(ℝ) → 값 선언({2}) : 이질 형태 — 해집합 보존 전제 불성립 → undecidable(정직).
        all_reals = EquationSolset(all_reals=True, values=frozenset())
        finite = EquationSolset(all_reals=False, values=frozenset({2}))
        assert solset_transition_status(all_reals, finite) is IdentityVerdict.undecidable
        # 역방향(유한 → ℝ·예: 2x=4 → 0=0 자명화)도 동일 — 참 진술을 incorrect로 오판 금지.
        assert solset_transition_status(finite, all_reals) is IdentityVerdict.undecidable

    def test_both_all_reals_is_identity(self) -> None:
        all_reals = EquationSolset(all_reals=True, values=frozenset())
        assert solset_transition_status(all_reals, all_reals) is IdentityVerdict.identity

    def test_finite_comparison_unchanged(self) -> None:
        # 동질(유한↔유한) 비교는 S3-02 그대로 — 같으면 identity·다르면 not_identity.
        a = EquationSolset(all_reals=False, values=frozenset({2}))
        b = EquationSolset(all_reals=False, values=frozenset({3}))
        assert solset_transition_status(a, a) is IdentityVerdict.identity
        assert solset_transition_status(a, b) is IdentityVerdict.not_identity


class TestRootsEnumerationSolset:
    """근 나열/선언 파서 — 같은 변수 등식 나열의 해집합 union(S3-06 ②)."""

    def test_comma_enumeration_union(self) -> None:
        solset = roots_enumeration_solset("x=2, x=3")
        assert solset is not None
        assert solset.all_reals is False
        assert len(solset.values) == 2

    def test_korean_or_enumeration_union(self) -> None:
        solset = roots_enumeration_solset("x=2 또는 x=3")
        assert solset is not None
        assert len(solset.values) == 2

    def test_unicode_minus_value(self) -> None:
        # U+2212 음수 값도 정규화 경유 — x=−2, x=2 → {−2, 2}.
        solset = roots_enumeration_solset("x=−2, x=2")
        assert solset is not None
        assert len(solset.values) == 2

    def test_duplicate_values_deduped(self) -> None:
        # 중근 선언(x=2, x=2) → {2}(union 흡수).
        solset = roots_enumeration_solset("x=2, x=2")
        assert solset is not None
        assert len(solset.values) == 1

    def test_no_separator_is_none(self) -> None:
        # 구분자 없음 — 근 나열 아님(단일 등식 경로 폴백·비파괴 감지).
        assert roots_enumeration_solset("x=2") is None

    def test_different_variables_is_none(self) -> None:
        # x=2, y=3 은 연립(AND) — union(OR) 오해석 금지.
        assert roots_enumeration_solset("x=2, y=3") is None

    def test_sequence_terms_is_none(self) -> None:
        # 수열 항 개별 선언(a1=2, a2=4 — AND)을 근 나열로 오해석 금지(S3-06 ④와 같은 근거).
        assert roots_enumeration_solset("a1=2, a2=4") is None

    def test_non_symbol_lhs_is_none(self) -> None:
        # 좌변이 순수 미지수가 아니면 근 나열 아님(보수).
        assert roots_enumeration_solset("x^2=4, x=2") is None

    def test_non_constant_rhs_is_none(self) -> None:
        # 우변에 변수(파라미터 k) — 실수 상수가 아니므로 보수 회피.
        assert roots_enumeration_solset("x=2, x=k") is None

    def test_function_call_comma_is_none(self) -> None:
        # 함수 인자 콤마(f(x, y)=3)를 근 나열로 오분리하지 않음(항이 등식 꼴이 아님 → None).
        assert roots_enumeration_solset("f(x, y)=3") is None


class TestReadEquationStep:
    """단계 텍스트 등식 형태 해석 — 단일/연쇄/나열 통합 진입점(S3-06)."""

    def test_expression_is_none(self) -> None:
        # 등호 없음 — 표현식(호출자가 identity_status 경로로).
        assert read_equation_step("2x+3") is None

    def test_comparison_is_none(self) -> None:
        # 비교/부등 혼입 — 등식 형태 아님(기존 as_single_equation 관례 동일).
        assert read_equation_step("x<=2") is None

    def test_single_equation_solset(self) -> None:
        reading = read_equation_step("2x=4")
        assert reading is not None
        assert reading.violation is None
        assert reading.solset == EquationSolset(all_reals=False, values=frozenset({2}))

    def test_chain_normalizes_to_final_binding(self) -> None:
        # x=(1+3)/2=2 : 내부 전부 참(바인딩 쌍 1개) → 최초=최종(x=2) 정규화 → {2}.
        reading = read_equation_step("x=(1+3)/2=2")
        assert reading is not None
        assert reading.violation is None
        assert reading.solset is not None
        assert len(reading.solset.values) == 1

    def test_chain_violation_detected_with_fragments(self) -> None:
        # x=(1+3)/2=3 : (1+3)/2≠3 증명 → violation에 원문 조각 쌍.
        reading = read_equation_step("x=(1+3)/2=3")
        assert reading is not None
        assert reading.violation == ("(1+3)/2", "3")
        assert reading.solset is None

    def test_chain_two_undecidable_pairs_is_unverifiable_reading(self) -> None:
        # x=y=2 : 바인딩(판정 불가) 쌍 2개 — 체인 결속 미증명 → solset None(위반 아님).
        reading = read_equation_step("x=y=2")
        assert reading is not None
        assert reading.violation is None
        assert reading.solset is None

    def test_enumeration_reading(self) -> None:
        reading = read_equation_step("x=2, x=3")
        assert reading is not None
        assert reading.violation is None
        assert reading.solset is not None
        assert len(reading.solset.values) == 2

    def test_identity_chain_reading_is_all_reals(self) -> None:
        # 전 쌍 항등(2+3=5=5) → 정규화(2+3=5) → 무변수 참 등식 = ℝ.
        reading = read_equation_step("2+3=5=5")
        assert reading is not None
        assert reading.solset == EquationSolset(all_reals=True, values=frozenset())
