"""지수·로그 방정식 결정론 스켈레톤 생성기 — S2 대수 확장 단위테스트(hermetic·게이트 재사용).

지수(bˣ=bᵏ)·로그(log_b x=k) 두 형제 생성기가 ① 전건 S2-a 4종 게이트 통과(게이트 인프라 무변경
재사용 실증) ② answer가 derive_selected_root와 일치(교차 검증) ③ 결정론·풀 유일 ④ 개념 태깅·
유일근 선택을 못 박는다. LLM·DB·PG 0(순수 결정론).
"""

from __future__ import annotations

from whymath_backend.l3.equivalent.acceptance import (
    EquivalenceSpec,
    evaluate_equivalent_candidate,
)
from whymath_backend.l3.equivalent.exp_log_skeleton_generator import (
    ExponentialEquationSkeletonGenerator,
    LogarithmicEquationSkeletonGenerator,
    _build_exp_pool,
    _build_log_pool,
)
from whymath_backend.l3.equivalent.generator import CandidateProblem
from whymath_backend.l3.verify_answer import derive_selected_root

_STANDARD = "[12대수01-08]"


def _spec() -> EquivalenceSpec:
    return EquivalenceSpec(
        achievement_standard_codes=frozenset({_STANDARD}),
        target_misconception_ids=frozenset(),
        difficulty_overall=3.0,
        answer_format=None,
    )


def _drain(gen: object, limit: int) -> list[CandidateProblem]:
    out: list[CandidateProblem] = []
    while len(out) < limit:
        candidate = gen.generate(_spec())  # type: ignore[attr-defined]
        if candidate is None:
            break
        out.append(candidate)
    return out


class TestExponentialGenerator:
    def test_pool_nonempty_and_unique(self) -> None:
        pool = _build_exp_pool()
        assert len(pool) >= 15
        # (밑, 지수)가 유일 — 중복 뼈대 0.
        keys = {(s.base, s.exponent) for s in pool}
        assert len(keys) == len(pool)

    def test_all_pass_acceptance_gate(self) -> None:
        # 전건 4종 게이트 통과 — 게이트 인프라(verify evalf·근 선택·위생·동등성)가 지수를 수용.
        candidates = _drain(ExponentialEquationSkeletonGenerator(), 100)
        assert len(candidates) >= 15
        for candidate in candidates:
            verdict = evaluate_equivalent_candidate(
                _spec(),
                candidate.problem,
                provenance=candidate.provenance,
                conditions=candidate.conditions,
                answer_map=candidate.answer_map,
                answer_selection=candidate.answer_selection,
            )
            assert verdict.accepted is True, f"{candidate.problem.slug} 미수용: {verdict.reasons}"

    def test_answer_matches_independent_derivation(self) -> None:
        # 교차 검증 — answer가 derive_selected_root(conditions, unique)와 수치 일치.
        for candidate in _drain(ExponentialEquationSkeletonGenerator(), 100):
            derived = derive_selected_root(candidate.conditions, "unique")
            assert derived is not None
            assert int(derived) == int(candidate.answer_map["x"]), candidate.conditions

    def test_unique_selection_and_concept_tag(self) -> None:
        candidate = ExponentialEquationSkeletonGenerator().generate(_spec())
        assert candidate is not None
        assert candidate.answer_selection == "unique"
        assert [t.concept_src_id for t in candidate.concept_tags] == ["H:12대수01-08"]
        assert candidate.problem.question_format == "단답형"

    def test_deterministic_sequence(self) -> None:
        a = _drain(ExponentialEquationSkeletonGenerator(), 6)
        b = _drain(ExponentialEquationSkeletonGenerator(), 6)
        assert [c.problem.slug for c in a] == [c.problem.slug for c in b]


class TestLogarithmicGenerator:
    def test_pool_nonempty_and_unique(self) -> None:
        pool = _build_log_pool()
        assert len(pool) >= 15
        keys = {(s.base, s.exponent) for s in pool}
        assert len(keys) == len(pool)

    def test_all_pass_acceptance_gate(self) -> None:
        candidates = _drain(LogarithmicEquationSkeletonGenerator(), 100)
        assert len(candidates) >= 15
        for candidate in candidates:
            verdict = evaluate_equivalent_candidate(
                _spec(),
                candidate.problem,
                provenance=candidate.provenance,
                conditions=candidate.conditions,
                answer_map=candidate.answer_map,
                answer_selection=candidate.answer_selection,
            )
            assert verdict.accepted is True, f"{candidate.problem.slug} 미수용: {verdict.reasons}"

    def test_answer_matches_independent_derivation(self) -> None:
        for candidate in _drain(LogarithmicEquationSkeletonGenerator(), 100):
            derived = derive_selected_root(candidate.conditions, "unique")
            assert derived is not None
            assert int(derived) == int(candidate.answer_map["x"]), candidate.conditions

    def test_unique_selection_and_concept_tag(self) -> None:
        candidate = LogarithmicEquationSkeletonGenerator().generate(_spec())
        assert candidate is not None
        assert candidate.answer_selection == "unique"
        assert [t.concept_src_id for t in candidate.concept_tags] == ["H:12대수01-08"]

    def test_deterministic_sequence(self) -> None:
        a = _drain(LogarithmicEquationSkeletonGenerator(), 6)
        b = _drain(LogarithmicEquationSkeletonGenerator(), 6)
        assert [c.problem.slug for c in a] == [c.problem.slug for c in b]


class TestCrossFamily:
    def test_exp_and_log_slugs_disjoint(self) -> None:
        exp_slugs = {c.problem.slug for c in _drain(ExponentialEquationSkeletonGenerator(), 100)}
        log_slugs = {c.problem.slug for c in _drain(LogarithmicEquationSkeletonGenerator(), 100)}
        assert exp_slugs.isdisjoint(log_slugs)
