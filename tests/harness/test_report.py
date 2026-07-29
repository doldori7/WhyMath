"""report.py — 진행률 계산·게이트 리마인드·브리핑 렌더링 테스트 (날짜 고정)."""

from __future__ import annotations

from datetime import date

import report
from models import Backlog, Gate, Task, Track


def _backlog() -> Backlog:
    backlog = Backlog(stage_order=["S1", "S2"])
    backlog.tracks["main"] = Track(id="main", title="기본")
    backlog.gates["G-key"] = Gate(
        id="G-key",
        title="키 투입",
        requested="2026-07-05",
        remind_after_days=7,
    )
    backlog.tasks["S1-01-a"] = Task(
        id="S1-01-a",
        title="완료건",
        track="main",
        stage="S1",
        status="done",
        artifacts=["PR#1"],
        updated="2026-07-08",
    )
    backlog.tasks["S1-02-b"] = Task(
        id="S1-02-b",
        title="진행건",
        track="main",
        stage="S1",
        status="in_progress",
        session="branch-x",
        updated="2026-07-08",
    )
    backlog.tasks["S2-01-c"] = Task(
        id="S2-01-c",
        title="대기건",
        track="main",
        stage="S2",
        updated="2026-07-08",
    )
    return backlog


class TestProgress:
    def test_progress_per_stage(self):
        """스테이지별 진행률."""
        assert report.stage_progress(_backlog()) == [("S1", 1, 2), ("S2", 0, 1)]

    def test_current_stage_is_earliest_incomplete(self):
        """현재 스테이지는 미완 최전방."""
        assert report.current_stage(_backlog()) == "S1"

    def test_all_complete_yields_last_stage(self):
        """전부 완료면 마지막 스테이지."""
        backlog = _backlog()
        for task in backlog.tasks.values():
            task.status = "done"
            task.artifacts = ["PR#1"]
            task.session = None
        assert report.current_stage(backlog) == "S2"


class TestOverdueGates:
    def test_only_overdue_gates_are_reminded(self):
        """기한 초과 게이트만 리마인드."""
        backlog = _backlog()
        # 7일 기준: 15일 경과 → 리마인드, 3일 경과 → 리마인드 없음
        assert report.overdue_gates(backlog, date(2026, 7, 20)) == [("G-key", 15)]
        assert report.overdue_gates(backlog, date(2026, 7, 8)) == []

    def test_cleared_gates_are_excluded_from_reminders(self):
        """cleared 게이트는 리마인드 제외."""
        backlog = _backlog()
        backlog.gates["G-key"].status = "cleared"
        backlog.gates["G-key"].evidence = "PR#2"
        assert report.overdue_gates(backlog, date(2026, 7, 20)) == []


class TestBrief:
    def test_briefing_has_stage_task_and_reminder(self):
        """브리핑에 현재 스테이지와 내 태스크와 리마인드."""
        backlog = _backlog()
        text = report.render_brief(backlog, [], "branch-x", date(2026, 7, 20))
        assert "현재 스테이지: S1" in text
        assert "S1-02-b" in text  # 이 브랜치가 claim한 태스크
        assert "done S1-02-b" in text  # 완료 커맨드 안내
        assert "G-key" in text  # 15일 경과 리마인드
        assert "15일 경과" in text

    def test_integrity_warning_is_shown(self):
        """무결성 경고 표기."""
        text = report.render_brief(_backlog(), ["오류1"], "other", date(2026, 7, 8))
        assert "무결성 경고 1건" in text
