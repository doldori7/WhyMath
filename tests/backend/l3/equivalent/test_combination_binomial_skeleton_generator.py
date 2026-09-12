"""고등 경우의 수 — 중복조합·이항정리 계수 스켈레톤 생성기 단위테스트(hermetic).

`RepeatedCombinationSkeletonGenerator`·`BinomialCoefficientSkeletonGenerator`가 ① 전건
S2-a 4종 게이트 통과 ② answer가 독립 재계산(math.comb 기반)과 일치 ③ 풀 유일·소진 시
None ④ concept_src_id가 legacy 437 공간(H:12확통01-02/H:12확통01-03)에 실존해 정상
태깅됨 ⑤ question_text·answer_explanation 양쪽 모두 신규 Unicode 글리프 미사용을
못 박는다. LLM·DB·PG 0(순수 결정론).
"""

from __future__ import annotations

import math

import pytest

from whymath_backend.l3.equivalent.acceptance import (
    EquivalenceSpec,
    evaluate_equivalent_candidate,
)
from whymath_backend.l3.equivalent.combination_binomial_skeleton_generator import (
    BinomialCoefficientSkeletonGenerator,
    RepeatedCombinationSkeletonGenerator,
    _build_binomial_pool,
    _build_repeated_combination_pool,
)
from whymath_backend.l3.equivalent.generator import CandidateProblem
from whymath_backend.schema.enums import QuestionFormat

# PB-13: backend 잡 35분 상한 초과 해소 — PR 상시 경로에서 분리하고 전용 잡
# corpus-authoring(야간 + 생성기·배치 변경 PR)이 돌린다. 비활성화가 아니다.
pytestmark = pytest.mark.corpus_authoring

_REPEATED_COMBINATION_STANDARD = "[12확통01-02]"
_BINOMIAL_STANDARD = "[12확통01-03]"

_BAD_GLYPHS = ("Σ", "α", "β", "²", "³")


def _repeated_combination_spec() -> EquivalenceSpec:
    return EquivalenceSpec(
        achievement_standard_codes=frozenset({_REPEATED_COMBINATION_STANDARD}),
        target_misconception_ids=frozenset(),
        difficulty_overall=2.3,
        answer_format=None,
    )


