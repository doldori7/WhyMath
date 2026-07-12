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

import report
import selector
import store
from models import STATUS_TRANSITIONS, Task
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


def cmd_next(root: Path, args: argparse.Namespace) -> int:
    backlog, _ = _load(root)
    ready, excluded = selector.candidates(
        backlog, layer=args.layer, subject=args.subject, track=args.track
    )
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
    exclusion = selector.classify_todo(backlog, task)
    if exclusion is not None:
        return _fail(f"{task.id} 착수 거부 — {exclusion.reason}: {exclusion.detail}")
    task.status = "in_progress"
    task.session = args.session or store.current_branch(root)
    task.updated = _today()
    store.save_task(root, task)
    store.append_event(root, "start", task.id, session=task.session)
    print(f"▶ {task.id} 착수 (세션: {task.session})")
    print(f"  완료 조건: {task.acceptance or '(acceptance 미정의 — 정의 권장)'}")
    return 0


def cmd_done(root: Path, args: argparse.Namespace) -> int:
    backlog, _ = _load(root)
    task = backlog.tasks.get(args.id)
    if task is None:
        return _fail(f"태스크 '{args.id}' 없음")
    if not args.artifact:
        return _fail(f"{task.id}: --artifact <PR/커밋> 필수 (증적 없는 done 금지)")
    error = _transition(task, "done")
    if error:
        return _fail(error)
    task.status = "done"
    task.artifacts = list(dict.fromkeys(task.artifacts + args.artifact))
    task.session = None
    task.updated = _today()
    store.save_task(root, task)
    store.append_event(root, "done", task.id, artifacts=args.artifact)
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
    task.status = "blocked"
    task.session = None
    task.notes = args.reason
    task.updated = _today()
    store.save_task(root, task)
    store.append_event(root, "block", task.id, reason=args.reason)
    print(f"✖ {task.id} 차단 — {args.reason}")
    return 0


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
    print(report.render_brief(backlog, errors, store.current_branch(root), date.today()))
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
    """PostToolUse(Edit|Write) 훅 — backlog/ 파일을 직접 편집한 경우에만 validate."""
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        return 0
    file_path = str((payload.get("tool_input") or {}).get("file_path", ""))
    if "backlog/" not in file_path.replace("\\", "/"):
        return 0
    backlog, schema_errors = _load(root)
    errors = store.validate_backlog(backlog, schema_errors)
    if errors:
        print(f"[빌드하네스] backlog 직접 편집 후 무결성 위반 {len(errors)}건:", file=sys.stderr)
        for error in errors[:10]:
            print(f"  · {error}", file=sys.stderr)
        return 2
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
    p.set_defaults(func=cmd_next)

    p = sub.add_parser("start", help="태스크 착수 (claim)")
    p.add_argument("id")
    p.add_argument("--session")
    p.set_defaults(func=cmd_start)

    p = sub.add_parser("done", help="태스크 완료 (증적 필수)")
    p.add_argument("id")
    p.add_argument("--artifact", action="append", default=[])
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
