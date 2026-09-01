"""초등 도형과 측정 — 직육면체 부피·부피 단위·원주 스켈레톤 생성기 단위테스트(hermetic).

`RectangularPrismVolumeSkeletonGenerator`·`VolumeUnitConversionSkeletonGenerator`·
`CircleCircumferenceSkeletonGenerator`가 ① 전건 S2-a 4종 게이트 통과 ② answer가 독립
재계산과 일치 ③ 풀 유일·소진 시 None ④ concept_src_id가 legacy 437 공간(ME9/ME8/ME5)에
실존해 정상 태깅됨 ⑤ question_text·answer_explanation 양쪽 모두 신규 Unicode 글리프
미사용(2026-08-07 conic_section_focus 사고 재발 방지 — 두 필드 모두 확인) ⑥ 원주 생성기의
소수 답이 부동소수점 오차 없이 정수 연산만으로 산출됨(diameter*314 정수 스케일)을 못 박는다.
LLM·DB·PG 0(순수 결정론).
"""

from __future__ import annotations

from whymath_backend.l3.equivalent.acceptance import (
    EquivalenceSpec,
    evaluate_equivalent_candidate,
)
from whymath_backend.l3.equivalent.elementary_volume_measure_skeleton_generator import (
    CircleCircumferenceSkeletonGenerator,
    RectangularPrismVolumeSkeletonGenerator,
    VolumeUnitConversionSkeletonGenerator,
    _build_circumference_pool,
    _build_volume_pool,
    _build_volume_unit_pool,
)
from whymath_backend.l3.equivalent.generator import CandidateProblem
from whymath_backend.schema.enums import AnswerFormat, QuestionFormat

_VOLUME_STANDARD = "[6수03-19]"
_VOLUME_UNIT_STANDARD = "[6수03-18]"
_CIRCUMFERENCE_STANDARD = "[6수03-15]"

_BAD_GLYPHS = ("Σ", "α", "β", "²", "³", "㎠", "㎡", "㎢", "㎤", "㎥")


def _volume_spec() -> EquivalenceSpec:
    return EquivalenceSpec(
        achievement_standard_codes=frozenset({_VOLUME_STANDARD}),
        target_misconception_ids=frozenset(),
        difficulty_overall=2.0,
        answer_format=None,
    )


def _volume_unit_spec() -> EquivalenceSpec:
    return EquivalenceSpec(
        achievement_standard_codes=frozenset({_VOLUME_UNIT_STANDARD}),
        target_misconception_ids=frozenset(),
        difficulty_overall=1.8,
        answer_format=None,
    )


