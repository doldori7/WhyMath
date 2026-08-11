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
    def test_progress_by_stage(self):
        """test_스테이지별_진행률"""
        assert report.stage_progress(_backlog()) == [("S1", 1, 2), ("S2", 0, 1)]

    def test_current_stage_is_frontmost_incomplete(self):
        """test_현재_스테이지는_미완_최전방"""
        assert report.current_stage(_backlog()) == "S1"

    def test_all_done_returns_last_stage(self):
        """test_전부_완료면_마지막_스테이지"""
        backlog = _backlog()
        for task in backlog.tasks.values():
            task.status = "done"
            task.artifacts = ["PR#1"]
            task.session = None
        assert report.current_stage(backlog) == "S2"


class TestOverdueGates:
    def test_only_overdue_gates_are_reminded(self):
        """test_기한_초과_게이트만_리마인드"""
        backlog = _backlog()
        # 7일 기준: 15일 경과 → 리마인드, 3일 경과 → 리마인드 없음
        assert report.overdue_gates(backlog, date(2026, 7, 20)) == [("G-key", 15)]
        assert report.overdue_gates(backlog, date(2026, 7, 8)) == []

    def test_cleared_gate_excluded_from_reminder(self):
        """test_cleared_게이트는_리마인드_제외"""
        backlog = _backlog()
        backlog.gates["G-key"].status = "cleared"
        backlog.gates["G-key"].evidence = "PR#2"
        assert report.overdue_gates(backlog, date(2026, 7, 20)) == []


