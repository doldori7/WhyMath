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
    def test_스테이지별_진행률(self):
        assert report.stage_progress(_backlog()) == [("S1", 1, 2), ("S2", 0, 1)]

    def test_현재_스테이지는_미완_최전방(self):
        assert report.current_stage(_backlog()) == "S1"

    def test_전부_완료면_마지막_스테이지(self):
        backlog = _backlog()
        for task in backlog.tasks.values():
            task.status = "done"
            task.artifacts = ["PR#1"]
            task.session = None
        assert report.current_stage(backlog) == "S2"


class TestOverdueGates:
    def test_기한_초과_게이트만_리마인드(self):
        backlog = _backlog()
        # 7일 기준: 15일 경과 → 리마인드, 3일 경과 → 리마인드 없음
        assert report.overdue_gates(backlog, date(2026, 7, 20)) == [("G-key", 15)]
        assert report.overdue_gates(backlog, date(2026, 7, 8)) == []

    def test_cleared_게이트는_리마인드_제외(self):
        backlog = _backlog()
        backlog.gates["G-key"].status = "cleared"
        backlog.gates["G-key"].evidence = "PR#2"
        assert report.overdue_gates(backlog, date(2026, 7, 20)) == []


class TestBrief:
    def test_브리핑에_현재_스테이지와_내_태스크와_리마인드(self):
        backlog = _backlog()
        text = report.render_brief(backlog, [], "branch-x", date(2026, 7, 20))
        assert "현재 스테이지: S1" in text
        assert "S1-02-b" in text  # 이 브랜치가 claim한 태스크
        assert "done S1-02-b" in text  # 완료 커맨드 안내
        assert "G-key" in text  # 15일 경과 리마인드
        assert "15일 경과" in text

    def test_무결성_경고_표기(self):
        text = report.render_brief(_backlog(), ["오류1"], "other", date(2026, 7, 8))
        assert "무결성 경고 1건" in text

    def test_장기_미머지_브랜치_경고_표기(self):
        """HARN-13 — stale_branches가 있으면 브랜치·나이·ahead가 브리핑에 보여야 한다."""
        text = report.render_brief(
            _backlog(),
            [],
            "branch-x",
            date(2026, 7, 20),
            stale_branches=[("claude/old-orphan", 9.3, 42)],
        )
        assert "claude/old-orphan" in text
        assert "9일 전" in text
        assert "42커밋" in text

    def test_장기_미머지_브랜치_없으면_경고_생략(self):
        text = report.render_brief(_backlog(), [], "branch-x", date(2026, 7, 20), stale_branches=[])
        assert "장기 미머지" not in text

    def test_장기_미머지_브랜치_조회_실패는_판정_보류로_표기(self):
        """조회 실패가 '방치 브랜치 없음'과 같은 문구로 보이면 침묵 실패다."""
        text = report.render_brief(
            _backlog(),
            [],
            "branch-x",
            date(2026, 7, 20),
            stale_branches=[],
            stale_branch_status="offline",
        )
        assert "장기 미머지 브랜치 조회 불가" in text
        assert "판정 보류" in text
