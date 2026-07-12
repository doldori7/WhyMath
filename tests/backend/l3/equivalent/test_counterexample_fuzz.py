"""수치 반례 fuzzer 테스트 — 초인간 검증 §2 적대성(순수·결정론·라이브 0).

정상 문항 pass·오답/선택위반 fail(반례 보고)·무리근 pass·범위 밖 unverifiable을 동결.
스켈레톤 생성기 산출물에 대한 회귀(전부 pass)도 확인한다.
"""

from __future__ import annotations

from whymath_backend.l3.equivalent.acceptance import EquivalenceSpec
from whymath_backend.l3.equivalent.counterexample_fuzz import fuzz_answer
from whymath_backend.l3.equivalent.skeleton_generator import (
    SkeletonEquivalentProblemGenerator,
)


def test_pass_on_correct_answer() -> None:
    v = fuzz_answer("x**2 - 5*x = 0", {"x": "5"}, "largest")
    assert v.state == "pass"
    assert v.trials == 10_000  # §2 "≥10,000 검산" 실제 시행
    assert 0.0 in [round(r) for r in v.roots_found]
    assert 5.0 in [round(r) for r in v.roots_found]


def test_fail_on_wrong_answer_reports_counterexample() -> None:
    v = fuzz_answer("x**2 - 5*x = 0", {"x": "6"}, "largest")
    assert v.state == "fail"
    assert v.reason is not None and "근이 아님" in v.reason


def test_fail_on_selection_violation_smallest() -> None:
    # 작은 근이라며 5(실제 큰 근)를 주장 → 더 작은 근 0 존재 → fail.
    v = fuzz_answer("x**2 - 5*x = 0", {"x": "5"}, "smallest")
    assert v.state == "fail"
    assert v.reason is not None and "작은 근" in v.reason


def test_fail_on_selection_violation_largest() -> None:
    v = fuzz_answer("x**2 - 5*x = 0", {"x": "0"}, "largest")
    assert v.state == "fail"
    assert v.reason is not None and "큰 근" in v.reason


def test_fail_on_unique_when_multiple_roots() -> None:
    v = fuzz_answer("x**2 - 5*x = 0", {"x": "0"}, "unique")
    assert v.state == "fail"
    assert v.reason is not None and "유일근" in v.reason


def test_pass_on_irrational_root() -> None:
    # (x-1)^2 = 2 → 근 1±√2, 큰 근 1+√2. 정확값 문자열도 수치화된다.
    v = fuzz_answer("(x - 1)**2 = 2", {"x": "1 + sqrt(2)"}, "largest")
    assert v.state == "pass"


def test_double_root_unique_passes() -> None:
    # (x-3)^2 = 0 → 유일근(중근) 3.
    v = fuzz_answer("x**2 - 6*x + 9 = 0", {"x": "3"}, "unique")
    assert v.state == "pass"


def test_unverifiable_on_inequality() -> None:
    assert fuzz_answer("x > 0", {"x": "5"}).state == "unverifiable"


def test_unverifiable_on_multivariable() -> None:
    assert fuzz_answer("a*x = b", {"x": "b/a"}).state == "unverifiable"


def test_unverifiable_on_parse_error() -> None:
    assert fuzz_answer("$$broken$$", {"x": "1"}).state == "unverifiable"


def test_deterministic() -> None:
    a = fuzz_answer("x**2 - 5*x = 0", {"x": "5"}, "largest")
    b = fuzz_answer("x**2 - 5*x = 0", {"x": "5"}, "largest")
    assert a.state == b.state and a.roots_found == b.roots_found


def test_skeleton_outputs_all_pass_fuzz() -> None:
    # 결정론 생성기의 산출물은 구성상 참이므로 fuzzer도 전부 pass여야 한다(회귀 앵커).
    spec = EquivalenceSpec(
        achievement_standard_codes=frozenset({"[10공수1-02-02]"}), difficulty_overall=2.5
    )
    gen = SkeletonEquivalentProblemGenerator(variant="short_answer")
    checked = 0
    for _ in range(30):
        candidate = gen.generate(spec)
        if candidate is None:  # pragma: no cover — 풀 충분
            break
        conditions = candidate.conditions
        assert isinstance(conditions, str)
        v = fuzz_answer(conditions, candidate.answer_map, candidate.answer_selection)
        assert v.state == "pass", f"{conditions} / {candidate.answer_map} → {v.state}: {v.reason}"
        checked += 1
    assert checked == 30
