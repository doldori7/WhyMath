"""미적분(무리 임계점 극값) 스켈레톤 생성기 — hermetic(LLM 0·결정론) 단위·성질 테스트.

핵심 성질(전수/표본), 극값·접선 생성기 테스트 미러:
  ① 후보는 전부 S2-a 게이트 통과(accepted·verified) — 결정론 코어가 곧 검증 가능성.
  ② answer_map은 derive_selected_root(독립 유도)와 정확히 일치 — 무리수 정확값 교차 검증.
  ③ 극대→smallest·극소→largest 매핑이 도함수 근(p±√q) 대소와 정합·답은 무리수(sqrt 포함).
  ④ 구조 signature 전부 상이·skip 존중·풀 소진 시 None·재현 결정론(바이트 동일 slug).
  ⑤ 개념/단원 태깅이 극대·극소([12미적Ⅰ-02-07]·H:12미적Ⅰ02-07)로 주입됨.
  ⑥ 단답형·answer_format=실수·distractor_map None·삼차 전개 계수 전부 정수(답만 무리수).
"""

from __future__ import annotations

import sympy

from whymath_backend.l3.equivalent.acceptance import (
    EquivalenceSpec,
    evaluate_equivalent_candidate,
)
from whymath_backend.l3.equivalent.calculus_skeleton_generator import (
    CalculusIrrationalExtremumSkeletonGenerator,
    _build_irrational_pool,
)
from whymath_backend.l3.equivalent.canonicalize import canonical_signature
from whymath_backend.l3.equivalent.generator import (
    CandidateProblem,
    EquivalentProblemGenerator,
)
from whymath_backend.l3.verify_answer import derive_selected_root
from whymath_backend.l3.verify_solution import verify_solution
from whymath_backend.schema.enums import AnswerFormat, QuestionFormat

_STANDARD = "[12미적Ⅰ-02-07]"


def _spec(**overrides: object) -> EquivalenceSpec:
    kwargs: dict[str, object] = {
        "achievement_standard_codes": frozenset({_STANDARD}),
        "target_misconception_ids": frozenset(),
        "difficulty_overall": 3.5,
        "answer_format": AnswerFormat.실수,
    }
    kwargs.update(overrides)
    return EquivalenceSpec(**kwargs)  # type: ignore[arg-type]


def _draw(generator: CalculusIrrationalExtremumSkeletonGenerator, n: int) -> list[CandidateProblem]:
    out: list[CandidateProblem] = []
    for _ in range(n):
        candidate = generator.generate(_spec())
        assert candidate is not None
        out.append(candidate)
    return out


class TestSeatContract:
    def test_satisfies_generator_protocol(self) -> None:
        assert isinstance(CalculusIrrationalExtremumSkeletonGenerator(), EquivalentProblemGenerator)

    def test_deterministic_sequence(self) -> None:
        a = [c.problem.slug for c in _draw(CalculusIrrationalExtremumSkeletonGenerator(), 8)]
        b = [c.problem.slug for c in _draw(CalculusIrrationalExtremumSkeletonGenerator(), 8)]
        assert a == b

    def test_pool_exhaustion_returns_none(self) -> None:
        gen = CalculusIrrationalExtremumSkeletonGenerator()
        count = 0
        while gen.generate(_spec()) is not None:
            count += 1
            assert count < 1000
        assert count > 150  # 풀 180(9 p × 10 q × 2 종)
        assert gen.generate(_spec()) is None


