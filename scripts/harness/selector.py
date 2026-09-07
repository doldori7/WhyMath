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
    reason: str  # deps|deps_cancelled|gates|owner|track_gate|claimed|claimed_remote|path_overlap
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


def cancelled_dependencies(backlog: Backlog, task: Task) -> list[str]:
    """depends_on 중 **취소된** 선행 — 영구 차단의 후보 (HARN-67 ②).

    왜 따로 세는가: `unmet_dependencies`는 done만 해소로 치므로 cancelled 선행은 그 안에
    묻혀 일반 "의존 미충족"으로 보인다. 그런데 cancelled는 done과 달리 **앞으로도 해소되지
    않는다** — 선행이 "불필요해서 취소"됐는지 "잘못 등재돼 취소"됐는지 기계는 모르므로
    (모른다 ≠ 아니다) 해소로 간주하지 않고 차단을 유지하되, 따로 세어 화면에 드러낸다.
    정정 경로는 `amend <id> --remove-depends <dep>`이다 — 차단은 영구가 아니라 *결정 대기*다.
    (사고 경위 2026-09-05: EOS-94를 cancel하자 EOS-96이 후보에서 조용히 사라졌다)
    """
    return [
        dep
        for dep in task.depends_on
        if dep in backlog.tasks and backlog.tasks[dep].status == "cancelled"
    ]


def cancelled_dependency_blocks(backlog: Backlog) -> list[tuple[Task, list[str]]]:
    """취소된 선행에 차단된 **todo** 태스크 전건 — status·brief·validate 요약용 (HARN-67 ②).

    classify_todo의 `excluded`가 아니라 직접 훑는 이유: classify는 owner·트랙 게이트 제외가
    먼저라 사람 소유·게이트 대기 태스크의 취소 선행이 그 뒤에 숨는다. 요약은 "결정이 필요한
    태스크"를 빠짐없이 보여 주는 것이 목적이므로 순서에 가려지면 안 된다. id 정렬(결정적).
    """
    result = [
        (task, cancelled_dependencies(backlog, task))
        for task in sorted(backlog.tasks.values(), key=lambda t: t.id)
        if task.status == "todo"
    ]
    return [(task, deps) for task, deps in result if deps]


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
) -> Exclusion | None:
    """todo 태스크의 제외 사유 (None = 착수 가능 후보).

    remote_claimed: task_id → 원격 claim 브랜치 (refs/claims/* — 병렬 세션 가시성).
    overlap_block: task_id → 겹침 근거 (policy.path_overlap=block일 때만 채워짐).
    allow_human_owner: True면 owner!=claude 제외를 건너뛴다 — **소유자 본인이 `--as
        <owner>`로 기입하는 start 경로 전용**(HARN-06). candidates()는 기본값(False)만
        쓰므로 next/status/brief의 자동 착수 후보에서 사람 태스크는 계속 제외된다.
        deps·게이트·claim 등 나머지 검사는 사람 기입에도 동일 적용(우회 아님).
    """
    if not allow_human_owner and task.owner != "claude":
        return Exclusion(task.id, "owner", [task.owner])
    if not track_gate_passed(backlog, task):
        track = backlog.tracks[task.track]
        return Exclusion(task.id, "track_gate", [track.entry_gate or "?"])
    # 취소된 선행은 일반 deps보다 **먼저** 판정한다 — 같은 "미충족"이라도 done을 기다리면
    # 풀리는 것과 영원히 안 풀리는 것을 한 사유로 뭉치면 후자가 조용한 영구 차단이 된다
    # (HARN-67 ②: 침묵 실패 금지). unmet_dependencies의 의미(done만 해소)는 그대로다.
    cancelled = cancelled_dependencies(backlog, task)
    if cancelled:
        return Exclusion(task.id, "deps_cancelled", cancelled)
    deps = unmet_dependencies(backlog, task)
    if deps:
        return Exclusion(task.id, "deps", deps)
    gates = unmet_gates(backlog, task)
    if gates:
        return Exclusion(task.id, "gates", gates)
    if task.session:
        return Exclusion(task.id, "claimed", [task.session])
    if remote_claimed and task.id in remote_claimed:
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
    # 취소된 선행에 막힌 태스크 → 상세 목록에 사유를 병기하기 위해 따로 모은다 (HARN-67 ②).
    # blocked 계열(other_reasons)로 취급하되, 목록에서 일반 차단과 구별되지 않으면 "왜
    # 안 풀리는가"를 사람이 다시 조사해야 한다 — 취소는 done과 달리 기다려도 안 풀린다.
    cancelled_detail: dict[str, list[str]] = {}
    other_reasons = False
    for exc in excluded:
        if exc.reason in ("gates", "track_gate"):
            gate_ids.extend(exc.detail)
        elif exc.reason == "owner":
            continue  # 사람 소유 태스크도 사람 대기의 일종
        elif exc.reason == "claimed_remote":
            # 다른 세션이 원격 claim 중 — in_progress 대기의 일종
            remote_held.append(f"{exc.task_id} (원격: {exc.detail[0] if exc.detail else '?'})")
        elif exc.reason == "deps_cancelled":
            cancelled_detail[exc.task_id] = list(exc.detail)
            other_reasons = True
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

    def _label(task: Task) -> str:
        # 취소된 선행 표기 — 정정 경로(amend --remove-depends)가 있음을 목록에서 바로 알린다
        deps = cancelled_detail.get(task.id)
        return f"{task.id} (취소된 선행: {', '.join(deps)})" if deps else task.id

    return "blocked", sorted(_label(t) for t in open_todo)
