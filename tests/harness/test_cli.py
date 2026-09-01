"""backlog.py CLI — 시딩·라이프사이클·훅 진입점 종단 테스트.

실제 git 저장소 픽스처(git_repo) 위에서 main(argv)를 직접 호출한다.
"""

from __future__ import annotations

import io
import json
import subprocess
from pathlib import Path

import pytest
import store

import backlog as cli


@pytest.fixture
def seeded_repo(git_repo: Path, monkeypatch) -> Path:
    """seed까지 끝난 저장소 (cwd 고정)."""
    monkeypatch.chdir(git_repo)
    assert cli.main(["seed"]) == 0
    return git_repo


def _run_git(repo: Path, *argv: str) -> str:
    return subprocess.run(
        ["git", *argv], cwd=repo, capture_output=True, text=True, check=True
    ).stdout.strip()


def _all_events_text(repo: Path) -> str:
    """이벤트 대장 전문 — 레거시 + 세션 샤드 합집합(HARN-46 샤딩 이후의 정본 읽기)."""
    return "".join(path.read_text(encoding="utf-8") for path in store.event_paths(repo))


class TestSeed:
    def test_seed_result_is_validate_green(self, seeded_repo: Path):
        """시딩_결과는_validate_green"""
        assert cli.main(["validate"]) == 0

    def test_seeds_six_gate_types(self, seeded_repo: Path):
        """게이트_6종_시딩"""
        backlog, _ = store.load_backlog(seeded_repo)
        assert set(backlog.gates) == {
            "G-phaiakes9-key",
            "G-kiki-device-demo",
            "G-orphan-prod-run",
            "G-domain-partner",
            "G-crosswalk-approval",
            "G-s5-subject-expansion",
        }

    def test_e_axis_is_hard_locked(self, seeded_repo: Path, capsys):
        """E축은_하드락_상태"""
        # S5 확장 게이트 통과 전에는 물리 등 E축 태스크가 next에 절대 등장하지 않는다
        assert cli.main(["next", "--n", "50", "--json"]) == 0
        ids = [item["id"] for item in json.loads(capsys.readouterr().out)]
        assert ids  # 후보 자체는 존재
        assert not any(tid.startswith("E") for tid in ids)

    def test_seeds_multi_subject_tasks(self, seeded_repo: Path):
        """다과목_태스크_시딩_확인"""
        backlog, _ = store.load_backlog(seeded_repo)
        subjects = {t.subject for t in backlog.tasks.values()}
        # 물리·화학·생물·지구과학·역사사회·국어·영어가 백로그에 실재해야 한다
        assert {
            "physics",
            "chemistry",
            "biology",
            "earth-science",
            "social",
            "korean",
            "english",
        } <= subjects

    def test_reseed_without_force_rejected(self, seeded_repo: Path):
        """재시딩은_force_없이_거부"""
        assert cli.main(["seed"]) == 1


class TestNextTruncationDisclosure:
    """`next` 사람용 출력이 **절단 규모**를 드러내는지 (HARN-52 후속).

    사고 경위(2026-09-01): 어떤 태스크가 착수 후보인지 판정하려고 `next`(상위 3건)를
    썼는데, 대상이 priority 2라 **정상 상태와 뮤테이션 상태 양쪽 모두 "후보에 없음"**
    이 나왔다 — 검증 스텝의 변별력이 0이었다. 출력이 "상위 3건"이라고 정직하게 적어도,
    *얼마나* 잘렸는지와 전건 조회 방법이 없으면 그 출력은 부재 판정에 쓰이고 만다.

    CLAUDE.md "검사 명령의 출력을 억제하거나 잘라서 판정 금지"의 *도구가 자르는* 축.
    """

    def test_shows_total_and_recovery_when_truncated(self, seeded_repo: Path, capsys):
        """잘렸으면 분모와 전건 조회 방법을 함께 낸다."""
        assert cli.main(["next", "--n", "50", "--json"]) == 0
        total = len(json.loads(capsys.readouterr().out))
        assert total > 1, "시드에 후보가 2건 이상 있어야 이 검사가 성립한다"

        assert cli.main(["next", "--n", "1"]) == 0
        out = capsys.readouterr().out
        assert f"전체 {total}건 중 상위 1건" in out, "분모가 없으면 절단 규모를 알 수 없다"
        assert "--json" in out and f"--n {total}" in out, "전건 조회 방법을 안내해야 한다"

    def test_no_truncation_notice_when_complete(self, seeded_repo: Path, capsys):
        """안 잘렸으면 '중 상위' 표기를 내지 않는다 — 대조군(항상 같은 말을 하면 위장)."""
        assert cli.main(["next", "--n", "50", "--json"]) == 0
        total = len(json.loads(capsys.readouterr().out))

        assert cli.main(["next", "--n", str(total + 10)]) == 0
        out = capsys.readouterr().out
        assert f"전체 {total}건" in out
        assert "중 상위" not in out, "잘리지 않았는데 절단 표기가 났다"
        assert "표시되지 않았다" not in out


class TestLifecycle:
    def test_start_done_roundtrip(self, seeded_repo: Path, capsys):
        """start_done_왕복"""
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

    def test_done_without_artifact_rejected(self, seeded_repo: Path, capsys):
        """증적_없는_done_거부"""
        assert cli.main(["next", "--n", "1", "--json"]) == 0
        task_id = json.loads(capsys.readouterr().out)[0]["id"]
        assert cli.main(["start", task_id, "--session", "b"]) == 0
        assert cli.main(["done", task_id]) == 1  # --artifact 없음 → 거부

    def test_gate_pending_task_start_rejected(self, seeded_repo: Path):
        """게이트_대기_태스크는_start_거부"""
        # S1-12는 G-phaiakes9-key(pending) 필요 → 착수 거부
        assert cli.main(["start", "S1-12-phaiakes9-live-verify"]) == 1

    def test_non_todo_task_start_rejected(self, seeded_repo: Path, capsys):
        """todo가_아닌_태스크_start_거부"""
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
    def test_clear_without_evidence_rejected(self, seeded_repo: Path):
        """evidence_없는_clear_거부"""
        assert cli.main(["gates", "clear", "G-phaiakes9-key"]) == 1

    def test_clear_unblocks_dependent_task(self, seeded_repo: Path, capsys):
        """clear_후_의존_태스크_해금"""
        assert (
            cli.main(
                ["gates", "clear", "G-phaiakes9-key", "--evidence", "라이브 키 투입 커밋 abc123"]
            )
            == 0
        )
        capsys.readouterr()  # clear 출력 비우고 next의 JSON만 파싱
        assert cli.main(["next", "--n", "10", "--json"]) == 0
        ids = [item["id"] for item in json.loads(capsys.readouterr().out)]
        assert "S1-12-phaiakes9-live-verify" in ids


class TestGatesAdd:
    """HARN-18 — gates add CLI 경로 (손편집 금지 규약의 구멍 메움).

    task add와 동일하게 (a)정상 등재+감사로그 (b)중복 id 거부 (c)필수 필드 누락 거부의
    *변별력*을 동결한다 — (b)(c)는 정상 케이스가 0을 내는 것과 대비해 실제 거부(1)를 확인.
    """

    def test_add_creates_gate_and_appends_event(self, seeded_repo: Path):
        """정상_add로_게이트_생성_및_감사로그_기록"""
        assert (
            cli.main(
                [
                    "gates",
                    "add",
                    "G-new-human-approval",
                    "--title",
                    "새 사람 승인 게이트",
                    "--kind",
                    "human",
                    "--assignee",
                    "kiki",
                    "--remind-after-days",
                    "7",
                ]
            )
            == 0
        )
        backlog, _ = store.load_backlog(seeded_repo)
        assert "G-new-human-approval" in backlog.gates
        gate = backlog.gates["G-new-human-approval"]
        assert gate.status == "pending"
        assert gate.kind == "human"
        assert gate.remind_after_days == 7
        assert gate.requested  # requested 자동 스탬프(YYYY-MM-DD)
        # events.ndjson 감사 로그에 gate_add 이벤트가 남는다 (누가·언제·무엇)
        events = _all_events_text(seeded_repo)
        assert any(
            json.loads(line).get("action") == "gate_add"
            and json.loads(line).get("id") == "G-new-human-approval"
            for line in events.splitlines()
        )

    def test_added_gate_keeps_validate_green(self, seeded_repo: Path):
        """add_후_대장_validate_green (기존 대장 무결성 불변)"""
        assert cli.main(["gates", "add", "G-extra-check", "--title", "추가 점검"]) == 0
        assert cli.main(["validate"]) == 0
        backlog, _ = store.load_backlog(seeded_repo)
        # 기본값 정합 — kind=human, assignee=kiki, pending
        gate = backlog.gates["G-extra-check"]
        assert (gate.kind, gate.assignee, gate.status) == ("human", "kiki", "pending")

    def test_added_decision_gate_can_gate_task(self, seeded_repo: Path):
        """add한_게이트가_실제로_태스크를_게이팅한다 (배선 실재 확인)"""
        assert (
            cli.main(
                ["gates", "add", "G-live-gate", "--title", "라이브 게이트", "--kind", "decision"]
            )
            == 0
        )
        # 이 게이트를 requires_gates로 건 태스크는 게이트가 pending인 동안 착수 거부돼야 한다
        assert (
            cli.main(
                [
                    "add",
                    "--id",
                    "S2-93-gated-task",
                    "--title",
                    "게이트 대기 태스크",
                    "--track",
                    "math-completion",
                    "--stage",
                    "S2",
                    "--gates",
                    "G-live-gate",
                ]
            )
            == 0
        )
        assert cli.main(["start", "S2-93-gated-task", "--session", "b"]) == 1  # pending → 거부

    def test_duplicate_id_rejected(self, seeded_repo: Path):
        """중복_id_add_거부 (변별력 — 정상 0 대비 실제 거부 1)"""
        assert cli.main(["gates", "add", "G-phaiakes9-key", "--title", "중복 시도"]) == 1
        # 대장 오염 없음 — 기존 게이트 제목이 덮이지 않았다
        backlog, _ = store.load_backlog(seeded_repo)
        assert backlog.gates["G-phaiakes9-key"].title != "중복 시도"

    def test_missing_title_rejected(self, seeded_repo: Path):
        """필수_필드(title)_누락_add_거부"""
        assert cli.main(["gates", "add", "G-no-title"]) == 1
        backlog, _ = store.load_backlog(seeded_repo)
        assert "G-no-title" not in backlog.gates

    def test_missing_id_rejected(self, seeded_repo: Path):
        """필수_필드(id)_누락_add_거부"""
        assert cli.main(["gates", "add", "--title", "id 없음"]) == 1

    def test_invalid_id_format_rejected(self, seeded_repo: Path):
        """잘못된_id_형식_거부 (스키마 무결성 — G- 소문자 kebab 아님)"""
        assert cli.main(["gates", "add", "BadId", "--title", "형식 위반"]) == 1
        backlog, _ = store.load_backlog(seeded_repo)
        assert "BadId" not in backlog.gates
        assert cli.main(["validate"]) == 0  # 거부됐으므로 대장은 여전히 green


