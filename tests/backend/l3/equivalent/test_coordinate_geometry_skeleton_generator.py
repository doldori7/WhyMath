"""좌표평면 — 두 점 사이의 거리·직선의 방정식 스켈레톤 생성기 단위테스트(hermetic·게이트 재사용).

`PointDistanceSkeletonGenerator`·`LineEquationSkeletonGenerator`가 ① 전건 S2-a 4종 게이트
통과 ② answer가 원시 좌표로부터의 독립 재계산(피타고라스·기울기 공식)과 일치 ③ 풀 유일
(구조 키)·소진 시 None ④ 답(거리·a+b) 재출현이 서로 다른 좌표쌍에서 정당함(형제 수열
생성기의 답-유일 dedup과 의도적으로 다른 설계 — 회귀 아님을 명시) ⑤ 조사(와/과·을/를)
정합·신규 Unicode 글리프 미사용 ⑥ 개념 태깅·위생 게이트 무오탐을 못 박는다. LLM·DB·PG 0.
"""

from __future__ import annotations

import math
import re

from whymath_backend.l3.equivalent.acceptance import (
    EquivalenceSpec,
    evaluate_equivalent_candidate,
)
from whymath_backend.l3.equivalent.coordinate_geometry_skeleton_generator import (
    LineEquationSkeletonGenerator,
    PointDistanceSkeletonGenerator,
    _build_distance_pool,
    _build_line_pool,
)
from whymath_backend.l3.equivalent.generator import CandidateProblem
from whymath_backend.schema.enums import QuestionFormat

_DISTANCE_STANDARD = "[10공수2-01-01]"
_LINE_STANDARD = "[10공수2-01-02]"


def _distance_spec() -> EquivalenceSpec:
    return EquivalenceSpec(
        achievement_standard_codes=frozenset({_DISTANCE_STANDARD}),
        target_misconception_ids=frozenset(),
        difficulty_overall=2.0,
        answer_format=None,
    )


