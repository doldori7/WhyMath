"""대학 미적분학 I 몫의 미분법·연쇄법칙 스켈레톤 생성기 단위테스트(hermetic·게이트 재사용).

`CalculusQuotientRuleSkeletonGenerator`·`CalculusChainRuleSkeletonGenerator`가 ① 전건
S2-a 4종 게이트 통과(`calculus_product_rule_skeleton_generator`와 동형 검증 설계 재실증)
② answer가 독립 재계산(몫의 미분법 전개식·연쇄법칙 전개식)과 일치 ③ 풀 유일·소진 시 None
④ 몫의 미분법이 g(k)=±1 구성으로 항상 정수 답을 내는지 ⑤ concept_tags=()(대학 원자 태깅
공백 정직 표시, 가짜 태그 금지)를 못 박는다. LLM·DB·PG 0(순수 결정론).
"""

from __future__ import annotations

from whymath_backend.l3.equivalent.acceptance import (
    EquivalenceSpec,
    evaluate_equivalent_candidate,
)
from whymath_backend.l3.equivalent.calculus_chain_quotient_rule_skeleton_generator import (
    CalculusChainRuleSkeletonGenerator,
    CalculusQuotientRuleSkeletonGenerator,
    _build_chain_pool,
    _build_quotient_pool,
)
from whymath_backend.l3.equivalent.generator import CandidateProblem
from whymath_backend.schema.enums import QuestionFormat

_QUOTIENT_STANDARD = "[CALC1-02-03]"
_CHAIN_STANDARD = "[CALC1-02-04]"


def _quotient_spec() -> EquivalenceSpec:
    return EquivalenceSpec(
        achievement_standard_codes=frozenset({_QUOTIENT_STANDARD}),
        target_misconception_ids=frozenset(),
        difficulty_overall=3.9,
        answer_format=None,
    )