class TestAdd:
    def test_add_creates_task(self, seeded_repo: Path):
        """add로_태스크_생성"""
        assert (
            cli.main(
                [
                    "add",
                    "--id",
                    "S2-90-new-task",
                    "--title",
                    "새 태스크",
                    "--track",
                    "math-completion",
                    "--stage",
                    "S2",
                    "--acceptance",
                    "테스트 green",
                ]
            )
            == 0
        )
        backlog, _ = store.load_backlog(seeded_repo)
        assert "S2-90-new-task" in backlog.tasks

    def test_add_with_integrity_violation_rejected(self, seeded_repo: Path):
        """무결성_위반_add_거부"""
        # 존재하지 않는 의존성 → 거부
        assert (
            cli.main(
                [
                    "add",
                    "--id",
                    "S2-91-bad-task",
                    "--title",
                    "불량",
                    "--track",
                    "math-completion",
                    "--stage",
                    "S2",
                    "--depends",
                    "S9-99-ghost",
                ]
            )
            == 1
        )
        backlog, _ = store.load_backlog(seeded_repo)
        assert "S2-91-bad-task" not in backlog.tasks


class TestIdNumberCollision:
    """HARN-10 — `<PREFIX>-<번호>` 중복 등재 차단.

    실측 2회(ARCH-13·OPS-15)가 전부 **병렬 세션이 서로의 브랜치를 못 봐서** 났으므로,
    로컬 차단만이 아니라 *원격 claim 대장 조회*와 *변별력*(정상 케이스 통과)을 함께 동결한다.
    """

    def _add(self, task_id: str) -> int:
        return cli.main(
            [
                "add",
                "--id",
                task_id,
                "--title",
                "번호 충돌 테스트",
                "--track",
                "math-completion",
                "--stage",
                "S2",
            ]
        )

    def test_same_number_different_slug_rejected(self, seeded_repo: Path):
        """같은_번호_다른_슬러그_거부"""
        assert self._add("S2-90-first") == 0
        assert self._add("S2-90-second-slug") == 1  # 번호 충돌
        backlog, _ = store.load_backlog(seeded_repo)
        assert "S2-90-second-slug" not in backlog.tasks

    def test_different_number_passes(self, seeded_repo: Path):
        """다른_번호는_통과

        변별력 — 충돌이 아닌 것까지 막으면 그건 게이트가 아니라 고장이다.
        """
        assert self._add("S2-90-first") == 0
        assert self._add("S2-91-different-number") == 0

    def test_number_held_by_remote_claim_rejected(self, seeded_repo: Path, monkeypatch):
        """원격_claim이_점유한_번호도_거부

        로컬 백로그엔 없지만 *타 세션이 인플라이트*인 번호 — 실제 사고 형태.
        """
        import remote_claims

        claim = remote_claims.RemoteClaim(
            task_id="S2-95-other-session", sha="deadbeef", branch="claude/other"
        )
        monkeypatch.setattr(remote_claims, "list_claims", lambda root, **kw: ([claim], "ok"))
        assert self._add("S2-95-my-slug") == 1
        backlog, _ = store.load_backlog(seeded_repo)
        assert "S2-95-my-slug" not in backlog.tasks

    def test_same_full_id_readd_is_not_a_collision(self, seeded_repo: Path, monkeypatch):
        """같은_full_ID_재등재는_충돌이_아니다

        다른 클론에서 같은 태스크를 재등재하는 것(시딩·복제 세션)은 정상 경로다.

        구현 중 실제로 이걸 막아 기존 교차세션 테스트 5건을 깨뜨렸다 — 번호 참조가
        모호해지는 것은 **슬러그가 다를 때**뿐이므로, 동일 ID는 통과해야 한다.
        """
        import remote_claims

        claim = remote_claims.RemoteClaim(
            task_id="S2-97-same-task", sha="deadbeef", branch="claude/other"
        )
        monkeypatch.setattr(remote_claims, "list_claims", lambda root, **kw: ([claim], "ok"))
        assert self._add("S2-97-same-task") == 0

    def test_remote_lookup_failure_warns_but_does_not_block_add(
        self, seeded_repo: Path, monkeypatch, capsys
    ):
        """원격_조회_실패는_등재를_막지_않되_경고한다

        fail-open — 단 침묵 금지(예외 타입명 노출·CLAUDE.md 침묵 실패 금지).
        """
        import remote_claims

        def _boom(root, **kw):
            raise RuntimeError("원격 불가")

        monkeypatch.setattr(remote_claims, "list_claims", _boom)
        assert self._add("S2-96-offline-ok") == 0
        captured = capsys.readouterr()
        assert "RuntimeError" in captured.err

    def test_validate_catches_merged_collision(self, seeded_repo: Path):
        """validate가_머지된_충돌을_잡는다

        2선 방어 — add를 우회해 손 편집으로 들어온 충돌도 validate가 실패시킨다.
        """
        assert self._add("S2-90-first") == 0
        backlog, _ = store.load_backlog(seeded_repo)
        smuggled = backlog.tasks["S2-90-first"]
        smuggled.id = "S2-90-smuggled-by-hand"
        store.save_task(seeded_repo, smuggled)
        assert cli.main(["validate"]) == 1

    def test_grandfathered_number_passes(self, seeded_repo: Path):
        """grandfather_번호는_통과

        이미 머지된 과거 충돌(개명 시 참조 파손)은 사유와 함께 면제된다.
        """
        backlog, _ = store.load_backlog(seeded_repo)
        assert store._id_number_collisions(["ARCH-13-a", "ARCH-13-b"]) == []
        assert store._id_number_collisions(["ZZ-01-a", "ZZ-01-b"]), "면제 아닌 번호는 잡혀야 함"


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

    def test_reentry_passes_immediately(self, seeded_repo: Path, monkeypatch, capsys):
        """재진입은_즉시_통과"""
        self._claim_and_commit(seeded_repo, capsys)
        assert self._invoke(monkeypatch, {"stop_hook_active": True}) == 0

    def test_blocks_when_in_progress_task_not_updated(self, seeded_repo: Path, monkeypatch, capsys):
        """진행중_태스크_미갱신이면_차단"""
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

    def test_passes_when_task_updated(self, seeded_repo: Path, monkeypatch, capsys):
        """태스크_갱신했으면_통과"""
        self._claim_and_commit(seeded_repo, capsys)
        # claim 커밋(태스크 파일 변경 포함)이 브랜치 diff에 있으므로 통과해야 한다
        assert self._invoke(monkeypatch, {}) == 0

    def test_passes_when_no_claim(self, seeded_repo: Path, monkeypatch):
        """claim_없으면_통과"""
        _run_git(seeded_repo, "checkout", "-b", "idle-branch")
        assert self._invoke(monkeypatch, {}) == 0

    def test_main_branch_passes(self, seeded_repo: Path, monkeypatch):
        """main_브랜치는_통과"""
        assert self._invoke(monkeypatch, {}) == 0