def _binomial_spec() -> EquivalenceSpec:
    return EquivalenceSpec(
        achievement_standard_codes=frozenset({_BINOMIAL_STANDARD}),
        target_misconception_ids=frozenset(),
        difficulty_overall=2.4,
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


class TestRepeatedCombinationPool:
    def test_pool_nonempty_and_unique(self) -> None:
        pool = _build_repeated_combination_pool()
        assert len(pool) == 56  # 7(n=2..8) * 8(r=1..8)
        keys = {(s.n, s.r) for s in pool}
        assert len(keys) == len(pool)

    def test_answer_matches_independent_recompute(self) -> None:
        for skeleton in _build_repeated_combination_pool():
            expected = math.comb(skeleton.n + skeleton.r - 1, skeleton.r)
            assert skeleton.answer == expected

    def test_generation_exhausts_to_none(self) -> None:
        pool_size = len(_build_repeated_combination_pool())
        gen = RepeatedCombinationSkeletonGenerator()
        drained = _drain(gen, _repeated_combination_spec(), pool_size + 5)
        assert len(drained) == pool_size
        assert gen.generate(_repeated_combination_spec()) is None


class TestRepeatedCombinationAcceptance:
    def test_all_pass_acceptance_gate(self) -> None:
        candidates = _drain(
            RepeatedCombinationSkeletonGenerator(), _repeated_combination_spec(), 56
        )
        assert len(candidates) == 56
        for candidate in candidates:
            verdict = evaluate_equivalent_candidate(
                _repeated_combination_spec(),
                candidate.problem,
                provenance=candidate.provenance,
                conditions=candidate.conditions,
                answer_map=candidate.answer_map,
                solution_steps=candidate.solution_steps,
            )
            assert verdict.accepted is True, f"{candidate.problem.slug} 미수용: {verdict.reasons}"
            assert verdict.verification == "verified"

    def test_gate_rejects_wrong_answer(self) -> None:
        candidate = RepeatedCombinationSkeletonGenerator().generate(_repeated_combination_spec())
        assert candidate is not None
        broken_answer = str(int(candidate.problem.answer) + 1)
        verdict = evaluate_equivalent_candidate(
            _repeated_combination_spec(),
            candidate.problem.model_copy(update={"answer": broken_answer}),
            provenance=candidate.provenance,
            conditions=candidate.conditions,
            answer_map={"x": broken_answer},
            solution_steps=candidate.solution_steps,
        )
        assert verdict.accepted is False
        assert any("Tier1" in r for r in verdict.reasons)


class TestRepeatedCombinationShape:
    def test_question_format_and_no_choices(self) -> None:
        gen = RepeatedCombinationSkeletonGenerator()
        for candidate in _drain(gen, _repeated_combination_spec(), 20):
            assert candidate.problem.question_format == QuestionFormat.단답형
            assert candidate.problem.choices is None
            assert candidate.problem.distractor_map is None

    def test_concept_tags_resolve_via_legacy_437_space(self) -> None:
        candidate = RepeatedCombinationSkeletonGenerator().generate(_repeated_combination_spec())
        assert candidate is not None
        assert len(candidate.concept_tags) == 1
        assert candidate.concept_tags[0].concept_src_id == "H:12확통01-02"

    def test_no_unverified_glyphs_in_both_fields(self) -> None:
        for candidate in _drain(
            RepeatedCombinationSkeletonGenerator(), _repeated_combination_spec(), 56
        ):
            _assert_no_bad_glyphs(candidate)


class TestBinomialPool:
    def test_pool_nonempty_unique_and_excludes_trivial_ends(self) -> None:
        pool = _build_binomial_pool()
        assert len(pool) == sum(n - 1 for n in range(3, 13))
        keys = {(s.n, s.r) for s in pool}
        assert len(keys) == len(pool)
        for skeleton in pool:
            assert 1 <= skeleton.r <= skeleton.n - 1  # 자명 끝항(r=0/r=n) 제외.

    def test_answer_matches_independent_recompute(self) -> None:
        for skeleton in _build_binomial_pool():
            assert skeleton.answer == math.comb(skeleton.n, skeleton.r)

    def test_term_display_omits_exponent_one(self) -> None:
        for skeleton in _build_binomial_pool():
            term = skeleton.term_display
            if skeleton.n - skeleton.r == 1:
                assert "x^1" not in term
            if skeleton.r == 1:
                assert "y^1" not in term

    def test_generation_exhausts_to_none(self) -> None:
        pool_size = len(_build_binomial_pool())
        gen = BinomialCoefficientSkeletonGenerator()
        drained = _drain(gen, _binomial_spec(), pool_size + 5)
        assert len(drained) == pool_size
        assert gen.generate(_binomial_spec()) is None


class TestBinomialAcceptance:
    def test_all_pass_acceptance_gate(self) -> None:
        pool_size = len(_build_binomial_pool())
        candidates = _drain(BinomialCoefficientSkeletonGenerator(), _binomial_spec(), pool_size)
        assert len(candidates) == pool_size
        for candidate in candidates:
            verdict = evaluate_equivalent_candidate(
                _binomial_spec(),
                candidate.problem,
                provenance=candidate.provenance,
                conditions=candidate.conditions,
                answer_map=candidate.answer_map,
                solution_steps=candidate.solution_steps,
            )
            assert verdict.accepted is True, f"{candidate.problem.slug} 미수용: {verdict.reasons}"
            assert verdict.verification == "verified"

    def test_gate_rejects_wrong_answer(self) -> None:
        candidate = BinomialCoefficientSkeletonGenerator().generate(_binomial_spec())
        assert candidate is not None
        broken_answer = str(int(candidate.problem.answer) + 1)
        verdict = evaluate_equivalent_candidate(
            _binomial_spec(),
            candidate.problem.model_copy(update={"answer": broken_answer}),
            provenance=candidate.provenance,
            conditions=candidate.conditions,
            answer_map={"x": broken_answer},
            solution_steps=candidate.solution_steps,
        )
        assert verdict.accepted is False
        assert any("Tier1" in r for r in verdict.reasons)


class TestBinomialShape:
    def test_question_format_and_no_choices(self) -> None:
        gen = BinomialCoefficientSkeletonGenerator()
        for candidate in _drain(gen, _binomial_spec(), 20):
            assert candidate.problem.question_format == QuestionFormat.단답형
            assert candidate.problem.choices is None
            assert candidate.problem.distractor_map is None

    def test_concept_tags_resolve_via_legacy_437_space(self) -> None:
        candidate = BinomialCoefficientSkeletonGenerator().generate(_binomial_spec())
        assert candidate is not None
        assert len(candidate.concept_tags) == 1
        assert candidate.concept_tags[0].concept_src_id == "H:12확통01-03"

    def test_no_unverified_glyphs_in_both_fields(self) -> None:
        pool_size = len(_build_binomial_pool())
        for candidate in _drain(
            BinomialCoefficientSkeletonGenerator(), _binomial_spec(), pool_size
        ):
            _assert_no_bad_glyphs(candidate)
