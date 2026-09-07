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
  ④ **상태 전이 표면 불변** — status·session·id는 건드리지 않는다. (HARN-57에서 정밀화:
     artifacts·paths·title은 *기술(記述)* 축이라 정정 경로가 열렸다 — 아래 세 클래스가
     그 계약을, `TestFrozenAxesStayFrozen`이 닫힌 축의 동결을 각각 동결한다.)
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
    """④ *acceptance만* 고치는 호출은 다른 필드를 하나도 건드리지 않는다.

    HARN-57 이후 artifacts·title에는 전용 플래그가 생겼지만, 그것을 지정하지 않은 호출이
    부수 효과로 바꾸지 않는다는 계약은 그대로다. 열린 축의 동결은
    `TestFrozenAxesStayFrozen`이 담당한다.
    """

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


# ─────────────────────────────────────────────────────────────────────────────
# HARN-57 — 정정 경로 3축(artifacts·paths·title) + `--no-pr` 사후 해소
#
# 원칙 2("다른 필드 불변")를 *무효화*한 것이 아니라 **정밀화**한 결과를 동결한다:
#   · 여전히 닫힌 것 = id·status·session (상태 전이 우회 표면)
#   · 열린 것       = artifacts(append만)·paths(교체)·title(교체)
# 셋 다 정정 경로가 없어 실측 사고를 냈고, 그때마다 YAML 손편집(금기)으로만 고쳐졌다.
# ─────────────────────────────────────────────────────────────────────────────


def _add_titled(task_id: str, title: str, *extra: str) -> int:
    """title을 지정해 등재 — `next` 노출 문자열을 검사하려면 태스크마다 제목이 달라야 한다."""
    return cli.main(
        [
            "add",
            "--eos-priority",
            "P2",
            "--id",
            task_id,
            "--title",
            title,
            "--track",
            "math-completion",
            "--stage",
            "S1",
            "--acceptance",
            "원래 조건 ①",
            *extra,
        ]
    )


def _finish_without_pr(task_id: str, reason: str, artifact: str = "커밋 예정(PR 동반)") -> None:
    """`--no-pr <사유>`로 종결시킨다 — HARN-44가 실제로 남긴 상태의 재현."""
    assert cli.main(["start", task_id, "--no-remote"]) == 0
    assert cli.main(["done", task_id, "--artifact", artifact, "--no-pr", reason]) == 0


def _amend_events(repo: Path, task_id: str) -> list[dict]:
    return [
        e
        for path in store.event_paths(repo)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
        for e in [json.loads(line)]
        if e.get("action") == "amend" and e.get("id") == task_id
    ]


