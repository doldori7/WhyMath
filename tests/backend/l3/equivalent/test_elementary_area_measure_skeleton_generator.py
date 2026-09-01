"""초등 도형과 측정 — 넓이 단위 환산·직육면체 겉넓이 스켈레톤 생성기 단위테스트(hermetic).

`AreaUnitConversionSkeletonGenerator`·`RectangularPrismSurfaceAreaSkeletonGenerator`가 ①
전건 S2-a 4종 게이트 통과 ② answer가 독립 재계산과 일치 ③ 풀 유일·소진 시 None ④ `pair`
필터로 밴드가 실제로 분리됨(2026-08-05 elementary_addsub 사고 재발 방지 회귀 봉인) ⑤ CJK
제곱단위 글리프(㎠·㎡·㎢) 미사용 — ASCII cm^2/m^2/km^2만 사용 ⑥ 개념 태깅·위생 게이트
무오탐을 못 박는다. LLM·DB·PG 0(순수 결정론).
"""

from __future__ import annotations

from whymath_backend.l3.equivalent.acceptance import (
    EquivalenceSpec,
    evaluate_equivalent_candidate,
)
from whymath_backend.l3.equivalent.elementary_area_measure_skeleton_generator import (
    AreaUnitConversionSkeletonGenerator,
    RectangularPrismSurfaceAreaSkeletonGenerator,
    _build_conversion_pool,
    _build_surface_area_pool,
)
from whymath_backend.l3.equivalent.generator import CandidateProblem
from whymath_backend.schema.enums import QuestionFormat

_CONVERSION_STANDARD = "[6수03-12]"
_SURFACE_AREA_STANDARD = "[6수03-17]"


def _conversion_spec() -> EquivalenceSpec:
    return EquivalenceSpec(
        achievement_standard_codes=frozenset({_CONVERSION_STANDARD}),
        target_misconception_ids=frozenset(),
        difficulty_overall=1.6,
        answer_format=None,
    )


