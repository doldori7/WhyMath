"""HARN-24 — amend CLI 동사: 등재된 태스크의 acceptance·게이트·트랙 정정.

배경: 이 CLI의 서브커맨드 18개 중 *등재된 태스크의* acceptance를 고치는 것이 0건이었다
(`grep acceptance backlog.py` → cmd_start의 print·cmd_add의 생성자·add 파서 3곳뿐).
그래서 정정이 문서에만 착지하고 태스크 YAML에 도달하지 못했고, 그 정정을 조상으로 가진
세션이 stale acceptance를 그대로 집행했다(ADMIN-02 → subscription_* 3컬럼 드롭·b3a58b02).

이 파일이 계약으로 동결하는 것:
  ① acceptance는 **append만** — 기존 항이 살아남는다(HARN-20의 notes 교훈 승계).
  ② `--gate`가 add 시점 외 requires_gates 부착 경로로 실제 작동하고, selector가 그
     게이트를 미통과로 읽어 태스크를 next에서 뺀다(부착이 장식이 아님을 실증).
  ③ `--track` 이관이 entry_gate 하드락으로의 강등에 실제로 쓰인다.
  ④ **다른 필드 불변** — status·session·artifacts·id·title을 건드리지 않는다.
  ⑤ 변별력 — 무변경 호출·중복 항·미등재 게이트/트랙은 거부(exit 1)한다. 성공/실패
     양쪽에서 같은 결과를 내면 검증이 아니라 위장이다.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import selector
import store

import backlog as cli


@pytest.fixture
def seeded_repo(git_repo: Path, monkeypatch) -> Path:
    monkeypatch.chdir(git_repo)
    assert cli.main(["seed"]) == 0
    return git_repo


def _add(task_id: str, *extra: str, acceptance: str = "원래 조건 ①") -> int:
    return cli.main(
        [
            "add",
            "--eos-priority",
            "P2",
            "--id",
            task_id,
            "--title",
            "HARN-24 테스트 태스크",
            "--track",
            "math-completion",
            "--stage",
            "S1",
            "--acceptance",
            acceptance,
            *extra,
        ]
    )


def _task(repo: Path, task_id: str):
    backlog, _ = store.load_backlog(repo)
    return backlog.tasks[task_id]


class TestAcceptanceAppendOnly:
    """① acceptance는 append — 원 항이 살아남는다."""

    def test_append_preserves_original(self, seeded_repo: Path):
        assert _add("T1-01-amend-append") == 0
        assert (
            cli.main(
                [
                    "amend",
                    "T1-01-amend-append",
                    "--acceptance",
                    "정정 조건 ② — 드롭 대상은 school_id 1컬럼뿐",
                    "--reason",
                    "ADMIN-02형 stale acceptance 정정",
                ]
            )
            == 0
        )
        task = _task(seeded_repo, "T1-01-amend-append")
        # 원 항이 살아 있고, 정정 항이 뒤에 붙었다 — 덮어쓰기였다면 길이가 1이다
        assert task.acceptance == [
            "원래 조건 ①",
            "정정 조건 ② — 드롭 대상은 school_id 1컬럼뿐",
        ]

    def test_notes_appended_not_overwritten(self, seeded_repo: Path):
        assert _add("T1-02-amend-notes", "--notes", "발견 경위: 원문 보존돼야 한다") == 0
        assert (
            cli.main(
                [
                    "amend",
                    "T1-02-amend-notes",
                    "--acceptance",
                    "추가 항",
                    "--reason",
                    "사유 기록",
                ]
            )
            == 0
        )
        notes = _task(seeded_repo, "T1-02-amend-notes").notes
        assert "발견 경위: 원문 보존돼야 한다" in notes
        assert "[정정" in notes and "사유 기록" in notes

    def test_duplicate_acceptance_rejected(self, seeded_repo: Path):
        """변별력 — 같은 항 재추가는 거부(대장이 중복으로 부풀지 않게)."""
        assert _add("T1-03-amend-dup") == 0
        assert (
            cli.main(
                ["amend", "T1-03-amend-dup", "--acceptance", "원래 조건 ①", "--reason", "중복"]
            )
            == 1
        )

    def test_empty_acceptance_rejected(self, seeded_repo: Path):
        assert _add("T1-04-amend-empty") == 0
        assert (
            cli.main(["amend", "T1-04-amend-empty", "--acceptance", "   ", "--reason", "빈 항"])
            == 1
        )


class TestGateAttachment:
    """② --gate — add 시점 외 requires_gates 부착의 유일 경로. 부착이 실제로 듣는가."""

    def test_gate_attach_excludes_from_next(self, seeded_repo: Path):
        assert _add("T1-05-amend-gate") == 0
        backlog, _ = store.load_backlog(seeded_repo)
        # 부착 전: 게이트 미통과 사유로 제외되지 않는다
        before = selector.classify_todo(backlog, backlog.tasks["T1-05-amend-gate"])
        assert before is None or before.reason != "gates"

        assert cli.main(["gates", "add", "G-harn24-test", "--title", "테스트 게이트"]) == 0
        assert (
            cli.main(
                [
                    "amend",
                    "T1-05-amend-gate",
                    "--gate",
                    "G-harn24-test",
                    "--reason",
                    "관여도 판정 대기",
                ]
            )
            == 0
        )

        backlog, _ = store.load_backlog(seeded_repo)
        task = backlog.tasks["T1-05-amend-gate"]
        assert task.requires_gates == ["G-harn24-test"]
        # 부착 후: 미통과 게이트로 실제 제외된다 — 부착이 장식이 아님
        assert selector.unmet_gates(backlog, task) == ["G-harn24-test"]
        after = selector.classify_todo(backlog, task)
        assert after is not None and after.reason == "gates"

    def test_unknown_gate_rejected(self, seeded_repo: Path, capsys):
        """변별력 — gates.yaml에 없는 게이트 부착은 거부(영구 차단 방지).

        거부 자체는 `validate_backlog`(store.py의 dangling 참조 검사)도 잡아내므로
        exit code만 보면 amend의 선제 검사가 없어도 통과한다(뮤테이션 M2 생존 실측).
        그래서 **어느 방어선이 잡았는지**를 메시지로 구별한다 — 선제 검사는 "먼저
        `gates add` 로 등재하라"는 복구 경로를 알려주고, validate 폴백은 알려주지
        않는다. 이 구별이 없으면 검사 제거가 무증상이 된다.
        """
        assert _add("T1-06-amend-badgate") == 0
        assert (
            cli.main(
                ["amend", "T1-06-amend-badgate", "--gate", "G-does-not-exist", "--reason", "오타"]
            )
            == 1
        )
        assert _task(seeded_repo, "T1-06-amend-badgate").requires_gates == []
        err = capsys.readouterr().err
        assert "gates add" in err, "선제 검사가 복구 경로를 안내해야 한다(validate 폴백과 구별)"

    def test_duplicate_gate_rejected(self, seeded_repo: Path):
        assert _add("T1-07-amend-dupgate") == 0
        assert cli.main(["gates", "add", "G-harn24-dup", "--title", "테스트"]) == 0
        assert (
            cli.main(["amend", "T1-07-amend-dupgate", "--gate", "G-harn24-dup", "--reason", "1차"])
            == 0
        )
        assert (
            cli.main(["amend", "T1-07-amend-dupgate", "--gate", "G-harn24-dup", "--reason", "2차"])
            == 1
        )


class TestTrackTransfer:
    """③ --track — entry_gate 하드락 트랙으로의 강등 경로."""

    def test_track_transfer_applies_entry_gate(self, seeded_repo: Path):
        assert _add("T1-08-amend-track") == 0
        # subject-expansion은 시드에서 entry_gate=G-s5-subject-expansion(pending)로 잠겨 있다
        assert (
            cli.main(
                [
                    "amend",
                    "T1-08-amend-track",
                    "--track",
                    "subject-expansion",
                    "--reason",
                    "12월 검증 비관여 — 이월",
                ]
            )
            == 0
        )
        backlog, _ = store.load_backlog(seeded_repo)
        task = backlog.tasks["T1-08-amend-track"]
        assert task.track == "subject-expansion"
        # 트랙 entry_gate가 실제로 next에서 뺀다 — 이관이 표시가 아니라 강등임을 실증
        excl = selector.classify_todo(backlog, task)
        assert excl is not None and excl.reason == "track_gate"

    def test_unknown_track_rejected(self, seeded_repo: Path):
        assert _add("T1-09-amend-badtrack") == 0
        assert (
            cli.main(
                ["amend", "T1-09-amend-badtrack", "--track", "no-such-track", "--reason", "오타"]
            )
            == 1
        )
        assert _task(seeded_repo, "T1-09-amend-badtrack").track == "math-completion"

    def test_same_track_rejected(self, seeded_repo: Path):
        assert _add("T1-10-amend-sametrack") == 0
        assert (
            cli.main(
                [
                    "amend",
                    "T1-10-amend-sametrack",
                    "--track",
                    "math-completion",
                    "--reason",
                    "무변경",
                ]
            )
            == 1
        )


class TestDependsAttach:
    """⑥ `--depends` — 등재 후 선행을 붙이는 유일한 CLI 경로 (HARN-52).

    이 경로가 없으면 `audit-deps` 게이트는 **고칠 수 없는 위반**을 지적하게 되고,
    그런 게이트는 사람이 게이트 자체를 끄게 만든다.
    """

    def test_depends_attach_blocks_from_next(self, seeded_repo: Path):
        """부착이 장식이 아님을 실증 — selector가 실제로 후보에서 뺀다."""
        _add("HARN-90-blocker")
        _add("HARN-91-dependent")
        backlog, _ = store.load_backlog(seeded_repo)
        # 부착 전: 의존 사유로 제외되지 않는다
        before = selector.classify_todo(backlog, backlog.tasks["HARN-91-dependent"])
        assert before is None or before.reason != "deps"

        assert (
            cli.main(
                ["amend", "HARN-91-dependent", "--depends", "HARN-90-blocker", "--reason", "선행"]
            )
            == 0
        )

        backlog, _ = store.load_backlog(seeded_repo)
        task = backlog.tasks["HARN-91-dependent"]
        assert task.depends_on == ["HARN-90-blocker"]
        # 부착 후: 미해소 의존으로 실제 제외된다 — 부착이 장식이 아님
        assert selector.unmet_dependencies(backlog, task) == ["HARN-90-blocker"]
        after = selector.classify_todo(backlog, task)
        assert after is not None and after.reason == "deps"

    def test_self_dependency_rejected(self, seeded_repo: Path):
        _add("HARN-92-self")
        assert (
            cli.main(["amend", "HARN-92-self", "--depends", "HARN-92-self", "--reason", "x"]) == 1
        )

    def test_unknown_dependency_rejected(self, seeded_repo: Path):
        """존재하지 않는 의존은 영구 차단이 된다 — 등록 자체를 막는다."""
        _add("HARN-93-x")
        assert cli.main(["amend", "HARN-93-x", "--depends", "NOPE-99-ghost", "--reason", "x"]) == 1

    def test_cycle_rejected(self, seeded_repo: Path, capsys):
        """순환은 양쪽을 영구 착수 불가로 만든다 — 부착 *시점*에 막는다.

        거부 자체는 `validate_backlog`의 DAG 검사도 잡아내므로 exit code만 보면 amend의
        선제 순환 검사가 없어도 통과한다(뮤테이션 D1 생존 실측 — 2026-09-01). 그래서
        **어느 방어선이 잡았는지**를 메시지로 구별한다: 선제 검사는 순환 경로를
        `A → … → B` 형태로 지목하고, validate 폴백은 그러지 않는다.
        """
        _add("HARN-94-a")
        _add("HARN-95-b")
        assert cli.main(["amend", "HARN-95-b", "--depends", "HARN-94-a", "--reason", "x"]) == 0
        capsys.readouterr()
        assert cli.main(["amend", "HARN-94-a", "--depends", "HARN-95-b", "--reason", "x"]) == 1
        err = capsys.readouterr().err
        # validate 폴백은 "depends_on 순환 참조 검출: [...]" 라고만 한다 — "순환"·ID 포함
        # 여부로는 구별되지 않는다(실측). 선제 검사에만 있는 문구로 고정한다.
        assert "순환을 만든다" in err, "선제 검사 문구가 아니다 — validate 폴백과 구별 불가"
        assert "→ … →" in err, "선제 검사는 순환 경로를 화살표로 지목해야 한다"
        # 부착이 실제로 일어나지 않았다 — 거부가 메시지만이 아님
        assert _task(seeded_repo, "HARN-94-a").depends_on == []

    def test_duplicate_dependency_rejected(self, seeded_repo: Path):
        _add("HARN-96-a")
        _add("HARN-97-b")
        assert cli.main(["amend", "HARN-97-b", "--depends", "HARN-96-a", "--reason", "x"]) == 0
        assert cli.main(["amend", "HARN-97-b", "--depends", "HARN-96-a", "--reason", "x"]) == 1


class TestPriorityReassign:
    """⑦ `--priority` — 등재 후 우선순위를 고치는 유일한 CLI 경로 (HARN-52 후속).

    track·acceptance·gate·depends에 이은 마지막 필드였다. 정정 경로가 없으면 잘못 잡힌
    우선순위가 대장 손편집(금기)으로만 고쳐진다 — 실제로 `HARN-53`이 그랜드파더 만료
    지점인데 priority 3이라 만료가 명목상으로만 성립하던 상태를 이 경로로 고쳤다.
    """

    def test_priority_reassigned_and_logged(self, seeded_repo: Path):
        _add("HARN-98-p")
        assert _task(seeded_repo, "HARN-98-p").priority == 3
        assert (
            cli.main(["amend", "HARN-98-p", "--priority", "1", "--reason", "차단 해소 지점"]) == 0
        )
        task = _task(seeded_repo, "HARN-98-p")
        assert task.priority == 1
        # 이전 값이 notes에 남는다 — 흔적 없이 덮어쓰면 왜 올렸는지 사라진다(HARN-49 관례)
        assert "3 → 1" in task.notes

    def test_priority_changes_next_ordering(self, seeded_repo: Path):
        """부착이 장식이 아님을 실증 — selector 정렬이 실제로 바뀐다."""
        # 동점 tie-break이 task.id이므로, 우열이 *실제로 뒤집히는* 값으로 잡는다
        # (둘 다 1로 만들면 id 순으로 갈려 이 검사가 우선순위를 보는지 알 수 없다).
        _add("HARN-99-low")  # priority 3 (기본)
        _add("HARN-80-high", "--priority", "2")
        backlog, _ = store.load_backlog(seeded_repo)
        low, high = backlog.tasks["HARN-99-low"], backlog.tasks["HARN-80-high"]
        assert selector.sort_key(backlog, high) < selector.sort_key(backlog, low)

        assert cli.main(["amend", "HARN-99-low", "--priority", "1", "--reason", "상향"]) == 0
        backlog, _ = store.load_backlog(seeded_repo)
        low, high = backlog.tasks["HARN-99-low"], backlog.tasks["HARN-80-high"]
        assert low.priority == 1
        # 상향 후 정렬 우열이 뒤집힌다 — 정정 전/후가 같은 값을 내면 검증이 아니다
        assert selector.sort_key(backlog, low) < selector.sort_key(backlog, high)

    @pytest.mark.parametrize("bad", ["0", "6", "-1"])
    def test_out_of_range_rejected(self, seeded_repo: Path, capsys, bad: str):
        """범위 밖은 거부 — 선제 검사가 잡았는지 메시지로 구별한다.

        거부 자체는 `models.Task.validate()`의 priority 범위 검사도 잡아내므로 exit code
        만 보면 amend의 선제 검사가 없어도 통과한다(뮤테이션 P1 생존 실측 — 2026-09-01).
        선제 검사는 받은 값과 허용 범위를 함께 알려주고 **태스크를 건드리지 않은 채**
        멈춘다; validate 폴백은 이미 대입한 뒤 되돌린다.
        """
        _add("HARN-81-r")
        capsys.readouterr()
        assert cli.main(["amend", "HARN-81-r", "--priority", bad, "--reason", "x"]) == 1
        err = capsys.readouterr().err
        assert "1(최고)~5" in err, "선제 검사가 허용 범위를 안내해야 한다(validate 폴백과 구별)"
        assert bad in err, "거부 메시지가 받은 값을 되비춰야 한다"
        assert _task(seeded_repo, "HARN-81-r").priority == 3

    def test_same_priority_rejected(self, seeded_repo: Path):
        """무변경 amend는 이벤트 대장을 오염시킨다(정정했다고 읽힌다)."""
        _add("HARN-82-s")
        assert cli.main(["amend", "HARN-82-s", "--priority", "3", "--reason", "x"]) == 1


class TestOtherFieldsFrozen:
    """④ amend는 status·session·artifacts·id·title을 건드리지 않는다."""

    def test_status_and_session_untouched(self, seeded_repo: Path):
        assert _add("T1-11-amend-frozen") == 0
        assert cli.main(["start", "T1-11-amend-frozen", "--no-remote"]) == 0
        before = _task(seeded_repo, "T1-11-amend-frozen")
        before_status, before_session = before.status, before.session
        assert (
            cli.main(
                ["amend", "T1-11-amend-frozen", "--acceptance", "추가", "--reason", "진행 중 정정"]
            )
            == 0
        )
        after = _task(seeded_repo, "T1-11-amend-frozen")
        assert after.status == before_status == "in_progress"
        assert after.session == before_session
        assert after.artifacts == []
        assert after.id == "T1-11-amend-frozen"
        assert after.title == "HARN-24 테스트 태스크"


class TestGuards:
    """⑤ 변별력 — 무변경 호출·미존재 태스크·사유 누락은 거부."""

    def test_no_change_rejected(self, seeded_repo: Path):
        """사유만 남기고 아무것도 안 바꾸는 호출은 이벤트 대장을 오염시킨다."""
        assert _add("T1-12-amend-nochange") == 0
        assert cli.main(["amend", "T1-12-amend-nochange", "--reason", "사유만"]) == 1

    def test_missing_task_rejected(self, seeded_repo: Path):
        assert cli.main(["amend", "T1-99-nonexistent", "--acceptance", "x", "--reason", "y"]) == 1

    def test_reason_is_required(self, seeded_repo: Path):
        assert _add("T1-13-amend-noreason") == 0
        with pytest.raises(SystemExit):
            cli.main(["amend", "T1-13-amend-noreason", "--acceptance", "x"])


class TestEventLedger:
    """정정이 이벤트 대장에 사유·변경내역과 함께 남는다 — 추적 가능성."""

    def test_amend_event_recorded(self, seeded_repo: Path):
        assert _add("T1-14-amend-event") == 0
        assert (
            cli.main(
                ["amend", "T1-14-amend-event", "--acceptance", "새 항", "--reason", "정정 사유 X"]
            )
            == 0
        )
        # 이벤트 대장은 세션 샤딩됐다(HARN-46) — 레거시 단일 파일만 읽으면 샤딩 이후
        # 기록이 통째로 안 보인다. store.event_paths()가 레거시+샤드를 모두 준다.
        events = [
            json.loads(line)
            for path in store.event_paths(seeded_repo)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        amends = [e for e in events if e.get("action") == "amend"]
        assert len(amends) == 1
        assert amends[0]["id"] == "T1-14-amend-event"
        assert amends[0]["reason"] == "정정 사유 X"
        assert any("acceptance" in c for c in amends[0]["changed"])


class TestReasonFeedbackGuard:
    """⑥ HARN-53 — `--reason` 문구가 *새 의존 선언*을 만들면 쓰기 전에 거부한다.

    되먹임의 실체: `--reason`은 notes에 append되고 notes는 의존 선언 스캐너(HARN-52)의
    입력이다. 그래서 "…'선행'이라 선언한 방향을 부착한다" 같은 **정정 사유 인용**이 그 문장
    안의 태스크 ID를 새 선행 선언으로 만든다. notes는 append 전용이라 되돌릴 CLI 경로가
    없으므로, 기록된 뒤에 고치는 것이 불가능하다 — 그래서 쓰기 *전에* 막는다.

    이 클래스가 동결하는 것은 세 가지다: 거부한다 · **거부 시 대장을 건드리지 않는다** ·
    무해한 사유는 통과한다(무조건 거부면 정정 경로 자체가 막힌다).
    """

    def _seed_pair(self) -> None:
        assert _add("T1-90-feedback-target") == 0
        assert _add("T1-91-feedback-ref") == 0

    def test_reason_creating_a_new_declaration_is_refused(self, seeded_repo: Path, capsys):
        self._seed_pair()
        before = _task(seeded_repo, "T1-90-feedback-target")
        assert (
            cli.main(
                [
                    "amend",
                    "T1-90-feedback-target",
                    "--priority",
                    "1",
                    "--reason",
                    "T1-91 착지 후 재검토한다",  # 선행 어구 + 타 태스크 ID가 한 문장에
                ]
            )
            == 1
        )
        err = capsys.readouterr().err
        assert "새 의존 선언을 만든다" in err
        after = _task(seeded_repo, "T1-90-feedback-target")
        # 거부는 **쓰기 0**이어야 한다 — 절반 기록되면 notes만 오염되고 정정은 안 된 상태가 된다.
        assert after.priority == before.priority
        assert after.notes == before.notes

    def test_harmless_reason_still_passes(self, seeded_repo: Path):
        """양성 대조 — 무조건 거부면 가드가 아니라 정정 차단기다."""
        self._seed_pair()
        assert (
            cli.main(
                ["amend", "T1-90-feedback-target", "--priority", "1", "--reason", "우선순위 재배정"]
            )
            == 0
        )
        assert _task(seeded_repo, "T1-90-feedback-target").priority == 1

    def test_guard_only_judges_findings_this_amendment_created(self, seeded_repo: Path):
        """기존 위반은 이 명령의 책임이 아니다 — 아니면 대장에 위반이 하나만 있어도 amend가 전부 막힌다.

        `--depends`로 선행을 부착하는 정정은 *기존* 위반을 해소하는 정상 경로인데, 그때 사유에
        같은 ID를 적는 것은 자연스럽다. 그 경우까지 막으면 게이트가 자기 정정 경로를 봉쇄한다.
        """
        self._seed_pair()
        # 먼저 위반 상태를 만든다(사유에 어구 없이 — 가드를 건드리지 않고).
        assert (
            cli.main(["amend", "T1-90-feedback-target", "--priority", "1", "--reason", "준비"]) == 0
        )
        # 그 위반을 depends 부착으로 해소하는 정정은 통과해야 한다.
        assert (
            cli.main(
                [
                    "amend",
                    "T1-90-feedback-target",
                    "--depends",
                    "T1-91-feedback-ref",
                    "--reason",
                    "선행 관계 확정",
                ]
            )
            == 0
        )
        assert "T1-91-feedback-ref" in _task(seeded_repo, "T1-90-feedback-target").depends_on


class TestBlockReasonFeedbackGuard:
    """⑦ HARN-53 — `block --reason`도 notes에 append된다(amend와 같은 되먹임).

    `done`·`cancel`은 스캐너가 건너뛰는 상태(done/cancelled)로 바꾸므로 위반을 만들 수 없다 —
    그래서 가드는 `amend`·`block` 두 곳에만 있다. 이 클래스는 block 쪽을 동결한다.
    """

    def test_block_reason_creating_a_declaration_is_refused(self, seeded_repo: Path, capsys):
        assert _add("T1-95-block-guard") == 0
        assert _add("T1-96-block-ref") == 0
        before = _task(seeded_repo, "T1-95-block-guard")
        assert cli.main(["block", "T1-95-block-guard", "--reason", "T1-96 착지 후 재개한다"]) == 1
        assert "새 의존 선언을 만든다" in capsys.readouterr().err
        after = _task(seeded_repo, "T1-95-block-guard")
        assert after.status == before.status, "거부인데 상태가 바뀌었다"
        assert after.notes == before.notes, "거부인데 notes가 오염됐다"

    def test_block_with_harmless_reason_still_works(self, seeded_repo: Path):
        """양성 대조 — 차단 경로 자체를 막으면 안 된다."""
        assert _add("T1-97-block-ok") == 0
        assert cli.main(["block", "T1-97-block-ok", "--reason", "외부 의사결정 대기"]) == 0
        assert _task(seeded_repo, "T1-97-block-ok").status == "blocked"
