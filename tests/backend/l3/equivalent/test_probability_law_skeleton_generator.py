"""고등 확률 — 덧셈정리·여사건·곱셈정리 스켈레톤 생성기 단위테스트(hermetic).

`AdditionLawSkeletonGenerator`·`ComplementLawSkeletonGenerator`·`MultiplicationLaw
SkeletonGenerator`가 ① 전건 S2-a 4종 게이트 통과 ② answer가 독립 재계산(Fraction 기반)과
일치 ③ 풀 유일·소진 시 None ④ concept_src_id가 legacy 437 공간에 실존해 정상 태깅됨
⑤ question_text·answer_explanation 양쪽 모두 신규 Unicode 글리프(특히 ∩·∪ — 이 세션에서
새로 발견된 위험 글리프) 미사용을 못 박는다. LLM·DB·PG 0(순수 결정론).
"""

from __future__ import annotations

from fractions import Fraction

from whymath_backend.l3.equivalent.acceptance import (
    EquivalenceSpec,
    evaluate_equivalent_candidate,
)
from whymath_backend.l3.equivalent.generator import CandidateProblem
from whymath_backend.l3.equivalent.probability_law_skeleton_generator import (
    AdditionLawSkeletonGenerator,
    ComplementLawSkeletonGenerator,
    MultiplicationLawSkeletonGenerator,
    _build_addition_pool,
    _build_complement_pool,
    _build_multiplication_pool,
)
from whymath_backend.schema.enums import QuestionFormat

_ADDITION_STANDARD = "[12확통02-02]"
_COMPLEMENT_STANDARD = "[12확통02-03]"
_MULTIPLICATION_STANDARD = "[12확통02-06]"

_BAD_GLYPHS = ("Σ", "α", "β", "²", "³", "∩", "∪")


def _addition_spec() -> EquivalenceSpec:
    return EquivalenceSpec(
        achievement_standard_codes=frozenset({_ADDITION_STANDARD}),
        target_misconception_ids=frozenset(),
        difficulty_overall=2.8,
        answer_format=None,
    )


def _complement_spec() -> EquivalenceSpec:
    return EquivalenceSpec(
        achievement_standard_codes=frozenset({_COMPLEMENT_STANDARD}),
        target_misconception_ids=frozenset(),
        difficulty_overall=2.0,
        answer_format=None,
    )


