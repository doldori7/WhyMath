"""backlog.py CLI — 시딩·라이프사이클·훅 진입점 종단 테스트.

실제 git 저장소 픽스처(git_repo) 위에서 main(argv)를 직접 호출한다.
"""

from __future__ import annotations

import io
import json
import subprocess
from pathlib import Path

import pytest

import backlog as cli
import store


@pytest.fixture
def seeded_repo(git_repo: Path, monkeypatch) -> Path:
    """seed까지 끝난 저장소 (cwd 고정)."""
    monkeypatch.chdir(git_repo)
    assert cli.main(["seed"]) == 0
    return git_repo


def _run_git(repo: Path, *argv: str) -> str:
    return subprocess.run(["git", *argv], cwd=repo, capture_output=True,
                          text=True, check=True).stdout.strip()


class TestSeed:
    def test_시딩_결과는_validate_green(self, seeded_repo: Path):
        assert cli.main(["validate"]) == 0

    def test_게이트_6종_시딩(self, seeded_repo: Path):
        backlog, _ = store.load_backlog(seeded_repo)
        assert set(backlog.gates) == {
            "G-phaiakes9-key", "G-kiki-device-demo", "G-orphan-prod-run",
            "G-domain-partner", "G-crosswalk-approval", "G-s5-subject-expansion",
        }

    def test_E축은_하드락_상태(self, seeded_repo: Path, capsys):
        # S5 확장 게이트 통과 전에는 물리 등 E축 태스크가 next에 절대 등장하지 않는다
        assert cli.main(["next", "--n", "50", "--json"]) == 0
        ids = [item["id"] for item in json.loads(capsys.readouterr().out)]
        assert ids  # 후보 자체는 존재
        assert not any(tid.startswith("E") for tid in ids)

    def test_다과목_태스크_시딩_확인(self, seeded_repo: Path):
        backlog, _ = store.load_backlog(seeded_repo)
        subjects = {t.subject for t in backlog.tasks.values()}
        # 물리·화학·생물·지구과학·역사사회·국어·영어가 백로그에 실재해야 한다
        assert {"physics", "chemistry", "biology", "earth-science",
                "social", "korean", "english"} <= subjects

    def test_재시딩은_force_없이_거부(self, seeded_repo: Path):
        assert cli.main(["seed"]) == 1


class TestLifecycle:
    def test_start_done_왕복(self, seeded_repo: Path, capsys):
        # 게이트 없는 즉시 착수 가능 태스크 하나를 골라 start→done
        assert cli.main(["next", "--n", "1", "--json"]) == 0
        task_id = json.loads(capsys.readouterr().out)[0]["id"]

        assert cli.main(["start", task_id, "--session", "test-branch"]) == 0
        backlog, _ = store.load_backlog(seeded_repo)
        assert backlog.tasks[task_id].status == "in_progress"
        assert backlog.tasks[task_id].session == "test-branch"

        assert cli.main(["done", task_id, "--artifact", "PR #999"]) == 0
        backlog, _ = store.load_backlog(seeded_repo)
        assert backlog.tasks[task_id].status == "done"
        assert "PR #999" in backlog.tasks[task_id].artifacts
        assert backlog.tasks[task_id].session is None

    def test_증적_없는_done_거부(self, seeded_repo: Path, capsys):
        assert cli.main(["next", "--n", "1", "--json"]) == 0
        task_id = json.loads(capsys.readouterr().out)[0]["id"]
        assert cli.main(["start", task_id, "--session", "b"]) == 0
        assert cli.main(["done", task_id]) == 1  # --artifact 없음 → 거부

    def test_게이트_대기_태스크는_start_거부(self, seeded_repo: Path):
        # S1-12는 G-phaiakes9-key(pending) 필요 → 착수 거부
        assert cli.main(["start", "S1-12-phaiakes9-live-verify"]) == 1

    def test_todo가_아닌_태스크_start_거부(self, seeded_repo: Path, capsys):
        assert cli.main(["next", "--n", "1", "--json"]) == 0
        task_id = json.loads(capsys.readouterr().out)[0]["id"]
        assert cli.main(["start", task_id, "--session", "b1"]) == 0
        assert cli.main(["start", task_id, "--session", "b2"]) == 1  # 이중 claim 거부

    def test_block_unblock(self, seeded_repo: Path, capsys):
        assert cli.main(["next", "--n", "1", "--json"]) == 0
        task_id = json.loads(capsys.readouterr().out)[0]["id"]
        assert cli.main(["start", task_id, "--session", "b"]) == 0
        assert cli.main(["block", task_id, "--reason", "검증 2연속 실패"]) == 0
        backlog, _ = store.load_backlog(seeded_repo)
        assert backlog.tasks[task_id].status == "blocked"
        assert cli.main(["unblock", task_id]) == 0
        backlog, _ = store.load_backlog(seeded_repo)
        assert backlog.tasks[task_id].status == "todo"