class TestMathematicalSoundness:
    def test_all_candidates_pass_acceptance_gate(self) -> None:
        # ① 결정론 코어가 곧 검증 가능성 — 무리근 답도 S2-a 게이트를 통과해야 저장된다.
        for candidate in _draw(CalculusIrrationalExtremumSkeletonGenerator(), 120):
            verdict = evaluate_equivalent_candidate(
                _spec(),
                candidate.problem,
                provenance=candidate.provenance,
                conditions=candidate.conditions,
                answer_map=candidate.answer_map,
                solution_steps=candidate.solution_steps,  # S2-02: Tier2 단계 동치 포함 게이트
                answer_selection=candidate.answer_selection,
            )
            assert verdict.accepted is True, f"{candidate.problem.slug} 미수용: {verdict.reasons}"
            assert verdict.verification == "verified"

    def test_answer_matches_independent_derivation(self) -> None:
        # ② 무리수 정확값 교차 검증 — 독립 유도(sympy.solve 기반)가 answer_map과 문자 일치.
        for candidate in _draw(CalculusIrrationalExtremumSkeletonGenerator(), 120):
            assert candidate.answer_selection is not None
            derived = derive_selected_root(candidate.conditions, candidate.answer_selection)
            assert derived == candidate.answer_map["x"], candidate.conditions

    def test_pick_maps_to_correct_extremum_and_answer_is_irrational(self) -> None:
        # ③ 극대→smallest(작은 임계점)·극소→largest(큰 임계점)·답은 무리수(sqrt 포함).
        for candidate in _draw(CalculusIrrationalExtremumSkeletonGenerator(), 120):
            q = candidate.problem.question_text
            if "극대" in q or "극댓" in q:  # 극대·극댓값(사이시옷) 발문
                assert candidate.answer_selection == "smallest"
            elif "극소" in q or "극솟" in q:  # 극소·극솟값(사이시옷) 발문
                assert candidate.answer_selection == "largest"
            else:  # pragma: no cover — 템플릿은 극대/극소만
                raise AssertionError(f"발문에 극대/극소 없음: {q}")
            assert candidate.answer_map["x"] == candidate.problem.answer
            assert "sqrt" in candidate.problem.answer  # 무리근 임계점 — 답에 √ 존재

    def test_cubic_coefficients_are_integers(self) -> None:
        # ⑥ 임계점만 무리수·삼차함수 계수는 정수 — 발문의 삼차식에 sqrt가 없어야 한다.
        for candidate in _draw(CalculusIrrationalExtremumSkeletonGenerator(), 120):
            assert "sqrt" not in candidate.problem.question_text
            # conditions(도함수 monic)는 정수계수 이차식 — SymPy 파싱 후 유리계수 확인.
            lhs = candidate.conditions.split("=")[0]
            poly = sympy.Poly(sympy.sympify(lhs), sympy.Symbol("x"))
            assert all(c.is_integer for c in poly.all_coeffs())


class TestSolutionSteps:
    def test_steps_emitted_and_fully_verified(self) -> None:
        # S2-02: 무리근은 유리계수 인수분해 불가 — 도함수 전개형→3(x−p)²−3q 완전제곱형 체인
        # (sqrt quad 규약 미러). 전 전이 correct·unverifiable 0(수용 게이트 요구 미러).
        for candidate in _draw(CalculusIrrationalExtremumSkeletonGenerator(), 120):
            steps = candidate.solution_steps
            assert steps is not None and len(steps) == 2
            assert steps[0].startswith("3*x**2")  # 도함수 전개형에서 시작(미분 전이 미포함)
            result = verify_solution(steps)
            assert result.has_incorrect is False, steps
            assert result.n_unverifiable == 0, steps
            assert result.n_correct >= 1


class TestStructuralDiversity:
    def test_signatures_all_distinct(self) -> None:
        sigs = [
            canonical_signature(c.conditions, c.answer_selection)
            for c in _draw(CalculusIrrationalExtremumSkeletonGenerator(), 150)
        ]
        assert all(s is not None for s in sigs)
        assert len(set(sigs)) == len(sigs)

    def test_skip_signatures_respected(self) -> None:
        first = CalculusIrrationalExtremumSkeletonGenerator().generate(_spec())
        assert first is not None
        skip = {canonical_signature(first.conditions, first.answer_selection)}
        gen = CalculusIrrationalExtremumSkeletonGenerator(skip_signatures=skip)
        for _ in range(50):
            candidate = gen.generate(_spec())
            assert candidate is not None
            assert canonical_signature(candidate.conditions, candidate.answer_selection) not in skip

    def test_disjoint_from_integer_extremum_pool(self) -> None:
        # 무리근 monic은 판별식 비제곱 → 정수 극값 풀의 정수근 monic과 근의 체가 달라 서로소.
        pool = _build_irrational_pool()
        keys = {(*s.derivative_monic, s.selection) for s in pool}
        assert len(keys) == len(pool)  # 빌드 시점 dedup — 판박이 0


class TestMetadataInjection:
    def test_default_concept_and_unit_tags(self) -> None:
        candidate = CalculusIrrationalExtremumSkeletonGenerator().generate(_spec())
        assert candidate is not None
        assert [t.concept_src_id for t in candidate.concept_tags] == ["H:12미적Ⅰ02-07"]
        assert candidate.problem.unit_codes == ["CALC-EXTREMUM-IRR"]
        assert candidate.problem.achievement_standard_codes == [_STANDARD]

    def test_short_answer_real_format_no_distractors(self) -> None:
        # ⑥ 단답형·answer_format=실수·distractor_map None(오개념 주입 0·pending 게이트 미발생).
        for candidate in _draw(CalculusIrrationalExtremumSkeletonGenerator(), 30):
            assert candidate.problem.question_format == QuestionFormat.단답형
            assert candidate.problem.answer_format == AnswerFormat.실수
            assert candidate.problem.distractor_map is None
            assert candidate.problem.choices is None

    def test_slug_prefix_is_calc_extirr(self) -> None:
        candidate = CalculusIrrationalExtremumSkeletonGenerator().generate(_spec())
        assert candidate is not None
        assert candidate.problem.slug.startswith("wm-calc-extirr-")