class TestCheckEdit:
    def _invoke(self, monkeypatch, file_path: str) -> int:
        payload = {"tool_input": {"file_path": file_path}}
        monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))
        return cli.main(["check-edit"])

    def test_non_backlog_file_ignored(self, seeded_repo: Path, monkeypatch):
        """backlog_외_파일은_무시"""
        assert self._invoke(monkeypatch, "/repo/src/backend/app.py") == 0

    def test_blocked_when_direct_backlog_edit_breaks_it(self, seeded_repo: Path, monkeypatch):
        """backlog_직접_편집으로_깨지면_차단"""
        path = seeded_repo / "backlog" / "tasks" / "S2-03-problem-concept-relink.yaml"
        path.write_text(
            path.read_text(encoding="utf-8").replace("layer: backend", "layer: frontend"),
            encoding="utf-8",
        )
        assert self._invoke(monkeypatch, str(path)) == 2

    def test_valid_edit_passes(self, seeded_repo: Path, monkeypatch):
        """정상_편집은_통과"""
        path = seeded_repo / "backlog" / "tasks" / "S2-03-problem-concept-relink.yaml"
        assert self._invoke(monkeypatch, str(path)) == 0


class TestReporting:
    def test_status_output_has_current_stage_and_gates(self, seeded_repo: Path, capsys):
        """status_출력에_현재_스테이지와_게이트"""
        assert cli.main(["status"]) == 0
        out = capsys.readouterr().out
        assert "S1" in out
        assert "G-phaiakes9-key" in out

    def test_brief_output_has_next_candidate_and_reminder(self, seeded_repo: Path, capsys):
        """brief_출력에_다음_후보와_리마인드"""
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

    def test_start_creates_remote_claim(self, bare_remote, monkeypatch, capsys):
        """start가_원격_claim을_생성한다"""
        _, clone = bare_remote
        repo = self._seeded_clone(clone, monkeypatch, "session-a")
        [task_id] = self._next_ids(capsys)
        assert cli.main(["start", task_id]) == 0
        assert "원격 claim: ok" in capsys.readouterr().out
        import remote_claims

        claims, status = remote_claims.list_claims(repo)
        assert status == "ok"
        assert [c.task_id for c in claims] == [task_id]

    def test_race_two_sessions_same_task_latecomer_rejected(self, bare_remote, monkeypatch, capsys):
        """레이스_두_세션_같은_태스크는_후발이_거부된다"""
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

    def test_done_releases_remote_claim(self, bare_remote, monkeypatch, capsys):
        """done이_원격_claim을_해제한다"""
        _, clone = bare_remote
        repo = self._seeded_clone(clone, monkeypatch, "session-a")
        [task_id] = self._next_ids(capsys)
        assert cli.main(["start", task_id]) == 0
        assert cli.main(["done", task_id, "--artifact", "PR#1"]) == 0
        import remote_claims

        claims, _ = remote_claims.list_claims(repo)
        assert claims == []

    def test_block_converts_claim_to_block_hold(self, bare_remote, monkeypatch, capsys):
        """block이_착수_claim을_차단_홀드로_전환한다 (HARN-42로 계약 변경)

        **구 계약**: block은 원격 claim을 *해제*했다(`claims == []`).
        **신 계약**: 해제 대신 `kind="block"` 홀드로 **전환**한다.

        왜 바꿨나 — 구 계약은 차단이 보호를 거는 순간 유일한 교차 세션 신호를
        지웠다. 태스크 YAML의 `blocked`는 main에 머지돼야 남에게 보이는데 이
        저장소의 머지 지연은 시간 단위라(CI ~30분 + HARN-32 경합), 그 창에서 타
        세션이 마찰 없이 착수했다(CUR-11 실사고 2026-08-31 — block 00:28 → 타 세션
        claim 00:41 → 구현·머지 완료, 차단은 끝내 발효 못 함).

        구 계약의 *원 의도*("차단된 태스크가 진행 중 점유로 남지 않는다")는
        유지된다 — 아래에서 kind가 더 이상 `claim`이 아님을 함께 확인한다.
        교차 세션 차단 동작 자체는 test_block_hold_cross_session.py가 동결한다.
        """
        _, clone = bare_remote
        repo = self._seeded_clone(clone, monkeypatch, "session-a")
        [task_id] = self._next_ids(capsys)
        assert cli.main(["start", task_id]) == 0
        assert cli.main(["block", task_id, "--reason", "테스트"]) == 0
        import remote_claims

        claims, _ = remote_claims.list_claims(repo, with_meta=True)
        held = [c for c in claims if c.task_id == task_id]
        assert len(held) == 1, "차단 홀드가 원격에 남아야 병렬 세션이 본다"
        assert held[0].kind == "block"
        assert held[0].kind != "claim", "구 의도 유지 — 진행 중 점유로 남지 않는다"

    def test_no_remote_flag_skips_remote(self, bare_remote, monkeypatch, capsys):
        """no_remote_플래그는_원격을_생략한다"""
        _, clone = bare_remote
        repo = self._seeded_clone(clone, monkeypatch, "session-a")
        [task_id] = self._next_ids(capsys)
        assert cli.main(["start", task_id, "--no-remote"]) == 0
        assert "원격 claim: disabled" in capsys.readouterr().out
        import remote_claims

        claims, _ = remote_claims.list_claims(repo)
        assert claims == []

    def test_start_proceeds_without_remote_fail_open(self, seeded_repo: Path, capsys):
        """원격_없어도_start는_진행된다_fail_open"""
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

    def test_claims_reap_cleans_orphan_refs(self, bare_remote, monkeypatch, capsys):
        """claims_reap_고아_ref_청소"""
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