def _line_spec() -> EquivalenceSpec:
    return EquivalenceSpec(
        achievement_standard_codes=frozenset({_LINE_STANDARD}),
        target_misconception_ids=frozenset(),
        difficulty_overall=2.2,
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


class TestDistancePool:
    def test_pool_nonempty_and_structurally_unique(self) -> None:
        pool = _build_distance_pool()
        assert len(pool) >= 200
        keys = {(s.x1, s.y1, s.x2, s.y2) for s in pool}
        assert len(keys) == len(pool)

    def test_answer_matches_independent_pythagorean_recompute(self) -> None:
        """교차 검증 — answer가 생성기 밖 독립 재계산(√((x2-x1)²+(y2-y1)²))과 일치."""
        for skeleton in _build_distance_pool()[:150]:
            dx = skeleton.x2 - skeleton.x1
            dy = skeleton.y2 - skeleton.y1
            assert skeleton.answer == math.isqrt(dx * dx + dy * dy)
            assert skeleton.answer**2 == dx * dx + dy * dy  # 완전제곱 보장(정수 답).

    def test_answers_legitimately_repeat_across_distinct_pairs(self) -> None:
        """답(거리) 재출현은 이 도메인에서 정상 — 형제 수열 생성기의 답-유일 dedup과 의도적으로
        다른 설계임을 명시(quad_ineq 관례 계승). 회귀로 오판하지 않도록 못 박는다."""
        pool = _build_distance_pool()
        answers = [s.answer for s in pool]
        assert len(set(answers)) < len(answers)  # 답 종류는 유한(삼조 10개)·좌표쌍은 그보다 많다.

    def test_generation_exhausts_to_none(self) -> None:
        pool_size = len(_build_distance_pool())
        gen = PointDistanceSkeletonGenerator()
        drained = _drain(gen, _distance_spec(), pool_size + 5)
        assert len(drained) == pool_size
        assert gen.generate(_distance_spec()) is None


class TestDistanceAcceptance:
    def test_all_pass_acceptance_gate(self) -> None:
        candidates = _drain(PointDistanceSkeletonGenerator(), _distance_spec(), 200)
        assert len(candidates) >= 200
        for candidate in candidates:
            verdict = evaluate_equivalent_candidate(
                _distance_spec(),
                candidate.problem,
                provenance=candidate.provenance,
                conditions=candidate.conditions,
                answer_map=candidate.answer_map,
                solution_steps=candidate.solution_steps,
            )
            assert verdict.accepted is True, f"{candidate.problem.slug} 미수용: {verdict.reasons}"
            assert verdict.verification == "verified"

    def test_gate_rejects_wrong_answer(self) -> None:
        candidate = PointDistanceSkeletonGenerator().generate(_distance_spec())
        assert candidate is not None
        broken_answer = str(int(candidate.problem.answer) + 1)
        verdict = evaluate_equivalent_candidate(
            _distance_spec(),
            candidate.problem.model_copy(update={"answer": broken_answer}),
            provenance=candidate.provenance,
            conditions=candidate.conditions,
            answer_map={"x": broken_answer},
            solution_steps=candidate.solution_steps,
        )
        assert verdict.accepted is False
        assert any("Tier1" in r for r in verdict.reasons)


class TestDistanceShape:
    def test_question_format_and_no_choices(self) -> None:
        for candidate in _drain(PointDistanceSkeletonGenerator(), _distance_spec(), 20):
            assert candidate.problem.question_format == QuestionFormat.단답형
            assert candidate.problem.choices is None
            assert candidate.problem.distractor_map is None

    def test_concept_tags_resolve_via_legacy_437_space(self) -> None:
        candidate = PointDistanceSkeletonGenerator().generate(_distance_spec())
        assert candidate is not None
        assert len(candidate.concept_tags) == 1
        assert candidate.concept_tags[0].concept_src_id == "HK17"

    def test_no_unverified_glyphs_and_josa_correct(self) -> None:
        """신규 글리프 미사용 + '와/과' 조사 정합 — 2026-08-07 실측 회귀 봉인.

        최초 설계는 두 번째 템플릿에 '을/를'을 잘못 적용해 "(-3, 3)을 (0, 7) 사이의 거리"처럼
        비문이 났다(연결 조사 '와/과'가 필요한 자리에 목적격 조사를 씀) — 스파이크 테스트로
        발견해 `josa.wa_gwa`로 교정했다. 그 회귀를 봉인한다.
        """
        for candidate in _drain(PointDistanceSkeletonGenerator(), _distance_spec(), 200):
            text = candidate.problem.question_text
            assert "Σ" not in text
            assert "∑" not in text
            assert "α" not in text
            assert "β" not in text
            if "좌표평면 위의" in text:
                assert re.search(r"\)\s*(을|를)\s*\(", text) is None, text
                assert re.search(r"\)\s*(과|와)\s*\(", text) is not None, text


class TestLinePool:
    def test_pool_nonempty_and_structurally_unique(self) -> None:
        pool = _build_line_pool()
        assert len(pool) >= 200
        keys = {(s.x1, s.y1, s.x2, s.y2) for s in pool}
        assert len(keys) == len(pool)
        for skeleton in pool:
            assert skeleton.x1 != skeleton.x2  # 수직선 배제(기울기 정의역).

    def test_answer_matches_independent_slope_intercept_recompute(self) -> None:
        """교차 검증 — answer(a+b)가 원시 좌표로부터의 독립 재계산과 일치."""
        for skeleton in _build_line_pool()[:150]:
            slope = (skeleton.y2 - skeleton.y1) / (skeleton.x2 - skeleton.x1)
            intercept = skeleton.y1 - slope * skeleton.x1
            assert skeleton.answer == round(slope + intercept)

    def test_generation_exhausts_to_none(self) -> None:
        pool_size = len(_build_line_pool())
        gen = LineEquationSkeletonGenerator()
        drained = _drain(gen, _line_spec(), pool_size + 5)
        assert len(drained) == pool_size
        assert gen.generate(_line_spec()) is None


class TestLineAcceptance:
    def test_all_pass_acceptance_gate(self) -> None:
        candidates = _drain(LineEquationSkeletonGenerator(), _line_spec(), 200)
        assert len(candidates) >= 200
        for candidate in candidates:
            verdict = evaluate_equivalent_candidate(
                _line_spec(),
                candidate.problem,
                provenance=candidate.provenance,
                conditions=candidate.conditions,
                answer_map=candidate.answer_map,
                solution_steps=candidate.solution_steps,
            )
            assert verdict.accepted is True, f"{candidate.problem.slug} 미수용: {verdict.reasons}"
            assert verdict.verification == "verified"

    def test_gate_rejects_wrong_answer(self) -> None:
        candidate = LineEquationSkeletonGenerator().generate(_line_spec())
        assert candidate is not None
        broken_answer = str(int(candidate.problem.answer) + 1)
        verdict = evaluate_equivalent_candidate(
            _line_spec(),
            candidate.problem.model_copy(update={"answer": broken_answer}),
            provenance=candidate.provenance,
            conditions=candidate.conditions,
            answer_map={"x": broken_answer},
            solution_steps=candidate.solution_steps,
        )
        assert verdict.accepted is False
        assert any("Tier1" in r for r in verdict.reasons)


class TestLineShape:
    def test_question_format_and_no_choices(self) -> None:
        for candidate in _drain(LineEquationSkeletonGenerator(), _line_spec(), 20):
            assert candidate.problem.question_format == QuestionFormat.단답형
            assert candidate.problem.choices is None
            assert candidate.problem.distractor_map is None

    def test_concept_tags_resolve_via_legacy_437_space(self) -> None:
        candidate = LineEquationSkeletonGenerator().generate(_line_spec())
        assert candidate is not None
        assert len(candidate.concept_tags) == 1
        assert candidate.concept_tags[0].concept_src_id == "HK19"

    def test_no_unverified_glyphs(self) -> None:
        for candidate in _drain(LineEquationSkeletonGenerator(), _line_spec(), 200):
            text = candidate.problem.question_text
            assert "Σ" not in text
            assert "∑" not in text
            assert "α" not in text
            assert "β" not in text
