"""HARN-42 — 차단(block)의 원격 게시: 머지 없이 병렬 세션에 즉시 보이게.

**결함 (2026-08-31 실측 사고)**: `cmd_block`은 태스크 YAML에 `blocked`를 쓰고 원격
claim을 *해제*했다. 그런데 YAML은 **main에 머지돼야** 병렬 세션에 보이고, 이 저장소의
머지 지연은 CI(~30분) + base 전진 경합(HARN-32)으로 시간 단위다. 즉 차단은 보호를 거는
순간 유일한 교차 세션 신호를 **지웠고**, 그 창에서 다른 세션이 아무 마찰 없이 착수했다.

실사고 시간선 — `CUR-11`:
  00:28:07  세션 A가 block (Kiki 승인 게이트 대기)
  00:41:24  세션 B가 원격 claim — 마찰 0
  ~03:40    세션 B가 구현·머지 완료(PR #920) → 차단은 끝내 발효하지 못함

차단은 대장에 실재했고 `next`에서도 사라졌다. 그런데도 **미머지 브랜치에 있었기 때문에**
아무것도 막지 못했다. 교훈: 대장 조치의 실효 시점은 조치 시점이 아니라 머지 시점이다.

**해소**: `harness-claims` 브랜치는 머지 없이 즉시 push되는 유일한 교차 세션 채널이다.
차단을 그 채널에 `kind="block"` 레코드로 실어 보호가 조치 시점에 발효하게 한다.

이 파일이 계약으로 동결하는 것:
  ① 실사고 재현 — A가 block한 뒤 B의 `start`가 **거부**된다(수정 전에는 통과했다).
  ② 차단과 착수 claim이 **구별**된다 — 안내가 `unblock`을 가리키고 `--force` 탈취를
     유도하지 않는다.
  ③ `unblock`이 홀드를 걷는다 — 안 걷으면 해제된 태스크가 영구 차단으로 보인다.
  ④ 차단이 남의 **진행 중 claim을 덮어쓰지 않는다**(적대적 탈취 방지).
  ⑤ 게시 실패는 침묵하지 않는다 — "로컬에만 있다"를 명시한다(fail-open 위장 금지).
"""

from __future__ import annotations

import json
from pathlib import Path

import remote_claims
import store

import backlog as cli

TASK = "T1-01-block-hold-target"


def _seed_session(path: Path, monkeypatch) -> None:
    monkeypatch.chdir(path)
    assert cli.main(["seed"]) == 0


def _add(task_id: str = TASK) -> int:
    return cli.main(
        [
            "add",
            "--eos-priority",
            "P2",
            "--id",
            task_id,
            "--title",
            "HARN-42 차단 홀드 대상",
            "--track",
            "math-completion",
            "--stage",
            "S1",
        ]
    )


class TestIncidentReproduction:
    """① 실사고 재현 — 차단 후 타 세션 착수가 실제로 막히는가."""

    def test_block_in_session_a_refuses_start_in_session_b(self, bare_remote, monkeypatch):
        """CUR-11 사고 그대로: A가 block → B가 start → **거부**돼야 한다."""
        _, clone = bare_remote
        a, b = clone("session-a"), clone("session-b")

        _seed_session(a, monkeypatch)
        assert _add() == 0
        assert cli.main(["block", TASK, "--reason", "관여도 판정 대기"]) == 0

        # 세션 B는 A의 브랜치를 못 본다 — main에 머지되지 않았으므로 태스크 YAML도 없다.
        # 원격 대장만이 유일한 채널이다.
        _seed_session(b, monkeypatch)
        assert _add() == 0  # B의 로컬 대장에서는 여전히 todo
        assert cli.main(["start", TASK]) == 1, "차단된 태스크를 타 세션이 착수했다 — 사고 재현"

    def test_block_hold_visible_in_remote_ledger(self, bare_remote, monkeypatch):
        """홀드가 원격 대장에 kind=block으로 실린다 — 채널 실재 확인."""
        _, clone = bare_remote
        a = clone("session-a")
        _seed_session(a, monkeypatch)
        assert _add() == 0
        assert cli.main(["block", TASK, "--reason", "사유 텍스트 X"]) == 0

        claims, status = remote_claims.list_claims(a, with_meta=True)
        assert status == "ok"
        held = [c for c in claims if c.task_id == TASK]
        assert len(held) == 1
        assert held[0].kind == "block"
        assert held[0].reason == "사유 텍스트 X"


