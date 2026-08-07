"""초등 최대공약수·최소공배수 스켈레톤 생성기 단위테스트(hermetic·게이트 재사용).

`GcdLcmSkeletonGenerator`가 ① 전건 S2-a 4종 게이트 통과(SymPy `gcd()`/`lcm()` 조건 재확인)
② answer가 독립 재계산(math.gcd·a*b//gcd)과 일치 ③ 풀 유일·소진 시 None ④ `kind`가
밴드뿐 아니라 **성취기준 코드 자체**를 가른다는 이 도메인 고유 설계(형제 생성기들과 다름 —
gcd→[6수01-04]·lcm→[6수01-05])를 못 박는다 ⑤ 조사(와/과) 정합·개념 태깅·위생 게이트
무오탐. LLM·DB·PG 0(순수 결정론).
"""

from __future__ import annotations

import math

from whymath_backend.l3.equivalent.acceptance import (
    EquivalenceSpec,
    evaluate_equivalent_candidate,
)
from whymath_backend.l3.equivalent.elementary_gcd_lcm_skeleton_generator import (
    GCD_STANDARD_CODE,
    LCM_STANDARD_CODE,
    GcdLcmSkeletonGenerator,
    _build_pool,
)
from whymath_backend.l3.equivalent.generator import CandidateProblem
from whymath_backend.schema.enums import QuestionFormat


def _spec(code: str, difficulty: float) -> EquivalenceSpec:
    return EquivalenceSpec(
        achievement_standard_codes=frozenset({code}),
        target_misconception_ids=frozenset(),
        difficulty_overall=difficulty,
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


class TestPool:
    def test_pool_nonempty_and_unique_and_ordered(self) -> None:
        for kind in ("gcd", "lcm"):
            pool = _build_pool(kind)
            assert len(pool) >= 1000
            keys = {(s.a, s.b) for s in pool}
            assert len(keys) == len(pool)
            for skeleton in pool:
                assert skeleton.a < skeleton.b

    def test_answer_matches_independent_recompute(self) -> None:
        for skeleton in _build_pool()[:200]:
            g = math.gcd(skeleton.a, skeleton.b)
            expected = g if skeleton.kind == "gcd" else skeleton.a * skeleton.b // g
            assert skeleton.answer == expected

    def test_kind_selects_distinct_standard_code_and_concept_tag(self) -> None:
        """이 도메인 고유 설계 — kind가 성취기준 코드 자체를 가른다(형제 생성기와 다름)."""
        gcd_candidate = GcdLcmSkeletonGenerator(kind="gcd").generate(_spec(GCD_STANDARD_CODE, 1.6))
        lcm_candidate = GcdLcmSkeletonGenerator(kind="lcm").generate(_spec(LCM_STANDARD_CODE, 1.8))
        assert gcd_candidate is not None and lcm_candidate is not None
        assert gcd_candidate.problem.achievement_standard_codes == [GCD_STANDARD_CODE]
        assert lcm_candidate.problem.achievement_standard_codes == [LCM_STANDARD_CODE]
        assert gcd_candidate.concept_tags[0].concept_src_id == "B1"
        assert lcm_candidate.concept_tags[0].concept_src_id == "B2"

    def test_kind_filter_ids_stay_unique_across_bands(self) -> None:
        gcd_gen = GcdLcmSkeletonGenerator(kind="gcd")
        lcm_gen = GcdLcmSkeletonGenerator(kind="lcm")
        gcd_candidates = _drain(gcd_gen, _spec(GCD_STANDARD_CODE, 1.6), 30)
        lcm_candidates = _drain(lcm_gen, _spec(LCM_STANDARD_CODE, 1.8), 30)
        assert len(gcd_candidates) == 30
        assert len(lcm_candidates) == 30
        gcd_ids = {c.problem.problem_id for c in gcd_candidates}
        lcm_ids = {c.problem.problem_id for c in lcm_candidates}
        assert not (gcd_ids & lcm_ids), "밴드 간 problem_id 중복 — 밴드 분리 실패(회귀)."

    def test_generation_exhausts_to_none_per_kind(self) -> None:
        for kind, code, diff in (("gcd", GCD_STANDARD_CODE, 1.6), ("lcm", LCM_STANDARD_CODE, 1.8)):
            pool_size = len(_build_pool(kind))
            gen = GcdLcmSkeletonGenerator(kind=kind)
            drained = _drain(gen, _spec(code, diff), pool_size + 5)
            assert len(drained) == pool_size, kind
            assert gen.generate(_spec(code, diff)) is None


class TestAcceptance:
    def test_all_pass_acceptance_gate(self) -> None:
        for kind, code, diff in (("gcd", GCD_STANDARD_CODE, 1.6), ("lcm", LCM_STANDARD_CODE, 1.8)):
            candidates = _drain(GcdLcmSkeletonGenerator(kind=kind), _spec(code, diff), 300)
            assert len(candidates) == 300
            for candidate in candidates:
                verdict = evaluate_equivalent_candidate(
                    _spec(code, diff),
                    candidate.problem,
                    provenance=candidate.provenance,
                    conditions=candidate.conditions,
                    answer_map=candidate.answer_map,
                    solution_steps=candidate.solution_steps,
                )
                label = f"{kind}/{candidate.problem.slug}"
                assert verdict.accepted is True, f"{label}: {verdict.reasons}"
                assert verdict.verification == "verified"

    def test_gate_rejects_wrong_answer(self) -> None:
        candidate = GcdLcmSkeletonGenerator(kind="lcm").generate(_spec(LCM_STANDARD_CODE, 1.8))
        assert candidate is not None
        broken_answer = str(int(candidate.problem.answer) + 1)
        verdict = evaluate_equivalent_candidate(
            _spec(LCM_STANDARD_CODE, 1.8),
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
        gen = GcdLcmSkeletonGenerator(kind="gcd")
        for candidate in _drain(gen, _spec(GCD_STANDARD_CODE, 1.6), 20):
            assert candidate.problem.question_format == QuestionFormat.단답형
            assert candidate.problem.choices is None
            assert candidate.problem.distractor_map is None

    def test_no_unverified_glyphs(self) -> None:
        gen = GcdLcmSkeletonGenerator(kind="lcm")
        for candidate in _drain(gen, _spec(LCM_STANDARD_CODE, 1.8), 100):
            text = candidate.problem.question_text
            assert "Σ" not in text
            assert "α" not in text
            assert "β" not in text
