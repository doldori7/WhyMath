"""board.py — 작업 보드 열 판정·집계·렌더 테스트 (날짜 고정).

이 보드는 "무엇을 했고 무엇을 하는 중이며 무엇이 예정인가"를 보여주는 읽기 전용
투영이다. 따라서 테스트가 고정하는 계약은 두 가지다:
    ① 열 판정을 selector와 따로 만들지 않는다(이중 진실원천 금지)
    ② 어떤 태스크도 조용히 사라지지 않는다(열 배치 + 취소 = 전체)
"""

from __future__ import annotations

import json
import re
from datetime import date

import board
from models import Backlog, Gate, Task, Track

TODAY = date(2026, 8, 31)


def _backlog() -> Backlog:
    backlog = Backlog(stage_order=["S1", "S2", "E1"])
    backlog.tracks["main"] = Track(id="main", title="기본")
    backlog.tracks["e-axis"] = Track(id="e-axis", title="확장", entry_gate="G-e-axis")
    backlog.gates["G-e-axis"] = Gate(id="G-e-axis", title="E축 진입", status="pending")
    backlog.gates["G-key"] = Gate(
        id="G-key", title="키 투입", requested="2026-08-11", remind_after_days=7
    )
    backlog.tasks["S1-01-done"] = Task(
        id="S1-01-done",
        title="완료건",
        track="main",
        stage="S1",
        status="done",
        artifacts=["#101"],
        updated="2026-08-20",
    )
    backlog.tasks["S1-02-done"] = Task(
        id="S1-02-done",
        title="더 최근 완료건",
        track="main",
        stage="S1",
        status="done",
        artifacts=["#102"],
        updated="2026-08-29",
    )
    backlog.tasks["S1-03-run"] = Task(
        id="S1-03-run",
        title="진행건",
        track="main",
        stage="S1",
        status="in_progress",
        session="claude/x",
    )
    backlog.tasks["S1-04-review"] = Task(
        id="S1-04-review", title="검토건", track="main", stage="S1", status="review"
    )
    backlog.tasks["S1-05-blocked"] = Task(
        id="S1-05-blocked",
        title="차단건",
        track="main",
        stage="S1",
        status="blocked",
        notes="원 사유 문단\n\n[차단 2026-08-11] 최신 사유 문단\n\n[복구 불가] 부기 문단",
    )
    backlog.tasks["S2-01-ready"] = Task(
        id="S2-01-ready", title="착수가능", track="main", stage="S2"
    )
    backlog.tasks["S2-02-deps"] = Task(
        id="S2-02-deps",
        title="의존대기",
        track="main",
        stage="S2",
        depends_on=["S1-03-run"],
    )
    backlog.tasks["S2-03-gate"] = Task(
        id="S2-03-gate", title="게이트대기", track="main", stage="S2", requires_gates=["G-key"]
    )
    backlog.tasks["S2-04-human"] = Task(
        id="S2-04-human", title="사람소유", track="main", stage="S2", owner="kiki"
    )
    backlog.tasks["E1-01-track"] = Task(
        id="E1-01-track", title="트랙게이트", track="e-axis", stage="E1"
    )
    backlog.tasks["S2-05-cancel"] = Task(
        id="S2-05-cancel", title="취소건", track="main", stage="S2", status="cancelled"
    )
    return backlog


def _column_of(payload: dict, task_id: str) -> str:
    return next(t["column"] for t in payload["tasks"] if t["id"] == task_id)


class TestClassify:
    def test_status_maps_to_column(self):
        """test_상태가_열로_매핑된다"""
        backlog = _backlog()
        cases = {
            "S1-01-done": "done",
            "S1-03-run": "in_progress",
            "S1-04-review": "in_progress",
            "S1-05-blocked": "blocked",
            "S2-01-ready": "ready",
            "S2-05-cancel": "cancelled",
        }
        for task_id, expected in cases.items():
            assert board.classify(backlog, backlog.tasks[task_id])[0] == expected

    def test_waiting_reasons_come_from_selector(self):
        """test_대기_사유는_selector_판정을_그대로_쓴다"""
        backlog = _backlog()
        reasons = {
            "S2-02-deps": "선행 태스크 대기",
            "S2-03-gate": "사람 게이트 대기",
            "S2-04-human": "사람 소유",
            "E1-01-track": "트랙 진입 게이트",
        }
        for task_id, label in reasons.items():
            column, reason, detail = board.classify(backlog, backlog.tasks[task_id])
            assert column == "waiting"
            assert reason == label
            assert detail  # 근거(의존 id·게이트 id·owner)가 비어 있으면 카드가 무의미하다

    def test_blocked_card_shows_latest_block_paragraph(self):
        """test_차단_카드는_최신_차단_문단을_보여준다"""
        backlog = _backlog()
        _, _, detail = board.classify(backlog, backlog.tasks["S1-05-blocked"])
        assert "최신 사유 문단" in detail
        assert "부기 문단" not in detail

    def test_excerpt_without_block_paragraph_falls_back_to_first(self):
        """test_차단_문단이_없으면_첫_문단으로_되돌린다"""
        assert board._excerpt("원 사유\n\n[복구 불가] 부기") == "원 사유"

    def test_excerpt_is_truncated(self):
        """test_발췌는_상한에서_잘린다"""
        excerpt = board._excerpt("가" * 500)
        assert len(excerpt) <= board._NOTE_MAX
        assert excerpt.endswith("…")


