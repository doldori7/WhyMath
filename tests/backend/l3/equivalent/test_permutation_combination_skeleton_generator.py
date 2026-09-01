"""고등 경우의 수 — 합의 법칙·곱의 법칙·순열 스켈레톤 생성기 단위테스트(hermetic·게이트 재사용).

`SumProductPrincipleSkeletonGenerator`·`PermutationSkeletonGenerator`가 ① 전건 S2-a 4종
게이트 통과(SymPy factorial() 조건이 Tier1에서 정확히 검증되는지 실측 재확인 포함) ②
answer가 독립 재계산과 일치 ③ 풀 유일·소진 시 None ④ `kind` 필터로 밴드가 실제로 분리됨
(2026-08-05 elementary_addsub 사고 재발 방지 회귀 봉인) ⑤ 개념 태깅·위생 게이트 무오탐을
못 박는다. LLM·DB·PG 0(순수 결정론).
"""

from __future__ import annotations

import math

import pytest

from whymath_backend.l3.equivalent.acceptance import (
    EquivalenceSpec,
    evaluate_equivalent_candidate,
)
from whymath_backend.l3.equivalent.generator import CandidateProblem
from whymath_backend.l3.equivalent.permutation_combination_skeleton_generator import (
    PermutationSkeletonGenerator,
    SumProductPrincipleSkeletonGenerator,
    _build_permutation_pool,
    _build_sum_product_pool,
)
from whymath_backend.schema.enums import QuestionFormat

# PB-13: backend 잡 35분 상한 초과 해소 — PR 상시 경로에서 분리하고 전용 잡
# corpus-authoring(야간 + 생성기·배치 변경 PR)이 돌린다. 비활성화가 아니다.
pytestmark = pytest.mark.corpus_authoring

_SUM_PRODUCT_STANDARD = "[10공수1-03-01]"
_PERMUTATION_STANDARD = "[10공수1-03-02]"


def _sum_product_spec() -> EquivalenceSpec:
    return EquivalenceSpec(
        achievement_standard_codes=frozenset({_SUM_PRODUCT_STANDARD}),
        target_misconception_ids=frozenset(),
        difficulty_overall=1.8,
        answer_format=None,
    )


def _permutation_spec() -> EquivalenceSpec:
    return EquivalenceSpec(
        achievement_standard_codes=frozenset({_PERMUTATION_STANDARD}),
        target_misconception_ids=frozenset(),
        difficulty_overall=2.0,
        answer_format=None,
    )


def _drain(gen: object, spec: EquivalenceSpec, limit: int) -> list[CandidateProblem]:
    out: list[CandidateProblem] = []
    while len(out) < limit:
        candidate = gen.generate(spec)  # type: ignore[attr-defined]
        if candidate is None:
            break
        out.append(candidate)
    return out


class TestSumProductPool:
    def test_pool_nonempty_and_unique(self) -> None:
        pool = _build_sum_product_pool()
        assert len(pool) >= 100
        keys = {(s.kind, s.m, s.n) for s in pool}
        assert len(keys) == len(pool)

    def test_answer_matches_independent_recompute(self) -> None:
        for skeleton in _build_sum_product_pool():
            if skeleton.kind == "sum":
                expected = skeleton.m + skeleton.n
            else:
                expected = skeleton.m * skeleton.n
            assert skeleton.answer == expected

    def test_kind_filter_restricts_output_and_ids_stay_unique_across_bands(self) -> None:
        """`kind` 필터가 실제로 밴드를 분리한다 — 2026-08-05 사고 회귀 봉인."""
        ids_by_kind: dict[str, set] = {}
        for kind in ("sum", "product"):
            candidates = _drain(
                SumProductPrincipleSkeletonGenerator(kind=kind), _sum_product_spec(), 30
            )
            assert len(candidates) == 30
            expected_word = "동시에 일어날 수 없을" if kind == "sum" else "연이어 일어나는"
            assert all(expected_word in c.problem.question_text for c in candidates), kind
            ids_by_kind[kind] = {c.problem.problem_id for c in candidates}
        assert not (
            ids_by_kind["sum"] & ids_by_kind["product"]
        ), "밴드 간 problem_id 중복 — 밴드 분리 실패(회귀)."

    def test_generation_exhausts_to_none_per_kind(self) -> None:
        for kind in ("sum", "product"):
            pool_size = len([s for s in _build_sum_product_pool() if s.kind == kind])
            gen = SumProductPrincipleSkeletonGenerator(kind=kind)
            drained = _drain(gen, _sum_product_spec(), pool_size + 5)
            assert len(drained) == pool_size, kind
            assert gen.generate(_sum_product_spec()) is None