def _multiplication_spec() -> EquivalenceSpec:
    return EquivalenceSpec(
        achievement_standard_codes=frozenset({_MULTIPLICATION_STANDARD}),
        target_misconception_ids=frozenset(),
        difficulty_overall=3.0,
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


def _assert_no_bad_glyphs(candidate: CandidateProblem) -> None:
    for field in (candidate.problem.question_text, candidate.problem.answer_explanation):
        for glyph in _BAD_GLYPHS:
            assert glyph not in field, f"{glyph!r} in {field!r}"


class TestAdditionPool:
    def test_pool_nonempty_and_unique(self) -> None:
        pool = _build_addition_pool()
        assert len(pool) >= 1000
        keys = {(s.n, s.a, s.b, s.both) for s in pool}
        assert len(keys) == len(pool)

    def test_answer_matches_independent_recompute_and_valid_probability(self) -> None:
        for skeleton in _build_addition_pool()[:500]:
            expected = Fraction(skeleton.a + skeleton.b - skeleton.both, skeleton.n)
            assert skeleton.answer == expected
            assert 0 <= skeleton.answer <= 1  # 유효 확률공간(날조 없는 P(A∪B)≤1).

    def test_generation_exhausts_to_none(self) -> None:
        pool_size = len(_build_addition_pool())
        gen = AdditionLawSkeletonGenerator()
        drained = _drain(gen, _addition_spec(), pool_size + 5)
        assert len(drained) == pool_size
        assert gen.generate(_addition_spec()) is None


class TestAdditionAcceptance:
    def test_all_pass_acceptance_gate(self) -> None:
        candidates = _drain(AdditionLawSkeletonGenerator(), _addition_spec(), 400)
        assert len(candidates) == 400
        for candidate in candidates:
            verdict = evaluate_equivalent_candidate(
                _addition_spec(),
                candidate.problem,
                provenance=candidate.provenance,
                conditions=candidate.conditions,
                answer_map=candidate.answer_map,
                solution_steps=candidate.solution_steps,
            )
            assert verdict.accepted is True, f"{candidate.problem.slug} 미수용: {verdict.reasons}"
            assert verdict.verification == "verified"

    def test_gate_rejects_wrong_answer(self) -> None:
        candidate = AdditionLawSkeletonGenerator().generate(_addition_spec())
        assert candidate is not None
        broken_answer = "9999/10000"
        verdict = evaluate_equivalent_candidate(
            _addition_spec(),
            candidate.problem.model_copy(update={"answer": broken_answer}),
            provenance=candidate.provenance,
            conditions=candidate.conditions,
            answer_map={"y": broken_answer},
            solution_steps=candidate.solution_steps,
        )
        assert verdict.accepted is False
        assert any("Tier1" in r for r in verdict.reasons)


class TestAdditionShape:
    def test_question_format_and_no_choices(self) -> None:
        gen = AdditionLawSkeletonGenerator()
        for candidate in _drain(gen, _addition_spec(), 20):
            assert candidate.problem.question_format == QuestionFormat.단답형
            assert candidate.problem.choices is None
            assert candidate.problem.distractor_map is None

    def test_concept_tags_resolve_via_legacy_437_space(self) -> None:
        candidate = AdditionLawSkeletonGenerator().generate(_addition_spec())
        assert candidate is not None
        assert len(candidate.concept_tags) == 1
        assert candidate.concept_tags[0].concept_src_id == "H:12확통02-02"

    def test_no_unverified_glyphs_in_both_fields(self) -> None:
        for candidate in _drain(AdditionLawSkeletonGenerator(), _addition_spec(), 400):
            _assert_no_bad_glyphs(candidate)


class TestComplementPool:
    def test_pool_nonempty_and_unique(self) -> None:
        pool = _build_complement_pool()
        assert len(pool) >= 50
        keys = {(s.n, s.a) for s in pool}
        assert len(keys) == len(pool)

    def test_answer_matches_independent_recompute(self) -> None:
        for skeleton in _build_complement_pool():
            assert skeleton.answer == 1 - Fraction(skeleton.a, skeleton.n)

    def test_generation_exhausts_to_none(self) -> None:
        pool_size = len(_build_complement_pool())
        gen = ComplementLawSkeletonGenerator()
        drained = _drain(gen, _complement_spec(), pool_size + 5)
        assert len(drained) == pool_size
        assert gen.generate(_complement_spec()) is None


class TestComplementAcceptance:
    def test_all_pass_acceptance_gate(self) -> None:
        pool_size = len(_build_complement_pool())
        candidates = _drain(ComplementLawSkeletonGenerator(), _complement_spec(), pool_size)
        assert len(candidates) == pool_size
        for candidate in candidates:
            verdict = evaluate_equivalent_candidate(
                _complement_spec(),
                candidate.problem,
                provenance=candidate.provenance,
                conditions=candidate.conditions,
                answer_map=candidate.answer_map,
                solution_steps=candidate.solution_steps,
            )
            assert verdict.accepted is True, f"{candidate.problem.slug} 미수용: {verdict.reasons}"
            assert verdict.verification == "verified"

    def test_gate_rejects_wrong_answer(self) -> None:
        candidate = ComplementLawSkeletonGenerator().generate(_complement_spec())
        assert candidate is not None
        broken_answer = "9999/10000"
        verdict = evaluate_equivalent_candidate(
            _complement_spec(),
            candidate.problem.model_copy(update={"answer": broken_answer}),
            provenance=candidate.provenance,
            conditions=candidate.conditions,
            answer_map={"y": broken_answer},
            solution_steps=candidate.solution_steps,
        )
        assert verdict.accepted is False
        assert any("Tier1" in r for r in verdict.reasons)


class TestComplementShape:
    def test_concept_tags_resolve_via_legacy_437_space(self) -> None:
        candidate = ComplementLawSkeletonGenerator().generate(_complement_spec())
        assert candidate is not None
        assert len(candidate.concept_tags) == 1
        assert candidate.concept_tags[0].concept_src_id == "H:12확통02-03"

    def test_no_unverified_glyphs_in_both_fields(self) -> None:
        pool_size = len(_build_complement_pool())
        for candidate in _drain(ComplementLawSkeletonGenerator(), _complement_spec(), pool_size):
            _assert_no_bad_glyphs(candidate)


class TestMultiplicationPool:
    def test_pool_nonempty_and_unique(self) -> None:
        pool = _build_multiplication_pool()
        assert len(pool) >= 500
        keys = {(s.n, s.a, s.m, s.c) for s in pool}
        assert len(keys) == len(pool)

    def test_answer_matches_independent_recompute(self) -> None:
        for skeleton in _build_multiplication_pool()[:400]:
            expected = Fraction(skeleton.a, skeleton.n) * Fraction(skeleton.c, skeleton.m)
            assert skeleton.answer == expected

    def test_generation_exhausts_to_none(self) -> None:
        pool_size = len(_build_multiplication_pool())
        gen = MultiplicationLawSkeletonGenerator()
        drained = _drain(gen, _multiplication_spec(), pool_size + 5)
        assert len(drained) == pool_size
        assert gen.generate(_multiplication_spec()) is None


class TestMultiplicationAcceptance:
    def test_all_pass_acceptance_gate(self) -> None:
        candidates = _drain(MultiplicationLawSkeletonGenerator(), _multiplication_spec(), 400)
        assert len(candidates) == 400
        for candidate in candidates:
            verdict = evaluate_equivalent_candidate(
                _multiplication_spec(),
                candidate.problem,
                provenance=candidate.provenance,
                conditions=candidate.conditions,
                answer_map=candidate.answer_map,
                solution_steps=candidate.solution_steps,
            )
            assert verdict.accepted is True, f"{candidate.problem.slug} 미수용: {verdict.reasons}"
            assert verdict.verification == "verified"

    def test_gate_rejects_wrong_answer(self) -> None:
        candidate = MultiplicationLawSkeletonGenerator().generate(_multiplication_spec())
        assert candidate is not None
        broken_answer = "9999/10000"
        verdict = evaluate_equivalent_candidate(
            _multiplication_spec(),
            candidate.problem.model_copy(update={"answer": broken_answer}),
            provenance=candidate.provenance,
            conditions=candidate.conditions,
            answer_map={"y": broken_answer},
            solution_steps=candidate.solution_steps,
        )
        assert verdict.accepted is False
        assert any("Tier1" in r for r in verdict.reasons)


class TestMultiplicationShape:
    def test_question_format_and_no_choices(self) -> None:
        gen = MultiplicationLawSkeletonGenerator()
        for candidate in _drain(gen, _multiplication_spec(), 20):
            assert candidate.problem.question_format == QuestionFormat.단답형
            assert candidate.problem.choices is None
            assert candidate.problem.distractor_map is None

    def test_concept_tags_resolve_via_legacy_437_space(self) -> None:
        candidate = MultiplicationLawSkeletonGenerator().generate(_multiplication_spec())
        assert candidate is not None
        assert len(candidate.concept_tags) == 1
        assert candidate.concept_tags[0].concept_src_id == "H:12확통02-06"

    def test_no_unverified_glyphs_in_both_fields(self) -> None:
        for candidate in _drain(MultiplicationLawSkeletonGenerator(), _multiplication_spec(), 400):
            _assert_no_bad_glyphs(candidate)
