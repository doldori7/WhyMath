"""미적분(극값 객관식) 스켈레톤 생성기 — hermetic(LLM 0·결정론) 단위·성질 테스트.

핵심 성질(전수/표본), 극값-값 단답형 테스트 미러 + 객관식 고유:
  ① 후보는 전부 S2-a 게이트 통과(accepted·verified) — 결정론 코어가 곧 검증 가능성.
  ② 정답 derive_selected_root(독립 유도)와 정확히 일치 — 교차 검증.
  ③ 4지선다: 선지 4개 전부 상이·정답∈선지·distractor 3개.
  ④ 오답 귀속: 극대극소 혼동 1 + 값↔x좌표 혼동 2, 오개념 집합=주입 2종·전부 CATALOG 실재.
  ⑤ 극대극소 혼동 오답은 *반대 극값*(조건 이차방정식의 나머지 근)·값↔좌표 오답은 근이 아님.
  ⑥ distractor_codes 주입 필수(키 누락 시 ValueError)·개념/단원(H:12미적Ⅰ02-07·CALC-EXTREMUM-MC).
"""

from __future__ import annotations

import sympy

from whymath_backend.l3.equivalent.acceptance import (
    EquivalenceSpec,
    evaluate_equivalent_candidate,
)
from whymath_backend.l3.equivalent.calculus_skeleton_generator import (
    CalculusExtremumMCSkeletonGenerator,
)
from whymath_backend.l3.equivalent.canonicalize import canonical_signature
from whymath_backend.l3.equivalent.generator import (
    CandidateProblem,
    EquivalentProblemGenerator,
)
from whymath_backend.l3.verify_answer import derive_selected_root
from whymath_backend.l4.misconception.catalog import CATALOG_BY_ID

_STANDARD = "[12미적Ⅰ-02-07]"
_MAX_MIN = "extremum-max-min-confused"
_VALUE_VS_POINT = "extremum-value-vs-point-confused"
_CODES: dict[str, tuple[str, str]] = {
    "max_min": (_MAX_MIN, "select-opposite-extremum"),
    "value_vs_point": (_VALUE_VS_POINT, "report-x-coordinate-for-value"),
}
_TARGET = frozenset({_MAX_MIN, _VALUE_VS_POINT})


def _spec(**overrides: object) -> EquivalenceSpec:
    kwargs: dict[str, object] = {
        "achievement_standard_codes": frozenset({_STANDARD}),
        "target_misconception_ids": _TARGET,
        "difficulty_overall": 3.3,
        "answer_format": None,
    }
    kwargs.update(overrides)
    return EquivalenceSpec(**kwargs)  # type: ignore[arg-type]


def _gen(**kw: object) -> CalculusExtremumMCSkeletonGenerator:
    return CalculusExtremumMCSkeletonGenerator(_CODES, **kw)  # type: ignore[arg-type]


def _draw(generator: CalculusExtremumMCSkeletonGenerator, n: int) -> list[CandidateProblem]:
    out: list[CandidateProblem] = []
    for _ in range(n):
        candidate = generator.generate(_spec())
        assert candidate is not None
        out.append(candidate)
    return out


def _condition_roots(condition: str) -> set[int]:
    """조건 이차방정식(dummy x)의 정수근 집합 — 극값 쌍 {v1, v2}."""
    lhs = condition.split("=")[0]
    roots = sympy.solve(sympy.Eq(sympy.sympify(lhs, convert_xor=True), 0), sympy.Symbol("x"))
    return {int(r) for r in roots}


class TestSeatContract:
    def test_satisfies_generator_protocol(self) -> None:
        assert isinstance(_gen(), EquivalentProblemGenerator)

    def test_deterministic_sequence(self) -> None:
        a = [c.problem.slug for c in _draw(_gen(), 5)]
        b = [c.problem.slug for c in _draw(_gen(), 5)]
        assert a == b

    def test_pool_exhaustion_returns_none(self) -> None:
        gen = _gen()
        count = 0
        while gen.generate(_spec()) is not None:
            count += 1
            assert count < 1000
        assert count > 100
        assert gen.generate(_spec()) is None

    def test_missing_injection_key_rejected(self) -> None:
        # distractor_codes 주입 키 누락 → 즉시 ValueError(조용한 무매핑 금지).
        import pytest

        with pytest.raises(ValueError):
            CalculusExtremumMCSkeletonGenerator({"max_min": (_MAX_MIN, "select-opposite-extremum")})


