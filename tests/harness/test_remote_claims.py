"""remote_claims.py — 원격 claim(harness-claims 브랜치) CAS 원자성·폴백·청소 테스트.

가짜 git이 아니라 진짜 로컬 bare 원격으로 병렬 세션 레이스를 재현한다 — 시임이면
`--force-with-lease`의 서버측 트랜잭션을 검증할 수 없고, 그게 이 모듈의 존재 이유다.
"""

from __future__ import annotations

import subprocess
from datetime import datetime, timedelta, timezone
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
    def test_claim_success_creates_remote_ref(self, bare_remote):
        """claim_성공_후_ls_remote에_ref_존재"""
        _, clone = bare_remote
        a = clone("session-a")
        result = remote_claims.claim(a, TASK, "claude/session-a")
        assert result.status == "ok"
        claims, status = remote_claims.list_claims(a, with_meta=True)
        assert status == "ok"
        assert [c.task_id for c in claims] == [TASK]
        assert claims[0].branch == "claude/session-a"
        assert claims[0].ts  # UTC ISO8601 타임스탬프 기록됨

    def test_race_only_one_of_two_sessions_succeeds(self, bare_remote):
        """레이스_두_세션_중_한쪽만_성공"""
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

    def test_reclaim_possible_after_release(self, bare_remote):
        """release_후_재claim_가능"""
        _, clone = bare_remote
        a = clone("session-a")
        b = clone("session-b")
        assert remote_claims.claim(a, TASK, "claude/session-a").status == "ok"
        assert remote_claims.release(a, TASK, "claude/session-a").status == "ok"
        assert remote_claims.claim(b, TASK, "claude/session-b").status == "ok"

    def test_different_tasks_claim_independently(self, bare_remote):
        """서로_다른_태스크는_독립_claim"""
        _, clone = bare_remote
        a = clone("session-a")
        b = clone("session-b")
        assert remote_claims.claim(a, TASK, "claude/session-a").status == "ok"
        assert remote_claims.claim(b, "S1-02-other-task", "claude/session-b").status == "ok"

    # ── HARN-09 — 단일 브랜치 레이아웃이 새로 만든 계약 ────────────────────────

    def test_contention_different_tasks_both_survive(self, bare_remote):
        """경합해도_서로_다른_태스크는_둘_다_살아남는다

        lease 경합 재시도가 **기능을 죽이지 않는다**.

        단일 브랜치라 서로 다른 태스크를 claim해도 같은 ref를 갱신한다. 재시도가 없으면
        경합한 쪽이 실패하고 "한 번에 한 세션만 claim 가능"이라는 치명적 퇴행이 된다.

        ⚠️ **진짜 경합을 만들어야 한다**: 순차 호출은 매번 최신 base를 fetch하므로
        lease가 절대 깨지지 않는다(초안이 그랬고, `CAS_RETRIES=1` 돌연변이를 못 잡아
        무효 검사임이 드러났다). 그래서 B가 base를 읽은 *뒤* push하기 *직전*에 A를
        끼워넣어 B의 lease를 강제로 낡게 만든다.
        """
        _, clone = bare_remote
        a = clone("session-a")
        b = clone("session-b")

        original_push = remote_claims._push_claims
        attempts: list[str] = []

        def racing_push(root, base_sha, commit_sha):
            attempts.append(base_sha)
            if len(attempts) == 1:
                # B가 base를 읽은 뒤 push하기 직전에 A가 먼저 착륙 → B의 lease는 낡는다
                remote_claims._push_claims = original_push
                assert remote_claims.claim(a, TASK, "claude/session-a").status == "ok"
                remote_claims._push_claims = racing_push
            return original_push(root, base_sha, commit_sha)

        remote_claims._push_claims = racing_push
        try:
            result = remote_claims.claim(b, "S1-02-other-task", "claude/session-b")
        finally:
            remote_claims._push_claims = original_push

        assert result.status == "ok", f"lease 경합에서 재시도가 실패했다: {result.message}"
        assert len(attempts) >= 2, "경합이 재현되지 않았다 — 이 테스트는 재시도를 검증하지 못한다"
        claims, status = remote_claims.list_claims(a)
        assert status == "ok"
        assert {c.task_id for c in claims} == {TASK, "S1-02-other-task"}, "경합이 claim을 삼켰다"

    def test_claim_does_not_touch_worktree_or_index(self, bare_remote):
        """claim은_작업트리와_인덱스를_건드리지_않는다

        트리를 `mktree`로 만드는 이유 — 인덱스를 쓰면 사용자 스테이징이 오염된다.

        하네스는 개발자가 편집 중인 클론에서 그대로 돈다. claim 하나가 스테이징을
        흔들면 그건 도구가 아니라 사고다.
        """
        _, clone = bare_remote
        a = clone("session-a")
        # 스테이징된 것 *과* 스테이징되지 않은 것을 **둘 다** 만든다.
        # 스테이징만 있으면 `git add -A` 류의 오염이 무변화로 보여 검사가 무효가 된다
        # (초안이 그랬고 돌연변이를 못 잡았다). 미스테이징 파일이 있어야 변별력이 산다.
        (a / "스테이징됨.txt").write_text("staged", encoding="utf-8")
        subprocess.run(["git", "add", "스테이징됨.txt"], cwd=a, check=True, capture_output=True)
        (a / "미스테이징.txt").write_text("untracked", encoding="utf-8")
        before = subprocess.run(
            ["git", "status", "--porcelain"], cwd=a, capture_output=True, text=True
        ).stdout
        assert "??" in before, "미스테이징 상태가 만들어지지 않으면 이 검사는 변별력이 없다"

        assert remote_claims.claim(a, TASK, "claude/session-a").status == "ok"
        assert remote_claims.release(a, TASK, "claude/session-a").status == "ok"

        after = subprocess.run(
            ["git", "status", "--porcelain"], cwd=a, capture_output=True, text=True
        ).stdout
        assert after == before, f"claim/release가 작업트리를 오염시켰다:\n{before!r} → {after!r}"

    def test_release_does_not_use_ref_deletion(self, bare_remote):
        """해제는_ref_삭제를_쓰지_않는다

        이 환경의 프록시가 ref 삭제를 거부하므로 삭제 push는 설계상 금지다.

        구현이 삭제 push로 회귀하면 실 환경에서만 조용히 깨진다(로컬 bare 원격은
        삭제를 허용하므로 이 테스트 없이는 안 잡힌다) — 그래서 명령을 직접 감시한다.
        """
        _, clone = bare_remote
        a = clone("session-a")
        assert remote_claims.claim(a, TASK, "claude/session-a").status == "ok"

        original = remote_claims._git
        seen: list[tuple[str, ...]] = []

        def spy_git(root, *argv, **kwargs):
            seen.append(argv)
            return original(root, *argv, **kwargs)

        remote_claims._git = spy_git
        try:
            assert remote_claims.release(a, TASK, "claude/session-a").status == "ok"
        finally:
            remote_claims._git = original

        deletions = [
            argv
            for argv in seen
            if argv and argv[0] == "push" and any(a_.startswith(":") for a_ in argv)
        ]
        assert not deletions, f"삭제 push가 쓰였다 — 실 프록시에서 거부된다: {deletions}"
        claims, status = remote_claims.list_claims(a)
        assert status == "ok" and claims == []

    def test_missing_claim_branch_not_mistaken_for_query_failure(self, bare_remote):
        """claim_브랜치_부재가_조회_실패로_오인되지_않는다

        claim 0건은 정상 상태다 — ok로 보고돼야 후속 로직이 진행된다.
        """
        _, clone = bare_remote
        a = clone("session-a")
        claims, status = remote_claims.list_claims(a)
        assert claims == [] and status == "ok"

    def test_corrupted_meta_claim_not_silently_hijacked(self, bare_remote, monkeypatch):
        """메타가_파손된_claim은_조용히_탈취되지_않는다

        홀더를 특정 못 해도 **통과가 아니라 conflict**다.

        "누가 잡았는지 모르니 일단 진행"은 조용한 탈취이고, 그게 이 모듈이 막으려는
        바로 그 사고(OPS-07·OPS-12 병렬 중복 구현)다. 복구는 --force로 명시한다.
        """
        _, clone = bare_remote
        a = clone("session-a")
        b = clone("session-b")
        assert remote_claims.claim(a, TASK, "claude/session-a").status == "ok"

        # 메타 파손 재현 — 브랜치 필드를 읽을 수 없는 상태
        original_read = remote_claims._read_claims

        def corrupt_read(root, base_sha):
            claims = original_read(root, base_sha)
            for c in claims:
                c.branch = ""
                c.meta = None
            return claims

        monkeypatch.setattr(remote_claims, "_read_claims", corrupt_read)
        result = remote_claims.claim(b, TASK, "claude/session-b")
        assert result.status == "conflict", "홀더 불명이 통과로 이어지면 조용한 탈취다"
        assert "--force" in result.message, "복구 경로를 안내해야 막힌 채로 남지 않는다"