def _circumference_spec() -> EquivalenceSpec:
    return EquivalenceSpec(
        achievement_standard_codes=frozenset({_CIRCUMFERENCE_STANDARD}),
        target_misconception_ids=frozenset(),
        difficulty_overall=2.1,
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


class TestVolumePool:
    def test_pool_nonempty_unique_and_ordered(self) -> None:
        pool = _build_volume_pool()
        assert len(pool) >= 200
        keys = {(s.length, s.width, s.height) for s in pool}
        assert len(keys) == len(pool)
        for skeleton in pool:
            assert skeleton.length <= skeleton.width <= skeleton.height

    def test_answer_matches_independent_recompute(self) -> None:
        for skeleton in _build_volume_pool()[:150]:
            assert skeleton.answer == skeleton.length * skeleton.width * skeleton.height

    def test_generation_exhausts_to_none(self) -> None:
        pool_size = len(_build_volume_pool())
        gen = RectangularPrismVolumeSkeletonGenerator()
        drained = _drain(gen, _volume_spec(), pool_size + 5)
        assert len(drained) == pool_size
        assert gen.generate(_volume_spec()) is None


class TestVolumeAcceptance:
    def test_all_pass_acceptance_gate(self) -> None:
        candidates = _drain(RectangularPrismVolumeSkeletonGenerator(), _volume_spec(), 200)
        assert len(candidates) >= 200
        for candidate in candidates:
            verdict = evaluate_equivalent_candidate(
                _volume_spec(),
                candidate.problem,
                provenance=candidate.provenance,
                conditions=candidate.conditions,
                answer_map=candidate.answer_map,
                solution_steps=candidate.solution_steps,
            )
            assert verdict.accepted is True, f"{candidate.problem.slug} 미수용: {verdict.reasons}"
            assert verdict.verification == "verified"

    def test_gate_rejects_wrong_answer(self) -> None:
        candidate = RectangularPrismVolumeSkeletonGenerator().generate(_volume_spec())
        assert candidate is not None
        broken_answer = str(int(candidate.problem.answer) + 1)
        verdict = evaluate_equivalent_candidate(
            _volume_spec(),
            candidate.problem.model_copy(update={"answer": broken_answer}),
            provenance=candidate.provenance,
            conditions=candidate.conditions,
            answer_map={"x": broken_answer},
            solution_steps=candidate.solution_steps,
        )
        assert verdict.accepted is False
        assert any("Tier1" in r for r in verdict.reasons)


class TestVolumeShape:
    def test_question_format_and_no_choices(self) -> None:
        gen = RectangularPrismVolumeSkeletonGenerator()
        for candidate in _drain(gen, _volume_spec(), 20):
            assert candidate.problem.question_format == QuestionFormat.단답형
            assert candidate.problem.choices is None
            assert candidate.problem.distractor_map is None

    def test_concept_tags_resolve_via_legacy_437_space(self) -> None:
        candidate = RectangularPrismVolumeSkeletonGenerator().generate(_volume_spec())
        assert candidate is not None
        assert len(candidate.concept_tags) == 1
        assert candidate.concept_tags[0].concept_src_id == "ME9"

    def test_no_unverified_glyphs_in_both_fields(self) -> None:
        for candidate in _drain(RectangularPrismVolumeSkeletonGenerator(), _volume_spec(), 200):
            _assert_no_bad_glyphs(candidate)


class TestVolumeUnitPool:
    def test_pool_nonempty_and_unique(self) -> None:
        pool = _build_volume_unit_pool()
        assert len(pool) == 50
        keys = {s.big_value for s in pool}
        assert len(keys) == len(pool)

    def test_answer_matches_independent_recompute(self) -> None:
        for skeleton in _build_volume_unit_pool():
            assert skeleton.answer == skeleton.big_value * 1_000_000

    def test_generation_exhausts_to_none(self) -> None:
        pool_size = len(_build_volume_unit_pool())
        gen = VolumeUnitConversionSkeletonGenerator()
        drained = _drain(gen, _volume_unit_spec(), pool_size + 5)
        assert len(drained) == pool_size
        assert gen.generate(_volume_unit_spec()) is None


class TestVolumeUnitAcceptance:
    def test_all_pass_acceptance_gate(self) -> None:
        candidates = _drain(VolumeUnitConversionSkeletonGenerator(), _volume_unit_spec(), 50)
        assert len(candidates) == 50
        for candidate in candidates:
            verdict = evaluate_equivalent_candidate(
                _volume_unit_spec(),
                candidate.problem,
                provenance=candidate.provenance,
                conditions=candidate.conditions,
                answer_map=candidate.answer_map,
                solution_steps=candidate.solution_steps,
            )
            assert verdict.accepted is True, f"{candidate.problem.slug} 미수용: {verdict.reasons}"
            assert verdict.verification == "verified"

    def test_gate_rejects_wrong_answer(self) -> None:
        candidate = VolumeUnitConversionSkeletonGenerator().generate(_volume_unit_spec())
        assert candidate is not None
        broken_answer = str(int(candidate.problem.answer) + 1)
        verdict = evaluate_equivalent_candidate(
            _volume_unit_spec(),
            candidate.problem.model_copy(update={"answer": broken_answer}),
            provenance=candidate.provenance,
            conditions=candidate.conditions,
            answer_map={"x": broken_answer},
            solution_steps=candidate.solution_steps,
        )
        assert verdict.accepted is False
        assert any("Tier1" in r for r in verdict.reasons)


class TestVolumeUnitShape:
    def test_concept_tags_resolve_via_legacy_437_space(self) -> None:
        candidate = VolumeUnitConversionSkeletonGenerator().generate(_volume_unit_spec())
        assert candidate is not None
        assert len(candidate.concept_tags) == 1
        assert candidate.concept_tags[0].concept_src_id == "ME8"

    def test_no_unverified_glyphs_in_both_fields(self) -> None:
        for candidate in _drain(VolumeUnitConversionSkeletonGenerator(), _volume_unit_spec(), 50):
            _assert_no_bad_glyphs(candidate)


class TestCircumferencePool:
    def test_pool_nonempty_and_unique(self) -> None:
        pool = _build_circumference_pool()
        assert len(pool) == 50
        keys = {s.diameter for s in pool}
        assert len(keys) == len(pool)

    def test_answer_cents_are_exact_integer_arithmetic(self) -> None:
        """핵심 설계 불변식 — 소수 답이 부동소수점을 전혀 거치지 않는다(diameter*314 정수
        스케일)."""
        for skeleton in _build_circumference_pool():
            assert skeleton.answer_cents == skeleton.diameter * 314
            assert isinstance(skeleton.answer_cents, int)

    def test_answer_matches_independent_recompute(self) -> None:
        for skeleton in _build_circumference_pool():
            whole, cents = divmod(skeleton.diameter * 314, 100)
            if cents == 0:
                expected = str(whole)
            elif cents % 10 == 0:
                expected = f"{whole}.{cents // 10}"
            else:
                expected = f"{whole}.{cents:02d}"
            assert skeleton.answer == expected

    def test_generation_exhausts_to_none(self) -> None:
        pool_size = len(_build_circumference_pool())
        gen = CircleCircumferenceSkeletonGenerator()
        drained = _drain(gen, _circumference_spec(), pool_size + 5)
        assert len(drained) == pool_size
        assert gen.generate(_circumference_spec()) is None


class TestCircumferenceAcceptance:
    def test_all_pass_acceptance_gate(self) -> None:
        candidates = _drain(CircleCircumferenceSkeletonGenerator(), _circumference_spec(), 50)
        assert len(candidates) == 50
        for candidate in candidates:
            verdict = evaluate_equivalent_candidate(
                _circumference_spec(),
                candidate.problem,
                provenance=candidate.provenance,
                conditions=candidate.conditions,
                answer_map=candidate.answer_map,
                solution_steps=candidate.solution_steps,
            )
            assert verdict.accepted is True, f"{candidate.problem.slug} 미수용: {verdict.reasons}"
            assert verdict.verification == "verified"

    def test_gate_rejects_wrong_answer(self) -> None:
        candidate = CircleCircumferenceSkeletonGenerator().generate(_circumference_spec())
        assert candidate is not None
        broken_answer = "9999.9"
        verdict = evaluate_equivalent_candidate(
            _circumference_spec(),
            candidate.problem.model_copy(update={"answer": broken_answer}),
            provenance=candidate.provenance,
            conditions=candidate.conditions,
            answer_map={"x": broken_answer},
            solution_steps=candidate.solution_steps,
        )
        assert verdict.accepted is False
        assert any("Tier1" in r for r in verdict.reasons)


class TestCircumferenceShape:
    def test_question_format_and_answer_format_is_real(self) -> None:
        gen = CircleCircumferenceSkeletonGenerator()
        for candidate in _drain(gen, _circumference_spec(), 20):
            assert candidate.problem.question_format == QuestionFormat.단답형
            assert candidate.problem.answer_format == AnswerFormat.실수
            assert candidate.problem.choices is None
            assert candidate.problem.distractor_map is None

    def test_concept_tags_resolve_via_legacy_437_space(self) -> None:
        candidate = CircleCircumferenceSkeletonGenerator().generate(_circumference_spec())
        assert candidate is not None
        assert len(candidate.concept_tags) == 1
        assert candidate.concept_tags[0].concept_src_id == "ME5"

    def test_no_unverified_glyphs_in_both_fields(self) -> None:
        for candidate in _drain(CircleCircumferenceSkeletonGenerator(), _circumference_spec(), 50):
            _assert_no_bad_glyphs(candidate)
