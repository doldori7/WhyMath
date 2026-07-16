"""backlog/ 저장소 — 로드·저장·이벤트 로그·무결성 검증.

파일 배치 (전부 git 커밋 대상):
    backlog/tracks.yaml      트랙 정의 + stage_order
    backlog/gates.yaml       사람 게이트 대장
    backlog/tasks/<id>.yaml  태스크당 1파일 (병렬 세션 충돌 원천 차단)
    backlog/events.ndjson    append-only 상태변경 로그 (merge=union)

읽기는 PyYAML(사람 손 편집 허용을 위해), 쓰기는 자체 직렬화기
(키 순서·인용 규칙 고정 → diff 안정·결정적 출력).
"""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import fields as dc_fields
from datetime import date, datetime
from pathlib import Path

from models import (
    Backlog,
    Gate,
    Policy,
    Task,
    Track,
)

try:
    import yaml  # type: ignore[import-untyped]
except ImportError:  # pragma: no cover - 환경 의존
    yaml = None

YAML_MISSING_MSG = (
    "[빌드하네스] PyYAML이 없습니다. `python3 -m pip install pyyaml` 후 재시도하세요."
)

# ── 경로 ─────────────────────────────────────────────────────────────────────


def find_repo_root(start: Path | None = None) -> Path:
    """`.git`을 기준으로 저장소 루트 탐색 (스크립트 위치 → 상위)."""
    here = (start or Path(__file__).resolve().parent)
    for candidate in (here, *here.parents):
        if (candidate / ".git").exists():
            return candidate
    raise RuntimeError("git 저장소 루트를 찾지 못했습니다")


def backlog_dir(root: Path) -> Path:
    return root / "backlog"


# ── 직렬화 (쓰기: 자체 규칙, 읽기: PyYAML) ──────────────────────────────────

_BARE_SAFE_RE = re.compile(r"^[A-Za-z0-9가-힣][A-Za-z0-9가-힣 ._/·→\-]*$")
_YAML_RESERVED = {"null", "true", "false", "yes", "no", "on", "off", "~"}