class TestBoardPayload:
    def test_no_task_silently_disappears(self):
        """test_어떤_태스크도_조용히_사라지지_않는다"""
        payload = board.build_board(_backlog(), [], TODAY)
        placed = sum(len(col["ids"]) for col in payload["columns"])
        assert placed + payload["counts"]["cancelled"] == payload["total"]
        assert payload["total"] == len(payload["tasks"])

    def test_counts_match_column_sizes(self):
        """test_집계_수치가_열_크기와_일치한다"""
        payload = board.build_board(_backlog(), [], TODAY)
        for column in payload["columns"]:
            assert payload["counts"][column["key"]] == len(column["ids"])

    def test_done_column_is_newest_first(self):
        """test_완료_열은_최근_갱신_우선"""
        payload = board.build_board(_backlog(), [], TODAY)
        done = next(c for c in payload["columns"] if c["key"] == "done")
        assert done["ids"] == ["S1-02-done", "S1-01-done"]

    def test_active_columns_follow_next_ordering(self):
        """test_활성_열은_next_정렬(스테이지→우선순위→해금수→id)을_따른다"""
        backlog = _backlog()
        backlog.tasks["S1-06-ready"] = Task(
            id="S1-06-ready", title="앞선 스테이지", track="main", stage="S1", priority=1
        )
        payload = board.build_board(backlog, [], TODAY)
        ready = next(c for c in payload["columns"] if c["key"] == "ready")
        assert ready["ids"][0] == "S1-06-ready"

    def test_pending_gates_carry_elapsed_days_and_overdue(self):
        """test_대기_게이트는_경과일과_초과여부를_싣는다"""
        payload = board.build_board(_backlog(), [], TODAY)
        gates = {g["id"]: g for g in payload["gates"]}
        assert gates["G-key"]["days"] == 20
        assert gates["G-key"]["overdue"] is True
        assert gates["G-e-axis"]["overdue"] is False

    def test_stage_and_track_rollups(self):
        """test_스테이지·트랙_집계"""
        payload = board.build_board(_backlog(), [], TODAY)
        assert {"stage": "S1", "done": 2, "total": 5} in payload["stages"]
        assert payload["tracks"]["e-axis"]["entry_gate"] == "G-e-axis"
        assert payload["layers"]["backend"]["total"] == payload["total"]

    def test_errors_are_surfaced(self):
        """test_정합성_경고는_보드에_실린다"""
        payload = board.build_board(_backlog(), ["샘플 위반"], TODAY)
        assert payload["errors"] == ["샘플 위반"]


class TestRender:
    def test_html_embeds_parsable_payload(self):
        """test_HTML에_박힌_페이로드가_그대로_파싱된다"""
        payload = board.build_board(_backlog(), [], TODAY)
        html = board.render_html(payload)
        blob = re.search(r'<script id="payload" type="application/json">(.*?)</script>', html, re.S)
        assert blob is not None
        assert json.loads(blob.group(1))["total"] == payload["total"]

    def test_html_is_self_contained(self):
        """test_HTML은_외부_요청을_하지_않는다"""
        html = board.render_html(board.build_board(_backlog(), [], TODAY))
        assert "http://" not in html and "https://" not in html

    def test_payload_cannot_close_the_script_tag(self):
        """test_제목의_script_종료_태그가_주입되지_않는다"""
        backlog = _backlog()
        injected = "</script><script>alert(1)</script>"
        backlog.tasks["S1-03-run"].title = injected
        html = board.render_html(board.build_board(backlog, [], TODAY))
        marker = '<script id="payload" type="application/json">'
        start = html.index(marker) + len(marker)
        # 브라우저는 **첫** </script>에서 스크립트를 닫는다 — 거기까지가 실제 페이로드다.
        # 이스케이프가 빠지면 이 조각이 JSON 중간에서 잘려 파싱이 실패한다(변별력 있는 검사).
        blob = html[start : html.index("</script>", start)]
        assert injected in [task["title"] for task in json.loads(blob)["tasks"]]
        assert "<" not in blob

    def test_text_summary_reports_every_column(self):
        """test_터미널_요약은_열별_건수를_보고한다"""
        text = board.render_text(board.build_board(_backlog(), [], TODAY))
        assert "진행 중 (2건)" in text
        assert "차단 (1건)" in text
        assert "완료" not in text.split("──")[2]  # 완료 열은 요약에서 제외(최근 이력은 HTML에서)


