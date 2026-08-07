"""고등 미적분Ⅱ 몫의 미분법 스켈레톤 생성기 단위테스트(hermetic·게이트 재사용).

`HighschoolQuotientRuleSkeletonGenerator`가 ① 전건 S2-a 4종 게이트 통과(대학 CALC1 축
형제와 동형 검증 설계 재실증) ② answer가 독립 재계산(몫의 미분법 전개식)과 일치 ③ 풀
유일·소진 시 None ④ 분모 g(k)=±1 구성으로 항상 정수 답 보장 ⑤ concept_tags가 legacy 437
공간에 정상 태깅됨(대학 축의 concept_tags=() 공백과 대비 — 이 코드는 legacy 공간에 실존)
⑥ question_text·answer_explanation 양쪽 모두 신규 Unicode 글리프 미사용(2026-08-07
conic_section_focus 사고 재발 방지 — 두 필드 모두 확인해야 함을 실측으로 배운 교훈 반영)을
못 박는다. LLM·DB·PG 0(순수 결정론).
"""

from __future__ import annotations

from whymath_backend.l3.equivalent.acceptance import (
    EquivalenceSpec,
    evaluate_equivalent_candidate,
)
from whymath_backend.l3.equivalent.generator import CandidateProblem
from whymath_backend.l3.equivalent.highschool_quotient_rule_skeleton_generator import (
    HighschoolQuotientRuleSkeletonGenerator,
    _build_pool,
)
from whymath_backend.schema.enums import QuestionFormat

_STANDARD = "[12미적Ⅱ-02-04]"


def _spec() -> EquivalenceSpec:
    return EquivalenceSpec(
        achievement_standard_codes=frozenset({_STANDARD}),
        target_misconception_ids=frozenset(),
        difficulty_overall=3.7,
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
    def test_pool_reaches_target_and_structurally_unique(self) -> None:
        pool = _build_pool()
        assert len(pool) == 300
        keys = {(s.a, s.b, s.c, s.d, s.k, s.g_sign) for s in pool}
        assert len(keys) == len(pool)

    def test_denominator_at_k_is_always_pm_one(self) -> None:
        """핵심 설계 불변식 — g(k)=dk+e는 항상 ±1(정수 답 보장의 근거)."""
        for skeleton in _build_pool():
            g_at_k = skeleton.d * skeleton.k + skeleton.e
            assert g_at_k == skeleton.g_sign
            assert abs(g_at_k) == 1

    def test_answer_matches_independent_quotient_rule_recompute(self) -> None:
        for skeleton in _build_pool()[:150]:
            a, b, c, d, k = skeleton.a, skeleton.b, skeleton.c, skeleton.d, skeleton.k
            e = skeleton.e
            g_at_k = d * k + e
            f1_prime = 2 * a * k + b
            f1_at_k = a * k * k + b * k + c
            expected = (f1_prime * g_at_k - f1_at_k * d) // (g_at_k * g_at_k)
            assert skeleton.result == expected

    def test_generation_exhausts_to_none(self) -> None:
        pool_size = len(_build_pool())
        gen = HighschoolQuotientRuleSkeletonGenerator()
        drained = _drain(gen, _spec(), pool_size + 5)
        assert len(drained) == pool_size
        assert gen.generate(_spec()) is None


class TestAcceptance:
    def test_all_pass_acceptance_gate(self) -> None:
        candidates = _drain(HighschoolQuotientRuleSkeletonGenerator(), _spec(), 300)
        assert len(candidates) == 300
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

    def test_gate_rejects_wrong_answer(self) -> None:
        candidate = HighschoolQuotientRuleSkeletonGenerator().generate(_spec())
        assert candidate is not None
        broken_answer = str(int(candidate.problem.answer) + 1)
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


class TestShape:
    def test_question_format_and_no_choices(self) -> None:
        gen = HighschoolQuotientRuleSkeletonGenerator()
        for candidate in _drain(gen, _spec(), 20):
            assert candidate.problem.question_format == QuestionFormat.단답형
            assert candidate.problem.choices is None
            assert candidate.problem.distractor_map is None

    def test_concept_tags_resolve_via_legacy_437_space(self) -> None:
        """대학 축(CALC1)과 대비 — 이 K-12 개념은 legacy 437 공간에 실존해 정상 태깅된다."""
        candidate = HighschoolQuotientRuleSkeletonGenerator().generate(_spec())
        assert candidate is not None
        assert len(candidate.concept_tags) == 1
        assert candidate.concept_tags[0].concept_src_id == "H:12미적Ⅱ02-04"

    def test_no_unverified_glyphs_in_both_question_and_explanation_fields(self) -> None:
        """question_text·answer_explanation 양쪽 모두 확인 — 2026-08-07 conic_section_focus
        사고 재발 방지(question_text만 확인하고 explanation을 놓쳐 ² 유출됨)."""
        gen = HighschoolQuotientRuleSkeletonGenerator()
        for candidate in _drain(gen, _spec(), 300):
            for field in (candidate.problem.question_text, candidate.problem.answer_explanation):
                assert "Σ" not in field
                assert "α" not in field
                assert "β" not in field
                assert "²" not in field
                assert "³" not in field