class TestBlockVsClaimDistinction:
    """② 차단과 착수 claim은 해소 경로가 다르다 — 안내가 구별돼야 한다."""

    def test_start_message_points_to_unblock_not_force(self, bare_remote, monkeypatch, capsys):
        _, clone = bare_remote
        a, b = clone("session-a"), clone("session-b")
        _seed_session(a, monkeypatch)
        assert _add() == 0
        assert cli.main(["block", TASK, "--reason", "게이트 대기"]) == 0

        _seed_session(b, monkeypatch)
        assert _add() == 0
        capsys.readouterr()
        assert cli.main(["start", TASK]) == 1
        err = capsys.readouterr().err
        assert "차단" in err, "차단을 '남이 작업 중'으로 안내하면 --force 탈취를 유도한다"
        assert "unblock" in err
        assert "게이트 대기" in err, "차단 사유가 안내에 실려야 판단이 가능하다"

    def test_plain_claim_message_unchanged(self, bare_remote, monkeypatch, capsys):
        """변별력 — 일반 claim 충돌은 기존 안내(release --force)를 그대로 낸다."""
        _, clone = bare_remote
        a, b = clone("session-a"), clone("session-b")
        _seed_session(a, monkeypatch)
        assert _add() == 0
        assert cli.main(["start", TASK]) == 0  # 평범한 착수 claim

        _seed_session(b, monkeypatch)
        assert _add() == 0
        capsys.readouterr()
        assert cli.main(["start", TASK]) == 1
        err = capsys.readouterr().err
        assert "원격 claim" in err
        assert "release" in err
        assert "차단" not in err


class TestUnblockReleasesHold:
    """③ unblock이 홀드를 걷는다 — 안 걷으면 영구 차단이 된다."""

    def test_unblock_clears_remote_hold(self, bare_remote, monkeypatch):
        _, clone = bare_remote
        a, b = clone("session-a"), clone("session-b")
        _seed_session(a, monkeypatch)
        assert _add() == 0
        assert cli.main(["block", TASK, "--reason", "임시"]) == 0
        assert cli.main(["unblock", TASK]) == 0
        assert [c for c in remote_claims.list_claims(a)[0] if c.task_id == TASK] == []

        # 해제 후에는 타 세션이 정상 착수할 수 있어야 한다
        _seed_session(b, monkeypatch)
        assert _add() == 0
        assert cli.main(["start", TASK]) == 0


class TestNoHostileTakeover:
    """④ 차단이 남의 진행 중 claim을 덮어쓰지 않는다."""

    def test_block_does_not_steal_active_claim(self, bare_remote, monkeypatch):
        _, clone = bare_remote
        a, b = clone("session-a"), clone("session-b")
        _seed_session(a, monkeypatch)
        assert _add() == 0
        assert cli.main(["start", TASK]) == 0  # A가 착수 중

        # B가 같은 태스크를 차단하려 해도 A의 claim은 살아 있어야 한다
        result = remote_claims.hold(b, TASK, "claude/session-b", "차단 시도")
        assert result.status == "conflict"
        claims, _ = remote_claims.list_claims(a, with_meta=True)
        held = [c for c in claims if c.task_id == TASK]
        assert held[0].kind == "claim"
        assert held[0].branch == "claude/session-a"