class TestCli:
    def test_json_mode_prints_payload(self, capsys):
        """test_json_모드는_페이로드를_출력한다"""
        assert board.main(["--json"]) == 0
        printed = json.loads(capsys.readouterr().out)
        assert printed["total"] == len(printed["tasks"])

    def test_writes_html_file(self, tmp_path, capsys):
        """test_HTML_파일을_생성한다"""
        out = tmp_path / "board.html"
        assert board.main(["--out", str(out)]) == 0
        capsys.readouterr()
        assert out.exists()
        assert "WhyMath 작업 보드" in out.read_text(encoding="utf-8")

    def test_backlog_files_are_not_mutated(self, tmp_path, capsys):
        """test_보드_생성은_백로그를_쓰지_않는다 (읽기 전용 계약)"""
        import store

        root = store.find_repo_root()
        before = {
            path: path.stat().st_mtime_ns
            for path in (root / "backlog").rglob("*")
            if path.is_file()
        }
        assert board.main(["--out", str(tmp_path / "board.html")]) == 0
        capsys.readouterr()
        after = {
            path: path.stat().st_mtime_ns
            for path in (root / "backlog").rglob("*")
            if path.is_file()
        }
        assert before == after


class TestFragment:
    def test_fragment_omits_document_shell(self):
        """test_조각_모드는_문서_껍데기를_생략한다"""
        payload = board.build_board(_backlog(), [], TODAY)
        fragment = board.render_html(payload, fragment=True)
        for tag in ("<!doctype", "<html", "<head>", "<body>"):
            assert tag not in fragment.lower()
        assert fragment.startswith("<title>")
        assert '<script id="payload"' in fragment

    def test_document_wraps_the_same_content(self):
        """test_완전_문서는_같은_본문을_두른다"""
        payload = board.build_board(_backlog(), [], TODAY)
        document = board.render_html(payload)
        fragment = board.render_html(payload, fragment=True)
        assert document.lower().startswith("<!doctype html>")
        assert fragment.split("</style>", 1)[1].strip() in document


class TestUnmergedDone:
    """미머지 완료분 재조정 — 끝난 작업이 "예정"으로 보이면 중복 구현을 부른다 (HARN-11 동형)."""

    def test_ready_task_done_elsewhere_moves_to_waiting(self):
        """test_다른_브랜치에서_완료된_태스크는_다음착수에서_빠진다"""
        payload = board.build_board(
            _backlog(),
            [],
            TODAY,
            remote_done={"S2-01-ready": ["claude/other-session"]},
            remote_done_status="ok",
        )
        assert _column_of(payload, "S2-01-ready") == "waiting"
        card = next(t for t in payload["tasks"] if t["id"] == "S2-01-ready")
        assert card["reason"] == "미머지 완료(다른 브랜치)"
        assert card["detail"] == "claude/other-session"

    def test_reconciliation_is_lossless(self):
        """test_재조정도_무손실이다"""
        payload = board.build_board(
            _backlog(),
            [],
            TODAY,
            remote_done={"S2-01-ready": ["claude/other-session"]},
            remote_done_status="ok",
        )
        placed = sum(len(col["ids"]) for col in payload["columns"])
        assert placed + payload["counts"]["cancelled"] == payload["total"]

    def test_terminal_states_are_untouched(self):
        """test_완료·진행·차단_카드는_재조정_대상이_아니다"""
        remote_done = {"S1-01-done": ["b1"], "S1-03-run": ["b2"], "S1-05-blocked": ["b3"]}
        payload = board.build_board(
            _backlog(), [], TODAY, remote_done=remote_done, remote_done_status="ok"
        )
        assert _column_of(payload, "S1-01-done") == "done"
        assert _column_of(payload, "S1-03-run") == "in_progress"
        assert _column_of(payload, "S1-05-blocked") == "blocked"

    def test_indeterminate_scan_is_surfaced_not_swallowed(self):
        """test_판정_불가는_빈_결과로_위장되지_않는다"""
        payload = board.build_board(
            _backlog(), [], TODAY, remote_done={}, remote_done_status="offline"
        )
        assert payload["remote_done_status"] == "offline"
        assert "판정 불가(offline)" in board.render_text(payload)

    def test_clean_scan_reports_the_exclusion_count(self):
        """test_정상_스캔은_제외_건수를_보고한다"""
        payload = board.build_board(
            _backlog(), [], TODAY, remote_done={"S2-01-ready": ["b1"]}, remote_done_status="ok"
        )
        text = board.render_text(payload)
        assert "미머지 완료 1건" in text
        assert "판정 불가" not in text

    def test_default_status_is_skipped_not_ok(self):
        """test_스캔을_안_했으면_ok가_아니라_skipped다"""
        payload = board.build_board(_backlog(), [], TODAY)
        assert payload["remote_done_status"] == "skipped"
        assert "판정 불가(skipped)" in board.render_text(payload)

    def test_no_remote_flag_skips_the_scan(self, tmp_path):
        """test_no_remote는_스캔을_건너뛰고_그_사실을_남긴다"""
        import store

        root = store.find_repo_root()
        backlog, _ = store.load_backlog(root)
        assert board.scan_unmerged_done(root, backlog, skip=True) == ({}, "skipped")


