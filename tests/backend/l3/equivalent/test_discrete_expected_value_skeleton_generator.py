"""고등 이산확률변수 기댓값 결정론 스켈레톤 생성기 — W2 단위테스트(hermetic·게이트 재사용).

`DiscreteExpectedValueSkeletonGenerator`가 ① 전건 S2-a 4종 게이트 통과(초등 산술·고등 행렬·
대학 미분·중등 함숫값에 이은 다섯 번째 도메인·최초 유리수 도메인에서 게이트 인프라 무변경
재사용 재실증) ② answer가 독립 재계산(가중합 정의·SymPy 밖 순수 Fraction 산술)과 일치
③ 확률 분자가 항상 10으로 합산됨(유효 확률분포) ④ 풀 유일·소진 시 None ⑤ 개념 태깅(legacy
437 공간 실존)·정답형식(분수)·위생 게이트 무오탐(발문의 "P(X=k)=n/10" 표기가 하이지엔
게이트를 트립하지 않음 — 2026-08-05 실측 확인)을 못 박는다. LLM·DB·PG 0(순수 결정론).
"""

from __future__ import annotations

from fractions import Fraction

import pytest

from whymath_backend.l3.equivalent.acceptance import (
    EquivalenceSpec,
    evaluate_equivalent_candidate,
)
from whymath_backend.l3.equivalent.discrete_expected_value_skeleton_generator import (
    DiscreteExpectedValueSkeletonGenerator,
    _build_pool,
)
from whymath_backend.l3.equivalent.generator import CandidateProblem
from whymath_backend.schema.enums import AnswerFormat, QuestionFormat

# PB-13: backend 잡 35분 상한 초과 해소 — PR 상시 경로에서 분리하고 전용 잡
# corpus-authoring(야간 + 생성기·배치 변경 PR)이 돌린다. 비활성화가 아니다.
pytestmark = pytest.mark.corpus_authoring

_STANDARD = "[12확통03-02]"


def _spec() -> EquivalenceSpec:
    return EquivalenceSpec(
        achievement_standard_codes=frozenset({_STANDARD}),
        target_misconception_ids=frozenset(),
        difficulty_overall=2.8,
        answer_format=None,
    )


def _drain(gen: DiscreteExpectedValueSkeletonGenerator, limit: int) -> list[CandidateProblem]:
    out: list[CandidateProblem] = []
    while len(out) < limit:
        candidate = gen.generate(_spec())
        if candidate is None:
            break
        out.append(candidate)
    return out


class TestPool:
    def test_pool_nonempty_and_unique(self) -> None:
        pool = _build_pool()
        assert len(pool) >= 250
        keys = {(s.x1, s.x2, s.x3, s.n1, s.n2, s.n3) for s in pool}
        assert len(keys) == len(pool)

    def test_probability_numerators_always_sum_to_denominator(self) -> None:
        """확률 분자 합이 항상 10 — 유효 확률분포(Σp=1) 불변식."""
        for skeleton in _build_pool():
            assert skeleton.n1 + skeleton.n2 + skeleton.n3 == 10
            assert skeleton.n1 >= 1 and skeleton.n2 >= 1 and skeleton.n3 >= 1

    def test_x_values_are_distinct_and_sorted(self) -> None:
        for skeleton in _build_pool():
            assert skeleton.x1 < skeleton.x2 < skeleton.x3

    def test_generation_exhausts_to_none(self) -> None:
        pool_size = len(_build_pool())
        gen = DiscreteExpectedValueSkeletonGenerator()
        drained = _drain(gen, pool_size + 10)
        assert len(drained) == pool_size
        assert gen.generate(_spec()) is None