class TestGatesCli:
    def test_evidence_없는_clear_거부(self, seeded_repo: Path):
        assert cli.main(["gates", "clear", "G-phaiakes9-key"]) == 1

    def test_clear_후_의존_태스크_해금(self, seeded_repo: Path, capsys):
        assert cli.main(["gates", "clear", "G-phaiakes9-key",
                         "--evidence", "라이브 키 투입 커밋 abc123"]) == 0
        capsys.readouterr()  # clear 출력 비우고 next의 JSON만 파싱
        assert cli.main(["next", "--n", "10", "--json"]) == 0
        ids = [item["id"] for item in json.loads(capsys.readouterr().out)]
        assert "S1-12-phaiakes9-live-verify" in ids


class TestAdd:
    def test_add로_태스크_생성(self, seeded_repo: Path):
        assert cli.main([
            "add", "--id", "S2-90-new-task", "--title", "새 태스크",
            "--track", "math-completion", "--stage", "S2",
            "--acceptance", "테스트 green",
        ]) == 0
        backlog, _ = store.load_backlog(seeded_repo)
        assert "S2-90-new-task" in backlog.tasks

    def test_무결성_위반_add_거부(self, seeded_repo: Path):
        # 존재하지 않는 의존성 → 거부
        assert cli.main([
            "add", "--id", "S2-91-bad-task", "--title", "불량",
            "--track", "math-completion", "--stage", "S2",
            "--depends", "S9-99-ghost",
        ]) == 1
        backlog, _ = store.load_backlog(seeded_repo)
        assert "S2-91-bad-task" not in backlog.tasks


