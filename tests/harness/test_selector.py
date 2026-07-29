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
    def test_unresolved_dependency_is_excluded(self):
        """의존성 미해소 제외."""
        backlog = _backlog(
            [
                _task(id="S1-01-alpha", depends_on=["S1-02-beta"]),
                _task(id="S1-02-beta", title="베타"),
            ]
        )
        ready, excluded = selector.candidates(backlog)
        assert [t.id for t in ready] == ["S1-02-beta"]
        assert excluded[0].reason == "deps"

    def test_done_dependency_makes_task_a_candidate(self):
        """의존성 done이면 후보 포함."""
        backlog = _backlog(
            [
                _task(id="S1-01-alpha", depends_on=["S1-02-beta"]),
                _task(id="S1-02-beta", title="베타", status="done", artifacts=["PR#1"]),
            ]
        )
        ready, _ = selector.candidates(backlog)
        assert [t.id for t in ready] == ["S1-01-alpha"]

    def test_pending_gate_is_excluded(self):
        """pending 게이트 제외."""
        backlog = _backlog(
            [_task(requires_gates=["G-key"])],
            gates=[Gate(id="G-key", title="키")],
        )
        ready, excluded = selector.candidates(backlog)
        assert ready == []
        assert excluded[0].reason == "gates"

    def test_waived_gate_passes(self):
        """waived 게이트는 통과."""
        backlog = _backlog(
            [_task(requires_gates=["G-key"])],
            gates=[Gate(id="G-key", title="키", status="waived")],
        )
        ready, _ = selector.candidates(backlog)
        assert len(ready) == 1

    def test_human_owned_task_is_excluded(self):
        """사람 소유 태스크 제외."""
        backlog = _backlog([_task(owner="kiki")])
        ready, excluded = selector.candidates(backlog)
        assert ready == []
        assert excluded[0].reason == "owner"

    def test_track_entry_gate_hard_locks(self):
        """트랙 entry gate 하드락."""
        # E축 트랙은 S5 게이트 통과 전 후보에서 알고리즘 수준으로 제외
        backlog = _backlog(
            [_task(id="E1-01-physics", stage="E1", track="expansion", subject="physics")],
            gates=[Gate(id="G-s5", title="확장 게이트")],
            tracks=[Track(id="expansion", title="E축", entry_gate="G-s5")],
        )
        ready, excluded = selector.candidates(backlog)
        assert ready == []
        assert excluded[0].reason == "track_gate"

    def test_unlocks_after_entry_gate_passes(self):
        """entry gate 통과 후 해금."""
        backlog = _backlog(
            [_task(id="E1-01-physics", stage="E1", track="expansion", subject="physics")],
            gates=[Gate(id="G-s5", title="확장 게이트", status="cleared", evidence="판정 문서")],
            tracks=[Track(id="expansion", title="E축", entry_gate="G-s5")],
        )
        ready, _ = selector.candidates(backlog)
        assert [t.id for t in ready] == ["E1-01-physics"]

    def test_other_session_claim_is_excluded(self):
        """타 세션 claim 제외."""
        backlog = _backlog([_task(session="other-branch")])
        ready, excluded = selector.candidates(backlog)
        assert ready == []
        assert excluded[0].reason == "claimed"

    def test_layer_and_subject_filters(self):
        """layer subject 필터."""
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
    def test_stage_outranks_priority(self):
        """스테이지가 우선순위보다 우선."""
        # S1 잔여(priority 5)가 S2(priority 1)보다 먼저
        backlog = _backlog(
            [
                _task(id="S2-01-later", stage="S2", priority=1),
                _task(id="S1-01-alpha", priority=5),
            ]
        )
        ready, _ = selector.candidates(backlog)
        assert [t.id for t in ready] == ["S1-01-alpha", "S2-01-later"]

    def test_priority_decides_within_same_stage(self):
        """같은 스테이지는 priority 우선."""
        backlog = _backlog(
            [
                _task(id="S1-02-beta", title="베타", priority=1),
                _task(id="S1-01-alpha", priority=3),
            ]
        )
        ready, _ = selector.candidates(backlog)
        assert [t.id for t in ready] == ["S1-02-beta", "S1-01-alpha"]

    def test_bottleneck_unlocking_most_successors_wins(self):
        """해금 후속 수가 많은 병목 우선."""
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

    def test_ordering_is_deterministic(self):
        """정렬은 결정적."""
        tasks = [_task(id=f"S1-{i:02d}-t{i}", title=str(i)) for i in range(1, 6)]
        backlog = _backlog(tasks)
        first = [t.id for t in selector.candidates(backlog)[0]]
        second = [t.id for t in selector.candidates(backlog)[0]]
        assert first == second == sorted(first)


class TestStallReason:
    def test_all_complete(self):
        """전부 완료."""
        backlog = _backlog([_task(status="done", artifacts=["PR#1"])])
        _, excluded = selector.candidates(backlog)
        code, _ = selector.stall_reason(backlog, excluded)
        assert code == "all_done"

    def test_waiting_on_human_gate(self):
        """사람 게이트 대기."""
        backlog = _backlog(
            [_task(requires_gates=["G-key"])],
            gates=[Gate(id="G-key", title="키")],
        )
        _, excluded = selector.candidates(backlog)
        code, detail = selector.stall_reason(backlog, excluded)
        assert code == "human_gate"
        assert detail == ["G-key"]

    def test_track_gate_also_counts_as_human_wait(self):
        """트랙 게이트도 사람 대기로 분류."""
        backlog = _backlog(
            [_task(id="E1-01-physics", stage="E1", track="expansion")],
            gates=[Gate(id="G-s5", title="확장 게이트")],
            tracks=[Track(id="expansion", title="E축", entry_gate="G-s5")],
        )
        _, excluded = selector.candidates(backlog)
        code, detail = selector.stall_reason(backlog, excluded)
        assert code == "human_gate"
        assert detail == ["G-s5"]

    def test_another_session_in_progress(self):
        """다른 세션 진행 중."""
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

    def test_owner_exclusion_default_is_unchanged(self):
        """candidates(자동 후보)는 owner!=claude를 계속 제외한다 — 자동 착수 방지."""
        backlog = _backlog([_task(owner="kiki")])
        ready, excluded = selector.candidates(backlog)
        assert ready == []
        assert excluded[0].reason == "owner"

    def test_allow_human_owner_bypasses_owner_only(self):
        """allow_human_owner=True면 owner 제외를 건너뛰어 착수 가능(None)."""
        backlog = _backlog([_task(owner="kiki")])
        task = backlog.tasks["S1-01-alpha"]
        assert selector.classify_todo(backlog, task) is not None  # 기본은 제외
        assert selector.classify_todo(backlog, task, allow_human_owner=True) is None

    def test_allow_human_owner_still_checks_deps(self):
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

    def test_allow_human_owner_still_checks_gates(self):
        """사람 기입 경로도 pending 게이트면 거부."""
        from models import Gate

        backlog = _backlog(
            [_task(owner="kiki", requires_gates=["G-key"])],
            gates=[Gate(id="G-key", title="키")],
        )
        task = backlog.tasks["S1-01-alpha"]
        exclusion = selector.classify_todo(backlog, task, allow_human_owner=True)
        assert exclusion is not None and exclusion.reason == "gates"
