#!/usr/bin/env python3
"""빌드 하네스 CLI — 작업일정 단일 진실 원천(backlog/)의 유일한 조작 창구.

사용:
    python3 scripts/harness/backlog.py status [--json]
    python3 scripts/harness/backlog.py next [--n 3] [--layer L] [--subject S] [--track T]
    python3 scripts/harness/backlog.py start <id> [--session <branch>]
                                                 [--no-remote | --ignore-remote-claim]
    python3 scripts/harness/backlog.py done <id> --artifact <PR/커밋> [--artifact ...]
    python3 scripts/harness/backlog.py block <id> --reason <사유>
    python3 scripts/harness/backlog.py unblock <id>
    python3 scripts/harness/backlog.py review <id>                (in_progress → review)
    python3 scripts/harness/backlog.py cancel <id> --reason <사유>  (todo/blocked → cancelled)
    python3 scripts/harness/backlog.py gates [list]
    python3 scripts/harness/backlog.py gates add <G-id> --title <제목>
                                                 [--kind human|external|decision]
                                                 [--assignee <담당자>] [--remind-after-days N]
    python3 scripts/harness/backlog.py gates clear <G-id> --evidence <근거>
    python3 scripts/harness/backlog.py gates waive <G-id> [--reason <사유>]
    python3 scripts/harness/backlog.py add --id ... --title ... --track ... --stage ... (상세는 -h)
    python3 scripts/harness/backlog.py validate [--quiet]
    python3 scripts/harness/backlog.py brief [--format hook]
    python3 scripts/harness/backlog.py check-stop        (Stop 훅 전용 — stdin JSON)
    python3 scripts/harness/backlog.py seed [--force]    (최초 1회 초기 시딩)

종료 코드: 0 정상 / 1 거부(규칙 위반) / 2 Stop 훅 차단 신호 / 3 환경 오류
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections.abc import Mapping
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pathscope
import remote_claims
import report
import selector
import store
from models import GATE_KINDS, OWNERS, STATUS_TRANSITIONS, Gate, Task
from seed_data import build_seed


def _today() -> str:
    return date.today().strftime("%Y-%m-%d")


def _load(root: Path):
    backlog, schema_errors = store.load_backlog(root)
    return backlog, schema_errors


def _fail(message: str, code: int = 1) -> int:
    print(f"❌ {message}", file=sys.stderr)
    return code


def _transition(task: Task, new_status: str) -> str | None:
    """상태 전이 검사 — 허용되지 않으면 오류 메시지 반환."""
    allowed = STATUS_TRANSITIONS.get(task.status, ())
    if new_status not in allowed:
        return (
            f"{task.id}: {task.status} → {new_status} 전이 불가 "
            f"(허용: {list(allowed) or '없음(종결 상태)'})"
        )
    return None


def _append_note(original: str, reason: str, tag: str) -> str:
    """사유를 원 notes 뒤에 append — 원문을 지우지 않는다 (HARN-20).

    구 구현(`task.notes = args.reason`)은 태스크의 발견 경위·설계 근거를 호출마다
    통째로 덮어써 데이터 손실을 냈다(2026-08-10 통합점검 실측 — blocked 4건 전건
    원 notes 소실). append 방식은 원문 뒤에 `[tag YYYY-MM-DD] 사유`를 이어붙여
    이력을 누적한다 — unblock 이후에도 "왜 한번 막혔었는지"가 notes에 남는다.
    """
    stamp = f"[{tag} {_today()}] {reason}"
    if not original.strip():
        return stamp
    return f"{original}\n\n{stamp}"


# ── 서브커맨드 ───────────────────────────────────────────────────────────────


def cmd_status(root: Path, args: argparse.Namespace) -> int:
    backlog, schema_errors = _load(root)
    errors = store.validate_backlog(backlog, schema_errors)
    if args.json:
        print(report.render_status_json(backlog, errors, date.today()))
    else:
        print(report.render_status(backlog, errors, date.today()))
    return 0


def _remote_claim_map(root: Path, policy, skip: bool = False) -> tuple[dict[str, str], str]:
    """원격 claim 조회 best-effort — (task_id→branch, 상태). 실패는 빈 dict (fail-open).

    성공 시 스냅샷을 .git/ 캐시에 남긴다 — check-edit 훅이 편집마다
    네트워크를 타지 않고 이 캐시로 교차 세션 겹침을 판정한다.
    """
    if skip or not policy.remote_claims:
        return {}, "disabled"
    claims, status = remote_claims.list_claims(root, with_meta=True)
    if status != "ok":
        return {}, status
    remote_claims.save_cache(root, claims)
    return {c.task_id: (c.branch or "?") for c in claims}, "ok"


def _overlap_block_map(root: Path, backlog, policy) -> dict[str, list[str]] | None:
    """block 모드일 때만 — todo 태스크별 in-flight 겹침 근거 (selector 제외용)."""
    if policy.path_overlap != "block":
        return None
    inflight = [
        t for t in backlog.tasks.values() if t.status in ("in_progress", "review") and t.paths
    ]
    if not inflight:
        return None
    files = pathscope.repo_files(root)
    result: dict[str, list[str]] = {}
    for task in backlog.tasks.values():
        if task.status != "todo" or not task.paths:
            continue
        for other in inflight:
            hit = pathscope.overlap(task.id, task.paths, other.id, other.paths, files)
            if hit:
                result[task.id] = [other.id, hit.describe()]
                break
    return result or None


def cmd_next(root: Path, args: argparse.Namespace) -> int:
    backlog, _ = _load(root)
    policy, _ = store.load_policy(root)
    remote_claimed, remote_status = _remote_claim_map(
        root, policy, skip=getattr(args, "no_remote", False)
    )
    ready, excluded = selector.candidates(
        backlog,
        layer=args.layer,
        subject=args.subject,
        track=args.track,
        remote_claimed=remote_claimed,
        overlap_block=_overlap_block_map(root, backlog, policy),
    )
    if remote_status not in ("ok", "disabled"):
        print(
            f"⚠ 원격 claim 조회 불가({remote_status}) — 로컬 claim 정보만 반영",
            file=sys.stderr,
        )

    # 미머지 done 제외 (HARN-11) — 타 세션이 끝냈으나 머지 전인 태스크는 후보가 아니다.
    # fetch 없이 캐시된 remote-tracking ref만 본다(네트워크 0·실측 12ms): `next`는 자주
    # 도는 조회이고, 확정 지점인 `start`가 fetch=True로 다시 본다(2선).
    if policy.remote_claims and not getattr(args, "no_remote", False) and ready:
        done_map, done_status = remote_claims.scan_remote_done(root, [t.id for t in ready])
        if done_map:
            for task_id, finishers in sorted(done_map.items()):
                print(
                    f"⚠ 후보 제외 {task_id} — 이미 완료(미머지): "
                    f"{', '.join(f.branch for f in finishers)}",
                    file=sys.stderr,
                )
            ready = [t for t in ready if t.id not in done_map]
        elif done_status != "ok":
            print(
                f"⚠ 미머지 done 탐지 불가({done_status}) — 완료분이 섞였을 수 있음",
                file=sys.stderr,
            )
    if args.json:
        print(
            json.dumps(
                [
                    {
                        "id": t.id,
                        "layer": t.layer,
                        "subject": t.subject,
                        "title": t.title,
                        "rationale": selector.selection_rationale(backlog, t),
                    }
                    for t in ready[: args.n]
                ],
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    if not ready:
        code, detail = selector.stall_reason(backlog, excluded)
        print(f"착수 가능 태스크 없음 — 사유: {code}")
        for item in detail:
            print(f"  · {item}")
        return 0
    print(f"착수 가능 후보 (상위 {min(args.n, len(ready))}건):")
    for i, task in enumerate(ready[: args.n], start=1):
        print(f"{i}. {task.id} [{task.layer}/{task.subject}] {task.title}")
        print(f"   사유: {selector.selection_rationale(backlog, task)}")
    return 0


def cmd_start(root: Path, args: argparse.Namespace) -> int:
    backlog, _ = _load(root)
    task = backlog.tasks.get(args.id)
    if task is None:
        return _fail(f"태스크 '{args.id}' 없음")
    error = _transition(task, "in_progress")
    if error:
        return _fail(error)
    # 사람-소유 태스크 기입 경로(HARN-06): 소유자 본인이 `--as <owner>`를 명시하면
    # owner 제외만 건너뛴다(deps·게이트·claim 검사는 동일). next 후보 계산은 불변.
    as_owner = getattr(args, "as_owner", None)
    if as_owner is not None and as_owner != task.owner:
        return _fail(f"{task.id}: --as {as_owner} 불일치 — 이 태스크의 owner는 '{task.owner}'")
    human = as_owner is not None and as_owner == task.owner
    exclusion = selector.classify_todo(backlog, task, allow_human_owner=human)
    if exclusion is not None:
        message = f"{task.id} 착수 거부 — {exclusion.reason}: {exclusion.detail}"
        if exclusion.reason == "owner":
            # 거부→소유자 이관 규칙(CLAUDE.md 프로세스·안내)의 CLI 구현 — 우회 대신 안내.
            message += (
                f"\n  사람 소유 태스크 — 소유자 본인이 직접 기입하세요: "
                f"python3 scripts/harness/backlog.py start {task.id} --as {task.owner}"
            )
        return _fail(message)
    session = args.session or store.current_branch(root)
    policy, _ = store.load_policy(root)

    # 원격 claim 스냅샷 — 다른 세션의 in-flight는 로컬 backlog 사본에 안 보이므로
    # (claim은 각 브랜치의 worktree에만 기록) 원격 ref로만 교차 세션 겹침을 알 수 있다
    remote_claimed, _ = _remote_claim_map(root, policy, skip=getattr(args, "no_remote", False))

    # [프리플라이트 0] 미머지 done — 타 세션이 이미 끝냈으나 머지 전인 태스크 (HARN-11).
    # claim 대장은 done 시 release돼 비어 있고 트렁크 사본은 아직 todo라, 다른 어떤
    # 검사도 이걸 못 본다. 되돌리기 비싼 지점이므로 fetch=True로 최신 상태를 본다.
    if policy.remote_claims and not getattr(args, "no_remote", False):
        done_map, done_status = remote_claims.scan_remote_done(root, [task.id], fetch=True)
        finishers = done_map.get(task.id, [])
        if finishers:
            branches = ", ".join(f.branch for f in finishers)
            message = (
                f"{task.id} 착수 거부 — 이미 **완료된** 태스크다(미머지): {branches}\n"
                f"  그 브랜치의 백로그 사본이 status: done — 착수하면 중복 구현이 된다.\n"
                f"  확인: git show origin/<branch>:backlog/tasks/{task.id}.yaml\n"
                f"  그래도 착수해야 하면(예: 그 브랜치가 폐기됨): --ignore-remote-claim"
            )
            if getattr(args, "ignore_remote_claim", False):
                print(
                    f"⚠ 미머지 done 무시하고 진행({branches}) — 중복 구현 위험을 감수합니다",
                    file=sys.stderr,
                )
                store.append_event(root, "start_ignored_unmerged_done", task.id, branches=branches)
            else:
                return _fail(message)
        elif done_status != "ok":
            # 판정 불가를 '완료분 없음'으로 위장하지 않는다 (측정 실패 ≠ 통과)
            print(
                f"⚠ 미머지 done 탐지 불가({done_status}) — 타 세션 완료분을 못 봤을 수 있음",
                file=sys.stderr,
            )

    # [프리플라이트 1] 파일 범위 겹침 — 타 in-flight(로컬 ∪ 원격 claim) paths와 교차
    overlap_error = _check_path_overlap(
        root, backlog, task, policy, remote_claimed=remote_claimed, session=session
    )
    if overlap_error:
        return _fail(overlap_error)

    # [프리플라이트 2] 원격 claim — 로컬 검사 전부 통과 후 마지막 (dangling ref 방지).
    # conflict만 차단, offline/error는 읽기측 교차 세션 탐지(프리플라이트 3)로 폴백.
    remote_status = "disabled"
    if policy.remote_claims and not getattr(args, "no_remote", False):
        result = remote_claims.claim(root, task.id, session)
        remote_status = result.status
        if result.status == "conflict":
            other = result.claim
            detail = f" (세션: {other.branch or '?'}, {other.ts or '시각 불명'})" if other else ""
            message = (
                f"{task.id} 착수 거부 — 다른 세션이 이미 원격 claim{detail}\n"
                f"  본인 claim이 확실하면: claims release {task.id} --force 후 재시도"
            )
            if getattr(args, "ignore_remote_claim", False):
                # 플래그의 사정거리를 명시 — 무엇을 껐는지 착각하게 두지 않는다.
                message += (
                    "\n  ※ --ignore-remote-claim은 *읽기측* 판정만 무시합니다 — "
                    "CAS claim conflict는 확정 신호라 우회 대상이 아닙니다"
                )
            return _fail(message)
        if result.status in ("offline", "error"):
            print(
                f"⚠ 원격 CAS claim 불가({result.status}): {result.message}",
                file=sys.stderr,
            )
            store.append_event(root, "claim_remote_unavailable", task.id, status=result.status)
            # [프리플라이트 3] 읽기측 교차 세션 탐지 (HARN-07) — CAS(쓰기)가 막힌
            # 환경의 2선 방어. HARN-09가 claim을 `harness-claims` 브랜치로 옮겨 CAS를
            # 복구하기 전까지, 이 환경의 프록시는 refs/claims/* push를 403 거부해
            # CAS가 **한 번도 성공하지 못했고** fail-open이 중복 방지를 영구 무력화했다
            # (OPS-07·OPS-12 병렬 구현 사고 2회). 이제 CAS가 1선이지만, 진짜 오프라인·
            # 권한 문제로 실패하는 환경이 남아 있으므로 이 경로는 유지한다.
            # CAS 성공 시에는 돌지 않는다 — 전체 브랜치 fetch(~5초)를 불필요하게 물지 않는다.
            scan = remote_claims.scan_remote_in_progress(root, task.id, session)
            remote_status = f"{result.status}+readscan_{scan.status}"
            # 규칙 A·B로 걸러낸 stale 홀더를 조용히 버리지 않는다 (HARN-08 관측성)
            skipped_summary = _readside_skipped_summary(scan)
            if skipped_summary:
                print(skipped_summary, file=sys.stderr)
                store.append_event(
                    root,
                    "claim_readside_stale_skipped",
                    task.id,
                    trunk=f"{scan.trunk_branch}:{scan.trunk_status or '없음'}"
                    f"({scan.trunk_source})",
                    skipped=[f"{s.branch}:{s.reason}" for s in scan.skipped],
                )
            conflict = _readside_conflict_message(task, scan, result.status)
            if conflict and getattr(args, "ignore_remote_claim", False):
                # [규칙 C] 태스크 단위 세분 우회 — 무엇을 포기하는지 명시하고 이벤트로 남긴다.
                print(_readside_ignore_warning(task, scan), file=sys.stderr)
                store.append_event(
                    root,
                    "claim_readside_ignored",
                    task.id,
                    cas_status=result.status,
                    holders=[f"{h.branch}:{h.session}" for h in scan.holders],
                )
                remote_status += "+ignored"
                conflict = None
            if conflict:
                store.append_event(
                    root,
                    "claim_readside_conflict",
                    task.id,
                    cas_status=result.status,
                    holders=[f"{h.branch}:{h.session}" for h in scan.holders],
                )
                return _fail(conflict)
            # 홀더가 남아 있는데 여기 도달했다면 규칙 C로 무시하고 온 경로다 —
            # 그 경우 '중복 없음'이라고 말하면 거짓말이므로 아래 안내를 내지 않는다.
            if scan.status == "ok" and not scan.holders:
                extra = " (브랜치 수 상한 도달 — 일부만 확인)" if scan.truncated else ""
                unused = (
                    " · --ignore-remote-claim은 무시할 판정이 없어 효과 없음"
                    if getattr(args, "ignore_remote_claim", False)
                    else ""
                )
                print(
                    f"  ↳ 읽기측 교차 세션 탐지로 폴백: 원격 브랜치 {scan.scanned_refs}개에서 "
                    f"중복 in_progress 없음{extra}.{unused}\n"
                    f"    ※ *부분* 방어입니다 — 상대가 브랜치를 push한 뒤에만 보이며 "
                    f"CAS의 원자성은 대체하지 못합니다.",
                    file=sys.stderr,
                )
            elif scan.status != "ok":
                # 침묵 실패 금지 — 폴백까지 실패했으면 '보호 없음'을 명시적으로 말한다.
                print(
                    f"  ↳ 읽기측 교차 세션 탐지도 불가({scan.status}) — "
                    f"로컬 claim만으로 진행합니다.\n"
                    f"    ⚠ 이 착수에는 중복 착수 보호가 전혀 없습니다 "
                    f"(다른 세션이 같은 태스크를 잡고 있어도 알 수 없음): {scan.message}",
                    file=sys.stderr,
                )
                store.append_event(
                    root,
                    "claim_readside_unavailable",
                    task.id,
                    cas_status=result.status,
                    scan_status=scan.status,
                )

    task.status = "in_progress"
    task.session = session
    task.updated = _today()
    store.save_task(root, task)
    # 사람 기입(--as)은 이벤트에 as_owner를 남겨 claude 기입과 대장에서 구분한다(HARN-06).
    start_extra: dict[str, object] = {"session": task.session, "remote": remote_status}
    if human:
        start_extra["as_owner"] = as_owner
    store.append_event(root, "start", task.id, **start_extra)
    print(f"▶ {task.id} 착수 (세션: {task.session}, 원격 claim: {remote_status})")
    print(f"  완료 조건: {task.acceptance or '(acceptance 미정의 — 정의 권장)'}")
    if not task.paths:
        print(
            "  ⚠ paths 미선언 — 겹침 검사에서 제외됩니다. "
            "태스크 YAML에 paths(작업 파일 glob) 선언을 권장",
            file=sys.stderr,
        )
    for warning in task.layer_drift_warnings():
        print(f"  ⚠ {warning}", file=sys.stderr)
    return 0


_SKIP_REASON_HINT = {
    "trunk_not_session": "트렁크는 세션이 아님 — 대장 위생 실패(done 미기입 머지)",
}


def _readside_skipped_summary(scan) -> str | None:
    """규칙 A·B로 홀더에서 제외한 내역 요약 (없으면 None).

    stale을 조용히 버리면 '보호가 안 걸린 것'과 '보호를 껐던 것'이 구분되지 않는다.
    """
    if not scan.skipped:
        return None
    parts = []
    for s in scan.skipped[:5]:
        hint = _SKIP_REASON_HINT.get(
            s.reason, f"{scan.trunk_branch}가 {scan.trunk_status} — 작업이 이미 착륙"
        )
        parts.append(f"origin/{s.branch}(session={s.session}, {s.reason}: {hint})")
    more = f" 외 {len(scan.skipped) - 5}건" if len(scan.skipped) > 5 else ""
    return (
        f"  ↳ stale 홀더 {len(scan.skipped)}건 제외: "
        + " · ".join(parts)
        + more
        + f"\n    (기준 트렁크: {scan.trunk_ref or '?'} "
        f"= {scan.trunk_source}, 태스크 status={scan.trunk_status or '없음'})"
    )


def _readside_ignore_warning(task: Task, scan) -> str:
    """규칙 C(--ignore-remote-claim) 사용 시 경고 — 무엇을 포기하는지 명시."""
    lines = [
        f"⚠ --ignore-remote-claim: {task.id}의 읽기측 교차 세션 판정을 " f"무시하고 착수합니다."
    ]
    for holder in scan.holders[:3]:
        lines.append(
            f"  · 무시된 홀더: origin/{holder.branch} "
            f"(status=in_progress, session={holder.session})"
        )
    if len(scan.holders) > 3:
        lines.append(f"  · … 외 {len(scan.holders) - 3}건")
    lines.append(
        "  포기하는 것: 이 태스크의 중복 착수 보호. 상대 세션이 실제로 살아 있어도 "
        "이 착수는 막히지 않습니다 — 지금부터 중복 구현일 수 있습니다."
    )
    lines.append(
        "  (CAS claim conflict는 이 플래그로 무시되지 않습니다. 보호를 통째로 끄는 "
        "것은 여전히 --no-remote입니다.)"
    )
    if scan.holders:
        lines.append(
            "  상대 브랜치가 정말 죽었는지 확인: "
            f"git log -1 --format='%cr %h %s' origin/{scan.holders[0].branch}"
        )
    return "\n".join(lines)


def _readside_conflict_message(task: Task, scan, cas_status: str) -> str | None:
    """읽기측 탐지 결과 → 착수 거부 메시지 (충돌 없으면 None).

    status가 ok가 아니면 *판정 불가*이므로 거부하지 않는다(호출측이 '보호 없음'을
    별도로 경고한다) — 측정 실패를 '충돌 없음'으로 위장하지 않기 위한 분기다.
    """
    if scan.status != "ok" or not scan.holders:
        return None
    lines = [
        f"{task.id} 착수 거부 — 다른 세션이 이미 in_progress "
        f"(원격 브랜치 읽기 탐지 · CAS claim은 {cas_status})"
    ]
    for holder in scan.holders[:3]:
        lines.append(
            f"  · origin/{holder.branch} 의 backlog 사본: "
            f"status=in_progress, session={holder.session}"
        )
    if len(scan.holders) > 3:
        lines.append(f"  · … 외 {len(scan.holders) - 3}건")
    lines.append(
        "  ※ 이 탐지는 CAS claim(harness-claims 브랜치)이 불가할 때 도는 *부분* 방어입니다 — "
        "상대가 브랜치를 push한 뒤에만 보이며, 원자성은 대체하지 못합니다."
    )
    lines.append(
        f"  트렁크({scan.trunk_branch or '?'})의 이 태스크 status="
        f"{scan.trunk_status or '없음'} — done/cancelled였다면 자동으로 stale 처리됩니다"
        f" (규칙 A)."
    )
    lines.append(
        f"  상대 브랜치가 이미 죽었으면(stale in_progress) 확인 후 이 태스크만 무시: "
        f"git log -1 --format='%cr %h %s' origin/{scan.holders[0].branch} → "
        f"python3 scripts/harness/backlog.py start {task.id} --ignore-remote-claim\n"
        f"  (원격 검사 전체를 끄는 것은 여전히 --no-remote — 보호 범위가 다릅니다)"
    )
    return "\n".join(lines)


def _inflight_tasks(
    backlog, remote_claimed: dict[str, str] | None, session: str | None
) -> list[Task]:
    """in-flight 태스크 = 로컬(in_progress·review) ∪ 원격 claim (내 세션 제외).

    태스크 정의(YAML·paths)는 git으로 전 세션에 공유되지만, 상태(in_progress)는
    claim한 브랜치의 사본에만 있다 — 원격 claim ref가 교차 세션의 유일한 신호다.
    """
    result: dict[str, Task] = {
        t.id: t for t in backlog.tasks.values() if t.status in ("in_progress", "review")
    }
    for tid, branch in (remote_claimed or {}).items():
        if session and branch == session:
            continue  # 내 claim은 겹침 대상 아님
        t = backlog.tasks.get(tid)
        if t is not None and t.id not in result:
            # 로컬 사본에선 todo로 보여도 원격 claim이 있으면 in-flight로 취급
            t_session = t.session or branch
            result[t.id] = t
            if not t.session:
                t.session = t_session  # 경고 메시지용 (저장하지 않음 — 메모리만)
    return list(result.values())


def _check_path_overlap(
    root: Path,
    backlog,
    task: Task,
    policy,
    remote_claimed: dict[str, str] | None = None,
    session: str | None = None,
) -> str | None:
    """start 프리플라이트 — 타 in-flight 태스크와 paths 교차 검사.

    warn: stderr 경고 + policy_warn 이벤트 후 진행(None 반환).
    block: 오류 메시지 반환(호출측이 exit 1).
    """
    if policy.path_overlap == "off" or not task.paths:
        return None
    inflight = [
        t for t in _inflight_tasks(backlog, remote_claimed, session) if t.id != task.id and t.paths
    ]
    if not inflight:
        return None
    files = pathscope.repo_files(root)
    for other in inflight:
        hit = pathscope.overlap(task.id, task.paths, other.id, other.paths, files)
        if hit is None:
            continue
        desc = (
            f"{task.id} ↔ {other.id}(세션: {other.session or '?'}) "
            f"파일 범위 겹침 — {hit.describe()}"
        )
        store.append_event(
            root,
            "policy_warn",
            task.id,
            rule="path_overlap",
            other=other.id,
            detail=hit.describe(),
            mode=policy.path_overlap,
        )
        if policy.path_overlap == "block":
            return f"착수 거부 — {desc}\n  겹침 해소(paths 조정·상대 태스크 완료 대기) 후 재시도"
        print(f"⚠ {desc}", file=sys.stderr)
    return None


def cmd_done(root: Path, args: argparse.Namespace) -> int:
    backlog, _ = _load(root)
    task = backlog.tasks.get(args.id)
    if task is None:
        return _fail(f"태스크 '{args.id}' 없음")
    if not args.artifact:
        return _fail(f"{task.id}: --artifact <PR/커밋> 필수 (증적 없는 done 금지)")
    # 사람-소유 태스크의 done도 소유자 본인의 `--as <owner>` 명시 필수(HARN-06) —
    # start와 동일한 소유자 확인. claude 태스크에는 --as가 불필요하다(있으면 불일치 검사).
    as_owner = getattr(args, "as_owner", None)
    if as_owner is not None and as_owner != task.owner:
        return _fail(f"{task.id}: --as {as_owner} 불일치 — 이 태스크의 owner는 '{task.owner}'")
    if task.owner != "claude" and as_owner != task.owner:
        return _fail(
            f"{task.id}: 사람 소유 태스크({task.owner}) — 소유자 본인이 직접 기입하세요: "
            f"python3 scripts/harness/backlog.py done {task.id} --as {task.owner} --artifact <증적>"
        )
    error = _transition(task, "done")
    if error:
        return _fail(error)
    prev_session = task.session
    task.status = "done"
    task.artifacts = list(dict.fromkeys(task.artifacts + args.artifact))
    task.session = None
    task.updated = _today()
    store.save_task(root, task)
    done_extra: dict[str, object] = {"artifacts": args.artifact}
    if as_owner is not None:
        done_extra["as_owner"] = as_owner
    store.append_event(root, "done", task.id, **done_extra)
    _release_remote_claim(root, task.id, prev_session)
    print(f"✔ {task.id} 완료 — 증적: {', '.join(args.artifact)}")
    # 이 완료로 해금된 후속 태스크 안내 (순차 조율의 연결 고리)
    unlocked = [
        t
        for t in backlog.tasks.values()
        if task.id in t.depends_on
        and t.status == "todo"
        and not selector.unmet_dependencies(backlog, t)
    ]
    if unlocked:
        print("해금된 후속 태스크:")
        for t in sorted(unlocked, key=lambda x: x.id):
            gates = selector.unmet_gates(backlog, t)
            suffix = f" (게이트 대기: {gates})" if gates else " — 착수 가능"
            print(f"  · {t.id} {t.title}{suffix}")
    return 0


def cmd_block(root: Path, args: argparse.Namespace) -> int:
    backlog, _ = _load(root)
    task = backlog.tasks.get(args.id)
    if task is None:
        return _fail(f"태스크 '{args.id}' 없음")
    error = _transition(task, "blocked")
    if error:
        return _fail(error)
    prev_session = task.session
    task.status = "blocked"
    task.session = None
    task.notes = _append_note(task.notes, args.reason, "차단")  # 덮어쓰지 않고 append (HARN-20)
    task.updated = _today()
    store.save_task(root, task)
    store.append_event(root, "block", task.id, reason=args.reason)
    _release_remote_claim(root, task.id, prev_session)
    print(f"✖ {task.id} 차단 — {args.reason}")
    return 0


def cmd_review(root: Path, args: argparse.Namespace) -> int:
    """in_progress → review 전이 (HARN-20) — 구현 완료·검토 대기 상태로 전환.

    review는 여전히 in-flight(원격 claim 유지·session 필드 보존) — done/block과 달리
    세션이 계속 이 태스크를 들고 있다는 뜻이라 `_release_remote_claim`을 부르지 않는다.
    전이표(STATUS_TRANSITIONS)가 `in_progress → review`만 허용하므로 다른 상태에서의
    호출은 `_transition`이 자연히 거부한다.
    """
    backlog, _ = _load(root)
    task = backlog.tasks.get(args.id)
    if task is None:
        return _fail(f"태스크 '{args.id}' 없음")
    error = _transition(task, "review")
    if error:
        return _fail(error)
    task.status = "review"
    task.updated = _today()
    store.save_task(root, task)
    store.append_event(root, "review", task.id)
    print(f"👀 {task.id} 검토 대기 (세션: {task.session or '?'})")
    return 0


def cmd_cancel(root: Path, args: argparse.Namespace) -> int:
    """todo/blocked → cancelled 전이 (HARN-20) — 종결 상태.

    전이표는 `in_progress`에서 `cancelled`로의 직접 경로를 열지 않는다 — 진행 중인
    태스크를 취소하려면 먼저 `block` 또는 `todo`로 내린 뒤 취소해야 한다는 기존 설계를
    그대로 존중한다(우회 아님). cancelled는 종결 상태이므로 block과 동일하게 원격
    claim을 해제한다.
    """
    backlog, _ = _load(root)
    task = backlog.tasks.get(args.id)
    if task is None:
        return _fail(f"태스크 '{args.id}' 없음")
    error = _transition(task, "cancelled")
    if error:
        return _fail(error)
    prev_session = task.session
    task.status = "cancelled"
    task.session = None
    task.notes = _append_note(task.notes, args.reason, "취소")  # block과 동일 — 덮어쓰지 않음
    task.updated = _today()
    store.save_task(root, task)
    store.append_event(root, "cancel", task.id, reason=args.reason)
    _release_remote_claim(root, task.id, prev_session)
    print(f"🗑 {task.id} 취소 — {args.reason}")
    return 0


def _release_remote_claim(root: Path, task_id: str, prev_session: str | None) -> None:
    """done/block 후 원격 claim 해제 — best-effort (실패해도 진행, reap이 나중에 청소)."""
    policy, _ = store.load_policy(root)
    if not policy.remote_claims:
        return
    result = remote_claims.release(root, task_id, prev_session or store.current_branch(root))
    if result.status not in ("ok", "offline"):
        print(
            f"⚠ 원격 claim 해제 실패({result.status}): {result.message} — "
            f"`claims reap`이 이후 청소합니다",
            file=sys.stderr,
        )
        store.append_event(root, "claim_release_failed", task_id, status=result.status)


def cmd_unblock(root: Path, args: argparse.Namespace) -> int:
    backlog, _ = _load(root)
    task = backlog.tasks.get(args.id)
    if task is None:
        return _fail(f"태스크 '{args.id}' 없음")
    error = _transition(task, "todo")
    if error:
        return _fail(error)
    task.status = "todo"
    task.updated = _today()
    store.save_task(root, task)
    store.append_event(root, "unblock", task.id)
    print(f"· {task.id} 차단 해제 → todo")
    return 0


def cmd_gates(root: Path, args: argparse.Namespace) -> int:
    backlog, _ = _load(root)
    if args.gate_action == "list" or args.gate_action is None:
        pending = [g for g in backlog.gates.values() if g.status == "pending"]
        others = [g for g in backlog.gates.values() if g.status != "pending"]
        print("⏳ 대기 중 게이트:")
        for gate in sorted(pending, key=lambda g: g.id):
            days = report._days_pending(gate.requested, date.today())
            age = f" — {days}일 경과" if days is not None else ""
            print(f"  {gate.id} [{gate.assignee}/{gate.kind}] {gate.title}{age}")
        if others:
            print("✔ 통과/면제:")
            for gate in sorted(others, key=lambda g: g.id):
                print(f"  {gate.id} ({gate.status}) {gate.title}")
        return 0

    if args.gate_action == "add":
        return _cmd_gates_add(root, args, backlog)

    gate = backlog.gates.get(args.gate_id)
    if gate is None:
        return _fail(f"게이트 '{args.gate_id}' 없음")
    if args.gate_action == "clear":
        if not args.evidence:
            return _fail(f"{gate.id}: clear에는 --evidence <근거> 필수")
        gate.status = "cleared"
        gate.evidence = args.evidence
    elif args.gate_action == "waive":
        gate.status = "waived"
        gate.notes = args.reason or gate.notes
    store.save_gates(root, sorted(backlog.gates.values(), key=lambda g: g.id))
    store.append_event(
        root,
        f"gate_{args.gate_action}",
        gate.id,
        evidence=gate.evidence,
        reason=args.reason,
    )
    print(f"✔ {gate.id} → {gate.status}")
    return 0


def _cmd_gates_add(root: Path, args: argparse.Namespace, backlog) -> int:
    """게이트 대장(gates.yaml)에 새 게이트를 CLI로 등재한다 (HARN-18).

    "대장은 CLI로만 조작한다"(손편집 금지) 규약의 구멍을 메운다 — 기존에는 gates에
    add 경로가 없어 새 게이트 등재가 손편집뿐이었다(HARN-06과 동형 설계 공백).

    task `add`(cmd_add)와 동일한 검사 골격을 답습한다:
      ① id 필수·형식 ② title 필수 ③ id 중복 거부 ④ 스키마 무결성(Gate.validate)
      ⑤ events.ndjson 감사 로그 append(누가·언제·무엇을 만들었나).
    거부는 전부 명확한 종료코드(1)+메시지 — 침묵 실패 금지.
    """
    gate_id = args.gate_id
    # ② 필수 필드 검증 — 누락 시 명확한 거부 (argparse required로 걸면 list/clear/waive가
    #    같이 --title을 요구하게 되므로, add 액션 안에서 수동 검증한다)
    if not gate_id:
        return _fail("gates add <G-id> — 게이트 ID 필수")
    if not args.title:
        return _fail(f"{gate_id}: gates add 에는 --title <제목> 필수 (필수 필드 누락)")
    # ③ id 중복 거부 — 게이트는 원격 claim 대상이 아니다(원격 claim 대장은 task_id 전용이라
    #    G-* 게이트 id는 애초에 그 대장에 실리지 않는다). 따라서 gates.yaml 내 중복만 본다.
    if gate_id in backlog.gates:
        return _fail(f"게이트 ID 중복: {gate_id} (이미 gates.yaml에 존재)")

    gate = Gate(
        id=gate_id,
        title=args.title,
        kind=args.kind,
        assignee=args.assignee,
        status="pending",
        requested=_today(),
        remind_after_days=args.remind_after_days,
    )
    backlog.gates[gate.id] = gate
    # ④ 스키마/무결성 검증 — 새 게이트가 유발한 오류만 걸러 거부(기존 대장의 무관한
    #    경고에 볼모 잡히지 않게 — cmd_add의 own_errors 패턴 답습). id 형식 위반(예:
    #    소문자 kebab·G- 접두 아님)은 여기서 잡힌다.
    errors = store.validate_backlog(backlog)
    own_errors = [e for e in errors if gate_id in e]
    if own_errors:
        for e in own_errors:
            print(f"  · {e}", file=sys.stderr)
        return _fail(f"{gate_id}: 스키마/무결성 위반으로 게이트 추가 거부")

    store.save_gates(root, sorted(backlog.gates.values(), key=lambda g: g.id))
    # ⑤ 감사 로그 — gate clear/waive·task add의 이벤트 append 패턴 답습
    store.append_event(
        root,
        "gate_add",
        gate.id,
        kind=gate.kind,
        assignee=gate.assignee,
        title=gate.title,
    )
    print(
        f"＋ 게이트 {gate.id} 추가 " f"(kind={gate.kind}, assignee={gate.assignee}, status=pending)"
    )
    return 0


def _taken_id_numbers(root: Path, backlog: object, policy: object) -> dict[str, tuple[str, str]]:
    """이미 쓰인 `<PREFIX>-<번호>` → (점유 태스크의 full ID, 출처 라벨).

    **로컬 백로그 + 원격 claim 대장 + 원격 브랜치 backlog/tasks/ 파일명** 세 곳을 본다.
    원격을 보는 것이 핵심이다 — ARCH-13·OPS-15 두 사고 모두 병렬 세션이 *서로의
    브랜치를 못 봐서* 같은 번호를 각각 등재한 것이라, 로컬만 검사하면 재발을 하나도
    막지 못한다(HARN-10).

    세 번째 출처(원격 브랜치 파일명 스캔)는 HARN-15 — 원격 claim 대장은 **in_progress로
    claim된** 태스크만 기록하므로, "다른 브랜치에 이미 backlog/tasks/<ID>.yaml로
    등재만 되고 아직 착수(claim)되지 않은" 번호는 claim 대장에 원천적으로 안 잡힌다
    (OPS-17·OPS-18이 main과 미머지 브랜치에 각각 다른 슬러그로 이중 등재된 사고,
    HARN-10의 3번째 재발). `remote_claims.scan_remote_task_files`가 이미 있는
    remote-tracking ref만 읽어(fetch 없음) 이 맹점을 메운다.

    full ID를 함께 돌려주는 이유: 충돌은 **슬러그가 다를 때만** 성립한다. 같은 태스크를
    다른 클론에서 재등재하는 것(시딩·복제 세션)은 정상이므로 막으면 안 된다.

    원격 조회 실패는 등재를 막지 않는다(fail-open) — 다만 호출부가 그 사실을
    **경고로 표시**한다. 조용한 축소는 "검사했는데 안 걸림"으로 위장되기 때문이다.
    claim 대장 조회는 기존 관례대로 상태를 조용히 버린다(genuine 예외만 이 함수를
    벗어나 cmd_add의 fail-open 경로로 흘러간다). 파일명 스캔은 "offline"(원격 자체가
    없음 — 로컬 테스트·오프라인 클론의 일상적 상태)은 같은 관례로 조용히 넘기되,
    "error:<타입명>"(scan_remote_task_files 내부에서 이미 예외 타입명을 포장해 돌려줌)
    은 **여기서 바로 경고**한다 — list_claims는 이미 성공했는데 파일명 스캔만 실패한
    경우까지 통째로 예외로 승격하면 이미 확보한 claim 정보까지 버리게 되기 때문이다.
    """
    taken: dict[str, tuple[str, str]] = {}
    for task_id in getattr(backlog, "tasks", {}):
        number = store.id_number_of(str(task_id))
        if number:
            taken.setdefault(number, (str(task_id), "로컬 백로그"))
    if getattr(policy, "remote_claims", False):
        claims, _status = remote_claims.list_claims(root)
        for claim in claims:
            number = store.id_number_of(claim.task_id)
            if number:
                taken.setdefault(number, (claim.task_id, "원격 claim"))
        task_files, files_status = remote_claims.scan_remote_task_files(root)
        if files_status.startswith("error"):
            # 침묵 금지(CLAUDE.md) — status 자체에 이미 예외 타입명이 담겨 있다
            # (scan_remote_task_files 내부의 f"error:{type(exc).__name__}" 포장).
            print(
                f"  ⚠ 원격 브랜치 backlog/tasks/ 파일명 스캔 실패({files_status}) — "
                "등재만 되고 아직 claim되지 않은 원격 번호는 놓칠 수 있다",
                file=sys.stderr,
            )
        for task_file in task_files:
            number = store.id_number_of(task_file.task_id)
            if number:
                taken.setdefault(
                    number,
                    (task_file.task_id, f"원격 브랜치 backlog/tasks/({task_file.branch})"),
                )
    return taken


def _next_free_number(prefix: str, taken: Mapping[str, tuple[str, str]]) -> str | None:
    """`<PREFIX>-<n>` 다음 빈 번호(2자리 zero-padded) — **최대 사용 번호 +1**부터 찾는다.

    가장 작은 빈 번호를 주면 과거에 비워진 낮은 번호(예 HARN-01)를 제안하게 되는데,
    그건 "이 트랙의 다음 작업"이라는 사람의 기대와 어긋나 제안이 오히려 혼선을 준다.

    `{index:02d}`는 **최소** 2자리이지 **정확히** 2자리가 아니다 — index가 100을 넘으면
    "100"(3자리)을 내는데, `models.TASK_ID_RE`는 `\\d{2}` 정확히 2자리만 허용한다. 즉
    프리픽스가 00~99번을 다 쓰면 다음 제안이 형식 위반 ID가 된다(HARN-21 결함②). 그래서
    index가 99를 넘어서면 날조된 3자리를 내지 않고 **`None`을 반환** — 호출부(`cmd_add`)가
    사람에게 "이 프리픽스가 소진됐다"는 명시적 오류를 낸다.
    """
    used = [
        int(number.rsplit("-", 1)[1])
        for number in taken
        if number.rsplit("-", 1)[0] == prefix and number.rsplit("-", 1)[1].isdigit()
    ]
    index = max(used) + 1 if used else 1
    while index <= 99 and (f"{prefix}-{index}" in taken or f"{prefix}-{index:02d}" in taken):
        index += 1
    if index > 99:
        return None
    return f"{prefix}-{index:02d}"


def cmd_add(root: Path, args: argparse.Namespace) -> int:
    backlog, _ = _load(root)
    if args.id in backlog.tasks:
        return _fail(f"태스크 ID 중복: {args.id}")

    # ID 번호 충돌 차단 (HARN-10 — ARCH-13·OPS-15 2회 실측 후 등재)
    number = store.id_number_of(args.id)
    if number:
        policy, _ = store.load_policy(root)
        try:
            taken = _taken_id_numbers(root, backlog, policy)
            remote_ok = True
        except Exception as exc:  # 원격 조회 실패는 등재를 막지 않는다 — 단 침묵 금지
            taken = _taken_id_numbers(root, backlog, None)
            remote_ok = False
            print(
                f"  ⚠ 원격 claim 대장 조회 실패({type(exc).__name__}) — 번호 충돌 검사가 "
                "로컬 백로그로 축소됨(병렬 세션의 인플라이트 번호는 못 본다)",
                file=sys.stderr,
            )
        owner, source = taken.get(number, ("", ""))
        # 같은 full ID의 재등재(다른 클론에서의 시딩 등)는 충돌이 아니다 — 슬러그가
        # 다를 때만 번호 참조가 모호해진다.
        if owner and owner != args.id:
            prefix = number.rsplit("-", 1)[0]
            suggestion = _next_free_number(prefix, taken)
            if suggestion is None:
                # 프리픽스가 00~99번을 이미 다 썼다 — 3자리 제안은 TASK_ID_RE 위반이라
                # 날조하지 않는다(HARN-21 결함②). 사람의 결정(새 프리픽스 분리 등)이 필요.
                return _fail(
                    f"태스크 ID 번호 충돌: '{number}' 는 이미 {owner}({source}) 가 쓰고 있다. "
                    f"게다가 프리픽스 '{prefix}'는 00~99번을 모두 소진해 TASK_ID_RE(정확히 "
                    "2자리 숫자)를 지키는 다음 번호를 더 이상 제안할 수 없다 — 새 프리픽스로 "
                    "분리하는 등 사람의 결정이 필요하다(HARN-21). "
                    "(같은 번호를 나눠 쓰면 문서·커밋의 번호 참조가 결정 불가가 된다 — HARN-10)"
                )
            return _fail(
                f"태스크 ID 번호 충돌: '{number}' 는 이미 {owner}({source}) 가 쓰고 있다. "
                f"다음 빈 번호 제안: {suggestion}. "
                "(같은 번호를 나눠 쓰면 문서·커밋의 번호 참조가 결정 불가가 된다 — HARN-10)"
            )
        if not remote_ok:
            print("  · 번호 충돌 검사: 로컬만 통과 — 머지 시 validate가 2선 방어한다")
    task = Task(
        id=args.id,
        title=args.title,
        track=args.track,
        stage=args.stage,
        subject=args.subject,
        layer=args.layer,
        priority=args.priority,
        owner=args.owner,
        depends_on=args.depends or [],
        requires_gates=args.gates or [],
        acceptance=args.acceptance or [],
        paths=args.paths or [],
        notes=args.notes or "",
        updated=_today(),
    )
    backlog.tasks[task.id] = task
    errors = store.validate_backlog(backlog)
    # 새 태스크가 유발한 오류만 걸러 거부 (기존 백로그의 무관한 경고에 볼모 잡히지 않게)
    own_errors = [e for e in errors if args.id in e]
    if own_errors:
        for e in own_errors:
            print(f"  · {e}", file=sys.stderr)
        return _fail(f"{args.id}: 스키마/무결성 위반으로 추가 거부")
    path = store.save_task(root, task)
    store.append_event(root, "add", task.id)
    print(f"＋ {task.id} 추가 → {path.relative_to(root)}")
    return 0


def cmd_validate(root: Path, args: argparse.Namespace) -> int:
    backlog, schema_errors = _load(root)
    errors = store.validate_backlog(backlog, schema_errors)
    if not errors:
        if not args.quiet:
            print(
                f"✔ 백로그 무결성 green — 태스크 {len(backlog.tasks)}건, "
                f"게이트 {len(backlog.gates)}건, 트랙 {len(backlog.tracks)}건"
            )
        return 0
    print(f"❌ 무결성 위반 {len(errors)}건:", file=sys.stderr)
    for error in errors:
        print(f"  · {error}", file=sys.stderr)
    return 1


def cmd_brief(root: Path, args: argparse.Namespace) -> int:
    backlog, schema_errors = _load(root)
    errors = store.validate_backlog(backlog, schema_errors)
    policy, _ = store.load_policy(root)
    try:
        remote_claimed, remote_status = _remote_claim_map(root, policy)
    except Exception as exc:  # 훅 진입점 — 어떤 실패도 브리핑을 막지 않는다(fail-open·침묵 금지)
        remote_claimed, remote_status = {}, "error"
        print(
            f"⚠ 원격 claim 조회 실패({type(exc).__name__}) — 로컬 정보만 반영",
            file=sys.stderr,
        )

    # 장기 미머지 브랜치 경고 (HARN-13 + 2026-08-05 3분류 확장) — SessionStart 1회 비용,
    # 정보성(브리핑을 막지 않음). active_branches는 이미 계산해둔 remote_claimed의 브랜치
    # 집합을 재사용한다 — 새 원격 조회 없이 "타 세션 진행중"을 판별하기 위함.
    stale_branches: list[tuple[str, float, int, str, str]] = []
    stale_branch_status = "ok"
    stale_branch_message = ""
    if policy.remote_claims:
        try:
            scan = remote_claims.scan_stale_branches(
                root, active_branches=frozenset(remote_claimed.values())
            )
            stale_branch_status = scan.status
            stale_branch_message = scan.message
            if scan.status == "ok":
                stale_branches = [
                    (s.branch, s.age_days, s.ahead, s.status, s.evidence) for s in scan.stale
                ]
        except Exception as exc:  # 훅 진입점 — 어떤 실패도 브리핑을 막지 않는다 (fail-open)
            # 침묵 실패 금지 — 예외 타입명을 브리핑 문자열에 남긴다(훅은 stderr를 버린다).
            stale_branch_status = "error"
            stale_branch_message = f"{type(exc).__name__}: {exc}"
    else:
        stale_branch_status = "disabled"

    # 설계 문서 중복 착수 탐지 (HARN-14) — SessionStart 1회 비용, 나이 임계 없음(HARN-13의
    # 3일 임계 아래에서 새는 것이 이 스캔의 존재 이유 — 문서 중복은 착수 당일이 가장 위험).
    #
    # 2026-08-06 병렬 세션 충돌 정정: 동일 브랜치명(claude/harn-14-doc-series-duplicate-
    # detection)에서 독립 세션이 같은 태스크를 병행 구현해 커밋 41f42a82(scan_new_review_
    # docs)를 먼저 푸시했다. 그 구현은 후보 파일을 3-dot diff(`{trunk}...{ref}`, merge-base
    # 기준)로 얻는데, 이 저장소의 SQUASH 머지 관행에서는 **이미 병합된 브랜치도 오탐**한다
    # — squash는 원본 브랜치 커밋을 트렁크의 조상으로 만들지 않아 merge-base가 옛 분기점에
    # 고정되고, 그 시점 이후 트렁크에 흡수된 파일이 "신규 추가"로 계속 잡힌다(실측: 이미
    # PR #666으로 머지된 claude/whymath-gamification-design-n3mf50에 대해 3-dot은
    # gamification_module_gap_review.md를 거짓 양성으로 보고, 2-dot 직접 diff는 빈 목록을
    # 정확히 반환 — 브랜치가 삭제되지 않는 한 이 오탐은 영구화된다). 이 아래 구현(2-dot
    # 직접 diff, scan_doc_series_duplicates)을 정본으로 유지하고 3-dot 버전은 폐기한다.
    doc_series_candidates: list[tuple[str, tuple[str, ...], str]] = []
    doc_series_status = "ok"
    if policy.remote_claims:
        try:
            doc_scan = remote_claims.scan_doc_series_duplicates(root)
            doc_series_status = doc_scan.status
            if doc_scan.status == "ok":
                doc_series_candidates = [
                    (c.branch, c.files, c.last_commit_at.isoformat()) for c in doc_scan.candidates
                ]
        except Exception:  # 훅 진입점 — 어떤 실패도 브리핑을 막지 않는다 (fail-open)
            doc_series_status = "error"
    else:
        doc_series_status = "disabled"

    # 미머지 done 제외 (HARN-12 — next의 HARN-11 필터를 브리핑에도 배선). render_brief가
    # 내부에서 계산하는 후보 집합과 동일하게(layer/subject/track 미지정) 구해 그 id만
    # scan_remote_done에 묻는다 — fetch 없이 캐시 ref만(훅은 빠르고 네트워크 0이어야 함).
    # 어떤 실패도 브리핑을 막지 않는다(fail-open) — 단 판정 불가를 조용히 넘기지 않는다.
    done_excluded: dict[str, list[str]] = {}
    try:
        if policy.remote_claims:
            ready, _ = selector.candidates(backlog, remote_claimed=remote_claimed)
            if ready:
                done_map, done_status = remote_claims.scan_remote_done(root, [t.id for t in ready])
                done_excluded = {
                    tid: [f.branch for f in finishers] for tid, finishers in done_map.items()
                }
                if done_status != "ok" and not done_excluded:
                    print(
                        f"⚠ 미머지 done 탐지 불가({done_status}) — 완료분이 후보에 섞였을 수 있음",
                        file=sys.stderr,
                    )
    except Exception as exc:  # 훅 진입점 — 어떤 실패도 브리핑을 막지 않는다(fail-open·침묵 금지)
        done_excluded = {}
        print(
            f"⚠ 미머지 done 필터 실패({type(exc).__name__}) — 완료분이 후보에 섞였을 수 있음",
            file=sys.stderr,
        )

    print(
        report.render_brief(
            backlog,
            errors,
            store.current_branch(root),
            date.today(),
            remote_claimed=remote_claimed,
            remote_status=remote_status,
            stale_branches=stale_branches,
            stale_branch_status=stale_branch_status,
            stale_branch_message=stale_branch_message,
            done_excluded=done_excluded,
            doc_series_candidates=doc_series_candidates,
            doc_series_status=doc_series_status,
        )
    )
    return 0


def cmd_check_stop(root: Path, args: argparse.Namespace) -> int:
    """Stop 훅 — 진행 중 태스크가 있는데 상태 갱신 없이 세션이 끝나면 차단(exit 2).

    무한 루프 방지: stop_hook_active=true(이미 이 훅이 개입한 재정지)면 즉시 통과.
    판정이 불확실한 모든 경우는 통과(exit 0) — 훅이 개발을 볼모로 잡으면 안 된다.
    """
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        payload = {}
    if payload.get("stop_hook_active"):
        return 0

    branch = store.current_branch(root)
    if branch in ("unknown", "main", ""):
        return 0

    try:
        backlog, _ = _load(root)
    except Exception:
        return 0

    mine = [t for t in backlog.tasks.values() if t.status == "in_progress" and t.session == branch]
    if not mine:
        return 0

    def _git(*argv: str) -> str:
        result = subprocess.run(
            ["git", *argv],
            cwd=root,
            capture_output=True,
            # HARN-19: 로케일(cp949) 디코드 금지 — git 출력은 UTF-8이 정본이다.
            encoding="utf-8",
            errors="replace",
            timeout=15,
        )
        return (result.stdout or "").strip()

    try:
        base = _git("merge-base", "origin/main", "HEAD") or _git("merge-base", "main", "HEAD")
        if not base:
            return 0
        ahead = int(_git("rev-list", "--count", f"{base}..HEAD") or "0")
        if ahead == 0:
            return 0  # 커밋한 작업이 없으면 갱신을 강제하지 않음
        changed = set(_git("diff", "--name-only", f"{base}..HEAD").splitlines())
        changed |= {
            line[3:] for line in _git("status", "--porcelain").splitlines() if len(line) > 3
        }
    except Exception:
        return 0

    stale = [t for t in mine if f"backlog/tasks/{t.id}.yaml" not in changed]
    if not stale:
        return 0
    ids = ", ".join(t.id for t in stale)
    print(
        f"[빌드하네스] 이 브랜치가 claim한 태스크({ids})의 상태가 갱신되지 않았습니다. "
        f"완료했다면 `python3 scripts/harness/backlog.py done <id> --artifact <PR/커밋>`, "
        f"미완이면 태스크 파일의 notes에 진행 메모를 남기거나 "
        f"`block <id> --reason ...` 처리 후 종료하세요.",
        file=sys.stderr,
    )
    return 2


def cmd_check_edit(root: Path, args: argparse.Namespace) -> int:
    """PostToolUse(Edit|Write) 훅 — 편집 파일에 따라 두 갈래 검사.

    1) backlog/ 파일 직접 편집 → 무결성 validate (기존 동작, 위반 시 exit 2).
    2) 그 외 파일 → 조율 정책 검사 (harness v1.1):
        ① scope_drift  — 내 claim 태스크의 paths 밖 편집
        ② path_overlap — 다른 in-flight 태스크의 paths 안 편집
        ③ adhoc_edit   — claim 없이 코드 도메인(src/ 등) 편집
       warn = stderr 1줄 + policy_warn 이벤트 + exit 0 / block = exit 2.
    판정 불확실·예외는 전부 통과(exit 0) — 훅이 개발을 볼모로 잡으면 안 된다.
    """
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        return 0
    file_path = str((payload.get("tool_input") or {}).get("file_path", ""))
    if "backlog/" in file_path.replace("\\", "/"):
        backlog, schema_errors = _load(root)
        errors = store.validate_backlog(backlog, schema_errors)
        if errors:
            print(
                f"[빌드하네스] backlog 직접 편집 후 무결성 위반 {len(errors)}건:",
                file=sys.stderr,
            )
            for error in errors[:10]:
                print(f"  · {error}", file=sys.stderr)
            return 2
        return 0
    try:
        return _check_edit_policy(root, file_path)
    except Exception:  # 정책 검사 실패는 무조건 통과 (fail-open)
        return 0


def _check_edit_policy(root: Path, file_path: str) -> int:
    """비-backlog 파일 편집의 조율 정책 검사 — check-edit ①②③."""
    from models import CODE_DOMAIN_PREFIXES

    if not file_path:
        return 0
    try:
        rel = str(Path(file_path).resolve().relative_to(root.resolve()))
    except ValueError:
        return 0  # 레포 밖 파일 — 관할 아님
    rel = rel.replace("\\", "/")

    policy, _ = store.load_policy(root)
    branch = store.current_branch(root)
    if branch in ("unknown", "main", ""):
        return 0
    backlog, _ = _load(root)
    mine = [t for t in backlog.tasks.values() if t.status == "in_progress" and t.session == branch]
    violations: list[tuple[str, str, str]] = []  # (rule, mode, 메시지)

    if mine:
        # ① scope_drift — 내 claim 태스크가 paths를 선언했는데 그 밖을 편집
        me = mine[0]
        if me.paths and policy.scope_drift != "off" and not pathscope.path_in_scope(rel, me.paths):
            violations.append(
                (
                    "scope_drift",
                    policy.scope_drift,
                    f"'{rel}' 은 claim 태스크 {me.id}의 선언 범위(paths) 밖 — "
                    f"범위 확장이 맞으면 태스크 YAML의 paths에 추가",
                )
            )
    elif policy.adhoc_edit != "off" and rel.startswith(CODE_DOMAIN_PREFIXES):
        # ③ adhoc_edit — claim 없이 코드 도메인 편집 (하네스에 불가시한 ad-hoc 작업)
        violations.append(
            (
                "adhoc_edit",
                policy.adhoc_edit,
                f"claim한 태스크 없이 코드 파일 '{rel}' 편집 — "
                f"`backlog.py next` 후 `start <id>`로 착수 등록 권장 (중복작업 방지)",
            )
        )

    # ② path_overlap — 다른 세션 in-flight 태스크의 선언 범위 안을 편집.
    # 교차 세션 claim은 로컬 backlog에 안 보이므로 원격 claim 캐시(.git/)를 병합
    # (캐시는 brief/next/start가 원격 조회 성공 시 갱신 — 훅은 네트워크 미사용)
    if policy.path_overlap != "off":
        cached = remote_claims.load_cache(root)
        for other in _inflight_tasks(backlog, cached, branch):
            if not other.paths or other.session == branch:
                continue
            if pathscope.path_in_scope(rel, other.paths):
                violations.append(
                    (
                        "path_overlap",
                        policy.path_overlap,
                        f"'{rel}' 은 다른 세션 태스크 {other.id}"
                        f"(세션: {other.session or '?'})의 작업 범위 — 동시 편집 충돌 위험",
                    )
                )
                break

    if not violations:
        return 0
    blocked = False
    for rule, mode, message in violations:
        store.append_event(root, "policy_warn", "-", rule=rule, file=rel, mode=mode, detail=message)
        print(f"[빌드하네스/{rule}:{mode}] {message}", file=sys.stderr)
        if mode == "block":
            blocked = True
    return 2 if blocked else 0


def cmd_claims(root: Path, args: argparse.Namespace) -> int:
    """원격 claim 관리 — list(기본)·release·reap."""
    backlog, _ = _load(root)
    policy, _ = store.load_policy(root)

    if args.claims_action == "release":
        if not args.claims_id:
            return _fail("claims release <task-id> — 태스크 ID 필수")
        result = remote_claims.release(
            root, args.claims_id, store.current_branch(root), force=args.force
        )
        if result.status != "ok":
            return _fail(f"해제 실패({result.status}): {result.message}")
        store.append_event(root, "claim_release", args.claims_id, forced=args.force)
        print(f"✔ {args.claims_id} 원격 claim 해제")
        return 0

    if args.claims_action == "reap":
        ttl = args.ttl_hours or policy.claim_ttl_hours
        reaped, scan_status, warnings = remote_claims.reap(
            root,
            backlog,
            ttl,
            dry_run=not args.apply,
            branch_grace_hours=policy.claim_branch_grace_hours,
        )
        if scan_status != "ok":
            # 조회 실패를 "stale 없음"으로 위장하지 않는다 — 이 구분이 없어서 CI
            # 교차검증이 공전했다(HARN-09). 판정 불가는 판정 불가라고 말한다.
            print(f"원격 claim 조회 불가 ({scan_status}) — stale 판정 불가")
            return 0 if scan_status == "offline" else 1
        if warnings:
            # reap에서 제외됐지만 침묵시키면 안 되는 것들 — 유예 구간 claim
            # (`task_missing_recent` HARN-21 · `branch_gone_recent` HARN-26)과
            # 홀더 브랜치 조회 실패(판정 미수행). 둘 다 "지우지 않았다"인데 이유가 다르므로
            # 사유 문자열을 그대로 노출한다(CLAUDE.md 침묵 실패 금지).
            print(
                f"⚠ reap 제외 {len(warnings)}건 — 유예 구간이거나 판정 불가"
                "(경합 조건 가능성: 다른 세션이 방금 add+claim했거나 아직 첫 push 전일 수 있다):"
            )
            for item in warnings:
                print(f"  · {item}")
        if not reaped:
            print("stale claim 없음")
            return 0
        label = "삭제됨" if args.apply else "삭제 대상 (dry-run — 실제 삭제는 --apply)"
        print(f"stale claim {len(reaped)}건 {label}:")
        for item in reaped:
            print(f"  · {item}")
        if args.apply:
            store.append_event(root, "claim_reap", "-", reaped=reaped)
        return 0

    # list (기본)
    claims, status = remote_claims.list_claims(root, with_meta=args.verbose or args.json)
    if status != "ok":
        print(f"원격 claim 조회 불가 ({status})")
        return 0 if status == "offline" else 1
    if args.json:
        print(
            json.dumps(
                [{"task": c.task_id, "branch": c.branch, "ts": c.ts, "sha": c.sha} for c in claims],
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    if not claims:
        print("원격 claim 없음")
        return 0
    print(f"원격 claim {len(claims)}건:")
    for c in sorted(claims, key=lambda x: x.task_id):
        meta = f" — {c.branch} ({c.ts})" if c.branch else ""
        local = backlog.tasks.get(c.task_id)
        state = f" [로컬: {local.status}]" if local else " [로컬: 미존재]"
        print(f"  · {c.task_id}{meta}{state}")
    return 0


def cmd_overlap(root: Path, args: argparse.Namespace) -> int:
    """태스크 간 파일 범위 겹침 진단 — 착수 전 수동 확인용."""
    backlog, _ = _load(root)
    task = backlog.tasks.get(args.id)
    if task is None:
        return _fail(f"태스크 '{args.id}' 없음")
    if not task.paths:
        print(f"{task.id}: paths 미선언 — 겹침 판정 불가 (paths 선언 권장)")
        return 0
    if args.against:
        others = [backlog.tasks[args.against]] if args.against in backlog.tasks else []
        if not others:
            return _fail(f"태스크 '{args.against}' 없음")
    else:
        others = [
            t
            for t in backlog.tasks.values()
            if t.id != task.id and t.status in ("in_progress", "review") and t.paths
        ]
    if not others:
        print("비교 대상 in-flight 태스크 없음")
        return 0
    files = pathscope.repo_files(root)
    found = False
    for other in others:
        hit = pathscope.overlap(task.id, task.paths, other.id, other.paths, files)
        if hit:
            found = True
            print(f"⚠ {task.id} ↔ {other.id} (세션: {other.session or '?'}): {hit.describe()}")
    if not found:
        print(f"✔ {task.id}: 겹침 없음 ({len(others)}건 비교)")
    return 0


def cmd_policy(root: Path, args: argparse.Namespace) -> int:
    """조율 정책 — show(현재 값)·report(warn 측정 요약: warn→block 승격 근거)."""
    policy, policy_errors = store.load_policy(root)
    if policy_errors:
        for e in policy_errors:
            print(f"  · {e}", file=sys.stderr)
        return _fail("policy.yaml 오류")

    if args.policy_action == "show" or args.policy_action is None:
        print(store.dump_policy(policy), end="")
        return 0

    # report — events.ndjson의 policy_warn을 rule별 집계 (승격 판단 근거)
    from datetime import datetime, timedelta

    cutoff = datetime.now() - timedelta(days=args.days)
    path = store.backlog_dir(root) / "events.ndjson"
    by_rule: dict[str, list[dict]] = {}
    total = 0
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if event.get("action") != "policy_warn":
                continue
            try:
                ts = datetime.strptime(event.get("ts", ""), "%Y-%m-%dT%H:%M:%S")
            except ValueError:
                continue
            if ts < cutoff:
                continue
            total += 1
            by_rule.setdefault(str(event.get("rule", "?")), []).append(event)
    print(f"조율 정책 warn 리포트 — 최근 {args.days}일, 총 {total}건")
    if not by_rule:
        print("  (경고 없음 — 오탐 0. 승격 기준 충족 여부는 정탐 사례와 함께 판단)")
        return 0
    for rule in sorted(by_rule):
        events = by_rule[rule]
        actors = sorted({str(e.get("actor", "?")) for e in events})
        print(f"  {rule}: {len(events)}건 (세션 {len(actors)}개)")
        for event in events[-3:]:
            detail = event.get("detail") or event.get("file") or event.get("other") or ""
            print(f"    · {event.get('ts')} {detail}")
    print(
        "승격 기준: 2주/30세션 관찰 후 (a)충돌 예방 사례 ≥1 또는 정탐률 ≥50% "
        "(b)오탐 개발중단 0건 → 해당 rule만 block (MEMORY.md 결정로그 필수)"
    )
    return 0


def cmd_seed(root: Path, args: argparse.Namespace) -> int:
    bdir = store.backlog_dir(root)
    if (bdir / "tracks.yaml").exists() and not args.force:
        return _fail("backlog/ 이미 존재 — 재시딩은 --force (기존 상태를 덮어씀에 주의)")
    stage_order, tracks, gates, tasks = build_seed()
    store.save_tracks(root, stage_order, tracks)
    store.save_gates(root, gates)
    for task in tasks:
        store.save_task(root, task)
    backlog, schema_errors = _load(root)
    errors = store.validate_backlog(backlog, schema_errors)
    if errors:
        for error in errors:
            print(f"  · {error}", file=sys.stderr)
        return _fail("시딩 결과 무결성 위반 — seed_data.py 수정 필요")
    store.append_event(
        root, "seed", "backlog", tasks=len(tasks), gates=len(gates), tracks=len(tracks)
    )
    print(
        f"🌱 시딩 완료 — 태스크 {len(tasks)}건, 게이트 {len(gates)}건, "
        f"트랙 {len(tracks)}건 (validate green)"
    )
    return 0


# ── argparse 배선 ────────────────────────────────────────────────────────────


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="backlog.py", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("status", help="프로젝트 현재 상태 한 화면")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("next", help="착수 가능 후보 계산")
    p.add_argument("--n", type=int, default=3)
    p.add_argument("--layer")
    p.add_argument("--subject")
    p.add_argument("--track")
    p.add_argument("--json", action="store_true")
    p.add_argument(
        "--no-remote",
        action="store_true",
        dest="no_remote",
        help="원격 claim 조회 생략",
    )
    p.set_defaults(func=cmd_next)

    p = sub.add_parser("start", help="태스크 착수 (claim)")
    p.add_argument("id")
    p.add_argument("--session")
    p.add_argument(
        "--no-remote",
        action="store_true",
        dest="no_remote",
        help="원격 claim 생략 (오프라인·긴급용) — CAS·읽기측 보호 전체 포기",
    )
    p.add_argument(
        "--ignore-remote-claim",
        action="store_true",
        dest="ignore_remote_claim",
        help="이 태스크의 읽기측 교차 세션 판정만 무시 (stale 홀더 확인 후 — "
        "HARN-08). CAS conflict는 무시되지 않는다",
    )
    p.add_argument(
        "--as",
        dest="as_owner",
        default=None,
        choices=[o for o in OWNERS if o != "claude"],
        help="사람-소유 태스크를 소유자 본인이 기입할 때 명시 (HARN-06)",
    )
    p.set_defaults(func=cmd_start)

    p = sub.add_parser("done", help="태스크 완료 (증적 필수)")
    p.add_argument("id")
    p.add_argument("--artifact", action="append", default=[])
    p.add_argument(
        "--as",
        dest="as_owner",
        default=None,
        choices=[o for o in OWNERS if o != "claude"],
        help="사람-소유 태스크를 소유자 본인이 기입할 때 명시 (HARN-06)",
    )
    p.set_defaults(func=cmd_done)

    p = sub.add_parser("block", help="태스크 차단")
    p.add_argument("id")
    p.add_argument("--reason", required=True)
    p.set_defaults(func=cmd_block)

    p = sub.add_parser("unblock", help="차단 해제")
    p.add_argument("id")
    p.set_defaults(func=cmd_unblock)

    p = sub.add_parser("review", help="검토 대기로 전환 (in_progress → review, HARN-20)")
    p.add_argument("id")
    p.set_defaults(func=cmd_review)

    p = sub.add_parser("cancel", help="태스크 취소 (todo/blocked → cancelled, HARN-20)")
    p.add_argument("id")
    p.add_argument("--reason", required=True)
    p.set_defaults(func=cmd_cancel)

    p = sub.add_parser("gates", help="사람 게이트 대장")
    p.add_argument("gate_action", nargs="?", choices=["list", "add", "clear", "waive"])
    p.add_argument("gate_id", nargs="?")
    p.add_argument("--evidence")
    p.add_argument("--reason")
    # gates add 전용 플래그 (다른 액션에서는 무시됨 — 기본값이 간섭하지 않음)
    p.add_argument("--title", help="gates add: 게이트 제목 (필수)")
    p.add_argument(
        "--kind",
        choices=list(GATE_KINDS),
        default="human",
        help="gates add: 게이트 종류 (기본 human)",
    )
    p.add_argument("--assignee", default="kiki", help="gates add: 담당자 (기본 kiki)")
    p.add_argument(
        "--remind-after-days",
        type=int,
        dest="remind_after_days",
        default=None,
        help="gates add: 경과 시 SessionStart 브리핑 리마인드 일수",
    )
    p.set_defaults(func=cmd_gates)

    p = sub.add_parser("add", help="태스크 추가 (/plan의 산출물)")
    p.add_argument("--id", required=True)
    p.add_argument("--title", required=True)
    p.add_argument("--track", required=True)
    p.add_argument("--stage", required=True)
    p.add_argument("--subject", default="math")
    p.add_argument("--layer", default="backend")
    p.add_argument("--priority", type=int, default=3)
    p.add_argument("--owner", default="claude")
    p.add_argument("--depends", action="append", default=[])
    p.add_argument("--gates", action="append", default=[])
    p.add_argument("--acceptance", action="append", default=[])
    p.add_argument(
        "--path",
        action="append",
        default=[],
        dest="paths",
        help="작업 파일 범위 glob (겹침 검사용 — 반복 지정 가능)",
    )
    p.add_argument("--notes")
    p.set_defaults(func=cmd_add)

    p = sub.add_parser("validate", help="백로그 무결성 전수 검증")
    p.add_argument("--quiet", action="store_true")
    p.set_defaults(func=cmd_validate)

    p = sub.add_parser("brief", help="SessionStart 훅용 압축 브리핑")
    p.add_argument("--format", choices=["hook", "text"], default="text")
    p.set_defaults(func=cmd_brief)

    p = sub.add_parser("check-stop", help="Stop 훅 — 상태 갱신 강제")
    p.set_defaults(func=cmd_check_stop)

    p = sub.add_parser("check-edit", help="PostToolUse 훅 — backlog 직접 편집 검증")
    p.set_defaults(func=cmd_check_edit)

    p = sub.add_parser("claims", help="원격 claim(harness-claims 브랜치) 조회·해제·청소")
    p.add_argument("claims_action", nargs="?", default="list", choices=["list", "release", "reap"])
    p.add_argument("claims_id", nargs="?")
    p.add_argument("--json", action="store_true")
    p.add_argument("--verbose", action="store_true", help="claim 메타(브랜치·시각) 포함")
    p.add_argument("--force", action="store_true", help="남의 claim 강제 해제")
    p.add_argument(
        "--ttl-hours",
        type=int,
        dest="ttl_hours",
        help="reap TTL (기본: policy.claim_ttl_hours)",
    )
    p.add_argument("--apply", action="store_true", help="reap 실제 삭제 (기본 dry-run)")
    p.set_defaults(func=cmd_claims)

    p = sub.add_parser("overlap", help="태스크 간 파일 범위 겹침 진단")
    p.add_argument("id")
    p.add_argument("--against", help="특정 태스크와만 비교 (기본: 전체 in-flight)")
    p.set_defaults(func=cmd_overlap)

    p = sub.add_parser("policy", help="조율 정책 표시·warn 측정 리포트")
    p.add_argument("policy_action", nargs="?", choices=["show", "report"])
    p.add_argument("--days", type=int, default=14)
    p.set_defaults(func=cmd_policy)

    p = sub.add_parser("seed", help="초기 백로그 시딩 (최초 1회)")
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=cmd_seed)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        root = find_root_for_cli()
    except RuntimeError as exc:
        return _fail(str(exc), code=3)
    try:
        return args.func(root, args)
    except RuntimeError as exc:  # PyYAML 부재 등 환경 오류
        return _fail(str(exc), code=3)


def find_root_for_cli() -> Path:
    """CLI 실행 위치와 무관하게 저장소 루트 결정 (worktree 대응: cwd 우선)."""
    cwd = Path.cwd()
    for candidate in (cwd, *cwd.parents):
        if (candidate / ".git").exists():
            return candidate
    return store.find_repo_root()


if __name__ == "__main__":
    sys.exit(main())