class TestArtifactCorrection:
    """① done 이후 열린 PR의 증적을 붙이는 유일한 합법 경로 — **append만**.

    경위: `done`은 종결 상태라 재실행이 거부되고(done→done 전이 불가) `amend`에는
    `--artifact`가 없었다. 그래서 done을 PR 생성 *전에* 부르면 잘못된 증적이 영구 고정된다
    — HARN-44의 artifacts에 "커밋 예정(PR 동반)"이 남고 실제 PR #965는 대장에서 추적 불가.
    """

    def test_append_preserves_existing_artifacts(self, seeded_repo: Path):
        """덮어쓰기가 아니다 — 기존 증적이 살아남고 새 증적이 뒤에 붙는다."""
        assert _add("T1-60-artifact-append") == 0
        _finish_without_pr("T1-60-artifact-append", "incomplete")
        before = _task(seeded_repo, "T1-60-artifact-append").artifacts
        assert before == ["커밋 예정(PR 동반)"]

        assert (
            cli.main(
                [
                    "amend",
                    "T1-60-artifact-append",
                    "--artifact",
                    "PR #965",
                    "--reason",
                    "done 이후 개설된 PR 증적 보강",
                ]
            )
            == 0
        )
        after = _task(seeded_repo, "T1-60-artifact-append").artifacts
        # 정정 전/후가 실제로 다르고(변별력), 원 항이 보존됐다(덮어쓰기였다면 길이가 1이다)
        assert after != before
        assert after == ["커밋 예정(PR 동반)", "PR #965"]

    def test_removal_is_not_opened(self, seeded_repo: Path):
        """증적 *제거* 플래그는 존재하지 않는다 — 지울 수 있으면 이 CLI가 위조 표면이 된다."""
        parser = cli.build_parser()
        amend = parser._subparsers._group_actions[0].choices["amend"]  # type: ignore[union-attr]
        options = {opt for action in amend._actions for opt in action.option_strings}
        assert "--artifact" in options
        assert not {"--drop-artifact", "--remove-artifact", "--clear-artifacts"} & options

    def test_duplicate_artifact_rejected(self, seeded_repo: Path):
        assert _add("T1-61-artifact-dup") == 0
        _finish_without_pr("T1-61-artifact-dup", "ci-red", artifact="PR #900")
        assert (
            cli.main(["amend", "T1-61-artifact-dup", "--artifact", "PR #900", "--reason", "중복"])
            == 1
        )
        assert _task(seeded_repo, "T1-61-artifact-dup").artifacts == ["PR #900"]

    def test_artifact_recorded_in_event_ledger(self, seeded_repo: Path):
        assert _add("T1-62-artifact-event") == 0
        _finish_without_pr("T1-62-artifact-event", "incomplete")
        assert (
            cli.main(
                ["amend", "T1-62-artifact-event", "--artifact", "PR #965", "--reason", "증적 보강"]
            )
            == 0
        )
        events = _amend_events(seeded_repo, "T1-62-artifact-event")
        assert len(events) == 1
        assert events[0]["artifacts"] == ["PR #965"]

    def test_works_on_a_task_that_is_still_in_progress(self, seeded_repo: Path):
        """정정 축은 상태 전이와 무관하다 — done 전이든 후든 증적을 붙일 수 있다."""
        assert _add("T1-63-artifact-wip") == 0
        assert cli.main(["start", "T1-63-artifact-wip", "--no-remote"]) == 0
        assert (
            cli.main(
                ["amend", "T1-63-artifact-wip", "--artifact", "PR #1", "--reason", "선행 증적"]
            )
            == 0
        )
        task = _task(seeded_repo, "T1-63-artifact-wip")
        assert task.artifacts == ["PR #1"]
        # 닫힌 축은 그대로다 — status·session·id는 이 verb가 건드리지 않는다
        assert task.status == "in_progress"
        assert task.session is not None