class TestCheckStop:
    def _claim_and_commit(self, repo: Path, capsys) -> str:
        """작업 브랜치에서 태스크 claim + 무관한 커밋 1개 생성."""
        _run_git(repo, "checkout", "-b", "work-branch")
        assert cli.main(["next", "--n", "1", "--json"]) == 0
        task_id = json.loads(capsys.readouterr().out)[0]["id"]
        assert cli.main(["start", task_id]) == 0
        capsys.readouterr()
        # backlog 변경을 커밋해 base와 분리한 뒤, 무관한 코드 커밋 추가
        _run_git(repo, "add", ".")
        _run_git(repo, "commit", "-m", "claim")
        (repo / "feature.py").write_text("# 작업물\n", encoding="utf-8")
        _run_git(repo, "add", ".")
        _run_git(repo, "commit", "-m", "feat: 작업")
        return task_id

    def _invoke(self, monkeypatch, stdin_payload: dict) -> int:
        monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(stdin_payload)))
        return cli.main(["check-stop"])

    def test_재진입은_즉시_통과(self, seeded_repo: Path, monkeypatch, capsys):
        self._claim_and_commit(seeded_repo, capsys)
        assert self._invoke(monkeypatch, {"stop_hook_active": True}) == 0

    def test_진행중_태스크_미갱신이면_차단(self, seeded_repo: Path, monkeypatch, capsys):
        # claim 커밋 이후 태스크 파일 변경 없이 코드 커밋만 있으면… claim 커밋이
        # 이미 태스크 파일을 포함하므로 통과 — 여기서는 claim을 base(main)에 합쳐
        # "브랜치 diff에 태스크 파일이 없는" 상태를 재현한다
        task_id = self._claim_and_commit(seeded_repo, capsys)
        _run_git(seeded_repo, "checkout", "main")
        _run_git(seeded_repo, "merge", "work-branch", "--ff-only")
        _run_git(seeded_repo, "checkout", "work-branch")
        (seeded_repo / "feature2.py").write_text("# 추가 작업\n", encoding="utf-8")
        _run_git(seeded_repo, "add", ".")
        _run_git(seeded_repo, "commit", "-m", "feat: 추가 작업")
        code = self._invoke(monkeypatch, {})
        err = capsys.readouterr().err
        assert code == 2
        assert task_id in err

    def test_태스크_갱신했으면_통과(self, seeded_repo: Path, monkeypatch, capsys):
        self._claim_and_commit(seeded_repo, capsys)
        # claim 커밋(태스크 파일 변경 포함)이 브랜치 diff에 있으므로 통과해야 한다
        assert self._invoke(monkeypatch, {}) == 0

    def test_claim_없으면_통과(self, seeded_repo: Path, monkeypatch):
        _run_git(seeded_repo, "checkout", "-b", "idle-branch")
        assert self._invoke(monkeypatch, {}) == 0

    def test_main_브랜치는_통과(self, seeded_repo: Path, monkeypatch):
        assert self._invoke(monkeypatch, {}) == 0


class TestCheckEdit:
    def _invoke(self, monkeypatch, file_path: str) -> int:
        payload = {"tool_input": {"file_path": file_path}}
        monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))
        return cli.main(["check-edit"])

    def test_backlog_외_파일은_무시(self, seeded_repo: Path, monkeypatch):
        assert self._invoke(monkeypatch, "/repo/src/backend/app.py") == 0

    def test_backlog_직접_편집으로_깨지면_차단(self, seeded_repo: Path, monkeypatch):
        path = seeded_repo / "backlog" / "tasks" / "S2-03-problem-concept-relink.yaml"
        path.write_text(path.read_text(encoding="utf-8").replace(
            "layer: backend", "layer: frontend"), encoding="utf-8")
        assert self._invoke(monkeypatch, str(path)) == 2

    def test_정상_편집은_통과(self, seeded_repo: Path, monkeypatch):
        path = seeded_repo / "backlog" / "tasks" / "S2-03-problem-concept-relink.yaml"
        assert self._invoke(monkeypatch, str(path)) == 0


class TestReporting:
    def test_status_출력에_현재_스테이지와_게이트(self, seeded_repo: Path, capsys):
        assert cli.main(["status"]) == 0
        out = capsys.readouterr().out
        assert "S1" in out
        assert "G-phaiakes9-key" in out

    def test_brief_출력에_다음_후보와_리마인드(self, seeded_repo: Path, capsys):
        assert cli.main(["brief", "--format", "hook"]) == 0
        out = capsys.readouterr().out
        assert "[빌드하네스 브리핑]" in out
        assert "다음 착수 후보" in out

    def test_status_json(self, seeded_repo: Path, capsys):
        assert cli.main(["status", "--json"]) == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["current_stage"] == "S1"
        assert payload["validate_errors"] == []


