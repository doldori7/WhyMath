"""초등 길이·들이·무게 단위 관계 스켈레톤 생성기 단위테스트(hermetic).

`MeasurementUnitConversionSkeletonGenerator`가 ① 전건 S2-a 4종 게이트 통과 ② answer가
독립 재계산과 일치 ③ 풀 유일·소진 시 None ④ `pair` 필터로 밴드가 실제로 분리되고 성취기준
코드도 함께 결정됨(mm_to_cm·km_to_m은 같은 코드 공유, L_to_mL·kg_to_g는 각각 별도 코드
— gcd_lcm·conic_section_focus 생성기의 "kind→코드" 패턴 재실증) ⑤ concept_src_id가 legacy
437 공간(L5/V1/W1)에 실존 ⑥ question_text·answer_explanation 양쪽 모두 신규 Unicode
글리프 미사용을 못 박는다. LLM·DB·PG 0(순수 결정론).
"""

from __future__ import annotations

from whymath_backend.l3.equivalent.acceptance import (
    EquivalenceSpec,
    evaluate_equivalent_candidate,
)
from whymath_backend.l3.equivalent.generator import CandidateProblem
from whymath_backend.l3.equivalent.measurement_unit_conversion_skeleton_generator import (
    LENGTH_STANDARD_CODE,
    MASS_STANDARD_CODE,
    VOLUME_STANDARD_CODE,
    MeasurementUnitConversionSkeletonGenerator,
    _build_pool,
)
from whymath_backend.schema.enums import QuestionFormat

MM_CM = "mm_to_cm"
KM_M = "km_to_m"
L_ML = "L_to_mL"
KG_G = "kg_to_g"

_BAD_GLYPHS = ("Σ", "α", "β", "²", "³", "∩", "∪", "㎠", "㎡", "㎢", "㎤", "㎥")

_PAIR_TO_CODE = {
    MM_CM: LENGTH_STANDARD_CODE,
    KM_M: LENGTH_STANDARD_CODE,
    L_ML: VOLUME_STANDARD_CODE,
    KG_G: MASS_STANDARD_CODE,
}
_PAIR_TO_CONCEPT = {MM_CM: "L5", KM_M: "L5", L_ML: "V1", KG_G: "W1"}
_PAIR_TO_FACTOR = {MM_CM: 10, KM_M: 1_000, L_ML: 1_000, KG_G: 1_000}


def _spec(pair: str) -> EquivalenceSpec:
    return EquivalenceSpec(
        achievement_standard_codes=frozenset({_PAIR_TO_CODE[pair]}),
        target_misconception_ids=frozenset(),
        difficulty_overall=1.9,
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


class TestPool:
    def test_pool_nonempty_and_unique(self) -> None:
        pool = _build_pool()
        assert len(pool) >= 180  # 100(mm_to_cm)+20(km_to_m)+30(L_to_mL)+30(kg_to_g).
        keys = {(s.pair, s.big_value) for s in pool}
        assert len(keys) == len(pool)

    def test_answer_matches_independent_recompute(self) -> None:
        for skeleton in _build_pool():
            expected = skeleton.big_value * _PAIR_TO_FACTOR[skeleton.pair]
            assert skeleton.answer == expected

    def test_generation_exhausts_to_none_per_pair(self) -> None:
        for pair in (MM_CM, KM_M, L_ML, KG_G):
            pool_size = len([s for s in _build_pool() if s.pair == pair])
            gen = MeasurementUnitConversionSkeletonGenerator(pair=pair)  # type: ignore[arg-type]
            drained = _drain(gen, _spec(pair), pool_size + 5)
            assert len(drained) == pool_size, pair
            assert gen.generate(_spec(pair)) is None


class TestPairFilterDeterminesCode:
    def test_pair_filter_restricts_output_and_sets_expected_code(self) -> None:
        """`pair` 필터가 실제로 밴드를 분리하고 코드도 함께 결정한다 — kind→코드 패턴 재실증."""
        ids_by_pair: dict[str, set] = {}
        for pair in (MM_CM, KM_M, L_ML, KG_G):
            candidates = _drain(
                MeasurementUnitConversionSkeletonGenerator(pair=pair),  # type: ignore[arg-type]
                _spec(pair),
                10,
            )
            assert len(candidates) == 10
            assert all(
                c.problem.achievement_standard_codes == [_PAIR_TO_CODE[pair]] for c in candidates
            ), pair
            assert all(
                c.concept_tags[0].concept_src_id == _PAIR_TO_CONCEPT[pair] for c in candidates
            ), pair
            ids_by_pair[pair] = {c.problem.problem_id for c in candidates}
        all_ids = [i for ids in ids_by_pair.values() for i in ids]
        assert len(all_ids) == len(set(all_ids)), "밴드 간 problem_id 중복 — 밴드 분리 실패(회귀)."

    def test_mm_to_cm_and_km_to_m_share_length_code(self) -> None:
        assert _PAIR_TO_CODE[MM_CM] == _PAIR_TO_CODE[KM_M] == LENGTH_STANDARD_CODE


class TestAcceptance:
    def test_all_pass_acceptance_gate(self) -> None:
        for pair in (MM_CM, KM_M, L_ML, KG_G):
            candidates = _drain(
                MeasurementUnitConversionSkeletonGenerator(pair=pair),  # type: ignore[arg-type]
                _spec(pair),
                200,
            )
            assert len(candidates) >= 20
            for candidate in candidates:
                verdict = evaluate_equivalent_candidate(
                    _spec(pair),
                    candidate.problem,
                    provenance=candidate.provenance,
                    conditions=candidate.conditions,
                    answer_map=candidate.answer_map,
                    solution_steps=candidate.solution_steps,
                )
                label = f"{pair}/{candidate.problem.slug}"
                assert verdict.accepted is True, f"{label}: {verdict.reasons}"
                assert verdict.verification == "verified"

    def test_gate_rejects_wrong_answer(self) -> None:
        candidate = MeasurementUnitConversionSkeletonGenerator(pair=MM_CM).generate(  # type: ignore[arg-type]
            _spec(MM_CM)
        )
        assert candidate is not None
        broken_answer = str(int(candidate.problem.answer) + 1)
        verdict = evaluate_equivalent_candidate(
            _spec(MM_CM),
            candidate.problem.model_copy(update={"answer": broken_answer}),
            provenance=candidate.provenance,
            conditions=candidate.conditions,
            answer_map={"x": broken_answer},
            solution_steps=candidate.solution_steps,
        )
        assert verdict.accepted is False
        assert any("Tier1" in r for r in verdict.reasons)


class TestShape:
    def test_question_format_and_no_choices(self) -> None:
        gen = MeasurementUnitConversionSkeletonGenerator(pair=KG_G)  # type: ignore[arg-type]
        for candidate in _drain(gen, _spec(KG_G), 20):
            assert candidate.problem.question_format == QuestionFormat.단답형
            assert candidate.problem.choices is None
            assert candidate.problem.distractor_map is None

    def test_no_unverified_glyphs_in_both_fields(self) -> None:
        for pair in (MM_CM, KM_M, L_ML, KG_G):
            gen = MeasurementUnitConversionSkeletonGenerator(pair=pair)  # type: ignore[arg-type]
            for candidate in _drain(gen, _spec(pair), 50):
                _assert_no_bad_glyphs(candidate)