class TestNoPrPostHocResolution:
    """② `--no-pr` 사유의 사후 해소 — PR이 실제로 열렸으면 그 사실이 대장에 남는다.

    현재는 "커밋 예정" 같은 문구가 영구 증적으로 굳고, 이벤트 대장만 보는 도구는 그 태스크를
    영원히 "PR 없이 끝난 건"으로 센다. 해소는 **증적에서 파생**된다(별도 플래그 없음) —
    사람이 기억해야 하는 플래그를 하나 더 만들면 그것이 다음 망각 지점이 된다.
    """

    def test_resolution_recorded_in_notes_and_events(self, seeded_repo: Path):
        assert _add("T1-64-nopr-resolve") == 0
        _finish_without_pr("T1-64-nopr-resolve", "incomplete")
        assert "[PR 보류" in _task(seeded_repo, "T1-64-nopr-resolve").notes

        assert (
            cli.main(
                [
                    "amend",
                    "T1-64-nopr-resolve",
                    "--artifact",
                    "PR #965",
                    "--reason",
                    "종결 후 개설된 PR",
                ]
            )
            == 0
        )
        task = _task(seeded_repo, "T1-64-nopr-resolve")
        assert "[PR 보류 해소" in task.notes
        assert "incomplete" in task.notes
        assert "PR #965" in task.notes
        events = _amend_events(seeded_repo, "T1-64-nopr-resolve")
        assert events[-1]["no_pr_resolved"] == "incomplete"

    def test_ci_red_reason_is_carried_into_the_resolution(self, seeded_repo: Path):
        """어느 사유가 해소됐는지가 남아야 한다 — '해소됨'만으로는 회계가 복원되지 않는다."""
        assert _add("T1-65-nopr-cired") == 0
        _finish_without_pr("T1-65-nopr-cired", "ci-red")
        assert (
            cli.main(
                ["amend", "T1-65-nopr-cired", "--artifact", "PR #7", "--reason", "CI 복구 후 개설"]
            )
            == 0
        )
        assert _amend_events(seeded_repo, "T1-65-nopr-cired")[-1]["no_pr_resolved"] == "ci-red"

    def test_non_pr_artifact_does_not_resolve(self, seeded_repo: Path):
        """대조군 — PR 참조가 없는 증적은 해소가 아니다(항상 해소하면 위장이다)."""
        assert _add("T1-66-nopr-noresolve") == 0
        _finish_without_pr("T1-66-nopr-noresolve", "incomplete")
        assert (
            cli.main(
                [
                    "amend",
                    "T1-66-nopr-noresolve",
                    "--artifact",
                    "커밋 a1b2c3d",
                    "--reason",
                    "커밋 해시 보강",
                ]
            )
            == 0
        )
        task = _task(seeded_repo, "T1-66-nopr-noresolve")
        assert "[PR 보류 해소" not in task.notes
        assert "no_pr_resolved" not in _amend_events(seeded_repo, "T1-66-nopr-noresolve")[-1]

    def test_task_without_a_hold_marker_is_not_marked_resolved(self, seeded_repo: Path):
        """대조군 — 애초에 보류가 없던 태스크에 '해소'를 기록하면 대장이 거짓말을 한다."""
        assert _add("T1-67-nopr-none") == 0
        assert cli.main(["start", "T1-67-nopr-none", "--no-remote"]) == 0
        assert cli.main(["done", "T1-67-nopr-none", "--artifact", "PR #10"]) == 0
        assert (
            cli.main(["amend", "T1-67-nopr-none", "--artifact", "PR #11", "--reason", "후속 PR"])
            == 0
        )
        assert "[PR 보류 해소" not in _task(seeded_repo, "T1-67-nopr-none").notes

    def test_resolution_is_recorded_once(self, seeded_repo: Path):
        """두 번째 PR 증적이 해소를 다시 기록하면 대장이 소음으로 부푼다."""
        assert _add("T1-68-nopr-once") == 0
        _finish_without_pr("T1-68-nopr-once", "incomplete")
        assert cli.main(["amend", "T1-68-nopr-once", "--artifact", "PR #1", "--reason", "1차"]) == 0
        assert cli.main(["amend", "T1-68-nopr-once", "--artifact", "PR #2", "--reason", "2차"]) == 0
        assert _task(seeded_repo, "T1-68-nopr-once").notes.count("[PR 보류 해소") == 1