class TestReleaseSafety:
    def test_releasing_others_claim_requires_force(self, bare_remote):
        """남의_claim_해제는_force_필수"""
        _, clone = bare_remote
        a = clone("session-a")
        b = clone("session-b")
        assert remote_claims.claim(a, TASK, "claude/session-a").status == "ok"
        denied = remote_claims.release(b, TASK, "claude/session-b")
        assert denied.status == "error"
        assert "force" in denied.message
        forced = remote_claims.release(b, TASK, "claude/session-b", force=True)
        assert forced.status == "ok"

    def test_release_of_nonexistent_claim_is_idempotent(self, bare_remote):
        """없는_claim_해제는_멱등"""
        _, clone = bare_remote
        a = clone("session-a")
        assert remote_claims.release(a, TASK, "claude/session-a").status == "ok"


class TestFailOpen:
    def test_repo_without_remote_is_offline(self, git_repo: Path):
        """원격_없는_저장소는_offline"""
        result = remote_claims.claim(git_repo, TASK, "claude/x")
        assert result.status == "offline"

    def test_dead_remote_returns_offline_or_error_never_raises(self, git_repo: Path, tmp_path):
        """죽은_원격은_offline_또는_error_절대_예외_아님"""
        import subprocess

        subprocess.run(
            ["git", "remote", "add", "origin", str(tmp_path / "no-such-repo.git")],
            cwd=git_repo,
            check=True,
            capture_output=True,
        )
        result = remote_claims.claim(git_repo, TASK, "claude/x")
        assert result.status in ("offline", "error")

    def test_list_claims_without_remote_is_offline(self, git_repo: Path):
        """list_claims_원격_없으면_offline"""
        claims, status = remote_claims.list_claims(git_repo)
        assert claims == []
        assert status == "offline"


