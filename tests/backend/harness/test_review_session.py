"""검수 세션 CLI — 타이머 생산자 배선·반려코드 강제·양방향 변별력 (EOS-78).

정본: `harness/review_session.py`. 이 스위트가 동결하는 것:

  1. **생산자가 실제로 이벤트를 낸다** — EOS-78의 정의 그 자체(착수 시점 `src/` 생산 호출자
     0건이었다). started→finished 페어링·즉시 flush를 파일로 확인한다.
  2. **반려는 F1~F8 없이 통과 못 한다** — 설계서 §4의 CLI 입력 경로 집행.
  3. **acceptance ④ 양방향 변별력** — 타이머 없이 판정만 있으면 `hit_cu_metrics`가 *측정
     실패*(exit 1)를 내고, 이 CLI를 태우면 HIT가 산출(exit 0)된다. 성공/실패가 같은 값을
     내면 검증이 아니라 위장이므로 **두 방향을 모두** 실측한다.
  4. **중단도 사실로 남는다** — 보류·종료·EOF가 조용한 종료가 아니라 `aborted` 이벤트다.

hermetic — tmp_path와 주입된 스트림·시계만 쓴다(대화형이지만 실제 stdin은 건드리지 않는다).
"""

from __future__ import annotations

import io
import json
from datetime import UTC, datetime
from pathlib import Path

from whymath_backend.harness.review_session import (
    ReviewItem,
    load_review_items,
    run_review_session,
)
from whymath_backend.ops import hit_cu_metrics


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    return path


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _run(
    tmp_path: Path,
    items: list[ReviewItem],
    keystrokes: str,
    *,
    resume: bool = False,
    step_ns: int = 60_000_000_000,
):
    ticks = [0]

    def monotonic_ns() -> int:
        value = ticks[0]
        ticks[0] += step_ns
        return value

    out = io.StringIO()
    outcome = run_review_session(
        items,
        events_path=tmp_path / "events.jsonl",
        verdicts_path=tmp_path / "verdicts.jsonl",
        reviewer_id="kiki",
        stream_in=io.StringIO(keystrokes),
        stream_out=out,
        monotonic_ns=monotonic_ns,
        now_utc=lambda: datetime(2026, 9, 1, 12, 0, tzinfo=UTC),
        resume=resume,
    )
    return outcome, out.getvalue()


class TestLoadReviewItems:
    """입력 로더 — 두 기존 형식 수용·실패 원인 보존(값 미노출)."""

    def test_accepts_queue_and_corpus_rows_by_shared_slug_key(self, tmp_path: Path) -> None:
        path = _write_jsonl(
            tmp_path / "queue.jsonl",
            [
                {"slug": "cu-a", "status": "needs_review", "reasons": ["동등성 0.71"]},
                {"slug": "cu-b"},  # 코퍼스 레코드 형태(근거 없음)
            ],
        )
        items, errors = load_review_items(path)
        assert [item.slug for item in items] == ["cu-a", "cu-b"]
        assert items[0].status == "needs_review"
        assert items[0].reasons == ("동등성 0.71",)
        assert items[1].status is None
        assert errors == []

    def test_failures_carry_exception_type_and_line_but_not_values(self, tmp_path: Path) -> None:
        path = tmp_path / "queue.jsonl"
        path.write_text(
            '{"slug": "cu-a"}\n'
            "{not json — 시크릿토큰123}\n"
            '{"status": "needs_review"}\n'
            '{"slug": "cu-a"}\n',
            encoding="utf-8",
        )
        items, errors = load_review_items(path)
        assert [item.slug for item in items] == ["cu-a"]
        assert any("JSONDecodeError" in reason for reason in errors)
        assert any("MissingIdentityKey" in reason for reason in errors)
        assert any("DuplicateSlug" in reason for reason in errors)
        # 실패 사유에 원문·값이 새지 않는다(시크릿/필드값 제외 규칙).
        assert not any("시크릿토큰123" in reason for reason in errors)