class TestPathsCorrection:
    """④ paths 정정이 **겹침 판정을 실제로 바꾼다** — 오탐 감소가 이 축의 존재 이유다.

    넓게 잡은 glob이 고정되면 overlap 경보가 대량 오탐이 되고, 상시 오탐은 병렬 세션이
    경보를 무시하게 만든다(이 저장소가 이미 겪은 fail-open 습관화). 실측: 2026-09-03
    MOB-20이 `src/mobile/lib/**`로 경보 17건을 냈고 좁힐 CLI 경로가 없어 YAML을 손편집했다.

    주장이 아니라 **판정으로** 증명한다 — `overlap` 서브커맨드가 내는 경보 건수가 줄어야 한다.
    """

    def _seed_three(self) -> None:
        assert _add("T1-70-paths-wide", "--path", "src/mobile/lib/**") == 0
        assert _add("T1-71-paths-attempts", "--path", "src/mobile/lib/features/attempts/**") == 0
        assert _add("T1-72-paths-diagnosis", "--path", "src/mobile/lib/features/diagnosis/**") == 0

    def _overlap_warnings(self, capsys) -> int:
        capsys.readouterr()
        assert cli.main(["overlap", "T1-70-paths-wide"]) == 0
        return capsys.readouterr().out.count("⚠")

    def test_narrowing_paths_reduces_overlap_warnings(self, seeded_repo: Path, capsys):
        self._seed_three()
        assert self._overlap_warnings(capsys) == 2, "넓은 glob이 두 태스크 모두와 겹쳐야 한다"

        assert (
            cli.main(
                [
                    "amend",
                    "T1-70-paths-wide",
                    "--path",
                    "src/mobile/lib/features/attempts/**",
                    "--reason",
                    "실제 작업 범위로 축소 — 경보 오탐 제거",
                ]
            )
            == 0
        )
        assert _task(seeded_repo, "T1-70-paths-wide").paths == [
            "src/mobile/lib/features/attempts/**"
        ]
        # 정정 전/후로 **판정**이 달라진다 — 같은 숫자를 내면 ④의 목적이 성립하지 않는다
        assert self._overlap_warnings(capsys) == 1

    def test_amend_reports_the_overlap_delta(self, seeded_repo: Path, capsys):
        """알고리즘을 붙였으면 *작동한 비율*을 말해야 한다 — 정정 직후 건수 변화를 보고한다."""
        self._seed_three()
        capsys.readouterr()
        assert (
            cli.main(
                [
                    "amend",
                    "T1-70-paths-wide",
                    "--path",
                    "src/mobile/lib/features/attempts/**",
                    "--reason",
                    "범위 축소",
                ]
            )
            == 0
        )
        out = capsys.readouterr().out
        assert "겹침 후보 2건 → 1건" in out
        assert "감소" in out

    def test_replacement_not_append(self, seeded_repo: Path):
        """paths는 **교체**다 — append로는 넓은 패턴을 좁힐 방법이 없다(축의 목적 자체가 무산)."""
        assert _add("T1-73-paths-replace", "--path", "src/mobile/lib/**") == 0
        assert (
            cli.main(
                [
                    "amend",
                    "T1-73-paths-replace",
                    "--path",
                    "src/mobile/lib/core/**",
                    "--reason",
                    "축소",
                ]
            )
            == 0
        )
        paths = _task(seeded_repo, "T1-73-paths-replace").paths
        assert paths == ["src/mobile/lib/core/**"], "이전 넓은 패턴이 남으면 좁혀지지 않는다"

    def test_previous_value_kept_in_notes(self, seeded_repo: Path):
        """교체 축은 이전 값을 notes에 남긴다(HARN-49 track 선례) — 흔적 없이 덮어쓰면 근거가 사라진다."""
        assert _add("T1-74-paths-notes", "--path", "src/mobile/lib/**") == 0
        assert (
            cli.main(
                [
                    "amend",
                    "T1-74-paths-notes",
                    "--path",
                    "src/mobile/lib/core/**",
                    "--reason",
                    "오탐 17건 제거",
                ]
            )
            == 0
        )
        notes = _task(seeded_repo, "T1-74-paths-notes").notes
        assert "src/mobile/lib/**" in notes, "이전 값이 없다 — 왜 좁혔는지 되짚을 수 없다"
        assert "오탐 17건 제거" in notes

    def test_same_paths_rejected(self, seeded_repo: Path):
        assert _add("T1-75-paths-same", "--path", "src/mobile/lib/**") == 0
        assert (
            cli.main(
                ["amend", "T1-75-paths-same", "--path", "src/mobile/lib/**", "--reason", "무변경"]
            )
            == 1
        )

    def test_invalid_pattern_rejected(self, seeded_repo: Path, capsys):
        """절대경로·상위참조는 스키마 위반 — 정정이 대장을 깨뜨리면 안 된다."""
        assert _add("T1-76-paths-bad", "--path", "src/mobile/lib/**") == 0
        assert cli.main(["amend", "T1-76-paths-bad", "--path", "/etc/passwd", "--reason", "x"]) == 1
        assert _task(seeded_repo, "T1-76-paths-bad").paths == ["src/mobile/lib/**"]

    def test_duplicate_path_in_one_call_rejected(self, seeded_repo: Path):
        assert _add("T1-77-paths-dupe") == 0
        assert (
            cli.main(
                [
                    "amend",
                    "T1-77-paths-dupe",
                    "--path",
                    "docs/a/**",
                    "--path",
                    "docs/a/**",
                    "--reason",
                    "x",
                ]
            )
            == 1
        )


