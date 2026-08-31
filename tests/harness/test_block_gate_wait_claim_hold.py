"""HARN-45 — 게이트 대기와 차단을 claim 소유권으로 가른다.

배경(2026-08-31 실사례): '사람 게이트 대기'와 '차단'은 의미가 반대다 — 전자는 *같은
세션이 게이트 해소 후 이어받아야* 하고, 후자는 *다른 세션이 맡을 수 있어야* 한다.
그런데 구 `cmd_block`은 둘 다 `blocked`로 표현하며 **무조건 claim을 반납**했다.

그 결과가 실제 사고다. HARN-38이 입력 부재로 사람 게이트를 신설하고 block하자 claim이
풀렸고, **55초 뒤** 다른 세션이 같은 태스크를 claim해 같은 일을 병렬 수행했다
(2026-08-31T05:00:05Z 실측). 게이트 해소 후 원 세션의 재claim은 CAS 충돌로 거부됐다.

**로컬 status로는 막을 수 없다**는 점이 이 파일의 설계 전제다: 다른 세션은 *자기
클론의* 백로그 사본을 보므로, 이쪽 브랜치의 `blocked`는 머지 전까지 그쪽 눈에
보이지 않는다(그쪽에서 태스크는 여전히 `todo`다). 교차 세션에서 실효를 갖는 신호는
**원격 claim 대장 하나뿐**이다. 그래서 테스트는 전부 진짜 원격(`bare_remote`)과 독립
클론으로 *교차 세션*을 재현한다 — 한 클론 안에서 status만 확인하면 이 사고를 재현조차
할 수 없다.

변별력은 **양방향**이다(acceptance ②). 자리 보전만 검증하면 "아무도 못 집어간다"는
반대 결함(인계 불가)을 놓친다.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import remote_claims
import store

import backlog as cli


def _add_task(task_id: str, gates: list[str] | None = None) -> int:
    argv = [
        "add",
        "--id",
        task_id,
        "--title",
        "게이트 대기 claim 보전 테스트",
        "--track",
        "math-completion",
        "--stage",
        "S2",
    ]
    for gid in gates or []:
        argv += ["--gates", gid]
    return cli.main(argv)


def _register_gate(gate_id: str) -> None:
    assert (
        cli.main(["gates", "add", gate_id, "--title", "테스트용 사람 게이트", "--kind", "human"])
        == 0
    )


def _attach_gate_midflight(repo: Path, task_id: str, gate_id: str) -> None:
    """착수 *후*에 게이트를 태스크에 연결한다 — 이 플래그의 유일한 실제 경로.

    `start`는 미해소 게이트가 있는 태스크를 거부하므로(기존 가드), `--gate-wait`가
    성립하는 상황은 **착수한 뒤에 막히는 사유가 발견되어 게이트를 신설**하는 흐름뿐이다.
    HARN-38이 정확히 그랬다 — 입력이 미push 브랜치에만 있음을 착수 후에 알았고,
    그때 `G-cur16-branch-push`를 만들어 붙였다.

    `requires_gates` 갱신 CLI가 아직 없어(그 CLI가 곧 `HARN-24`) 실사용도 YAML 직접
    편집이며, 여기서도 store 경유로 같은 일을 한다 — 우회가 아니라 경로 부재다.
    """
    backlog, _ = store.load_backlog(repo)
    task = backlog.tasks[task_id]
    task.requires_gates = [*task.requires_gates, gate_id]
    store.save_task(repo, task)


def _publish(repo: Path, branch: str, message: str) -> None:
    """이 세션의 대장 변경을 원격에 올린다 — 타 세션이 보는 것은 *머지된* 사본뿐이지만,
    이 테스트가 겨누는 것은 대장이 아니라 claim이므로 브랜치 push로 충분하다."""
    for argv in (
        ["add", "."],
        ["commit", "-q", "-m", message],
        ["push", "--quiet", "-u", "origin", branch],
    ):
        subprocess.run(["git", *argv], cwd=repo, check=True, capture_output=True)


class TestGateWaitHoldsClaim:
    """`block --gate-wait` = 자리 보전 (acceptance ①·②의 보전 축)."""

    def test_gate_wait_keeps_remote_claim_and_session(self, bare_remote, monkeypatch, capsys):
        """게이트대기는_원격claim과_session을_유지한다"""
        _, clone = bare_remote
        owner = clone("owner")
        monkeypatch.chdir(owner)
        assert cli.main(["seed"]) == 0
        assert _add_task("S9-10-gate-wait") == 0
        assert cli.main(["start", "S9-10-gate-wait"]) == 0
        _register_gate("G-test-human-action")
        _attach_gate_midflight(owner, "S9-10-gate-wait", "G-test-human-action")

        claims, status = remote_claims.list_claims(owner)
        assert status == "ok" and any(c.task_id == "S9-10-gate-wait" for c in claims)

        capsys.readouterr()
        assert (
            cli.main(["block", "S9-10-gate-wait", "--reason", "사람 행동 대기", "--gate-wait"]) == 0
        )

        backlog, _ = store.load_backlog(owner)
        task = backlog.tasks["S9-10-gate-wait"]
        assert task.status == "blocked"
        assert task.session == "claude/owner", "게이트 대기는 자리를 잃으면 안 된다"

        claims, status = remote_claims.list_claims(owner)
        assert status == "ok"
        held = [c for c in claims if c.task_id == "S9-10-gate-wait"]
        assert held, "원격 claim이 반납되면 다른 세션이 같은 일을 병렬 수행한다(HARN-38 사고)"
        assert held[0].branch == "claude/owner"

    def test_other_session_start_is_refused_while_gate_waiting(self, bare_remote, monkeypatch):
        """게이트대기_중에는_다른_세션의_start가_거부된다 — 사고 재현 축(acceptance ③)

        2026-08-31 사고의 정확한 재현이다: 원 세션이 block한 뒤 **다른 클론**이 같은
        태스크를 집어가려 한다. 수정 전에는 claim이 비어 있어 성공했다.
        """
        _, clone = bare_remote
        owner = clone("owner")
        monkeypatch.chdir(owner)
        assert cli.main(["seed"]) == 0
        assert _add_task("S9-11-race") == 0
        assert cli.main(["start", "S9-11-race"]) == 0
        _register_gate("G-test-human-action")
        _attach_gate_midflight(owner, "S9-11-race", "G-test-human-action")
        assert cli.main(["block", "S9-11-race", "--reason", "사람 행동 대기", "--gate-wait"]) == 0
        _publish(owner, "claude/owner", "게이트 대기 상태")

        # 다른 세션: 자기 클론에서 같은 태스크를 등재(그쪽 눈엔 todo)하고 착수 시도.
        other = clone("other")
        monkeypatch.chdir(other)
        assert cli.main(["seed"]) == 0
        assert _add_task("S9-11-race") == 0

        assert (
            cli.main(["start", "S9-11-race"]) != 0
        ), "게이트 대기 중 태스크를 다른 세션이 집어가면 HARN-38 사고가 재발한다"

    def test_owner_can_resume_after_gate_clears(self, bare_remote, monkeypatch):
        """게이트_해소_후_원_세션은_자기_자리를_되찾는다 — 보전이 잠금이 되면 안 된다

        claim을 쥔 채로 원 세션이 재착수하지 못하면 자리 보전은 자기 발등 찍기다.
        `remote_claims.claim`이 같은 브랜치에 멱등이라는 계약에 의존한다.
        """
        _, clone = bare_remote
        owner = clone("owner")
        monkeypatch.chdir(owner)
        assert cli.main(["seed"]) == 0
        assert _add_task("S9-12-resume") == 0
        assert cli.main(["start", "S9-12-resume"]) == 0
        _register_gate("G-test-human-action")
        _attach_gate_midflight(owner, "S9-12-resume", "G-test-human-action")
        assert cli.main(["block", "S9-12-resume", "--reason", "대기", "--gate-wait"]) == 0

        assert cli.main(["gates", "clear", "G-test-human-action", "--evidence", "완료"]) == 0
        assert cli.main(["unblock", "S9-12-resume"]) == 0
        assert cli.main(["start", "S9-12-resume"]) == 0, "원 세션이 자기 claim에 막히면 안 된다"

        backlog, _ = store.load_backlog(owner)
        assert backlog.tasks["S9-12-resume"].status == "in_progress"


class TestPlainBlockStillHandsOff:
    """플래그 없는 `block` = 인계 가능 (acceptance ②의 반대 축).

    이 축이 없으면 "게이트 대기가 claim을 쥔다"는 수정이 *모든* block을 잠그는
    회귀와 구별되지 않는다. 두 결과가 갈리는 것 자체가 플래그가 실제로 분기한다는 증거다.
    """

    def test_plain_block_releases_claim_so_another_session_can_take_over(
        self, bare_remote, monkeypatch
    ):
        """플래그없는_block은_claim을_반납해_인계를_허용한다"""
        _, clone = bare_remote
        owner = clone("owner")
        monkeypatch.chdir(owner)
        assert cli.main(["seed"]) == 0
        assert _add_task("S9-13-handoff") == 0
        assert cli.main(["start", "S9-13-handoff"]) == 0
        assert cli.main(["block", "S9-13-handoff", "--reason", "설계 재검토 필요"]) == 0

        backlog, _ = store.load_backlog(owner)
        assert backlog.tasks["S9-13-handoff"].session is None, "인계 가능 차단은 자리를 비운다"

        claims, status = remote_claims.list_claims(owner)
        assert status == "ok"
        assert not [
            c for c in claims if c.task_id == "S9-13-handoff"
        ], "일반 차단이 claim을 쥐고 있으면 아무도 인계할 수 없다"

        other = clone("other")
        monkeypatch.chdir(other)
        assert cli.main(["seed"]) == 0
        assert _add_task("S9-13-handoff") == 0
        assert cli.main(["start", "S9-13-handoff"]) == 0, "인계가 막히면 반대 방향 결함이다"


class TestGateWaitRequiresRealGate:
    """게이트 없는 '게이트 대기'는 검증 불가능한 주장이다 — 자리 점유를 정당화할 근거가
    대장에 없으면 그 보전은 점유일 뿐이다."""

    def test_gate_wait_without_unmet_gate_is_refused(self, bare_remote, monkeypatch, capsys):
        """미해소_게이트가_없으면_gate_wait은_거부된다"""
        _, clone = bare_remote
        owner = clone("owner")
        monkeypatch.chdir(owner)
        assert cli.main(["seed"]) == 0
        assert _add_task("S9-14-no-gate") == 0
        assert cli.main(["start", "S9-14-no-gate"]) == 0

        capsys.readouterr()
        assert cli.main(["block", "S9-14-no-gate", "--reason", "대기", "--gate-wait"]) != 0
        assert "미해소 게이트가 없다" in capsys.readouterr().err

        backlog, _ = store.load_backlog(owner)
        assert (
            backlog.tasks["S9-14-no-gate"].status == "in_progress"
        ), "거부된 전이가 상태를 바꾸면 안 된다"

    def test_gate_wait_refused_once_the_gate_is_already_cleared(self, bare_remote, monkeypatch):
        """이미_해소된_게이트만_있으면_gate_wait은_거부된다 — 'requires_gates 존재'가 아니라
        '미해소'가 조건임을 동결한다(변별력)."""
        _, clone = bare_remote
        owner = clone("owner")
        monkeypatch.chdir(owner)
        assert cli.main(["seed"]) == 0
        assert _add_task("S9-15-cleared-gate") == 0
        assert cli.main(["start", "S9-15-cleared-gate"]) == 0
        _register_gate("G-test-human-action")
        _attach_gate_midflight(owner, "S9-15-cleared-gate", "G-test-human-action")
        assert cli.main(["gates", "clear", "G-test-human-action", "--evidence", "이미 처리"]) == 0

        assert cli.main(["block", "S9-15-cleared-gate", "--reason", "대기", "--gate-wait"]) != 0


class TestGateWaitRequiresHeldSeat:
    """지키지 않은 자리는 보전할 수 없다 (Codex P1 · PR #942).

    `todo → blocked` 전이가 허용되므로, **착수한 적 없는** 태스크에도 `--gate-wait`가
    걸린다. 그 경우 `task.session`은 `None`이고 원격 claim은 애초에 없다 — 그런데
    출력은 "claim 유지 — 다른 세션의 착수가 거부된다"고 말한다. 다른 클론에서는 그
    태스크가 여전히 자유롭게 claim되므로, **이 옵션이 막으려던 중복 착수가 그대로
    재발**한다. 거짓 안전 신호는 안전 신호가 없는 것보다 나쁘다.

    여기서 claim을 *대신 획득*하지 않는 이유: 착수하지 않은 태스크의 자리를 잡는 것은
    이 설계가 명시적으로 거부한 '근거 없는 점유'다(게이트 유무 검사와 같은 취지).
    """

    def test_gate_wait_on_unstarted_task_is_refused(self, bare_remote, monkeypatch, capsys):
        """착수하지_않은_태스크의_gate_wait은_거부된다"""
        _, clone = bare_remote
        owner = clone("owner")
        monkeypatch.chdir(owner)
        assert cli.main(["seed"]) == 0
        _register_gate("G-test-human-action")
        assert _add_task("S9-16-unstarted", gates=["G-test-human-action"]) == 0

        capsys.readouterr()
        assert cli.main(["block", "S9-16-unstarted", "--reason", "대기", "--gate-wait"]) != 0
        assert "착수" in capsys.readouterr().err

        backlog, _ = store.load_backlog(owner)
        assert backlog.tasks["S9-16-unstarted"].status == "todo", "거부가 상태를 바꾸면 안 된다"

    def test_unstarted_task_can_still_be_blocked_plainly(self, bare_remote, monkeypatch):
        """착수_전_태스크도_일반_block은_된다 — 거부가 block 자체로 번지면 과잉이다"""
        _, clone = bare_remote
        owner = clone("owner")
        monkeypatch.chdir(owner)
        assert cli.main(["seed"]) == 0
        assert _add_task("S9-17-unstarted-plain") == 0
        assert cli.main(["block", "S9-17-unstarted-plain", "--reason", "선행 조사 필요"]) == 0

        backlog, _ = store.load_backlog(owner)
        assert backlog.tasks["S9-17-unstarted-plain"].status == "blocked"


class TestHandoffFromGateWaitActuallyWorks:
    """안내한 인계 절차가 *실제로* 인계를 성립시키는가 (Codex P2 · PR #942).

    `--gate-wait` 출력은 "인계하려면 `unblock` 후 `claims release`"라고 안내한다.
    그런데 `claims release`가 원격 claim만 지우고 보전된 로컬 `task.session`을 그대로
    두면, 그 사본을 받은 다른 세션은 `classify_todo`의 로컬 `claimed` 판정에 계속
    막힌다 — 그리고 그것을 푸는 CLI가 없어 **금지된 YAML 손편집**밖에 남지 않는다.

    안내한 절차가 안내한 결과를 내지 못하는 것은 문서 결함이 아니라 계약 결함이다.
    """

    def test_documented_handoff_frees_the_task_for_another_session(self, bare_remote, monkeypatch):
        """안내된_인계_절차가_실제로_다른_세션의_착수를_허용한다"""
        _, clone = bare_remote
        owner = clone("owner")
        monkeypatch.chdir(owner)
        assert cli.main(["seed"]) == 0
        assert _add_task("S9-18-handoff-from-wait") == 0
        assert cli.main(["start", "S9-18-handoff-from-wait"]) == 0
        _register_gate("G-test-human-action")
        _attach_gate_midflight(owner, "S9-18-handoff-from-wait", "G-test-human-action")
        assert (
            cli.main(["block", "S9-18-handoff-from-wait", "--reason", "대기", "--gate-wait"]) == 0
        )

        # 출력이 안내하는 그대로: unblock → claims release
        assert cli.main(["gates", "clear", "G-test-human-action", "--evidence", "완료"]) == 0
        assert cli.main(["unblock", "S9-18-handoff-from-wait"]) == 0
        assert cli.main(["claims", "release", "S9-18-handoff-from-wait"]) == 0

        backlog, _ = store.load_backlog(owner)
        assert (
            backlog.tasks["S9-18-handoff-from-wait"].session is None
        ), "원격만 비우고 로컬 자리를 남기면 인계는 서류상으로만 성립한다"

        _publish(owner, "claude/owner", "인계 준비 완료")

        other = clone("other")
        monkeypatch.chdir(other)
        assert cli.main(["seed"]) == 0
        assert _add_task("S9-18-handoff-from-wait") == 0
        assert (
            cli.main(["start", "S9-18-handoff-from-wait"]) == 0
        ), "안내한 절차를 그대로 밟았는데 인계가 안 되면 그 안내는 거짓이다"
