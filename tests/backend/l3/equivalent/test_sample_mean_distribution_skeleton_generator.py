"""고등 표본평균의 평균·분산 스켈레톤 생성기 단위테스트(hermetic·게이트 재사용).

`SampleMeanDistributionSkeletonGenerator`가 ① 전건 S2-a 4종 게이트 통과(분수/정수 답 검증
재실증 — binomial_distribution_skeleton_generator와 동형 설계) ② answer가 독립 재계산
(E(X바)=mu·V(X바)=sigma_sq/n)과 일치 ③ `kind` 필터로 밴드가 실제로 분리됨(2026-08-05
elementary_addsub 사고 재발 방지 회귀 봉인) ④ 개념 태깅·위생 게이트 무오탐(X̄ 등 결합 악센트
글리프 미사용 포함)을 못 박는다. 풀이 17,400개(밴드당)로 커서 게이트 소진 테스트는 표본으로
한다(SymPy 검증 비용 — 형제 생성기의 전량 소진 패턴을 그대로 따르면 과도하게 느려짐).
LLM·DB·PG 0(순수 결정론).
"""

from __future__ import annotations

from fractions import Fraction

import pytest

from whymath_backend.l3.equivalent.acceptance import (
    EquivalenceSpec,
    evaluate_equivalent_candidate,
)
from whymath_backend.l3.equivalent.generator import CandidateProblem
from whymath_backend.l3.equivalent.sample_mean_distribution_skeleton_generator import (
    SampleMeanDistributionSkeletonGenerator,
    _build_pool,
)
from whymath_backend.schema.enums import QuestionFormat

# PB-13: backend 잡 35분 상한 초과 해소 — PR 상시 경로에서 분리하고 전용 잡
# corpus-authoring(야간 + 생성기·배치 변경 PR)이 돌린다. 비활성화가 아니다.
pytestmark = pytest.mark.corpus_authoring

_STANDARD = "[12확통03-06]"
_BAD_GLYPHS = ("Σ", "α", "β", "²", "³", "∩", "∪", "X̄")


def _spec() -> EquivalenceSpec:
    return EquivalenceSpec(
        achievement_standard_codes=frozenset({_STANDARD}),
        target_misconception_ids=frozenset(),
        difficulty_overall=2.85,
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
        assert len(pool) == 17400 * 2
        keys = {(s.kind, s.mu, s.sigma_sq, s.n) for s in pool}
        assert len(keys) == len(pool)

    def test_answer_matches_independent_recompute(self) -> None:
        for skeleton in _build_pool()[:1000]:
            expected = (
                Fraction(skeleton.mu)
                if skeleton.kind == "mean"
                else Fraction(skeleton.sigma_sq, skeleton.n)
            )
            assert skeleton.result == expected

    def test_kind_filter_restricts_output_and_ids_stay_unique_across_bands(self) -> None:
        """`kind` 필터가 실제로 밴드를 분리한다 — 2026-08-05 사고 회귀 봉인."""
        ids_by_kind: dict[str, set] = {}
        for kind in ("mean", "variance"):
            candidates = _drain(SampleMeanDistributionSkeletonGenerator(kind=kind), _spec(), 30)
            assert len(candidates) == 30
            expected_word = "평균" if kind == "mean" else "분산"
            assert all(expected_word in c.problem.question_text for c in candidates), kind
            ids_by_kind[kind] = {c.problem.problem_id for c in candidates}
        assert not (
            ids_by_kind["mean"] & ids_by_kind["variance"]
        ), "밴드 간 problem_id 중복 — 밴드 분리 실패(회귀)."

    def test_generation_continues_well_past_batch_default(self) -> None:
        """풀이 커서(밴드당 17,400) 배치 기본 요청 수(200)를 훨씬 넘겨도 소진되지 않는다."""
        for kind in ("mean", "variance"):
            gen = SampleMeanDistributionSkeletonGenerator(kind=kind)
            drained = _drain(gen, _spec(), 500)
            assert len(drained) == 500, kind


class TestAcceptance:
    def test_sample_passes_acceptance_gate(self) -> None:
        for kind in ("mean", "variance"):
            candidates = _drain(SampleMeanDistributionSkeletonGenerator(kind=kind), _spec(), 300)
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
                label = f"{kind}/{candidate.problem.slug}"
                assert verdict.accepted is True, f"{label}: {verdict.reasons}"
                assert verdict.verification == "verified"

    def test_gate_rejects_wrong_answer(self) -> None:
        candidate = SampleMeanDistributionSkeletonGenerator(kind="mean").generate(_spec())
        assert candidate is not None
        original = Fraction(candidate.problem.answer)  # type: ignore[arg-type]
        broken = str(original + 1)
        verdict = evaluate_equivalent_candidate(
            _spec(),
            candidate.problem.model_copy(update={"answer": broken}),
            provenance=candidate.provenance,
            conditions=candidate.conditions,
            answer_map={"y": broken},
            solution_steps=candidate.solution_steps,
        )
        assert verdict.accepted is False
        assert any("Tier1" in r for r in verdict.reasons)


class TestShape:
    def test_question_format_and_no_choices(self) -> None:
        gen = SampleMeanDistributionSkeletonGenerator()
        for candidate in _drain(gen, _spec(), 20):
            assert candidate.problem.question_format == QuestionFormat.단답형
            assert candidate.problem.choices is None
            assert candidate.problem.distractor_map is None

    def test_concept_tags_resolve_via_legacy_437_space(self) -> None:
        candidate = SampleMeanDistributionSkeletonGenerator().generate(_spec())
        assert candidate is not None
        assert len(candidate.concept_tags) == 1
        assert candidate.concept_tags[0].concept_src_id == "H:12확통03-06"

    def test_no_unverified_glyphs_in_both_fields(self) -> None:
        gen = SampleMeanDistributionSkeletonGenerator()
        for candidate in _drain(gen, _spec(), 300):
            _assert_no_bad_glyphs(candidate)
