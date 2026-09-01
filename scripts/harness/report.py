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
    stale_branches: list[tuple[str, ...]] | None = None,
    stale_branch_status: str = "ok",
    stale_branch_message: str = "",
    done_excluded: dict[str, list[str]] | None = None,
    doc_series_candidates: list[tuple[str, tuple[str, ...], str]] | None = None,
    doc_series_status: str = "ok",
) -> str:
    """SessionStart 훅용 — 컨텍스트에 주입되는 최소 브리핑.

    remote_claimed: task_id → 원격 claim 브랜치 (refs/claims/* 조회 결과, best-effort).
    stale_branches: (branch, age_days, ahead, status, evidence[, partial_port[, port_scan_error]])
        목록
        (HARN-13 + 2026-08-05
    3분류 확장) — 원시 튜플로 받아 이 모듈이 `remote_claims`를 직접 import하지 않게 한다
    (remote_claimed와 동일한 결합도 원칙). status는 "unresolved"|"ported"|"active" —
    구분 없이 하나로 뭉쳐 보여주면 매 세션 전부를 훑어야 해서 신호 대 잡음비가 나빠진다
    (2026-08-05 실측: 19건 중 실제 결정 대기는 6건뿐이었다). 하위호환을 위해 4-튜플
    (status·evidence 생략)도 받아들인다 — 그 경우 전부 "unresolved"로 취급.
    stale_branch_message: 판정 불가 사유의 사람이 읽는 설명(선택). status가 "ok"가 아닐
    때 "판정 보류" 줄에 덧붙는다 — shallow 클론처럼 *복구 명령이 있는* 실패에서 화면만
    보고 고칠 수 있게 한다(2026-08-11: 브리핑이 shallow 위에서 10건을 오분류하고도
    "ok"로 보고했다). 비면 종전 문구 그대로 — 하위호환.
    done_excluded: task_id → 완료 브랜치 목록(HARN-12) — 타 세션이 이미 끝냈으나 아직
    머지 전인 태스크. `next`(HARN-11)와 동형으로 후보에서 제외해 브리핑이 이미 끝난
    일을 1순위로 추천하는 근접사고를 막는다. 순수 함수 — 원격 조회는 호출부(`cmd_brief`)
    책임이라 여기서는 이미 계산된 결과만 받는다(테스트 용이성·기존 시그니처 하위호환 유지).
    doc_series_candidates: (branch, files, last_commit_at_iso) 목록(HARN-14) — 나이 임계
    없이 트렁크에 없는 `docs/**/*_review.md`를 추가한 미머지 브랜치 전부. stale_branches와
    같은 결합도 원칙(원시 튜플만 받음). **훅이 stderr를 버리므로**(`.claude/settings.json`
    `2>/dev/null`) 스캔 실패는 이 함수가 반환하는 문자열(stdout) 안에만 표시해야 실제로
    보인다 — stale_branch_status와 동형 처리.
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
                f" (완료 시 PR을 연 뒤 `backlog.py done {task.id} --artifact <PR 번호 포함>`)"
            )

    # 병렬 세션 가시성 — 다른 세션의 원격 claim을 브리핑에 노출 (중복 착수 예방)
    others = {tid: br for tid, br in (remote_claimed or {}).items() if br != branch}
    if others:
        lines.append("다른 세션 원격 claim (착수 금지):")
        for tid, br in sorted(others.items()):
            lines.append(f"  · {tid} — {br}")
    elif remote_status not in ("ok", "disabled"):
        lines.append(f"(원격 claim 조회 불가: {remote_status} — 로컬 claim 정보만 표시)")

    # 장기 미머지 브랜치 (HARN-13 + 2026-08-05 3분류 + HARN-47 고립/PR대기 분리) —
    # 정보성일 뿐 착수를 막지 않는다. **행동이 필요한 축(isolated)만 강조**하고 나머지는
    # 참고로 낮춰, 매 세션 Kiki가 훑어야 하는 줄 수를 실제 조치 대상으로 좁힌다.
    if stale_branches:
        normalized = []
        for entry in stale_branches:
            branch_name, age_days_val, ahead_val = entry[0], entry[1], entry[2]
            status_val, evidence_val = entry[3:5] if len(entry) >= 5 else ("unresolved", "")
            # 6번째 원소(부분 착지 단서)는 선택 — 구 호출부 5튜플 호환(HARN-37).
            partial_val = entry[5] if len(entry) >= 6 else ""
            scan_err_val = entry[6] if len(entry) >= 7 else ""
            normalized.append(
                (
                    branch_name,
                    age_days_val,
                    ahead_val,
                    status_val,
                    evidence_val,
                    partial_val,
                    scan_err_val,
                )
            )
        isolated = [e for e in normalized if e[3] == "isolated"]
        pr_filed = [e for e in normalized if e[3] == "pr_filed"]
        unresolved = [e for e in normalized if e[3] == "unresolved"]
        ported = [e for e in normalized if e[3] == "ported"]
        active = [e for e in normalized if e[3] == "active"]

        # 고립(HARN-47) — PR로 노출된 적이 없어 *이 줄이 유일한 존재 증거*다. 가장 위에
        # 두고 행동을 명시한다. 이 축과 pr_filed를 한 덩어리로 부르던 것이 경고 습관화의
        # 원인이었다(2026-08-31 실측: 18건 중 11건은 이미 PR·처분 라벨 보유).
        if isolated:
            lines.append(
                f"🔴 고립 브랜치 — PR로 노출된 적 없음 (회수 또는 삭제 필요) — {len(isolated)}건:"
            )
            for stale_branch, age_days, ahead, _status, _evidence, partial, scan_err in isolated:
                lines.append(
                    f"  · {stale_branch} — 최종 커밋 {age_days:.0f}일 전 · "
                    f"trunk 대비 {ahead}커밋 앞섬"
                )
                if scan_err:
                    # 판정 불가를 조용히 넘기면 "검사했는데 근거 없음"으로 읽힌다.
                    lines.append(f"      ↳ 포팅 판정 불가: {scan_err} — 삭제 전 수동 확인 필요")
                if partial:
                    # 흡수 흔적은 있으나 전건은 아니다 — 사람이 같은 조사를 다시 하지
                    # 않게 단서를 잇고, 동시에 '결정 불요'로 숨기지도 않는다(HARN-37).
                    lines.append(f"      ↳ 부분 착지: {partial} — 잔여분 확인 필요")
        # PR 대기 — 작업은 GitHub에 보인다. Kiki에게 "결정하라"고 다시 묻지 않고 PR
        # 번호를 건넨다. 열림/닫힘은 오프라인 git으로 판정 불가라 번호로 넘긴다.
        if pr_filed:
            lines.append(f"(참고) PR 제출됨 — 처분은 해당 PR에서 — {len(pr_filed)}건:")
            for stale_branch, age_days, _ahead, _status, evidence, _partial, _err in pr_filed:
                lines.append(f"  · {stale_branch} — {evidence} · 최종 커밋 {age_days:.0f}일 전")
        # unresolved는 이제 "PR 조회를 못 해 분리하지 못한" 잔여 축이다(측정 실패).
        if unresolved:
            lines.append(
                f"⚠️ 미머지 브랜치 (PR 조회 실패로 고립 여부 미판정) — {len(unresolved)}건:"
            )
            for stale_branch, age_days, ahead, _status, _evidence, _partial, _err in unresolved:
                lines.append(
                    f"  · {stale_branch} — 최종 커밋 {age_days:.0f}일 전 · "
                    f"trunk 대비 {ahead}커밋 앞섬"
                )
        if ported:
            lines.append(f"(참고) 이미 포팅됨 — 원본 정리만 필요, 결정 불요 — {len(ported)}건:")
            for stale_branch, _age_days, _ahead, _status, evidence, _partial, _err in ported:
                lines.append(f"  · {stale_branch} — 근거: {evidence}")
        if active:
            lines.append(f"(참고) 타 세션 진행중 — 정보성, 결정 불요 — {len(active)}건:")
            for stale_branch, age_days, ahead, _status, _evidence, _partial, _err in active:
                lines.append(
                    f"  · {stale_branch} — 최종 커밋 {age_days:.0f}일 전 · "
                    f"trunk 대비 {ahead}커밋 앞섬"
                )
    elif stale_branch_status not in ("ok", "disabled"):
        # 판정 보류는 무기한 침묵이 아니라 *매 세션 화면에 뜨는 명시적 미측정 신고*다.
        # 복구 명령을 함께 실어 보류가 "고칠 수 있는 상태"임을 화면에서 알 수 있게 한다
        # (shallow 클론이 대표 사례 — remote_claims.SHALLOW_PENDING_MESSAGE).
        detail = f" — {stale_branch_message}" if stale_branch_message else ""
        lines.append(f"(장기 미머지 브랜치 조회 불가: {stale_branch_status}{detail} — 판정 보류)")

    # 설계 문서 중복 착수 (HARN-14) — 나이 임계 없음. 정보성 경고일 뿐 착수를 막지 않는다.
    if doc_series_candidates:
        lines.append("📄 미머지 브랜치의 신규 설계 문서 (중복 착수 확인):")
        for doc_branch, files, last_commit_iso in doc_series_candidates:
            file_list = ", ".join(files)
            lines.append(f"  · {doc_branch} ({last_commit_iso[:10]}) — {file_list}")
    elif doc_series_status not in ("ok", "disabled"):
        lines.append(f"(설계 문서 중복 스캔 실패: {doc_series_status} — 판정 보류)")

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