class TestReadSideFallback:
    """HARN-07 — CAS claim이 막힌 환경의 읽기측 교차 세션 탐지 폴백.

    사고(2026-07-27): 이 실행 환경의 git 프록시가 `refs/claims/*` push를 403 거부해
    CAS claim이 *한 번도* 성공하지 못했고, fail-open이 모든 start를 통과시켜 두 세션이
    OPS-07을 병렬 구현했다. 아래 테스트는 그 환경(CAS 실패)만 시임으로 재현하고,
    **읽기 경로는 진짜 로컬 원격에서 실제 git fetch/show로** 검증한다.
    """

    TASK_ID = "T7-01-readside-fallback"

    def _seeded_clone(self, clone, monkeypatch, name: str) -> Path:
        repo = clone(name)
        monkeypatch.chdir(repo)
        assert cli.main(["seed"]) == 0
        # 태스크 정의는 실환경에서 git으로 전 세션에 공유된다 — 각 클론에 동일 정의를 둔다
        assert (
            cli.main(
                [
                    "add",
                    "--id",
                    self.TASK_ID,
                    "--title",
                    "읽기측 폴백 대상",
                    "--track",
                    "math-completion",
                    "--stage",
                    "S1",
                ]
            )
            == 0
        )
        return repo

    def _push_branch(self, repo: Path, branch: str) -> None:
        """현재 backlog 상태를 원격 브랜치로 push — 타 세션이 push한 상태 재현."""
        for argv in (
            ["checkout", "-q", "-B", branch],
            ["add", "."],
            ["commit", "-q", "-m", "claim"],
            ["push", "--quiet", "-u", "origin", branch],
        ):
            subprocess.run(["git", *argv], cwd=repo, check=True, capture_output=True)

    def _force_cas_failure(self, monkeypatch, status: str = "error") -> None:
        """CAS claim만 실패시킨다 — 프록시 403 환경 재현(읽기 경로는 진짜)."""
        import remote_claims

        monkeypatch.setattr(
            remote_claims,
            "claim",
            lambda *a, **k: remote_claims.ClaimResult(
                status, message="RPC failed; HTTP 403 curl 22 The requested URL returned error: 403"
            ),
        )

    def _spy_scan(self, monkeypatch) -> list[tuple]:
        """읽기측 탐지 호출 기록기 — '호출하지 않음' 계약 검증용."""
        import remote_claims

        calls: list[tuple] = []

        def spy(root, task_id, session, **kwargs):
            calls.append((task_id, session))
            return remote_claims.ScanResult("ok")

        monkeypatch.setattr(remote_claims, "scan_remote_in_progress", spy)
        return calls

    def _events(self, repo: Path) -> list[dict]:
        raw = _all_events_text(repo)
        return [json.loads(line) for line in raw.splitlines() if line.strip()]

    def test_cas_success_skips_readside_scan(self, bare_remote, monkeypatch, capsys):
        """CAS_성공이면_읽기측_탐지를_호출하지_않는다"""
        # 폴백은 CAS 실패 시에만 — 성공 경로에서 전체 브랜치 fetch(~5초)를 물면 안 된다
        _, clone = bare_remote
        self._seeded_clone(clone, monkeypatch, "session-a")
        calls = self._spy_scan(monkeypatch)
        assert cli.main(["start", self.TASK_ID]) == 0
        assert "원격 claim: ok" in capsys.readouterr().out
        assert calls == []

    def test_no_remote_skips_fallback_too(self, bare_remote, monkeypatch, capsys):
        """no_remote는_폴백도_건너뛴다"""
        _, clone = bare_remote
        self._seeded_clone(clone, monkeypatch, "session-a")
        self._force_cas_failure(monkeypatch)
        calls = self._spy_scan(monkeypatch)
        assert cli.main(["start", self.TASK_ID, "--no-remote"]) == 0
        assert "원격 claim: disabled" in capsys.readouterr().out
        assert calls == []

    def test_cas_failure_other_session_in_progress_start_rejected(
        self, bare_remote, monkeypatch, capsys
    ):
        """CAS_실패_타세션이_in_progress면_착수_거부"""
        # 사고 그대로의 재현: 두 세션이 같은 태스크를 잡되 CAS는 상시 실패한다
        _, clone = bare_remote
        repo_a = self._seeded_clone(clone, monkeypatch, "session-a")
        assert cli.main(["start", self.TASK_ID]) == 0
        self._push_branch(repo_a, "claude/session-a")

        repo_b = self._seeded_clone(clone, monkeypatch, "session-b")
        self._force_cas_failure(monkeypatch)
        capsys.readouterr()
        assert cli.main(["start", self.TASK_ID]) == 1
        err = capsys.readouterr().err
        assert "착수 거부" in err
        assert "claude/session-a" in err  # 어느 브랜치·어느 세션인지 명시
        assert "--no-remote" in err  # 본인 것이 확실할 때의 우회 경로 안내
        assert "부분" in err  # 한계(CAS 대체 아님) 고지
        # 거부 시 로컬 상태는 불변 — 대장 오염 없음
        backlog, _ = store.load_backlog(repo_b)
        assert backlog.tasks[self.TASK_ID].status == "todo"
        # 탐지는 이벤트로 남는다 (측정 가능)
        conflicts = [
            e for e in self._events(repo_b) if e.get("action") == "claim_readside_conflict"
        ]
        assert conflicts and conflicts[-1]["id"] == self.TASK_ID
        assert "claude/session-a:claude/session-a" in conflicts[-1]["holders"]

    def test_cas_failure_no_conflict_proceeds_with_partial_protection_notice(
        self, bare_remote, monkeypatch, capsys
    ):
        """CAS_실패_충돌_없으면_진행하고_부분방어임을_고지한다"""
        _, clone = bare_remote
        repo = self._seeded_clone(clone, monkeypatch, "session-a")
        self._force_cas_failure(monkeypatch)
        capsys.readouterr()
        assert cli.main(["start", self.TASK_ID]) == 0
        captured = capsys.readouterr()
        assert "중복 in_progress 없음" in captured.err
        assert "부분" in captured.err  # 과장 금지 — 한계를 매번 말한다
        backlog, _ = store.load_backlog(repo)
        assert backlog.tasks[self.TASK_ID].status == "in_progress"

    def test_cas_failure_own_session_in_progress_allows_proceeding(
        self, bare_remote, monkeypatch, capsys
    ):
        """CAS_실패_내_세션의_in_progress는_진행_허용"""
        # 자기 claim을 자기가 막으면 안 된다 (브랜치를 이미 push한 세션의 재진입)
        _, clone = bare_remote
        repo_a = self._seeded_clone(clone, monkeypatch, "session-a")
        assert cli.main(["start", self.TASK_ID, "--session", "claude/session-b"]) == 0
        self._push_branch(repo_a, "claude/session-b")  # session 필드 = claude/session-b

        self._seeded_clone(clone, monkeypatch, "session-b")
        self._force_cas_failure(monkeypatch)
        capsys.readouterr()
        assert cli.main(["start", self.TASK_ID]) == 0
        assert "중복 in_progress 없음" in capsys.readouterr().err

    def test_fallback_failure_states_no_protection_and_fail_opens(
        self, bare_remote, monkeypatch, capsys
    ):
        """폴백까지_실패하면_보호없음을_명시하고_fail_open"""
        import remote_claims

        _, clone = bare_remote
        repo = self._seeded_clone(clone, monkeypatch, "session-a")
        self._force_cas_failure(monkeypatch)
        original = remote_claims._git

        def fake_git(root, *argv, **kwargs):
            if argv and argv[0] == "fetch" and any("refs/heads" in a for a in argv):
                return subprocess.CompletedProcess(
                    ["git", *argv],
                    128,
                    stdout="",
                    stderr="fatal: unable to access origin: HTTP 403",
                )
            return original(root, *argv, **kwargs)

        monkeypatch.setattr(remote_claims, "_git", fake_git)
        capsys.readouterr()
        assert cli.main(["start", self.TASK_ID]) == 0  # fail-open — 볼모 금지
        captured = capsys.readouterr()
        # 침묵 실패 금지 — '보호가 전혀 없다'를 사용자가 읽을 수 있어야 한다
        assert "중복 착수 보호가 전혀 없습니다" in captured.err
        assert "403" in captured.err  # 원인도 함께
        unavailable = [
            e for e in self._events(repo) if e.get("action") == "claim_readside_unavailable"
        ]
        assert unavailable and unavailable[-1]["id"] == self.TASK_ID


