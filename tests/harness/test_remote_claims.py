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
        id=TASK,
        title="샘플",
        track="math-completion",
        stage="S1",
        status=status,
        session=session,
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
            cwd=git_repo,
            check=True,
            capture_output=True,
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

        body = store.dump_task(
            Task(
                id=TASK,
                title="샘플: 콜론 포함",
                track="math-completion",
                stage="S1",
                status="in_progress",
                session="claude/session-a",
                paths=["scripts/harness/**"],
            )
        )
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
        body = (
            "status: todo\n"
            'notes: "이전 세션에서 status: in_progress 였음"\n'
            'acceptance:\n  - "status: in_progress 금지"\n'
        )
        assert remote_claims._top_level_field(body, "status") == "todo"

    def test_없는_키는_빈_문자열(self):
        assert remote_claims._top_level_field("id: X\n", "session") == ""


class TestReadSideScan:
    """읽기측 교차 세션 탐지 (HARN-07) — CAS가 막힌 환경의 폴백.

    쓰기(refs/claims push)가 403인 환경을 가정하되, 읽기 경로는 진짜 로컬 원격에서
    실제 git fetch/show로 검증한다(시임 아님).
    """

    def _push_task_copy(
        self, repo: Path, branch: str, status: str, session: str | None, task_id: str = TASK
    ) -> None:
        """원격 브랜치에 태스크 YAML 사본을 심는다 — 타 세션이 push한 상태 재현."""
        import subprocess

        import store

        def run(*argv: str) -> None:
            subprocess.run(["git", *argv], cwd=repo, check=True, capture_output=True)

        store.save_task(
            repo,
            Task(
                id=task_id,
                title="샘플",
                track="math-completion",
                stage="S1",
                status=status,
                session=session,
            ),
        )
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
        self._push_task_copy(
            a, "claude/session-a", "in_progress", "claude/session-a", task_id="S1-99-other-task"
        )
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
                    ["git", *argv],
                    128,
                    stdout="",
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
        result = remote_claims.scan_remote_in_progress(b, TASK, "claude/session-b", max_refs=1)
        assert result.status == "ok"
        assert result.scanned_refs == 1
        assert result.truncated is True  # 조용한 축소 금지


