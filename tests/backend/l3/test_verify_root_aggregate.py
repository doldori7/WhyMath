"""verify_root_aggregate 테스트 — 근의 합/곱(Vieta) 검증 프리미티브(순수·라이브 0).

유리·무리·삼차·복소 Vieta 정확값 pass·틀림 fail·범위 밖 unverifiable을 동결.
"""

from __future__ import annotations

from whymath_backend.l3.verify_answer import verify_root_aggregate


def test_sum_rational() -> None:
    # x^2-5x+6=0 근 2,3 → 합 5.
    assert verify_root_aggregate("x**2 - 5*x + 6 = 0", "5", "sum").state == "pass"
    assert verify_root_aggregate("x**2 - 5*x + 6 = 0", "7", "sum").state == "fail"


def test_product_rational() -> None:
    assert verify_root_aggregate("x**2 - 5*x + 6 = 0", "6", "product").state == "pass"
    assert verify_root_aggregate("x**2 - 5*x + 6 = 0", "5", "product").state == "fail"


def test_irrational_roots_vieta_exact() -> None:
    # x^2-2=0 근 ±√2 → 합 0·곱 -2 (근을 못 구해도 Vieta 정확).
    assert verify_root_aggregate("x**2 - 2 = 0", "0", "sum").state == "pass"
    assert verify_root_aggregate("x**2 - 2 = 0", "-2", "product").state == "pass"


def test_cubic_sum_and_product() -> None:
    # (x-1)(x-2)(x-3)=x^3-6x^2+11x-6 → 합 6·곱 6.
    cond = "x**3 - 6*x**2 + 11*x - 6 = 0"
    assert verify_root_aggregate(cond, "6", "sum").state == "pass"
    assert verify_root_aggregate(cond, "6", "product").state == "pass"
    assert verify_root_aggregate(cond, "5", "sum").state == "fail"


def test_complex_roots_vieta_still_exact() -> None:
    # x^2+1=0 근 ±i → 합 0·곱 1 (복소 포함 Vieta 정확).
    assert verify_root_aggregate("x**2 + 1 = 0", "0", "sum").state == "pass"
    assert verify_root_aggregate("x**2 + 1 = 0", "1", "product").state == "pass"


def test_double_root_multiplicity() -> None:
    # (x-3)^2=0 → 근 3(중복 2) → 합 6·곱 9.
    assert verify_root_aggregate("x**2 - 6*x + 9 = 0", "6", "sum").state == "pass"
    assert verify_root_aggregate("x**2 - 6*x + 9 = 0", "9", "product").state == "pass"


def test_unverifiable_out_of_scope() -> None:
    assert verify_root_aggregate("x > 0", "0", "sum").state == "unverifiable"
    assert verify_root_aggregate("a*x = b", "0", "sum").state == "unverifiable"
    assert verify_root_aggregate("$$broken$$", "0", "sum").state == "unverifiable"


def test_irrational_claimed_value_exact() -> None:
    # 무리 정답도 정확 비교(정수 아님). (x^2-2x-1=0) 근 1±√2 → 곱 = -1.
    assert verify_root_aggregate("x**2 - 2*x - 1 = 0", "-1", "product").state == "pass"