class TestAcceptanceGate:
    def test_all_pass_acceptance_gate(self) -> None:
        """전건 4종 게이트 통과 — 발문의 'P(X=k)=n/10' 표기가 위생 게이트를 트립하지 않음을
        실측으로 못 박는다(등호 인접 표기가 있음에도 오탐 없음 — calculus/matrix와 다른
        형태의 오탐 후보였으나 실제로는 안전했음을 확인)."""
        candidates = _drain(DiscreteExpectedValueSkeletonGenerator(), 150)
        assert len(candidates) >= 150
        for candidate in candidates:
            verdict = evaluate_equivalent_candidate(
                _spec(),
                candidate.problem,
                provenance=candidate.provenance,
                conditions=candidate.conditions,
                answer_map=candidate.answer_map,
                solution_steps=candidate.solution_steps,
            )
            assert verdict.accepted is True, f"{candidate.problem.slug} 미수용: {verdict.reasons}"
            assert verdict.verification == "verified"

    def test_answer_matches_independent_weighted_sum_recomputation(self) -> None:
        """교차 검증 — answer가 생성기 밖 독립 재계산(가중합 정의·Fraction)과 일치."""
        for skeleton in _build_pool()[:100]:
            expected = Fraction(
                skeleton.x1 * skeleton.n1 + skeleton.x2 * skeleton.n2 + skeleton.x3 * skeleton.n3,
                10,
            )
            assert skeleton.result == expected

    def test_gate_rejects_wrong_answer(self) -> None:
        """변별력 — 정답을 어긋나게 만든 후보는 Tier1 유리수 검산에서 거부된다."""
        candidate = DiscreteExpectedValueSkeletonGenerator().generate(_spec())
        assert candidate is not None
        broken = Fraction(candidate.problem.answer) + 1
        broken_answer = str(broken.numerator) if broken.denominator == 1 else str(broken)
        verdict = evaluate_equivalent_candidate(
            _spec(),
            candidate.problem.model_copy(update={"answer": broken_answer}),
            provenance=candidate.provenance,
            conditions=candidate.conditions,
            answer_map={"y": broken_answer},
            solution_steps=candidate.solution_steps,
        )
        assert verdict.accepted is False
        assert any("Tier1" in r for r in verdict.reasons)


class TestCandidateShape:
    def test_question_format_and_answer_format(self) -> None:
        for candidate in _drain(DiscreteExpectedValueSkeletonGenerator(), 20):
            assert candidate.problem.question_format == QuestionFormat.단답형
            assert candidate.problem.answer_format == AnswerFormat.분수
            assert candidate.problem.choices is None
            assert candidate.problem.distractor_map is None

    def test_difficulty_is_fixed_procedural_conceptual_boundary(self) -> None:
        for candidate in _drain(DiscreteExpectedValueSkeletonGenerator(), 30):
            assert candidate.problem.difficulty_overall == 2.8

    def test_concept_tags_resolve_via_legacy_437_space(self) -> None:
        candidate = DiscreteExpectedValueSkeletonGenerator().generate(_spec())
        assert candidate is not None
        assert len(candidate.concept_tags) == 1
        assert candidate.concept_tags[0].concept_src_id == "H:12확통03-02"
        assert candidate.concept_tags[0].role == "PRIMARY"

    def test_solution_steps_intentionally_none(self) -> None:
        candidate = DiscreteExpectedValueSkeletonGenerator().generate(_spec())
        assert candidate is not None
        assert candidate.solution_steps is None

    def test_answer_is_reduced_fraction_string(self) -> None:
        """답이 기약분수 문자열('7/2') 또는 정수 문자열('4') — 비기약(예 '14/10') 금지."""
        for candidate in _drain(DiscreteExpectedValueSkeletonGenerator(), 100):
            answer = candidate.problem.answer
            if "/" in answer:
                num, denom = answer.split("/")
                from math import gcd

                assert gcd(int(num), int(denom)) == 1, answer


class TestSkipConditions:
    def test_skip_conditions_filters_already_seen(self) -> None:
        seen: set[str] = set()
        first = DiscreteExpectedValueSkeletonGenerator(skip_conditions=seen).generate(_spec())
        assert first is not None
        seen.add(first.conditions)  # type: ignore[arg-type]

        second = DiscreteExpectedValueSkeletonGenerator(skip_conditions=seen).generate(_spec())
        assert second is not None
        assert second.conditions != first.conditions