class TestReadSideStaleHandling:
    """HARN-08 — 머지·폐기 브랜치에 남은 in_progress 과탐 해소 (규칙 A·B).

    SQUASH 머지 저장소라 조상 검사(`merge-base --is-ancestor`)는 쓸 수 없다 —
    머지된 브랜치도 트렁크의 조상이 아니다(2026-07-27 5건 전수 실측). 대신
    트렁크 사본의 status(규칙 A)와 "트렁크는 세션이 아니다"(규칙 B)로 판별한다.
    """

    def _write_task(
        self, repo: Path, status: str, session: str | None, task_id: str = TASK
    ) -> None:
        import store

        store.save_task(
            repo,
            Task(
                id=task_id,
                title="샘플",
                track="math-completion",
                stage="S1",
                status=status,
                session=session,
                artifacts=["PR#0"] if status == "done" else [],
            ),
        )

    def _run(self, repo: Path, *argv: str) -> None:
        subprocess.run(["git", *argv], cwd=repo, check=True, capture_output=True)

    def _push_trunk(
        self, repo: Path, status: str, session: str | None = None, task_id: str = TASK
    ) -> None:
        """트렁크(origin/main)에 태스크 사본을 심는다 — 규칙 A·B의 신호원."""
        self._run(repo, "checkout", "-q", "main")
        self._write_task(repo, status, session, task_id)
        self._run(repo, "add", ".")
        self._run(repo, "commit", "-q", "-m", f"trunk {status}")
        self._run(repo, "push", "--quiet", "origin", "main")

    def _push_session_branch(
        self, repo: Path, branch: str, status: str, session: str | None, task_id: str = TASK
    ) -> None:
        """세션 브랜치에 태스크 사본을 심는다 (홀더 후보)."""
        self._run(repo, "checkout", "-q", "-B", branch)
        self._write_task(repo, status, session, task_id)
        self._run(repo, "add", ".")
        self._run(repo, "commit", "-q", "-m", f"claim {task_id}")
        self._run(repo, "push", "--quiet", "-u", "origin", branch)

    def test_규칙A_트렁크가_done이면_홀더는_stale로_제외된다(self, bare_remote):
        _, clone = bare_remote
        a, b = clone("session-a"), clone("session-b")
        self._push_trunk(a, "done")
        self._push_session_branch(a, "claude/session-a", "in_progress", "claude/session-a")
        result = remote_claims.scan_remote_in_progress(b, TASK, "claude/session-b")
        assert result.status == "ok"
        assert result.holders == []  # 과탐 해소 — 착수 허용
        assert result.trunk_status == "done"
        # 조용히 버리지 않는다 — 무엇을 왜 무시했는지 남는다
        assert [(s.branch, s.reason) for s in result.skipped] == [
            ("claude/session-a", "trunk_done")
        ]

    def test_규칙A_역_트렁크가_todo면_여전히_차단한다(self, bare_remote):
        # 규칙 A가 보호를 과잉 무력화하면 안 된다 — 착륙하지 않은 태스크는 그대로 막힌다
        _, clone = bare_remote
        a, b = clone("session-a"), clone("session-b")
        self._push_trunk(a, "todo")
        self._push_session_branch(a, "claude/session-a", "in_progress", "claude/session-a")
        result = remote_claims.scan_remote_in_progress(b, TASK, "claude/session-b")
        assert result.status == "ok"
        assert [(h.branch, h.session) for h in result.holders] == [
            ("claude/session-a", "claude/session-a")
        ]
        assert result.skipped == []

    def test_규칙A_cancelled도_착륙으로_본다(self, bare_remote):
        _, clone = bare_remote
        a, b = clone("session-a"), clone("session-b")
        self._push_trunk(a, "cancelled")
        self._push_session_branch(a, "claude/session-a", "in_progress", "claude/session-a")
        result = remote_claims.scan_remote_in_progress(b, TASK, "claude/session-b")
        assert result.holders == []
        assert [s.reason for s in result.skipped] == ["trunk_cancelled"]

    def test_규칙B_트렁크_자신은_홀더가_될_수_없다(self, bare_remote):
        # main의 in_progress는 활성 claim이 아니라 대장 위생 실패(done 미기입 머지)다
        _, clone = bare_remote
        a, b = clone("session-a"), clone("session-b")
        self._push_trunk(a, "in_progress", "claude/dead-session")
        result = remote_claims.scan_remote_in_progress(b, TASK, "claude/session-b")
        assert result.status == "ok"
        assert result.holders == []
        assert [(s.branch, s.reason) for s in result.skipped] == [("main", "trunk_not_session")]

    def test_규칙B는_실_세션_claim까지_지우지는_않는다(self, bare_remote):
        _, clone = bare_remote
        a, b = clone("session-a"), clone("session-b")
        self._push_trunk(a, "in_progress", "claude/dead-session")
        self._push_session_branch(a, "claude/session-a", "in_progress", "claude/session-a")
        result = remote_claims.scan_remote_in_progress(b, TASK, "claude/session-b")
        assert [h.branch for h in result.holders] == ["claude/session-a"]  # 살아있는 claim은 남는다
        assert [s.branch for s in result.skipped] == ["main"]

    def test_트렁크에_태스크_파일이_없으면_규칙A_신호없이_홀더검사(self, bare_remote):
        # 브랜치에서 신설된 태스크 — 트렁크 사본이 없다고 stale로 오해하면 안 된다
        _, clone = bare_remote
        a, b = clone("session-a"), clone("session-b")
        self._push_session_branch(a, "claude/session-a", "in_progress", "claude/session-a")
        result = remote_claims.scan_remote_in_progress(b, TASK, "claude/session-b")
        assert result.trunk_status == ""
        assert [h.branch for h in result.holders] == ["claude/session-a"]

    def _break_ls_remote(self, monkeypatch):
        """원격 HEAD 조회만 실패시킨다 (fetch·show는 진짜)."""
        original = remote_claims._git

        def fake_git(root, *argv, **kwargs):
            if argv and argv[0] == "ls-remote":
                return subprocess.CompletedProcess(
                    ["git", *argv],
                    128,
                    stdout="",
                    stderr="fatal: unable to access origin: HTTP 403",
                )
            return original(root, *argv, **kwargs)

        monkeypatch.setattr(remote_claims, "_git", fake_git)

    def test_트렁크_ref는_원격_HEAD를_먼저_묻는다(self, bare_remote):
        _, clone = bare_remote
        b = clone("session-b")
        result = remote_claims.scan_remote_in_progress(b, TASK, "claude/session-b")
        assert result.trunk_source == "ls-remote"  # 하드코딩 아님·원격 권위 우선
        assert result.trunk_ref == "refs/remotes/origin/main"

    def test_로컬_origin_HEAD가_stale이어도_원격_권위를_따른다(self, bare_remote):
        """실측 사고 재현(2026-07-27): 로컬 origin/HEAD가 *세션 브랜치*를 가리킨 클론.

        그 값을 트렁크로 믿으면 규칙 A가 남의 세션 브랜치 status를 권위로 삼아
        보호를 조용히 꺼버린다(미탐). 원격 HEAD가 이겨야 한다.
        """
        _, clone = bare_remote
        a, b = clone("session-a"), clone("session-b")
        self._push_trunk(a, "todo")  # 진짜 트렁크: 미착륙
        self._push_session_branch(a, "claude/session-a", "in_progress", "claude/session-a")
        self._push_session_branch(a, "claude/liar", "done", None)  # 착륙했다고 주장하는 사본
        self._run(b, "fetch", "--quiet", "origin", "+refs/heads/*:refs/remotes/origin/*")
        self._run(b, "symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/claude/liar")
        result = remote_claims.scan_remote_in_progress(b, TASK, "claude/session-b")
        assert result.trunk_ref == "refs/remotes/origin/main"
        assert result.trunk_status == "todo"
        assert [h.branch for h in result.holders] == ["claude/session-a"]  # 보호 유지

    def test_원격_HEAD_조회가_막히면_로컬_symbolic_ref로_폴백(self, bare_remote, monkeypatch):
        _, clone = bare_remote
        a, b = clone("session-a"), clone("session-b")
        self._push_trunk(a, "done")
        self._push_session_branch(a, "claude/session-a", "in_progress", "claude/session-a")
        self._break_ls_remote(monkeypatch)
        result = remote_claims.scan_remote_in_progress(b, TASK, "claude/session-b")
        assert result.trunk_source == "symbolic-ref"
        assert result.holders == []  # 규칙 A는 그대로 작동

    def test_해소_전부_실패하면_main으로_폴백한다(self, bare_remote, monkeypatch):
        _, clone = bare_remote
        a, b = clone("session-a"), clone("session-b")
        self._push_trunk(a, "done")
        self._push_session_branch(a, "claude/session-a", "in_progress", "claude/session-a")
        self._run(b, "symbolic-ref", "--delete", "refs/remotes/origin/HEAD")
        self._break_ls_remote(monkeypatch)
        result = remote_claims.scan_remote_in_progress(b, TASK, "claude/session-b")
        assert result.trunk_source == "fallback"
        assert result.trunk_ref == "refs/remotes/origin/main"
        assert result.holders == []


