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