class TestRemoteClaimCli:
    """start/done/block의 원격 claim(refs/claims/*) 통합 — 병렬 세션 레이스 종단 재현."""

    def _seeded_clone(self, clone, monkeypatch, name: str) -> Path:
        repo = clone(name)
        monkeypatch.chdir(repo)
        assert cli.main(["seed"]) == 0
        return repo

    def _next_ids(self, capsys, n: int = 1) -> list[str]:
        """게이트 없는 즉시 착수 가능 태스크 id를 n개 고른다 (기존 컨벤션)."""
        capsys.readouterr()  # 시딩 출력 등 이전 버퍼 비우기
        assert cli.main(["next", "--n", str(n), "--json"]) == 0
        return [row["id"] for row in json.loads(capsys.readouterr().out)]

    def test_start가_원격_claim을_생성한다(self, bare_remote, monkeypatch, capsys):
        _, clone = bare_remote
        repo = self._seeded_clone(clone, monkeypatch, "session-a")
        [task_id] = self._next_ids(capsys)
        assert cli.main(["start", task_id]) == 0
        assert "원격 claim: ok" in capsys.readouterr().out
        import remote_claims
        claims, status = remote_claims.list_claims(repo)
        assert status == "ok"
        assert [c.task_id for c in claims] == [task_id]

    def test_레이스_두_세션_같은_태스크는_후발이_거부된다(self, bare_remote, monkeypatch, capsys):
        _, clone = bare_remote
        self._seeded_clone(clone, monkeypatch, "session-a")
        [task_id] = self._next_ids(capsys)
        assert cli.main(["start", task_id]) == 0
        capsys.readouterr()
        # 세션 B — 독립 클론(백로그 사본에는 A의 claim이 안 보임 = 기존 TOCTOU 구멍)
        repo_b = self._seeded_clone(clone, monkeypatch, "session-b")
        assert cli.main(["start", task_id]) == 1
        err = capsys.readouterr().err
        assert "이미 원격 claim" in err
        assert "claude/session-a" in err
        # B의 로컬 백로그는 오염되지 않음 (claim 실패 시 저장 안 함)
        backlog, _ = store.load_backlog(repo_b)
        assert backlog.tasks[task_id].status == "todo"

    def test_done이_원격_claim을_해제한다(self, bare_remote, monkeypatch, capsys):
        _, clone = bare_remote
        repo = self._seeded_clone(clone, monkeypatch, "session-a")
        [task_id] = self._next_ids(capsys)
        assert cli.main(["start", task_id]) == 0
        assert cli.main(["done", task_id, "--artifact", "PR#1"]) == 0
        import remote_claims
        claims, _ = remote_claims.list_claims(repo)
        assert claims == []

    def test_block이_원격_claim을_해제한다(self, bare_remote, monkeypatch, capsys):
        _, clone = bare_remote
        repo = self._seeded_clone(clone, monkeypatch, "session-a")
        [task_id] = self._next_ids(capsys)
        assert cli.main(["start", task_id]) == 0
        assert cli.main(["block", task_id, "--reason", "테스트"]) == 0
        import remote_claims
        claims, _ = remote_claims.list_claims(repo)
        assert claims == []

    def test_no_remote_플래그는_원격을_생략한다(self, bare_remote, monkeypatch, capsys):
        _, clone = bare_remote
        repo = self._seeded_clone(clone, monkeypatch, "session-a")
        [task_id] = self._next_ids(capsys)
        assert cli.main(["start", task_id, "--no-remote"]) == 0
        assert "원격 claim: disabled" in capsys.readouterr().out
        import remote_claims
        claims, _ = remote_claims.list_claims(repo)
        assert claims == []

    def test_원격_없어도_start는_진행된다_fail_open(self, seeded_repo: Path, capsys):
        # origin이 아예 없는 저장소 — offline 경고 후 로컬 claim으로 진행
        [task_id] = self._next_ids(capsys)
        assert cli.main(["start", task_id]) == 0
        captured = capsys.readouterr()
        assert "원격 claim: offline" in captured.out
        assert "로컬 claim만" in captured.err

    def test_claims_list_release(self, bare_remote, monkeypatch, capsys):
        _, clone = bare_remote
        self._seeded_clone(clone, monkeypatch, "session-a")
        [task_id] = self._next_ids(capsys)
        assert cli.main(["start", task_id]) == 0
        capsys.readouterr()
        assert cli.main(["claims", "list", "--verbose"]) == 0
        out = capsys.readouterr().out
        assert task_id in out
        assert "claude/session-a" in out
        # 내 claim이므로 force 불필요
        assert cli.main(["claims", "release", task_id]) == 0

    def test_claims_reap_고아_ref_청소(self, bare_remote, monkeypatch, capsys):
        _, clone = bare_remote
        repo = self._seeded_clone(clone, monkeypatch, "session-a")
        task_a, task_b = self._next_ids(capsys, n=2)
        # 고아 ref 인위 생성: claim만 남기고 로컬은 done 처리 (세션 사망 모사)
        import remote_claims
        assert remote_claims.claim(repo, task_b, "claude/ghost").status == "ok"
        backlog, _ = store.load_backlog(repo)
        backlog.tasks[task_b].status = "done"
        backlog.tasks[task_b].artifacts = ["x"]
        store.save_task(repo, backlog.tasks[task_b])
        capsys.readouterr()
        assert cli.main(["claims", "reap"]) == 0
        assert "dry-run" in capsys.readouterr().out
        claims, _ = remote_claims.list_claims(repo)
        assert len(claims) == 1  # dry-run — 남아 있음
        assert cli.main(["claims", "reap", "--apply"]) == 0
        claims, _ = remote_claims.list_claims(repo)
        assert claims == []


