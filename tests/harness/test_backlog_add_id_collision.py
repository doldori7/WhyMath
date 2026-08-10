"""backlog.py add — 원격 브랜치 backlog/tasks/ 파일명 교차 스캔 (HARN-15).

HARN-10 가드(`cmd_add`의 `<PREFIX>-<번호>` 충돌 검사, `tests/harness/test_cli.py`의
`TestIdNumberCollision`)의 3회차 결함 교정이다. 기존 가드는 로컬 백로그 + 원격
claim 대장(harness-claims 브랜치, **in_progress로 claim된 태스크만** 기록)만 본다.
그래서 "다른 브랜치에 이미 backlog/tasks/<ID>.yaml로 **등재만 되고 아직 착수(claim)
되지 않은** 번호"는 claim 대장에 원천적으로 안 잡힌다 — OPS-17·OPS-18이 main과
미머지 브랜치에 각각 다른 슬러그로 이중 등재된 사고(2026-08-03)가 정확히 이 맹점이다.

이 파일은 그 맹점을 메우는 `remote_claims.scan_remote_task_files` 배선을
`backlog.py add`(CLI 종단)에서 검증한다. 진짜 로컬 원격(bare repo, `bare_remote`
픽스처)에서 실제 git push/fetch/ls-tree로 검증한다 — 시임(가짜 monkeypatch)이 아니다.

변별력(양방향, acceptance ③):
    ① 타 브랜치의 backlog/tasks/에만 존재하는 번호로 add → 거부 + 다음 빈 번호 제안
    ② 그 브랜치의 remote-tracking ref가 없는 상태에서는 → 통과
두 결과가 갈리는 것 자체가 "번호를 실제로 원격 브랜치에서 읽어서 판정한다"는 증거다.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import remote_claims
import store

import backlog as cli


class TestCrossBranchTaskFileNumberCollision:
    """원격 브랜치의 backlog/tasks/ 파일명만으로 존재하는 번호 충돌."""

    def _add(self, task_id: str, title: str = "교차 브랜치 번호 충돌 테스트") -> int:
        return cli.main(
            [
                "add",
                "--id",
                task_id,
                "--title",
                title,
                "--track",
                "math-completion",
                "--stage",
                "S2",
            ]
        )

    def _push_branch(self, repo: Path, branch: str) -> None:
        for argv in (
            ["checkout", "-q", "-B", branch],
            ["add", "."],
            ["commit", "-q", "-m", "등재만 하고 claim은 하지 않은 상태"],
            ["push", "--quiet", "-u", "origin", branch],
        ):
            subprocess.run(["git", *argv], cwd=repo, check=True, capture_output=True)

    def _seed_other_branch_with_task(self, clone, monkeypatch, task_id: str) -> Path:
        """`other` 세션이 태스크를 add만 하고(claim 없이) 브랜치를 push한 상태를 만든다."""
        other = clone("other")
        monkeypatch.chdir(other)
        assert cli.main(["seed"]) == 0
        assert self._add(task_id) == 0  # 이 시점엔 other 자신의 로컬 백로그라 충돌 없음
        self._push_branch(other, "claude/other")
        return other

    def test_number_registered_only_in_other_branch_task_file_rejected(
        self, bare_remote, monkeypatch, capsys
    ):
        """다른_브랜치_backlog_tasks_파일명만_있는_번호도_거부되고_다음_빈번호_제안"""
        _, clone = bare_remote
        self._seed_other_branch_with_task(clone, monkeypatch, "S9-50-other-branch-task")

        # newcomer는 other의 push *이후* clone하므로, git clone의 기본 refspec이
        # refs/remotes/origin/claude/other를 이미 캐시해 둔다 — 이 테스트는 이후
        # 별도 fetch를 걸지 않는다(= scan_remote_task_files가 실제로 fetch 없이
        # 캐시된 ref만으로 판정함을 증명한다).
        newcomer = clone("newcomer")
        monkeypatch.chdir(newcomer)
        assert cli.main(["seed"]) == 0

        capsys.readouterr()  # 셋업 출력을 버리고 add 출력만 본다
        assert self._add("S9-50-my-slug") == 1, "번호 충돌은 거부돼야 한다"
        captured = capsys.readouterr()
        assert "S9-50" in captured.err
        assert "원격 브랜치 backlog/tasks/" in captured.err, "새 출처 라벨이 노출돼야 한다"
        assert "claude/other" in captured.err, "어느 브랜치가 점유했는지 밝혀야 한다"
        assert "S9-51" in captured.err, "다음 빈 번호가 제안돼야 한다"

        backlog, _ = store.load_backlog(newcomer)
        assert "S9-50-my-slug" not in backlog.tasks

    def test_branch_tracking_ref_removed_then_add_passes(self, bare_remote, monkeypatch, capsys):
        """원격_브랜치_ref가_없으면_통과한다 — 변별력의 반대쪽 축(과탐이 아님을 증명)"""
        _, clone = bare_remote
        self._seed_other_branch_with_task(clone, monkeypatch, "S9-60-other-branch-task")

        newcomer = clone("newcomer")
        monkeypatch.chdir(newcomer)
        assert cli.main(["seed"]) == 0

        # remote-tracking ref 자체를 지운다 — "이 브랜치를 본 적 없는 클론" 재현.
        # scan_remote_task_files는 fetch하지 않으므로, ref가 없으면 그 브랜치는
        # 애초에 스캔 후보에도 오르지 않는다.
        subprocess.run(
            ["git", "update-ref", "-d", "refs/remotes/origin/claude/other"],
            cwd=newcomer,
            check=True,
            capture_output=True,
        )

        capsys.readouterr()
        assert (
            self._add("S9-60-my-slug") == 0
        ), "ref가 없으면 그 번호는 점유된 것으로 보이면 안 된다"
        backlog, _ = store.load_backlog(newcomer)
        assert "S9-60-my-slug" in backlog.tasks

    def test_same_full_id_across_branches_is_not_a_collision(self, bare_remote, monkeypatch):
        """같은_full_ID를_다른_클론에서_재등재하는_것은_충돌이_아니다

        HARN-10 기존 규칙(슬러그가 다를 때만 충돌)을 새 출처에도 그대로 적용한다 —
        시딩·복제 세션이 같은 태스크를 다시 add하는 정상 경로를 막으면 안 된다.
        """
        _, clone = bare_remote
        self._seed_other_branch_with_task(clone, monkeypatch, "S9-70-shared-task")

        newcomer = clone("newcomer")
        monkeypatch.chdir(newcomer)
        assert cli.main(["seed"]) == 0

        assert self._add("S9-70-shared-task") == 0, "같은 full ID 재등재는 통과해야 한다"

    def test_remote_task_file_scan_failure_warns_with_exception_type_but_does_not_block(
        self, bare_remote, monkeypatch, capsys
    ):
        """파일명_스캔_실패는_등재를_막지_않되_예외_타입명으로_경고한다

        CLAUDE.md 침묵 실패 금지 — scan_remote_task_files가 완전히 죽어도(모의 예외)
        add 자체는 fail-open으로 통과해야 하고, 경고에는 예외 타입명이 남아야 한다.
        """
        _, clone = bare_remote
        newcomer = clone("newcomer")
        monkeypatch.chdir(newcomer)
        assert cli.main(["seed"]) == 0

        def _boom(root, **kw):
            raise RuntimeError("원격 파일명 스캔 불가")

        monkeypatch.setattr(remote_claims, "scan_remote_task_files", _boom)
        capsys.readouterr()
        assert self._add("S9-80-scan-failure-ok") == 0, "스캔 실패가 add 자체를 막으면 안 된다"
        captured = capsys.readouterr()
        assert "RuntimeError" in captured.err, "예외 타입명이 경고에 남아야 한다(침묵 실패 금지)"


class TestScanRemoteTaskFilesNetworkCostGuard:
    """`scan_remote_task_files`가 실제로 fetch 없이 캐시된 ref만 읽는지 — 단위 레벨.

    CLI 종단 테스트(위 클래스)는 "결과가 맞다"만 증명한다. 이 클래스는 acceptance
    ②(네트워크 비용 가드)를 `git fetch`가 **호출조차 되지 않는다**는 사실로 직접
    증명한다 — `scan_remote_done`이 이미 쓰는 `fetch=False` 선례와 동일한 계약.
    """

    def _spy_git(self, monkeypatch) -> list[tuple[str, ...]]:
        calls: list[tuple[str, ...]] = []
        original = remote_claims._git

        def spy(root, *argv, **kwargs):
            calls.append(argv)
            return original(root, *argv, **kwargs)

        monkeypatch.setattr(remote_claims, "_git", spy)
        return calls

    def test_default_call_never_invokes_git_fetch(self, bare_remote, monkeypatch):
        """fetch=False_기본값은_git_fetch를_호출하지_않는다"""
        _, clone = bare_remote
        newcomer = clone("newcomer")

        calls = self._spy_git(monkeypatch)
        _, status = remote_claims.scan_remote_task_files(newcomer)
        assert status == "ok"
        assert not any(
            a and a[0] == "fetch" for a in calls
        ), "fetch=False 기본값인데 git fetch가 호출됐다 — 네트워크 비용 가드 위반"

    def test_fetch_true_does_invoke_git_fetch(self, bare_remote, monkeypatch):
        """fetch=True는_명시적으로_git_fetch를_호출한다 — 위 테스트의 반대 축(변별력)"""
        _, clone = bare_remote
        newcomer = clone("newcomer")

        calls = self._spy_git(monkeypatch)
        _, status = remote_claims.scan_remote_task_files(newcomer, fetch=True)
        assert status == "ok"
        assert any(a and a[0] == "fetch" for a in calls), "fetch=True인데 git fetch가 안 불렸다"