class TestMathematicalSoundness:
    def test_all_candidates_pass_acceptance_gate(self) -> None:
        for candidate in _draw(_gen(), 100):
            verdict = evaluate_equivalent_candidate(
                _spec(),
                candidate.problem,
                provenance=candidate.provenance,
                conditions=candidate.conditions,
                answer_map=candidate.answer_map,
                answer_selection=candidate.answer_selection,
            )
            assert verdict.accepted is True, f"{candidate.problem.slug} 미수용: {verdict.reasons}"
            assert verdict.verification == "verified"

    def test_answer_matches_independent_derivation(self) -> None:
        for candidate in _draw(_gen(), 100):
            assert candidate.answer_selection is not None
            derived = derive_selected_root(candidate.conditions, candidate.answer_selection)
            assert derived == candidate.answer_map["x"], candidate.conditions


class TestChoicesAndDistractors:
    def test_four_distinct_choices_answer_present(self) -> None:
        for candidate in _draw(_gen(), 120):
            problem = candidate.problem
            assert problem.question_format == "객관식"
            assert problem.choices is not None
            assert len(problem.choices) == 4
            assert len(set(problem.choices)) == 4
            assert problem.answer in problem.choices

    def test_distractor_map_two_misconceptions(self) -> None:
        # ④ 오답 3종: 극대극소 혼동 1 + 값↔x좌표 혼동 2·오개념 집합=주입 2종·전부 CATALOG 실재.
        for candidate in _draw(_gen(), 120):
            dm = candidate.problem.distractor_map
            assert dm is not None and len(dm) == 3
            ids = [e.misconception_id for e in dm]
            assert set(ids) == _TARGET
            assert ids.count(_MAX_MIN) == 1
            assert ids.count(_VALUE_VS_POINT) == 2
            for entry in dm:
                assert entry.misconception_id in CATALOG_BY_ID

    def test_maxmin_is_other_extremum_valuepoint_is_not_root(self) -> None:
        # ⑤ 극대극소 오답=반대 극값(조건 근)·값↔좌표 오답=근이 아님(x좌표).
        for candidate in _draw(_gen(), 120):
            problem = candidate.problem
            assert problem.choices is not None and problem.distractor_map is not None
            roots = _condition_roots(candidate.conditions)
            answer = int(problem.answer or "0")
            assert answer in roots
            for entry in problem.distractor_map:
                choice_value = int(problem.choices[entry.choice_index])
                if entry.misconception_id == _MAX_MIN:
                    assert choice_value in roots and choice_value != answer
                else:  # value-vs-point — 극점 x좌표는 조건 근이 아님
                    assert choice_value not in roots


class TestStructuralDiversity:
    def test_signatures_all_distinct(self) -> None:
        sigs = [canonical_signature(c.conditions, c.answer_selection) for c in _draw(_gen(), 120)]
        assert all(s is not None for s in sigs)
        assert len(set(sigs)) == len(sigs)

    def test_skip_signatures_respected(self) -> None:
        first = _gen().generate(_spec())
        assert first is not None
        skip = {canonical_signature(first.conditions, first.answer_selection)}
        gen = _gen(skip_signatures=skip)
        for _ in range(50):
            candidate = gen.generate(_spec())
            assert candidate is not None
            assert canonical_signature(candidate.conditions, candidate.answer_selection) not in skip


class TestMetadataInjection:
    def test_default_concept_and_unit_tags(self) -> None:
        candidate = _gen().generate(_spec())
        assert candidate is not None
        assert [t.concept_src_id for t in candidate.concept_tags] == ["H:12미적Ⅰ02-07"]
        assert candidate.problem.unit_codes == ["CALC-EXTREMUM-MC"]
        assert candidate.problem.achievement_standard_codes == [_STANDARD]

    def test_slug_prefix_is_calc_extmc(self) -> None:
        candidate = _gen().generate(_spec())
        assert candidate is not None
        assert candidate.problem.slug.startswith("wm-calc-extmc-")
