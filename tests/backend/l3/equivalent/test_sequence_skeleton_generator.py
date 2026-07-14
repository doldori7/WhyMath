"""수열(등차·등비) 결정론 스켈레톤 생성기 — S2 대수 확장 단위테스트(hermetic·게이트 재사용).

등차(aₙ=a+(n−1)d)·등비(aₙ=a·rⁿ⁻¹) 두 형제 생성기가 ① 전건 S2-a 4종 게이트 통과(게이트 인프라
무변경 재사용 실증) ② answer가 derive_selected_root와 일치(교차 검증·독립 재계산) ③ 결정론·풀
유일 ④ **답 유일 → signature 유일**(구조 dedup 오병합 방지) ⑤ 개념 태깅·유일해 선택
⑥ **solution_steps 방출(S2-02)** — 공식 대입 체인 전 전이 correct·unverifiable 0(Tier2 무결)을
못 박는다. LLM·DB·PG 0(순수 결정론).
"""

from __future__ import annotations

from whymath_backend.l3.equivalent.acceptance import (
    EquivalenceSpec,
    evaluate_equivalent_candidate,
)
from whymath_backend.l3.equivalent.canonicalize import canonical_signature
from whymath_backend.l3.equivalent.generator import CandidateProblem
from whymath_backend.l3.equivalent.sequence_skeleton_generator import (
    ArithmeticSequenceSkeletonGenerator,
    GeometricSequenceSkeletonGenerator,
    _build_arith_pool,
    _build_geo_pool,
)
from whymath_backend.l3.verify_answer import derive_selected_root
from whymath_backend.l3.verify_solution import verify_solution

_ARITH_STANDARD = "[12대수03-02]"
_GEO_STANDARD = "[12대수03-03]"


def _spec(code: str) -> EquivalenceSpec:
    return EquivalenceSpec(
        achievement_standard_codes=frozenset({code}),
        target_misconception_ids=frozenset(),
        difficulty_overall=3.0,
        answer_format=None,
    )


def _drain(gen: object, code: str, limit: int) -> list[CandidateProblem]:
    out: list[CandidateProblem] = []
    while len(out) < limit:
        candidate = gen.generate(_spec(code))  # type: ignore[attr-defined]
        if candidate is None:
            break
        out.append(candidate)
    return out


class TestArithmeticGenerator:
    def test_pool_answers_unique(self) -> None:
        pool = _build_arith_pool()
        assert len(pool) >= 30
        answers = [s.answer for s in pool]
        assert len(answers) == len(set(answers))  # 답 유일(signature 유일 보장)
        assert all(a > 0 for a in answers)

    def test_all_pass_acceptance_gate(self) -> None:
        candidates = _drain(ArithmeticSequenceSkeletonGenerator(), _ARITH_STANDARD, 500)
        assert len(candidates) >= 30
        for candidate in candidates:
            verdict = evaluate_equivalent_candidate(
                _spec(_ARITH_STANDARD),
                candidate.problem,
                provenance=candidate.provenance,
                conditions=candidate.conditions,
                answer_map=candidate.answer_map,
                solution_steps=candidate.solution_steps,  # S2-02: Tier2 단계 검증 포함 게이트
                answer_selection=candidate.answer_selection,
            )
            assert verdict.accepted is True, f"{candidate.problem.slug} 미수용: {verdict.reasons}"

    def test_solution_steps_all_verified(self) -> None:
        # S2-02: 공식 대입 체인(대입식→값)이 방출되고 전 전이 correct·unverifiable 0(Tier2 무결).
        candidates = _drain(ArithmeticSequenceSkeletonGenerator(), _ARITH_STANDARD, 500)
        assert candidates
        for candidate in candidates:
            steps = candidate.solution_steps
            assert steps is not None and len(steps) == 2, candidate.problem.slug
            assert steps[1] == candidate.answer_map["x"]  # 체인 종단 = 정답(단일 진실 원천)
            result = verify_solution(steps)
            assert result.n_transitions == 1
            assert result.n_correct == 1 and result.n_unverifiable == 0
            assert result.has_incorrect is False

    def test_answer_matches_independent_derivation(self) -> None:
        # 교차 검증 — answer가 조건식의 독립 SymPy 재계산(derive_selected_root)과 정수 일치.
        for candidate in _drain(ArithmeticSequenceSkeletonGenerator(), _ARITH_STANDARD, 500):
            derived = derive_selected_root(candidate.conditions, "unique")
            assert derived is not None
            assert int(derived) == int(candidate.answer_map["x"]), candidate.conditions

    def test_signatures_unique(self) -> None:
        # 답 유일 → signature 유일(오케스트레이터 구조 dedup 오병합 0).
        cands = _drain(ArithmeticSequenceSkeletonGenerator(), _ARITH_STANDARD, 500)
        sigs = {canonical_signature(c.conditions, "unique") for c in cands}
        assert len(sigs) == len(cands)

    def test_unique_selection_and_concept_tag(self) -> None:
        candidate = ArithmeticSequenceSkeletonGenerator().generate(_spec(_ARITH_STANDARD))
        assert candidate is not None
        assert candidate.answer_selection == "unique"
        assert [t.concept_src_id for t in candidate.concept_tags] == ["H:12대수03-02"]
        assert candidate.problem.question_format == "단답형"

    def test_deterministic_sequence(self) -> None:
        a = _drain(ArithmeticSequenceSkeletonGenerator(), _ARITH_STANDARD, 6)
        b = _drain(ArithmeticSequenceSkeletonGenerator(), _ARITH_STANDARD, 6)
        assert [c.problem.slug for c in a] == [c.problem.slug for c in b]


