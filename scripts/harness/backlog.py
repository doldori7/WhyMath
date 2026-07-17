#!/usr/bin/env python3
"""빌드 하네스 CLI — 작업일정 단일 진실 원천(backlog/)의 유일한 조작 창구.

사용:
    python3 scripts/harness/backlog.py status [--json]
    python3 scripts/harness/backlog.py next [--n 3] [--layer L] [--subject S] [--track T]
    python3 scripts/harness/backlog.py start <id> [--session <branch>]
    python3 scripts/harness/backlog.py done <id> --artifact <PR/커밋> [--artifact ...]
    python3 scripts/harness/backlog.py block <id> --reason <사유>
    python3 scripts/harness/backlog.py unblock <id>
    python3 scripts/harness/backlog.py gates [list]
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
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pathscope
import remote_claims
import report
import selector
import store
from models import OWNERS, STATUS_TRANSITIONS, Task
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
        return (f"{task.id}: {task.status} → {new_status} 전이 불가 "
                f"(허용: {list(allowed) or '없음(종결 상태)'})")
    return None


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
    inflight = [t for t in backlog.tasks.values()
                if t.status in ("in_progress", "review") and t.paths]
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
        root, policy, skip=getattr(args, "no_remote", False))
    ready, excluded = selector.candidates(
        backlog, layer=args.layer, subject=args.subject, track=args.track,
        remote_claimed=remote_claimed,
        overlap_block=_overlap_block_map(root, backlog, policy),
    )
    if remote_status not in ("ok", "disabled"):
        print(f"⚠ 원격 claim 조회 불가({remote_status}) — 로컬 claim 정보만 반영",
              file=sys.stderr)
    if args.json:
        print(json.dumps(
            [{"id": t.id, "layer": t.layer, "subject": t.subject, "title": t.title,
              "rationale": selector.selection_rationale(backlog, t)}
             for t in ready[: args.n]],
            ensure_ascii=False, indent=2,
        ))
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
        return _fail(
            f"{task.id}: --as {as_owner} 불일치 — 이 태스크의 owner는 '{task.owner}'"
        )
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
    remote_claimed, _ = _remote_claim_map(
        root, policy, skip=getattr(args, "no_remote", False))

    # [프리플라이트 1] 파일 범위 겹침 — 타 in-flight(로컬 ∪ 원격 claim) paths와 교차
    overlap_error = _check_path_overlap(root, backlog, task, policy,
                                        remote_claimed=remote_claimed, session=session)
    if overlap_error:
        return _fail(overlap_error)

    # [프리플라이트 2] 원격 claim — 로컬 검사 전부 통과 후 마지막 (dangling ref 방지).
    # conflict만 차단, offline/error는 fail-open(경고 후 로컬 claim으로 진행).
    remote_status = "disabled"
    if policy.remote_claims and not getattr(args, "no_remote", False):
        result = remote_claims.claim(root, task.id, session)
        remote_status = result.status
        if result.status == "conflict":
            other = result.claim
            detail = (f" (세션: {other.branch or '?'}, {other.ts or '시각 불명'})"
                      if other else "")
            return _fail(f"{task.id} 착수 거부 — 다른 세션이 이미 원격 claim{detail}\n"
                         f"  본인 claim이 확실하면: claims release {task.id} --force 후 재시도")
        if result.status in ("offline", "error"):
            print(f"⚠ 원격 claim 불가({result.status}) — 로컬 claim만으로 진행: "
                  f"{result.message}", file=sys.stderr)
            store.append_event(root, "claim_remote_unavailable", task.id,
                               status=result.status)

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
        print("  ⚠ paths 미선언 — 겹침 검사에서 제외됩니다. "
              "태스크 YAML에 paths(작업 파일 glob) 선언을 권장", file=sys.stderr)
    for warning in task.layer_drift_warnings():
        print(f"  ⚠ {warning}", file=sys.stderr)
    return 0


def _inflight_tasks(backlog, remote_claimed: dict[str, str] | None,
                    session: str | None) -> list[Task]:
    """in-flight 태스크 = 로컬(in_progress·review) ∪ 원격 claim (내 세션 제외).

    태스크 정의(YAML·paths)는 git으로 전 세션에 공유되지만, 상태(in_progress)는
    claim한 브랜치의 사본에만 있다 — 원격 claim ref가 교차 세션의 유일한 신호다.
    """
    result: dict[str, Task] = {
        t.id: t for t in backlog.tasks.values()
        if t.status in ("in_progress", "review")
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


def _check_path_overlap(root: Path, backlog, task: Task, policy,
                        remote_claimed: dict[str, str] | None = None,
                        session: str | None = None) -> str | None:
    """start 프리플라이트 — 타 in-flight 태스크와 paths 교차 검사.

    warn: stderr 경고 + policy_warn 이벤트 후 진행(None 반환).
    block: 오류 메시지 반환(호출측이 exit 1).
    """
    if policy.path_overlap == "off" or not task.paths:
        return None
    inflight = [t for t in _inflight_tasks(backlog, remote_claimed, session)
                if t.id != task.id and t.paths]
    if not inflight:
        return None
    files = pathscope.repo_files(root)
    for other in inflight:
        hit = pathscope.overlap(task.id, task.paths, other.id, other.paths, files)
        if hit is None:
            continue
        desc = (f"{task.id} ↔ {other.id}(세션: {other.session or '?'}) "
                f"파일 범위 겹침 — {hit.describe()}")
        store.append_event(root, "policy_warn", task.id, rule="path_overlap",
                           other=other.id, detail=hit.describe(),
                           mode=policy.path_overlap)
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
        return _fail(
            f"{task.id}: --as {as_owner} 불일치 — 이 태스크의 owner는 '{task.owner}'"
        )
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
        t for t in backlog.tasks.values()
        if task.id in t.depends_on and t.status == "todo"
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
    task.notes = args.reason
    task.updated = _today()
    store.save_task(root, task)
    store.append_event(root, "block", task.id, reason=args.reason)
    _release_remote_claim(root, task.id, prev_session)
    print(f"✖ {task.id} 차단 — {args.reason}")
    return 0


def _release_remote_claim(root: Path, task_id: str, prev_session: str | None) -> None:
    """done/block 후 원격 claim 해제 — best-effort (실패해도 진행, reap이 나중에 청소)."""
    policy, _ = store.load_policy(root)
    if not policy.remote_claims:
        return
    result = remote_claims.release(root, task_id,
                                   prev_session or store.current_branch(root))
    if result.status not in ("ok", "offline"):
        print(f"⚠ 원격 claim 해제 실패({result.status}): {result.message} — "
              f"`claims reap`이 이후 청소합니다", file=sys.stderr)
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
    store.append_event(root, f"gate_{args.gate_action}", gate.id,
                       evidence=gate.evidence, reason=args.reason)
    print(f"✔ {gate.id} → {gate.status}")
    return 0


def cmd_add(root: Path, args: argparse.Namespace) -> int:
    backlog, _ = _load(root)
    if args.id in backlog.tasks:
        return _fail(f"태스크 ID 중복: {args.id}")
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
            print(f"✔ 백로그 무결성 green — 태스크 {len(backlog.tasks)}건, "
                  f"게이트 {len(backlog.gates)}건, 트랙 {len(backlog.tracks)}건")
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
    except Exception:  # 훅 진입점 — 어떤 실패도 브리핑을 막지 않는다 (fail-open)
        remote_claimed, remote_status = {}, "error"
    print(report.render_brief(backlog, errors, store.current_branch(root), date.today(),
                              remote_claimed=remote_claimed, remote_status=remote_status))
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

    mine = [t for t in backlog.tasks.values()
            if t.status == "in_progress" and t.session == branch]
    if not mine:
        return 0

    def _git(*argv: str) -> str:
        result = subprocess.run(["git", *argv], cwd=root,
                                capture_output=True, text=True, timeout=15)
        return result.stdout.strip()

    try:
        base = _git("merge-base", "origin/main", "HEAD") or _git("merge-base", "main", "HEAD")
        if not base:
            return 0
        ahead = int(_git("rev-list", "--count", f"{base}..HEAD") or "0")
        if ahead == 0:
            return 0  # 커밋한 작업이 없으면 갱신을 강제하지 않음
        changed = set(_git("diff", "--name-only", f"{base}..HEAD").splitlines())
        changed |= {line[3:] for line in _git("status", "--porcelain").splitlines() if len(line) > 3}
    except Exception:
        return 0

    stale = [t for t in mine
             if f"backlog/tasks/{t.id}.yaml" not in changed]
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
            print(f"[빌드하네스] backlog 직접 편집 후 무결성 위반 {len(errors)}건:", file=sys.stderr)
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
    mine = [t for t in backlog.tasks.values()
            if t.status == "in_progress" and t.session == branch]
    violations: list[tuple[str, str, str]] = []  # (rule, mode, 메시지)

    if mine:
        # ① scope_drift — 내 claim 태스크가 paths를 선언했는데 그 밖을 편집
        me = mine[0]
        if me.paths and policy.scope_drift != "off" \
                and not pathscope.path_in_scope(rel, me.paths):
            violations.append((
                "scope_drift", policy.scope_drift,
                f"'{rel}' 은 claim 태스크 {me.id}의 선언 범위(paths) 밖 — "
                f"범위 확장이 맞으면 태스크 YAML의 paths에 추가",
            ))
    elif policy.adhoc_edit != "off" and rel.startswith(CODE_DOMAIN_PREFIXES):
        # ③ adhoc_edit — claim 없이 코드 도메인 편집 (하네스에 불가시한 ad-hoc 작업)
        violations.append((
            "adhoc_edit", policy.adhoc_edit,
            f"claim한 태스크 없이 코드 파일 '{rel}' 편집 — "
            f"`backlog.py next` 후 `start <id>`로 착수 등록 권장 (중복작업 방지)",
        ))

    # ② path_overlap — 다른 세션 in-flight 태스크의 선언 범위 안을 편집.
    # 교차 세션 claim은 로컬 backlog에 안 보이므로 원격 claim 캐시(.git/)를 병합
    # (캐시는 brief/next/start가 원격 조회 성공 시 갱신 — 훅은 네트워크 미사용)
    if policy.path_overlap != "off":
        cached = remote_claims.load_cache(root)
        for other in _inflight_tasks(backlog, cached, branch):
            if not other.paths or other.session == branch:
                continue
            if pathscope.path_in_scope(rel, other.paths):
                violations.append((
                    "path_overlap", policy.path_overlap,
                    f"'{rel}' 은 다른 세션 태스크 {other.id}"
                    f"(세션: {other.session or '?'})의 작업 범위 — 동시 편집 충돌 위험",
                ))
                break

    if not violations:
        return 0
    blocked = False
    for rule, mode, message in violations:
        store.append_event(root, "policy_warn", "-", rule=rule, file=rel, mode=mode,
                           detail=message)
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
        result = remote_claims.release(root, args.claims_id,
                                       store.current_branch(root), force=args.force)
        if result.status != "ok":
            return _fail(f"해제 실패({result.status}): {result.message}")
        store.append_event(root, "claim_release", args.claims_id, forced=args.force)
        print(f"✔ {args.claims_id} 원격 claim 해제")
        return 0

    if args.claims_action == "reap":
        ttl = args.ttl_hours or policy.claim_ttl_hours
        reaped = remote_claims.reap(root, backlog, ttl, dry_run=not args.apply)
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
        print(json.dumps(
            [{"task": c.task_id, "branch": c.branch, "ts": c.ts, "sha": c.sha}
             for c in claims],
            ensure_ascii=False, indent=2,
        ))
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
        others = [t for t in backlog.tasks.values()
                  if t.id != task.id and t.status in ("in_progress", "review") and t.paths]
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
    print("승격 기준: 2주/30세션 관찰 후 (a)충돌 예방 사례 ≥1 또는 정탐률 ≥50% "
          "(b)오탐 개발중단 0건 → 해당 rule만 block (MEMORY.md 결정로그 필수)")
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
    store.append_event(root, "seed", "backlog",
                       tasks=len(tasks), gates=len(gates), tracks=len(tracks))
    print(f"🌱 시딩 완료 — 태스크 {len(tasks)}건, 게이트 {len(gates)}건, "
          f"트랙 {len(tracks)}건 (validate green)")
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
    p.add_argument("--no-remote", action="store_true", dest="no_remote",
                   help="원격 claim 조회 생략")
    p.set_defaults(func=cmd_next)

    p = sub.add_parser("start", help="태스크 착수 (claim)")
    p.add_argument("id")
    p.add_argument("--session")
    p.add_argument("--no-remote", action="store_true", dest="no_remote",
                   help="원격 claim 생략 (오프라인·긴급용)")
    p.add_argument("--as", dest="as_owner", default=None,
                   choices=[o for o in OWNERS if o != "claude"],
                   help="사람-소유 태스크를 소유자 본인이 기입할 때 명시 (HARN-06)")
    p.set_defaults(func=cmd_start)

    p = sub.add_parser("done", help="태스크 완료 (증적 필수)")
    p.add_argument("id")
    p.add_argument("--artifact", action="append", default=[])
    p.add_argument("--as", dest="as_owner", default=None,
                   choices=[o for o in OWNERS if o != "claude"],
                   help="사람-소유 태스크를 소유자 본인이 기입할 때 명시 (HARN-06)")
    p.set_defaults(func=cmd_done)

    p = sub.add_parser("block", help="태스크 차단")
    p.add_argument("id")
    p.add_argument("--reason", required=True)
    p.set_defaults(func=cmd_block)

    p = sub.add_parser("unblock", help="차단 해제")
    p.add_argument("id")
    p.set_defaults(func=cmd_unblock)

    p = sub.add_parser("gates", help="사람 게이트 대장")
    p.add_argument("gate_action", nargs="?", choices=["list", "clear", "waive"])
    p.add_argument("gate_id", nargs="?")
    p.add_argument("--evidence")
    p.add_argument("--reason")
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
    p.add_argument("--path", action="append", default=[], dest="paths",
                   help="작업 파일 범위 glob (겹침 검사용 — 반복 지정 가능)")
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

    p = sub.add_parser("claims", help="원격 claim(refs/claims/*) 조회·해제·청소")
    p.add_argument("claims_action", nargs="?", default="list",
                   choices=["list", "release", "reap"])
    p.add_argument("claims_id", nargs="?")
    p.add_argument("--json", action="store_true")
    p.add_argument("--verbose", action="store_true", help="claim 메타(브랜치·시각) 포함")
    p.add_argument("--force", action="store_true", help="남의 claim 강제 해제")
    p.add_argument("--ttl-hours", type=int, dest="ttl_hours",
                   help="reap TTL (기본: policy.claim_ttl_hours)")
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