class TestTitleCorrection:
    """⑤ title 정정이 **`next`가 내는 줄을 바꾼다** — paths보다 위험도가 높은 축.

    SessionStart 브리핑과 `next`가 노출하는 것은 title 한 줄이다. 범위가 정정된 태스크의 옛
    제목이 남으면 다음 세션이 *정정 전 처방*을 읽고 착수한다 — MOB-20이 acceptance로 범위를
    고친 뒤에도 title이 옛 처방을 1순위 후보로 노출했고, 그대로 구현했으면 이중 적재였다.
    """

    # 실제 MOB-20 제목에 들어 있던 라우트 리터럴은 **일부러 옮겨 쓰지 않는다**:
    # `scripts/analysis/eos_feature_inventory_v2.py`의 테스트 계상은 tests/ 전 파일을
    # 라우트 문자열로 grep하므로, 무관한 테스트 파일이 그 문자열을 담기만 해도 해당
    # 기능의 테스트 함수 수가 통째로 부풀어 인벤토리 대장이 red가 된다(실측).
    _OLD = "시도 제출 엔드포인트 클라 호출 착지"
    _NEW = "숙달 신호 단일 경로 정리 — attempts 직접 호출은 하지 않는다"

    def test_next_line_changes_after_correction(self, seeded_repo: Path, capsys):
        assert _add_titled("T1-80-title-next", self._OLD) == 0
        capsys.readouterr()
        assert cli.main(["next", "--n", "500"]) == 0
        before = capsys.readouterr().out
        assert self._OLD in before, "정정 전에는 옛 제목이 노출된다(이 검사의 전제)"

        assert (
            cli.main(
                [
                    "amend",
                    "T1-80-title-next",
                    "--title",
                    self._NEW,
                    "--reason",
                    "범위 정정 반영 — 옛 처방이 후보로 노출되던 상태 해소",
                ]
            )
            == 0
        )
        capsys.readouterr()
        assert cli.main(["next", "--n", "500"]) == 0
        after = capsys.readouterr().out
        assert self._NEW in after
        assert self._OLD not in after, "옛 제목이 남으면 다음 세션이 정정 전 처방을 읽는다"

    def test_brief_reflects_the_corrected_title(self, seeded_repo: Path, capsys):
        """SessionStart 브리핑도 같은 문자열을 읽는다 — 노출 경로가 둘이므로 둘 다 본다."""
        assert _add_titled("T1-81-title-brief", self._OLD) == 0
        assert (
            cli.main(["amend", "T1-81-title-brief", "--title", self._NEW, "--reason", "정정"]) == 0
        )
        capsys.readouterr()
        assert cli.main(["brief"]) == 0
        out = capsys.readouterr().out
        if "T1-81-title-brief" in out:
            assert self._NEW in out and self._OLD not in out
        else:  # 브리핑은 상위 N건만 낸다 — 노출되지 않았으면 이 검사는 판정 불가다
            pytest.skip("브리핑 상위 목록에 대상 태스크가 없어 노출 여부를 판정할 수 없다")

    def test_previous_title_kept_in_notes(self, seeded_repo: Path):
        assert _add_titled("T1-82-title-notes", self._OLD) == 0
        assert (
            cli.main(["amend", "T1-82-title-notes", "--title", self._NEW, "--reason", "범위 정정"])
            == 0
        )
        notes = _task(seeded_repo, "T1-82-title-notes").notes
        assert self._OLD in notes, "이전 제목이 없다 — 무엇이 어떻게 바뀌었는지 사라진다"

    def test_same_title_rejected(self, seeded_repo: Path):
        assert _add_titled("T1-83-title-same", self._OLD) == 0
        assert (
            cli.main(["amend", "T1-83-title-same", "--title", self._OLD, "--reason", "무변경"]) == 1
        )