class TestReadSideStaleHandling:
    """HARN-08 — 읽기측 폴백의 stale 과탐 처리 (규칙 A·B) + 태스크 단위 우회(규칙 C).

    HARN-07 종단 실측에서 머지·폐기된 브랜치에 남은 `in_progress`가 그 태스크를
    영구 차단했다(우회는 보호 전체를 끄는 `--no-remote`뿐). 여기서는 CAS 실패
    환경만 시임으로 재현하고 트렁크·브랜치 상태는 진짜 로컬 원격에 심는다.
    """

    TASK_ID = "T8-01-stale-holder"

    def _add_task(self, repo: Path) -> None:
        assert (
            cli.main(
                [
                    "add",
                    "--id",
                    self.TASK_ID,
                    "--title",
                    "stale 홀더 대상",
                    "--track",
                    "math-completion",
                    "--stage",
                    "S1",
                ]
            )
            == 0
        )

    def _seeded_clone(self, clone, monkeypatch, name: str) -> Path:
        repo = clone(name)
        monkeypatch.chdir(repo)
        assert cli.main(["seed"]) == 0
        self._add_task(repo)
        return repo

    def _seed_trunk(self, clone, monkeypatch, status: str, session: str | None = None) -> Path:
        """origin/main에 이 태스크 사본을 특정 status로 심는다 (규칙 A·B 신호원)."""
        repo = clone("trunk-writer")
        monkeypatch.chdir(repo)
        assert cli.main(["seed"]) == 0
        self._add_task(repo)
        backlog, _ = store.load_backlog(repo)
        task = backlog.tasks[self.TASK_ID]
        task.status = status
        task.session = session
        task.artifacts = ["PR#trunk"] if status == "done" else []
        store.save_task(repo, task)
        for argv in (
            ["checkout", "-q", "main"],
            ["add", "."],
            ["commit", "-q", "-m", f"trunk {status}"],
            ["push", "--quiet", "origin", "main"],
        ):
            subprocess.run(["git", *argv], cwd=repo, check=True, capture_output=True)
        return repo

    def _push_holder_branch(self, clone, monkeypatch, name: str) -> Path:
        """타 세션이 in_progress를 push한 상태를 만든다."""
        repo = self._seeded_clone(clone, monkeypatch, name)
        assert cli.main(["start", self.TASK_ID, "--no-remote"]) == 0
        for argv in (
            ["checkout", "-q", "-B", f"claude/{name}"],
            ["add", "."],
            ["commit", "-q", "-m", "claim"],
            ["push", "--quiet", "-u", "origin", f"claude/{name}"],
        ):
            subprocess.run(["git", *argv], cwd=repo, check=True, capture_output=True)
        return repo

    def _force_cas_failure(self, monkeypatch) -> None:
        import remote_claims

        monkeypatch.setattr(
            remote_claims,
            "claim",
            lambda *a, **k: remote_claims.ClaimResult("error", message="RPC failed; HTTP 403"),
        )

    def _events(self, repo: Path) -> list[dict]:
        raw = _all_events_text(repo)
        return [json.loads(line) for line in raw.splitlines() if line.strip()]

    def _setup(
        self,
        clone,
        monkeypatch,
        trunk_status: str | None,
        trunk_session: str | None = None,
        holder: bool = True,
    ) -> Path:
        """내 세션(B) → 홀더 브랜치(A) → 트렁크 착륙 순으로 재현하고 B로 복귀.

        B를 **먼저** 클론하는 것이 핵심이다 — 트렁크에 done이 착륙하기 *전에* 분기한
        장수 브랜치가 실제 과탐 피해자이며(로컬 사본은 여전히 todo), 착륙 후 분기한
        세션은 로컬 status만으로 전이 거부되어 읽기측까지 오지도 않는다.
        """
        repo_b = self._seeded_clone(clone, monkeypatch, "session-b")
        if holder:
            self._push_holder_branch(clone, monkeypatch, "session-a")
        if trunk_status is not None:
            self._seed_trunk(clone, monkeypatch, trunk_status, session=trunk_session)
        monkeypatch.chdir(repo_b)
        self._force_cas_failure(monkeypatch)
        return repo_b

    def test_rule_a_trunk_done_allows_start_and_reports_exclusion_reason(
        self, bare_remote, monkeypatch, capsys
    ):
        """규칙A_트렁크가_done이면_착수를_허용하고_제외사유를_보고한다"""
        _, clone = bare_remote
        repo_b = self._setup(clone, monkeypatch, "done")
        capsys.readouterr()
        assert cli.main(["start", self.TASK_ID]) == 0  # 영구 차단 해소
        err = capsys.readouterr().err
        assert "stale 홀더" in err  # 조용히 버리지 않는다
        assert "trunk_done" in err
        assert "claude/session-a" in err  # 무엇을 제외했는지 명시
        backlog, _ = store.load_backlog(repo_b)
        assert backlog.tasks[self.TASK_ID].status == "in_progress"
        skipped = [
            e for e in self._events(repo_b) if e.get("action") == "claim_readside_stale_skipped"
        ]
        assert skipped and "claude/session-a:trunk_done" in skipped[-1]["skipped"]

    def test_rule_a_inverse_trunk_todo_still_blocks(self, bare_remote, monkeypatch, capsys):
        """규칙A_역_트렁크가_todo면_여전히_차단한다"""
        # 규칙 A가 보호를 과잉 무력화하면 안 된다 (착륙하지 않은 태스크)
        _, clone = bare_remote
        repo_b = self._setup(clone, monkeypatch, "todo")
        capsys.readouterr()
        assert cli.main(["start", self.TASK_ID]) == 1
        err = capsys.readouterr().err
        assert "착수 거부" in err
        assert "claude/session-a" in err
        assert "--ignore-remote-claim" in err  # 세분 우회 경로 안내
        backlog, _ = store.load_backlog(repo_b)
        assert backlog.tasks[self.TASK_ID].status == "todo"

    def test_rule_b_trunk_residual_in_progress_is_not_a_holder(
        self, bare_remote, monkeypatch, capsys
    ):
        """규칙B_트렁크의_잔존_in_progress는_홀더가_아니다"""
        # done 미기입 머지로 main에 in_progress가 남은 상태 (실측 OPS-07 사례)
        _, clone = bare_remote
        self._setup(
            clone, monkeypatch, "in_progress", trunk_session="claude/merged-session", holder=False
        )
        capsys.readouterr()
        assert cli.main(["start", self.TASK_ID]) == 0
        err = capsys.readouterr().err
        assert "trunk_not_session" in err
        assert "main" in err

    def test_rule_c_flag_ignores_only_this_task_and_warns_what_is_skipped(
        self, bare_remote, monkeypatch, capsys
    ):
        """규칙C_플래그는_이_태스크만_무시하고_포기항목을_경고한다"""
        _, clone = bare_remote
        repo_b = self._setup(clone, monkeypatch, "todo")  # 규칙 A 미적용 = 실 홀더
        capsys.readouterr()
        assert cli.main(["start", self.TASK_ID, "--ignore-remote-claim"]) == 0
        captured = capsys.readouterr()
        assert "--ignore-remote-claim" in captured.err
        assert "포기하는 것" in captured.err  # 침묵 실패 금지
        assert "claude/session-a" in captured.err  # 무엇을 무시했는지
        # 무시했으면서 '중복 없음'이라고 말하면 거짓말이다
        assert "중복 in_progress 없음" not in captured.err
        assert "+ignored" in captured.out
        ignored = [e for e in self._events(repo_b) if e.get("action") == "claim_readside_ignored"]
        assert ignored and ignored[-1]["id"] == self.TASK_ID
        assert "claude/session-a:claude/session-a" in ignored[-1]["holders"]

    def test_rule_c_does_not_disable_protection_for_other_tasks(
        self, bare_remote, monkeypatch, capsys
    ):
        """규칙C는_다른_태스크의_보호를_끄지_않는다"""
        # 세분 우회 — 플래그를 쓴 태스크 외에는 그대로 차단돼야 한다
        _, clone = bare_remote
        other = "T8-02-other-stale"
        repo_a = self._push_holder_branch(clone, monkeypatch, "session-a")
        monkeypatch.chdir(repo_a)
        assert (
            cli.main(
                [
                    "add",
                    "--id",
                    other,
                    "--title",
                    "다른 태스크",
                    "--track",
                    "math-completion",
                    "--stage",
                    "S1",
                ]
            )
            == 0
        )
        assert cli.main(["start", other, "--no-remote"]) == 0
        for argv in (
            ["add", "."],
            ["commit", "-q", "-m", "claim2"],
            ["push", "--quiet", "origin", "claude/session-a"],
        ):
            subprocess.run(["git", *argv], cwd=repo_a, check=True, capture_output=True)

        repo_b = self._seeded_clone(clone, monkeypatch, "session-b")
        assert (
            cli.main(
                [
                    "add",
                    "--id",
                    other,
                    "--title",
                    "다른 태스크",
                    "--track",
                    "math-completion",
                    "--stage",
                    "S1",
                ]
            )
            == 0
        )
        self._force_cas_failure(monkeypatch)
        capsys.readouterr()
        assert cli.main(["start", self.TASK_ID, "--ignore-remote-claim"]) == 0
        capsys.readouterr()
        assert cli.main(["start", other]) == 1  # 다른 태스크는 여전히 차단
        assert "착수 거부" in capsys.readouterr().err
        backlog, _ = store.load_backlog(repo_b)
        assert backlog.tasks[other].status == "todo"

    def test_rule_c_does_not_ignore_cas_conflict(self, bare_remote, monkeypatch, capsys):
        """규칙C는_CAS_conflict를_무시하지_않는다"""
        # 확정 신호(CAS)는 우회 대상이 아니다 — 플래그의 사정거리를 명시한다
        _, clone = bare_remote
        self._seeded_clone(clone, monkeypatch, "session-a")
        assert cli.main(["start", self.TASK_ID]) == 0
        self._seeded_clone(clone, monkeypatch, "session-b")
        capsys.readouterr()
        assert cli.main(["start", self.TASK_ID, "--ignore-remote-claim"]) == 1
        err = capsys.readouterr().err
        assert "이미 원격 claim" in err
        assert "읽기측" in err

    def test_rule_c_states_no_effect_when_nothing_to_ignore(self, bare_remote, monkeypatch, capsys):
        """규칙C_무시할_판정이_없으면_효과없음을_말한다"""
        _, clone = bare_remote
        repo = self._seeded_clone(clone, monkeypatch, "session-a")
        self._force_cas_failure(monkeypatch)
        capsys.readouterr()
        assert cli.main(["start", self.TASK_ID, "--ignore-remote-claim"]) == 0
        err = capsys.readouterr().err
        assert "효과 없음" in err
        assert not [e for e in self._events(repo) if e.get("action") == "claim_readside_ignored"]