def _chain_spec() -> EquivalenceSpec:
    return EquivalenceSpec(
        achievement_standard_codes=frozenset({_CHAIN_STANDARD}),
        target_misconception_ids=frozenset(),
        difficulty_overall=3.8,
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


class TestQuotientPool:
    def test_pool_reaches_target_and_structurally_unique(self) -> None:
        pool = _build_quotient_pool()
        assert len(pool) == 260
        keys = {(s.a, s.b, s.c, s.d, s.k, s.g_sign) for s in pool}
        assert len(keys) == len(pool)

    def test_denominator_at_k_is_always_pm_one(self) -> None:
        """핵심 설계 불변식 — g(k)=dk+e는 항상 ±1(정수 답 보장의 근거)."""
        for skeleton in _build_quotient_pool():
            g_at_k = skeleton.d * skeleton.k + skeleton.e
            assert g_at_k == skeleton.g_sign
            assert abs(g_at_k) == 1

    def test_answer_matches_independent_quotient_rule_recompute(self) -> None:
        for skeleton in _build_quotient_pool()[:150]:
            a, b, c, d, k = skeleton.a, skeleton.b, skeleton.c, skeleton.d, skeleton.k
            e = skeleton.e
            g_at_k = d * k + e
            f1_prime = 2 * a * k + b
            f1_at_k = a * k * k + b * k + c
            expected = (f1_prime * g_at_k - f1_at_k * d) // (g_at_k * g_at_k)
            assert skeleton.result == expected

    def test_generation_exhausts_to_none(self) -> None:
        pool_size = len(_build_quotient_pool())
        gen = CalculusQuotientRuleSkeletonGenerator()
        drained = _drain(gen, _quotient_spec(), pool_size + 5)
        assert len(drained) == pool_size
        assert gen.generate(_quotient_spec()) is None


class TestQuotientAcceptance:
    def test_all_pass_acceptance_gate(self) -> None:
        candidates = _drain(CalculusQuotientRuleSkeletonGenerator(), _quotient_spec(), 260)
        assert len(candidates) == 260
        for candidate in candidates:
            verdict = evaluate_equivalent_candidate(
                _quotient_spec(),
                candidate.problem,
                provenance=candidate.provenance,
                conditions=candidate.conditions,
                answer_map=candidate.answer_map,
                solution_steps=candidate.solution_steps,
            )
            assert verdict.accepted is True, f"{candidate.problem.slug} 미수용: {verdict.reasons}"
            assert verdict.verification == "verified"

    def test_gate_rejects_wrong_answer(self) -> None:
        candidate = CalculusQuotientRuleSkeletonGenerator().generate(_quotient_spec())
        assert candidate is not None
        broken_answer = str(int(candidate.problem.answer) + 1)
        verdict = evaluate_equivalent_candidate(
            _quotient_spec(),
            candidate.problem.model_copy(update={"answer": broken_answer}),
            provenance=candidate.provenance,
            conditions=candidate.conditions,
            answer_map={"y": broken_answer},
            solution_steps=candidate.solution_steps,
        )
        assert verdict.accepted is False
        assert any("Tier1" in r for r in verdict.reasons)


class TestQuotientShape:
    def test_question_format_and_no_choices(self) -> None:
        gen = CalculusQuotientRuleSkeletonGenerator()
        for candidate in _drain(gen, _quotient_spec(), 20):
            assert candidate.problem.question_format == QuestionFormat.단답형
            assert candidate.problem.choices is None
            assert candidate.problem.distractor_map is None

    def test_concept_tags_intentionally_empty(self) -> None:
        """대학 원자 태깅 공백 — 가짜 orphan-skip 태그 대신 정직하게 빈 튜플(형제 관례)."""
        candidate = CalculusQuotientRuleSkeletonGenerator().generate(_quotient_spec())
        assert candidate is not None
        assert candidate.concept_tags == []


class TestChainPool:
    def test_pool_reaches_target_and_structurally_unique(self) -> None:
        pool = _build_chain_pool()
        assert len(pool) == 260
        keys = {(s.a, s.b, s.n, s.k) for s in pool}
        assert len(keys) == len(pool)
        for skeleton in pool:
            assert skeleton.n >= 2

    def test_answer_matches_independent_chain_rule_recompute(self) -> None:
        for skeleton in _build_chain_pool()[:150]:
            inner_at_k = skeleton.a * skeleton.k + skeleton.b
            expected = skeleton.n * skeleton.a * inner_at_k ** (skeleton.n - 1)
            assert skeleton.result == expected

    def test_generation_exhausts_to_none(self) -> None:
        pool_size = len(_build_chain_pool())
        gen = CalculusChainRuleSkeletonGenerator()
        drained = _drain(gen, _chain_spec(), pool_size + 5)
        assert len(drained) == pool_size
        assert gen.generate(_chain_spec()) is None


class TestChainAcceptance:
    def test_all_pass_acceptance_gate(self) -> None:
        candidates = _drain(CalculusChainRuleSkeletonGenerator(), _chain_spec(), 260)
        assert len(candidates) == 260
        for candidate in candidates:
            verdict = evaluate_equivalent_candidate(
                _chain_spec(),
                candidate.problem,
                provenance=candidate.provenance,
                conditions=candidate.conditions,
                answer_map=candidate.answer_map,
                solution_steps=candidate.solution_steps,
            )
            assert verdict.accepted is True, f"{candidate.problem.slug} 미수용: {verdict.reasons}"
            assert verdict.verification == "verified"

    def test_gate_rejects_wrong_answer(self) -> None:
        candidate = CalculusChainRuleSkeletonGenerator().generate(_chain_spec())
        assert candidate is not None
        broken_answer = str(int(candidate.problem.answer) + 1)
        verdict = evaluate_equivalent_candidate(
            _chain_spec(),
            candidate.problem.model_copy(update={"answer": broken_answer}),
            provenance=candidate.provenance,
            conditions=candidate.conditions,
            answer_map={"y": broken_answer},
            solution_steps=candidate.solution_steps,
        )
        assert verdict.accepted is False
        assert any("Tier1" in r for r in verdict.reasons)


class TestChainShape:
    def test_question_format_and_no_choices(self) -> None:
        gen = CalculusChainRuleSkeletonGenerator()
        for candidate in _drain(gen, _chain_spec(), 20):
            assert candidate.problem.question_format == QuestionFormat.단답형
            assert candidate.problem.choices is None
            assert candidate.problem.distractor_map is None

    def test_concept_tags_intentionally_empty(self) -> None:
        candidate = CalculusChainRuleSkeletonGenerator().generate(_chain_spec())
        assert candidate is not None
        assert candidate.concept_tags == []