class TestFrozenAxesStayFrozen:
    """정밀화의 반대편 — id·status·session은 **여전히** amend가 건드리지 않는다.

    원칙 2를 조용히 지우면 다음 세션이 그 교훈을 잃는다. artifacts·paths·title이 열린 뒤에도
    상태 전이 표면은 닫혀 있어야 하고, 그것을 여기서 기계로 동결한다.
    """

    def test_no_flags_exist_for_state_transition_fields(self, seeded_repo: Path):
        parser = cli.build_parser()
        amend = parser._subparsers._group_actions[0].choices["amend"]  # type: ignore[union-attr]
        options = {opt for action in amend._actions for opt in action.option_strings}
        assert not {"--status", "--session", "--id", "--owner", "--stage"} & options

    def test_multi_axis_amend_leaves_state_untouched(self, seeded_repo: Path):
        assert _add_titled("T1-84-frozen", "옛 제목", "--path", "docs/a/**") == 0
        assert cli.main(["start", "T1-84-frozen", "--no-remote"]) == 0
        before = _task(seeded_repo, "T1-84-frozen")
        assert (
            cli.main(
                [
                    "amend",
                    "T1-84-frozen",
                    "--title",
                    "새 제목",
                    "--path",
                    "docs/b/**",
                    "--artifact",
                    "PR #3",
                    "--reason",
                    "3축 동시 정정",
                ]
            )
            == 0
        )
        after = _task(seeded_repo, "T1-84-frozen")
        assert after.status == before.status == "in_progress"
        assert after.session == before.session
        assert after.id == before.id

    def test_every_axis_previous_value_survives_a_multi_axis_amend(self, seeded_repo: Path):
        """다축 정정에서 *뒤* 축의 이전 값이 사라지면 안 된다.

        구 구현은 notes에 `note_lines[0]`만 남겨, `--title`과 `--priority`를 함께 고치면
        한쪽의 이전 값이 침묵으로 유실됐다 — 이전 값 보존이 교체 축의 유일한 안전장치인데
        그것이 무증상으로 깨지는 형태였다.
        """
        assert _add_titled("T1-85-multinote", "옛 제목", "--path", "docs/a/**") == 0
        assert (
            cli.main(
                [
                    "amend",
                    "T1-85-multinote",
                    "--priority",
                    "1",
                    "--title",
                    "새 제목",
                    "--path",
                    "docs/b/**",
                    "--reason",
                    "3축 정정",
                ]
            )
            == 0
        )
        notes = _task(seeded_repo, "T1-85-multinote").notes
        assert "3 → 1" in notes, "priority 이전 값 유실"
        assert "옛 제목" in notes, "title 이전 값 유실"
        assert "docs/a/**" in notes, "paths 이전 값 유실"


class TestMeaninglessInputRejection:
    """③ 무의미 입력 4종은 **각각 다른 메시지**로 거부한다.

    같은 메시지를 내면 사람이 무엇을 고쳐야 하는지 알 수 없고, 검사가 하나 사라져도 무증상이
    된다(변별력 없는 검증 스텝 = 위장). 빈 문자열과 공백만도 가른다 — 셸 변수가 비어 전달된
    경우와 공백이 섞인 경우는 고칠 지점이 다르다.
    """

    def _reject_message(self, capsys, *argv: str) -> str:
        capsys.readouterr()
        assert cli.main(list(argv)) == 1
        return capsys.readouterr().err

    def test_four_kinds_have_four_distinct_messages(self, seeded_repo: Path, capsys):
        assert _add("T1-86-meaningless") == 0
        _finish_without_pr("T1-86-meaningless", "incomplete", artifact="PR #900")
        base = ["amend", "T1-86-meaningless", "--reason", "x"]

        empty = self._reject_message(capsys, *base, "--artifact", "")
        blank = self._reject_message(capsys, *base, "--artifact", "   ")
        self_id = self._reject_message(capsys, *base, "--artifact", "T1-86-meaningless")
        same = self._reject_message(capsys, *base, "--artifact", "PR #900")

        assert "빈" in empty
        assert "공백" in blank
        assert "자기 태스크 id" in self_id
        assert "동일한 증적이 이미 있다" in same
        assert len({empty, blank, self_id, same}) == 4, "네 거부가 같은 말을 하면 진단이 아니다"

    def test_rejection_writes_nothing(self, seeded_repo: Path):
        """거부는 **쓰기 0** — 절반 기록되면 notes만 오염되고 정정은 안 된 상태가 된다."""
        assert _add("T1-87-meaningless-write", "--path", "docs/a/**") == 0
        before = _task(seeded_repo, "T1-87-meaningless-write")
        assert (
            cli.main(["amend", "T1-87-meaningless-write", "--artifact", "  ", "--reason", "x"]) == 1
        )
        after = _task(seeded_repo, "T1-87-meaningless-write")
        assert after.artifacts == before.artifacts
        assert after.notes == before.notes
        assert after.paths == before.paths

    @pytest.mark.parametrize("axis", ["--path", "--title"])
    def test_blank_rejected_on_every_new_axis(self, seeded_repo: Path, capsys, axis: str):
        """세 축 모두가 무의미 입력을 거부한다 — 한 축만 검사하면 나머지가 뚫린다."""
        task_id = f"T1-88-blank{'p' if axis == '--path' else 't'}"
        assert _add(task_id) == 0
        capsys.readouterr()
        assert cli.main(["amend", task_id, axis, "   ", "--reason", "x"]) == 1
        assert "공백" in capsys.readouterr().err

    def test_empty_string_reaches_the_blank_diagnosis_on_title(self, seeded_repo: Path, capsys):
        """`--title ""`은 *지정된* 빈 값이다 — "변경 항목이 없다"로 새면 진단이 거짓말이 된다.

        실측(2026-09-07 검증자): 무변경 가드가 title을 truthiness로 보던 동안 `--title ""`은
        "변경 항목이 없다"로 거부됐다. exit 1은 같아서 **거부된다는 사실만 보면 정상으로
        보인다** — 틀린 것은 사람이 어디를 고쳐야 하는지였다(셸 변수가 비어 전달된 경우가
        정확히 이 형태다). 공백만(`"   "`)은 통과 경로가 달라 이 결함을 드러내지 못한다.
        """
        assert _add("T1-90-empty-title") == 0
        capsys.readouterr()
        assert cli.main(["amend", "T1-90-empty-title", "--title", "", "--reason", "x"]) == 1
        err = capsys.readouterr().err
        assert "빈 title 값은 받지 않는다" in err, err
        assert "변경 항목이 없다" not in err, err

    def test_self_id_rejected_as_title(self, seeded_repo: Path, capsys):
        """제목이 자기 id면 `next` 줄이 'ID ID'가 되어 아무것도 말하지 않는다."""
        assert _add("T1-89-self-title") == 0
        capsys.readouterr()
        assert (
            cli.main(["amend", "T1-89-self-title", "--title", "T1-89-self-title", "--reason", "x"])
            == 1
        )
        assert "자기 태스크 id" in capsys.readouterr().err


