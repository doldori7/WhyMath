"""status / brief 렌더링 — 사람이 읽는 출력과 SessionStart 훅용 압축 출력.

원칙: brief는 백로그 전체가 아니라 "지금 필요한 최소"만 컨텍스트에 주입한다
(next 상위 3건 + 초과 경과 게이트 + 무결성 경고) — Minimal Subgraph 정신의 빌드판.
"""

from __future__ import annotations

import json
from datetime import date

import selector
from models import Backlog

# 상태별 표시 기호 (터미널 폭 절약)
_STATUS_MARK = {
    "todo": "· ",
    "in_progress": "▶ ",
    "blocked": "✖ ",
    "review": "◇ ",
    "done": "✔ ",
    "cancelled": "— ",
}


def _days_pending(gate_requested: str, today: date) -> int | None:
    if not gate_requested:
        return None
    try:
        y, m, d = (int(x) for x in gate_requested.split("-"))
        return (today - date(y, m, d)).days
    except ValueError:
        return None


def overdue_gates(backlog: Backlog, today: date) -> list[tuple[str, int]]:
    """remind_after_days를 초과한 pending 게이트 (id, 경과일) 목록."""
    result: list[tuple[str, int]] = []
    for gate in backlog.gates.values():
        if gate.status != "pending" or gate.remind_after_days is None:
            continue
        days = _days_pending(gate.requested, today)
        if days is not None and days >= gate.remind_after_days:
            result.append((gate.id, days))
    result.sort(key=lambda pair: -pair[1])
    return result


def stage_progress(backlog: Backlog) -> list[tuple[str, int, int]]:
    """스테이지별 (stage, done 수, 전체 수) — stage_order 순."""
    counts: dict[str, list[int]] = {}
    for task in backlog.tasks.values():
        done, total = counts.setdefault(task.stage, [0, 0])
        counts[task.stage][1] = total + 1
        if task.status == "done":
            counts[task.stage][0] = done + 1
    ordered = sorted(counts, key=backlog.stage_index)
    return [(s, counts[s][0], counts[s][1]) for s in ordered]


def current_stage(backlog: Backlog) -> str:
    """미완료 태스크가 남은 가장 앞 스테이지 (전부 완료면 마지막 스테이지)."""
    for stage, done, total in stage_progress(backlog):
        if done < total:
            return stage
    progress = stage_progress(backlog)
    return progress[-1][0] if progress else "?"


def render_status(backlog: Backlog, errors: list[str], today: date) -> str:
    lines = ["📊 빌드 하네스 — 프로젝트 현재 상태", ""]

    lines.append("── 스테이지 진행률 ──")
    for stage, done, total in stage_progress(backlog):
        bar = "완료 ✅" if done == total else f"{done}/{total}"
        marker = "→ " if stage == current_stage(backlog) else "  "
        lines.append(f"{marker}{stage}: {bar}")

    active = [t for t in backlog.tasks.values() if t.status in ("in_progress", "review")]
    if active:
        lines.append("")
        lines.append("── 진행 중 ──")
        for task in sorted(active, key=lambda t: t.id):
            lines.append(
                f"{_STATUS_MARK[task.status]}{task.id} [{task.session or '?'}] {task.title}"
            )

    blocked = [t for t in backlog.tasks.values() if t.status == "blocked"]
    if blocked:
        lines.append("")
        lines.append("── 차단됨 ──")
        for task in sorted(blocked, key=lambda t: t.id):
            lines.append(
                f"{_STATUS_MARK['blocked']}{task.id} {task.title} — {task.notes or '사유 미기록'}"
            )

    pending = [g for g in backlog.gates.values() if g.status == "pending"]
    if pending:
        lines.append("")
        lines.append("── 대기 중 게이트 (사람 행동 필요) ──")
        for gate in sorted(pending, key=lambda g: g.id):
            days = _days_pending(gate.requested, today)
            age = f" — {days}일 경과" if days is not None else ""
            lines.append(f"⏳ {gate.id} [{gate.assignee}] {gate.title}{age}")

    ready, excluded = selector.candidates(backlog)
    lines.append("")
    lines.append("── 다음 착수 후보 (next) ──")
    if ready:
        for i, task in enumerate(ready[:3], start=1):
            lines.append(f"  {i}. {task.id} ({task.layer}) {task.title}")
    else:
        code, detail = selector.stall_reason(backlog, excluded)
        lines.append(f"(후보 없음 — 사유: {code} {detail})")

    if errors:
        lines.append("")
        lines.append(f"⚠️ 무결성 경고 {len(errors)}건 — `backlog.py validate` 로 상세 확인")

    return "\n".join(lines)


