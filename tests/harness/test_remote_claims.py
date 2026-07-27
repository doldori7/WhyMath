"""remote_claims.py — 원격 claim(refs/claims/*) CAS 원자성·폴백·청소 테스트.

가짜 git이 아니라 진짜 로컬 bare 원격으로 병렬 세션 레이스를 재현한다.
"""

from __future__ import annotations

import subprocess
from datetime import datetime, timezone
from pathlib import Path

import remote_claims
from models import Backlog, Task

TASK = "S1-01-sample-task"


def _mk_backlog(status: str = "in_progress", session: str | None = "claude/a") -> Backlog:
    backlog = Backlog(stage_order=["S1"])
    backlog.tasks[TASK] = Task(
        id=TASK, title="샘플", track="math-completion", stage="S1",
        status=status, session=session,
    )
    return backlog


class TestClaimCAS:
    def test_claim_성공_후_ls_remote에_ref_존재(self, bare_remote):
        _, clone = bare_remote
        a = clone("session-a")
        result = remote_claims.claim(a, TASK, "claude/session-a")
        assert result.status == "ok"
        claims, status = remote_claims.list_claims(a, with_meta=True)
        assert status == "ok"
        assert [c.task_id for c in claims] == [TASK]
        assert claims[0].branch == "claude/session-a"
        assert claims[0].ts  # UTC ISO8601 타임스탬프 기록됨

    def test_레이스_두_세션_중_한쪽만_성공(self, bare_remote):
        # 핵심 시나리오: A claim 후 B가 같은 태스크 claim → B는 conflict
        _, clone = bare_remote
        a = clone("session-a")
        b = clone("session-b")
        assert remote_claims.claim(a, TASK, "claude/session-a").status == "ok"
        result_b = remote_claims.claim(b, TASK, "claude/session-b")
        assert result_b.status == "conflict"
        # conflict 시 상대 claim 정보가 조회된다
        assert result_b.claim is not None
        assert result_b.claim.branch == "claude/session-a"

    def test_release_후_재claim_가능(self, bare_remote):
        _, clone = bare_remote
        a = clone("session-a")
        b = clone("session-b")
        assert remote_claims.claim(a, TASK, "claude/session-a").status == "ok"
        assert remote_claims.release(a, TASK, "claude/session-a").status == "ok"
        assert remote_claims.claim(b, TASK, "claude/session-b").status == "ok"

    def test_서로_다른_태스크는_독립_claim(self, bare_remote):
        _, clone = bare_remote
        a = clone("session-a")
        b = clone("session-b")
        assert remote_claims.claim(a, TASK, "claude/session-a").status == "ok"
        assert remote_claims.claim(b, "S1-02-other-task", "claude/session-b").status == "ok"


class TestReleaseSafety:
    def test_남의_claim_해제는_force_필수(self, bare_remote):
        _, clone = bare_remote
        a = clone("session-a")
        b = clone("session-b")
        assert remote_claims.claim(a, TASK, "claude/session-a").status == "ok"
        denied = remote_claims.release(b, TASK, "claude/session-b")
        assert denied.status == "error"
        assert "force" in denied.message
        forced = remote_claims.release(b, TASK, "claude/session-b", force=True)
        assert forced.status == "ok"

    def test_없는_claim_해제는_멱등(self, bare_remote):
        _, clone = bare_remote
        a = clone("session-a")
        assert remote_claims.release(a, TASK, "claude/session-a").status == "ok"


class TestFailOpen:
    def test_원격_없는_저장소는_offline(self, git_repo: Path):
        result = remote_claims.claim(git_repo, TASK, "claude/x")
        assert result.status == "offline"

    def test_죽은_원격은_offline_또는_error_절대_예외_아님(self, git_repo: Path, tmp_path):
        import subprocess
        subprocess.run(
            ["git", "remote", "add", "origin", str(tmp_path / "no-such-repo.git")],
            cwd=git_repo, check=True, capture_output=True,
        )
        result = remote_claims.claim(git_repo, TASK, "claude/x")
        assert result.status in ("offline", "error")

    def test_list_claims_원격_없으면_offline(self, git_repo: Path):
        claims, status = remote_claims.list_claims(git_repo)
        assert claims == []
        assert status == "offline"


