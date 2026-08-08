"""L1 진단 프로브 후보 역인덱스 조회 — 순수 코어 단위테스트 (REC-02 ①④).

`_match_probe_rows`(DB 무관·순수)만 검증한다 — 실 PostgreSQL이 필요한 얇은 DB 시암
(`fetch_probe_candidates_by_mids`)은 `l1/misconception/resolve.py` 선례와 동형으로 분리됐고,
DB 통합테스트는 별도(스킵 가능)로 두는 게 이 코드베이스 관례다. 여기서는 mids 매칭·난이도
필터·미응답(exclude) 필터·정렬·limit 절단을 실 DB 없이 전부 검증한다.

핵심 봉인:
- ① 오개념 미태깅 문항은 후보에서 빠지고 `tagged_count`가 늘지 않는다.
- ① distractor_map 태깅은 있으나 difficulty_overall 없는 문항은 `tagged_count`엔 잡히되
  `tagged_with_difficulty_count`·최종 rows엔 안 잡힌다(사유 구분의 원재료).
- ① exclude_problem_ids(미응답 필터 결과)로 배제된 문항은 최종 rows에서 빠지되 두 카운트엔
  이미 반영돼 있다(카운트는 필터 *전* 단계 회계).
- discrimination: irt_a 양수면 그대로, None/비양수면 1.0.
- misconception_tags는 질의 mids로 국한되지 않고 그 문항의 distractor_map 전체 오개념을 담는다
  (§3.2 정보이득 근사가 competing_mids 배제를 판정하려면 전체 태그가 필요).
- 결정론 정렬(problem_id 오름차순)·limit 절단.
- 입력 불변(원본 리스트가 훼손되지 않음).
"""

from __future__ import annotations

from whymath_backend.l1.problem_bank.probe_candidates import (
    ProbeCandidateQuery,
    _match_probe_rows,
)

_MID_A = "mis.sign-error"
_MID_B = "mis.distribute-fail"
_MID_C = "mis.off-by-one"


def _row(
    problem_id: str,
    tags: list[str] | None,
    difficulty: float | None = 3.0,
    irt_a: float | None = None,
    irt_b: float | None = None,
) -> tuple[str, list[dict[str, object]] | None, float | None, float | None, float | None]:
    distractor_map = (
        None
        if tags is None
        else [{"choice_index": i, "misconception_id": t} for i, t in enumerate(tags)]
    )
    return (problem_id, distractor_map, difficulty, irt_a, irt_b)


class TestMatching:
    def test_untagged_problem_excluded_and_not_counted(self) -> None:
        rows = [_row("p1", [_MID_C]), _row("p2", None)]  # p1: 다른 오개념·p2: distractor_map 없음
        result = _match_probe_rows(rows, frozenset({_MID_A}))
        assert result == ProbeCandidateQuery(
            rows=(), tagged_count=0, tagged_with_difficulty_count=0
        )

    def test_tagged_problem_included(self) -> None:
        rows = [_row("p1", [_MID_A, _MID_B])]
        result = _match_probe_rows(rows, frozenset({_MID_A}))
        assert result.tagged_count == 1
        assert result.tagged_with_difficulty_count == 1
        assert len(result.rows) == 1
        row = result.rows[0]
        assert row.problem_id == "p1"
        # 전체 태그(질의 mid 하나뿐이어도 dist_map 전 원소를 담는다 — competing 판정용).
        assert row.misconception_tags == frozenset({_MID_A, _MID_B})


class TestDifficultyGate:
    def test_tagged_without_difficulty_counted_but_not_rowed(self) -> None:
        """② 사유 분리 원재료: 태깅은 됐으나 difficulty_overall 없음 → tagged엔 잡히고
        tagged_with_difficulty·최종 rows엔 안 잡힌다(untagged와 다른 값)."""
        rows = [_row("p1", [_MID_A], difficulty=None)]
        result = _match_probe_rows(rows, frozenset({_MID_A}))
        assert result.tagged_count == 1
        assert result.tagged_with_difficulty_count == 0
        assert result.rows == ()

    def test_mixed_difficulty_presence(self) -> None:
        rows = [
            _row("p1", [_MID_A], difficulty=None),
            _row("p2", [_MID_A], difficulty=2.5),
        ]
        result = _match_probe_rows(rows, frozenset({_MID_A}))
        assert result.tagged_count == 2
        assert result.tagged_with_difficulty_count == 1
        assert [r.problem_id for r in result.rows] == ["p2"]


