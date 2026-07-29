"""근의 합/곱 킬러 생성기 테스트 — S2 wedge 킬러(순수·결정론·라이브 0).

결정론·전 산출물 게이트 통과(verify_root_aggregate 경유)·오답 검출·킬러성(무리근)을 동결.
"""

from __future__ import annotations

import sympy
from whymath_backend.l3.equivalent.acceptance import (
    EquivalenceSpec,
    evaluate_equivalent_candidate,
)
from whymath_backend.l3.equivalent.generator import CandidateProblem
from whymath_backend.l3.equivalent.root_aggregate_skeleton_generator import (
    RootAggregateSkeletonGenerator,
)

_SPEC = EquivalenceSpec(
    achievement_standard_codes=frozenset({"[10공수1-02-02]"}), difficulty_overall=4.0
)


def _accept(candidate: CandidateProblem) -> object:
    return evaluate_equivalent_candidate(
        _SPEC,
        candidate.problem,
        provenance=candidate.provenance,
        conditions=candidate.conditions,
        answer_map=candidate.answer_map,
        answer_selection=candidate.answer_selection,
        answer_aggregate=candidate.answer_aggregate,
    )


def test_deterministic() -> None:
    a = RootAggregateSkeletonGenerator(kind="sum", degree=3)
    b = RootAggregateSkeletonGenerator(kind="sum", degree=3)
    seq_a = [a.generate(_SPEC).problem.slug for _ in range(10)]  # type: ignore[union-attr]
    seq_b = [b.generate(_SPEC).problem.slug for _ in range(10)]  # type: ignore[union-attr]
    assert seq_a == seq_b


def test_all_variants_pass_gate() -> None:
    # 4종(합/곱 × 이차/삼차) 산출물이 전부 수용 게이트를 통과한다(verify_root_aggregate 경유).
    for kind in ("sum", "product"):
        for degree in (2, 3):
            gen = RootAggregateSkeletonGenerator(kind=kind, degree=degree)  # type: ignore[arg-type]
            for _ in range(12):
                candidate = gen.generate(_SPEC)
                assert candidate is not None
                assert candidate.answer_aggregate == kind
                verdict = _accept(candidate)
                assert verdict.accepted, (  # type: ignore[attr-defined]
                    f"{kind}/{degree} 거부: {candidate.problem.question_text}"
                    f" — {verdict.reasons}"  # type: ignore[attr-defined]
                )


def test_wrong_answer_detected() -> None:
    gen = RootAggregateSkeletonGenerator(kind="sum", degree=2)
    candidate = gen.generate(_SPEC)
    assert candidate is not None
    data = candidate.model_dump()
    data["problem"]["answer"] = str(int(candidate.problem.answer) + 1)  # type: ignore[arg-type]
    bad = CandidateProblem.model_validate(data)
    verdict = _accept(bad)
    assert not verdict.accepted  # type: ignore[attr-defined]
    assert verdict.verification == "failed"  # type: ignore[attr-defined]


def test_killer_roots_are_irrational() -> None:
    # 킬러성: 조건 방정식의 근이 무리수라 학생이 근을 일일이 못 구하고 Vieta로 풀어야 한다.
    gen = RootAggregateSkeletonGenerator(kind="sum", degree=2)
    candidate = gen.generate(_SPEC)
    assert candidate is not None
    x = sympy.Symbol("x")
    lhs = candidate.conditions.split("=")[0]  # type: ignore[union-attr]
    roots = sympy.solve(sympy.Eq(sympy.sympify(lhs), 0), x)
    assert any(not r.is_rational for r in roots), f"무리근 없음: {roots}"


def test_answer_map_empty_for_aggregate() -> None:
    # 답이 근이 아니라 집계값이라 근 치환맵은 비어 있다(정직).
    gen = RootAggregateSkeletonGenerator(kind="product", degree=3)
    candidate = gen.generate(_SPEC)
    assert candidate is not None
    assert candidate.answer_map == {}
    assert candidate.answer_selection is None
