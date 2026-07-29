"""remote_claims.py — 원격 claim(harness-claims 브랜치) CAS 원자성·폴백·청소 테스트.

가짜 git이 아니라 진짜 로컬 bare 원격으로 병렬 세션 레이스를 재현한다 — 시임이면
`--force-with-lease`의 서버측 트랜잭션을 검증할 수 없고, 그게 이 모듈의 존재 이유다.
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
    def test_ref_exists_on_remote_after_successful_claim(self, bare_remote):
        """claim 성공 후 ls remote에 ref 존재."""
        _, clone = bare_remote
        a = clone("session-a")
        result = remote_claims.claim(a, TASK, "claude/session-a")
        assert result.status == "ok"
        claims, status = remote_claims.list_claims(a, with_meta=True)
        assert status == "ok"
        assert [c.task_id for c in claims] == [TASK]
        assert claims[0].branch == "claude/session-a"
        assert claims[0].ts  # UTC ISO8601 타임스탬프 기록됨

    def test_race_lets_only_one_of_two_sessions_win(self, bare_remote):
        """레이스 두 세션 중 한쪽만 성공."""
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

    def test_can_reclaim_after_release(self, bare_remote):
        """release 후 재claim 가능."""
        _, clone = bare_remote
        a = clone("session-a")
        b = clone("session-b")
        assert remote_claims.claim(a, TASK, "claude/session-a").status == "ok"
        assert remote_claims.release(a, TASK, "claude/session-a").status == "ok"
        assert remote_claims.claim(b, TASK, "claude/session-b").status == "ok"

    def test_different_tasks_claim_independently(self, bare_remote):
        """서로 다른 태스크는 독립 claim."""
        _, clone = bare_remote
        a = clone("session-a")
        b = clone("session-b")
        assert remote_claims.claim(a, TASK, "claude/session-a").status == "ok"
        assert remote_claims.claim(b, "S1-02-other-task", "claude/session-b").status == "ok"

    # ── HARN-09 — 단일 브랜치 레이아웃이 새로 만든 계약 ────────────────────────

    def test_contention_keeps_both_claims_for_different_tasks(self, bare_remote):
        """lease 경합 재시도가 **기능을 죽이지 않는다**.

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

    def test_claim_leaves_worktree_and_index_untouched(self, bare_remote):
        """트리를 `mktree`로 만드는 이유 — 인덱스를 쓰면 사용자 스테이징이 오염된다.

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
        """이 환경의 프록시가 ref 삭제를 거부하므로 삭제 push는 설계상 금지다.

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

    def test_missing_claim_branch_is_not_mistaken_for_lookup_failure(self, bare_remote):
        """claim 0건은 정상 상태다 — ok로 보고돼야 후속 로직이 진행된다."""
        _, clone = bare_remote
        a = clone("session-a")
        claims, status = remote_claims.list_claims(a)
        assert claims == [] and status == "ok"

    def test_corrupt_meta_claim_is_not_silently_stolen(self, bare_remote, monkeypatch):
        """홀더를 특정 못 해도 **통과가 아니라 conflict**다.

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
    def test_releasing_another_sessions_claim_requires_force(self, bare_remote):
        """남의 claim 해제는 force 필수."""
        _, clone = bare_remote
        a = clone("session-a")
        b = clone("session-b")
        assert remote_claims.claim(a, TASK, "claude/session-a").status == "ok"
        denied = remote_claims.release(b, TASK, "claude/session-b")
        assert denied.status == "error"
        assert "force" in denied.message
        forced = remote_claims.release(b, TASK, "claude/session-b", force=True)
        assert forced.status == "ok"

    def test_releasing_absent_claim_is_idempotent(self, bare_remote):
        """없는 claim 해제는 멱등."""
        _, clone = bare_remote
        a = clone("session-a")
        assert remote_claims.release(a, TASK, "claude/session-a").status == "ok"


class TestFailOpen:
    def test_repository_without_remote_reports_offline(self, git_repo: Path):
        """원격 없는 저장소는 offline."""
        result = remote_claims.claim(git_repo, TASK, "claude/x")
        assert result.status == "offline"

    def test_dead_remote_reports_offline_or_error_never_raises(self, git_repo: Path, tmp_path):
        """죽은 원격은 offline 또는 error 절대 예외 아님."""
        import subprocess

        subprocess.run(
            ["git", "remote", "add", "origin", str(tmp_path / "no-such-repo.git")],
            cwd=git_repo,
            check=True,
            capture_output=True,
        )
        result = remote_claims.claim(git_repo, TASK, "claude/x")
        assert result.status in ("offline", "error")

    def test_list_claims_reports_offline_without_remote(self, git_repo: Path):
        """list claims 원격 없으면 offline."""
        claims, status = remote_claims.list_claims(git_repo)
        assert claims == []
        assert status == "offline"


class TestTopLevelFieldParser:
    """태스크 YAML 최상위 스칼라 파서 — PyYAML 비의존 (하네스 의존성 0 설계)."""

    def test_reads_the_real_dump_task_format(self):
        """실제 dump task 형식을 읽는다."""
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

    def test_null_session_becomes_empty_string(self):
        """null 세션은 빈 문자열."""
        body = "id: X\nstatus: todo\nsession: null\n"
        assert remote_claims._top_level_field(body, "session") == ""

    def test_strips_quotes_from_quoted_values(self):
        """인용된 값의 따옴표를 벗긴다."""
        body = 'status: "in_progress"\nsession: "claude/a-b"\n'
        assert remote_claims._top_level_field(body, "session") == "claude/a-b"

    def test_not_fooled_by_indented_lines_or_colons_in_values(self):
        """들여쓰기된 줄과 값 속 콜론에 속지 않는다."""
        # notes 값 안의 'status: in_progress'와 리스트 항목이 최상위로 오인되면 안 된다
        body = (
            "status: todo\n"
            'notes: "이전 세션에서 status: in_progress 였음"\n'
            'acceptance:\n  - "status: in_progress 금지"\n'
        )
        assert remote_claims._top_level_field(body, "status") == "todo"

    def test_missing_key_yields_empty_string(self):
        """없는 키는 빈 문자열."""
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

    def test_detects_in_progress_from_another_session(self, bare_remote):
        """타 세션 in progress를 탐지한다."""
        _, clone = bare_remote
        a, b = clone("session-a"), clone("session-b")
        self._push_task_copy(a, "claude/session-a", "in_progress", "claude/session-a")
        result = remote_claims.scan_remote_in_progress(b, TASK, "claude/session-b")
        assert result.status == "ok"
        assert [(h.branch, h.session) for h in result.holders] == [
            ("claude/session-a", "claude/session-a")
        ]

    def test_own_session_in_progress_does_not_block_me(self, bare_remote):
        """내 세션의 in progress는 나를 막지 않는다."""
        _, clone = bare_remote
        a, b = clone("session-a"), clone("session-b")
        # 원격에 남은 claim의 session이 '나'인 경우 (내 브랜치를 이미 push한 상태)
        self._push_task_copy(a, "claude/session-b", "in_progress", "claude/session-b")
        result = remote_claims.scan_remote_in_progress(b, TASK, "claude/session-b")
        assert result.status == "ok"
        assert result.holders == []

    def test_todo_status_is_not_detected(self, bare_remote):
        """todo 상태는 탐지하지 않는다."""
        _, clone = bare_remote
        a, b = clone("session-a"), clone("session-b")
        self._push_task_copy(a, "claude/session-a", "todo", None)
        result = remote_claims.scan_remote_in_progress(b, TASK, "claude/session-b")
        assert result.status == "ok"
        assert result.holders == []

    def test_branch_without_task_file_is_skipped(self, bare_remote):
        """태스크 파일이 없는 브랜치는 건너뛴다."""
        _, clone = bare_remote
        _, b = clone("session-a"), clone("session-b")
        # main에는 backlog/ 자체가 없다 — 예외 없이 조용히 넘어가야 한다
        result = remote_claims.scan_remote_in_progress(b, TASK, "claude/session-b")
        assert result.status == "ok"
        assert result.holders == []
        assert result.scanned_refs >= 1

    def test_does_not_react_to_claims_on_other_tasks(self, bare_remote):
        """다른 태스크의 claim에는 반응하지 않는다."""
        _, clone = bare_remote
        a, b = clone("session-a"), clone("session-b")
        self._push_task_copy(
            a, "claude/session-a", "in_progress", "claude/session-a", task_id="S1-99-other-task"
        )
        result = remote_claims.scan_remote_in_progress(b, TASK, "claude/session-b")
        assert result.status == "ok"
        assert result.holders == []

    def test_without_remote_the_verdict_is_offline(self, git_repo: Path):
        """원격 없으면 offline 판정불가."""
        result = remote_claims.scan_remote_in_progress(git_repo, TASK, "claude/x")
        assert result.status == "offline"
        assert result.holders == []  # 빈 holders를 '충돌 없음'으로 읽으면 안 된다

    def test_fetch_failure_is_reported_as_status_not_raised(self, bare_remote, monkeypatch):
        """fetch 실패는 상태로 보고되고 예외가 아니다."""
        _, clone = bare_remote
        b = clone("session-b")
        original = remote_claims._git

        def fake_git(root, *argv, **kwargs):
            if argv and argv[0] == "fetch" and any("refs/heads" in a for a in argv):
                return subprocess.CompletedProcess(
                    ["git", *argv],
                    128,
                    stdout="",
                    stderr=(
                        "fatal: unable to access 'origin': " "The requested URL returned error: 403"
                    ),
                )
            return original(root, *argv, **kwargs)

        monkeypatch.setattr(remote_claims, "_git", fake_git)
        result = remote_claims.scan_remote_in_progress(b, TASK, "claude/session-b")
        assert result.status in ("offline", "error")
        assert result.holders == []
        assert "403" in result.message  # 침묵 실패 금지 — 원인이 메시지에 남는다

    def test_exceeding_branch_cap_is_reported_as_truncated(self, bare_remote):
        """브랜치 상한 초과는 truncated로 보고된다."""
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

    def test_rule_a_done_on_trunk_marks_holders_stale(self, bare_remote):
        """규칙A 트렁크가 done이면 홀더는 stale로 제외된다."""
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

    def test_rule_a_inverse_todo_on_trunk_still_blocks(self, bare_remote):
        """규칙A 역 트렁크가 todo면 여전히 차단한다."""
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

    def test_rule_a_treats_cancelled_as_landed(self, bare_remote):
        """규칙A cancelled도 착륙으로 본다."""
        _, clone = bare_remote
        a, b = clone("session-a"), clone("session-b")
        self._push_trunk(a, "cancelled")
        self._push_session_branch(a, "claude/session-a", "in_progress", "claude/session-a")
        result = remote_claims.scan_remote_in_progress(b, TASK, "claude/session-b")
        assert result.holders == []
        assert [s.reason for s in result.skipped] == ["trunk_cancelled"]

    def test_rule_b_trunk_itself_cannot_be_a_holder(self, bare_remote):
        """규칙B 트렁크 자신은 홀더가 될 수 없다."""
        # main의 in_progress는 활성 claim이 아니라 대장 위생 실패(done 미기입 머지)다
        _, clone = bare_remote
        a, b = clone("session-a"), clone("session-b")
        self._push_trunk(a, "in_progress", "claude/dead-session")
        result = remote_claims.scan_remote_in_progress(b, TASK, "claude/session-b")
        assert result.status == "ok"
        assert result.holders == []
        assert [(s.branch, s.reason) for s in result.skipped] == [("main", "trunk_not_session")]

    def test_rule_b_does_not_erase_live_session_claims(self, bare_remote):
        """규칙B는 실 세션 claim까지 지우지는 않는다."""
        _, clone = bare_remote
        a, b = clone("session-a"), clone("session-b")
        self._push_trunk(a, "in_progress", "claude/dead-session")
        self._push_session_branch(a, "claude/session-a", "in_progress", "claude/session-a")
        result = remote_claims.scan_remote_in_progress(b, TASK, "claude/session-b")
        assert [h.branch for h in result.holders] == ["claude/session-a"]  # 살아있는 claim은 남는다
        assert [s.branch for s in result.skipped] == ["main"]

    def test_no_task_file_on_trunk_falls_through_to_holder_check(self, bare_remote):
        """트렁크에 태스크 파일이 없으면 규칙A 신호없이 홀더검사."""
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

    def test_trunk_ref_asks_remote_head_first(self, bare_remote):
        """트렁크 ref는 원격 HEAD를 먼저 묻는다."""
        _, clone = bare_remote
        b = clone("session-b")
        result = remote_claims.scan_remote_in_progress(b, TASK, "claude/session-b")
        assert result.trunk_source == "ls-remote"  # 하드코딩 아님·원격 권위 우선
        assert result.trunk_ref == "refs/remotes/origin/main"

    def test_remote_wins_even_when_local_origin_head_is_stale(self, bare_remote):
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

    def test_falls_back_to_local_symbolic_ref_when_remote_head_blocked(
        self, bare_remote, monkeypatch
    ):
        """원격 HEAD 조회가 막히면 로컬 symbolic ref로 폴백."""
        _, clone = bare_remote
        a, b = clone("session-a"), clone("session-b")
        self._push_trunk(a, "done")
        self._push_session_branch(a, "claude/session-a", "in_progress", "claude/session-a")
        self._break_ls_remote(monkeypatch)
        result = remote_claims.scan_remote_in_progress(b, TASK, "claude/session-b")
        assert result.trunk_source == "symbolic-ref"
        assert result.holders == []  # 규칙 A는 그대로 작동

    def test_falls_back_to_main_when_all_resolution_fails(self, bare_remote, monkeypatch):
        """해소 전부 실패하면 main으로 폴백한다."""
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
    def test_stale_detection_three_criteria(self):
        """stale 3중 기준."""
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

    def test_reap_dry_run_does_not_delete(self, bare_remote):
        """reap dry run은 삭제하지 않는다."""
        _, clone = bare_remote
        a = clone("session-a")
        assert remote_claims.claim(a, "S1-03-ghost-task", "claude/session-a").status == "ok"
        backlog = _mk_backlog()  # ghost-task 미포함 → task_missing
        reaped, status = remote_claims.reap(a, backlog, ttl_hours=72, dry_run=True)
        assert status == "ok"
        assert len(reaped) == 1 and "task_missing" in reaped[0]
        claims, _ = remote_claims.list_claims(a)
        assert len(claims) == 1  # dry-run — 아직 남아 있음

    def test_reap_apply_actually_deletes(self, bare_remote):
        """reap apply는 실제 삭제."""
        _, clone = bare_remote
        a = clone("session-a")
        assert remote_claims.claim(a, "S1-03-ghost-task", "claude/session-a").status == "ok"
        backlog = _mk_backlog()
        reaped, status = remote_claims.reap(a, backlog, ttl_hours=72, dry_run=False)
        assert status == "ok" and len(reaped) == 1
        claims, _ = remote_claims.list_claims(a)
        assert claims == []

    def test_lookup_failure_is_not_disguised_as_no_stale(self, bare_remote, monkeypatch):
        """HARN-09 — 이 구분이 없어서 CI 교차검증이 공전했다.

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
        reaped, status = remote_claims.reap(a, _mk_backlog(), ttl_hours=72, dry_run=True)
        assert reaped == []
        assert status != "ok", "조회 실패가 ok로 보고되면 '0건 통과' 위장이 된다"
