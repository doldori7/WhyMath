"""미적분(극값의 값) 스켈레톤 생성기 — hermetic(LLM 0·결정론) 단위·성질 테스트.

핵심 성질(전수/표본), 극값 x좌표 `test_calculus_skeleton_generator.py` 미러:
  ① 후보는 전부 S2-a 게이트 통과(accepted) — 결정론 코어가 곧 검증 가능성.
  ② answer_map은 derive_selected_root(독립 유도)와 정확히 일치 — 교차 검증.
  ③ 극댓값→largest·극솟값→smallest 매핑이 극값 쌍 이차방정식의 근과 정합.
  ④ 구조 signature 전부 상이·skip 존중·풀 소진 시 None·재현 결정론.
  ⑤ 개념/단원 태깅이 극대·극소([12미적Ⅰ-02-07]·H:12미적Ⅰ02-07)로 주입됨(극값 x좌표와 동일).
  ⑥ 정답(극값의 값) = f(임계점) — 독립 계산과 일치(값 환원 정합).
"""

from __future__ import annotations

from whymath_backend.l3.equivalent.acceptance import (
    EquivalenceSpec,
    evaluate_equivalent_candidate,
)
from whymath_backend.l3.equivalent.calculus_skeleton_generator import (
    CalculusExtremumValueSkeletonGenerator,
)
from whymath_backend.l3.equivalent.canonicalize import canonical_signature
from whymath_backend.l3.equivalent.generator import (
    CandidateProblem,
    EquivalentProblemGenerator,
)
from whymath_backend.l3.verify_answer import derive_selected_root
from whymath_backend.l3.verify_solution import verify_solution

_STANDARD = "[12미적Ⅰ-02-07]"


def _spec(**overrides: object) -> EquivalenceSpec:
    kwargs: dict[str, object] = {
        "achievement_standard_codes": frozenset({_STANDARD}),
        "target_misconception_ids": frozenset(),
        "difficulty_overall": 3.3,
        "answer_format": None,
    }
    kwargs.update(overrides)
    return EquivalenceSpec(**kwargs)  # type: ignore[arg-type]


def _draw(generator: CalculusExtremumValueSkeletonGenerator, n: int) -> list[CandidateProblem]:
    out: list[CandidateProblem] = []
    for _ in range(n):
        candidate = generator.generate(_spec())
        assert candidate is not None
        out.append(candidate)
    return out


class TestSeatContract:
    def test_satisfies_generator_protocol(self) -> None:
        assert isinstance(CalculusExtremumValueSkeletonGenerator(), EquivalentProblemGenerator)

    def test_deterministic_sequence(self) -> None:
        a = [c.problem.slug for c in _draw(CalculusExtremumValueSkeletonGenerator(), 5)]
        b = [c.problem.slug for c in _draw(CalculusExtremumValueSkeletonGenerator(), 5)]
        assert a == b

    def test_pool_exhaustion_returns_none(self) -> None:
        gen = CalculusExtremumValueSkeletonGenerator()
        count = 0
        while gen.generate(_spec()) is not None:
            count += 1
            assert count < 1000
        assert count > 100
        assert gen.generate(_spec()) is None


class TestMathematicalSoundness:
    def test_all_candidates_pass_acceptance_gate(self) -> None:
        for candidate in _draw(CalculusExtremumValueSkeletonGenerator(), 100):
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
        for candidate in _draw(CalculusExtremumValueSkeletonGenerator(), 100):
            assert candidate.answer_selection is not None
            derived = derive_selected_root(candidate.conditions, candidate.answer_selection)
            assert derived == candidate.answer_map["x"], candidate.conditions

    def test_pick_maps_to_correct_extremum_value(self) -> None:
        # ③ 극댓값→largest·극솟값→smallest — 발문의 극값 종류와 선택·정답 정합.
        for candidate in _draw(CalculusExtremumValueSkeletonGenerator(), 120):
            q = candidate.problem.question_text
            if "극댓값" in q:
                assert candidate.answer_selection == "largest"
            elif "극솟값" in q:
                assert candidate.answer_selection == "smallest"
            else:  # pragma: no cover — 템플릿은 극댓값/극솟값만
                raise AssertionError(f"발문에 극댓값/극솟값 없음: {q}")
            assert candidate.answer_map["x"] == candidate.problem.answer

    def test_answer_is_extremum_value_not_x_coordinate(self) -> None:
        # ⑥ 정답은 극값의 *값* f(임계점) — 임계점 x좌표(작은 정수 −9~9)가 아님을 표본으로 확인.
        # 값은 대체로 임계점 범위를 벗어난다(예 f(1)=4·f(3)=0·f(−1)=8) — 전건이 x좌표 대역이면
        # 회귀(x좌표 생성기 오연결). 값이 넓게 분포하는지(|정답|>9 다수)로 값 환원을 가른다.
        answers = {
            int(c.problem.answer) for c in _draw(CalculusExtremumValueSkeletonGenerator(), 120)
        }
        assert any(abs(a) > 9 for a in answers), "정답이 전부 임계점 x좌표 대역 — 값 환원 회귀 의심"


class TestSolutionSteps:
    def test_steps_emitted_and_fully_verified(self) -> None:
        # S2-02: 극값-값 문항도 *도함수 인수분해 체인만* — 극값 대입(f(m)=v)은 비동치 전이라
        # 체인에 못 섞고(단일 동치 스레드), 값 검증은 Tier1 conditions가 담당한다.
        for candidate in _draw(CalculusExtremumValueSkeletonGenerator(), 100):
            steps = candidate.solution_steps
            assert steps is not None and len(steps) == 2
            assert steps[0].startswith("3*x**2")  # 도함수 전개형에서 시작(미분 전이 미포함)
            assert steps[1].startswith("3*(")  # 3(x−m)(x−n) 인수분해형
            result = verify_solution(steps)
            assert result.has_incorrect is False, steps
            assert result.n_unverifiable == 0, steps
            assert result.n_correct >= 1


class TestStructuralDiversity:
    def test_signatures_all_distinct(self) -> None:
        sigs = [
            canonical_signature(c.conditions, c.answer_selection)
            for c in _draw(CalculusExtremumValueSkeletonGenerator(), 120)
        ]
        assert all(s is not None for s in sigs)
        assert len(set(sigs)) == len(sigs)

    def test_skip_signatures_respected(self) -> None:
        first = CalculusExtremumValueSkeletonGenerator().generate(_spec())
        assert first is not None
        skip = {canonical_signature(first.conditions, first.answer_selection)}
        gen = CalculusExtremumValueSkeletonGenerator(skip_signatures=skip)
        for _ in range(50):
            candidate = gen.generate(_spec())
            assert candidate is not None
            assert canonical_signature(candidate.conditions, candidate.answer_selection) not in skip


class TestMetadataInjection:
    def test_default_concept_and_unit_tags(self) -> None:
        candidate = CalculusExtremumValueSkeletonGenerator().generate(_spec())
        assert candidate is not None
        assert [t.concept_src_id for t in candidate.concept_tags] == ["H:12미적Ⅰ02-07"]
        assert candidate.problem.unit_codes == ["CALC-EXTREMUM-VALUE"]
        assert candidate.problem.achievement_standard_codes == [_STANDARD]

    def test_slug_prefix_is_calc_extv(self) -> None:
        candidate = CalculusExtremumValueSkeletonGenerator().generate(_spec())
        assert candidate is not None
        assert candidate.problem.slug.startswith("wm-calc-extv-")
