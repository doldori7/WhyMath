"""미적분(접선 기울기) 스켈레톤 생성기 — hermetic(LLM 0·결정론) 단위·성질 테스트.

핵심 성질(전수/표본), 극값 `test_calculus_skeleton_generator.py` 미러:
  ① 후보는 전부 S2-a 게이트 통과(accepted) — 결정론 코어가 곧 검증 가능성.
  ② answer_map은 derive_selected_root(독립 유도)와 정확히 일치 — 교차 검증.
  ③ 큰→largest·작은→smallest 매핑이 실제 도함수(f'=m) 근과 정합.
  ④ 구조 signature 전부 상이·skip 존중·풀 소진 시 None·재현 결정론.
  ⑤ 개념/단원 태깅이 미분계수([12미적Ⅰ-02-01]·H:12미적Ⅰ02-01)로 주입됨.
  ⑥ 접선 기울기 m≠0(극값 f'=0과 구조 구분) 불변.
"""

from __future__ import annotations

from whymath_backend.l3.equivalent.acceptance import (
    EquivalenceSpec,
    evaluate_equivalent_candidate,
)
from whymath_backend.l3.equivalent.calculus_skeleton_generator import (
    CalculusTangentSlopeSkeletonGenerator,
)
from whymath_backend.l3.equivalent.canonicalize import canonical_signature
from whymath_backend.l3.equivalent.generator import (
    CandidateProblem,
    EquivalentProblemGenerator,
)
from whymath_backend.l3.verify_answer import derive_selected_root
from whymath_backend.schema.enums import AnswerFormat

_STANDARD = "[12미적Ⅰ-02-01]"


def _spec(**overrides: object) -> EquivalenceSpec:
    kwargs: dict[str, object] = {
        "achievement_standard_codes": frozenset({_STANDARD}),
        "target_misconception_ids": frozenset(),
        "difficulty_overall": 3.3,
        "answer_format": AnswerFormat.실수,
    }
    kwargs.update(overrides)
    return EquivalenceSpec(**kwargs)  # type: ignore[arg-type]


def _draw(generator: CalculusTangentSlopeSkeletonGenerator, n: int) -> list[CandidateProblem]:
    out: list[CandidateProblem] = []
    for _ in range(n):
        candidate = generator.generate(_spec())
        assert candidate is not None
        out.append(candidate)
    return out


class TestSeatContract:
    def test_satisfies_generator_protocol(self) -> None:
        assert isinstance(CalculusTangentSlopeSkeletonGenerator(), EquivalentProblemGenerator)

    def test_deterministic_sequence(self) -> None:
        a = [c.problem.slug for c in _draw(CalculusTangentSlopeSkeletonGenerator(), 5)]
        b = [c.problem.slug for c in _draw(CalculusTangentSlopeSkeletonGenerator(), 5)]
        assert a == b

    def test_pool_exhaustion_returns_none(self) -> None:
        gen = CalculusTangentSlopeSkeletonGenerator()
        count = 0
        while gen.generate(_spec()) is not None:
            count += 1
            assert count < 1000
        assert count > 100
        assert gen.generate(_spec()) is None


class TestMathematicalSoundness:
    def test_all_candidates_pass_acceptance_gate(self) -> None:
        for candidate in _draw(CalculusTangentSlopeSkeletonGenerator(), 100):
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
        for candidate in _draw(CalculusTangentSlopeSkeletonGenerator(), 100):
            assert candidate.answer_selection is not None
            derived = derive_selected_root(candidate.conditions, candidate.answer_selection)
            assert derived == candidate.answer_map["x"], candidate.conditions

    def test_pick_maps_to_correct_tangent_point(self) -> None:
        # ③ 큰→largest·작은→smallest — 발문 방향과 선택·정답 정합.
        for candidate in _draw(CalculusTangentSlopeSkeletonGenerator(), 120):
            q = candidate.problem.question_text
            assert "접선의 기울기" in q
            if "큰" in q:
                assert candidate.answer_selection == "largest"
            elif "작은" in q:
                assert candidate.answer_selection == "smallest"
            else:  # pragma: no cover — 템플릿은 큰/작은만
                raise AssertionError(f"발문에 큰/작은 없음: {q}")
            assert candidate.answer_map["x"] == candidate.problem.answer

    def test_slope_is_nonzero(self) -> None:
        # ⑥ 접선 기울기 m≠0 — m=0이면 수평 접선=극값과 동치라 구조 구분이 사라진다.
        for candidate in _draw(CalculusTangentSlopeSkeletonGenerator(), 120):
            assert "기울기가 0인" not in candidate.problem.question_text


class TestStructuralDiversity:
    def test_signatures_all_distinct(self) -> None:
        sigs = [
            canonical_signature(c.conditions, c.answer_selection)
            for c in _draw(CalculusTangentSlopeSkeletonGenerator(), 120)
        ]
        assert all(s is not None for s in sigs)
        assert len(set(sigs)) == len(sigs)

    def test_skip_signatures_respected(self) -> None:
        first = CalculusTangentSlopeSkeletonGenerator().generate(_spec())
        assert first is not None
        skip = {canonical_signature(first.conditions, first.answer_selection)}
        gen = CalculusTangentSlopeSkeletonGenerator(skip_signatures=skip)
        for _ in range(50):
            candidate = gen.generate(_spec())
            assert candidate is not None
            assert canonical_signature(candidate.conditions, candidate.answer_selection) not in skip


class TestMetadataInjection:
    def test_default_concept_and_unit_tags(self) -> None:
        candidate = CalculusTangentSlopeSkeletonGenerator().generate(_spec())
        assert candidate is not None
        assert [t.concept_src_id for t in candidate.concept_tags] == ["H:12미적Ⅰ02-01"]
        assert candidate.problem.unit_codes == ["CALC-TANGENT"]
        assert candidate.problem.achievement_standard_codes == [_STANDARD]

    def test_slug_prefix_is_calc_tan(self) -> None:
        candidate = CalculusTangentSlopeSkeletonGenerator().generate(_spec())
        assert candidate is not None
        assert candidate.problem.slug.startswith("wm-calc-tan-")
