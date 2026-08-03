"""오개념 표적 프로브 역인덱스 조회 *단위테스트* — REC-02 (hermetic·PG 불요).

순수 코어(`_extract_tags`·`_classify_rows`)만 DB 없이 못 박는다. 실 라운드트립
(`lookup_probe_candidates_by_mids`·2쿼리)은 통합테스트
(`test_misconception_probe_lookup_integration.py`)로 미룬다.

  ① `_extract_tags` — 정상·빈/None·misconception_id 결측·비문자열 방어
  ② `_classify_rows` — 3사유 배타(missing_difficulty/fully_administered/kept)·matched_target_mids
     계상(사유 무관하게 코퍼스 태깅 여부만 반영)
"""

from __future__ import annotations

import uuid

from whymath_backend.l1.misconception.probe_lookup import (
    ProbeCandidateRow,
    _classify_rows,
    _extract_tags,
)


# ──────────────────────────────────────────────────────────────────────────
# ① _extract_tags — dict 파싱(raw ORM JSONB)
# ──────────────────────────────────────────────────────────────────────────
class TestExtractTags:
    def test_normal_entries(self) -> None:
        raw = [
            {"choice_index": 0, "misconception_id": "m-a"},
            {"choice_index": 1, "misconception_id": "m-b", "op_code": "x"},
        ]
        assert _extract_tags(raw) == frozenset({"m-a", "m-b"})

    def test_none_is_empty(self) -> None:
        assert _extract_tags(None) == frozenset()

    def test_empty_list_is_empty(self) -> None:
        assert _extract_tags([]) == frozenset()

    def test_missing_misconception_id_key_skipped(self) -> None:
        raw = [{"choice_index": 0}, {"choice_index": 1, "misconception_id": "m-a"}]
        assert _extract_tags(raw) == frozenset({"m-a"})

    def test_non_string_misconception_id_skipped(self) -> None:
        raw = [{"choice_index": 0, "misconception_id": 123}]
        assert _extract_tags(raw) == frozenset()

    def test_empty_string_misconception_id_skipped(self) -> None:
        raw = [{"choice_index": 0, "misconception_id": ""}]
        assert _extract_tags(raw) == frozenset()

    def test_dedupes_repeated_tags(self) -> None:
        raw = [
            {"choice_index": 0, "misconception_id": "m-a"},
            {"choice_index": 1, "misconception_id": "m-a"},
        ]
        assert _extract_tags(raw) == frozenset({"m-a"})


def _row(
    tags: frozenset[str],
    *,
    difficulty: float | None = 3.0,
    pid: uuid.UUID | None = None,
) -> tuple[uuid.UUID, frozenset[str], float | None, float | None, float | None]:
    return (pid or uuid.uuid4(), tags, difficulty, None, None)


# ──────────────────────────────────────────────────────────────────────────
# ② _classify_rows — 3사유 배타 + matched_target_mids
# ──────────────────────────────────────────────────────────────────────────
class TestClassifyRows:
    def test_kept_when_difficulty_present_and_not_attempted(self) -> None:
        pid = uuid.uuid4()
        rows = [_row(frozenset({"M-A"}), difficulty=2.5, pid=pid)]
        kept, missing, administered, matched = _classify_rows(rows, frozenset({"M-A"}), frozenset())
        assert missing == 0
        assert administered == 0
        assert matched == frozenset({"M-A"})
        assert len(kept) == 1
        assert kept[0] == ProbeCandidateRow(
            problem_id=pid,
            difficulty_overall=2.5,
            irt_difficulty_b=None,
            irt_a=None,
            misconception_tags=frozenset({"M-A"}),
        )

    def test_missing_difficulty_excluded(self) -> None:
        rows = [_row(frozenset({"M-A"}), difficulty=None)]
        kept, missing, administered, matched = _classify_rows(rows, frozenset({"M-A"}), frozenset())
        assert kept == []
        assert missing == 1
        assert administered == 0
        assert matched == frozenset({"M-A"})  # 태깅은 됐음 — 미태깅 아님

    def test_fully_administered_excluded(self) -> None:
        pid = uuid.uuid4()
        rows = [_row(frozenset({"M-A"}), difficulty=2.0, pid=pid)]
        kept, missing, administered, matched = _classify_rows(
            rows, frozenset({"M-A"}), frozenset({pid})
        )
        assert kept == []
        assert missing == 0
        assert administered == 1
        assert matched == frozenset({"M-A"})

    def test_reasons_are_mutually_exclusive_priority(self) -> None:
        """난이도 부재가 미응답보다 먼저 판정된다(응답 여부와 무관하게 missing_difficulty)."""
        pid = uuid.uuid4()
        rows = [_row(frozenset({"M-A"}), difficulty=None, pid=pid)]
        kept, missing, administered, _matched = _classify_rows(
            rows, frozenset({"M-A"}), frozenset({pid})
        )
        assert kept == []
        assert missing == 1
        assert administered == 0

    def test_matched_target_mids_only_intersection(self) -> None:
        rows = [_row(frozenset({"M-A", "M-C"}), difficulty=1.0)]
        _kept, _missing, _administered, matched = _classify_rows(
            rows, frozenset({"M-A", "M-B"}), frozenset()
        )
        # M-C는 target이 아니라 matched에 안 실림, M-B는 이 행에 없으니 안 실림.
        assert matched == frozenset({"M-A"})

    def test_four_scenario_distinct_counts(self) -> None:
        """4사유(가설없음은 상위 계층 몫 제외) 중 3사유가 서로 다른 값을 낸다."""
        kept_pid = uuid.uuid4()
        admin_pid = uuid.uuid4()
        rows = [
            _row(frozenset({"M-A"}), difficulty=1.0, pid=kept_pid),
            _row(frozenset({"M-B"}), difficulty=None),
            _row(frozenset({"M-C"}), difficulty=1.5, pid=admin_pid),
        ]
        target = frozenset({"M-A", "M-B", "M-C"})
        kept, missing, administered, matched = _classify_rows(rows, target, frozenset({admin_pid}))
        assert len(kept) == 1
        assert missing == 1
        assert administered == 1
        assert matched == target
