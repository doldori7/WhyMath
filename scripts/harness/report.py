"""status / brief 렌더링 — 사람이 읽는 출력과 SessionStart 훅용 압축 출력.

원칙: brief는 백로그 전체가 아니라 "지금 필요한 최소"만 컨텍스트에 주입한다
(next 상위 3건 + 초과 경과 게이트 + 무결성 경고) — Minimal Subgraph 정신의 빌드판.
"""

from __future__ import annotations

import json
from datetime import date, timedelta

import selector
from models import Backlog, Gate

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


def gate_due(gate: Gate, today: date) -> bool:
    """게이트가 지금 사람 행동이 필요한 상태인가.

    remind_after_days가 없으면(즉시형) 항상 대상이다. 있으면 그 문턱을 넘어야
    대상이다 — '만료 없는 유예·제외 금지'(CLAUDE.md)의 반대편 실수를 막는다:
    재확인 지점을 미래로 못박은 게이트(예: G-state-machine-deferral-recheck,
    remind_after_days=101)는 그 지점 전까지는 *일정대로 대기 중*이지 지체가
    아니다. 문턱 전에 '경과일'만 보여 주면 정상 대기가 지체처럼 읽힌다.
    """
    if gate.remind_after_days is None:
        return True
    days = _days_pending(gate.requested, today)
    return days is not None and days >= gate.remind_after_days


def gate_target_date(gate: Gate) -> date | None:
    """remind_after_days 문턱에 도달하는 날짜 (requested + remind_after_days)."""
    if not gate.requested or gate.remind_after_days is None:
        return None
    try:
        y, m, d = (int(x) for x in gate.requested.split("-"))
    except ValueError:
        return None
    return date(y, m, d) + timedelta(days=gate.remind_after_days)


def gate_status_suffix(gate: Gate, today: date) -> str:
    """게이트 한 줄에 붙일 상태 표기.

    지금 행동이 필요한 게이트만 '{N}일 경과'로 표시한다(진짜 지체). 아직 문턱
    전인 예정된 재확인은 대신 목표일과 D-day를 보여 준다 — 경과일 숫자만
    보이면 재확인 지점이 미래(예: 12/13)인데도 마치 그날부터 밀린 것처럼 읽힌다.
    """
    days = _days_pending(gate.requested, today)
    if days is None:
        return ""
    if gate_due(gate, today):
        return f" — {days}일 경과"
    target = gate_target_date(gate)
    remaining = gate.remind_after_days - days if gate.remind_after_days is not None else None
    if target is not None and remaining is not None:
        return f" — 예정 재확인 {target.isoformat()} (D-{remaining})"
    return f" — {days}일 경과"


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


def cancelled_dep_blocked_line(backlog: Backlog) -> str | None:
    """취소된 선행에 차단된 todo 태스크의 한 줄 요약 — 0건이면 None (HARN-67 ②).

    status·brief·validate 세 화면이 같은 문장을 내게 한 곳에 둔다. "결정 불가 → 차단
    유지"인 상태를 침묵으로 두면 그 태스크는 영구 차단처럼 보이고, 정정 경로가 있어도
    아무도 쓰지 않는다 — 그래서 요약 줄에 정정 명령을 함께 싣는다.
    """
    blocked = selector.cancelled_dependency_blocks(backlog)
    if not blocked:
        return None
    items = " ".join(f"{task.id}(←{','.join(deps)})" for task, deps in blocked)
    return (
        f"취소된 선행에 차단된 태스크 {len(blocked)}건: {items}"
        " — 정정: backlog.py amend <id> --remove-depends <dep> --reason '...'"
    )