class TestProducerWiring:
    """EOS-78의 정의 — 이 CLI가 실제로 타이머 이벤트를 낸다."""

    def test_approve_emits_paired_started_and_finished(self, tmp_path: Path) -> None:
        outcome, _ = _run(tmp_path, [ReviewItem(slug="cu-a")], "a\n")
        events = _read_jsonl(tmp_path / "events.jsonl")

        assert outcome.approved == 1
        assert [e["event_type"] for e in events] == ["started", "finished"]
        # 한 앉음(sitting) 페어링 — start가 발급한 세션 id를 finish가 재사용한다.
        assert events[0]["review_session_id"] == events[1]["review_session_id"]
        assert events[0]["cu_slug"] == events[1]["cu_slug"] == "cu-a"
        # started에는 판정·경과가 없다(계약상 금지).
        assert events[0]["verdict"] is None
        assert events[0]["elapsed_ms"] is None
        # 경과는 재어서 넣는다 — 주입 시계 기준 정확히 60초.
        assert events[1]["verdict"] == "approved"
        assert events[1]["elapsed_ms"] == 60_000

    def test_started_is_written_before_the_verdict_is_known(self, tmp_path: Path) -> None:
        """검수 도중 죽어도 '보기 시작했다'가 남는다 — EOF로 중도 사망을 흉내낸다."""
        _run(tmp_path, [ReviewItem(slug="cu-a")], "")  # 입력 없음 = 즉시 EOF
        events = _read_jsonl(tmp_path / "events.jsonl")
        assert [e["event_type"] for e in events] == ["started", "aborted"]

    def test_verdict_rows_match_the_format_hit_cu_metrics_already_consumes(
        self, tmp_path: Path
    ) -> None:
        """신규 형식 0 — 판독기의 파서가 우리 행을 판정으로 인식하는지 직접 대조한다."""
        _run(tmp_path, [ReviewItem(slug="cu-a")], "a\n")
        rows = _read_jsonl(tmp_path / "verdicts.jsonl")
        verdicts, non_verdict, errors = hit_cu_metrics._parse_verdict_rows(rows)
        assert verdicts == [("cu-a", "approved")]
        assert non_verdict == 0
        assert errors == []


class TestVerdictPromptIsForgiving:
    """오타가 중단으로 둔갑하지 않는다 — 중단 건수의 정직성."""

    def test_invalid_keys_are_reprompted_and_do_not_abort(self, tmp_path: Path) -> None:
        outcome, rendered = _run(tmp_path, [ReviewItem(slug="cu-a")], "x\n\na\n")
        events = _read_jsonl(tmp_path / "events.jsonl")

        assert (outcome.approved, outcome.aborted) == (1, 0)
        assert [e["event_type"] for e in events] == ["started", "finished"]
        # 무효 입력 2회(오타 'x' + 빈 Enter)를 실제로 되물었다.
        assert rendered.count("a/e/r/s/q 중 하나여야 합니다") == 2

    def test_eof_at_the_verdict_prompt_still_aborts_and_stops(self, tmp_path: Path) -> None:
        """되묻기가 EOF까지 삼키면 무한 루프가 된다 — 그 반대임을 동결한다."""
        outcome, _ = _run(tmp_path, [ReviewItem(slug="cu-a"), ReviewItem(slug="cu-b")], "")
        assert (outcome.aborted, outcome.stopped_early) == (1, True)
        assert {e["cu_slug"] for e in _read_jsonl(tmp_path / "events.jsonl")} == {"cu-a"}


class TestRejectionRequiresFailureCode:
    """설계서 §4 — 자유 텍스트 단독 금지의 입력 경로 집행."""

    def test_invalid_code_is_refused_until_a_valid_one_is_given(self, tmp_path: Path) -> None:
        outcome, rendered = _run(tmp_path, [ReviewItem(slug="cu-a")], "r\nF9\n아무말\nF3\n메모\n")
        events = _read_jsonl(tmp_path / "events.jsonl")

        assert outcome.rejected == 1
        assert events[1]["verdict"] == "rejected"
        assert events[1]["failure_code"] == "F3"
        assert events[1]["failure_note"] == "메모"
        # 무효 입력 2회를 실제로 거부했다(되묻기가 일어났다는 증거).
        assert rendered.count("F1~F8 중 하나여야 합니다") == 2

    def test_eof_during_failure_code_becomes_abort_not_a_forced_verdict(
        self, tmp_path: Path
    ) -> None:
        """반려를 완성하지 못하면 억지 판정 대신 중단으로 남긴다."""
        outcome, _ = _run(tmp_path, [ReviewItem(slug="cu-a")], "r\n")
        events = _read_jsonl(tmp_path / "events.jsonl")

        assert outcome.rejected == 0
        assert outcome.aborted == 1
        assert [e["event_type"] for e in events] == ["started", "aborted"]
        # 판정이 없으므로 판정 파일에도 쓰지 않는다(분모 오염 방지).
        assert not (tmp_path / "verdicts.jsonl").exists()


