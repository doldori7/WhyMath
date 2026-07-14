"""미적분(극값) 스켈레톤 생성기 — hermetic(LLM 0·결정론) 단위·성질 테스트.

핵심 성질(전수/표본), quad `test_skeleton_generator.py` 미러:
  ① 후보는 전부 S2-a 게이트 통과(accepted) — 결정론 코어가 곧 검증 가능성.
  ② answer_map은 derive_selected_root(독립 유도)와 정확히 일치 — 교차 검증.
  ③ 극대→작은 임계점(smallest)·극소→큰 임계점(largest) 매핑이 실제 도함수 근과 정합.
  ④ 구조 signature 전부 상이·skip_signatures 존중·풀 소진 시 None·재현 결정론.
  ⑤ 개념/단원 태깅이 미적분 극값([12미적Ⅰ-02-07]·H:12미적Ⅰ02-07)으로 주입됨.
"""

from __future__ import annotations

from whymath_backend.l3.equivalent.acceptance import (
    EquivalenceSpec,
    evaluate_equivalent_candidate,
)
from whymath_backend.l3.equivalent.calculus_skeleton_generator import (
    CalculusExtremumSkeletonGenerator,
)
from whymath_backend.l3.equivalent.canonicalize import canonical_signature
from whymath_backend.l3.equivalent.generator import (
    CandidateProblem,
    EquivalentProblemGenerator,
)
from whymath_backend.l3.verify_answer import derive_selected_root
from whymath_backend.l3.verify_solution import verify_solution
from whymath_backend.schema.enums import AnswerFormat

_STANDARD = "[12미적Ⅰ-02-07]"


def _spec(**overrides: object) -> EquivalenceSpec:
    kwargs: dict[str, object] = {
        "achievement_standard_codes": frozenset({_STANDARD}),
        "target_misconception_ids": frozenset(),
        "difficulty_overall": 3.3,
        "answer_format": AnswerFormat.실수,
    }
    kwargs.update(overrides)
    return EquivalenceSpec(**kwargs)  # type: ignore[arg-type]


def _draw(generator: CalculusExtremumSkeletonGenerator, n: int) -> list[CandidateProblem]:
    out: list[CandidateProblem] = []
    for _ in range(n):
        candidate = generator.generate(_spec())
        assert candidate is not None
        out.append(candidate)
    return out


class TestSeatContract:
    def test_satisfies_generator_protocol(self) -> None:
        assert isinstance(CalculusExtremumSkeletonGenerator(), EquivalentProblemGenerator)

    def test_deterministic_sequence(self) -> None:
        a = [c.problem.slug for c in _draw(CalculusExtremumSkeletonGenerator(), 5)]
        b = [c.problem.slug for c in _draw(CalculusExtremumSkeletonGenerator(), 5)]
        assert a == b

    def test_pool_exhaustion_returns_none(self) -> None:
        gen = CalculusExtremumSkeletonGenerator()
        count = 0
        while gen.generate(_spec()) is not None:
            count += 1
            assert count < 1000  # 무한루프 방어(풀은 유한)
        assert count > 100  # 수백 조합(단조 방지)
        assert gen.generate(_spec()) is None  # 소진 후에도 안정적으로 None


class TestMathematicalSoundness:
    def test_all_candidates_pass_acceptance_gate(self) -> None:
        # ① 결정론 코어 = 게이트 통과 가능성 — 표본 100 전건 accepted(verified).
        for candidate in _draw(CalculusExtremumSkeletonGenerator(), 100):
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
        # ② 교차 검증 — 생성기 answer_map을 도함수 방정식의 독립 유도(derive_selected_root)와 대조.
        for candidate in _draw(CalculusExtremumSkeletonGenerator(), 100):
            assert candidate.answer_selection is not None
            derived = derive_selected_root(candidate.conditions, candidate.answer_selection)
            assert derived == candidate.answer_map["x"], candidate.conditions

    def test_extremum_kind_maps_to_correct_critical_point(self) -> None:
        # ③ 극대→작은 임계점(smallest)·극소→큰 임계점(largest) — 발문 종류와 선택·정답 정합.
        for candidate in _draw(CalculusExtremumSkeletonGenerator(), 120):
            q = candidate.problem.question_text
            # 사이시옷 주의 — 극댓값/극솟값은 '극대'/'극소'를 부분문자열로 갖지 않는다.
            is_max = "극대" in q or "극댓값" in q
            is_min = "극소" in q or "극솟값" in q
            assert is_max != is_min, f"발문 극대/극소 판별 실패: {q}"
            if is_max:
                assert candidate.answer_selection == "smallest"  # 극대 = 작은 임계점
            else:
                assert candidate.answer_selection == "largest"  # 극소 = 큰 임계점
            # answer_map의 근이 실제 도함수 방정식의 그 극단 근인지 재확인(derive와 별개 경로).
            assert candidate.answer_map["x"] == candidate.problem.answer


class TestSolutionSteps:
    def test_steps_emitted_and_fully_verified(self) -> None:
        # S2-02: 도함수 전개형→인수분해형 체인 — 전 전이 correct·unverifiable 0(게이트 요구 미러).
        for candidate in _draw(CalculusExtremumSkeletonGenerator(), 100):
            steps = candidate.solution_steps
            assert steps is not None and len(steps) == 2
            assert steps[0].startswith("3*x**2")  # 미분 전이 미포함 — 도함수 다항식에서 시작
            assert steps[1].startswith("3*(")  # 3(x−m)(x−n) 인수분해형
            result = verify_solution(steps)
            assert result.has_incorrect is False, steps
            assert result.n_unverifiable == 0, steps
            assert result.n_correct >= 1


class TestStructuralDiversity:
    def test_signatures_all_distinct(self) -> None:
        # ④ 판박이가 생성 자체가 안 됨 — 표본 signature 전건 상이.
        sigs = [
            canonical_signature(c.conditions, c.answer_selection)
            for c in _draw(CalculusExtremumSkeletonGenerator(), 120)
        ]
        assert all(s is not None for s in sigs)
        assert len(set(sigs)) == len(sigs)

    def test_skip_signatures_respected(self) -> None:
        # 이미 코퍼스에 있는 구조는 건너뛴다 — skip에 든 첫 후보 signature는 재출제되지 않는다.
        first = CalculusExtremumSkeletonGenerator().generate(_spec())
        assert first is not None
        skip = {canonical_signature(first.conditions, first.answer_selection)}
        gen = CalculusExtremumSkeletonGenerator(skip_signatures=skip)
        for _ in range(50):
            candidate = gen.generate(_spec())
            assert candidate is not None
            assert canonical_signature(candidate.conditions, candidate.answer_selection) not in skip


class TestMetadataInjection:
    def test_default_concept_and_unit_tags(self) -> None:
        # ⑤ 미적분 극값 태깅 — 개념 src_id·단원·성취기준이 결정론 주입됨.
        candidate = CalculusExtremumSkeletonGenerator().generate(_spec())
        assert candidate is not None
        assert [t.concept_src_id for t in candidate.concept_tags] == ["H:12미적Ⅰ02-07"]
        assert candidate.problem.unit_codes == ["CALC-EXTREMUM"]
        assert candidate.problem.achievement_standard_codes == [_STANDARD]

    def test_slug_prefix_is_calc(self) -> None:
        candidate = CalculusExtremumSkeletonGenerator().generate(_spec())
        assert candidate is not None
        assert candidate.problem.slug.startswith("wm-calc-ext-")
