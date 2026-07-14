"""지수·로그 방정식 결정론 스켈레톤 생성기 — S2 대수 확장 단위테스트(hermetic·게이트 재사용).

지수(bˣ=bᵏ)·로그(log_b x=k) 두 형제 생성기가 ① 전건 S2-a 4종 게이트 통과(게이트 인프라 무변경
재사용 실증) ② answer가 derive_selected_root와 일치(교차 검증) ③ 결정론·풀 유일 ④ 개념 태깅·
유일근 선택 ⑤ solution_steps 닫힌형 체인의 Tier2 무결(전 전이 correct·unverifiable 0 — S2-02)을
못 박는다. LLM·DB·PG 0(순수 결정론).
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
from whymath_backend.l3.verify_solution import verify_solution

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
        # S2-02: solution_steps를 함께 결선해 Tier2 포함 verified를 못 박는다(수율 회귀 봉인).
        candidates = _drain(ExponentialEquationSkeletonGenerator(), 100)
        assert len(candidates) >= 15
        for candidate in candidates:
            verdict = evaluate_equivalent_candidate(
                _spec(),
                candidate.problem,
                provenance=candidate.provenance,
                conditions=candidate.conditions,
                answer_map=candidate.answer_map,
                solution_steps=candidate.solution_steps,
                answer_selection=candidate.answer_selection,
            )
            assert verdict.accepted is True, f"{candidate.problem.slug} 미수용: {verdict.reasons}"
            assert verdict.verification == "verified"

    def test_solution_steps_closed_form_tier2_clean(self) -> None:
        # S2-02: 전건 닫힌형 체인(log(v, b) → k) — 전 전이 correct·unverifiable 0(게이트
        # verified 전제). 마지막 단계 = answer(체인 종착이 답과 자기정합).
        for candidate in _drain(ExponentialEquationSkeletonGenerator(), 100):
            steps = candidate.solution_steps
            assert steps is not None and len(steps) == 2, candidate.problem.slug
            assert steps[-1] == candidate.answer_map["x"]
            result = verify_solution(steps)
            assert result.has_incorrect is False, candidate.problem.slug
            assert result.n_unverifiable == 0, candidate.problem.slug
            assert result.n_correct >= 1

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
        # S2-02: solution_steps 결선 포함 — Tier2까지 전건 verified(수율 회귀 봉인).
        candidates = _drain(LogarithmicEquationSkeletonGenerator(), 100)
        assert len(candidates) >= 15
        for candidate in candidates:
            verdict = evaluate_equivalent_candidate(
                _spec(),
                candidate.problem,
                provenance=candidate.provenance,
                conditions=candidate.conditions,
                answer_map=candidate.answer_map,
                solution_steps=candidate.solution_steps,
                answer_selection=candidate.answer_selection,
            )
            assert verdict.accepted is True, f"{candidate.problem.slug} 미수용: {verdict.reasons}"
            assert verdict.verification == "verified"

    def test_solution_steps_closed_form_tier2_clean(self) -> None:
        # S2-02: 전건 닫힌형 체인(bᵏ → 값) — 전 전이 correct·unverifiable 0·종착=answer.
        for candidate in _drain(LogarithmicEquationSkeletonGenerator(), 100):
            steps = candidate.solution_steps
            assert steps is not None and len(steps) == 2, candidate.problem.slug
            assert steps[-1] == candidate.answer_map["x"]
            result = verify_solution(steps)
            assert result.has_incorrect is False, candidate.problem.slug
            assert result.n_unverifiable == 0, candidate.problem.slug
            assert result.n_correct >= 1

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


def test_difficulty_one_step_below_quad_factoring() -> None:
    # 계통 관찰 2 회귀 차단(S2-08): 밑 통일·로그 정의 1스텝은 QUAD-EQ 기초 인수분해(2.0)보다
    # 쉬워야 한다. 대표 1스텝의 최소값 < 2.0·전건 상한 < 2.5.
    from whymath_backend.l3.equivalent.difficulty import estimate_difficulty

    quad = estimate_difficulty(root_kind="integer", lead_coefficient=1, max_abs_coefficient=10)
    assert quad == 2.0
    exp = [
        c.problem.difficulty_overall for c in _drain(ExponentialEquationSkeletonGenerator(), 100)
    ]
    log = [
        c.problem.difficulty_overall for c in _drain(LogarithmicEquationSkeletonGenerator(), 100)
    ]
    assert exp and log
    assert min(exp) < quad and min(log) < quad  # type: ignore[type-var]
    assert max(exp) < 2.5 and max(log) < 2.5  # type: ignore[type-var]
