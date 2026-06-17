"""순수 `verify_solution` 연쇄 검증 집계 단위테스트 — WH-1 1단계 결선(§3.1·hermetic).

다단계 연쇄(전부 correct·중간 incorrect·unverifiable 섞임)·`unverified_ratio`·
`first_incorrect_index`·`has_incorrect`·step_types 전파(전이별)·길이 규약(ValueError)·엣지
(steps <2·빈 리스트)·카운트 합 = n_transitions·결정론·필드셋·`verify_step` 결과 그대로 집계
(재구현 아님)를 검증한다.

텍스트→단계 분해(L5)·coach 결선·PRM 가중치는 *후속*이라 여기 없다(본 슬라이스는 집계만).
"""

from __future__ import annotations

import pytest

from whymath_backend.l3.verify_solution import (
    SolutionVerificationResult,
    verify_solution,
)
from whymath_backend.l3.verify_step import VerifyStepState, verify_step
from whymath_backend.schema.enums import StepType


class TestAllCorrectChain:
    """전부 correct인 연쇄 — 동치 변형만 이어진 풀이."""

    def test_three_step_all_correct(self) -> None:
        # 2(x+1) ≡ 2x+2 ≡ 2(x+1) — 두 전이 모두 심볼릭 동치.
        result = verify_solution(["2*(x+1)", "2*x+2", "2*(x+1)"])
        assert result.n_transitions == 2
        assert result.n_correct == 2
        assert result.n_incorrect == 0
        assert result.n_unverifiable == 0
        assert result.unverified_ratio == 0.0
        assert result.first_incorrect_index is None
        assert result.has_incorrect is False
        assert all(s.state == VerifyStepState.correct for s in result.steps)

    def test_two_step_correct(self) -> None:
        result = verify_solution(["2+3", "5"])
        assert result.n_transitions == 1
        assert result.n_correct == 1
        assert result.has_incorrect is False


class TestIncorrectInMiddle:
    """중간에 incorrect가 낀 연쇄 — `first_incorrect_index`가 정확해야 한다."""

    def test_first_incorrect_index_points_to_first_bad_transition(self) -> None:
        # 전이0: 2x ≡ 2x (correct)·전이1: 2x → 2x+1 (constant diff·incorrect)·
        # 전이2: 2x+1 ≡ 2x+1 (correct). 첫 incorrect는 전이1.
        result = verify_solution(["2*x", "2*x", "2*x+1", "2*x+1"])
        assert result.n_transitions == 3
        assert result.n_correct == 2
        assert result.n_incorrect == 1
        assert result.first_incorrect_index == 1
        assert result.has_incorrect is True

    def test_multiple_incorrect_records_only_first(self) -> None:
        # 전이0 correct·전이1 incorrect·전이2 incorrect — first_incorrect_index는 1만.
        result = verify_solution(["x", "x", "x+1", "x+3"])
        assert result.n_incorrect == 2
        assert result.first_incorrect_index == 1

    def test_incorrect_at_first_transition(self) -> None:
        result = verify_solution(["2*x+1", "2*x+3", "2*x+3"])
        assert result.first_incorrect_index == 0
        assert result.n_incorrect == 1


class TestUnverifiableRatio:
    """unverifiable 섞인 연쇄 — `unverified_ratio`가 정확해야 한다."""

    def test_ratio_half(self) -> None:
        # 전이0: 2+3≡5 (correct)·전이1: 산문→산문 (판정 불가·unverifiable). 1/2.
        result = verify_solution(["2+3", "5", "어쩌고저쩌고"])
        assert result.n_transitions == 2
        assert result.n_correct == 1
        assert result.n_unverifiable == 1
        assert result.unverified_ratio == pytest.approx(0.5)

    def test_ratio_all_unverifiable(self) -> None:
        # 두 전이 모두 산문(판정 불가) → unverifiable 2/2 = 1.0.
        result = verify_solution(["가나다", "라마바", "사아자"])
        assert result.n_unverifiable == 2
        assert result.unverified_ratio == pytest.approx(1.0)
        assert result.has_incorrect is False

    def test_ratio_mixed_three_states(self) -> None:
        # 전이0 correct(2+3≡5)·전이1 incorrect(5→6)·전이2 unverifiable(6→산문). 1/3.
        result = verify_solution(["2+3", "5", "6", "어쩌고"])
        assert result.n_correct == 1
        assert result.n_incorrect == 1
        assert result.n_unverifiable == 1
        assert result.unverified_ratio == pytest.approx(1 / 3)
        assert result.first_incorrect_index == 1