def _scalar(value: object) -> str:
    """스칼라 1개를 YAML 안전 문자열로 (모호하면 JSON 인용 = 유효한 YAML)."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    s = str(value)
    needs_quote = (
        not _BARE_SAFE_RE.match(s)
        or s.lower() in _YAML_RESERVED
        or re.match(r"^\d+$", s) is not None
        or s != s.strip()
    )
    return json.dumps(s, ensure_ascii=False) if needs_quote else s


def _dump_mapping(data: dict[str, object], key_order: list[str]) -> str:
    """1단 매핑 + 문자열 리스트를 고정 키 순서로 직렬화."""
    lines: list[str] = []
    for key in key_order:
        if key not in data:
            continue
        value = data[key]
        if isinstance(value, list):
            if not value:
                lines.append(f"{key}: []")
            else:
                lines.append(f"{key}:")
                lines.extend(f"  - {_scalar(item)}" for item in value)
        else:
            lines.append(f"{key}: {_scalar(value)}")
    return "\n".join(lines) + "\n"


_TASK_KEY_ORDER = [f.name for f in dc_fields(Task)]
_GATE_KEY_ORDER = [f.name for f in dc_fields(Gate)]


def dump_task(task: Task) -> str:
    data = {k: getattr(task, k) for k in _TASK_KEY_ORDER}
    header = "# 빌드 하네스 태스크 — 상태 변경은 scripts/harness/backlog.py CLI 사용 권장\n"
    return header + _dump_mapping(data, _TASK_KEY_ORDER)


def dump_gates(gates: list[Gate]) -> str:
    lines = ["# 사람 게이트 대장 — clear는 evidence 필수 (backlog.py gates clear <id> --evidence ...)", "gates:"]
    for gate in gates:
        data = {k: getattr(gate, k) for k in _GATE_KEY_ORDER}
        first = True
        for key in _GATE_KEY_ORDER:
            prefix = "  - " if first else "    "
            lines.append(f"{prefix}{key}: {_scalar(data[key])}")
            first = False
    return "\n".join(lines) + "\n"


def dump_tracks(stage_order: list[str], tracks: list[Track]) -> str:
    lines = [
        "# 트랙 정의 — stage_order가 next 정렬의 1차 키다",
        "stage_order: [" + ", ".join(stage_order) + "]",
        "tracks:",
    ]
    for track in tracks:
        lines.append(f"  {track.id}:")
        lines.append(f"    title: {_scalar(track.title)}")
        if track.roadmap_ref:
            lines.append(f"    roadmap_ref: {_scalar(track.roadmap_ref)}")
        if track.entry_gate:
            lines.append(f"    entry_gate: {_scalar(track.entry_gate)}")
    return "\n".join(lines) + "\n"


def _load_yaml(path: Path) -> dict:
    if yaml is None:  # pragma: no cover - 환경 의존
        raise RuntimeError(YAML_MISSING_MSG)
    with path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    return data or {}


def _coerce(cls: type, data: dict, source: str, errors: list[str]) -> object | None:
    """dict → dataclass. 미지 키는 오류로 기록(오타 방지)."""
    known = {f.name for f in dc_fields(cls)}
    unknown = set(data) - known
    if unknown:
        errors.append(f"{source}: 미지 필드 {sorted(unknown)}")
    kwargs = {k: v for k, v in data.items() if k in known}
    # 리스트 필드의 None을 빈 리스트로 정규화 (손 편집 관용)
    for f in dc_fields(cls):
        if f.name in kwargs and kwargs[f.name] is None and "list" in str(f.type):
            kwargs[f.name] = []
        # PyYAML이 날짜를 date 객체로 파싱하는 경우 문자열로 되돌림
        if isinstance(kwargs.get(f.name), (date, datetime)):
            kwargs[f.name] = kwargs[f.name].strftime("%Y-%m-%d")
    try:
        return cls(**kwargs)
    except TypeError as exc:
        errors.append(f"{source}: 필수 필드 누락 또는 형식 오류 — {exc}")
        return None


# ── 로드 ─────────────────────────────────────────────────────────────────────


def load_backlog(root: Path) -> tuple[Backlog, list[str]]:
    """backlog/ 전체 로드. (백로그, 스키마 오류 목록) 반환."""
    errors: list[str] = []
    bdir = backlog_dir(root)
    backlog = Backlog()

    tracks_path = bdir / "tracks.yaml"
    if tracks_path.exists():
        raw = _load_yaml(tracks_path)
        backlog.stage_order = list(raw.get("stage_order") or [])
        for tid, tdata in (raw.get("tracks") or {}).items():
            track = _coerce(Track, {"id": tid, **(tdata or {})}, f"tracks.yaml:{tid}", errors)
            if track:
                backlog.tracks[tid] = track  # type: ignore[assignment]
    else:
        errors.append("backlog/tracks.yaml 없음 (seed 미실행?)")

    gates_path = bdir / "gates.yaml"
    if gates_path.exists():
        raw = _load_yaml(gates_path)
        for gdata in raw.get("gates") or []:
            gate = _coerce(Gate, gdata or {}, f"gates.yaml:{(gdata or {}).get('id', '?')}", errors)
            if gate:
                backlog.gates[gate.id] = gate  # type: ignore[union-attr]

    tasks_dir = bdir / "tasks"
    if tasks_dir.is_dir():
        for path in sorted(tasks_dir.glob("*.yaml")):
            raw = _load_yaml(path)
            task = _coerce(Task, raw, path.name, errors)
            if task is None:
                continue
            assert isinstance(task, Task)
            if task.id != path.stem:
                errors.append(f"{path.name}: id '{task.id}' ≠ 파일명 stem (단일 진실 원천 위반)")
            if task.id in backlog.tasks:
                errors.append(f"{path.name}: 태스크 ID 중복 '{task.id}'")
            backlog.tasks[task.id] = task

    return backlog, errors


# ── 저장·이벤트 ──────────────────────────────────────────────────────────────


def save_task(root: Path, task: Task) -> Path:
    path = backlog_dir(root) / "tasks" / f"{task.id}.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dump_task(task), encoding="utf-8")
    return path


def save_gates(root: Path, gates: list[Gate]) -> Path:
    path = backlog_dir(root) / "gates.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dump_gates(gates), encoding="utf-8")
    return path


def save_tracks(root: Path, stage_order: list[str], tracks: list[Track]) -> Path:
    path = backlog_dir(root) / "tracks.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dump_tracks(stage_order, tracks), encoding="utf-8")
    return path


# ── 정책 (backlog/policy.yaml — 부재 시 전부 기본값 = 하위호환) ──────────────

_POLICY_KEY_ORDER = [f.name for f in dc_fields(Policy)]


def dump_policy(policy: Policy) -> str:
    header = (
        "# 조율 정책 — 중복·겹침 감지 강제 수준. 승격(warn→block)은 측정 근거 +\n"
        "# MEMORY.md 결정로그 필수 (docs/standards/build_harness.md §정책)\n"
    )
    data = {k: getattr(policy, k) for k in _POLICY_KEY_ORDER}
    return header + _dump_mapping(data, _POLICY_KEY_ORDER)


def load_policy(root: Path) -> tuple[Policy, list[str]]:
    """policy.yaml 로드. (정책, 오류 목록) 반환 — 파일 부재는 기본값(오류 아님)."""
    errors: list[str] = []
    path = backlog_dir(root) / "policy.yaml"
    if not path.exists():
        return Policy(), errors
    raw = _load_yaml(path)
    policy = _coerce(Policy, raw, "policy.yaml", errors)
    if policy is None:
        return Policy(), errors
    assert isinstance(policy, Policy)
    errors.extend(policy.validate())
    return policy, errors


def save_policy(root: Path, policy: Policy) -> Path:
    path = backlog_dir(root) / "policy.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dump_policy(policy), encoding="utf-8")
    return path


def current_branch(root: Path) -> str:
    """현재 git 브랜치명 (실패 시 'unknown')."""
    try:
        out = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=root, capture_output=True, text=True, timeout=10,
        )
        return out.stdout.strip() or "unknown"
    except Exception:  # pragma: no cover - 환경 의존
        return "unknown"


def append_event(root: Path, action: str, subject_id: str, **extra: object) -> None:
    """append-only 이벤트 로그 (merge=union — 병렬 세션 충돌 흡수)."""
    path = backlog_dir(root) / "events.ndjson"
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "ts": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "actor": current_branch(root),
        "action": action,
        "id": subject_id,
        **extra,
    }
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")


# ── 무결성 검증 ──────────────────────────────────────────────────────────────


def detect_cycle(backlog: Backlog) -> list[str]:
    """depends_on 그래프의 사이클을 Kahn 위상정렬로 검출. 사이클 노드 목록 반환."""
    indegree = {tid: 0 for tid in backlog.tasks}
    dependents: dict[str, list[str]] = {tid: [] for tid in backlog.tasks}
    for task in backlog.tasks.values():
        for dep in task.depends_on:
            if dep in backlog.tasks:
                indegree[task.id] += 1
                dependents[dep].append(task.id)
    queue = [tid for tid, deg in indegree.items() if deg == 0]
    visited = 0
    while queue:
        tid = queue.pop()
        visited += 1
        for nxt in dependents[tid]:
            indegree[nxt] -= 1
            if indegree[nxt] == 0:
                queue.append(nxt)
    if visited == len(backlog.tasks):
        return []
    return sorted(tid for tid, deg in indegree.items() if deg > 0)


def validate_backlog(backlog: Backlog, schema_errors: list[str] | None = None) -> list[str]:
    """전체 무결성 검증 — 위반 목록 반환 (빈 리스트 = green)."""
    errors: list[str] = list(schema_errors or [])

    for track in backlog.tracks.values():
        errors.extend(track.validate())
        if track.entry_gate and track.entry_gate not in backlog.gates:
            errors.append(f"{track.id}: entry_gate '{track.entry_gate}' 가 gates.yaml에 없음")
    for gate in backlog.gates.values():
        errors.extend(gate.validate())

    sessions_in_progress: dict[str, list[str]] = {}
    for task in backlog.tasks.values():
        errors.extend(task.validate())
        if task.track not in backlog.tracks:
            errors.append(f"{task.id}: track '{task.track}' 미정의")
        if task.stage not in backlog.stage_order:
            errors.append(f"{task.id}: stage '{task.stage}' 가 stage_order에 없음")
        for dep in task.depends_on:
            if dep not in backlog.tasks:
                errors.append(f"{task.id}: depends_on '{dep}' 미존재")
            elif backlog.stage_index(backlog.tasks[dep].stage) > backlog.stage_index(task.stage):
                errors.append(
                    f"{task.id}({task.stage}): 후행 스테이지 태스크 '{dep}'"
                    f"({backlog.tasks[dep].stage})에 의존 — 로드맵 순서 위반"
                )
        for gid in task.requires_gates:
            if gid not in backlog.gates:
                errors.append(f"{task.id}: requires_gates '{gid}' 미존재")
        if task.status == "in_progress" and task.session:
            sessions_in_progress.setdefault(task.session, []).append(task.id)

    for session, ids in sessions_in_progress.items():
        if len(ids) > 1:
            errors.append(f"세션 '{session}' 이 {len(ids)}개 태스크를 동시 claim: {ids} (1세션=1태스크)")

    cycle = detect_cycle(backlog)
    if cycle:
        errors.append(f"depends_on 순환 참조 검출: {cycle}")

    return errors