class TestStartOverlapPreflight:
    """start 프리플라이트 — in-flight 태스크와 paths 겹침 검사 (warn→block 단계적)."""

    def _add_two_overlapping(self, capsys) -> tuple[str, str]:
        assert cli.main(["add", "--id", "T9-01-overlap-a", "--title", "겹침 A",
                         "--track", "math-completion", "--stage", "S1",
                         "--path", "src/backend/api/**"]) == 0
        assert cli.main(["add", "--id", "T9-02-overlap-b", "--title", "겹침 B",
                         "--track", "math-completion", "--stage", "S1",
                         "--path", "src/backend/**"]) == 0
        capsys.readouterr()
        return "T9-01-overlap-a", "T9-02-overlap-b"

    def test_warn_모드_경고_후_진행(self, seeded_repo: Path, capsys):
        a, b = self._add_two_overlapping(capsys)
        assert cli.main(["start", a, "--session", "claude/other", "--no-remote"]) == 0
        capsys.readouterr()
        assert cli.main(["start", b, "--session", "claude/me", "--no-remote"]) == 0
        err = capsys.readouterr().err
        assert "파일 범위 겹침" in err
        # policy_warn 이벤트가 측정용으로 적재된다
        events = (seeded_repo / "backlog" / "events.ndjson").read_text(encoding="utf-8")
        assert '"action": "policy_warn"' in events
        assert '"rule": "path_overlap"' in events

    def test_block_모드_착수_거부(self, seeded_repo: Path, capsys):
        import store as store_mod
        from models import Policy
        store_mod.save_policy(seeded_repo, Policy(path_overlap="block"))
        a, b = self._add_two_overlapping(capsys)
        assert cli.main(["start", a, "--session", "claude/other", "--no-remote"]) == 0
        capsys.readouterr()
        assert cli.main(["start", b, "--session", "claude/me", "--no-remote"]) == 1
        assert "겹침" in capsys.readouterr().err
        backlog, _ = store.load_backlog(seeded_repo)
        assert backlog.tasks[b].status == "todo"  # 거부 시 상태 불변

    def test_paths_미선언_태스크는_겹침_검사_제외(self, seeded_repo: Path, capsys):
        capsys.readouterr()
        assert cli.main(["next", "--n", "1", "--json", "--no-remote"]) == 0
        task_id = json.loads(capsys.readouterr().out)[0]["id"]
        assert cli.main(["start", task_id, "--session", "claude/me", "--no-remote"]) == 0
        assert "paths 미선언" in capsys.readouterr().err  # 선언 권장 안내