class TestBrief:
    def test_brief_shows_current_stage_my_tasks_and_reminders(self):
        """test_브리핑에_현재_스테이지와_내_태스크와_리마인드"""
        backlog = _backlog()
        text = report.render_brief(backlog, [], "branch-x", date(2026, 7, 20))
        assert "현재 스테이지: S1" in text
        assert "S1-02-b" in text  # 이 브랜치가 claim한 태스크
        assert "done S1-02-b" in text  # 완료 커맨드 안내
        assert "G-key" in text  # 15일 경과 리마인드
        assert "15일 경과" in text

    def test_integrity_warning_shown(self):
        """test_무결성_경고_표기"""
        text = report.render_brief(_backlog(), ["오류1"], "other", date(2026, 7, 8))
        assert "무결성 경고 1건" in text

    def test_stale_branch_warning_shown(self):
        """test_장기_미머지_브랜치_경고_표기

        HARN-13 — stale_branches가 있으면 브랜치·나이·ahead가 브리핑에 보여야 한다.
        """
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

    def test_ported_classification_shown_as_no_decision_needed(self):
        """test_포팅됨_분류는_참고_섹션에_결정_불요로_표기

        2026-08-05 3분류 확장 — ported는 '결정 필요' 섹션이 아니라 참고로 분리돼야 한다.
        """
        text = report.render_brief(
            _backlog(),
            [],
            "branch-x",
            date(2026, 7, 20),
            stale_branches=[
                ("claude/whymath-example-953m1e", 6.0, 40, "ported", "abc1234 merge: 953m1e 흡수")
            ],
        )
        assert "이미 포팅됨" in text
        assert "결정 불요" in text
        assert "claude/whymath-example-953m1e" in text
        assert "abc1234 merge: 953m1e 흡수" in text
        assert "미해결 장기 미머지 브랜치" not in text, "결정 대기 0건인데 강조 섹션이 뜨면 안 된다"

    def test_active_classification_shown_as_informational(self):
        """test_진행중_분류는_참고_섹션에_정보성으로_표기"""
        text = report.render_brief(
            _backlog(),
            [],
            "branch-x",
            date(2026, 7, 20),
            stale_branches=[("claude/whymath-active-example", 6.0, 30, "active", "")],
        )
        assert "타 세션 진행중" in text
        assert "정보성" in text
        assert "claude/whymath-active-example" in text
        assert "미해결 장기 미머지 브랜치" not in text

    def test_mixed_classifications_leave_only_unresolved_highlighted(self):
        """test_3분류가_섞이면_미해결만_강조_섹션에_남는다

        미해결·포팅됨·진행중이 섞인 브리핑에서 Kiki가 실제로 훑어야 하는 줄만 상단에 뜬다.
        """
        text = report.render_brief(
            _backlog(),
            [],
            "branch-x",
            date(2026, 7, 20),
            stale_branches=[
                ("claude/whymath-unresolved-example", 27.0, 513, "unresolved", ""),
                ("claude/whymath-ported-example", 6.0, 48, "ported", "def5678 merge: 흡수"),
                ("claude/whymath-active-example", 7.0, 44, "active", ""),
            ],
        )
        assert "미해결 장기 미머지 브랜치 (Kiki 결정 필요) — 1건" in text
        assert "claude/whymath-unresolved-example" in text
        assert "이미 포팅됨" in text and "claude/whymath-ported-example" in text
        assert "타 세션 진행중" in text and "claude/whymath-active-example" in text

    def test_legacy_4tuple_input_treated_as_all_unresolved(self):
        """test_4튜플_구버전_입력은_전부_미해결로_취급

        하위호환 — status·evidence 없는 기존 3-튜플 호출부는 unresolved로 안전 폴백.
        """
        text = report.render_brief(
            _backlog(),
            [],
            "branch-x",
            date(2026, 7, 20),
            stale_branches=[("claude/old-orphan", 9.3, 42)],
        )
        assert "미해결 장기 미머지 브랜치 (Kiki 결정 필요) — 1건" in text

    def test_no_stale_branches_omits_warning(self):
        """test_장기_미머지_브랜치_없으면_경고_생략"""
        text = report.render_brief(_backlog(), [], "branch-x", date(2026, 7, 20), stale_branches=[])
        assert "장기 미머지" not in text

    def test_stale_branch_lookup_failure_shown_as_pending(self):
        """test_장기_미머지_브랜치_조회_실패는_판정_보류로_표기

        조회 실패가 '방치 브랜치 없음'과 같은 문구로 보이면 침묵 실패다.
        """
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

    def test_stale_branch_message_carries_remediation_command(self):
        """test_판정_보류에_복구_명령이_함께_실린다

        판정 보류가 무기한 침묵이 되지 않으려면 화면만 보고 고칠 수 있어야 한다
        (2026-08-11 shallow 사고 — 브리핑이 잘린 히스토리 위에서 10건을 오분류하고도
        'ok'로 보고했다).
        """
        text = report.render_brief(
            _backlog(),
            [],
            "branch-x",
            date(2026, 7, 20),
            stale_branches=[],
            stale_branch_status="shallow",
            stale_branch_message="shallow 클론 — `git fetch --unshallow origin` 후 재실행",
        )
        assert "판정 보류" in text
        assert "--unshallow" in text
        # 음성 — 판정 불가 상태에서 미해결 목록을 흉내 내면 안 된다.
        assert "미해결 장기 미머지 브랜치" not in text

    def test_stale_branch_message_absent_keeps_legacy_wording(self):
        """test_메시지가_없으면_종전_문구_그대로 (하위호환)"""
        text = report.render_brief(
            _backlog(),
            [],
            "branch-x",
            date(2026, 7, 20),
            stale_branches=[],
            stale_branch_status="offline",
        )
        assert "(장기 미머지 브랜치 조회 불가: offline — 판정 보류)" in text

    def test_unmerged_done_candidate_excluded_from_brief(self):
        """test_미머지_done_후보는_브리핑에서_제외된다"""
        # HARN-12 — S2-01-c(유일 todo)가 타 세션에서 이미 done 처리됐으나 미머지 상태.
        backlog = _backlog()
        text = report.render_brief(
            backlog,
            [],
            "branch-x",
            date(2026, 7, 20),
            done_excluded={"S2-01-c": ["claude/finisher"]},
        )
        assert "S2-01-c" not in text.split("다음 착수 후보")[-1]
        assert "착수 가능 태스크 없음" in text  # 유일 후보가 빠져 폴백 메시지로

    def test_unmerged_done_filter_does_not_affect_unrelated_candidates(self):
        """test_미머지_done_필터는_무관한_후보를_다치지_않는다"""
        # 변별력 — 제외 대상이 아닌 todo 태스크는 그대로 노출돼야 필터가 아니라 고장이 아니다.
        backlog = _backlog()
        backlog.tasks["S2-02-d"] = Task(
            id="S2-02-d", title="다른 대기건", track="main", stage="S2", updated="2026-07-08"
        )
        text = report.render_brief(
            backlog,
            [],
            "branch-x",
            date(2026, 7, 20),
            done_excluded={"S2-01-c": ["claude/finisher"]},
        )
        candidates = text.split("다음 착수 후보")[-1]
        assert "S2-01-c" not in candidates
        assert "S2-02-d" in candidates

    def test_done_excluded_unspecified_keeps_existing_behavior(self):
        """test_done_excluded_미지정시_기존_동작_불변"""
        # 하위호환 — 새 파라미터를 생략한 기존 호출부(테스트 포함)가 그대로 통과해야 한다.
        text = report.render_brief(_backlog(), [], "branch-x", date(2026, 7, 20))
        assert "S2-01-c" in text.split("다음 착수 후보")[-1]
