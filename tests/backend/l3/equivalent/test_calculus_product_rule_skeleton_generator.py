"""대학 미적분학 I 곱의 미분법 결정론 스켈레톤 생성기 — W2 단위테스트(hermetic·게이트 재사용).

`CalculusProductRuleSkeletonGenerator`가 ① 전건 S2-a 4종 게이트 통과(초등 산술·고등 행렬에
이어 세 번째 도메인·최초 미분 도메인에서 게이트 인프라 무변경 재사용 재실증) ② answer가
독립 재계산(곱의 미분법 전개식·SymPy 밖 순수 정수 산술)과 일치 ③ 풀 유일·소진 시 None
④ 위생 게이트(SymPy 산술/방정식 시드 검증기)가 해설 산문의 거짓 양성 오탐을 안 내는지
(2026-08-05 실측 사고 2건의 재발 방지 회귀 봉인) ⑤ 조사(을/를) 정확성·표기 정갈함(계수 1·
이중부호 생략)을 못 박는다. LLM·DB·PG 0(순수 결정론).
"""

from __future__ import annotations

from whymath_backend.l3.equivalent.acceptance import (
    EquivalenceSpec,
    evaluate_equivalent_candidate,
)
from whymath_backend.l3.equivalent.calculus_product_rule_skeleton_generator import (
    CalculusProductRuleSkeletonGenerator,
    _build_pool,
)
from whymath_backend.l3.equivalent.generator import CandidateProblem
from whymath_backend.schema.enums import QuestionFormat

_STANDARD = "[CALC1-02-02]"


def _spec() -> EquivalenceSpec:
    return EquivalenceSpec(
        achievement_standard_codes=frozenset({_STANDARD}),
        target_misconception_ids=frozenset(),
        difficulty_overall=3.8,
        answer_format=None,
    )


def _drain(gen: CalculusProductRuleSkeletonGenerator, limit: int) -> list[CandidateProblem]:
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
        keys = {(s.a, s.b, s.c, s.d, s.e, s.k) for s in pool}
        assert len(keys) == len(pool)

    def test_leading_coefficients_never_zero(self) -> None:
        """a·d는 0이 아니어야 각각 진짜 이차식·일차식(0이면 차수가 무너져 문제 취지 훼손)."""
        for skeleton in _build_pool():
            assert skeleton.a != 0
            assert skeleton.d != 0

    def test_generation_exhausts_to_none(self) -> None:
        pool_size = len(_build_pool())
        gen = CalculusProductRuleSkeletonGenerator()
        drained = _drain(gen, pool_size + 10)
        assert len(drained) == pool_size
        assert gen.generate(_spec()) is None


class TestAcceptanceGate:
    def test_all_pass_acceptance_gate(self) -> None:
        """전건 4종 게이트(저작권·정확성·위생·동등성) 통과 — 위생 게이트 오탐 실측 회귀 봉인.

        2026-08-05 실측: 해설 산문에 "f'(k)g(k)+f(k)g'(k) = 답" 형태를 그대로 쓰면 SymPy
        산술 시드 검증기가 괄호숫자 뒤 등호를 독립 등식으로 오탐(arithmetic)했고, 이를
        "f'(x)=2ax+b" 뒤 "x=k"로 고쳐도 방정식 시드 검증기가 "그 방정식의 해가 x=k"로
        오탐(solution)했다. 현재 해설은 등호를 아예 쓰지 않는 서술형이라 둘 다 피한다 —
        이 테스트가 그 우회를 다시 깨는 회귀(형식 변경 시 오탐 부활)를 잡는다.
        """
        candidates = _drain(CalculusProductRuleSkeletonGenerator(), 150)
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

    def test_answer_matches_independent_product_rule_recomputation(self) -> None:
        """교차 검증 — answer가 생성기 밖 독립 재계산(곱의 미분법 전개식)과 일치."""
        for skeleton in _build_pool()[:80]:
            a, b, c, d, e, k = (
                skeleton.a,
                skeleton.b,
                skeleton.c,
                skeleton.d,
                skeleton.e,
                skeleton.k,
            )
            f1_prime_at_k = 2 * a * k + b
            f2_at_k = d * k + e
            f1_at_k = a * k * k + b * k + c
            expected = f1_prime_at_k * f2_at_k + f1_at_k * d
            assert skeleton.result == expected

    def test_gate_rejects_wrong_answer(self) -> None:
        """변별력 — 정답을 1 틀리게 만든 후보는 Tier1 미분 평가 검산에서 거부된다."""
        candidate = CalculusProductRuleSkeletonGenerator().generate(_spec())
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
        for candidate in _drain(CalculusProductRuleSkeletonGenerator(), 20):
            assert candidate.problem.question_format == QuestionFormat.단답형
            assert candidate.problem.choices is None
            assert candidate.problem.distractor_map is None

    def test_difficulty_is_fixed_conceptual_mastery_boundary(self) -> None:
        for candidate in _drain(CalculusProductRuleSkeletonGenerator(), 30):
            assert candidate.problem.difficulty_overall == 3.8

    def test_concept_tags_intentionally_empty(self) -> None:
        """개념 태깅 공백(모듈 docstring) — 가짜 orphan-skip 태그 대신 정직하게 빈 목록."""
        candidate = CalculusProductRuleSkeletonGenerator().generate(_spec())
        assert candidate is not None
        assert candidate.concept_tags == []

    def test_solution_steps_intentionally_none(self) -> None:
        candidate = CalculusProductRuleSkeletonGenerator().generate(_spec())
        assert candidate is not None
        assert candidate.solution_steps is None

    def test_no_double_sign_or_redundant_unit_coefficient_in_display(self) -> None:
        """표기 정갈함 — '+ -3x'(이중부호)·'1x^2'(불필요한 계수 1) 금지."""
        for candidate in _drain(CalculusProductRuleSkeletonGenerator(), 100):
            text = candidate.problem.question_text
            assert "+ -" not in text
            assert "- -" not in text
            assert "1x" not in text  # 계수 1은 생략(선두·중간 항 공통).

    def test_josa_alternates_with_number_reading(self) -> None:
        """조사(을/를)가 숫자 읽기 기반으로 선택된다 — 하드코딩이면 한쪽만 관측된다(변별력)."""
        texts = [
            c.problem.question_text
            for c in _drain(CalculusProductRuleSkeletonGenerator(), 80)
            if "구하시오" in c.problem.question_text and "값을" not in c.problem.question_text
        ]
        joined = " ".join(texts)
        assert "을 구하시오" in joined or "를 구하시오" in joined


class TestSkipConditions:
    def test_skip_conditions_filters_already_seen(self) -> None:
        seen: set[str] = set()
        first = CalculusProductRuleSkeletonGenerator(skip_conditions=seen).generate(_spec())
        assert first is not None
        seen.add(first.conditions)  # type: ignore[arg-type]

        second = CalculusProductRuleSkeletonGenerator(skip_conditions=seen).generate(_spec())
        assert second is not None
        assert second.conditions != first.conditions