class TestCheckEditPolicy:
    """check-edit 훅의 조율 정책 3분기 — scope_drift·path_overlap·adhoc_edit."""

    def _invoke(self, monkeypatch, file_path: str) -> int:
        payload = {"tool_input": {"file_path": file_path}}
        monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))
        return cli.main(["check-edit"])

    def _on_branch(self, repo: Path, name: str) -> None:
        subprocess.run(["git", "checkout", "-q", "-b", name], cwd=repo, check=True)

    def test_main_브랜치는_전부_통과(self, seeded_repo: Path, monkeypatch):
        assert self._invoke(monkeypatch, str(seeded_repo / "src" / "x.py")) == 0

    def test_adhoc_edit_claim_없이_코드_편집_경고(self, seeded_repo: Path, monkeypatch, capsys):
        self._on_branch(seeded_repo, "claude/adhoc-session")
        code = self._invoke(monkeypatch, str(seeded_repo / "src" / "backend" / "app.py"))
        assert code == 0  # warn 모드 — 차단하지 않음
        assert "adhoc_edit" in capsys.readouterr().err

    def test_adhoc_edit_비코드_파일은_해당_없음(self, seeded_repo: Path, monkeypatch, capsys):
        self._on_branch(seeded_repo, "claude/adhoc-session")
        assert self._invoke(monkeypatch, str(seeded_repo / "MEMORY.md")) == 0
        assert "adhoc_edit" not in capsys.readouterr().err

    def test_scope_drift_선언_범위_밖_편집_경고(self, seeded_repo: Path, monkeypatch, capsys):
        self._on_branch(seeded_repo, "claude/drift-session")
        assert cli.main(["add", "--id", "T9-03-scoped-task", "--title", "범위 태스크",
                         "--track", "math-completion", "--stage", "S1",
                         "--path", "src/backend/api/**"]) == 0
        assert cli.main(["start", "T9-03-scoped-task", "--no-remote"]) == 0
        capsys.readouterr()
        # 선언 범위 안 — 조용히 통과
        assert self._invoke(monkeypatch, str(seeded_repo / "src/backend/api/routes.py")) == 0
        assert "scope_drift" not in capsys.readouterr().err
        # 선언 범위 밖 — 경고
        assert self._invoke(monkeypatch, str(seeded_repo / "src/mobile/lib/main.dart")) == 0
        assert "scope_drift" in capsys.readouterr().err

    def test_path_overlap_타_세션_범위_편집_경고(self, seeded_repo: Path, monkeypatch, capsys):
        self._on_branch(seeded_repo, "claude/my-session")
        assert cli.main(["add", "--id", "T9-04-other-task", "--title", "남의 태스크",
                         "--track", "math-completion", "--stage", "S1",
                         "--path", "src/data-pipeline/**"]) == 0
        assert cli.main(["start", "T9-04-other-task",
                         "--session", "claude/other-session", "--no-remote"]) == 0
        capsys.readouterr()
        code = self._invoke(monkeypatch, str(seeded_repo / "src/data-pipeline/crawler.py"))
        assert code == 0  # warn 모드
        err = capsys.readouterr().err
        assert "path_overlap" in err
        assert "T9-04-other-task" in err

    def test_block_모드는_편집을_차단한다(self, seeded_repo: Path, monkeypatch, capsys):
        import store as store_mod
        from models import Policy
        store_mod.save_policy(seeded_repo, Policy(adhoc_edit="block"))
        self._on_branch(seeded_repo, "claude/adhoc-session")
        code = self._invoke(monkeypatch, str(seeded_repo / "src" / "backend" / "app.py"))
        assert code == 2

    def test_예외_시_무조건_통과_fail_open(self, seeded_repo: Path, monkeypatch):
        self._on_branch(seeded_repo, "claude/failopen-session")
        # 정책 로드가 터져도 훅은 개발을 볼모로 잡지 않는다
        monkeypatch.setattr(store, "load_policy",
                            lambda root: (_ for _ in ()).throw(RuntimeError("boom")))
        assert self._invoke(monkeypatch, str(seeded_repo / "src" / "backend" / "app.py")) == 0


