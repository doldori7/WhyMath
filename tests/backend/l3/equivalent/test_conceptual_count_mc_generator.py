"""개념형 개수 MC 생성기 테스트 — 결정론·게이트 accept·answer_kind 담김(순수·hermetic).

각 템플릿이 게이트 통과 후보를 내고(개수 SymPy 독립 검증)·오개념 개수는 fail함을 동결한다.
"""

from __future__ import annotations

import pytest

from whymath_backend.harness.misconception_mc_batch import (
    build_kebab_distractor_codes_optional,
)
from whymath_backend.l3.equivalent.acceptance import (
    EquivalenceSpec,
    evaluate_equivalent_candidate,
)
from whymath_backend.l3.equivalent.conceptual_count_mc_generator import (
    ConceptualCountMCSkeletonGenerator,
    CountTemplateKind,
)

_CASES: tuple[tuple[CountTemplateKind, str, tuple[str, ...]], ...] = (
    ("real_root_count", "discriminant-negative-no-real-root", ("[10공수1-02-02]",)),
    ("extremum_count", "critical-point-implies-extremum", ("[12미적Ⅰ-02-01]",)),
    ("is_one_to_one", "invertibility-without-1-1", ("[10기수2-03-03]",)),
    ("geometric_convergence", "geometric-series-always-converges", ("[12대수03-01]",)),
    ("limit_equals_value", "limit-equals-function-value", ("[12미적Ⅰ-01-01]",)),
    ("is_differentiable", "continuity-implies-differentiability", ("[12미적Ⅰ-02-02]",)),
    ("series_converges", "term-to-zero-implies-convergence", ("[12미적Ⅱ-01-04]",)),
    ("excluded_point_count", "division-by-zero", ("[9수01-03]",)),
    ("mean_equals_median", "mean-vs-median", ("[6수04-01]",)),
    (
        "events_independent",
        "mutually-exclusive-implies-independent",
        ("[12확통02-05]",),
    ),
    ("conditional_equal", "prosecutor-fallacy", ("[12확통02-04]",)),
    ("congruent_by_ratio", "similarity-vs-congruence", ("[6수03-01]",)),
    ("dot_product_scalar", "dot-product-is-vector", ("[12기하03-03]",)),
    ("inequality_direction", "sign-flip-in-inequality", ("[9수02-11]",)),
)


def _spec(kebab: str, codes: tuple[str, ...]) -> EquivalenceSpec:
    return EquivalenceSpec(
        achievement_standard_codes=frozenset(codes),
        target_misconception_ids=frozenset({kebab}),
        difficulty_overall=3.0,
        answer_format=None,
    )


def _gen(template: CountTemplateKind, kebab: str) -> ConceptualCountMCSkeletonGenerator:
    return ConceptualCountMCSkeletonGenerator(
        template, build_kebab_distractor_codes_optional(kebab)
    )


@pytest.mark.parametrize("template,kebab,codes", _CASES)
def test_yields_and_deterministic(
    template: CountTemplateKind, kebab: str, codes: tuple[str, ...]
) -> None:
    a = _gen(template, kebab)
    b = _gen(template, kebab)
    spec = _spec(kebab, codes)
    out_a = [a.generate(spec) for _ in range(24)]
    out_b = [b.generate(spec) for _ in range(24)]
    assert all(c is not None for c in out_a)  # 풀 ≥24
    assert [c.conditions for c in out_a if c] == [
        c.conditions for c in out_b if c
    ]  # 결정론


@pytest.mark.parametrize("template,kebab,codes", _CASES)
def test_gate_accepts_correct_count(
    template: CountTemplateKind, kebab: str, codes: tuple[str, ...]
) -> None:
    spec = _spec(kebab, codes)
    cand = _gen(template, kebab).generate(spec)
    assert cand is not None and cand.answer_kind == template
    v = evaluate_equivalent_candidate(
        spec,
        cand.problem,
        provenance=cand.provenance,
        conditions=cand.conditions,
        answer_map=cand.answer_map,
        answer_kind=cand.answer_kind,
    )
    assert v.verification == "verified"  # 정답 개수는 SymPy 독립 검증 통과


@pytest.mark.parametrize("template,kebab,codes", _CASES)
def test_gate_fails_misconception_count(
    template: CountTemplateKind, kebab: str, codes: tuple[str, ...]
) -> None:
    # 오답 선지(오개념 개수)를 answer로 바꿔치면 게이트가 fail(진짜 개념 검증).
    spec = _spec(kebab, codes)
    cand = _gen(template, kebab).generate(spec)
    assert cand is not None
    misc_index = cand.problem.distractor_map[0].choice_index  # type: ignore[index]
    misc_answer = cand.problem.choices[misc_index]  # type: ignore[index]
    v = evaluate_equivalent_candidate(
        spec,
        cand.problem.model_copy(update={"answer": misc_answer}),
        provenance=cand.provenance,
        conditions=cand.conditions,
        answer_map=cand.answer_map,
        answer_kind=cand.answer_kind,
    )
    assert v.verification == "failed"
