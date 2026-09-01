"""중등 일차함수 함숫값 결정론 스켈레톤 생성기 — W2 단위테스트(hermetic·게이트 재사용).

`LinearFunctionValueSkeletonGenerator`가 ① 전건 S2-a 4종 게이트 통과(초등 산술·고등 행렬·
대학 미분에 이어 네 번째 도메인에서 게이트 인프라 무변경 재사용 재실증) ② answer가 독립
재계산(대입 산술)과 일치 ③ 풀 유일·소진 시 None ④ 개념 태깅이 legacy 437 공간 실존 개념
(J0214)이라 정상 동작함(대학 태깅 공백과 대비 확인) ⑤ 조사(을/를) 정확성·표기 정갈함(계수 1·
이중부호 생략)·위생 게이트 무오탐을 못 박는다. LLM·DB·PG 0(순수 결정론).
"""

from __future__ import annotations

from whymath_backend.l3.equivalent.acceptance import (
    EquivalenceSpec,
    evaluate_equivalent_candidate,
)
from whymath_backend.l3.equivalent.generator import CandidateProblem
from whymath_backend.l3.equivalent.linear_function_value_skeleton_generator import (
    LinearFunctionValueSkeletonGenerator,
    _build_pool,
)
from whymath_backend.schema.enums import QuestionFormat

_STANDARD = "[9수02-14]"


def _spec() -> EquivalenceSpec:
    return EquivalenceSpec(
        achievement_standard_codes=frozenset({_STANDARD}),
        target_misconception_ids=frozenset(),
        difficulty_overall=1.8,
        answer_format=None,
    )


def _drain(gen: LinearFunctionValueSkeletonGenerator, limit: int) -> list[CandidateProblem]:
    out: list[CandidateProblem] = []
    while len(out) < limit:
        candidate = gen.generate(_spec())
        if candidate is None:
            break
        out.append(candidate)
    return out


class TestPool:
    def test_pool_nonempty_and_unique(self) -> None:
        pool = _build_pool()
        assert len(pool) >= 250
        keys = {(s.a, s.b, s.k) for s in pool}
        assert len(keys) == len(pool)

    def test_slope_never_zero(self) -> None:
        """기울기 a가 0이면 상수함수가 되어 "일차함수" 취지가 무너진다."""
        for skeleton in _build_pool():
            assert skeleton.a != 0

    def test_generation_exhausts_to_none(self) -> None:
        pool_size = len(_build_pool())
        gen = LinearFunctionValueSkeletonGenerator()
        drained = _drain(gen, pool_size + 10)
        assert len(drained) == pool_size
        assert gen.generate(_spec()) is None


class TestAcceptanceGate:
    def test_all_pass_acceptance_gate(self) -> None:
        candidates = _drain(LinearFunctionValueSkeletonGenerator(), 150)
        assert len(candidates) >= 150
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

    def test_answer_matches_independent_substitution(self) -> None:
        """교차 검증 — answer가 생성기 밖 독립 재계산(단순 대입)과 일치."""
        for skeleton in _build_pool()[:100]:
            assert skeleton.result == skeleton.a * skeleton.k + skeleton.b

    def test_gate_rejects_wrong_answer(self) -> None:
        """변별력 — 정답을 1 틀리게 만든 후보는 Tier1 대입 검산에서 거부된다."""
        candidate = LinearFunctionValueSkeletonGenerator().generate(_spec())
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


class TestCandidateShape:
    def test_question_format_and_no_choices(self) -> None:
        for candidate in _drain(LinearFunctionValueSkeletonGenerator(), 20):
            assert candidate.problem.question_format == QuestionFormat.단답형
            assert candidate.problem.choices is None
            assert candidate.problem.distractor_map is None

    def test_difficulty_is_fixed_awareness_procedural_boundary(self) -> None:
        for candidate in _drain(LinearFunctionValueSkeletonGenerator(), 30):
            assert candidate.problem.difficulty_overall == 1.8

    def test_concept_tags_resolve_via_legacy_437_space(self) -> None:
        """대학 축(concept_tags=()) 공백과 대비 — 이 개념은 legacy 공간에 실존해 정상 태깅."""
        candidate = LinearFunctionValueSkeletonGenerator().generate(_spec())
        assert candidate is not None
        assert len(candidate.concept_tags) == 1
        assert candidate.concept_tags[0].concept_src_id == "J0214"
        assert candidate.concept_tags[0].role == "PRIMARY"

    def test_solution_steps_intentionally_none(self) -> None:
        candidate = LinearFunctionValueSkeletonGenerator().generate(_spec())
        assert candidate is not None
        assert candidate.solution_steps is None

    def test_no_double_sign_or_redundant_unit_coefficient_in_display(self) -> None:
        """표기 정갈함 — '+ -3x'(이중부호)·'1x'(불필요한 계수 1) 금지."""
        for candidate in _drain(LinearFunctionValueSkeletonGenerator(), 100):
            text = candidate.problem.question_text
            assert "+ -" not in text
            assert "- -" not in text
            assert "1x" not in text

    def test_josa_alternates_with_number_reading(self) -> None:
        """조사(을/를)가 숫자 읽기 기반으로 선택된다 — 하드코딩이면 한쪽만 관측된다(변별력).

        발문(question_text)·해설(answer_explanation) 둘 다 조사를 쓰므로 함께 확인한다
        (2026-08-05 실측 사고: 해설에서 조사를 재차 하드코딩해 회귀 — 재발 방지 봉인).
        """
        candidates = _drain(LinearFunctionValueSkeletonGenerator(), 80)
        joined = " ".join(
            c.problem.question_text + " " + c.problem.answer_explanation for c in candidates
        )
        assert "을 " in joined or "를 " in joined
        assert "을" in joined and "를" in joined  # 둘 다 관측(하드코딩이면 한쪽만 나옴).


class TestSkipConditions:
    def test_skip_conditions_filters_already_seen(self) -> None:
        seen: set[str] = set()
        first = LinearFunctionValueSkeletonGenerator(skip_conditions=seen).generate(_spec())
        assert first is not None
        seen.add(first.conditions)  # type: ignore[arg-type]

        second = LinearFunctionValueSkeletonGenerator(skip_conditions=seen).generate(_spec())
        assert second is not None
        assert second.conditions != first.conditions