class TestTopLevelFieldParser:
    """태스크 YAML 최상위 스칼라 파서 — PyYAML 비의존 (하네스 의존성 0 설계)."""

    def test_parses_real_dump_task_format(self):
        """실제_dump_task_형식을_읽는다"""
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

    def test_null_session_yields_empty_string(self):
        """null_세션은_빈_문자열"""
        body = "id: X\nstatus: todo\nsession: null\n"
        assert remote_claims._top_level_field(body, "session") == ""

    def test_strips_quotes_from_quoted_value(self):
        """인용된_값의_따옴표를_벗긴다"""
        body = 'status: "in_progress"\nsession: "claude/a-b"\n'
        assert remote_claims._top_level_field(body, "session") == "claude/a-b"

    def test_ignores_indented_lines_and_colons_inside_values(self):
        """들여쓰기된_줄과_값_속_콜론에_속지_않는다"""
        # notes 값 안의 'status: in_progress'와 리스트 항목이 최상위로 오인되면 안 된다
        body = (
            "status: todo\n"
            'notes: "이전 세션에서 status: in_progress 였음"\n'
            'acceptance:\n  - "status: in_progress 금지"\n'
        )
        assert remote_claims._top_level_field(body, "status") == "todo"

    def test_missing_key_yields_empty_string(self):
        """없는_키는_빈_문자열"""
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

    def test_detects_other_session_in_progress(self, bare_remote):
        """타_세션_in_progress를_탐지한다"""
        _, clone = bare_remote
        a, b = clone("session-a"), clone("session-b")
        self._push_task_copy(a, "claude/session-a", "in_progress", "claude/session-a")
        result = remote_claims.scan_remote_in_progress(b, TASK, "claude/session-b")
        assert result.status == "ok"
        assert [(h.branch, h.session) for h in result.holders] == [
            ("claude/session-a", "claude/session-a")
        ]

    def test_own_session_in_progress_does_not_block_self(self, bare_remote):
        """내_세션의_in_progress는_나를_막지_않는다"""
        _, clone = bare_remote
        a, b = clone("session-a"), clone("session-b")
        # 원격에 남은 claim의 session이 '나'인 경우 (내 브랜치를 이미 push한 상태)
        self._push_task_copy(a, "claude/session-b", "in_progress", "claude/session-b")
        result = remote_claims.scan_remote_in_progress(b, TASK, "claude/session-b")
        assert result.status == "ok"
        assert result.holders == []

    def test_todo_status_is_not_detected(self, bare_remote):
        """todo_상태는_탐지하지_않는다"""
        _, clone = bare_remote
        a, b = clone("session-a"), clone("session-b")
        self._push_task_copy(a, "claude/session-a", "todo", None)
        result = remote_claims.scan_remote_in_progress(b, TASK, "claude/session-b")
        assert result.status == "ok"
        assert result.holders == []

    def test_branch_without_task_file_skipped(self, bare_remote):
        """태스크_파일이_없는_브랜치는_건너뛴다"""
        _, clone = bare_remote
        _, b = clone("session-a"), clone("session-b")
        # main에는 backlog/ 자체가 없다 — 예외 없이 조용히 넘어가야 한다
        result = remote_claims.scan_remote_in_progress(b, TASK, "claude/session-b")
        assert result.status == "ok"
        assert result.holders == []
        assert result.scanned_refs >= 1

    def test_ignores_claims_for_different_task(self, bare_remote):
        """다른_태스크의_claim에는_반응하지_않는다"""
        _, clone = bare_remote
        a, b = clone("session-a"), clone("session-b")
        self._push_task_copy(
            a, "claude/session-a", "in_progress", "claude/session-a", task_id="S1-99-other-task"
        )
        result = remote_claims.scan_remote_in_progress(b, TASK, "claude/session-b")
        assert result.status == "ok"
        assert result.holders == []

    def test_scan_without_remote_is_offline(self, git_repo: Path):
        """원격_없으면_offline_판정불가"""
        result = remote_claims.scan_remote_in_progress(git_repo, TASK, "claude/x")
        assert result.status == "offline"
        assert result.holders == []  # 빈 holders를 '충돌 없음'으로 읽으면 안 된다

    def test_fetch_failure_reported_as_status_not_exception(self, bare_remote, monkeypatch):
        """fetch_실패는_상태로_보고되고_예외가_아니다"""
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

    def test_exceeding_branch_cap_reports_truncated(self, bare_remote):
        """브랜치_상한_초과는_truncated로_보고된다"""
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

    def test_rule_a_trunk_done_excludes_holder_as_stale(self, bare_remote):
        """규칙A_트렁크가_done이면_홀더는_stale로_제외된다"""
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

    def test_rule_a_inverse_trunk_todo_still_blocks(self, bare_remote):
        """규칙A_역_트렁크가_todo면_여전히_차단한다"""
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

    def test_rule_a_trunk_cancelled_counts_as_landed(self, bare_remote):
        """규칙A_cancelled도_착륙으로_본다"""
        _, clone = bare_remote
        a, b = clone("session-a"), clone("session-b")
        self._push_trunk(a, "cancelled")
        self._push_session_branch(a, "claude/session-a", "in_progress", "claude/session-a")
        result = remote_claims.scan_remote_in_progress(b, TASK, "claude/session-b")
        assert result.holders == []
        assert [s.reason for s in result.skipped] == ["trunk_cancelled"]

    def test_rule_b_trunk_itself_cannot_be_holder(self, bare_remote):
        """규칙B_트렁크_자신은_홀더가_될_수_없다"""
        # main의 in_progress는 활성 claim이 아니라 대장 위생 실패(done 미기입 머지)다
        _, clone = bare_remote
        a, b = clone("session-a"), clone("session-b")
        self._push_trunk(a, "in_progress", "claude/dead-session")
        result = remote_claims.scan_remote_in_progress(b, TASK, "claude/session-b")
        assert result.status == "ok"
        assert result.holders == []
        assert [(s.branch, s.reason) for s in result.skipped] == [("main", "trunk_not_session")]

    def test_rule_b_does_not_erase_real_session_claims(self, bare_remote):
        """규칙B는_실_세션_claim까지_지우지는_않는다"""
        _, clone = bare_remote
        a, b = clone("session-a"), clone("session-b")
        self._push_trunk(a, "in_progress", "claude/dead-session")
        self._push_session_branch(a, "claude/session-a", "in_progress", "claude/session-a")
        result = remote_claims.scan_remote_in_progress(b, TASK, "claude/session-b")
        assert [h.branch for h in result.holders] == ["claude/session-a"]  # 살아있는 claim은 남는다
        assert [s.branch for s in result.skipped] == ["main"]

    def test_missing_trunk_task_file_falls_back_to_holder_check(self, bare_remote):
        """트렁크에_태스크_파일이_없으면_규칙A_신호없이_홀더검사"""
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

    def test_trunk_ref_queries_remote_head_first(self, bare_remote):
        """트렁크_ref는_원격_HEAD를_먼저_묻는다"""
        _, clone = bare_remote
        b = clone("session-b")
        result = remote_claims.scan_remote_in_progress(b, TASK, "claude/session-b")
        assert result.trunk_source == "ls-remote"  # 하드코딩 아님·원격 권위 우선
        assert result.trunk_ref == "refs/remotes/origin/main"

    def test_stale_local_origin_head_defers_to_remote_authority(self, bare_remote):
        """로컬_origin_HEAD가_stale이어도_원격_권위를_따른다

        실측 사고 재현(2026-07-27): 로컬 origin/HEAD가 *세션 브랜치*를 가리킨 클론.

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

    def test_blocked_remote_head_query_falls_back_to_local_symbolic_ref(
        self, bare_remote, monkeypatch
    ):
        """원격_HEAD_조회가_막히면_로컬_symbolic_ref로_폴백"""
        _, clone = bare_remote
        a, b = clone("session-a"), clone("session-b")
        self._push_trunk(a, "done")
        self._push_session_branch(a, "claude/session-a", "in_progress", "claude/session-a")
        self._break_ls_remote(monkeypatch)
        result = remote_claims.scan_remote_in_progress(b, TASK, "claude/session-b")
        assert result.trunk_source == "symbolic-ref"
        assert result.holders == []  # 규칙 A는 그대로 작동

    def test_all_resolution_failure_falls_back_to_main(self, bare_remote, monkeypatch):
        """해소_전부_실패하면_main으로_폴백한다"""
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
    def test_stale_triple_criteria(self):
        """stale_3중_기준 + task_missing_recent 4번째 사유(HARN-21)"""
        now = datetime(2026, 7, 16, 12, 0, tzinfo=timezone.utc)
        fresh_ts = "2026-07-16T10:00:00Z"  # 2시간 전 — TTL(72h) 이내
        old_ts = "2026-07-10T10:00:00Z"  # 6일 전 — TTL 초과
        claims = [
            remote_claims.RemoteClaim(TASK, "sha1", "claude/a", fresh_ts),
            remote_claims.RemoteClaim("S1-02-done-task", "sha2", "claude/b", fresh_ts),
            remote_claims.RemoteClaim("S1-03-ghost-task", "sha3", "claude/c", fresh_ts),
            remote_claims.RemoteClaim("S1-04-old-task", "sha4", "claude/d", old_ts),
            # HARN-21 신규 — 오래된 missing claim(진짜 정리 대상)과
            # ts 없는 missing claim(나이 불명 → 보수적 보류) 두 축 추가.
            remote_claims.RemoteClaim("S1-05-old-ghost-task", "sha5", "claude/e", old_ts),
            remote_claims.RemoteClaim("S1-06-no-ts-ghost-task", "sha6", "claude/f", ""),
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
        # HARN-21 결함③ 수정: 신선한 missing claim은 "task_missing"이 아니라
        # "task_missing_recent"(경합 조건 가능성 — 즉시 삭제 금지).
        assert reasons["S1-03-ghost-task"] == "task_missing_recent"
        assert reasons["S1-04-old-task"] == "ttl"  # TTL 초과
        assert reasons["S1-05-old-ghost-task"] == "task_missing"  # 오래된 missing은 여전히 정리
        assert reasons["S1-06-no-ts-ghost-task"] == "task_missing_recent"  # ts 없음 = 보수적 보류

    def test_reap_dry_run_does_not_delete(self, bare_remote, monkeypatch):
        """reap_dry_run은_삭제하지_않는다 — 오래된(TTL 초과) claim 기준"""
        _, clone = bare_remote
        a = clone("session-a")
        old_ts = datetime(2026, 1, 1, tzinfo=timezone.utc)
        monkeypatch.setattr(remote_claims, "_utcnow", lambda: old_ts)
        assert remote_claims.claim(a, "S1-03-ghost-task", "claude/session-a").status == "ok"
        later_now = old_ts + timedelta(hours=200)  # TTL(72h) 초과 — 진짜 stale
        monkeypatch.setattr(remote_claims, "_utcnow", lambda: later_now)
        backlog = _mk_backlog()  # ghost-task 미포함 + 오래됨 → task_missing
        reaped, status, warnings = remote_claims.reap(a, backlog, ttl_hours=72, dry_run=True)
        assert status == "ok"
        assert len(reaped) == 1 and "task_missing" in reaped[0]
        assert "task_missing_recent" not in reaped[0]
        assert warnings == []
        claims, _ = remote_claims.list_claims(a)
        assert len(claims) == 1  # dry-run — 아직 남아 있음

    def test_reap_apply_actually_deletes(self, bare_remote, monkeypatch):
        """reap_apply는_실제_삭제 — 오래된(TTL 초과) claim 기준"""
        _, clone = bare_remote
        a = clone("session-a")
        old_ts = datetime(2026, 1, 1, tzinfo=timezone.utc)
        monkeypatch.setattr(remote_claims, "_utcnow", lambda: old_ts)
        assert remote_claims.claim(a, "S1-03-ghost-task", "claude/session-a").status == "ok"
        later_now = old_ts + timedelta(hours=200)  # TTL(72h) 초과 — 진짜 stale
        monkeypatch.setattr(remote_claims, "_utcnow", lambda: later_now)
        backlog = _mk_backlog()
        reaped, status, warnings = remote_claims.reap(a, backlog, ttl_hours=72, dry_run=False)
        assert status == "ok" and len(reaped) == 1
        assert warnings == []
        claims, _ = remote_claims.list_claims(a)
        assert claims == []

    def test_query_failure_not_disguised_as_no_stale(self, bare_remote, monkeypatch):
        """조회_실패는_stale_없음으로_위장되지_않는다

        HARN-09 — 이 구분이 없어서 CI 교차검증이 공전했다.

        구 구현은 조회 실패 시 빈 목록만 돌려줬고, 호출자는 그것을 "stale 없음"과
        구별할 수 없었다. 인프라가 죽으면 "측정 실패"가 보여야지 "0건 통과"로
        위장되면 안 된다(CLAUDE.md AI·신뢰).
        """
        _, clone = bare_remote
        a = clone("session-a")
        assert remote_claims.claim(a, "S1-03-ghost-task", "claude/session-a").status == "ok"
        original = remote_claims._git

        def fake_git(root, *argv, **kwargs):
            if argv and argv[0] == "ls-remote":
                return subprocess.CompletedProcess(
                    argv, 128, stdout="", stderr="fatal: unable to access 'origin'"
                )
            return original(root, *argv, **kwargs)

        monkeypatch.setattr(remote_claims, "_git", fake_git)
        reaped, status, warnings = remote_claims.reap(a, _mk_backlog(), ttl_hours=72, dry_run=True)
        assert reaped == []
        assert warnings == []
        assert status != "ok", "조회 실패가 ok로 보고되면 '0건 통과' 위장이 된다"


class TestTaskMissingRecentRaceGuard:
    """HARN-21 결함③ — 신선한 missing claim은 reap에서 제외되고, 오래된 것은 여전히
    정리된다. 실제 `bare_remote`(진짜 로컬 원격)로 양방향(변별력)을 hermetic하게 검증.

    사고 시나리오: 세션 A가 add+start(claim)를 원격에 방금 반영했는데, 그 직후 세션 B가
    `claims reap --apply`를 돌리면 — B의 로컬 클론엔 A가 방금 추가한 태스크 파일이 아직
    없다(A가 아직 안 머지했으므로). `task is None`이 참이 되어 나이와 무관하게 즉시
    task_missing으로 지워지던 것이 구 버그다.
    """

    def test_freshly_created_claim_not_reaped_when_task_missing_locally(
        self, bare_remote, monkeypatch
    ):
        """방금_생성된_claim은_로컬에_태스크가_없어도_reap_안_됨"""
        _, clone = bare_remote
        a = clone("session-a")
        fixed_now = datetime(2026, 8, 10, 15, 0, tzinfo=timezone.utc)
        monkeypatch.setattr(remote_claims, "_utcnow", lambda: fixed_now)
        assert remote_claims.claim(a, "HARN-99-race-task", "claude/session-a").status == "ok"

        backlog = _mk_backlog()  # HARN-99-race-task 미포함 → A가 아직 안 머지한 상태 모사
        reaped, status, warnings = remote_claims.reap(a, backlog, ttl_hours=72, dry_run=False)
        assert status == "ok"
        assert reaped == [], "방금 생성된 claim이 task_missing으로 즉시 reap되면 안 된다"
        assert any(
            "HARN-99-race-task" in w and "task_missing_recent" in w for w in warnings
        ), "삭제하지 않되 경고로는 노출해야 한다(침묵 실패 금지)"
        claims, _ = remote_claims.list_claims(a)
        assert [c.task_id for c in claims] == ["HARN-99-race-task"], "claim이 살아있어야 한다"

    def test_old_claim_still_reaped_as_task_missing(self, bare_remote, monkeypatch):
        """오래된_claim은_여전히_task_missing으로_reap된다 — 변별력의 반대 축

        진짜 취소·삭제된 태스크의 잔존 claim을 정리하는 정상 기능은 유지해야 한다.
        """
        _, clone = bare_remote
        a = clone("session-a")
        old_ts = datetime(2026, 8, 1, 9, 0, tzinfo=timezone.utc)
        monkeypatch.setattr(remote_claims, "_utcnow", lambda: old_ts)
        assert remote_claims.claim(a, "HARN-98-stale-task", "claude/session-a").status == "ok"

        later_now = old_ts + timedelta(hours=100)  # TTL(72h) 초과
        monkeypatch.setattr(remote_claims, "_utcnow", lambda: later_now)
        backlog = _mk_backlog()  # HARN-98-stale-task 미존재(진짜 삭제된 태스크 모사)
        reaped, status, warnings = remote_claims.reap(a, backlog, ttl_hours=72, dry_run=False)
        assert status == "ok"
        assert len(reaped) == 1
        assert "HARN-98-stale-task" in reaped[0] and "task_missing" in reaped[0]
        assert "task_missing_recent" not in reaped[0]
        assert warnings == []
        claims, _ = remote_claims.list_claims(a)
        assert claims == [], "오래된 claim은 실제로 삭제돼야 한다"


class TestScanStaleBranches:
    """장기 미머지 브랜치 감지 (HARN-13) — 진짜 로컬 원격에서 커밋 나이·ahead count 실측.

    2026-07-30 사고(claude/shadow-data-s3-pilot-nh5kbz 9일·40+커밋 고립)의 재발방지
    메커니즘. 변별력의 핵심은 "오래됐지만 이미 머지된 브랜치"와 "오래됐고 아직
    안 흡수된 브랜치"를 다른 값으로 구분하는가다 — 나이만 보고 ahead를 안 보면
    머지된 브랜치도 계속 stale로 오탐한다.
    """

    def _commit_backdated(self, repo: Path, days_ago: int, filename: str, message: str) -> None:
        """`days_ago`일 전 committerdate로 파일 1건을 커밋한다(나이 축 통제 실측용)."""
        (repo / filename).write_text(f"{message}\n", encoding="utf-8")
        past = datetime.now(timezone.utc) - timedelta(days=days_ago)
        iso = past.strftime("%Y-%m-%dT%H:%M:%S+00:00")
        env = {
            "GIT_AUTHOR_DATE": iso,
            "GIT_COMMITTER_DATE": iso,
        }
        subprocess.run(["git", "add", filename], cwd=repo, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", message],
            cwd=repo,
            check=True,
            capture_output=True,
            env={**_os_environ(), **env},
        )

    def test_detects_old_and_ahead_branch(self, bare_remote):
        """오래되고_ahead인_브랜치를_감지한다"""
        _, clone = bare_remote
        a, b = clone("session-a"), clone("session-b")
        subprocess.run(
            ["git", "checkout", "-b", "claude/old-orphan"], cwd=a, check=True, capture_output=True
        )
        self._commit_backdated(a, days_ago=9, filename="orphan.txt", message="orphan work")
        subprocess.run(
            ["git", "push", "-u", "origin", "claude/old-orphan"],
            cwd=a,
            check=True,
            capture_output=True,
        )
        result = remote_claims.scan_stale_branches(b, days_threshold=3)
        assert result.status == "ok"
        branches = {s.branch: s for s in result.stale}
        assert "claude/old-orphan" in branches
        assert branches["claude/old-orphan"].ahead >= 1
        assert branches["claude/old-orphan"].age_days >= 9
        # 포팅 근거도 active claim도 없으면 기본값 unresolved (2026-08-05 3분류 확장)
        assert branches["claude/old-orphan"].status == "unresolved"
        assert branches["claude/old-orphan"].evidence == ""

    def test_recently_committed_branch_not_detected(self, bare_remote):
        """최근_커밋된_브랜치는_감지하지_않는다

        나이 조건 미충족 — ahead는 있지만 threshold 미만이면 stale이 아니다.
        """
        _, clone = bare_remote
        a, b = clone("session-a"), clone("session-b")
        subprocess.run(
            ["git", "checkout", "-b", "claude/fresh"], cwd=a, check=True, capture_output=True
        )
        (a / "fresh.txt").write_text("fresh\n", encoding="utf-8")
        subprocess.run(["git", "add", "fresh.txt"], cwd=a, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "fresh work"], cwd=a, check=True, capture_output=True
        )
        subprocess.run(
            ["git", "push", "-u", "origin", "claude/fresh"], cwd=a, check=True, capture_output=True
        )
        result = remote_claims.scan_stale_branches(b, days_threshold=3)
        assert result.status == "ok"
        assert "claude/fresh" not in {s.branch for s in result.stale}

    def test_branch_absorbed_into_trunk_not_detected(self, bare_remote):
        """트렁크에_흡수된_브랜치는_감지하지_않는다

        ahead 조건 미충족 — 나이는 오래됐지만 트렁크가 이미 그 커밋을 포함하면 stale이 아니다.

        SQUASH 머지가 아니라 fast-forward로 트렁크에 실제로 흡수시켜, ahead count가
        정확히 0이 되는 경로를 재현한다(scan_remote_in_progress의 규칙 A·B와 동일하게
        조상 관계가 아니라 rev-list count로 판정하는 것을 검증).
        """
        _, clone = bare_remote
        a, b = clone("session-a"), clone("session-b")
        subprocess.run(
            ["git", "checkout", "-b", "claude/landed"], cwd=a, check=True, capture_output=True
        )
        self._commit_backdated(a, days_ago=10, filename="landed.txt", message="landed work")
        subprocess.run(
            ["git", "push", "-u", "origin", "claude/landed"], cwd=a, check=True, capture_output=True
        )
        # main으로 fast-forward 병합 후 push — 트렁크가 이 커밋을 실제로 흡수한다.
        subprocess.run(["git", "checkout", "main"], cwd=a, check=True, capture_output=True)
        subprocess.run(
            ["git", "merge", "--ff-only", "claude/landed"], cwd=a, check=True, capture_output=True
        )
        subprocess.run(["git", "push", "origin", "main"], cwd=a, check=True, capture_output=True)

        result = remote_claims.scan_stale_branches(b, days_threshold=3)
        assert result.status == "ok"
        assert "claude/landed" not in {s.branch for s in result.stale}

    def test_trunk_with_porting_trace_classified_as_ported(self, bare_remote):
        """trunk에_포팅_흔적이_있으면_ported로_분류한다

        PR#705류 패턴("merge: ...(953m1e) 흡수") 재현 — 원본은 결정 대기가 아니다.

        2026-08-05 실측: SessionStart가 경고하던 19개 브랜치 중 10개가 이미 이 패턴으로
        trunk에 흡수된 뒤 원본만 방치돼 있었다 — unresolved와 뭉뚱그리면 Kiki가 매번
        이미 끝난 일까지 다시 훑어야 한다.
        """
        _, clone = bare_remote
        a, b = clone("session-a"), clone("session-b")
        branch = "claude/whymath-example-review-953m1e"
        subprocess.run(["git", "checkout", "-b", branch], cwd=a, check=True, capture_output=True)
        self._commit_backdated(a, days_ago=9, filename="orphan2.txt", message="review work")
        subprocess.run(
            ["git", "push", "-u", "origin", branch], cwd=a, check=True, capture_output=True
        )
        subprocess.run(["git", "checkout", "main"], cwd=a, check=True, capture_output=True)
        (a / "ported.txt").write_text("ported content\n", encoding="utf-8")
        subprocess.run(["git", "add", "ported.txt"], cwd=a, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "merge: 953m1e 유용분 흡수"],
            cwd=a,
            check=True,
            capture_output=True,
        )
        subprocess.run(["git", "push", "origin", "main"], cwd=a, check=True, capture_output=True)

        result = remote_claims.scan_stale_branches(b, days_threshold=3)
        assert result.status == "ok"
        branches = {s.branch: s for s in result.stale}
        assert branch in branches
        assert branches[branch].status == "ported"
        assert "953m1e" in branches[branch].evidence

    def test_remote_claimed_branch_classified_as_active(self, bare_remote):
        """원격_claim_중인_브랜치는_active로_분류한다

        다른 세션이 지금 이 브랜치에서 작업 중이면 방치가 아니라 진행 중인 정상 작업이다.
        """
        _, clone = bare_remote
        a, b = clone("session-a"), clone("session-b")
        branch = "claude/whymath-active-example-aaaaaa"
        subprocess.run(["git", "checkout", "-b", branch], cwd=a, check=True, capture_output=True)
        self._commit_backdated(a, days_ago=9, filename="active.txt", message="active work")
        subprocess.run(
            ["git", "push", "-u", "origin", branch], cwd=a, check=True, capture_output=True
        )

        result = remote_claims.scan_stale_branches(
            b, days_threshold=3, active_branches=frozenset({branch})
        )
        assert result.status == "ok"
        branches = {s.branch: s for s in result.stale}
        assert branch in branches
        assert branches[branch].status == "active"
        assert branches[branch].evidence == ""

    def test_three_classifications_distinguished_in_one_scan(self, bare_remote):
        """세_분류가_한_스캔에서_동시에_구분된다

        unresolved·ported·active가 서로 다른 값으로 동시에 나오는지 변별력 실측.

        각 분류가 개별 테스트에서만 통과하고 한 스캔에서는 서로를 오염시키면(예: 전부
        unresolved로 뭉개짐) 실전에서 무의미하다 — 성공/실패에 같은 값을 내면 검증이
        아니라 위장(CLAUDE.md 변별력 없는 검증 스텝 금지).
        """
        _, clone = bare_remote
        a, b = clone("session-a"), clone("session-b")

        unresolved_branch = "claude/whymath-unresolved-example-zzzzzz"
        ported_branch = "claude/whymath-ported-example-953m1e"
        active_branch = "claude/whymath-active-example-bbbbbb"

        for branch, fname in [
            (unresolved_branch, "u.txt"),
            (ported_branch, "p.txt"),
            (active_branch, "ac.txt"),
        ]:
            subprocess.run(["git", "checkout", "main"], cwd=a, check=True, capture_output=True)
            subprocess.run(
                ["git", "checkout", "-b", branch], cwd=a, check=True, capture_output=True
            )
            self._commit_backdated(a, days_ago=9, filename=fname, message=f"{branch} work")
            subprocess.run(
                ["git", "push", "-u", "origin", branch], cwd=a, check=True, capture_output=True
            )

        subprocess.run(["git", "checkout", "main"], cwd=a, check=True, capture_output=True)
        (a / "port_commit.txt").write_text("ported\n", encoding="utf-8")
        subprocess.run(["git", "add", "port_commit.txt"], cwd=a, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "merge: 953m1e 흡수"], cwd=a, check=True, capture_output=True
        )
        subprocess.run(["git", "push", "origin", "main"], cwd=a, check=True, capture_output=True)

        result = remote_claims.scan_stale_branches(
            b, days_threshold=3, active_branches=frozenset({active_branch})
        )
        assert result.status == "ok"
        branches = {s.branch: s.status for s in result.stale}
        assert branches[unresolved_branch] == "unresolved"
        assert branches[ported_branch] == "ported"
        assert branches[active_branch] == "active"

    def test_no_remote_is_offline_determination(self, git_repo: Path):
        """원격_없음은_offline_판정

        origin이 아예 없는 저장소 — '방치 브랜치 없음'이 아니라 offline이어야 한다.
        """
        result = remote_claims.scan_stale_branches(git_repo, days_threshold=3)
        assert result.status == "offline"
        assert result.stale == []

    def test_query_failure_not_disguised_as_empty_list(self, bare_remote, monkeypatch):
        """조회_실패는_빈_목록으로_위장되지_않는다

        fetch 실패가 '방치 브랜치 0건'과 같은 값이면 인프라 장애가 "문제 없음"으로 읽힌다.
        """
        _, clone = bare_remote
        a = clone("session-a")
        original = remote_claims._git

        def fake_git(root, *argv, **kwargs):
            if argv and argv[0] == "fetch":
                return subprocess.CompletedProcess(
                    argv, 128, stdout="", stderr="fatal: unable to access 'origin'"
                )
            return original(root, *argv, **kwargs)

        monkeypatch.setattr(remote_claims, "_git", fake_git)
        result = remote_claims.scan_stale_branches(a, days_threshold=3)
        assert result.status != "ok"
        assert result.stale == []


class TestScanDocSeriesDuplicates:
    """설계 문서 중복 착수 탐지(HARN-14) — 나이 임계 없이 진짜 로컬 원격에서 실측.

    2026-08-04 사고(claude/whymath-operations-platform-cn6dxi 1일 경과·HARN-13의 3일
    나이 임계 아래라 브리핑에 안 뜸)의 재발방지. 변별력의 핵심은 "이미 SQUASH 머지돼
    트렁크에 실제로 존재하는 파일"과 "트렁크에 없는 진짜 신규 파일"을 다른 값으로
    구분하는가다 — 3점 diff(`A...B`)를 쓰면 전자도 오탐한다(SQUASH는 원 브랜치 커밋을
    트렁크의 조상으로 만들지 않아 merge-base가 머지 이전에 머무르기 때문).
    """

    def _add_doc(self, repo: Path, relpath: str, content: str = "content\n") -> None:
        path = repo / relpath
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        subprocess.run(["git", "add", relpath], cwd=repo, check=True, capture_output=True)

    def test_new_design_doc_branch_detected_regardless_of_age(self, bare_remote):
        """새_설계문서를_추가한_브랜치를_나이_무관하게_감지한다

        방금(0일 전) 만든 브랜치도 즉시 잡혀야 한다 — 이 스캔은 나이 임계가 없다.
        """
        _, clone = bare_remote
        a, b = clone("session-a"), clone("session-b")
        self._add_doc(a, "docs/architecture/foo_gap_review.md", "새 갭 리뷰\n")
        subprocess.run(
            ["git", "commit", "-m", "add foo gap review"],
            cwd=a,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "push", "-u", "origin", "claude/session-a"],
            cwd=a,
            check=True,
            capture_output=True,
        )

        result = remote_claims.scan_doc_series_duplicates(b)
        assert result.status == "ok"
        branches = {c.branch: c for c in result.candidates}
        assert "claude/session-a" in branches
        assert branches["claude/session-a"].files == ("docs/architecture/foo_gap_review.md",)

    def test_non_doc_file_addition_not_detected(self, bare_remote):
        """문서가_아닌_파일_추가는_감지하지_않는다"""
        _, clone = bare_remote
        a, b = clone("session-a"), clone("session-b")
        self._add_doc(a, "src/backend/whymath_backend/ops/foo.py", "# code\n")
        subprocess.run(
            ["git", "commit", "-m", "add unrelated code"], cwd=a, check=True, capture_output=True
        )
        subprocess.run(
            ["git", "push", "-u", "origin", "claude/session-a"],
            cwd=a,
            check=True,
            capture_output=True,
        )

        result = remote_claims.scan_doc_series_duplicates(b)
        assert result.status == "ok"
        assert "claude/session-a" not in {c.branch for c in result.candidates}

    def test_non_review_suffix_under_docs_not_detected(self, bare_remote):
        """docs_안이어도_review_접미어가_아니면_감지하지_않는다"""
        _, clone = bare_remote
        a, b = clone("session-a"), clone("session-b")
        self._add_doc(a, "docs/architecture/foo_notes.md", "무관 문서\n")
        subprocess.run(
            ["git", "commit", "-m", "add unrelated doc"], cwd=a, check=True, capture_output=True
        )
        subprocess.run(
            ["git", "push", "-u", "origin", "claude/session-a"],
            cwd=a,
            check=True,
            capture_output=True,
        )

        result = remote_claims.scan_doc_series_duplicates(b)
        assert result.status == "ok"
        assert "claude/session-a" not in {c.branch for c in result.candidates}

    def test_already_squash_merged_doc_not_false_positive(self, bare_remote):
        """이미_SQUASH_머지된_문서는_오탐하지_않는다

        핵심 회귀 — 3점 diff였다면 이 케이스가 오탐났을 것(설계 중 실측으로 발견).

        브랜치가 신규 문서를 추가해 push한 뒤, 그 브랜치를 SQUASH(비-ff)로 main에
        합치고 origin/main을 갱신한다. 원 브랜치 ref는 원격에 그대로 남는다(GitHub가
        squash 머지 후 브랜치를 자동 삭제하지 않는 한 흔한 상태) — 이 상태에서 스캔이
        그 브랜치를 더 이상 후보로 잡으면 안 된다(파일이 이미 트렁크에 있으므로).
        """
        _, clone = bare_remote
        a, b = clone("session-a"), clone("session-b")
        self._add_doc(a, "docs/architecture/landed_gap_review.md", "머지된 갭 리뷰\n")
        subprocess.run(
            ["git", "commit", "-m", "add landed gap review"], cwd=a, check=True, capture_output=True
        )
        subprocess.run(
            ["git", "push", "-u", "origin", "claude/session-a"],
            cwd=a,
            check=True,
            capture_output=True,
        )

        # session-a에서 SQUASH 머지 시뮬레이션: main으로 체크아웃 후 --squash 병합·새 커밋.
        subprocess.run(["git", "checkout", "main"], cwd=a, check=True, capture_output=True)
        subprocess.run(
            ["git", "merge", "--squash", "claude/session-a"],
            cwd=a,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "squash merge landed gap review"],
            cwd=a,
            check=True,
            capture_output=True,
        )
        subprocess.run(["git", "push", "origin", "main"], cwd=a, check=True, capture_output=True)

        result = remote_claims.scan_doc_series_duplicates(b)
        assert result.status == "ok"
        assert "claude/session-a" not in {
            c.branch for c in result.candidates
        }, "SQUASH 머지로 이미 트렁크에 존재하는 문서가 오탐됨 — 3점 diff 회귀 의심"

    def test_discriminates_unmerged_shown_then_merged_gone(self, bare_remote):
        """변별력_미머지일때_뜨고_머지후_사라진다

        ⑤ — 같은 브랜치가 미머지 상태와 머지 후 상태에서 실제로 다른 값을 낸다.
        """
        _, clone = bare_remote
        a, b = clone("session-a"), clone("session-b")
        self._add_doc(a, "docs/architecture/roundtrip_gap_review.md", "왕복 갭 리뷰\n")
        subprocess.run(
            ["git", "commit", "-m", "add roundtrip gap review"],
            cwd=a,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "push", "-u", "origin", "claude/session-a"],
            cwd=a,
            check=True,
            capture_output=True,
        )

        before = remote_claims.scan_doc_series_duplicates(b)
        assert "claude/session-a" in {c.branch for c in before.candidates}  # 미머지 — 뜬다

        subprocess.run(["git", "checkout", "main"], cwd=a, check=True, capture_output=True)
        subprocess.run(
            ["git", "merge", "--squash", "claude/session-a"],
            cwd=a,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "squash merge roundtrip"],
            cwd=a,
            check=True,
            capture_output=True,
        )
        subprocess.run(["git", "push", "origin", "main"], cwd=a, check=True, capture_output=True)

        after = remote_claims.scan_doc_series_duplicates(b)
        assert "claude/session-a" not in {c.branch for c in after.candidates}  # 머지 후 — 사라진다

    def test_no_remote_is_offline_judgment(self, git_repo: Path):
        """원격_없음은_offline_판정"""
        result = remote_claims.scan_doc_series_duplicates(git_repo)
        assert result.status == "offline"
        assert result.candidates == []

    def test_query_failure_not_disguised_as_empty_list(self, bare_remote, monkeypatch):
        """조회_실패는_빈_목록으로_위장되지_않는다"""
        _, clone = bare_remote
        a = clone("session-a")
        original = remote_claims._git

        def fake_git(root, *argv, **kwargs):
            if argv and argv[0] == "fetch":
                return subprocess.CompletedProcess(
                    argv, 128, stdout="", stderr="fatal: unable to access 'origin'"
                )
            return original(root, *argv, **kwargs)

        monkeypatch.setattr(remote_claims, "_git", fake_git)
        result = remote_claims.scan_doc_series_duplicates(a)
        assert result.status != "ok"
        assert result.candidates == []


def _os_environ() -> dict[str, str]:
    import os

    return dict(os.environ)