def _surface_area_spec() -> EquivalenceSpec:
    return EquivalenceSpec(
        achievement_standard_codes=frozenset({_SURFACE_AREA_STANDARD}),
        target_misconception_ids=frozenset(),
        difficulty_overall=2.2,
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


class TestConversionPool:
    def test_pool_nonempty_and_unique(self) -> None:
        pool = _build_conversion_pool()
        assert len(pool) >= 60
        keys = {(s.pair, s.big_value) for s in pool}
        assert len(keys) == len(pool)

    def test_answer_matches_independent_recompute(self) -> None:
        for skeleton in _build_conversion_pool():
            assert skeleton.answer == skeleton.big_value * skeleton.factor

    def test_pair_filter_restricts_output_and_ids_stay_unique_across_bands(self) -> None:
        """`pair` 필터가 실제로 밴드를 분리한다 — 2026-08-05 사고 회귀 봉인(quad_ineq 미러)."""
        ids_by_pair: dict[str, set] = {}
        for pair in ("m_to_cm", "km_to_m"):
            candidates = _drain(
                AreaUnitConversionSkeletonGenerator(pair=pair), _conversion_spec(), 15
            )
            assert len(candidates) == 15
            expected_unit = "m^2" if pair == "m_to_cm" else "km^2"
            assert all(expected_unit in c.problem.question_text for c in candidates), pair
            ids_by_pair[pair] = {c.problem.problem_id for c in candidates}
        assert not (
            ids_by_pair["m_to_cm"] & ids_by_pair["km_to_m"]
        ), "밴드 간 problem_id 중복 — 밴드 분리 실패(회귀)."

    def test_generation_exhausts_to_none_per_pair(self) -> None:
        for pair in ("m_to_cm", "km_to_m"):
            pool_size = len([s for s in _build_conversion_pool() if s.pair == pair])
            gen = AreaUnitConversionSkeletonGenerator(pair=pair)
            drained = _drain(gen, _conversion_spec(), pool_size + 5)
            assert len(drained) == pool_size, pair
            assert gen.generate(_conversion_spec()) is None


class TestConversionAcceptance:
    def test_all_pass_acceptance_gate(self) -> None:
        candidates = _drain(AreaUnitConversionSkeletonGenerator(), _conversion_spec(), 70)
        assert len(candidates) >= 60
        for candidate in candidates:
            verdict = evaluate_equivalent_candidate(
                _conversion_spec(),
                candidate.problem,
                provenance=candidate.provenance,
                conditions=candidate.conditions,
                answer_map=candidate.answer_map,
                solution_steps=candidate.solution_steps,
            )
            assert verdict.accepted is True, f"{candidate.problem.slug} 미수용: {verdict.reasons}"
            assert verdict.verification == "verified"

    def test_gate_rejects_wrong_answer(self) -> None:
        candidate = AreaUnitConversionSkeletonGenerator().generate(_conversion_spec())
        assert candidate is not None
        broken_answer = str(int(candidate.problem.answer) + 1)
        verdict = evaluate_equivalent_candidate(
            _conversion_spec(),
            candidate.problem.model_copy(update={"answer": broken_answer}),
            provenance=candidate.provenance,
            conditions=candidate.conditions,
            answer_map={"x": broken_answer},
            solution_steps=candidate.solution_steps,
        )
        assert verdict.accepted is False
        assert any("Tier1" in r for r in verdict.reasons)


class TestConversionShape:
    def test_question_format_and_no_choices(self) -> None:
        for candidate in _drain(AreaUnitConversionSkeletonGenerator(), _conversion_spec(), 20):
            assert candidate.problem.question_format == QuestionFormat.단답형
            assert candidate.problem.choices is None
            assert candidate.problem.distractor_map is None

    def test_concept_tags_resolve_via_legacy_437_space(self) -> None:
        candidate = AreaUnitConversionSkeletonGenerator().generate(_conversion_spec())
        assert candidate is not None
        assert len(candidate.concept_tags) == 1
        assert candidate.concept_tags[0].concept_src_id == "ME2"

    def test_no_cjk_square_unit_glyphs(self) -> None:
        """㎠·㎡·㎢ 등 CJK 제곱단위 합성 글리프 미사용 — ASCII cm^2/m^2/km^2만. 이 생성기의
        핵심 실측 발견(코퍼스·베이스라인 어디에도 없는 신규 글리프라 즉시 게이트 거부됨)."""
        for candidate in _drain(AreaUnitConversionSkeletonGenerator(), _conversion_spec(), 70):
            text = candidate.problem.question_text + candidate.problem.answer_explanation
            assert "㎠" not in text
            assert "㎡" not in text
            assert "㎢" not in text
            assert "²" not in text


class TestSurfaceAreaPool:
    def test_pool_nonempty_and_unique(self) -> None:
        pool = _build_surface_area_pool()
        assert len(pool) >= 200
        keys = {(s.length, s.width, s.height) for s in pool}
        assert len(keys) == len(pool)
        for skeleton in pool:
            assert skeleton.length <= skeleton.width <= skeleton.height

    def test_answer_matches_independent_recompute(self) -> None:
        for skeleton in _build_surface_area_pool()[:150]:
            expected = 2 * (
                skeleton.length * skeleton.width
                + skeleton.length * skeleton.height
                + skeleton.width * skeleton.height
            )
            assert skeleton.answer == expected

    def test_generation_exhausts_to_none(self) -> None:
        pool_size = len(_build_surface_area_pool())
        gen = RectangularPrismSurfaceAreaSkeletonGenerator()
        drained = _drain(gen, _surface_area_spec(), pool_size + 5)
        assert len(drained) == pool_size
        assert gen.generate(_surface_area_spec()) is None


class TestSurfaceAreaAcceptance:
    def test_all_pass_acceptance_gate(self) -> None:
        candidates = _drain(
            RectangularPrismSurfaceAreaSkeletonGenerator(), _surface_area_spec(), 200
        )
        assert len(candidates) >= 200
        for candidate in candidates:
            verdict = evaluate_equivalent_candidate(
                _surface_area_spec(),
                candidate.problem,
                provenance=candidate.provenance,
                conditions=candidate.conditions,
                answer_map=candidate.answer_map,
                solution_steps=candidate.solution_steps,
            )
            assert verdict.accepted is True, f"{candidate.problem.slug} 미수용: {verdict.reasons}"
            assert verdict.verification == "verified"

    def test_gate_rejects_wrong_answer(self) -> None:
        candidate = RectangularPrismSurfaceAreaSkeletonGenerator().generate(_surface_area_spec())
        assert candidate is not None
        broken_answer = str(int(candidate.problem.answer) + 1)
        verdict = evaluate_equivalent_candidate(
            _surface_area_spec(),
            candidate.problem.model_copy(update={"answer": broken_answer}),
            provenance=candidate.provenance,
            conditions=candidate.conditions,
            answer_map={"x": broken_answer},
            solution_steps=candidate.solution_steps,
        )
        assert verdict.accepted is False
        assert any("Tier1" in r for r in verdict.reasons)


class TestSurfaceAreaShape:
    def test_question_format_and_no_choices(self) -> None:
        gen = RectangularPrismSurfaceAreaSkeletonGenerator()
        for candidate in _drain(gen, _surface_area_spec(), 20):
            assert candidate.problem.question_format == QuestionFormat.단답형
            assert candidate.problem.choices is None
            assert candidate.problem.distractor_map is None

    def test_concept_tags_resolve_via_legacy_437_space(self) -> None:
        candidate = RectangularPrismSurfaceAreaSkeletonGenerator().generate(_surface_area_spec())
        assert candidate is not None
        assert len(candidate.concept_tags) == 1
        assert candidate.concept_tags[0].concept_src_id == "ME7"

    def test_no_unverified_glyphs(self) -> None:
        gen = RectangularPrismSurfaceAreaSkeletonGenerator()
        for candidate in _drain(gen, _surface_area_spec(), 200):
            text = candidate.problem.question_text
            assert "㎠" not in text
            assert "²" not in text
