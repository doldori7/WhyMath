"""`backlog.py amend --track` + 트랙 구조 가드 (HARN-49).

이 스위트가 지키는 것은 두 가지다.

1. **정정 경로가 실제로 착수 가능성을 바꾼다** — amend 전후로 `start`의 판정이 달라져야
   한다. 같은 결과면 verb가 아무것도 안 한 것이고, 그건 검증이 아니라 위장이다.
2. **구조 가드가 오분류만 잡는다** — 진입 게이트가 있는 트랙에서 stage가 동료 전원보다
   앞서는 태스크만 경고하고, 정상 배치는 조용해야 한다.

실피해 맥락: S1-16이 `stage: S1`인데 `track: subject-expansion`(진입 게이트 S5)으로
등재돼 12일간 착수 불가였다. `start`에 track_gate 우회 플래그는 없고 대장 손편집은
금지이므로, 정정 경로 자체가 없었다.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import store

import backlog as cli


@pytest.fixture
def seeded_repo(git_repo: Path, monkeypatch) -> Path:
    monkeypatch.chdir(git_repo)
    assert cli.main(["seed"]) == 0
    return git_repo


def _gated_track(repo: Path) -> tuple[str, str]:
    """시드 대장에서 진입 게이트가 있는 트랙과 그 게이트 id."""
    backlog, _ = store.load_backlog(repo)
    for name, track in backlog.tracks.items():
        gate = getattr(track, "entry_gate", None)
        if gate:
            return name, gate
    pytest.skip("시드에 진입 게이트가 있는 트랙이 없다")


def _open_track(repo: Path) -> str:
    backlog, _ = store.load_backlog(repo)
    for name, track in backlog.tracks.items():
        if not getattr(track, "entry_gate", None):
            return name
    pytest.skip("시드에 게이트 없는 트랙이 없다")


def _add(repo: Path, task_id: str, track: str, stage: str) -> None:
    assert (
        cli.main(
            [
                "add",
                "--id",
                task_id,
                "--title",
                f"{task_id} 픽스처",
                "--track",
                track,
                "--stage",
                stage,
                "--subject",
                "math",
                "--layer",
                "backend",
                "--acceptance",
                "픽스처",
            ]
        )
        == 0
    )


# ──────────────────────────────────────────────────────────────────────
# ① 정정 경로가 착수 가능성을 바꾸는가 (acceptance ④)
# ──────────────────────────────────────────────────────────────────────


def test_amend_track_unblocks_a_task_the_gate_was_holding(seeded_repo: Path) -> None:
    """정정 전 거부 → 정정 후 통과. 네 상태 중 하나라도 같으면 verb가 무의미하다."""
    gated, _ = _gated_track(seeded_repo)
    open_track = _open_track(seeded_repo)
    _add(seeded_repo, "S1-90-fixture", gated, "S1")

    assert cli.main(["start", "S1-90-fixture", "--no-remote"]) == 1, "게이트가 막지 않았다"

    assert (
        cli.main(["amend", "S1-90-fixture", "--track", open_track, "--reason", "오분류 정정"]) == 0
    )
    assert cli.main(["start", "S1-90-fixture", "--no-remote"]) == 0, "정정 후에도 막힌다"


def test_reverting_the_track_restores_the_rejection(seeded_repo: Path) -> None:
    """되돌리면 다시 거부돼야 한다 — 통과가 amend 때문임을 보이는 대조군."""
    gated, _ = _gated_track(seeded_repo)
    open_track = _open_track(seeded_repo)
    _add(seeded_repo, "S1-91-fixture", gated, "S1")

    cli.main(["amend", "S1-91-fixture", "--track", open_track, "--reason", "정정"])
    assert cli.main(["start", "S1-91-fixture", "--no-remote"]) == 0
    cli.main(["block", "S1-91-fixture", "--reason", "되돌림 준비"])
    cli.main(["unblock", "S1-91-fixture"])

    cli.main(["amend", "S1-91-fixture", "--track", gated, "--reason", "되돌림"])
    assert cli.main(["start", "S1-91-fixture", "--no-remote"]) == 1, "되돌렸는데 여전히 통과한다"


# ──────────────────────────────────────────────────────────────────────
# ② 정정이 기록을 남기는가 (덮어쓰기 금지)
# ──────────────────────────────────────────────────────────────────────


def test_amend_records_the_previous_value_in_notes(seeded_repo: Path) -> None:
    gated, _ = _gated_track(seeded_repo)
    open_track = _open_track(seeded_repo)
    _add(seeded_repo, "S1-92-fixture", gated, "S1")

    cli.main(["amend", "S1-92-fixture", "--track", open_track, "--reason", "사유가 남아야 한다"])
    backlog, _ = store.load_backlog(seeded_repo)
    task = backlog.tasks["S1-92-fixture"]
    assert task.track == open_track
    assert gated in task.notes, "이전 값이 notes에 없다 — 정정이 흔적 없이 덮어썼다"
    assert "사유가 남아야 한다" in task.notes


def test_amend_does_not_touch_other_fields(seeded_repo: Path) -> None:
    """정정은 track만 바꾼다 — status·session이 함께 움직이면 상태 기계가 오염된다."""
    gated, _ = _gated_track(seeded_repo)
    open_track = _open_track(seeded_repo)
    _add(seeded_repo, "S1-93-fixture", gated, "S1")
    before, _ = store.load_backlog(seeded_repo)
    prev = before.tasks["S1-93-fixture"]
    prev_status, prev_stage, prev_session = prev.status, prev.stage, prev.session

    cli.main(["amend", "S1-93-fixture", "--track", open_track, "--reason", "정정"])
    after, _ = store.load_backlog(seeded_repo)
    task = after.tasks["S1-93-fixture"]
    assert (task.status, task.stage, task.session) == (prev_status, prev_stage, prev_session)


# ──────────────────────────────────────────────────────────────────────
# ③ 거부해야 할 입력
# ──────────────────────────────────────────────────────────────────────


def test_amend_rejects_unknown_track(seeded_repo: Path) -> None:
    """tracks.yaml에 없는 트랙으로 옮기면 태스크가 어느 트랙에도 안 속한다."""
    gated, _ = _gated_track(seeded_repo)
    _add(seeded_repo, "S1-94-fixture", gated, "S1")
    assert cli.main(["amend", "S1-94-fixture", "--track", "없는트랙", "--reason", "x"]) == 1


def test_amend_rejects_noop(seeded_repo: Path) -> None:
    """같은 값으로의 정정은 이벤트 대장에 의미 없는 행만 남긴다."""
    gated, _ = _gated_track(seeded_repo)
    _add(seeded_repo, "S1-95-fixture", gated, "S1")
    assert cli.main(["amend", "S1-95-fixture", "--track", gated, "--reason", "x"]) == 1


def test_amend_rejects_missing_task(seeded_repo: Path) -> None:
    assert cli.main(["amend", "없는태스크", "--track", "math-completion", "--reason", "x"]) == 1


def test_amend_requires_a_field_to_change(seeded_repo: Path) -> None:
    """--track 없이 부르면 아무것도 안 하고 성공하면 안 된다(HARN-24가 축을 늘릴 자리)."""
    gated, _ = _gated_track(seeded_repo)
    _add(seeded_repo, "S1-96-fixture", gated, "S1")
    assert cli.main(["amend", "S1-96-fixture", "--reason", "x"]) == 1


# ──────────────────────────────────────────────────────────────────────
# ④ 구조 가드 — 오분류만 잡는가 (acceptance ⑤)
# ──────────────────────────────────────────────────────────────────────


def test_guard_flags_a_stage_outlier_on_a_gated_track(seeded_repo: Path) -> None:
    gated, gate_id = _gated_track(seeded_repo)
    _add(seeded_repo, "S1-97-fixture", gated, "S1")
    backlog, _ = store.load_backlog(seeded_repo)
    warnings = cli._stage_outliers_on_gated_tracks(backlog)
    assert any("S1-97-fixture" in w for w in warnings), "오분류를 못 잡았다"
    assert any(gate_id in w for w in warnings), "어느 게이트가 막는지 알려주지 않는다"


def test_guard_is_quiet_when_the_task_belongs_where_it_is(seeded_repo: Path) -> None:
    """정상 배치는 경고하지 않는다 — 상시 경고는 습관화돼 소음이 된다."""
    gated, _ = _gated_track(seeded_repo)
    backlog, _ = store.load_backlog(seeded_repo)
    peers = [t.stage for t in backlog.tasks.values() if t.track == gated]
    if not peers:
        pytest.skip("게이트 트랙에 태스크가 없다")
    _add(seeded_repo, "E9-01-fixture", gated, max(peers, key=backlog.stage_order.index))
    backlog, _ = store.load_backlog(seeded_repo)
    warnings = cli._stage_outliers_on_gated_tracks(backlog)
    assert not any("E9-01-fixture" in w for w in warnings), "정상 배치를 오탐했다"


def test_guard_ignores_ungated_tracks(seeded_repo: Path) -> None:
    """진입 게이트가 없으면 stage가 이질적이어도 착수를 막지 않으므로 경고할 이유가 없다."""
    open_track = _open_track(seeded_repo)
    _add(seeded_repo, "S0-90-fixture", open_track, "S0")
    backlog, _ = store.load_backlog(seeded_repo)
    warnings = cli._stage_outliers_on_gated_tracks(backlog)
    assert not any("S0-90-fixture" in w for w in warnings)


def test_guard_needs_a_peer_to_call_something_an_outlier(seeded_repo: Path) -> None:
    """소속 1건뿐인 트랙에서는 이질성을 말할 수 없다 — 비교 대상이 없다."""
    backlog, _ = store.load_backlog(seeded_repo)
    lone = {
        name
        for name, track in backlog.tracks.items()
        if getattr(track, "entry_gate", None)
        and sum(1 for t in backlog.tasks.values() if t.track == name) <= 1
    }
    for name in lone:
        warnings = cli._stage_outliers_on_gated_tracks(backlog)
        assert not any(f"트랙 '{name}'" in w for w in warnings)


def test_validate_surfaces_the_warning_without_failing(seeded_repo: Path, capsys) -> None:
    """구조 의심은 무결성 위반이 아니다 — exit 0을 바꾸면 의도적 배치까지 막는다."""
    gated, _ = _gated_track(seeded_repo)
    _add(seeded_repo, "S1-98-fixture", gated, "S1")
    capsys.readouterr()
    assert cli.main(["validate"]) == 0
    err = capsys.readouterr().err
    assert "트랙 구조 의심" in err
    assert "S1-98-fixture" in err
    assert "amend" in err, "정정 방법을 알려주지 않으면 경고가 행동으로 이어지지 않는다"