class TestThreeWayVerdict:
    """EOS-62 3종 판정 — 손질 승인이 무손질 승인으로 뭉개지지 않는다."""

    def test_edit_approval_is_recorded_as_its_own_verdict(self, tmp_path: Path) -> None:
        outcome, _ = _run(tmp_path, [ReviewItem(slug="cu-a")], "e\nF5\n난이도 조정\n")
        events = _read_jsonl(tmp_path / "events.jsonl")

        assert (outcome.approved, outcome.approved_with_edit) == (0, 1)
        assert events[1]["verdict"] == "approved_with_edit"
        assert events[1]["failure_code"] == "F5"

    def test_edit_approval_failure_code_is_optional(self, tmp_path: Path) -> None:
        """반려는 코드 필수·수정승인은 선택 — 계약이 갈라 둔 대로."""
        outcome, _ = _run(tmp_path, [ReviewItem(slug="cu-a")], "e\n\n\n")
        events = _read_jsonl(tmp_path / "events.jsonl")

        assert outcome.approved_with_edit == 1
        assert events[1]["verdict"] == "approved_with_edit"
        assert events[1]["failure_code"] is None

    def test_edit_approval_still_counts_as_a_verdict_for_coverage(self, tmp_path: Path) -> None:
        """**이 스위트의 핵심 회귀 가드.**

        `verdict`를 `review_status`에 그대로 복사하면 `approved_with_edit` 행이
        `hit_cu_metrics`의 판정 집합(approved/rejected)에 안 들어가 **적재율 분모에서
        조용히 빠진다**(review_status_for_verdict docstring이 예고한 바로 그 버그).
        변환 다리를 거치는지 판독기의 파서로 직접 대조한다.
        """
        _run(tmp_path, [ReviewItem(slug="cu-a")], "e\nF5\n\n")
        rows = _read_jsonl(tmp_path / "verdicts.jsonl")

        assert rows[0]["review_status"] == "approved"  # 노출 축 — 통과다
        assert rows[0]["verdict"] == "approved_with_edit"  # 계측 축 — 손질 사실 보존
        verdicts, non_verdict, errors = hit_cu_metrics._parse_verdict_rows(rows)
        assert verdicts == [("cu-a", "approved")]
        assert non_verdict == 0  # 분모에서 빠지지 않는다
        assert errors == []


class TestAbortAndResume:
    def test_skip_records_partial_elapsed_and_continues(self, tmp_path: Path) -> None:
        outcome, _ = _run(tmp_path, [ReviewItem(slug="cu-a"), ReviewItem(slug="cu-b")], "s\na\n")
        events = _read_jsonl(tmp_path / "events.jsonl")

        assert (outcome.aborted, outcome.approved) == (1, 1)
        assert [e["event_type"] for e in events] == [
            "started",
            "aborted",
            "started",
            "finished",
        ]
        # 보류에도 그때까지 쓴 시간이 남는다(그 시간도 그 CU에 쓴 인간 시간이다).
        assert events[1]["elapsed_ms"] == 60_000

    def test_quit_stops_the_session_and_leaves_the_rest_untouched(self, tmp_path: Path) -> None:
        outcome, _ = _run(tmp_path, [ReviewItem(slug="cu-a"), ReviewItem(slug="cu-b")], "q\n")
        events = _read_jsonl(tmp_path / "events.jsonl")

        assert outcome.stopped_early is True
        assert {e["cu_slug"] for e in events} == {"cu-a"}

    def test_resume_skips_already_finished_cus(self, tmp_path: Path) -> None:
        _run(tmp_path, [ReviewItem(slug="cu-a")], "a\n")
        outcome, rendered = _run(
            tmp_path,
            [ReviewItem(slug="cu-a"), ReviewItem(slug="cu-b")],
            "a\n",
            resume=True,
        )
        assert outcome.skipped_completed == 1
        assert outcome.approved == 1
        assert "이중 계측 방지" in rendered
        # cu-a는 한 번만 종결됐다 — 재개가 HIT를 부풀리지 않는다.
        finished = [
            e for e in _read_jsonl(tmp_path / "events.jsonl") if e["event_type"] == "finished"
        ]
        assert [e["cu_slug"] for e in finished] == ["cu-a", "cu-b"]

    def test_without_resume_the_same_cu_is_measured_again(self, tmp_path: Path) -> None:
        """--resume의 변별력 — 끄면 실제로 다시 잰다(옵션이 무의미하지 않다)."""
        _run(tmp_path, [ReviewItem(slug="cu-a")], "a\n")
        outcome, _ = _run(tmp_path, [ReviewItem(slug="cu-a")], "a\n", resume=False)
        assert outcome.skipped_completed == 0


class TestMeasurabilityDiscrimination:
    """acceptance ④ — 양방향 변별력. 판독기를 실제로 태워 exit code로 판정한다."""

    def test_verdicts_without_timer_events_are_a_measurement_failure(self, tmp_path: Path) -> None:
        """타이머 없이 판정만 제출한 상태(= EOS-78 착수 시점의 세계)를 재현한다."""
        events_path = _write_jsonl(tmp_path / "empty_events.jsonl", [])
        verdicts_path = _write_jsonl(
            tmp_path / "verdicts_only.jsonl",
            [{"slug": "cu-a", "review_status": "approved"}],
        )
        code = hit_cu_metrics.main(["--events", str(events_path), "--verdicts", str(verdicts_path)])
        # '0분 통과'가 아니라 측정 실패여야 한다.
        assert code == 1

    def test_running_the_session_makes_hit_measurable(self, tmp_path: Path) -> None:
        """같은 판독기·같은 명령이 이 CLI를 태운 뒤에는 exit 0을 낸다."""
        _run(tmp_path, [ReviewItem(slug="cu-a"), ReviewItem(slug="cu-b")], "a\nr\nF2\n\n")
        code = hit_cu_metrics.main(
            [
                "--events",
                str(tmp_path / "events.jsonl"),
                "--verdicts",
                str(tmp_path / "verdicts.jsonl"),
            ]
        )
        assert code == 0