class TestStaleAndReap:
    def test_stale_3중_기준(self):
        now = datetime(2026, 7, 16, 12, 0, tzinfo=timezone.utc)
        fresh_ts = "2026-07-16T10:00:00Z"  # 2시간 전 — TTL(72h) 이내
        old_ts = "2026-07-10T10:00:00Z"  # 6일 전 — TTL 초과
        claims = [
            remote_claims.RemoteClaim(TASK, "sha1", "claude/a", fresh_ts),
            remote_claims.RemoteClaim("S1-02-done-task", "sha2", "claude/b", fresh_ts),
            remote_claims.RemoteClaim("S1-03-ghost-task", "sha3", "claude/c", fresh_ts),
            remote_claims.RemoteClaim("S1-04-old-task", "sha4", "claude/d", old_ts),
        ]
        backlog = _mk_backlog()
        backlog.tasks["S1-02-done-task"] = Task(
            id="S1-02-done-task",
            title="완료됨",
            track="math-completion",
            stage="S1",
            status="done",
            artifacts=["PR#1"],
        )
        backlog.tasks["S1-04-old-task"] = Task(
            id="S1-04-old-task",
            title="오래됨",
            track="math-completion",
            stage="S1",
            status="in_progress",
            session="claude/d",
        )
        stale = remote_claims.stale_claims(claims, backlog, ttl_hours=72, now=now)
        reasons = {c.task_id: reason for c, reason in stale}
        assert TASK not in reasons  # 신선 + in_progress → 유지
        assert reasons["S1-02-done-task"] == "task_done"  # 로컬 이미 done
        assert reasons["S1-03-ghost-task"] == "task_missing"  # 태스크 미존재
        assert reasons["S1-04-old-task"] == "ttl"  # TTL 초과

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