class TestPolicyCli:
    def test_policy_show_기본값(self, seeded_repo: Path, capsys):
        capsys.readouterr()
        assert cli.main(["policy", "show"]) == 0
        out = capsys.readouterr().out
        assert "path_overlap: warn" in out

    def test_policy_report_경고_집계(self, seeded_repo: Path, capsys):
        # 인위적으로 policy_warn 이벤트 적재 후 리포트 확인
        store.append_event(seeded_repo, "policy_warn", "-",
                           rule="adhoc_edit", file="src/x.py", mode="warn")
        capsys.readouterr()
        assert cli.main(["policy", "report"]) == 0
        out = capsys.readouterr().out
        assert "adhoc_edit: 1건" in out
        assert "승격 기준" in out


class TestCrossSessionOverlap:
    """교차 세션 겹침 — 상태(in_progress)는 브랜치 로컬이므로 원격 claim이 유일한 신호."""

    def _seeded_clone(self, clone, monkeypatch, name: str) -> Path:
        repo = clone(name)
        monkeypatch.chdir(repo)
        assert cli.main(["seed"]) == 0
        return repo

    def _add_overlapping_pair(self) -> tuple[str, str]:
        # 두 클론 모두에 같은 태스크 정의가 있어야 한다(실환경에선 git으로 공유됨)
        assert cli.main(["add", "--id", "T8-05-cross-a", "--title", "교차 A",
                         "--track", "math-completion", "--stage", "S1",
                         "--path", "src/backend/**"]) == 0
        assert cli.main(["add", "--id", "T8-06-cross-b", "--title", "교차 B",
                         "--track", "math-completion", "--stage", "S1",
                         "--path", "src/backend/api/**"]) == 0
        return "T8-05-cross-a", "T8-06-cross-b"

    def test_start_프리플라이트가_원격_claim_태스크와의_겹침을_잡는다(
            self, bare_remote, monkeypatch, capsys):
        _, clone = bare_remote
        self._seeded_clone(clone, monkeypatch, "session-a")
        a, b = self._add_overlapping_pair()
        assert cli.main(["start", a]) == 0
        capsys.readouterr()
        # 세션 B의 독립 클론 — 로컬 backlog에서 a는 여전히 todo (claim 불가시)
        repo_b = self._seeded_clone(clone, monkeypatch, "session-b")
        self._add_overlapping_pair()
        backlog, _ = store.load_backlog(repo_b)
        assert backlog.tasks[a].status == "todo"  # 전제 확인: 로컬은 모름
        capsys.readouterr()
        assert cli.main(["start", b]) == 0  # warn 모드 — 진행은 되지만
        err = capsys.readouterr().err
        assert "파일 범위 겹침" in err
        assert a in err  # 원격 claim 기반으로 A와의 겹침을 식별

    def test_check_edit이_캐시로_교차_세션_겹침을_잡는다(
            self, bare_remote, monkeypatch, capsys):
        _, clone = bare_remote
        self._seeded_clone(clone, monkeypatch, "session-a")
        a, _ = self._add_overlapping_pair()
        assert cli.main(["start", a]) == 0
        # 세션 B: brief가 원격 claim 조회 + 캐시 갱신 (SessionStart 모사)
        repo_b = self._seeded_clone(clone, monkeypatch, "session-b")
        self._add_overlapping_pair()
        assert cli.main(["brief"]) == 0
        capsys.readouterr()
        # B가 A의 선언 범위(src/backend/**) 안 파일 편집 → path_overlap 경고
        payload = {"tool_input": {"file_path": str(repo_b / "src/backend/api/x.py")}}
        monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))
        assert cli.main(["check-edit"]) == 0  # warn 모드
        err = capsys.readouterr().err
        assert "path_overlap" in err
        assert a in err
