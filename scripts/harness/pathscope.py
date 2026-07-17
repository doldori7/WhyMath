"""파일 범위 겹침 판정 — 태스크 paths(glob) 간 교집합의 보수적 근사.

정확한 glob∩glob 판정은 비자명하므로 2단 보수 근사를 쓴다
(둘 중 하나라도 걸리면 "겹칠 수 있음" — 놓치는 쪽보다 과탐이 안전):
    1단: 실파일 교집합 — 두 태스크의 glob을 git ls-files 결과에 전개해 교집합.
         정밀하지만 아직 커밋되지 않은 신규 파일은 못 본다.
    2단: 정적 프리픽스 포함 — 한 패턴의 와일드카드 앞 경로 프리픽스가 다른 패턴의
         프리픽스를 포함하면 겹침 가능 판정. 신규 파일 케이스를 보수적으로 커버.

fnmatch를 쓰지 않는 이유: '**' 의미론이 틀림(경로 구분자를 무시) — 자체 번역기가
결정적이고 테스트 가능하다.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

# 와일드카드 문자 — 이 중 하나라도 포함하면 패턴, 없으면 리터럴 경로
_WILDCARD_RE = re.compile(r"[*?\[]")


def _is_dirlike(pattern: str) -> bool:
    """와일드카드 없는 패턴이 디렉토리를 가리키는가 (끝 '/' 또는 확장자 없음 휴리스틱 아님 —
    끝 '/'만 신뢰; 그 외 리터럴은 파일로 취급하되 프리픽스 판정이 커버)."""
    return pattern.endswith("/")


def normalize(pattern: str) -> str:
    """패턴 정규화 — 디렉토리성 패턴('p/' 또는 와일드카드 없는 기존 디렉토리)을 'p/**'로."""
    pattern = pattern.strip().lstrip("./")
    if _is_dirlike(pattern):
        return pattern + "**"
    return pattern


def glob_to_regex(pattern: str) -> re.Pattern[str]:
    """glob 패턴 → 정규식. '**/'→'(.*/)?', '**'→'.*', '*'→'[^/]*', '?'→'[^/]'."""
    pattern = normalize(pattern)
    out: list[str] = []
    i = 0
    while i < len(pattern):
        ch = pattern[i]
        if ch == "*":
            if pattern[i:i + 3] == "**/":
                out.append("(.*/)?")
                i += 3
                continue
            if pattern[i:i + 2] == "**":
                out.append(".*")
                i += 2
                continue
            out.append("[^/]*")
            i += 1
            continue
        if ch == "?":
            out.append("[^/]")
            i += 1
            continue
        out.append(re.escape(ch))
        i += 1
    return re.compile("^" + "".join(out) + "$")


def static_prefix(pattern: str) -> str:
    """첫 와일드카드 전까지의 디렉토리 경로 프리픽스 (마지막 '/'까지 자름)."""
    pattern = normalize(pattern)
    match = _WILDCARD_RE.search(pattern)
    literal = pattern if match is None else pattern[: match.start()]
    if "/" not in literal:
        return ""
    return literal[: literal.rfind("/") + 1]


def repo_files(root: Path) -> list[str]:
    """git ls-files 결과 (호출당 1회 — 인자 주입으로 캐시·테스트 용이)."""
    try:
        out = subprocess.run(
            ["git", "ls-files"], cwd=root,
            capture_output=True, text=True, timeout=15,
        )
        return out.stdout.splitlines()
    except Exception:  # pragma: no cover - 환경 의존
        return []


def expand(globs: list[str], files: list[str]) -> set[str]:
    """glob 목록을 실파일 목록에 전개."""
    matched: set[str] = set()
    regexes = [glob_to_regex(g) for g in globs]
    for f in files:
        if any(rx.match(f) for rx in regexes):
            matched.add(f)
    return matched


def path_in_scope(path: str, globs: list[str]) -> bool:
    """단일 파일이 패턴 범위 안인가 — 훅용 O(패턴 수), ls-files 불필요."""
    path = path.lstrip("./")
    return any(glob_to_regex(g).match(path) for g in globs)


@dataclass
class Overlap:
    """두 태스크 paths 간 겹침 판정 결과."""

    task_a: str
    task_b: str
    files: list[str] = field(default_factory=list)   # 실파일 교집합 샘플 (최대 5)
    prefix_hit: str | None = None                     # 프리픽스 포함 판정 사유 (신규 파일 대비)

    def describe(self) -> str:
        parts: list[str] = []
        if self.files:
            parts.append(f"실파일 교집합 {len(self.files)}건 예: {', '.join(self.files[:3])}")
        if self.prefix_hit:
            parts.append(f"프리픽스 포함: {self.prefix_hit}")
        return " · ".join(parts) or "겹침 근거 불명"


def _prefix_contains(a: str, b: str) -> bool:
    """프리픽스 a가 b를 경로 단위로 포함하는가 (빈 프리픽스 = 레포 루트 = 전부 포함)."""
    return b.startswith(a)


def overlap(task_a: str, globs_a: list[str], task_b: str, globs_b: list[str],
            files: list[str]) -> Overlap | None:
    """겹침 가능성 판정 — None이면 안전, Overlap이면 겹칠 수 있음."""
    if not globs_a or not globs_b:
        return None  # 한쪽이라도 paths 미선언이면 판정 불가 (강제는 정책이 결정)

    # 1단: 실파일 교집합
    common = sorted(expand(globs_a, files) & expand(globs_b, files))

    # 2단: 정적 프리픽스 포함 (와일드카드 패턴 간 — 신규 파일 대비)
    prefix_hit: str | None = None
    for ga in globs_a:
        pa = static_prefix(ga)
        for gb in globs_b:
            pb = static_prefix(gb)
            # 와일드카드 패턴끼리만 — 리터럴 파일 대 리터럴 파일은 1단이 정확 판정
            wild_a = _WILDCARD_RE.search(normalize(ga)) is not None
            wild_b = _WILDCARD_RE.search(normalize(gb)) is not None
            if not (wild_a or wild_b):
                continue
            if wild_a and _prefix_contains(pa, pb):
                prefix_hit = f"{ga} ⊇ {gb}"
                break
            if wild_b and _prefix_contains(pb, pa):
                prefix_hit = f"{gb} ⊇ {ga}"
                break
        if prefix_hit:
            break

    if not common and not prefix_hit:
        return None
    return Overlap(task_a=task_a, task_b=task_b, files=common[:5], prefix_hit=prefix_hit)
