"""순차 조율 알고리즘 — "다음 할 일"을 결정적으로 계산한다.

후보 조건 (전부 만족해야 착수 가능):
    status == todo
    ∧ depends_on 전부 done
    ∧ requires_gates 전부 cleared/waived
    ∧ owner == claude          (사람 소유 태스크는 자동 착수 금지)
    ∧ 소속 트랙 entry_gate 통과 (예: E축은 S5 게이트 전 하드락)
    ∧ session == null          (다른 세션이 claim하지 않음)

정렬 (결정적 — 같은 입력이면 항상 같은 순서):
    (stage_order 인덱스, priority, -해금 후속 수, id)
"""

from __future__ import annotations

from dataclasses import dataclass, field

from models import Backlog, Task


@dataclass
class Exclusion:
    """todo 태스크가 후보에서 제외된 사유 (정지 사유 판별·설명에 사용)."""

    task_id: str
    reason: str  # deps|gates|owner|track_gate|claimed|claimed_remote|path_overlap
    detail: list[str] = field(default_factory=list)


def track_gate_passed(backlog: Backlog, task: Task) -> bool:
    track = backlog.tracks.get(task.track)
    if track is None or not track.entry_gate:
        return True
    gate = backlog.gates.get(track.entry_gate)
    return gate is not None and gate.passed


def unmet_dependencies(backlog: Backlog, task: Task) -> list[str]:
    return [
        dep
        for dep in task.depends_on
        if dep not in backlog.tasks or backlog.tasks[dep].status != "done"
    ]


def unmet_gates(backlog: Backlog, task: Task) -> list[str]:
    return [
        gid
        for gid in task.requires_gates
        if gid not in backlog.gates or not backlog.gates[gid].passed
    ]


def classify_todo(
    backlog: Backlog,
    task: Task,
    *,
    remote_claimed: dict[str, str] | None = None,
    overlap_block: dict[str, list[str]] | None = None,
    allow_human_owner: bool = False,
    resuming_session: str | None = None,
) -> Exclusion | None:
    """todo 태스크의 제외 사유 (None = 착수 가능 후보).

    remote_claimed: task_id → 원격 claim 브랜치 (refs/claims/* — 병렬 세션 가시성).
    overlap_block: task_id → 겹침 근거 (policy.path_overlap=block일 때만 채워짐).
    allow_human_owner: True면 owner!=claude 제외를 건너뛴다 — **소유자 본인이 `--as
        <owner>`로 기입하는 start 경로 전용**(HARN-06). candidates()는 기본값(False)만
        쓰므로 next/status/brief의 자동 착수 후보에서 사람 태스크는 계속 제외된다.
        deps·게이트·claim 등 나머지 검사는 사람 기입에도 동일 적용(우회 아님).
    resuming_session: 착수를 시도하는 *본인* 세션(브랜치). claim 보유자가 그 세션 자신이면
        claimed/claimed_remote 제외를 건너뛴다 — **자기 자리로의 복귀**이지 중복 착수가
        아니기 때문이다. `remote_claims.claim()`이 같은 브랜치에 멱등인 것과 같은 계약을
        읽기측에도 맞춘 것(HARN-45). 기본값 None이면 종전대로 전부 제외되므로
        candidates()/next/status의 후보 계산은 불변이다.
    """
    if not allow_human_owner and task.owner != "claude":
        return Exclusion(task.id, "owner", [task.owner])
    if not track_gate_passed(backlog, task):
        track = backlog.tracks[task.track]
        return Exclusion(task.id, "track_gate", [track.entry_gate or "?"])
    deps = unmet_dependencies(backlog, task)
    if deps:
        return Exclusion(task.id, "deps", deps)
    gates = unmet_gates(backlog, task)
    if gates:
        return Exclusion(task.id, "gates", gates)
    if task.session and task.session != resuming_session:
        return Exclusion(task.id, "claimed", [task.session])
    if remote_claimed and task.id in remote_claimed and remote_claimed[task.id] != resuming_session:
        return Exclusion(task.id, "claimed_remote", [remote_claimed[task.id]])
    if overlap_block and task.id in overlap_block:
        return Exclusion(task.id, "path_overlap", overlap_block[task.id])
    return None


