"""classify_solvability 테스트 — 해 존재성·유일성 5분류 프리미티브(순수·라이브 0).

문항 품질 15축 ②(해 없음)·③(답 여러 개)의 검출 프리미티브를 동결한다: 항등식(무한해)·
해 없음·유일·다근·판정불가를 각각 확정하고, **비다항·다변수는 undecidable로 보수 회피**
(sympy.solve 빈결과를 "해 없음"으로 오판하지 않음)를 봉인한다.
"""

from __future__ import annotations

from whymath_backend.l3.verify_answer import classify_solvability


def test_identity_infinite_solutions() -> None:
    # 2(x+1) = 2x+2 → 항등식(모든 값이 해) → identity.
    assert classify_solvability("2*(x+1) = 2*x + 2").state == "identity"
    assert classify_solvability("3*x - x = 2*x").state == "identity"


def test_no_solution_constant_residual() -> None:
    # x+1 = x+2 → lhs-rhs = -1(0 아닌 상수) → 해 없음.
    assert classify_solvability("x + 1 = x + 2").state == "no_solution"


def test_no_solution_no_real_root() -> None:
    # x^2 + 1 = 0 → 실근 없음(복소근만) → 실답 스코프에서 해 없음.
    v = classify_solvability("x**2 + 1 = 0")
    assert v.state == "no_solution"


def test_unique_single_real_root() -> None:
    # 2x - 6 = 0 → x=3 유일.
    v = classify_solvability("2*x - 6 = 0")
    assert v.state == "unique" and v.n_distinct_real_roots == 1


def test_unique_double_root_folds_to_one() -> None:
    # (x-2)^2 = 0 → 중근 2 → 서로 다른 실근 1개 → unique.
    v = classify_solvability("x**2 - 4*x + 4 = 0")
    assert v.state == "unique" and v.n_distinct_real_roots == 1


def test_multiple_distinct_real_roots() -> None:
    # x^2 - 5x + 6 = 0 → 2,3 → multiple.
    v = classify_solvability("x**2 - 5*x + 6 = 0")
    assert v.state == "multiple" and v.n_distinct_real_roots == 2


def test_undecidable_non_polynomial() -> None:
    # 지수·로그 등 비다항은 solve 빈결과 오판 회피 → undecidable(정상 문항 거짓거부 금지).
    assert classify_solvability("2**x = 8").state == "undecidable"
    assert classify_solvability("log(x) = 1").state == "undecidable"


def test_undecidable_multivariable() -> None:
    # 파라미터/다변수(2*a*x = b)는 존재성 의미 불명확 → undecidable.
    assert classify_solvability("2*a*x = b").state == "undecidable"


def test_undecidable_inequality_and_system() -> None:
    # 부등식·연립은 등식 단일변수 스코프 밖 → undecidable.
    assert classify_solvability("x > 0").state == "undecidable"
    assert classify_solvability(["x + y = 3", "x - y = 1"]).state == "undecidable"


def test_undecidable_empty_and_unparsable() -> None:
    assert classify_solvability("").state == "undecidable"
    assert classify_solvability([]).state == "undecidable"
