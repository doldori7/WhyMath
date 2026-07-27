"""selector.py — 순차 조율 알고리즘 테스트 (필터 6종·정렬 결정성·정지 사유)."""

from __future__ import annotations

import selector
from models import Backlog, Gate, Task, Track


def _backlog(
    tasks: list[Task],
    gates: list[Gate] | None = None,
    tracks: list[Track] | None = None,
    stage_order: list[str] | None = None,
) -> Backlog:
    backlog = Backlog(stage_order=stage_order or ["S1", "S2", "E1"])
    for track in tracks or [Track(id="main", title="기본 트랙")]:
        backlog.tracks[track.id] = track
    for gate in gates or []:
        backlog.gates[gate.id] = gate
    for task in tasks:
        backlog.tasks[task.id] = task
    return backlog


def _task(**overrides) -> Task:
    base = dict(id="S1-01-alpha", title="알파", track="main", stage="S1", updated="2026-07-08")
    base.update(overrides)
    return Task(**base)


class TestCandidateFilters:
    def test_의존성_미해소_제외(self):
        backlog = _backlog(
            [
                _task(id="S1-01-alpha", depends_on=["S1-02-beta"]),
                _task(id="S1-02-beta", title="베타"),
            ]
        )
        ready, excluded = selector.candidates(backlog)
        assert [t.id for t in ready] == ["S1-02-beta"]
        assert excluded[0].reason == "deps"

    def test_의존성_done이면_후보_포함(self):
        backlog = _backlog(
            [
                _task(id="S1-01-alpha", depends_on=["S1-02-beta"]),
                _task(id="S1-02-beta", title="베타", status="done", artifacts=["PR#1"]),
            ]
        )
        ready, _ = selector.candidates(backlog)
        assert [t.id for t in ready] == ["S1-01-alpha"]

    def test_pending_게이트_제외(self):
        backlog = _backlog(
            [_task(requires_gates=["G-key"])],
            gates=[Gate(id="G-key", title="키")],
        )
        ready, excluded = selector.candidates(backlog)
        assert ready == []
        assert excluded[0].reason == "gates"

    def test_waived_게이트는_통과(self):
        backlog = _backlog(
            [_task(requires_gates=["G-key"])],
            gates=[Gate(id="G-key", title="키", status="waived")],
        )
        ready, _ = selector.candidates(backlog)
        assert len(ready) == 1

    def test_사람_소유_태스크_제외(self):
        backlog = _backlog([_task(owner="kiki")])
        ready, excluded = selector.candidates(backlog)
        assert ready == []
        assert excluded[0].reason == "owner"

    def test_트랙_entry_gate_하드락(self):
        # E축 트랙은 S5 게이트 통과 전 후보에서 알고리즘 수준으로 제외
        backlog = _backlog(
            [_task(id="E1-01-physics", stage="E1", track="expansion", subject="physics")],
            gates=[Gate(id="G-s5", title="확장 게이트")],
            tracks=[Track(id="expansion", title="E축", entry_gate="G-s5")],
        )
        ready, excluded = selector.candidates(backlog)
        assert ready == []
        assert excluded[0].reason == "track_gate"

    def test_entry_gate_통과_후_해금(self):
        backlog = _backlog(
            [_task(id="E1-01-physics", stage="E1", track="expansion", subject="physics")],
            gates=[Gate(id="G-s5", title="확장 게이트", status="cleared", evidence="판정 문서")],
            tracks=[Track(id="expansion", title="E축", entry_gate="G-s5")],
        )
        ready, _ = selector.candidates(backlog)
        assert [t.id for t in ready] == ["E1-01-physics"]

    def test_타_세션_claim_제외(self):
        backlog = _backlog([_task(session="other-branch")])
        ready, excluded = selector.candidates(backlog)
        assert ready == []
        assert excluded[0].reason == "claimed"

    def test_layer_subject_필터(self):
        backlog = _backlog(
            [
                _task(id="S1-01-alpha", layer="backend"),
                _task(id="S1-02-beta", title="베타", layer="mobile", subject="physics"),
            ]
        )
        ready, _ = selector.candidates(backlog, layer="mobile")
        assert [t.id for t in ready] == ["S1-02-beta"]
        ready, _ = selector.candidates(backlog, subject="physics")
        assert [t.id for t in ready] == ["S1-02-beta"]


