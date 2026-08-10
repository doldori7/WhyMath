"""L4 오답 선택 인덱스 → 오개념 역방향 조회 단위테스트 (ASM-06).

`resolve_misconception_from_choice`(순수·DB 무관)만 검증한다 — `l1.problem_bank.
probe_candidates::_match_probe_rows`의 순수 코어/DB 시암 분리 관례를 답습(테스트 자체는
`test_probe_candidates.py`·`test_distractor_validate.py` 스타일). API 결선(`POST
/v1/me/attempts`)은 `tests/backend/api/test_me.py::TestSubmitAttempt`가 별도로 검증한다.

핵심 봉인:
- ① `selected_choice_index`가 `None`이면 `distractor_map`을 보지 않고 즉시 `None`(reactive).
- ② `distractor_map`이 `None`/빈 리스트면 `None`(매핑 없음).
- ③ 일치하는 `choice_index` 엔트리의 `misconception_id`를 반환.
- ④ 일치하는 엔트리가 없으면(오답 인덱스 불일치·정답 인덱스는 애초에 매핑에 없음) `None`.
- ⑤ 형태 불량 원소(매핑 아님·키 누락·빈 misconception_id)는 조용히 건너뛴다(크래시 금지).
"""

from __future__ import annotations

from whymath_backend.l4.misconception.distractor_link import (
    resolve_misconception_from_choice,
)

_MID_A = "mis.sign-error"
_MID_B = "mis.distribute-fail"


class TestNoSelectedIndex:
    def test_none_index_returns_none_without_inspecting_map(self) -> None:
        """① selected_choice_index가 None이면 distractor_map이 있어도 즉시 None."""
        distractor_map = [{"choice_index": 0, "misconception_id": _MID_A}]
        assert resolve_misconception_from_choice(distractor_map, None) is None

    def test_none_index_with_none_map(self) -> None:
        assert resolve_misconception_from_choice(None, None) is None


class TestNoDistractorMap:
    def test_none_map_returns_none(self) -> None:
        """② distractor_map 자체가 없음(정답 인덱스가 애초에 매핑에 없는 경우와 동형 결과)."""
        assert resolve_misconception_from_choice(None, 1) is None

    def test_empty_map_returns_none(self) -> None:
        assert resolve_misconception_from_choice([], 1) is None


class TestMatching:
    def test_matching_index_returns_misconception_id(self) -> None:
        """③ 일치하는 choice_index → 그 misconception_id."""
        distractor_map = [
            {"choice_index": 0, "misconception_id": _MID_A},
            {"choice_index": 2, "misconception_id": _MID_B},
        ]
        assert resolve_misconception_from_choice(distractor_map, 2) == _MID_B

    def test_matching_index_among_multiple_entries(self) -> None:
        distractor_map = [
            {"choice_index": 0, "misconception_id": _MID_A},
            {"choice_index": 1, "misconception_id": _MID_B},
            {"choice_index": 3, "misconception_id": "mis.off-by-one"},
        ]
        assert resolve_misconception_from_choice(distractor_map, 0) == _MID_A
        assert resolve_misconception_from_choice(distractor_map, 1) == _MID_B
        assert resolve_misconception_from_choice(distractor_map, 3) == "mis.off-by-one"

    def test_entry_may_carry_optional_op_code(self) -> None:
        """DistractorEntry.model_dump() 동형 입력(op_code 포함)도 그대로 받는다."""
        distractor_map = [
            {"choice_index": 1, "misconception_id": _MID_A, "op_code": "some-op-code"}
        ]
        assert resolve_misconception_from_choice(distractor_map, 1) == _MID_A


class TestNonMatching:
    def test_wrong_index_returns_none(self) -> None:
        """④ 불일치 인덱스(다른 오답을 골랐거나 매핑되지 않은 인덱스) → None."""
        distractor_map = [{"choice_index": 0, "misconception_id": _MID_A}]
        assert resolve_misconception_from_choice(distractor_map, 1) is None

    def test_correct_answer_index_absent_from_map_returns_none(self) -> None:
        """④ 정답 선지 인덱스는 distractor_map에 애초에 없다(정답 제외 설계) → None.

        `Problem.choices`가 4개(0~3)이고 정답이 인덱스 2, distractor_map은 오답 3개(0·1·3)만
        담는다고 가정 — 학생이 정답(2)을 골랐을 때 조회 결과는 매핑 부재와 동일하게 None.
        """
        distractor_map = [
            {"choice_index": 0, "misconception_id": _MID_A},
            {"choice_index": 1, "misconception_id": _MID_B},
            {"choice_index": 3, "misconception_id": "mis.off-by-one"},
        ]
        assert resolve_misconception_from_choice(distractor_map, 2) is None


class TestMalformedEntries:
    def test_non_mapping_entry_skipped(self) -> None:
        """⑤ dict가 아닌 원소(예: 문자열)는 형태 불량 — 조용히 건너뛰고 계속 탐색."""
        distractor_map = ["not-a-mapping", {"choice_index": 1, "misconception_id": _MID_A}]
        assert resolve_misconception_from_choice(distractor_map, 1) == _MID_A

    def test_entry_missing_choice_index_skipped(self) -> None:
        distractor_map = [{"misconception_id": _MID_A}]  # choice_index 없음
        assert resolve_misconception_from_choice(distractor_map, 0) is None

    def test_entry_with_empty_misconception_id_returns_none(self) -> None:
        """choice_index는 일치하나 misconception_id가 빈 문자열이면 None(참조 무결성은 별도 소관)."""
        distractor_map = [{"choice_index": 0, "misconception_id": ""}]
        assert resolve_misconception_from_choice(distractor_map, 0) is None

    def test_entry_missing_misconception_id_returns_none(self) -> None:
        distractor_map = [{"choice_index": 0}]
        assert resolve_misconception_from_choice(distractor_map, 0) is None

    def test_all_malformed_entries_returns_none(self) -> None:
        distractor_map = ["bad", 42, {"choice_index": 9}]
        assert resolve_misconception_from_choice(distractor_map, 0) is None