class TestFailureIsLoud:
    """⑤ 게시 실패는 침묵하지 않는다 — fail-open을 '보호 있음'으로 위장 금지."""

    def test_offline_block_warns_local_only(self, git_repo: Path, monkeypatch, capsys):
        """origin이 없는 저장소에서 block하면 '로컬에만 있다'를 명시해야 한다."""
        monkeypatch.chdir(git_repo)
        assert cli.main(["seed"]) == 0
        assert _add() == 0
        capsys.readouterr()
        assert cli.main(["block", TASK, "--reason", "오프라인 차단"]) == 0
        err = capsys.readouterr().err
        assert "로컬에만" in err, "게시 실패를 알리지 않으면 없는 보호를 있다고 믿게 된다"
        # 그리고 그 사실이 이벤트 대장에도 남는다
        # 이벤트 대장 샤딩(HARN-46) — 레거시+샤드를 함께 읽는다
        evs = [
            json.loads(x)
            for path in store.event_paths(git_repo)
            for x in path.read_text(encoding="utf-8").splitlines()
            if x.strip()
        ]
        assert any(e.get("action") == "block_hold_failed" and e.get("id") == TASK for e in evs)


class TestHandoverIsStillPossible:
    """양방향 변별력 (HARN-45 acceptance ②) — 자리 보전과 인계가 **둘 다** 가능해야 한다.

    HARN-48의 수정은 "차단이 자리를 지킨다"만 만들었다. 그것만 검증하면 **반대 결함**을
    못 잡는다 — *아무도 이어받을 수 없는* 영구 점유다. HARN-45가 독립 사고(HARN-38,
    05:00:05Z)에서 같은 뿌리를 발견하며 정확히 이 축을 요구했다.

    구분: **게이트 대기**는 자리를 지켜야 하고(기본), **인계 차단**은 남이 이어받을 수
    있어야 한다(`--handover`). 두 방향을 함께 동결한다.
    """

    def test_handover_block_releases_seat(self, bare_remote, monkeypatch):
        """--handover 차단은 자리를 비운다 — 타 세션이 이어받을 수 있어야 한다."""
        _, clone = bare_remote
        a, b = clone("session-a"), clone("session-b")
        _seed_session(a, monkeypatch)
        assert _add() == 0
        assert cli.main(["block", TASK, "--reason", "설계 재검토 필요 — 인계", "--handover"]) == 0
        assert [c for c in remote_claims.list_claims(a)[0] if c.task_id == TASK] == []

        _seed_session(b, monkeypatch)
        assert _add() == 0
        assert cli.main(["start", TASK]) == 0, "인계 차단인데 타 세션이 이어받지 못했다"

    def test_default_block_keeps_seat(self, bare_remote, monkeypatch):
        """변별력 대조 — 기본 차단은 여전히 자리를 지킨다(같은 픽스처·플래그만 차이)."""
        _, clone = bare_remote
        a, b = clone("session-a"), clone("session-b")
        _seed_session(a, monkeypatch)
        assert _add() == 0
        assert cli.main(["block", TASK, "--reason", "게이트 대기"]) == 0

        _seed_session(b, monkeypatch)
        assert _add() == 0
        assert cli.main(["start", TASK]) == 1, "기본 차단이 자리를 못 지켰다"

    def test_handover_recorded_in_event(self, bare_remote, monkeypatch):
        """어느 쪽 의도였는지 대장에 남는다 — 나중에 판정 가능해야 한다."""
        _, clone = bare_remote
        a = clone("session-a")
        _seed_session(a, monkeypatch)
        assert _add() == 0
        assert cli.main(["block", TASK, "--reason", "인계", "--handover"]) == 0
        evs = [
            json.loads(x)
            for path in store.event_paths(a)
            for x in path.read_text(encoding="utf-8").splitlines()
            if x.strip()
        ]
        blocks = [e for e in evs if e.get("action") == "block" and e.get("id") == TASK]
        assert blocks and blocks[-1]["handover"] is True


class TestBackwardCompatibility:
    """구버전 레코드(kind 없음)는 claim으로 읽는다 — 메타 파손이 차단으로 둔갑하면 안 된다."""

    def test_legacy_record_without_kind_is_claim(self):
        legacy = remote_claims.RemoteClaim("X-01", "sha", "claude/old", "ts", {"branch": "x"})
        assert legacy.kind == "claim"
        broken = remote_claims.RemoteClaim("X-02", "sha", "", "", None)
        assert broken.kind == "claim"