class TestTopLevelFieldParser:
    """태스크 YAML 최상위 스칼라 파서 — PyYAML 비의존 (하네스 의존성 0 설계)."""

    def test_실제_dump_task_형식을_읽는다(self):
        import store

        body = store.dump_task(Task(
            id=TASK, title="샘플: 콜론 포함", track="math-completion", stage="S1",
            status="in_progress", session="claude/session-a",
            paths=["scripts/harness/**"],
        ))
        assert remote_claims._top_level_field(body, "status") == "in_progress"
        assert remote_claims._top_level_field(body, "session") == "claude/session-a"

    def test_null_세션은_빈_문자열(self):
        body = "id: X\nstatus: todo\nsession: null\n"
        assert remote_claims._top_level_field(body, "session") == ""

    def test_인용된_값의_따옴표를_벗긴다(self):
        body = 'status: "in_progress"\nsession: "claude/a-b"\n'
        assert remote_claims._top_level_field(body, "session") == "claude/a-b"

    def test_들여쓰기된_줄과_값_속_콜론에_속지_않는다(self):
        # notes 값 안의 'status: in_progress'와 리스트 항목이 최상위로 오인되면 안 된다
        body = ('status: todo\n'
                'notes: "이전 세션에서 status: in_progress 였음"\n'
                'acceptance:\n  - "status: in_progress 금지"\n')
        assert remote_claims._top_level_field(body, "status") == "todo"

    def test_없는_키는_빈_문자열(self):
        assert remote_claims._top_level_field("id: X\n", "session") == ""


class TestReadSideScan:
    """읽기측 교차 세션 탐지 (HARN-07) — CAS가 막힌 환경의 폴백.

    쓰기(refs/claims push)가 403인 환경을 가정하되, 읽기 경로는 진짜 로컬 원격에서
    실제 git fetch/show로 검증한다(시임 아님).
    """

    def _push_task_copy(self, repo: Path, branch: str, status: str,
                        session: str | None, task_id: str = TASK) -> None:
        """원격 브랜치에 태스크 YAML 사본을 심는다 — 타 세션이 push한 상태 재현."""
        import subprocess

        import store

        def run(*argv: str) -> None:
            subprocess.run(["git", *argv], cwd=repo, check=True, capture_output=True)

        store.save_task(repo, Task(
            id=task_id, title="샘플", track="math-completion", stage="S1",
            status=status, session=session,
        ))
        run("checkout", "-B", branch)
        run("add", ".")
        run("commit", "-m", f"claim {task_id}")
        run("push", "--quiet", "-u", "origin", branch)

    def test_타_세션_in_progress를_탐지한다(self, bare_remote):
        _, clone = bare_remote
        a, b = clone("session-a"), clone("session-b")
        self._push_task_copy(a, "claude/session-a", "in_progress", "claude/session-a")
        result = remote_claims.scan_remote_in_progress(b, TASK, "claude/session-b")
        assert result.status == "ok"
        assert [(h.branch, h.session) for h in result.holders] == [
            ("claude/session-a", "claude/session-a")
        ]

    def test_내_세션의_in_progress는_나를_막지_않는다(self, bare_remote):
        _, clone = bare_remote
        a, b = clone("session-a"), clone("session-b")
        # 원격에 남은 claim의 session이 '나'인 경우 (내 브랜치를 이미 push한 상태)
        self._push_task_copy(a, "claude/session-b", "in_progress", "claude/session-b")
        result = remote_claims.scan_remote_in_progress(b, TASK, "claude/session-b")
        assert result.status == "ok"
        assert result.holders == []

    def test_todo_상태는_탐지하지_않는다(self, bare_remote):
        _, clone = bare_remote
        a, b = clone("session-a"), clone("session-b")
        self._push_task_copy(a, "claude/session-a", "todo", None)
        result = remote_claims.scan_remote_in_progress(b, TASK, "claude/session-b")
        assert result.status == "ok"
        assert result.holders == []

    def test_태스크_파일이_없는_브랜치는_건너뛴다(self, bare_remote):
        _, clone = bare_remote
        _, b = clone("session-a"), clone("session-b")
        # main에는 backlog/ 자체가 없다 — 예외 없이 조용히 넘어가야 한다
        result = remote_claims.scan_remote_in_progress(b, TASK, "claude/session-b")
        assert result.status == "ok"
        assert result.holders == []
        assert result.scanned_refs >= 1

    def test_다른_태스크의_claim에는_반응하지_않는다(self, bare_remote):
        _, clone = bare_remote
        a, b = clone("session-a"), clone("session-b")
        self._push_task_copy(a, "claude/session-a", "in_progress", "claude/session-a",
                             task_id="S1-99-other-task")
        result = remote_claims.scan_remote_in_progress(b, TASK, "claude/session-b")
        assert result.status == "ok"
        assert result.holders == []

    def test_원격_없으면_offline_판정불가(self, git_repo: Path):
        result = remote_claims.scan_remote_in_progress(git_repo, TASK, "claude/x")
        assert result.status == "offline"
        assert result.holders == []  # 빈 holders를 '충돌 없음'으로 읽으면 안 된다

    def test_fetch_실패는_상태로_보고되고_예외가_아니다(self, bare_remote, monkeypatch):
        _, clone = bare_remote
        b = clone("session-b")
        original = remote_claims._git

        def fake_git(root, *argv, **kwargs):
            if argv and argv[0] == "fetch" and any("refs/heads" in a for a in argv):
                return subprocess.CompletedProcess(
                    ["git", *argv], 128, stdout="",
                    stderr="fatal: unable to access 'origin': The requested URL returned error: 403",
                )
            return original(root, *argv, **kwargs)

        monkeypatch.setattr(remote_claims, "_git", fake_git)
        result = remote_claims.scan_remote_in_progress(b, TASK, "claude/session-b")
        assert result.status in ("offline", "error")
        assert result.holders == []
        assert "403" in result.message  # 침묵 실패 금지 — 원인이 메시지에 남는다

    def test_브랜치_상한_초과는_truncated로_보고된다(self, bare_remote):
        _, clone = bare_remote
        a, b = clone("session-a"), clone("session-b")
        self._push_task_copy(a, "claude/session-a", "in_progress", "claude/session-a")
        result = remote_claims.scan_remote_in_progress(b, TASK, "claude/session-b",
                                                       max_refs=1)
        assert result.status == "ok"
        assert result.scanned_refs == 1
        assert result.truncated is True  # 조용한 축소 금지


