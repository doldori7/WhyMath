"""초등 어림(올림·버림·반올림) 스켈레톤 생성기 단위테스트(hermetic·게이트 재사용).

`RoundingSkeletonGenerator`가 ① 전건 S2-a 4종 게이트 통과(SymPy `ceiling()`/`floor()`
조건이 반올림의 round-half-up 관례까지 정확히 검증함을 재확인) ② answer가 독립 재계산과
일치 ③ 풀 유일·소진 시 None ④ `kind` 필터로 밴드가 실제로 분리됨(2026-08-05
elementary_addsub 사고 재발 방지 회귀 봉인) ⑤ 반올림이 Python 내장 `round()`(은행가
반올림)이 아니라 한국 교과서 관례(5는 항상 올림)를 따름을 실측 봉인 ⑥ 개념 태깅·위생 게이트
무오탐을 못 박는다. LLM·DB·PG 0(순수 결정론).
"""

from __future__ import annotations

from whymath_backend.l3.equivalent.acceptance import (
    EquivalenceSpec,
    evaluate_equivalent_candidate,
)
from whymath_backend.l3.equivalent.elementary_rounding_skeleton_generator import (
    RoundingSkeletonGenerator,
    _build_pool,
    _RoundingSkeleton,
)
from whymath_backend.l3.equivalent.generator import CandidateProblem
from whymath_backend.schema.enums import QuestionFormat

_STANDARD = "[6수01-03]"


def _spec() -> EquivalenceSpec:
    return EquivalenceSpec(
        achievement_standard_codes=frozenset({_STANDARD}),
        target_misconception_ids=frozenset(),
        difficulty_overall=1.5,
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
    def test_pool_reaches_target_per_kind_and_unique(self) -> None:
        for kind in ("ceil", "floor", "round"):
            pool = _build_pool(kind)
            assert len(pool) == 300
            keys = {(s.value, s.factor) for s in pool}
            assert len(keys) == len(pool)

    def test_kind_filter_restricts_output_and_ids_stay_unique_across_bands(self) -> None:
        """`kind` 필터가 실제로 밴드를 분리한다 — 2026-08-05 사고 회귀 봉인."""
        ids_by_kind: dict[str, set] = {}
        for kind in ("ceil", "floor", "round"):
            candidates = _drain(RoundingSkeletonGenerator(kind=kind), _spec(), 30)
            assert len(candidates) == 30
            ids_by_kind[kind] = {c.problem.problem_id for c in candidates}
        assert not (ids_by_kind["ceil"] & ids_by_kind["floor"])
        assert not (ids_by_kind["floor"] & ids_by_kind["round"])
        assert not (ids_by_kind["ceil"] & ids_by_kind["round"])

    def test_round_half_up_not_bankers_rounding(self) -> None:
        """핵심 실측 봉인 — 정확히 5인 경계값은 항상 올림(한국 교과서 관례), Python round()의
        은행가 반올림(5→짝수)과 다르다."""
        skeleton = _RoundingSkeleton(kind="round", value=125, place_name="십", factor=10)
        assert skeleton.answer == 130  # round-half-up. Python round(125,-1)=120(은행가)이면 회귀.
        skeleton2 = _RoundingSkeleton(kind="round", value=135, place_name="십", factor=10)
        assert skeleton2.answer == 140  # 은행가 반올림이면 140도 맞지만(홀→짝) 정책 일관성 확인.

    def test_generation_exhausts_to_none_per_kind(self) -> None:
        for kind in ("ceil", "floor", "round"):
            pool_size = len(_build_pool(kind))
            gen = RoundingSkeletonGenerator(kind=kind)
            drained = _drain(gen, _spec(), pool_size + 5)
            assert len(drained) == pool_size, kind
            assert gen.generate(_spec()) is None


class TestAcceptance:
    def test_all_pass_acceptance_gate(self) -> None:
        for kind in ("ceil", "floor", "round"):
            candidates = _drain(RoundingSkeletonGenerator(kind=kind), _spec(), 300)
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
        candidate = RoundingSkeletonGenerator(kind="round").generate(_spec())
        assert candidate is not None
        broken_answer = str(int(candidate.problem.answer) + 1)
        verdict = evaluate_equivalent_candidate(
            _spec(),
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
        gen = RoundingSkeletonGenerator()
        for candidate in _drain(gen, _spec(), 20):
            assert candidate.problem.question_format == QuestionFormat.단답형
            assert candidate.problem.choices is None
            assert candidate.problem.distractor_map is None

    def test_concept_tags_resolve_via_legacy_437_space(self) -> None:
        candidate = RoundingSkeletonGenerator().generate(_spec())
        assert candidate is not None
        assert len(candidate.concept_tags) == 1
        assert candidate.concept_tags[0].concept_src_id == "R2"

    def test_no_unverified_glyphs(self) -> None:
        gen = RoundingSkeletonGenerator()
        for candidate in _drain(gen, _spec(), 100):
            text = candidate.problem.question_text
            assert "Σ" not in text
            assert "α" not in text
            assert "β" not in text