class TestStepTypesPropagation:
    """step_types가 *전이별*로 verify_step에 전파되는지(전이당 하나)."""

    def test_step_types_propagated_per_transition(self) -> None:
        # 전이0: 계산(대수 경로)·전이1: 조건해석(비대수 → unverifiable·동치여도 시도 안 함).
        result = verify_solution(
            ["2+3", "5", "5"],
            step_types=[StepType.계산, StepType.조건해석],
        )
        assert result.steps[0].step_type == StepType.계산
        assert result.steps[0].state == VerifyStepState.correct
        assert result.steps[1].step_type == StepType.조건해석
        # 5≡5라도 비대수 step_type이면 verify_step이 unverifiable로 떨어뜨린다(상속).
        assert result.steps[1].state == VerifyStepState.unverifiable
        assert result.n_unverifiable == 1

    def test_step_types_none_means_all_none(self) -> None:
        result = verify_solution(["2+3", "5"])
        assert result.steps[0].step_type is None


class TestStepTypesLengthContract:
    """step_types 길이 규약 — 전이 개수와 다르면 ValueError(조용한 패딩 금지)."""

    def test_too_short_raises(self) -> None:
        # 전이 2개인데 step_types 1개 → ValueError.
        with pytest.raises(ValueError, match="step_types 길이"):
            verify_solution(["2+3", "5", "5"], step_types=[StepType.계산])

    def test_too_long_raises(self) -> None:
        # 전이 1개인데 step_types 2개 → ValueError.
        with pytest.raises(ValueError, match="step_types 길이"):
            verify_solution(["2+3", "5"], step_types=[StepType.계산, StepType.검산])

    def test_exact_length_ok(self) -> None:
        # 전이 1개·step_types 1개 → OK.
        result = verify_solution(["2+3", "5"], step_types=[StepType.계산])
        assert result.n_transitions == 1

    def test_empty_step_types_with_no_transitions_ok(self) -> None:
        # 단계 1개 → 전이 0개·step_types 빈 리스트 OK(길이 일치).
        result = verify_solution(["2+3"], step_types=[])
        assert result.n_transitions == 0


class TestEdgeCases:
    """엣지 — 단계 <2·빈 리스트는 전이 0개의 정직한 빈 결과(에러 아님)."""

    def test_single_step_empty_result(self) -> None:
        result = verify_solution(["2+3"])
        assert result.n_transitions == 0
        assert result.steps == []
        assert result.n_correct == 0
        assert result.n_incorrect == 0
        assert result.n_unverifiable == 0
        assert result.unverified_ratio == 0.0
        assert result.first_incorrect_index is None
        assert result.has_incorrect is False

    def test_empty_list_empty_result(self) -> None:
        result = verify_solution([])
        assert result.n_transitions == 0
        assert result.steps == []
        assert result.unverified_ratio == 0.0
        assert result.first_incorrect_index is None
        assert result.has_incorrect is False


class TestAggregationInvariants:
    """집계 불변식 — 카운트 합 = n_transitions·결과 순서 보존·재구현 아님."""

    def test_counts_sum_equals_transitions(self) -> None:
        result = verify_solution(["2+3", "5", "6", "어쩌고", "x+1", "x+2"])
        assert result.n_correct + result.n_incorrect + result.n_unverifiable == result.n_transitions
        assert len(result.steps) == result.n_transitions

    def test_aggregates_verify_step_results_verbatim(self) -> None:
        # verify_solution이 verify_step 판정을 *그대로* 집계하는지(재구현 아님) 직접 대조.
        steps = ["2*(x+1)", "2*x+2", "2*x+3"]
        result = verify_solution(steps)
        expected0 = verify_step(steps[0], steps[1])
        expected1 = verify_step(steps[1], steps[2])
        assert result.steps[0] == expected0
        assert result.steps[1] == expected1

    def test_has_incorrect_matches_count(self) -> None:
        clean = verify_solution(["2+3", "5"])
        assert clean.has_incorrect == (clean.n_incorrect > 0)
        dirty = verify_solution(["2*x+1", "2*x+3"])
        assert dirty.has_incorrect == (dirty.n_incorrect > 0)


class TestDeterminismAndFields:
    """결정론·프론즌 모델 필드셋."""

    def test_deterministic_repeated_calls(self) -> None:
        first = verify_solution(["2+3", "5", "6"])
        second = verify_solution(["2+3", "5", "6"])
        assert first == second

    def test_result_field_set(self) -> None:
        result = verify_solution(["2+3", "5"])
        assert isinstance(result, SolutionVerificationResult)
        assert set(result.model_dump().keys()) == {
            "steps",
            "n_correct",
            "n_incorrect",
            "n_unverifiable",
            "n_transitions",
            "unverified_ratio",
            "first_incorrect_index",
            "has_incorrect",
        }