class TestOrdering:
    def test_스테이지가_우선순위보다_우선(self):
        # S1 잔여(priority 5)가 S2(priority 1)보다 먼저
        backlog = _backlog(
            [
                _task(id="S2-01-later", stage="S2", priority=1),
                _task(id="S1-01-alpha", priority=5),
            ]
        )
        ready, _ = selector.candidates(backlog)
        assert [t.id for t in ready] == ["S1-01-alpha", "S2-01-later"]

    def test_같은_스테이지는_priority_우선(self):
        backlog = _backlog(
            [
                _task(id="S1-02-beta", title="베타", priority=1),
                _task(id="S1-01-alpha", priority=3),
            ]
        )
        ready, _ = selector.candidates(backlog)
        assert [t.id for t in ready] == ["S1-02-beta", "S1-01-alpha"]

    def test_해금_후속_수가_많은_병목_우선(self):
        backlog = _backlog(
            [
                _task(id="S1-01-alpha", priority=2),
                _task(id="S1-02-bottleneck", title="병목", priority=2),
                _task(id="S1-03-child-a", title="a", depends_on=["S1-02-bottleneck"]),
                _task(id="S1-04-child-b", title="b", depends_on=["S1-02-bottleneck"]),
            ]
        )
        ready, _ = selector.candidates(backlog)
        assert ready[0].id == "S1-02-bottleneck"

    def test_정렬은_결정적(self):
        tasks = [_task(id=f"S1-{i:02d}-t{i}", title=str(i)) for i in range(1, 6)]
        backlog = _backlog(tasks)
        first = [t.id for t in selector.candidates(backlog)[0]]
        second = [t.id for t in selector.candidates(backlog)[0]]
        assert first == second == sorted(first)


class TestStallReason:
    def test_전부_완료(self):
        backlog = _backlog([_task(status="done", artifacts=["PR#1"])])
        _, excluded = selector.candidates(backlog)
        code, _ = selector.stall_reason(backlog, excluded)
        assert code == "all_done"

    def test_사람_게이트_대기(self):
        backlog = _backlog(
            [_task(requires_gates=["G-key"])],
            gates=[Gate(id="G-key", title="키")],
        )
        _, excluded = selector.candidates(backlog)
        code, detail = selector.stall_reason(backlog, excluded)
        assert code == "human_gate"
        assert detail == ["G-key"]

    def test_트랙_게이트도_사람_대기로_분류(self):
        backlog = _backlog(
            [_task(id="E1-01-physics", stage="E1", track="expansion")],
            gates=[Gate(id="G-s5", title="확장 게이트")],
            tracks=[Track(id="expansion", title="E축", entry_gate="G-s5")],
        )
        _, excluded = selector.candidates(backlog)
        code, detail = selector.stall_reason(backlog, excluded)
        assert code == "human_gate"
        assert detail == ["G-s5"]

    def test_다른_세션_진행_중(self):
        backlog = _backlog(
            [
                _task(status="in_progress", session="other-branch"),
            ]
        )
        _, excluded = selector.candidates(backlog)
        code, detail = selector.stall_reason(backlog, excluded)
        assert code == "in_progress"
        assert "S1-01-alpha (other-branch)" in detail


class TestHumanOwnerPath:
    """HARN-06 — 사람-소유 태스크: 자동 후보 제외는 불변, 명시 기입 경로만 owner를 통과."""

    def test_owner_제외_기본_불변(self):
        """candidates(자동 후보)는 owner!=claude를 계속 제외한다 — 자동 착수 방지."""
        backlog = _backlog([_task(owner="kiki")])
        ready, excluded = selector.candidates(backlog)
        assert ready == []
        assert excluded[0].reason == "owner"

    def test_allow_human_owner는_owner만_통과(self):
        """allow_human_owner=True면 owner 제외를 건너뛰어 착수 가능(None)."""
        backlog = _backlog([_task(owner="kiki")])
        task = backlog.tasks["S1-01-alpha"]
        assert selector.classify_todo(backlog, task) is not None  # 기본은 제외
        assert selector.classify_todo(backlog, task, allow_human_owner=True) is None

    def test_allow_human_owner도_deps는_검사(self):
        """사람 기입 경로도 의존성 미해소면 거부 — owner 외 검사는 우회 아님."""
        backlog = _backlog(
            [
                _task(owner="kiki", depends_on=["S1-02-beta"]),
                _task(id="S1-02-beta", title="베타"),
            ]
        )
        task = backlog.tasks["S1-01-alpha"]
        exclusion = selector.classify_todo(backlog, task, allow_human_owner=True)
        assert exclusion is not None and exclusion.reason == "deps"

    def test_allow_human_owner도_게이트는_검사(self):
        """사람 기입 경로도 pending 게이트면 거부."""
        from models import Gate

        backlog = _backlog(
            [_task(owner="kiki", requires_gates=["G-key"])],
            gates=[Gate(id="G-key", title="키")],
        )
        task = backlog.tasks["S1-01-alpha"]
        exclusion = selector.classify_todo(backlog, task, allow_human_owner=True)
        assert exclusion is not None and exclusion.reason == "gates"
