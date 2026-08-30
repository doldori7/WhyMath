"""검수 타이머 writer — 생성 함수·JSONL 즉시 flush·로더 실패 경로 (EOS-54 acceptance ①·④).

정본: `harness/review_timer.py`. 핵심 검증 — 세션 페어링(start가 발급한 id를 finish/abort가
재사용), 반려는 failure_code 없이 생성 불가(함수 레벨 집행), append는 이벤트마다 즉시 파일에
남는다(2026-08-22 규칙 ① — 마지막 일괄 저장 금지), 로더는 실패 줄을 예외 타입명과 함께
수집하되 필드 값은 새지 않는다. hermetic — tmp_path만 사용.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from whymath_backend.harness.review_timer import (
    abort_review,
    append_event_jsonl,
    finish_review,
    load_events_jsonl,
    start_review,
)
from whymath_backend.schema.enums import GenerationFailureCode


class TestConstructors:
    def test_start_issues_session_id_and_stamps_occurred(self) -> None:
        event = start_review(cu_slug="cu-a", reviewer_id="kiki")
        assert event.event_type == "started"
        assert isinstance(event.review_session_id, uuid.UUID)
        assert event.occurred_at is not None and event.occurred_at.tzinfo is not None  # UTC aware
        assert event.recorded_at is None  # 수신 시각은 매체가 찍는다(EOS-48 분리)

    def test_finish_pairs_with_start_session(self) -> None:
        started = start_review(cu_slug="cu-a", reviewer_id="kiki")
        finished = finish_review(
            review_session_id=started.review_session_id,
            cu_slug="cu-a",
            reviewer_id="kiki",
            verdict="approved",
            elapsed_ms=120_000,
        )
        assert finished.review_session_id == started.review_session_id
        assert finished.verdict == "approved"

    def test_finish_rejected_requires_failure_code(self) -> None:
        """§4 강제 분류의 함수 레벨 집행 — 실패 신호 실측(변별력 양쪽)."""
        session_id = uuid.uuid4()
        with pytest.raises(ValidationError, match="failure_code"):
            finish_review(
                review_session_id=session_id,
                cu_slug="cu-a",
                reviewer_id="kiki",
                verdict="rejected",
                elapsed_ms=90_000,
            )
        ok = finish_review(
            review_session_id=session_id,
            cu_slug="cu-a",
            reviewer_id="kiki",
            verdict="rejected",
            failure_code=GenerationFailureCode.F2,
            elapsed_ms=90_000,
        )
        assert ok.failure_code == "F2"

    def test_finish_accepts_unmeasured_elapsed_as_explicit_none(self) -> None:
        """계측 실패한 종결 — None *명시*로 유효(0 날조 금지·집계가 미계측 분리)."""
        event = finish_review(
            review_session_id=uuid.uuid4(),
            cu_slug="cu-a",
            reviewer_id="kiki",
            verdict="approved",
            elapsed_ms=None,
        )
        assert event.elapsed_ms is None

    def test_abort_carries_partial_elapsed_without_verdict(self) -> None:
        event = abort_review(
            review_session_id=uuid.uuid4(),
            cu_slug="cu-a",
            reviewer_id="kiki",
            elapsed_ms=30_000,
        )
        assert event.event_type == "aborted"
        assert event.verdict is None
        assert event.elapsed_ms == 30_000


class TestAppendJsonl:
    def test_each_append_lands_immediately(self, tmp_path: Path) -> None:
        """이벤트마다 즉시 flush — 두 번째 append *전에* 첫 이벤트가 이미 파일에 있다."""
        path = tmp_path / "timer" / "events.jsonl"
        started = start_review(cu_slug="cu-a", reviewer_id="kiki")
        append_event_jsonl(path, started)
        assert len(path.read_text(encoding="utf-8").splitlines()) == 1  # 일괄 저장이면 0
        append_event_jsonl(
            path,
            finish_review(
                review_session_id=started.review_session_id,
                cu_slug="cu-a",
                reviewer_id="kiki",
                verdict="approved",
                elapsed_ms=60_000,
            ),
        )
        assert len(path.read_text(encoding="utf-8").splitlines()) == 2

    def test_append_stamps_recorded_at_and_returns_copy(self, tmp_path: Path) -> None:
        """recorded_at(수신)은 append가 스탬프 — 반환본에 반영·원본 불변."""
        path = tmp_path / "events.jsonl"
        original = start_review(cu_slug="cu-a", reviewer_id="kiki")
        stamped = append_event_jsonl(path, original)
        assert original.recorded_at is None  # 원본 불변(model_copy)
        assert stamped.recorded_at is not None
        on_disk = json.loads(path.read_text(encoding="utf-8"))
        assert on_disk["recorded_at"] is not None

    def test_append_respects_preset_recorded_at(self, tmp_path: Path) -> None:
        """이미 수신 시각이 있으면(재적재 등) 덮어쓰지 않는다 — 시각 날조 금지."""
        path = tmp_path / "events.jsonl"
        preset = datetime(2026, 8, 31, 2, 0, tzinfo=UTC)
        event = start_review(cu_slug="cu-a", reviewer_id="kiki").model_copy(
            update={"recorded_at": preset}
        )
        stamped = append_event_jsonl(path, event)
        assert stamped.recorded_at == preset


class TestLoadJsonl:
    def test_round_trip(self, tmp_path: Path) -> None:
        path = tmp_path / "events.jsonl"
        started = append_event_jsonl(path, start_review(cu_slug="cu-a", reviewer_id="kiki"))
        append_event_jsonl(
            path,
            finish_review(
                review_session_id=started.review_session_id,
                cu_slug="cu-a",
                reviewer_id="kiki",
                verdict="rejected",
                failure_code=GenerationFailureCode.F8,
                failure_note="L2 힌트에 정답 수치 노출",
                elapsed_ms=200_000,
            ),
        )
        events, errors = load_events_jsonl(path)
        assert errors == []
        assert [e.event_type for e in events] == ["started", "finished"]
        assert events[1].failure_code == "F8"

    def test_parse_failures_collected_with_type_names_without_values(self, tmp_path: Path) -> None:
        """실패 줄은 삼키지 않고 타입명+줄 번호로 수집 — 필드 값·원문은 새지 않는다."""
        path = tmp_path / "events.jsonl"
        good = start_review(cu_slug="cu-a", reviewer_id="kiki")
        secret_note = "SECRET-NOTE-SHOULD-NOT-LEAK"
        path.write_text(
            "not-json\n"
            + json.dumps({"cu_slug": "cu-bad", "failure_note": secret_note})
            + "\n"
            + good.model_dump_json()
            + "\n",
            encoding="utf-8",
        )
        events, errors = load_events_jsonl(path)
        assert len(events) == 1  # 유효분은 살린다(전멸 아님)
        assert len(errors) == 2
        assert errors[0].startswith("line 1: JSONDecodeError")
        assert errors[1].startswith("line 2: ValidationError")
        assert all(secret_note not in reason for reason in errors)  # 값 비유출

    def test_missing_file_propagates_not_empty(self, tmp_path: Path) -> None:
        """파일 부재는 이벤트 0건이 아니라 FileNotFoundError — 미측정≠0의 입력 축."""
        with pytest.raises(FileNotFoundError):
            load_events_jsonl(tmp_path / "absent.jsonl")

    def test_blank_lines_skipped(self, tmp_path: Path) -> None:
        path = tmp_path / "events.jsonl"
        event = start_review(cu_slug="cu-a", reviewer_id="kiki")
        path.write_text("\n" + event.model_dump_json() + "\n\n", encoding="utf-8")
        events, errors = load_events_jsonl(path)
        assert len(events) == 1 and errors == []