def gate_stale_blocked_line(backlog: Backlog) -> str | None:
    """해소된 게이트를 기다리는 blocked 태스크의 한 줄 요약 — 0건이면 None (HARN-74 ③).

    `cancelled_dep_blocked_line`과 같은 자리·같은 형식으로 status·brief가 같은 문장을 낸다.
    왜 0건에 침묵하는가 — ①의 `gates clear` 화면과 규약이 다르다: 그 화면은 *그 명령의 결과
    보고*라 줄이 없으면 "검사했는데 없었다"와 "검사하지 않았다"를 구분할 수 없어 0건도
    명시한다. 반면 brief·status는 매 세션 읽는 *요약*이라 0건에 줄을 더하면 신호 대 잡음비만
    떨어지고 경고가 습관화된다 — 그래서 None을 돌려 침묵을 허용한다.
    """
    stale = selector.stale_gate_blocked(backlog)
    if not stale:
        return None
    items = " ".join(f"{task.id}(←{','.join(gates)})" for task, gates in stale)
    return (
        f"해소된 게이트를 기다리는 blocked 태스크 {len(stale)}건: {items}"
        " — 확인: backlog.py unblock <id>"
    )


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

    # 취소된 선행에 차단된 todo — status=blocked가 아니라 화면에 안 잡히던 축 (HARN-67 ②)
    cancelled_line = cancelled_dep_blocked_line(backlog)
    if cancelled_line:
        lines.append("")
        lines.append(f"⚠ {cancelled_line}")

    # 해소된 게이트를 기다리는 blocked (HARN-74 ③) — "차단됨" 절만 보면 게이트 대기로 읽히는데
    # 실제로는 기다릴 게이트가 없는 상태. 위 "차단됨" 절과 별도 줄로 그 사실을 드러낸다.
    stale_gate_line = gate_stale_blocked_line(backlog)
    if stale_gate_line:
        lines.append("")
        lines.append(f"⚠ {stale_gate_line}")

    pending = [g for g in backlog.gates.values() if g.status == "pending"]
    if pending:
        due_now = [g for g in pending if gate_due(g, today)]
        scheduled = [g for g in pending if not gate_due(g, today)]
        if due_now:
            lines.append("")
            lines.append("── 대기 중 게이트 (사람 행동 필요) ──")
            # 오래된 순 — 가장 지체된 것이 먼저 보여야 한다.
            for gate in sorted(due_now, key=lambda g: -(_days_pending(g.requested, today) or 0)):
                suffix = gate_status_suffix(gate, today)
                lines.append(f"⏳ {gate.id} [{gate.assignee}] {gate.title}{suffix}")
        if scheduled:
            lines.append("")
            lines.append("── 예정된 재확인 (아직 기한 전 — 행동 불요) ──")
            # 가장 임박한 재확인부터 — 문턱까지 얼마나 남았는지가 관심사다.
            for gate in sorted(scheduled, key=lambda g: gate_target_date(g) or date.max):
                suffix = gate_status_suffix(gate, today)
                lines.append(f"🕓 {gate.id} [{gate.assignee}] {gate.title}{suffix}")

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
        # 취소된 선행에 차단된 todo (HARN-67 ②) — 텍스트 화면과 같은 사실을 기계도 읽게
        "cancelled_dep_blocked": [
            {"id": task.id, "cancelled": deps}
            for task, deps in selector.cancelled_dependency_blocks(backlog)
        ],
        # 해소된 게이트를 기다리는 blocked (HARN-74 ③) — 텍스트 화면과 같은 사실을 기계도 읽게
        "gate_stale_blocked": [
            {"id": task.id, "gates": gates} for task, gates in selector.stale_gate_blocked(backlog)
        ],
        "pending_gates": [
            {
                "id": g.id,
                "assignee": g.assignee,
                "days": _days_pending(g.requested, today),
                # due=False는 지체가 아니라 미래 재확인 지점을 기다리는 정상 대기다
                # (remind_after_days 미도달) — 소비자가 'days'만 보고 지체로 오독하지
                # 않도록 명시적 판정을 함께 싣는다.
                "due": gate_due(g, today),
                "remind_after_days": g.remind_after_days,
                "target_date": (gate_target_date(g).isoformat() if gate_target_date(g) else None),
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
    pr_state_lookup_ok: bool = True,
    pr_state_lookup_error: str = "",
    done_excluded: dict[str, list[str]] | None = None,
    doc_series_candidates: list[tuple[str, tuple[str, ...], str]] | None = None,
    doc_series_status: str = "ok",
    ruleset_reminder: str | None = None,
) -> str:
    """SessionStart 훅용 — 컨텍스트에 주입되는 최소 브리핑.

    remote_claimed: task_id → 원격 claim 브랜치 (refs/claims/* 조회 결과, best-effort).
    stale_branches: (branch, age_days, ahead, status, evidence[, partial_port[, port_scan_error]])
        목록
        (HARN-13 + 2026-08-05
    3분류 확장 · HARN-78 5분류) — 원시 튜플로 받아 이 모듈이 `remote_claims`를 직접
    import하지 않게 한다(remote_claimed와 동일한 결합도 원칙). status는
    "isolated"|"pr_filed"|"pr_closed"|"unresolved"|"ported"|"active" —
    구분 없이 하나로 뭉쳐 보여주면 매 세션 전부를 훑어야 해서 신호 대 잡음비가 나빠진다
    (2026-08-05 실측: 19건 중 실제 결정 대기는 6건뿐이었다). 하위호환을 위해 4-튜플
    (status·evidence 생략)도 받아들인다 — 그 경우 전부 "unresolved"로 취급.
    stale_branch_message: 판정 불가 사유의 사람이 읽는 설명(선택). status가 "ok"가 아닐
    때 "판정 보류" 줄에 덧붙는다 — shallow 클론처럼 *복구 명령이 있는* 실패에서 화면만
    보고 고칠 수 있게 한다(2026-08-11: 브리핑이 shallow 위에서 10건을 오분류하고도
    "ok"로 보고했다). 비면 종전 문구 그대로 — 하위호환.
    pr_state_lookup_ok/pr_state_lookup_error (HARN-78): pr_filed 후보의 열림/닫힘을
    GitHub API로 조회했는지·성공했는지. False면 pr_filed 절의 문구가 "처분은 해당
    PR에서"(이미 확인됨을 전제)가 아니라 "열림/닫힘을 확인하라"(모른다는 사실을
    명시)로 바뀐다 — 기본값 True는 하위호환(이 두 인자를 안 주는 기존 호출부는
    종전 문구 그대로).
    done_excluded: task_id → 완료 브랜치 목록(HARN-12) — 타 세션이 이미 끝냈으나 아직
    머지 전인 태스크. `next`(HARN-11)와 동형으로 후보에서 제외해 브리핑이 이미 끝난
    일을 1순위로 추천하는 근접사고를 막는다. 순수 함수 — 원격 조회는 호출부(`cmd_brief`)
    책임이라 여기서는 이미 계산된 결과만 받는다(테스트 용이성·기존 시그니처 하위호환 유지).
    doc_series_candidates: (branch, files, last_commit_at_iso) 목록(HARN-14) — 나이 임계
    없이 트렁크에 없는 `docs/**/*_review.md`를 추가한 미머지 브랜치 전부. stale_branches와
    같은 결합도 원칙(원시 튜플만 받음). **훅이 stderr를 버리므로**(`.claude/settings.json`
    `2>/dev/null`) 스캔 실패는 이 함수가 반환하는 문자열(stdout) 안에만 표시해야 실제로
    보인다 — stale_branch_status와 동형 처리.
    ruleset_reminder: 브랜치 보호 라이브 확인 리마인드 한 줄(HARN-63) 또는 None. 이미 만들어진
    문자열만 받는다 — 계산은 호출부(`cmd_brief`) 책임이라 이 모듈이 `ruleset_drift`를 직접
    import하지 않는다(stale_branches·doc_series와 동일한 결합도 원칙). **이 배선이 ④의 집행
    지점이다** — 탐지기를 만들어 두고 아무도 돌리지 않는 상태를 브리핑이 매 세션 지적한다.
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
        pr_closed = [e for e in normalized if e[3] == "pr_closed"]
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
        # PR 닫힘(미머지, HARN-78) — PR이 있었다는 사실이 처분 완료를 뜻하지 않는다.
        # isolated와 같은 행동 요구(재작업 또는 폐기 판단)이므로 같은 위계로 강조한다.
        if pr_closed:
            lines.append(f"🔴 PR 닫힘(미머지) — 재작업 또는 폐기 판단 필요 — {len(pr_closed)}건:")
            for stale_branch, age_days, ahead, _status, evidence, _partial, _err in pr_closed:
                lines.append(
                    f"  · {stale_branch} — {evidence} · 최종 커밋 {age_days:.0f}일 전 · "
                    f"trunk 대비 {ahead}커밋 앞섬"
                )
        # PR 대기 — 작업은 GitHub에 보인다. 열림이 GitHub API로 확인됐으면(pr_state_
        # lookup_ok) Kiki에게 "결정하라"고 다시 묻지 않고 PR 번호를 건넨다. 확인이
        # 안 됐으면(토큰 없음 등) "열림"이라고 단정하지 않고 직접 확인하라고 말한다
        # (모른다 ≠ 아니다 — 열려 있다고 가정하는 것도 마찬가지로 오판정이다).
        if pr_filed:
            if pr_state_lookup_ok:
                lines.append(
                    f"(참고) PR 제출됨(열림 확인) — 처분은 해당 PR에서 — {len(pr_filed)}건:"
                )
            else:
                reason = f" — {pr_state_lookup_error}" if pr_state_lookup_error else ""
                lines.append(
                    f"(참고) PR 제출됨 — 상태 미확인{reason}, PR 번호로 열림/닫힘을 "
                    f"확인하라 — {len(pr_filed)}건:"
                )
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

    # 취소된 선행에 차단된 todo (HARN-67 ②) — 훅은 stderr를 버리므로(`2>/dev/null`) 이 줄이
    # stdout(반환 문자열)에 있어야 세션이 실제로 본다. 0건이면 아무것도 내지 않는다.
    cancelled_line = cancelled_dep_blocked_line(backlog)
    if cancelled_line:
        lines.append(f"⚠️ {cancelled_line}")

    # 해소된 게이트를 기다리는 blocked (HARN-74 ③ 집행 지점) — clear 시점의 알림(①)을 사람이
    # 놓쳐도 다음 세션이 본다. 위와 같은 이유로 stdout(반환 문자열)에 싣는다. 0건이면 침묵.
    stale_gate_line = gate_stale_blocked_line(backlog)
    if stale_gate_line:
        lines.append(f"⚠️ {stale_gate_line}")

    for gate_id, days in overdue_gates(backlog, today):
        gate = backlog.gates[gate_id]
        lines.append(
            f"⚠️ 게이트 리마인드: {gate_id} [{gate.assignee}] {gate.title} — {days}일 경과"
        )

    if errors:
        lines.append(f"⚠️ 백로그 무결성 경고 {len(errors)}건 — `backlog.py validate` 확인 필요")

    # 브랜치 보호 라이브 확인 리마인드 (HARN-63 ④) — 저장소 *밖* 설정이라 어떤 테스트도 보지
    # 못한다. 자동 상시 실행이 불가능하므로(CI에 관리자 토큰 없음) 세션마다 사람에게 묻는다.
    if ruleset_reminder:
        lines.append(ruleset_reminder)

    return "\n".join(lines)
