"""HARN-20 — review·cancel CLI 동사 배선 + block notes 보존 회귀 테스트.

배경(2026-08-10 통합점검): STATUS_TRANSITIONS(models.py)가 선언한 review·cancelled
전이에 대응하는 CLI 동사가 없었다(도달 경로 0·실데이터 0건/229) — 선언≠배선. 또한
`cmd_block`이 `task.notes = args.reason`로 원 notes(발견 경위·설계 근거)를 통째로
덮어써 blocked 태스크 4건 전건의 원문이 유실됐다.

이 파일은:
  ① review/cancel 동사가 실제로 상태를 전이시키고, 전이표가 허용하지 않는 경로는
     거부하는지(변별력 — 허용 0 대비 거부 1) 확인한다.
  ② review 상태가 in-flight 취급 코드(path_overlap 겹침 판정)에서 실제로 작동하는지
     실증한다(기존 in_progress 취급 코드는 이미 review를 포함하고 있었으나 도달할 방법이
     없어 미검증이었다).
  ③ block이 notes를 append로 보존하고(원문 유지) 덮어쓰지 않음을 확인한다. 이 회귀는
     `cmd_block`을 구 버그 형태(`task.notes = args.reason`)로 되돌리면 RED가 되는지
     별도로 수동 뮤테이션 검증했다(보고서 참조 — cp 백업/복원, git checkout 미사용).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import store

import backlog as cli


@pytest.fixture
def seeded_repo(git_repo: Path, monkeypatch) -> Path:
    monkeypatch.chdir(git_repo)
    assert cli.main(["seed"]) == 0
    return git_repo


def _add_task(task_id: str, notes: str = "", stage: str = "S1") -> int:
    argv = [
        "add",
        "--id",
        task_id,
        "--title",
        "HARN-20 테스트 태스크",
        "--track",
        "math-completion",
        "--stage",
        stage,
    ]
    if notes:
        argv += ["--notes", notes]
    return cli.main(argv)


class TestReviewTransitionWiring:
    """review <id> — in_progress → review 전이만 허용 (전이표 강제)."""

    def test_review_from_in_progress_succeeds(self, seeded_repo: Path, capsys):
        assert _add_task("T1-01-review-target") == 0
        assert cli.main(["start", "T1-01-review-target", "--no-remote"]) == 0
        capsys.readouterr()
        assert cli.main(["review", "T1-01-review-target"]) == 0
        backlog, _ = store.load_backlog(seeded_repo)
        task = backlog.tasks["T1-01-review-target"]
        assert task.status == "review"
        # session은 그대로 유지 — review는 여전히 in-flight, 세션이 여전히 태스크를 들고 있다
        assert task.session == store.current_branch(seeded_repo)

    def test_review_rejects_from_todo(self, seeded_repo: Path):
        """변별력 — todo에서 곧장 review는 거부돼야 한다(전이표 미허용)."""
        assert _add_task("T1-02-review-from-todo") == 0
        assert cli.main(["review", "T1-02-review-from-todo"]) == 1

    def test_review_rejects_from_blocked(self, seeded_repo: Path):
        assert _add_task("T1-03-review-from-blocked") == 0
        assert cli.main(["start", "T1-03-review-from-blocked", "--no-remote"]) == 0
        assert cli.main(["block", "T1-03-review-from-blocked", "--reason", "테스트 차단"]) == 0
        assert cli.main(["review", "T1-03-review-from-blocked"]) == 1

    def test_review_then_done_allowed(self, seeded_repo: Path):
        """전이표: review → done 허용 — done CLI가 review 상태에도 그대로 작동해야 한다."""
        assert _add_task("T1-04-review-then-done") == 0
        assert cli.main(["start", "T1-04-review-then-done", "--no-remote"]) == 0
        assert cli.main(["review", "T1-04-review-then-done"]) == 0
        assert cli.main(["done", "T1-04-review-then-done", "--artifact", "PR #1"]) == 0
        backlog, _ = store.load_backlog(seeded_repo)
        assert backlog.tasks["T1-04-review-then-done"].status == "done"

    def test_review_does_not_release_remote_claim(self, bare_remote, monkeypatch, capsys):
        """review는_원격_claim을_해제하지_않는다 (done/block과 대비되는 핵심 차이)."""
        import remote_claims

        _, clone = bare_remote
        repo = clone("session-review")
        monkeypatch.chdir(repo)
        assert cli.main(["seed"]) == 0
        assert _add_task("T1-05-review-keeps-claim") == 0
        assert cli.main(["start", "T1-05-review-keeps-claim"]) == 0
        capsys.readouterr()
        assert cli.main(["review", "T1-05-review-keeps-claim"]) == 0
        claims, status = remote_claims.list_claims(repo)
        assert status == "ok"
        assert [c.task_id for c in claims] == ["T1-05-review-keeps-claim"]

    def test_review_missing_task_rejected(self, seeded_repo: Path):
        assert cli.main(["review", "GHOST-99-nope"]) == 1

    def test_review_appends_event(self, seeded_repo: Path):
        assert _add_task("T1-06-review-event") == 0
        assert cli.main(["start", "T1-06-review-event", "--no-remote"]) == 0
        assert cli.main(["review", "T1-06-review-event"]) == 0
        events = (seeded_repo / "backlog" / "events.ndjson").read_text(encoding="utf-8")
        assert any(
            json.loads(line).get("action") == "review"
            and json.loads(line).get("id") == "T1-06-review-event"
            for line in events.splitlines()
        )


class TestReviewInFlightWiring:
    """review 상태가 in-flight 취급 코드(path_overlap 겹침 판정)에서 실제로 작동하는지 실증.

    기존 코드(_overlap_block_map·_inflight_tasks·stall_reason)는 이미
    `t.status in ("in_progress", "review")`로 review를 취급하고 있었으나, review에
    도달하는 CLI 경로가 없어 *한 번도 실행되지 않은 분기*였다(선언≠배선의 핵심 증상).
    """

    def _two_overlapping(self) -> tuple[str, str]:
        assert (
            cli.main(
                [
                    "add",
                    "--id",
                    "T2-01-overlap-a",
                    "--title",
                    "겹침 A",
                    "--track",
                    "math-completion",
                    "--stage",
                    "S1",
                    "--path",
                    "src/backend/api/**",
                ]
            )
            == 0
        )
        assert (
            cli.main(
                [
                    "add",
                    "--id",
                    "T2-02-overlap-b",
                    "--title",
                    "겹침 B",
                    "--track",
                    "math-completion",
                    "--stage",
                    "S1",
                    "--path",
                    "src/backend/**",
                ]
            )
            == 0
        )
        return "T2-01-overlap-a", "T2-02-overlap-b"

    def test_review_status_task_blocks_overlapping_start_in_block_mode(
        self, seeded_repo: Path, capsys
    ):
        """review_상태_태스크도_path_overlap_block_모드에서_겹침으로_잡힌다"""
        import store as store_mod
        from models import Policy

        store_mod.save_policy(seeded_repo, Policy(path_overlap="block"))
        a, b = self._two_overlapping()
        assert cli.main(["start", a, "--session", "claude/other", "--no-remote"]) == 0
        assert cli.main(["review", a]) == 0  # in_progress → review — 여전히 in-flight
        capsys.readouterr()
        # B는 A와 paths가 겹치고, A는 지금 review 상태 — block 모드면 착수 거부돼야 한다
        assert cli.main(["start", b, "--session", "claude/me", "--no-remote"]) == 1
        err = capsys.readouterr().err
        assert "겹침" in err
        backlog, _ = store.load_backlog(seeded_repo)
        assert backlog.tasks[b].status == "todo"

    def test_review_status_counted_as_active_in_stall_reason(self, seeded_repo: Path, capsys):
        """review_상태가_stall_reason의_active_집계에_포함된다"""
        import selector

        assert _add_task("T2-03-review-stall") == 0
        assert cli.main(["start", "T2-03-review-stall", "--no-remote"]) == 0
        assert cli.main(["review", "T2-03-review-stall"]) == 0
        backlog, _ = store.load_backlog(seeded_repo)
        code, detail = selector.stall_reason(backlog, [])
        # all_done이 아니어야 한다 — review 상태 태스크가 active로 잡혀야 함
        if code == "in_progress":
            assert any("T2-03-review-stall" in d for d in detail)


class TestCancelTransitionWiring:
    """cancel <id> --reason <사유> — todo/blocked → cancelled만 허용."""

    def test_cancel_from_todo_allowed(self, seeded_repo: Path):
        assert _add_task("T3-01-cancel-from-todo") == 0
        assert cli.main(["cancel", "T3-01-cancel-from-todo", "--reason", "우선순위 하락"]) == 0
        backlog, _ = store.load_backlog(seeded_repo)
        task = backlog.tasks["T3-01-cancel-from-todo"]
        assert task.status == "cancelled"
        assert task.session is None

    def test_cancel_from_blocked_allowed(self, seeded_repo: Path):
        assert _add_task("T3-02-cancel-from-blocked") == 0
        assert cli.main(["start", "T3-02-cancel-from-blocked", "--no-remote"]) == 0
        assert cli.main(["block", "T3-02-cancel-from-blocked", "--reason", "차단"]) == 0
        assert cli.main(["cancel", "T3-02-cancel-from-blocked", "--reason", "더는 불필요"]) == 0
        backlog, _ = store.load_backlog(seeded_repo)
        assert backlog.tasks["T3-02-cancel-from-blocked"].status == "cancelled"

    def test_cancel_from_in_progress_rejected(self, seeded_repo: Path):
        """변별력 — in_progress에서 곧장 cancel은 거부돼야 한다(전이표: block/todo 경유 필수)."""
        assert _add_task("T3-03-cancel-from-in-progress") == 0
        assert cli.main(["start", "T3-03-cancel-from-in-progress", "--no-remote"]) == 0
        assert cli.main(["cancel", "T3-03-cancel-from-in-progress", "--reason", "시도"]) == 1
        backlog, _ = store.load_backlog(seeded_repo)
        # 거부됐으므로 상태 불변
        assert backlog.tasks["T3-03-cancel-from-in-progress"].status == "in_progress"

    def test_cancel_from_review_rejected(self, seeded_repo: Path):
        """변별력 — review에서도 곧장 cancel은 거부(전이표: review → done|in_progress만)."""
        assert _add_task("T3-04-cancel-from-review") == 0
        assert cli.main(["start", "T3-04-cancel-from-review", "--no-remote"]) == 0
        assert cli.main(["review", "T3-04-cancel-from-review"]) == 0
        assert cli.main(["cancel", "T3-04-cancel-from-review", "--reason", "시도"]) == 1

    def test_cancel_missing_task_rejected(self, seeded_repo: Path):
        assert cli.main(["cancel", "GHOST-98-nope", "--reason", "무엇"]) == 1

    def test_cancel_requires_reason_argument(self, seeded_repo: Path):
        assert _add_task("T3-05-cancel-no-reason") == 0
        with pytest.raises(SystemExit):
            cli.main(["cancel", "T3-05-cancel-no-reason"])  # --reason 누락 → argparse 거부

    def test_cancel_appends_reason_to_notes_without_erasing_original(self, seeded_repo: Path):
        assert (
            _add_task("T3-06-cancel-notes", notes="원래 설계 근거 — 이 태스크가 필요한 이유") == 0
        )
        assert cli.main(["cancel", "T3-06-cancel-notes", "--reason", "취소 사유입니다"]) == 0
        backlog, _ = store.load_backlog(seeded_repo)
        notes = backlog.tasks["T3-06-cancel-notes"].notes
        assert "원래 설계 근거" in notes
        assert "취소 사유입니다" in notes

    def test_cancel_appends_event(self, seeded_repo: Path):
        assert _add_task("T3-07-cancel-event") == 0
        assert cli.main(["cancel", "T3-07-cancel-event", "--reason", "이벤트 확인"]) == 0
        events = (seeded_repo / "backlog" / "events.ndjson").read_text(encoding="utf-8")
        assert any(
            json.loads(line).get("action") == "cancel"
            and json.loads(line).get("id") == "T3-07-cancel-event"
            for line in events.splitlines()
        )


class TestCancelReleasesRemoteClaim:
    def test_cancel_calls_remote_claim_release(self, seeded_repo: Path, monkeypatch):
        """cancel이_원격_claim_해제_경로를_호출한다 (block과 동일 배선 — 스파이로 확인)."""
        calls: list[tuple] = []
        original = cli._release_remote_claim

        def spy(root, task_id, prev_session):
            calls.append((task_id, prev_session))
            return original(root, task_id, prev_session)

        monkeypatch.setattr(cli, "_release_remote_claim", spy)
        assert _add_task("T4-01-cancel-release") == 0
        assert cli.main(["cancel", "T4-01-cancel-release", "--reason", "해제 확인"]) == 0
        assert calls == [("T4-01-cancel-release", None)]


class TestBlockNotesPreservation:
    """② block --reason이 원 notes를 append로 보존한다 (덮어쓰지 않음).

    실제 버그(수정 전 `task.notes = args.reason`)가 재발하면 이 테스트들이 RED가
    되는지는 cp 백업/복원 방식의 수동 뮤테이션으로 별도 검증했다(보고서 참조).
    """

    def test_block_appends_reason_preserves_original_notes(self, seeded_repo: Path):
        original = "원본 설계 근거 — 이 태스크가 왜 필요한지에 대한 상세 서술"
        assert _add_task("T5-01-block-preserve", notes=original) == 0
        assert cli.main(["start", "T5-01-block-preserve", "--no-remote"]) == 0
        assert cli.main(["block", "T5-01-block-preserve", "--reason", "검증 2연속 실패"]) == 0
        backlog, _ = store.load_backlog(seeded_repo)
        notes = backlog.tasks["T5-01-block-preserve"].notes
        assert original in notes  # 원문이 사라지지 않았다
        assert "검증 2연속 실패" in notes  # 차단 사유도 남는다

    def test_block_with_empty_original_notes_just_uses_reason(self, seeded_repo: Path):
        """원 notes가 비어 있으면(빈 문자열) append 결과는 사유 문구 자체다."""
        assert _add_task("T5-02-block-empty-notes") == 0
        assert cli.main(["start", "T5-02-block-empty-notes", "--no-remote"]) == 0
        assert cli.main(["block", "T5-02-block-empty-notes", "--reason", "빈 notes 케이스"]) == 0
        backlog, _ = store.load_backlog(seeded_repo)
        notes = backlog.tasks["T5-02-block-empty-notes"].notes
        assert "빈 notes 케이스" in notes

    def test_unblock_keeps_appended_block_history(self, seeded_repo: Path):
        """unblock은 notes를 건드리지 않는다 — 차단 이력이 unblock 후에도 남는다(의도된 동작)."""
        original = "원본 설계 근거"
        assert _add_task("T5-03-unblock-keeps-history", notes=original) == 0
        assert cli.main(["start", "T5-03-unblock-keeps-history", "--no-remote"]) == 0
        assert cli.main(["block", "T5-03-unblock-keeps-history", "--reason", "일시 차단"]) == 0
        assert cli.main(["unblock", "T5-03-unblock-keeps-history"]) == 0
        backlog, _ = store.load_backlog(seeded_repo)
        notes = backlog.tasks["T5-03-unblock-keeps-history"].notes
        assert original in notes
        assert "일시 차단" in notes

    def test_repeated_blocks_accumulate_history_without_losing_earlier_entries(
        self, seeded_repo: Path
    ):
        """차단이_반복돼도_이전_이력이_누적되고_사라지지_않는다 (S3-24 실제 사고 형태)."""
        original = "최초 설계 근거"
        assert _add_task("T5-04-repeated-block", notes=original) == 0
        assert cli.main(["start", "T5-04-repeated-block", "--no-remote"]) == 0
        assert cli.main(["block", "T5-04-repeated-block", "--reason", "1차 차단 사유"]) == 0
        assert cli.main(["unblock", "T5-04-repeated-block"]) == 0
        assert cli.main(["start", "T5-04-repeated-block", "--no-remote"]) == 0
        assert cli.main(["block", "T5-04-repeated-block", "--reason", "2차 차단 사유"]) == 0
        backlog, _ = store.load_backlog(seeded_repo)
        notes = backlog.tasks["T5-04-repeated-block"].notes
        assert original in notes
        assert "1차 차단 사유" in notes
        assert "2차 차단 사유" in notes


class TestAppendNoteHelper:
    """_append_note 헬퍼 단위 테스트 — block·cancel이 공유하는 로직."""

    def test_empty_original_returns_stamp_only(self):
        result = cli._append_note("", "사유", "차단")
        assert result.startswith("[차단 ")
        assert "사유" in result

    def test_whitespace_only_original_treated_as_empty(self):
        result = cli._append_note("   \n  ", "사유", "차단")
        assert result.startswith("[차단 ")

    def test_nonempty_original_is_preserved_and_appended(self):
        result = cli._append_note("원본 텍스트", "새 사유", "취소")
        assert result.startswith("원본 텍스트")
        assert "[취소 " in result
        assert "새 사유" in result
