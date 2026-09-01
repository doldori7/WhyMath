"""고등 벡터 — 벡터의 연산·위치벡터 성분 스켈레톤 생성기 단위테스트(hermetic·게이트 재사용).

`VectorLinearCombinationSkeletonGenerator`·`PositionVectorComponentSkeletonGenerator`가
① 전건 S2-a 4종 게이트 통과 ② answer가 원시 파라미터로부터의 독립 재계산과 일치 ③ 풀
유일(구조 키)·소진 시 None ④ 겹부호(+ -, - -) 없는 표기 ⑤ 신규 Unicode 글리프 미사용 ⑥
개념 태깅·위생 게이트 무오탐을 못 박는다. LLM·DB·PG 0(순수 결정론).
"""

from __future__ import annotations

import pytest

from whymath_backend.l3.equivalent.acceptance import (
    EquivalenceSpec,
    evaluate_equivalent_candidate,
)
from whymath_backend.l3.equivalent.generator import CandidateProblem
from whymath_backend.l3.equivalent.vector_operations_skeleton_generator import (
    PositionVectorComponentSkeletonGenerator,
    VectorLinearCombinationSkeletonGenerator,
    _build_linear_combo_pool,
    _build_position_vector_pool,
)
from whymath_backend.schema.enums import QuestionFormat

# PB-13: backend 잡 35분 상한 초과 해소 — PR 상시 경로에서 분리하고 전용 잡
# corpus-authoring(야간 + 생성기·배치 변경 PR)이 돌린다. 비활성화가 아니다.
pytestmark = pytest.mark.corpus_authoring

_LINEAR_COMBO_STANDARD = "[12기하03-01]"
_POSITION_VECTOR_STANDARD = "[12기하03-02]"


def _linear_combo_spec() -> EquivalenceSpec:
    return EquivalenceSpec(
        achievement_standard_codes=frozenset({_LINEAR_COMBO_STANDARD}),
        target_misconception_ids=frozenset(),
        difficulty_overall=2.1,
        answer_format=None,
    )


