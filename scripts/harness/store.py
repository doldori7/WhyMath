"""backlog/ 저장소 — 로드·저장·이벤트 로그·무결성 검증.

파일 배치 (전부 git 커밋 대상):
    backlog/tracks.yaml           트랙 정의 + stage_order
    backlog/gates.yaml            사람 게이트 대장
    backlog/tasks/<id>.yaml       태스크당 1파일 (병렬 세션 충돌 원천 차단)
    backlog/events/<actor>.ndjson append-only 상태변경 로그 — **세션(=브랜치)당 1샤드**
    backlog/events.ndjson         레거시 단일 대장 (읽기 전용 역사 — 신규 기록 없음)

이벤트 샤딩(HARN-46, 2026-08-31): 원래는 events.ndjson 한 파일에 모든 세션이
append했고 `.gitattributes merge=union`이 병렬 충돌을 흡수한다고 믿었다. 그러나
**GitHub의 mergeability 판정은 저장소 merge driver를 적용하지 않아서**, main에
어떤 PR이 착지하든 이 파일을 함께 만진 열린 PR은 전부 dirty(충돌)가 됐다 —
PR #931이 CI green을 4회 확보하고도 머지가 반복 지연된 실측 사고. 로컬 병합은
매번 충돌 0이었으므로 문제는 데이터가 아니라 **배치**다. 대책은 tasks/의
태스크당-1파일 선례와 동형: 세션당 1샤드로 나눠 두 브랜치가 같은 파일을 동시에
append하는 상황 자체를 없앤다(충돌을 '해소 가능'이 아니라 '발생 불가능'으로).

읽기는 PyYAML(사람 손 편집 허용을 위해), 쓰기는 자체 직렬화기
(키 순서·인용 규칙 고정 → diff 안정·결정적 출력).
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
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
    here = start or Path(__file__).resolve().parent
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
    lines = [
        "# 사람 게이트 대장 — clear는 evidence 필수 (backlog.py gates clear <id> --evidence ...)",
        "gates:",
    ]
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
            cwd=root,
            capture_output=True,
            # HARN-19: 로케일(cp949) 디코드 금지 — git 출력은 UTF-8이 정본이다.
            encoding="utf-8",
            errors="replace",
            timeout=10,
        )
        return (out.stdout or "").strip() or "unknown"
    except Exception as exc:  # pragma: no cover - 환경 의존
        # 침묵 실패 금지 — 예외 타입명을 남긴다 (CLAUDE.md AI·신뢰).
        # 브랜치 미상은 claim·세션 판정을 통째로 흐리므로 조용히 넘기면 안 된다.
        print(
            f"⚠ 현재 브랜치 조회 실패({type(exc).__name__}) — 'unknown'으로 진행", file=sys.stderr
        )
        return "unknown"


def _event_shard_name(actor: str) -> str:
    """actor(브랜치명) → 샤드 파일명 — 결정적·경로 탈출 불가.

    파일명 안전 문자([A-Za-z0-9._-]) 외 전부 '_' 치환: 브랜치명의 '/'가 하위
    디렉터리로 해석되거나 '..'이 events/ 밖을 가리키는 것을 원천 차단한다.
    치환 후 선두 '.'도 벗긴다('..'·숨김 파일 방지). 서로 다른 브랜치가 같은
    이름으로 붕괴하는 경우(예: 'a/b'와 'a_b')는 이론상 가능하지만, 그 한 쌍만
    종전(단일 파일) 상태로 퇴화할 뿐이고 union이 여전히 로컬 병합을 흡수한다.
    상한 120자: 파일시스템 255 한계에 여유를 둔다.
    """
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", actor).lstrip(".") or "unknown"
    return safe[:120] + ".ndjson"


def event_paths(root: Path) -> list[Path]:
    """이벤트 대장 파일 전부 — 레거시 단일 대장 + 세션 샤드(이름 정렬).

    소비자(policy 리포트 등)는 반드시 이 목록을 순회해야 한다. 레거시 파일만
    읽으면 샤딩 이후 기록이 통째로 안 보이고, 샤드만 읽으면 과거 역사가 사라진다
    — 어느 쪽도 무손실이 아니다.
    """
    paths: list[Path] = []
    legacy = backlog_dir(root) / "events.ndjson"
    if legacy.exists():
        paths.append(legacy)
    shard_dir = backlog_dir(root) / "events"
    if shard_dir.is_dir():
        paths.extend(sorted(shard_dir.glob("*.ndjson")))
    return paths


def append_event(root: Path, action: str, subject_id: str, **extra: object) -> None:
    """append-only 이벤트 로그 — **세션(=actor 브랜치)당 1샤드**에 기록 (HARN-46).

    레거시 `events.ndjson`에는 더 이상 쓰지 않는다(역사 보존·읽기 전용). 이유는
    모듈 docstring 참조 — GitHub mergeability가 merge=union을 적용하지 않아
    공용 단일 파일이 main 착지마다 열린 PR을 dirty로 만들었다(PR #931 실측).
    """
    actor = current_branch(root)
    path = backlog_dir(root) / "events" / _event_shard_name(actor)
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "ts": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "actor": actor,
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
            errors.append(
                f"세션 '{session}' 이 {len(ids)}개 태스크를 동시 claim: {ids} (1세션=1태스크)"
            )

    cycle = detect_cycle(backlog)
    if cycle:
        errors.append(f"depends_on 순환 참조 검출: {cycle}")

    errors.extend(_id_number_collisions(backlog.tasks.keys()))

    return errors


# ── 태스크 ID 번호 충돌 (HARN-10) ────────────────────────────────────────────
#
# ID는 `<PREFIX>-<번호>-<슬러그>` 규약이다. full-ID는 슬러그 덕에 유일해도 **번호가
# 겹치면** 사람·문서·커밋의 "OPS-15" 참조가 어느 태스크인지 결정 불가가 된다(CLI는
# full-ID를 받으므로 기계는 멀쩡 — 그래서 조용히 자란다).
#
# 실측 2회(2026-07-29): ARCH-13(둘 다 done·머지 완료), OPS-15(병렬 인플라이트). 두 사고
# 모두 **병렬 세션이 서로의 브랜치를 못 봐서** 났다 — 로컬 백로그만 보는 검사로는 애초에
# 예방할 수 없다. 그래서 예방의 본체는 `add` 시점의 *원격 claim 대장* 조회이고(backlog.py),
# 이 함수는 머지 후 잔존을 막는 2선 방어다.
_GRANDFATHERED_ID_NUMBERS: dict[str, str] = {
    # 이미 main에 머지된 과거 충돌 — 개명하면 MEMORY·커밋·PR의 기존 참조가 끊긴다.
    "ARCH-13": (
        "기존 충돌(2026-07-18 visualization-harness-tracking · 07-25 "
        "concept-atom-granularity-merge) — 둘 다 done·머지 완료. 개명 시 기존 참조 파손."
    ),
    # HARN-10 착수 시점에 두 브랜치에서 인플라이트 — 이 가드가 먼저 머지돼도
    # 그 브랜치들의 머지를 깨지 않게 미리 등재한다(타 세션 볼모 금지).
    "OPS-15": (
        "기존 충돌(2026-07-29 repo-root-lint-config · wh1-caplog-order-flake) — "
        "HARN-10 착수 시점에 타 세션 2곳에서 인플라이트였다. 사후 개명은 타 세션 볼모."
    ),
}

# 접두는 영숫자 혼합을 허용한다 — 이 저장소 ID의 다수파가 스테이지형(`S2-04`·`S4-07`)이라
# `[A-Za-z]+`로 잡으면 정작 가장 많은 축을 통째로 못 본다(HARN-10 구현 중 실측).
#
# 캡처 그룹 뒤는 `(?:-|$)` — 슬러그가 이어지거나(`-`) 문자열이 거기서 끝나야(`$`) 매치한다.
# `models.TASK_ID_RE`(`^[A-Z][A-Z0-9]{0,7}-\d{2}(-[a-z0-9]+(-[a-z0-9]+)*)?$`)는 슬러그가
# **옵션**이라 `HARN-20`처럼 슬러그 없는 ID도 유효한데, 구 정규식(`...-\d+)-`)은 캡처 그룹
# 뒤에 반드시 `-`가 와야 매치해서 슬러그 없는 ID를 전부 놓쳤다(HARN-21 결함① — 그 결과
# `_taken_id_numbers`·`_id_number_collisions`가 슬러그 없는 ID의 번호를 점유 목록에서
# 누락시켜 1선(add)·2선(validate) 번호 충돌 검사를 양쪽 다 우회할 수 있었다).
_ID_NUMBER_RE = re.compile(r"^([A-Za-z][A-Za-z0-9]*-\d+)(?:-|$)")


def id_number_of(task_id: str) -> str | None:
    """`<PREFIX>-<번호>` 부분. 규약을 벗어난 ID면 None(검사 대상 아님)."""
    match = _ID_NUMBER_RE.match(task_id)
    return match.group(1) if match else None


def _id_number_collisions(task_ids: object) -> list[str]:
    """같은 `<PREFIX>-<번호>`를 쓰는 태스크가 2건 이상이면 위반(grandfather 제외)."""
    groups: dict[str, list[str]] = {}
    for task_id in task_ids:  # type: ignore[union-attr]
        number = id_number_of(str(task_id))
        if number:
            groups.setdefault(number, []).append(str(task_id))
    errors: list[str] = []
    for number, ids in sorted(groups.items()):
        if len(ids) < 2 or number in _GRANDFATHERED_ID_NUMBERS:
            continue
        errors.append(
            f"태스크 ID 번호 충돌 '{number}': {sorted(ids)} — 사람·문서·커밋의 "
            f"'{number}' 참조가 결정 불가가 된다. 하나를 다음 빈 번호로 개명하거나, "
            "이미 머지돼 개명이 불가능하면 store._GRANDFATHERED_ID_NUMBERS에 사유와 함께 등재하라."
        )
    return errors