class TestStartOverlapPreflight:
    """start 프리플라이트 — in-flight 태스크와 paths 겹침 검사 (warn→block 단계적)."""

    def _add_two_overlapping(self, capsys) -> tuple[str, str]:
        assert (
            cli.main(
                [
                    "add",
                    "--id",
                    "T9-01-overlap-a",
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
                    "T9-02-overlap-b",
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
        capsys.readouterr()
        return "T9-01-overlap-a", "T9-02-overlap-b"

    def test_warn_mode_warns_then_proceeds(self, seeded_repo: Path, capsys):
        """warn_모드_경고_후_진행"""
        a, b = self._add_two_overlapping(capsys)
        assert cli.main(["start", a, "--session", "claude/other", "--no-remote"]) == 0
        capsys.readouterr()
        assert cli.main(["start", b, "--session", "claude/me", "--no-remote"]) == 0
        err = capsys.readouterr().err
        assert "파일 범위 겹침" in err
        # policy_warn 이벤트가 측정용으로 적재된다
        events = _all_events_text(seeded_repo)
        assert '"action": "policy_warn"' in events
        assert '"rule": "path_overlap"' in events

    def test_block_mode_start_rejected(self, seeded_repo: Path, capsys):
        """block_모드_착수_거부"""
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

    def test_task_without_declared_paths_excluded_from_overlap_check(
        self, seeded_repo: Path, capsys
    ):
        """paths_미선언_태스크는_겹침_검사_제외"""
        capsys.readouterr()
        assert cli.main(["next", "--n", "1", "--json", "--no-remote"]) == 0
        task_id = json.loads(capsys.readouterr().out)[0]["id"]
        assert cli.main(["start", task_id, "--session", "claude/me", "--no-remote"]) == 0
        assert "paths 미선언" in capsys.readouterr().err  # 선언 권장 안내


class TestTodoOverlapDetection:
    """HARN-29 — todo 태스크끼리도 파일 범위 겹침을 검출해야 한다."""

    PATHS = [".github/workflows/ci.yml", "tests/infra/**"]

    def _add_todo(self, capsys, task_id: str, title: str) -> None:
        assert (
            cli.main(
                [
                    "add",
                    "--id",
                    task_id,
                    "--title",
                    title,
                    "--track",
                    "infra-debt",
                    "--stage",
                    "S3",
                    "--subject",
                    "cross",
                    "--layer",
                    "infra",
                    "--path",
                    self.PATHS[0],
                    "--path",
                    self.PATHS[1],
                ]
            )
            == 0
        )
        capsys.readouterr()

    def test_overlap_command_detects_todo_duplicates(self, seeded_repo: Path, capsys):
        """overlap 명령이 todo끼리 겹침을 검출한다(기본: todo 포함)."""
        self._add_todo(capsys, "T9-11-todo-a", "todo 겹침 A")
        self._add_todo(capsys, "T9-12-todo-b", "todo 겹침 B")
        capsys.readouterr()

        assert cli.main(["overlap", "T9-11-todo-a"]) == 0
        out = capsys.readouterr().out
        assert "T9-12-todo-b" in out
        assert "프리픽스 포함" in out  # pathscope.overlap이 실제 교집합/포함을 출력

    def test_overlap_command_in_flight_only_excludes_todos(self, seeded_repo: Path, capsys):
        """--in-flight-only 플래그가 todo를 제외하고 기존 동작을 보존한다."""
        self._add_todo(capsys, "T9-13-todo-a", "todo 겹침 A")
        self._add_todo(capsys, "T9-14-todo-b", "todo 겹침 B")
        capsys.readouterr()

        assert cli.main(["overlap", "T9-13-todo-a", "--in-flight-only"]) == 0
        out = capsys.readouterr().out
        assert "T9-14-todo-b" not in out
        assert "in-flight" in out

    def test_add_warns_when_paths_overlap_with_existing_todo(self, seeded_repo: Path, capsys):
        """add가 기존 todo와 paths 겹치면 경고하지만 등록은 허용한다."""
        self._add_todo(capsys, "T9-15-todo-a", "todo 겹침 A")
        assert (
            cli.main(
                [
                    "add",
                    "--id",
                    "T9-16-todo-b",
                    "--title",
                    "todo 겹침 B",
                    "--track",
                    "infra-debt",
                    "--stage",
                    "S3",
                    "--subject",
                    "cross",
                    "--layer",
                    "infra",
                    "--path",
                    self.PATHS[1],  # wildcard path로 프리픽스 포함 검출
                ]
            )
            == 0
        )
        err = capsys.readouterr().err
        assert "파일 범위 겹침" in err
        assert "T9-15-todo-a" in err
        backlog, _ = store.load_backlog(seeded_repo)
        assert backlog.tasks["T9-16-todo-b"].status == "todo"  # 경고만, 차단 아님

    def test_start_blocked_by_inflight_but_warns_about_todo(self, seeded_repo: Path, capsys):
        """block 모드에서 in-flight와 겹치면 차단, 동시에 todo 겹침도 경고한다."""
        import store as store_mod
        from models import Policy

        store_mod.save_policy(seeded_repo, Policy(path_overlap="block"))
        self._add_todo(capsys, "T9-17-todo-a", "todo 겹침 A")
        self._add_todo(capsys, "T9-18-todo-b", "todo 겹침 B")
        assert cli.main(["start", "T9-17-todo-a", "--session", "claude/a", "--no-remote"]) == 0
        capsys.readouterr()

        assert cli.main(["start", "T9-18-todo-b", "--session", "claude/b", "--no-remote"]) == 1
        err = capsys.readouterr().err
        assert "착수 거부" in err
        assert "T9-17-todo-a" in err


class TestCheckEditPolicy:
    """check-edit 훅의 조율 정책 3분기 — scope_drift·path_overlap·adhoc_edit."""

    def _invoke(self, monkeypatch, file_path: str) -> int:
        payload = {"tool_input": {"file_path": file_path}}
        monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))
        return cli.main(["check-edit"])

    def _on_branch(self, repo: Path, name: str) -> None:
        subprocess.run(["git", "checkout", "-q", "-b", name], cwd=repo, check=True)

    def test_main_branch_all_pass(self, seeded_repo: Path, monkeypatch):
        """main_브랜치는_전부_통과"""
        assert self._invoke(monkeypatch, str(seeded_repo / "src" / "x.py")) == 0

    def test_adhoc_edit_code_edit_without_claim_warns(self, seeded_repo: Path, monkeypatch, capsys):
        """adhoc_edit_claim_없이_코드_편집_경고"""
        self._on_branch(seeded_repo, "claude/adhoc-session")
        code = self._invoke(monkeypatch, str(seeded_repo / "src" / "backend" / "app.py"))
        assert code == 0  # warn 모드 — 차단하지 않음
        assert "adhoc_edit" in capsys.readouterr().err

    def test_adhoc_edit_non_code_file_not_applicable(self, seeded_repo: Path, monkeypatch, capsys):
        """adhoc_edit_비코드_파일은_해당_없음"""
        self._on_branch(seeded_repo, "claude/adhoc-session")
        assert self._invoke(monkeypatch, str(seeded_repo / "MEMORY.md")) == 0
        assert "adhoc_edit" not in capsys.readouterr().err

    def test_scope_drift_edit_outside_declared_scope_warns(
        self, seeded_repo: Path, monkeypatch, capsys
    ):
        """scope_drift_선언_범위_밖_편집_경고"""
        self._on_branch(seeded_repo, "claude/drift-session")
        assert (
            cli.main(
                [
                    "add",
                    "--id",
                    "T9-03-scoped-task",
                    "--title",
                    "범위 태스크",
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
        assert cli.main(["start", "T9-03-scoped-task", "--no-remote"]) == 0
        capsys.readouterr()
        # 선언 범위 안 — 조용히 통과
        assert self._invoke(monkeypatch, str(seeded_repo / "src/backend/api/routes.py")) == 0
        assert "scope_drift" not in capsys.readouterr().err
        # 선언 범위 밖 — 경고
        assert self._invoke(monkeypatch, str(seeded_repo / "src/mobile/lib/main.dart")) == 0
        assert "scope_drift" in capsys.readouterr().err

    def test_path_overlap_edit_in_other_session_scope_warns(
        self, seeded_repo: Path, monkeypatch, capsys
    ):
        """path_overlap_타_세션_범위_편집_경고"""
        self._on_branch(seeded_repo, "claude/my-session")
        assert (
            cli.main(
                [
                    "add",
                    "--id",
                    "T9-04-other-task",
                    "--title",
                    "남의 태스크",
                    "--track",
                    "math-completion",
                    "--stage",
                    "S1",
                    "--path",
                    "src/data-pipeline/**",
                ]
            )
            == 0
        )
        assert (
            cli.main(
                ["start", "T9-04-other-task", "--session", "claude/other-session", "--no-remote"]
            )
            == 0
        )
        capsys.readouterr()
        code = self._invoke(monkeypatch, str(seeded_repo / "src/data-pipeline/crawler.py"))
        assert code == 0  # warn 모드
        err = capsys.readouterr().err
        assert "path_overlap" in err
        assert "T9-04-other-task" in err

    def test_block_mode_blocks_edit(self, seeded_repo: Path, monkeypatch, capsys):
        """block_모드는_편집을_차단한다"""
        import store as store_mod
        from models import Policy

        store_mod.save_policy(seeded_repo, Policy(adhoc_edit="block"))
        self._on_branch(seeded_repo, "claude/adhoc-session")
        code = self._invoke(monkeypatch, str(seeded_repo / "src" / "backend" / "app.py"))
        assert code == 2

    def test_exception_always_passes_fail_open(self, seeded_repo: Path, monkeypatch):
        """예외_시_무조건_통과_fail_open"""
        self._on_branch(seeded_repo, "claude/failopen-session")
        # 정책 로드가 터져도 훅은 개발을 볼모로 잡지 않는다
        monkeypatch.setattr(
            store, "load_policy", lambda root: (_ for _ in ()).throw(RuntimeError("boom"))
        )
        assert self._invoke(monkeypatch, str(seeded_repo / "src" / "backend" / "app.py")) == 0


class TestPolicyCli:
    def test_policy_show_defaults(self, seeded_repo: Path, capsys):
        """policy_show_기본값"""
        capsys.readouterr()
        assert cli.main(["policy", "show"]) == 0
        out = capsys.readouterr().out
        assert "path_overlap: warn" in out

    def test_policy_report_aggregates_warnings(self, seeded_repo: Path, capsys):
        """policy_report_경고_집계"""
        # 인위적으로 policy_warn 이벤트 적재 후 리포트 확인
        store.append_event(
            seeded_repo, "policy_warn", "-", rule="adhoc_edit", file="src/x.py", mode="warn"
        )
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
        assert (
            cli.main(
                [
                    "add",
                    "--id",
                    "T8-05-cross-a",
                    "--title",
                    "교차 A",
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
        assert (
            cli.main(
                [
                    "add",
                    "--id",
                    "T8-06-cross-b",
                    "--title",
                    "교차 B",
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
        return "T8-05-cross-a", "T8-06-cross-b"

    def test_start_preflight_catches_overlap_with_remote_claimed_task(
        self, bare_remote, monkeypatch, capsys
    ):
        """start_프리플라이트가_원격_claim_태스크와의_겹침을_잡는다"""
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

    def test_check_edit_catches_cross_session_overlap_via_cache(
        self, bare_remote, monkeypatch, capsys
    ):
        """check_edit이_캐시로_교차_세션_겹침을_잡는다"""
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


class TestHumanOwnerLifecycle:
    """HARN-06 — 사람-소유 태스크의 소유자 본인 기입(--as) 왕복.

    S1-14 사례 회귀: owner=kiki 태스크가 CLI로 done 전이 불가능해 YAML 손편집이
    유일한 경로였던 설계 공백(2026-07-16 실측)의 재발 방지.
    """

    def _add_human_task(self, capsys) -> str:
        task_id = "T9-10-human-judgement"
        assert (
            cli.main(
                [
                    "add",
                    "--id",
                    task_id,
                    "--title",
                    "사람 판정",
                    "--track",
                    "math-completion",
                    "--stage",
                    "S1",
                    "--owner",
                    "kiki",
                ]
            )
            == 0
        )
        capsys.readouterr()
        return task_id

    def test_start_without_as_rejected_with_guidance(self, seeded_repo: Path, capsys):
        """as_없이_start_거부_및_안내"""
        task_id = self._add_human_task(capsys)
        assert cli.main(["start", task_id, "--session", "b", "--no-remote"]) == 1
        err = capsys.readouterr().err
        assert "owner" in err
        assert "--as kiki" in err  # 거부→소유자 이관 안내(명령 동봉)

    def test_as_mismatch_rejected(self, seeded_repo: Path, capsys):
        """as_불일치_거부"""
        task_id = self._add_human_task(capsys)
        assert cli.main(["start", task_id, "--as", "partner", "--session", "b", "--no-remote"]) == 1
        err = capsys.readouterr().err
        assert "불일치" in err

    def test_owner_self_start_done_roundtrip(self, seeded_repo: Path, capsys):
        """소유자_본인_start_done_왕복"""
        task_id = self._add_human_task(capsys)
        # 소유자 본인 기입 — start
        assert (
            cli.main(["start", task_id, "--as", "kiki", "--session", "kiki-branch", "--no-remote"])
            == 0
        )
        backlog, _ = store.load_backlog(seeded_repo)
        assert backlog.tasks[task_id].status == "in_progress"
        # done도 --as 필수 (없으면 안내와 함께 거부)
        assert cli.main(["done", task_id, "--artifact", "판정 문서 (#77)"]) == 1
        assert "--as kiki" in capsys.readouterr().err
        # 소유자 본인 기입 — done
        assert cli.main(["done", task_id, "--as", "kiki", "--artifact", "판정 문서 (#77)"]) == 0
        backlog, _ = store.load_backlog(seeded_repo)
        assert backlog.tasks[task_id].status == "done"
        assert "판정 문서 (#77)" in backlog.tasks[task_id].artifacts
        # 이벤트 대장에 as_owner가 남아 claude 기입과 구분된다
        events = _all_events_text(seeded_repo)
        records = [json.loads(line) for line in events.splitlines() if line.strip()]
        human_events = [
            r for r in records if r.get("id") == task_id and r.get("as_owner") == "kiki"
        ]
        assert {r["action"] for r in human_events} == {"start", "done"}

    def test_human_task_never_shown_as_next_candidate(self, seeded_repo: Path, capsys):
        """사람_태스크는_next_후보_불변_미노출"""
        task_id = self._add_human_task(capsys)
        assert cli.main(["next", "--n", "50", "--json", "--no-remote"]) == 0
        ids = [t["id"] for t in json.loads(capsys.readouterr().out)]
        assert task_id not in ids

    def test_as_on_claude_task_rejected_as_mismatch(self, seeded_repo: Path, capsys):
        """owner=claude 태스크에 --as kiki를 주면 불일치로 거부(오용 방지)."""
        assert cli.main(["next", "--n", "1", "--json"]) == 0
        task_id = json.loads(capsys.readouterr().out)[0]["id"]
        assert cli.main(["start", task_id, "--as", "kiki", "--session", "b", "--no-remote"]) == 1
        assert "불일치" in capsys.readouterr().err


class TestUnmergedDoneDetection:
    """HARN-11 — 타 세션이 done 처리했으나 **미머지**인 태스크의 비가시성.

    HARN-08(과탐: 머지된 브랜치의 잔존 in_progress가 착수를 영구 차단)의 **반대 방향**이다.
    done 처리 시 원격 claim은 release돼 대장에서 사라지고, 트렁크 사본은 머지 전까지 todo다
    → claim 대장·로컬 백로그 **양쪽 모두 '가용'** 으로 보인다.

    사고 경위(2026-07-29 근접사고): /drive가 S3-09를 1순위로 계산해 claim까지 진행했으나,
    타 세션이 이미 720문 검수를 마치고 done 처리한 상태였다. 중복 구현 직전 회피.

    읽기 경로는 시임이 아니라 **진짜 로컬 원격에서 실제 git으로** 검증한다.
    """

    TASK_ID = "T11-01-unmerged-done"

    def _seeded_clone(self, clone, monkeypatch, name: str) -> Path:
        repo = clone(name)
        monkeypatch.chdir(repo)
        assert cli.main(["seed"]) == 0
        assert (
            cli.main(
                [
                    "add",
                    "--id",
                    self.TASK_ID,
                    "--title",
                    "미머지 done 대상 — 한국어 제목으로 바이트 정렬까지 검증한다",
                    "--track",
                    "math-completion",
                    "--stage",
                    "S1",
                ]
            )
            == 0
        )
        return repo

    def _push_branch(self, repo: Path, branch: str) -> None:
        for argv in (
            ["checkout", "-q", "-B", branch],
            ["add", "."],
            ["commit", "-q", "-m", "state"],
            ["push", "--quiet", "-u", "origin", branch],
        ):
            subprocess.run(["git", *argv], cwd=repo, check=True, capture_output=True)

    def _finished_elsewhere(self, clone, monkeypatch) -> Path:
        """타 세션이 태스크를 done 처리하고 브랜치를 push한 상태를 만든다."""
        other = self._seeded_clone(clone, monkeypatch, "finisher")
        assert cli.main(["start", self.TASK_ID]) == 0
        assert cli.main(["done", self.TASK_ID, "--artifact", "abc123 (#42)"]) == 0
        self._push_branch(other, "claude/finisher")
        return other

    def test_start_blocks_unmerged_done(self, bare_remote, monkeypatch, capsys):
        """start가_미머지_done을_차단한다"""
        _, clone = bare_remote
        self._finished_elsewhere(clone, monkeypatch)

        mine = self._seeded_clone(clone, monkeypatch, "newcomer")
        assert mine.exists()
        assert cli.main(["start", self.TASK_ID]) == 1
        captured = capsys.readouterr()
        assert "이미" in captured.err and "claude/finisher" in captured.err

    def test_next_excludes_unmerged_done_from_candidates(self, bare_remote, monkeypatch, capsys):
        """next가_미머지_done을_후보에서_제외한다"""
        _, clone = bare_remote
        self._finished_elsewhere(clone, monkeypatch)

        self._seeded_clone(clone, monkeypatch, "newcomer")
        subprocess.run(["git", "fetch", "--quiet", "origin"], cwd=Path.cwd(), check=True)
        capsys.readouterr()  # 셋업(seed·add) 출력을 버리고 next 출력만 본다
        assert cli.main(["next", "--n", "20"]) == 0
        captured = capsys.readouterr()
        assert self.TASK_ID not in captured.out, "완료된 태스크가 후보로 노출되면 안 된다"
        assert "후보 제외" in captured.err and self.TASK_ID in captured.err

    def test_incomplete_task_passes(self, bare_remote, monkeypatch, capsys):
        """미완료_태스크는_통과한다

        변별력 — 진행 중이 아닌 평범한 태스크까지 막으면 게이트가 아니라 고장이다.
        """
        _, clone = bare_remote
        other = self._seeded_clone(clone, monkeypatch, "finisher")
        self._push_branch(other, "claude/finisher")  # todo 상태 그대로 push

        self._seeded_clone(clone, monkeypatch, "newcomer")
        assert cli.main(["start", self.TASK_ID]) == 0

    def test_brief_excludes_unmerged_done_from_candidates(self, bare_remote, monkeypatch, capsys):
        """brief가_미머지_done을_후보에서_제외한다

        HARN-12 — next(HARN-11)의 필터가 브리핑(SessionStart 훅 진입점)에도 배선됐는지.
        """
        _, clone = bare_remote
        self._finished_elsewhere(clone, monkeypatch)

        self._seeded_clone(clone, monkeypatch, "newcomer")
        subprocess.run(["git", "fetch", "--quiet", "origin"], cwd=Path.cwd(), check=True)
        capsys.readouterr()  # 셋업(seed·add) 출력을 버리고 brief 출력만 본다
        assert cli.main(["brief"]) == 0
        captured = capsys.readouterr()
        candidates = captured.out.split("다음 착수 후보")[-1]
        assert self.TASK_ID not in candidates, "완료된 태스크가 브리핑 후보로 노출되면 안 된다"

    def test_brief_not_blocked_by_unmerged_done_filter_failure(
        self, bare_remote, monkeypatch, capsys
    ):
        """brief는_미머지_done_필터_실패에도_막히지_않는다

        변별력 — scan_remote_done이 예외를 던져도 브리핑은 fail-open으로 통과해야 한다.
        """
        import remote_claims

        _, clone = bare_remote
        self._finished_elsewhere(clone, monkeypatch)
        self._seeded_clone(clone, monkeypatch, "newcomer")
        subprocess.run(["git", "fetch", "--quiet", "origin"], cwd=Path.cwd(), check=True)

        def _boom(root, task_ids, **kw):
            raise RuntimeError("원격 불가")

        monkeypatch.setattr(remote_claims, "scan_remote_done", _boom)
        capsys.readouterr()
        assert cli.main(["brief"]) == 0, "필터 실패가 브리핑 자체를 막으면 안 된다(fail-open)"
        captured = capsys.readouterr()
        assert "RuntimeError" in captured.err, "예외를 삼키면 안 된다(무타입 침묵 실패 금지)"
        assert "[빌드하네스 브리핑]" in captured.out  # 정상 브리핑 본문은 그대로 출력됨

    def test_ignore_remote_claim_allows_bypass(self, bare_remote, monkeypatch, capsys):
        """ignore_remote_claim으로_우회_가능하다

        그 브랜치가 폐기된 경우의 탈출구 — 단 무엇을 감수하는지 경고한다.
        """
        _, clone = bare_remote
        self._finished_elsewhere(clone, monkeypatch)

        self._seeded_clone(clone, monkeypatch, "newcomer")
        assert cli.main(["start", self.TASK_ID, "--ignore-remote-claim"]) == 0
        assert "중복 구현 위험" in capsys.readouterr().err


class TestStaleBranchClassificationWiring:
    """brief(cmd_brief)가 active_branches를 실제로 scan_stale_branches에 넘기는지 —
    "장치가 존재함"과 "실제로 배선됨"은 다르다(OPS-10 배선 실재성 패턴). 2026-08-05
    3분류 확장(HARN-13 잔여)의 배선 축.
    """

    def test_brief_passes_remote_claim_branches_as_active_branches(
        self, bare_remote, monkeypatch, capsys
    ):
        """brief가_원격_claim_브랜치를_active_branches로_전달한다"""
        import remote_claims

        _, clone = bare_remote
        other = clone("claimer")
        assert remote_claims.claim(other, "S1-01-claimed", "claude/claimer").status == "ok"

        mine = clone("newcomer")
        monkeypatch.chdir(mine)
        assert cli.main(["seed"]) == 0

        captured_kwargs: dict = {}
        original = remote_claims.scan_stale_branches

        def spy(root, **kwargs):
            captured_kwargs.update(kwargs)
            return original(root, **kwargs)

        monkeypatch.setattr(remote_claims, "scan_stale_branches", spy)
        capsys.readouterr()
        assert cli.main(["brief"]) == 0
        assert "active_branches" in captured_kwargs, "cmd_brief가 active_branches를 안 넘기면 회귀"
        assert "claude/claimer" in captured_kwargs["active_branches"]

    def test_branches_cmd_passes_remote_claim_branches_as_active_branches(
        self, bare_remote, monkeypatch, capsys
    ):
        """branches_CLI도_원격_claim_브랜치를_active_branches로_전달한다

        `cmd_brief`만 넘기고 CI 진입점(`cmd_branches`)이 안 넘기면, **지금 누가 작업
        중인 브랜치가 "🔴 회수 또는 삭제 필요"로 경고된다** — 삭제를 유도하는 오경보다.
        문서(build_harness.md §3b-3)는 4분류라고 말하는데 CI 경로는 3분류만 낼 수 있는
        상태이기도 하다. Codex 리뷰 P1 지적(2026-08-31)으로 발견해 봉인한다.
        """
        import remote_claims

        _, clone = bare_remote
        other = clone("claimer")
        assert remote_claims.claim(other, "S1-01-claimed", "claude/claimer").status == "ok"

        mine = clone("newcomer-branches")
        monkeypatch.chdir(mine)
        assert cli.main(["seed"]) == 0

        captured_kwargs: dict = {}
        original = remote_claims.scan_stale_branches

        def spy(root, **kwargs):
            captured_kwargs.update(kwargs)
            return original(root, **kwargs)

        monkeypatch.setattr(remote_claims, "scan_stale_branches", spy)
        capsys.readouterr()
        cli.main(["branches"])
        assert (
            "active_branches" in captured_kwargs
        ), "cmd_branches가 active_branches를 안 넘기면 회귀"
        assert "claude/claimer" in captured_kwargs["active_branches"]

    def test_branches_cmd_reports_pr_lookup_failure_reason(self, bare_remote, monkeypatch, capsys):
        """branches_CLI가_PR_조회_실패_사유를_화면에_남긴다

        "PR 대조 실패"만 뜨고 사유가 없으면 타임아웃·git 미설치·권한 오류가 운영자에게
        같은 글자로 보인다(CLAUDE.md 침묵 실패 금지 — 예외 타입명 필수).
        """
        import remote_claims

        _, clone = bare_remote
        mine = clone("branches-reason")
        monkeypatch.chdir(mine)
        assert cli.main(["seed"]) == 0

        monkeypatch.setattr(
            remote_claims,
            "scan_stale_branches",
            lambda root, **kwargs: remote_claims.StaleBranchScanResult(
                "ok",
                stale=[],
                pr_lookup_ok=False,
                pr_lookup_error="TimeoutExpired: PR ref 조회 20초 초과",
            ),
        )
        capsys.readouterr()
        assert cli.main(["branches"]) == 2  # 측정 실패는 0(통과)이 아니다
        out = capsys.readouterr().out
        assert "TimeoutExpired" in out, f"실패 사유의 예외 타입명이 화면에 없다: {out!r}"

    def test_brief_forwards_scan_message_to_render(self, bare_remote, monkeypatch, capsys):
        """brief가_스캔_실패_사유를_렌더까지_전달한다

        `remote_claims → cmd_brief → render_brief` 전 구간 배선. 스캐너가 사유를
        만들어도 호출부가 안 넘기면 화면에는 여전히 사유 없는 "판정 보류"만 뜬다 —
        "장치 존재 ≠ 배선"(OPS-10). 2026-08-11 shallow 사고의 복구 명령 노출 축.
        """
        import remote_claims
        import report

        _, clone = bare_remote
        mine = clone("brief-message")
        monkeypatch.chdir(mine)
        assert cli.main(["seed"]) == 0

        monkeypatch.setattr(
            remote_claims,
            "scan_stale_branches",
            lambda root, **kwargs: remote_claims.StaleBranchScanResult(
                "shallow", message=remote_claims.SHALLOW_PENDING_MESSAGE
            ),
        )
        captured_kwargs: dict = {}
        original_render = report.render_brief

        def spy(*args, **kwargs):
            captured_kwargs.update(kwargs)
            return original_render(*args, **kwargs)

        monkeypatch.setattr(report, "render_brief", spy)
        capsys.readouterr()
        assert cli.main(["brief"]) == 0

        assert captured_kwargs.get("stale_branch_status") == "shallow"
        assert "--unshallow" in captured_kwargs.get("stale_branch_message", "")
        out = capsys.readouterr().out
        assert "판정 보류" in out
        assert "--unshallow" in out
        assert "미해결 장기 미머지 브랜치" not in out


class TestBatchBlobParsing:
    """HARN-11 — `git cat-file --batch` 출력 파싱의 바이트 정렬.

    `<size>`는 문자 수가 아니라 **바이트 수**다. 이 저장소의 태스크 YAML은 한국어라
    문자 길이로 세면 헤더 위치가 밀려 결과가 **엉뚱한 브랜치에 붙는다** — 2026-07-29
    실측으로 잡았다(S3-09의 done 보유 브랜치를 problem-bank 대신 teaching-strategy로 오보고).
    """

    def _batch_output(self, bodies: list[str | None]) -> str:
        out = []
        for body in bodies:
            if body is None:
                out.append("deadbeef:some/path missing\n")
            else:
                size = len(body.encode("utf-8"))
                out.append(f"{'a' * 40} blob {size}\n{body}\n")
        return "".join(out)

    def test_korean_body_mixed_in_still_ordered_by_request_order(self):
        """한국어_본문이_섞여도_요청_순서대로_정렬된다"""
        import remote_claims

        bodies = [
            "status: todo\ntitle: 한국어 제목 — 멀티바이트\n",
            None,
            "status: done\ntitle: 두 번째 한국어 본문\n",
            "status: in_progress\n",
        ]
        parsed = list(remote_claims._iter_batch_blobs(self._batch_output(bodies)))
        assert len(parsed) == len(bodies), "요청 1건당 정확히 1개를 내야 zip 정렬이 유지된다"
        assert parsed[1] is None
        assert remote_claims._top_level_field(parsed[0], "status") == "todo"
        assert remote_claims._top_level_field(parsed[2], "status") == "done"
        assert remote_claims._top_level_field(parsed[3], "status") == "in_progress"

    def test_ascii_only_behaves_identically(self):
        """ascii_전용에서도_동일하다"""
        import remote_claims

        bodies = ["status: done\n", "status: todo\n"]
        parsed = list(remote_claims._iter_batch_blobs(self._batch_output(bodies)))
        assert [remote_claims._top_level_field(p, "status") for p in parsed] == ["done", "todo"]