def unblock_count(backlog: Backlog, task: Task) -> int:
    """이 태스크 완료가 직접 해금하는 후속 태스크 수 (병목 우선 지표)."""
    return sum(1 for other in backlog.tasks.values() if task.id in other.depends_on)


def sort_key(backlog: Backlog, task: Task) -> tuple[int, int, int, str]:
    return (
        backlog.stage_index(task.stage),
        task.priority,
        -unblock_count(backlog, task),
        task.id,
    )


def candidates(
    backlog: Backlog,
    layer: str | None = None,
    subject: str | None = None,
    track: str | None = None,
    *,
    remote_claimed: dict[str, str] | None = None,
    overlap_block: dict[str, list[str]] | None = None,
) -> tuple[list[Task], list[Exclusion]]:
    """(정렬된 착수 가능 후보, 제외 사유 목록) 반환."""
    ready: list[Task] = []
    excluded: list[Exclusion] = []
    for task in backlog.tasks.values():
        if task.status != "todo":
            continue
        if layer and task.layer != layer:
            continue
        if subject and task.subject != subject:
            continue
        if track and task.track != track:
            continue
        exclusion = classify_todo(
            backlog, task, remote_claimed=remote_claimed, overlap_block=overlap_block
        )
        if exclusion is None:
            ready.append(task)
        else:
            excluded.append(exclusion)
    ready.sort(key=lambda t: sort_key(backlog, t))
    return ready, excluded


def selection_rationale(backlog: Backlog, task: Task) -> str:
    """왜 이 태스크가 지금 최우선인지 한 줄 설명."""
    parts = [f"stage={task.stage}", f"priority={task.priority}"]
    unlocks = unblock_count(backlog, task)
    if unlocks:
        parts.append(f"완료 시 후속 {unlocks}건 해금")
    if task.depends_on:
        parts.append(f"의존성 {len(task.depends_on)}건 전부 해소됨")
    if task.requires_gates:
        parts.append(f"게이트 {len(task.requires_gates)}건 전부 통과")
    return " · ".join(parts)


def stall_reason(backlog: Backlog, excluded: list[Exclusion]) -> tuple[str, list[str]]:
    """후보 0일 때의 정지 사유 판별 — /drive 정지 신호.

    반환: (사유 코드, 상세 목록)
        all_done    : 진행할 태스크 자체가 없음 → 스테이지/트랙 전환 제안
        human_gate  : 사람 게이트만 해소되면 진행 가능 → 게이트 목록 제시
        in_progress : 다른 세션이 진행 중 → 대기 또는 다른 layer 선택
        blocked     : 나머지 (blocked 태스크·미해소 의존성 연쇄)
    """
    active = [t for t in backlog.tasks.values() if t.status in ("in_progress", "review")]
    open_todo = [t for t in backlog.tasks.values() if t.status in ("todo", "blocked")]
    if not open_todo and not active:
        return "all_done", []

    # 사람 게이트만 걷어내면 풀리는가 — 게이트 제외 + owner 제외만 남은 경우
    gate_ids: list[str] = []
    remote_held: list[str] = []
    other_reasons = False
    for exc in excluded:
        if exc.reason in ("gates", "track_gate"):
            gate_ids.extend(exc.detail)
        elif exc.reason == "owner":
            continue  # 사람 소유 태스크도 사람 대기의 일종
        elif exc.reason == "claimed_remote":
            # 다른 세션이 원격 claim 중 — in_progress 대기의 일종
            remote_held.append(f"{exc.task_id} (원격: {exc.detail[0] if exc.detail else '?'})")
        else:
            other_reasons = True
    pending_gates = sorted(
        {g for g in gate_ids if g in backlog.gates and not backlog.gates[g].passed}
    )
    if pending_gates and not other_reasons:
        return "human_gate", pending_gates

    if active or remote_held:
        local = [f"{t.id} ({t.session or '?'})" for t in active]
        return "in_progress", sorted(local + remote_held)
    if pending_gates:
        return "human_gate", pending_gates
    return "blocked", sorted(t.id for t in open_todo)