def _position_vector_spec() -> EquivalenceSpec:
    return EquivalenceSpec(
        achievement_standard_codes=frozenset({_POSITION_VECTOR_STANDARD}),
        target_misconception_ids=frozenset(),
        difficulty_overall=1.9,
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


class TestLinearComboPool:
    def test_pool_reaches_target_and_structurally_unique(self) -> None:
        pool = _build_linear_combo_pool()
        assert len(pool) == 260
        keys = {(s.ax, s.ay, s.bx, s.by, s.p, s.q) for s in pool}
        assert len(keys) == len(pool)
        for skeleton in pool:
            assert skeleton.p != 0
            assert skeleton.q != 0

    def test_answer_matches_independent_recompute(self) -> None:
        for skeleton in _build_linear_combo_pool()[:150]:
            expected_x = skeleton.p * skeleton.ax + skeleton.q * skeleton.bx
            expected_y = skeleton.p * skeleton.ay + skeleton.q * skeleton.by
            assert skeleton.answer == expected_x + expected_y

    def test_generation_exhausts_to_none(self) -> None:
        pool_size = len(_build_linear_combo_pool())
        gen = VectorLinearCombinationSkeletonGenerator()
        drained = _drain(gen, _linear_combo_spec(), pool_size + 5)
        assert len(drained) == pool_size
        assert gen.generate(_linear_combo_spec()) is None


class TestLinearComboAcceptance:
    def test_all_pass_acceptance_gate(self) -> None:
        candidates = _drain(VectorLinearCombinationSkeletonGenerator(), _linear_combo_spec(), 260)
        assert len(candidates) == 260
        for candidate in candidates:
            verdict = evaluate_equivalent_candidate(
                _linear_combo_spec(),
                candidate.problem,
                provenance=candidate.provenance,
                conditions=candidate.conditions,
                answer_map=candidate.answer_map,
                solution_steps=candidate.solution_steps,
            )
            assert verdict.accepted is True, f"{candidate.problem.slug} 미수용: {verdict.reasons}"
            assert verdict.verification == "verified"

    def test_gate_rejects_wrong_answer(self) -> None:
        candidate = VectorLinearCombinationSkeletonGenerator().generate(_linear_combo_spec())
        assert candidate is not None
        broken_answer = str(int(candidate.problem.answer) + 1)
        verdict = evaluate_equivalent_candidate(
            _linear_combo_spec(),
            candidate.problem.model_copy(update={"answer": broken_answer}),
            provenance=candidate.provenance,
            conditions=candidate.conditions,
            answer_map={"x": broken_answer},
            solution_steps=candidate.solution_steps,
        )
        assert verdict.accepted is False
        assert any("Tier1" in r for r in verdict.reasons)


class TestLinearComboShape:
    def test_question_format_and_no_choices(self) -> None:
        gen = VectorLinearCombinationSkeletonGenerator()
        for candidate in _drain(gen, _linear_combo_spec(), 20):
            assert candidate.problem.question_format == QuestionFormat.단답형
            assert candidate.problem.choices is None
            assert candidate.problem.distractor_map is None

    def test_concept_tags_resolve_via_legacy_437_space(self) -> None:
        candidate = VectorLinearCombinationSkeletonGenerator().generate(_linear_combo_spec())
        assert candidate is not None
        assert len(candidate.concept_tags) == 1
        assert candidate.concept_tags[0].concept_src_id == "H:12기하03-01"

    def test_no_double_sign_and_no_unverified_glyphs(self) -> None:
        gen = VectorLinearCombinationSkeletonGenerator()
        for candidate in _drain(gen, _linear_combo_spec(), 260):
            text = candidate.problem.question_text
            assert "+ -" not in text
            assert "- -" not in text
            assert "+-" not in text
            assert "-+" not in text
            assert "Σ" not in text
            assert "α" not in text
            assert "β" not in text


class TestPositionVectorPool:
    def test_pool_reaches_target_and_structurally_unique(self) -> None:
        pool = _build_position_vector_pool()
        assert len(pool) == 260
        keys = {(s.ax, s.ay, s.bx, s.by) for s in pool}
        assert len(keys) == len(pool)
        for skeleton in pool:
            assert (skeleton.ax, skeleton.ay) != (skeleton.bx, skeleton.by)

    def test_answer_matches_independent_recompute(self) -> None:
        for skeleton in _build_position_vector_pool()[:150]:
            expected = (skeleton.bx - skeleton.ax) + (skeleton.by - skeleton.ay)
            assert skeleton.answer == expected

    def test_generation_exhausts_to_none(self) -> None:
        pool_size = len(_build_position_vector_pool())
        gen = PositionVectorComponentSkeletonGenerator()
        drained = _drain(gen, _position_vector_spec(), pool_size + 5)
        assert len(drained) == pool_size
        assert gen.generate(_position_vector_spec()) is None


class TestPositionVectorAcceptance:
    def test_all_pass_acceptance_gate(self) -> None:
        gen = PositionVectorComponentSkeletonGenerator()
        candidates = _drain(gen, _position_vector_spec(), 260)
        assert len(candidates) == 260
        for candidate in candidates:
            verdict = evaluate_equivalent_candidate(
                _position_vector_spec(),
                candidate.problem,
                provenance=candidate.provenance,
                conditions=candidate.conditions,
                answer_map=candidate.answer_map,
                solution_steps=candidate.solution_steps,
            )
            assert verdict.accepted is True, f"{candidate.problem.slug} 미수용: {verdict.reasons}"
            assert verdict.verification == "verified"

    def test_gate_rejects_wrong_answer(self) -> None:
        candidate = PositionVectorComponentSkeletonGenerator().generate(_position_vector_spec())
        assert candidate is not None
        broken_answer = str(int(candidate.problem.answer) + 1)
        verdict = evaluate_equivalent_candidate(
            _position_vector_spec(),
            candidate.problem.model_copy(update={"answer": broken_answer}),
            provenance=candidate.provenance,
            conditions=candidate.conditions,
            answer_map={"x": broken_answer},
            solution_steps=candidate.solution_steps,
        )
        assert verdict.accepted is False
        assert any("Tier1" in r for r in verdict.reasons)


class TestPositionVectorShape:
    def test_question_format_and_no_choices(self) -> None:
        gen = PositionVectorComponentSkeletonGenerator()
        for candidate in _drain(gen, _position_vector_spec(), 20):
            assert candidate.problem.question_format == QuestionFormat.단답형
            assert candidate.problem.choices is None
            assert candidate.problem.distractor_map is None

    def test_concept_tags_resolve_via_legacy_437_space(self) -> None:
        candidate = PositionVectorComponentSkeletonGenerator().generate(_position_vector_spec())
        assert candidate is not None
        assert len(candidate.concept_tags) == 1
        assert candidate.concept_tags[0].concept_src_id == "H:12기하03-02"

    def test_no_unverified_glyphs(self) -> None:
        gen = PositionVectorComponentSkeletonGenerator()
        for candidate in _drain(gen, _position_vector_spec(), 260):
            text = candidate.problem.question_text
            assert "Σ" not in text
            assert "α" not in text
            assert "β" not in text
