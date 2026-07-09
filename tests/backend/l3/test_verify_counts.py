"""개념형 검증 프리미티브 테스트 — 실근·극값 개수·일대일·등비급수 수렴(순수·SymPy·라이브 0).

정답 개수/판정 pass·오개념(판별식 무시·임계점=극값·역함수 오인·늘 수렴)의 틀린 답 fail·범위 밖
unverifiable을 동결한다.
"""

from __future__ import annotations

from whymath_backend.l3.verify_answer import (
    verify_extremum_count,
    verify_geometric_convergence,
    verify_is_one_to_one,
    verify_real_root_count,
)


class TestRealRootCount:
    def test_no_real_root_pass(self) -> None:
        # 판별식<0 → 실근 0개.
        assert verify_real_root_count("x**2 + x + 1 = 0", "0").state == "pass"

    def test_misconception_two_fails(self) -> None:
        # 판별식 무시("늘 2근") 오개념 — 실근 0인데 2로 답 → fail.
        assert verify_real_root_count("x**2 + x + 1 = 0", "2").state == "fail"

    def test_double_root_is_one(self) -> None:
        # 중근 → 서로 다른 실근 1개.
        assert verify_real_root_count("x**2 - 4*x + 4 = 0", "1").state == "pass"
        assert verify_real_root_count("x**2 - 4*x + 4 = 0", "2").state == "fail"

    def test_two_distinct_roots(self) -> None:
        assert verify_real_root_count("x**2 - 5*x + 6 = 0", "2").state == "pass"

    def test_non_polynomial_unverifiable(self) -> None:
        assert verify_real_root_count("2**x = 8", "1").state == "unverifiable"

    def test_non_count_claim_unverifiable(self) -> None:
        # 개수가 아닌 주장(음수·분수)은 보수적 회피.
        assert verify_real_root_count("x**2 + 1 = 0", "sqrt(2)").state == "unverifiable"


class TestExtremumCount:
    def test_cubic_perfect_cube_zero_extrema(self) -> None:
        # f(x)=x³ → f'=3x²(중근)·부호 불변 → 극값 0개.
        assert verify_extremum_count("x**3", "0").state == "pass"

    def test_misconception_critical_as_extremum_fails(self) -> None:
        # 임계점=극값 오개념 — 극값 0인데 1(임계점 수)로 답 → fail.
        assert verify_extremum_count("x**3", "1").state == "fail"
        assert verify_extremum_count("(x - 2)**3 + 5", "1").state == "fail"

    def test_cubic_two_extrema(self) -> None:
        # f(x)=x³-3x → f'=3x²-3(서로 다른 두 근·부호 변화) → 극값 2개.
        assert verify_extremum_count("x**3 - 3*x", "2").state == "pass"
        assert verify_extremum_count("x**3 - 3*x", "1").state == "fail"

    def test_shifted_perfect_cube_pass(self) -> None:
        assert verify_extremum_count("(x - 3)**3 + 1", "0").state == "pass"

    def test_equation_form_unverifiable(self) -> None:
        # 함수 식이어야 함(등식/부등식은 회피).
        assert verify_extremum_count("x**3 = 0", "0").state == "unverifiable"


class TestIsOneToOne:
    def test_parabola_not_one_to_one_pass(self) -> None:
        # 이차함수 f'=2x+b 부호 변화 → 일대일 아님(0).
        assert verify_is_one_to_one("x**2", "0").state == "pass"
        assert verify_is_one_to_one("x**2 + 3*x + 2", "0").state == "pass"

    def test_misconception_invertible_fails(self) -> None:
        # "일대일 아니어도 역함수 있다" 오개념 — 0인데 1로 답 → fail.
        assert verify_is_one_to_one("x**2", "1").state == "fail"
        assert verify_is_one_to_one("x**2 + 3*x + 2", "1").state == "fail"

    def test_monotone_cubic_is_one_to_one(self) -> None:
        # f(x)=x³ → f'=3x²(부호 불변·단조) → 일대일(1).
        assert verify_is_one_to_one("x**3", "1").state == "pass"
        assert verify_is_one_to_one("x**3", "0").state == "fail"

    def test_linear_is_one_to_one(self) -> None:
        assert verify_is_one_to_one("2*x + 1", "1").state == "pass"

    def test_non_count_claim_unverifiable(self) -> None:
        # 판정값(0/1)이 아닌 주장은 보수적 회피.
        assert verify_is_one_to_one("x**2", "2").state == "unverifiable"

    def test_multivariate_unverifiable(self) -> None:
        assert verify_is_one_to_one("x**2 + y", "0").state == "unverifiable"


class TestGeometricConvergence:
    def test_ratio_gt_one_diverges_pass(self) -> None:
        # |r|>1 → 발산(0).
        assert verify_geometric_convergence("3/2", "0").state == "pass"
        assert verify_geometric_convergence("5", "0").state == "pass"

    def test_misconception_always_converges_fails(self) -> None:
        # "등비급수는 늘 수렴" 오개념 — 발산(0)인데 1로 답 → fail.
        assert verify_geometric_convergence("3/2", "1").state == "fail"

    def test_ratio_lt_one_converges(self) -> None:
        # |r|<1 → 수렴(1).
        assert verify_geometric_convergence("1/2", "1").state == "pass"
        assert verify_geometric_convergence("1/2", "0").state == "fail"

    def test_boundary_ratio_one_diverges(self) -> None:
        # 경계 |r|=1은 발산(0).
        assert verify_geometric_convergence("1", "0").state == "pass"

    def test_non_count_claim_unverifiable(self) -> None:
        assert verify_geometric_convergence("1/2", "3").state == "unverifiable"