class TestStaleAndReap:
    def test_stale_3중_기준(self):
        now = datetime(2026, 7, 16, 12, 0, tzinfo=timezone.utc)
        fresh_ts = "2026-07-16T10:00:00Z"    # 2시간 전 — TTL(72h) 이내
        old_ts = "2026-07-10T10:00:00Z"      # 6일 전 — TTL 초과
        claims = [
            remote_claims.RemoteClaim(TASK, "sha1", "claude/a", fresh_ts),
            remote_claims.RemoteClaim("S1-02-done-task", "sha2", "claude/b", fresh_ts),
            remote_claims.RemoteClaim("S1-03-ghost-task", "sha3", "claude/c", fresh_ts),
            remote_claims.RemoteClaim("S1-04-old-task", "sha4", "claude/d", old_ts),
        ]
        backlog = _mk_backlog()
        backlog.tasks["S1-02-done-task"] = Task(
            id="S1-02-done-task", title="완료됨", track="math-completion", stage="S1",
            status="done", artifacts=["PR#1"],
        )
        backlog.tasks["S1-04-old-task"] = Task(
            id="S1-04-old-task", title="오래됨", track="math-completion", stage="S1",
            status="in_progress", session="claude/d",
        )
        stale = remote_claims.stale_claims(claims, backlog, ttl_hours=72, now=now)
        reasons = {c.task_id: reason for c, reason in stale}
        assert TASK not in reasons                            # 신선 + in_progress → 유지
        assert reasons["S1-02-done-task"] == "task_done"      # 로컬 이미 done
        assert reasons["S1-03-ghost-task"] == "task_missing"  # 태스크 미존재
        assert reasons["S1-04-old-task"] == "ttl"             # TTL 초과

    def test_reap_dry_run은_삭제하지_않는다(self, bare_remote):
        _, clone = bare_remote
        a = clone("session-a")
        assert remote_claims.claim(a, "S1-03-ghost-task", "claude/session-a").status == "ok"
        backlog = _mk_backlog()  # ghost-task 미포함 → task_missing
        reaped = remote_claims.reap(a, backlog, ttl_hours=72, dry_run=True)
        assert len(reaped) == 1 and "task_missing" in reaped[0]
        claims, _ = remote_claims.list_claims(a)
        assert len(claims) == 1  # dry-run — 아직 남아 있음

    def test_reap_apply는_실제_삭제(self, bare_remote):
        _, clone = bare_remote
        a = clone("session-a")
        assert remote_claims.claim(a, "S1-03-ghost-task", "claude/session-a").status == "ok"
        backlog = _mk_backlog()
        reaped = remote_claims.reap(a, backlog, ttl_hours=72, dry_run=False)
        assert len(reaped) == 1
        claims, _ = remote_claims.list_claims(a)
        assert claims == []