class TestSumProductAcceptance:
    def test_all_pass_acceptance_gate(self) -> None:
        candidates = _drain(SumProductPrincipleSkeletonGenerator(), _sum_product_spec(), 128)
        assert len(candidates) == 128
        for candidate in candidates:
            verdict = evaluate_equivalent_candidate(
                _sum_product_spec(),
                candidate.problem,
                provenance=candidate.provenance,
                conditions=candidate.conditions,
                answer_map=candidate.answer_map,
                solution_steps=candidate.solution_steps,
            )
            assert verdict.accepted is True, f"{candidate.problem.slug} 미수용: {verdict.reasons}"
            assert verdict.verification == "verified"

    def test_gate_rejects_wrong_answer(self) -> None:
        candidate = SumProductPrincipleSkeletonGenerator().generate(_sum_product_spec())
        assert candidate is not None
        broken_answer = str(int(candidate.problem.answer) + 1)
        verdict = evaluate_equivalent_candidate(
            _sum_product_spec(),
            candidate.problem.model_copy(update={"answer": broken_answer}),
            provenance=candidate.provenance,
            conditions=candidate.conditions,
            answer_map={"x": broken_answer},
            solution_steps=candidate.solution_steps,
        )
        assert verdict.accepted is False
        assert any("Tier1" in r for r in verdict.reasons)


class TestSumProductShape:
    def test_question_format_and_no_choices(self) -> None:
        gen = SumProductPrincipleSkeletonGenerator()
        for candidate in _drain(gen, _sum_product_spec(), 20):
            assert candidate.problem.question_format == QuestionFormat.단답형
            assert candidate.problem.choices is None
            assert candidate.problem.distractor_map is None

    def test_concept_tags_resolve_via_legacy_437_space(self) -> None:
        candidate = SumProductPrincipleSkeletonGenerator().generate(_sum_product_spec())
        assert candidate is not None
        assert len(candidate.concept_tags) == 1
        assert candidate.concept_tags[0].concept_src_id == "HK39"


class TestPermutationPool:
    def test_pool_nonempty_and_unique(self) -> None:
        pool = _build_permutation_pool()
        assert len(pool) >= 30
        keys = {(s.n, s.r) for s in pool}
        assert len(keys) == len(pool)
        for skeleton in pool:
            assert 1 <= skeleton.r <= skeleton.n

    def test_answer_matches_independent_factorial_recompute(self) -> None:
        """교차 검증 — SymPy factorial() 조건과 별개로, 파이썬 math.factorial 재계산과도 일치."""
        for skeleton in _build_permutation_pool():
            expected = math.factorial(skeleton.n) // math.factorial(skeleton.n - skeleton.r)
            assert skeleton.answer == expected

    def test_generation_exhausts_to_none(self) -> None:
        pool_size = len(_build_permutation_pool())
        gen = PermutationSkeletonGenerator()
        drained = _drain(gen, _permutation_spec(), pool_size + 5)
        assert len(drained) == pool_size
        assert gen.generate(_permutation_spec()) is None


class TestPermutationAcceptance:
    def test_all_pass_acceptance_gate(self) -> None:
        pool_size = len(_build_permutation_pool())
        candidates = _drain(PermutationSkeletonGenerator(), _permutation_spec(), pool_size)
        assert len(candidates) == pool_size
        for candidate in candidates:
            verdict = evaluate_equivalent_candidate(
                _permutation_spec(),
                candidate.problem,
                provenance=candidate.provenance,
                conditions=candidate.conditions,
                answer_map=candidate.answer_map,
                solution_steps=candidate.solution_steps,
            )
            assert verdict.accepted is True, f"{candidate.problem.slug} 미수용: {verdict.reasons}"
            assert verdict.verification == "verified"

    def test_gate_rejects_wrong_answer(self) -> None:
        candidate = PermutationSkeletonGenerator().generate(_permutation_spec())
        assert candidate is not None
        broken_answer = str(int(candidate.problem.answer) + 1)
        verdict = evaluate_equivalent_candidate(
            _permutation_spec(),
            candidate.problem.model_copy(update={"answer": broken_answer}),
            provenance=candidate.provenance,
            conditions=candidate.conditions,
            answer_map={"x": broken_answer},
            solution_steps=candidate.solution_steps,
        )
        assert verdict.accepted is False
        assert any("Tier1" in r for r in verdict.reasons)


class TestPermutationShape:
    def test_question_format_and_no_choices(self) -> None:
        gen = PermutationSkeletonGenerator()
        for candidate in _drain(gen, _permutation_spec(), 20):
            assert candidate.problem.question_format == QuestionFormat.단답형
            assert candidate.problem.choices is None
            assert candidate.problem.distractor_map is None

    def test_concept_tags_resolve_via_legacy_437_space(self) -> None:
        candidate = PermutationSkeletonGenerator().generate(_permutation_spec())
        assert candidate is not None
        assert len(candidate.concept_tags) == 1
        assert candidate.concept_tags[0].concept_src_id == "HK40"