def render_status_json(backlog: Backlog, errors: list[str], today: date) -> str:
    ready, excluded = selector.candidates(backlog)
    payload = {
        "current_stage": current_stage(backlog),
        "stages": [{"stage": s, "done": d, "total": t} for s, d, t in stage_progress(backlog)],
        "in_progress": [
            {"id": t.id, "session": t.session, "title": t.title}
            for t in backlog.tasks.values()
            if t.status == "in_progress"
        ],
        "blocked": [t.id for t in backlog.tasks.values() if t.status == "blocked"],
        "pending_gates": [
            {
                "id": g.id,
                "assignee": g.assignee,
                "days": _days_pending(g.requested, today),
            }
            for g in backlog.gates.values()
            if g.status == "pending"
        ],
        "next": [t.id for t in ready[:5]],
        "validate_errors": errors,
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def render_brief(
    backlog: Backlog,
    errors: list[str],
    branch: str,
    today: date,
    remote_claimed: dict[str, str] | None = None,
    remote_status: str = "ok",
    stale_branches: list[tuple[str, float, int]] | None = None,
    stale_branch_status: str = "ok",
    done_excluded: dict[str, list[str]] | None = None,
    review_doc_findings: list[tuple[str, str, str]] | None = None,
    review_doc_status: str = "ok",
) -> str:
    """SessionStart 훅용 — 컨텍스트에 주입되는 최소 브리핑.

    remote_claimed: task_id → 원격 claim 브랜치 (refs/claims/* 조회 결과, best-effort).
    stale_branches: (branch, age_days, ahead) 목록(HARN-13) — 원시 튜플로 받아 이 모듈이
    `remote_claims`를 직접 import하지 않게 한다(remote_claimed와 동일한 결합도 원칙).
    done_excluded: task_id → 완료 브랜치 목록(HARN-12) — 타 세션이 이미 끝냈으나 아직
    머지 전인 태스크. `next`(HARN-11)와 동형으로 후보에서 제외해 브리핑이 이미 끝난
    일을 1순위로 추천하는 근접사고를 막는다. 순수 함수 — 원격 조회는 호출부(`cmd_brief`)
    책임이라 여기서는 이미 계산된 결과만 받는다(테스트 용이성·기존 시그니처 하위호환 유지).
    review_doc_findings: (branch, path, age_days) 목록(HARN-14) — 미머지 브랜치가 트렁크에
    없는 `docs/**/*_{gap_,}review.md`를 추가한 사실. stale_branches와 달리 나이로 거르지
    않는다(문서 중복은 첫날이 가장 위험 — HARN-13 나이 임계의 사각 보완).
    """
    lines = ["[빌드하네스 브리핑]"]

    progress = stage_progress(backlog)
    stage = current_stage(backlog)
    stage_line = " · ".join(
        f"{s} {d}/{t}"
        for s, d, t in progress
        if backlog.stage_index(s) <= backlog.stage_index(stage)
    )
    lines.append(f"현재 스테이지: {stage} ({stage_line})")

    mine = [t for t in backlog.tasks.values() if t.status == "in_progress" and t.session == branch]
    if mine:
        for task in mine:
            lines.append(
                f"이 브랜치의 진행 중 태스크: {task.id} — {task.title}"
                f" (완료 시 `backlog.py done {task.id} --artifact <PR/커밋>`)"
            )

    # 병렬 세션 가시성 — 다른 세션의 원격 claim을 브리핑에 노출 (중복 착수 예방)
    others = {tid: br for tid, br in (remote_claimed or {}).items() if br != branch}
    if others:
        lines.append("다른 세션 원격 claim (착수 금지):")
        for tid, br in sorted(others.items()):
            lines.append(f"  · {tid} — {br}")
    elif remote_status not in ("ok", "disabled"):
        lines.append(f"(원격 claim 조회 불가: {remote_status} — 로컬 claim 정보만 표시)")

    # 장기 미머지 브랜치 (HARN-13) — 정보성 경고일 뿐 착수를 막지 않는다.
    if stale_branches:
        lines.append("⚠️ 장기 미머지 브랜치 (Kiki 확인 필요):")
        for stale_branch, age_days, ahead in stale_branches:
            lines.append(
                f"  · {stale_branch} — 최종 커밋 {age_days:.0f}일 전 · trunk 대비 {ahead}커밋 앞섬"
            )
    elif stale_branch_status not in ("ok", "disabled"):
        lines.append(f"(장기 미머지 브랜치 조회 불가: {stale_branch_status} — 판정 보류)")

    # 미머지 브랜치의 신규 설계 문서 (HARN-14) — 나이 무관·정보성 경고, 착수를 막지 않는다.
    if review_doc_findings:
        lines.append("⚠️ 미머지 브랜치의 신규 설계 문서 (중복 착수 위험 — 먼저 확인):")
        for doc_branch, doc_path, doc_age_days in review_doc_findings:
            lines.append(f"  · {doc_branch} — {doc_path} (최종 커밋 {doc_age_days}일 전)")
    elif review_doc_status not in ("ok", "disabled"):
        lines.append(f"(신규 설계 문서 조회 불가: {review_doc_status} — 판정 보류)")

    ready, excluded = selector.candidates(backlog, remote_claimed=remote_claimed)
    if done_excluded:
        ready = [t for t in ready if t.id not in done_excluded]
    if ready:
        lines.append("다음 착수 후보:")
        for i, task in enumerate(ready[:3], start=1):
            lines.append(
                f"  {i}. {task.id} [{task.layer}/{task.subject}] {task.title}"
                f" — {selector.selection_rationale(backlog, task)}"
            )
        lines.append("착수: `python3 scripts/harness/backlog.py start <id>` 또는 /drive")
    else:
        code, detail = selector.stall_reason(backlog, excluded)
        label = {
            "all_done": "모든 태스크 완료 — 스테이지 전환 계획 필요",
            "human_gate": "사람 게이트 대기 중",
            "in_progress": "다른 세션 진행 중",
            "blocked": "차단 상태 — /status 로 원인 확인",
        }.get(code, code)
        lines.append(f"착수 가능 태스크 없음: {label} {detail}")

    for gate_id, days in overdue_gates(backlog, today):
        gate = backlog.gates[gate_id]
        lines.append(
            f"⚠️ 게이트 리마인드: {gate_id} [{gate.assignee}] {gate.title} — {days}일 경과"
        )

    if errors:
        lines.append(f"⚠️ 백로그 무결성 경고 {len(errors)}건 — `backlog.py validate` 확인 필요")

    return "\n".join(lines)