class TestNewAxesHitTheReasonFeedbackGuard:
    """⑥ 새 플래그의 `--reason`도 HARN-53 되먹임 가드를 탄다 — 가드를 복제하지 않고 재사용한다.

    `--reason`은 notes에 append되고 notes는 의존 선언 스캐너의 입력이다. 새 축이 가드를
    우회하면 "정정 사유가 새 위반을 만드는" 되먹임이 이 경로로만 되살아난다.
    """

    @pytest.mark.parametrize(
        "axis_argv",
        [
            ["--artifact", "PR #5"],
            ["--path", "docs/z/**"],
            ["--title", "새 제목"],
        ],
        ids=["artifact", "path", "title"],
    )
    def test_guard_applies_to_each_new_axis(self, seeded_repo: Path, capsys, axis_argv: list[str]):
        target = f"T1-93-guard{axis_argv[0][2]}"
        assert _add(target) == 0
        assert _add("T1-94-guard-ref") == 0
        before = _task(seeded_repo, target)
        capsys.readouterr()
        assert (
            cli.main(
                ["amend", target, *axis_argv, "--reason", "T1-94 착지 후 재검토한다"],
            )
            == 1
        )
        assert "새 의존 선언을 만든다" in capsys.readouterr().err
        after = _task(seeded_repo, target)
        # 거부는 쓰기 0 — 가드가 통과시킨 뒤 되돌리는 형태면 대장이 잠깐 오염된다
        assert after.artifacts == before.artifacts
        assert after.paths == before.paths
        assert after.title == before.title
        assert after.notes == before.notes

    def test_harmless_reason_still_passes_on_new_axes(self, seeded_repo: Path):
        """양성 대조 — 무조건 거부면 가드가 아니라 정정 차단기다."""
        assert _add("T1-95-guard-ok") == 0
        assert (
            cli.main(
                ["amend", "T1-95-guard-ok", "--title", "정정된 제목", "--reason", "범위 정정 반영"]
            )
            == 0
        )
        assert _task(seeded_repo, "T1-95-guard-ok").title == "정정된 제목"