class TestGeometricGenerator:
    def test_pool_answers_unique(self) -> None:
        pool = _build_geo_pool()
        assert len(pool) >= 20
        answers = [s.answer for s in pool]
        assert len(answers) == len(set(answers))
        assert all(a > 0 for a in answers)

    def test_all_pass_acceptance_gate(self) -> None:
        candidates = _drain(GeometricSequenceSkeletonGenerator(), _GEO_STANDARD, 500)
        assert len(candidates) >= 20
        for candidate in candidates:
            verdict = evaluate_equivalent_candidate(
                _spec(_GEO_STANDARD),
                candidate.problem,
                provenance=candidate.provenance,
                conditions=candidate.conditions,
                answer_map=candidate.answer_map,
                solution_steps=candidate.solution_steps,  # S2-02: Tier2 단계 검증 포함 게이트
                answer_selection=candidate.answer_selection,
            )
            assert verdict.accepted is True, f"{candidate.problem.slug} 미수용: {verdict.reasons}"

    def test_solution_steps_all_verified(self) -> None:
        # S2-02: 거듭제곱 대입 체인(a·r**(n−1)→값)이 방출되고 전 전이 correct·unverifiable 0.
        candidates = _drain(GeometricSequenceSkeletonGenerator(), _GEO_STANDARD, 500)
        assert candidates
        for candidate in candidates:
            steps = candidate.solution_steps
            assert steps is not None and len(steps) == 2, candidate.problem.slug
            assert steps[1] == candidate.answer_map["x"]  # 체인 종단 = 정답(단일 진실 원천)
            result = verify_solution(steps)
            assert result.n_transitions == 1
            assert result.n_correct == 1 and result.n_unverifiable == 0
            assert result.has_incorrect is False

    def test_answer_matches_independent_derivation(self) -> None:
        for candidate in _drain(GeometricSequenceSkeletonGenerator(), _GEO_STANDARD, 500):
            derived = derive_selected_root(candidate.conditions, "unique")
            assert derived is not None
            assert int(derived) == int(candidate.answer_map["x"]), candidate.conditions

    def test_signatures_unique(self) -> None:
        cands = _drain(GeometricSequenceSkeletonGenerator(), _GEO_STANDARD, 500)
        sigs = {canonical_signature(c.conditions, "unique") for c in cands}
        assert len(sigs) == len(cands)

    def test_unique_selection_and_concept_tag(self) -> None:
        candidate = GeometricSequenceSkeletonGenerator().generate(_spec(_GEO_STANDARD))
        assert candidate is not None
        assert candidate.answer_selection == "unique"
        assert [t.concept_src_id for t in candidate.concept_tags] == ["H:12대수03-03"]


class TestCrossFamily:
    def test_arith_and_geo_slugs_disjoint(self) -> None:
        arith = {
            c.problem.slug
            for c in _drain(ArithmeticSequenceSkeletonGenerator(), _ARITH_STANDARD, 500)
        }
        geo = {
            c.problem.slug for c in _drain(GeometricSequenceSkeletonGenerator(), _GEO_STANDARD, 500)
        }
        assert arith.isdisjoint(geo)


def test_difficulty_one_step_below_quad_factoring() -> None:
    # 계통 관찰 2 회귀 차단(S2-08): 일반항 직대입 1스텝은 QUAD-EQ 인수분해(2.0)보다 쉬워야 한다.
    from whymath_backend.l3.equivalent.difficulty import estimate_difficulty

    quad = estimate_difficulty(root_kind="integer", lead_coefficient=1, max_abs_coefficient=10)
    assert quad == 2.0
    arith = [
        c.problem.difficulty_overall
        for c in _drain(ArithmeticSequenceSkeletonGenerator(), _ARITH_STANDARD, 500)
    ]
    geo = [
        c.problem.difficulty_overall
        for c in _drain(GeometricSequenceSkeletonGenerator(), _GEO_STANDARD, 500)
    ]
    assert arith and geo
    assert min(arith) < quad and min(geo) < quad  # type: ignore[type-var]
    assert max(arith) <= 2.1 and max(geo) <= 2.2  # type: ignore[type-var]