class TestAdministeredExclusion:
    def test_excluded_problem_id_dropped_from_final_rows_but_counted(self) -> None:
        """④ 사유 분리 원재료: 미응답 필터로 빠진 문항도 tagged_with_difficulty엔 이미 잡혀
        있다 — '전부 응답함' 사유가 '난이도 부재'와 다른 값을 내는 근거."""
        rows = [_row("p1", [_MID_A]), _row("p2", [_MID_A])]
        result = _match_probe_rows(
            rows, frozenset({_MID_A}), exclude_problem_ids=frozenset({"p1", "p2"})
        )
        assert result.tagged_count == 2
        assert result.tagged_with_difficulty_count == 2
        assert result.rows == ()  # 전부 응답함 → 최종 후보 0

    def test_partial_exclusion(self) -> None:
        rows = [_row("p1", [_MID_A]), _row("p2", [_MID_A])]
        result = _match_probe_rows(rows, frozenset({_MID_A}), exclude_problem_ids=frozenset({"p1"}))
        assert [r.problem_id for r in result.rows] == ["p2"]


class TestDiscrimination:
    def test_positive_irt_a_used(self) -> None:
        rows = [_row("p1", [_MID_A], irt_a=1.7)]
        result = _match_probe_rows(rows, frozenset({_MID_A}))
        assert result.rows[0].discrimination == 1.7

    def test_missing_or_nonpositive_irt_a_defaults_to_one(self) -> None:
        rows = [_row("p1", [_MID_A], irt_a=None), _row("p2", [_MID_A], irt_a=-0.5)]
        result = _match_probe_rows(rows, frozenset({_MID_A}))
        assert result.rows[0].discrimination == 1.0
        assert result.rows[1].discrimination == 1.0


class TestDeterminismAndLimit:
    def test_sorted_by_problem_id_ascending(self) -> None:
        rows = [_row("p3", [_MID_A]), _row("p1", [_MID_A]), _row("p2", [_MID_A])]
        result = _match_probe_rows(rows, frozenset({_MID_A}))
        assert [r.problem_id for r in result.rows] == ["p1", "p2", "p3"]

    def test_limit_truncates_deterministically(self) -> None:
        rows = [_row(f"p{i}", [_MID_A]) for i in range(5)]
        result = _match_probe_rows(rows, frozenset({_MID_A}), limit=2)
        assert [r.problem_id for r in result.rows] == ["p0", "p1"]
        # 카운트는 limit 절단 *전* 전량 반영(정직 회계 — 잘려나간 후보도 계상돼야 함).
        assert result.tagged_count == 5
        assert result.tagged_with_difficulty_count == 5

    def test_input_rows_not_mutated(self) -> None:
        rows = [_row("p1", [_MID_A])]
        original = list(rows)
        _match_probe_rows(rows, frozenset({_MID_A}))
        assert rows == original


class TestMalformedDistractorEntries:
    def test_non_dict_or_missing_misconception_id_ignored(self) -> None:
        """distractor_map 원소가 dict가 아니거나 misconception_id가 없으면 태그에서 조용히
        제외(참조 무결성은 L4 검증자 소관 — 여긴 형태만 본다)."""
        distractor_map: list[dict[str, object]] = [
            {"choice_index": 0, "misconception_id": _MID_A},
            {"choice_index": 1},  # misconception_id 없음
            {"choice_index": 2, "misconception_id": ""},  # 빈 문자열
        ]
        rows = [("p1", distractor_map, 3.0, None, None)]
        result = _match_probe_rows(rows, frozenset({_MID_A}))
        assert result.rows[0].misconception_tags == frozenset({_MID_A})