class TestGateDetail:
    """게이트 상세 — "무엇을 하면 풀리는가"까지 화면이 답해야 한다."""

    def _gate(self, payload: dict, gate_id: str) -> dict:
        return next(g for g in payload["gates"] if g["id"] == gate_id)

    def test_detail_carries_the_full_note_and_meta(self):
        """test_상세는_노트_원문과_메타를_그대로_싣는다"""
        backlog = _backlog()
        backlog.gates["G-key"].notes = "여러 줄\n런북 본문\n\n두 번째 문단"
        payload = board.build_board(backlog, [], TODAY)
        gate = self._gate(payload, "G-key")
        assert gate["notes"] == "여러 줄\n런북 본문\n\n두 번째 문단"  # 발췌·요약하지 않는다
        assert gate["kind"] == "human"
        assert gate["assignee"] == "kiki"
        assert gate["remind_after_days"] == 7
        assert gate["days"] == 20 and gate["overdue"] is True

    def test_blocking_tasks_are_listed(self):
        """test_이_게이트를_건_태스크가_상세에_나온다"""
        payload = board.build_board(_backlog(), [], TODAY)
        gate = self._gate(payload, "G-key")
        assert [t["id"] for t in gate["blocking_tasks"]] == ["S2-03-gate"]

    def test_finished_tasks_are_not_counted_as_blocked(self):
        """test_종결된_태스크는_막힌_것으로_세지_않는다"""
        backlog = _backlog()
        backlog.tasks["S2-03-gate"].status = "cancelled"
        payload = board.build_board(backlog, [], TODAY)
        assert self._gate(payload, "G-key")["blocking_tasks"] == []

    def test_track_entry_gate_locks_are_visible(self):
        """test_트랙_진입_게이트_잠금이_보인다 (태스크 쪽엔 표시가 남지 않는 축)"""
        payload = board.build_board(_backlog(), [], TODAY)
        gate = self._gate(payload, "G-e-axis")
        assert gate["blocking_tasks"] == []  # 어떤 태스크도 requires_gates로 걸지 않았다
        assert gate["blocking_tracks"] == [{"track": "e-axis", "title": "확장", "pending": 1}]

    def test_resolved_gates_are_available_with_evidence(self):
        """test_해소된_게이트도_근거와_함께_열람_가능하다"""
        backlog = _backlog()
        backlog.gates["G-key"].status = "cleared"
        backlog.gates["G-key"].evidence = "PR #921"
        payload = board.build_board(backlog, [], TODAY)
        gate = self._gate(payload, "G-key")
        assert gate["status"] == "cleared"
        assert gate["evidence"] == "PR #921"
        assert gate["overdue"] is False  # 해소된 게이트는 경과일로 붉게 칠하지 않는다

    def test_pending_gates_sort_before_resolved(self):
        """test_대기_게이트가_해소된_것보다_앞선다"""
        backlog = _backlog()
        backlog.gates["G-key"].status = "waived"
        payload = board.build_board(backlog, [], TODAY)
        statuses = [g["status"] for g in payload["gates"]]
        assert statuses == sorted(statuses, key=lambda s: s != "pending")

    def test_gate_section_is_rendered_from_payload(self):
        """test_게이트_섹션이_페이로드에서_렌더된다"""
        backlog = _backlog()
        backlog.gates["G-key"].notes = "런북 본문"
        html = board.render_html(board.build_board(backlog, [], TODAY))
        assert 'id="gates-resolved"' in html  # 해소 그룹 자리
        assert "function gateBody(" in html  # 펼침 본문 렌더러
        assert "런북 본문" in html  # 노트가 실제로 페이지에 실린다
