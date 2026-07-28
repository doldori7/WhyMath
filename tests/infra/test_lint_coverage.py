"""[OPS-13] 파이썬 소스의 **lint 커버리지** 동결 — "어떤 lint도 받지 않는 소스"를 기계가 찾는다.

왜 이 테스트가 있는가
--------------------
이 저장소는 **"장치는 있는데 일부만 배선됨"** 사고가 여섯 번 반복됐다(`tests/infra` 미실행
→ OPS-03 / required check 통째 미강제 → OPS-08 / seed 훅이 backend rootdir 미로드 →
OPS-09 / `tests/infra` lint 미배선 → OPS-11 / `tests/harness`·`scripts/harness` lint
미배선 → OPS-12). CLAUDE.md에 규칙까지 등재했지만 **규칙을 쓴 뒤에도 계속 나왔다** —
기본값이 "안 걸림"이기 때문이다. 새 디렉터리는 조용히 무보호로 태어난다.

OPS-11·OPS-12는 *발견된 한 건씩*을 상환했고, `test_infra_lint_wiring.py`는 그 배선의
**품질**을 동결한다(`--check` 유무·`--line-length 100`·선언 대상 커버). 그러나 그 표는
**등재된 것만** 검사한다 — 등재 자체를 빠뜨리면 여전히 못 잡는 것이 남은 구멍이었다.

이 파일이 그 구멍을 닫는다. **소스에서 출발**해 "이 파일을 검사하는 lint 실행이 하나라도
있는가"를 전수로 묻는다. 등재를 잊어도 걸린다 — 그것이 일반화의 존재 이유다.
OPS-10(`test_test_suite_wiring.py`)이 *실행* 배선에 대해 한 일의 lint 판이며, 파서
헬퍼를 그 파일에서 그대로 **재사용**한다(파서를 복제하면 두 사본이 서로 어긋난다).

착수 실측이 이미 4건을 더 찾아냈다 — 아무도 모르고 있었다 (2026-07-28):
  - `scripts/` 비-harness 7파일 (`diagnose_atom_orphans.py` black 위반) — 이 PR에서 배선
  - `infra/phaiakes9/benchmark` 2파일 (`tests/infra`가 *테스트하는* 소스인데 무배선) — 배선
  - 레포 루트 `conftest.py` (OPS-09의 seed 훅이 사는 파일) — 배선
  - `tests/data_pipeline` 75파일 (black 28파일 위반) — 규모가 커 OPS-14로 분리

두 파일의 역할 분담 (중복 계약 금지)
-----------------------------------
- `test_infra_lint_wiring.py` (OPS-11·12) = 배선된 것의 **품질** — 이 파일은 재검사하지 않는다
- `test_lint_coverage.py` (이 파일)      = **누락** — 무엇이 아예 빠졌는가

실행축과의 핵심 차이: **lint 도구는 대상 디렉터리를 재귀로 훑는다.** 그래서 `scripts`를
지정하면 `scripts/harness/**`까지 덮인다(pytest 인자처럼 정확히 지정할 필요가 없다).
커버 판정이 "조상-또는-자기"인 이유다.

검증 계약 (각 항목은 변별력이 실측된 것만)
----------------------------------------
① 모든 파이썬 소스 파일이 어떤 CI lint 실행의 대상 범위 안에 있다 — 아니면 실패
② 의도적 제외는 **사유 필수** 허용목록 — 빈 사유는 무효(별도 테스트로 이중 신호)
③ 허용목록 stale 검출 — 이미 커버됐거나 경로가 사라졌으면 실패(영구화 방지)
④ 파서가 위장하지 않는다 — 워크플로 부재·YAML 파손·lint 실행 0건은 "위반 0 통과"가
   아니라 **예외**. 옵션값(`--line-length 100`의 `100`)을 경로로 오인하지 않는다
   (오인하면 커버리지가 거짓으로 부풀어 실제 공백이 감춰진다)
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

import pytest
import yaml

# 파서 헬퍼는 OPS-10에서 재사용한다 — 복제하면 두 사본이 서로 어긋난다.
from .test_test_suite_wiring import (
    _SKIP_DIRS,
    _default_working_directory,
    _is_within,
    _logical_lines,
    _rel,
    _simple_commands,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_WORKFLOW_DIR = _REPO_ROOT / ".github" / "workflows"

# ── 의도적 제외 (사유 필수) ────────────────────────────────────────────────────
#
# 여기 등재하는 순간 **그 경로의 lint 보호는 꺼진 상태**다. 검사는 공백을 *드러낼 뿐*
# 고치지 않는다. 부채(언젠가 켜야 함)면 사유에 **상환 태스크 ID를 박아** 영구화를 막는다.
_INTENTIONALLY_UNLINTED: dict[str, str] = {
    "docs": (
        "영구 — docs/ 하위 .py는 문서에 첨부된 **초안 스냅샷**이다"
        "(`260724_v2_migration_pedagogy_dsl.alembic_draft.py` — 실행되지 않는 설계 기록). "
        "재포맷은 소스를 고치는 게 아니라 과거 문서의 내용을 바꾼다."
    ),
}

# 컨테이너 디렉터리 — 한 단계 내려가야 의미 있는 단위가 나온다(`tests` 자체는 단위가 아니다).
_CONTAINER_DIRS = frozenset({"tests", "src"})

# lint 도구로 인정하는 실행 파일 이름.
_LINT_TOOLS = frozenset({"ruff", "black"})
_PYTHON_NAMES = frozenset({"python", "python3", "python3.12"})
# `ruff`는 서브커맨드를 요구한다 — 검사 목적인 것만 배선으로 센다.
_RUFF_CHECKING_SUBCOMMANDS = frozenset({"check", "format"})

# 값을 하나 소비하는 옵션.
#
# **오분류의 방향이 중요하다**: 옵션값을 경로로 세면 커버리지가 *거짓으로 부풀어* 실제
# 공백이 감춰진다(위험). 반대로 진짜 경로를 옵션값으로 먹으면 그 경로가 미배선으로
# 검출된다(시끄럽지만 안전). 그래서 이 집합은 **넉넉하게** 잡는다.
_VALUE_OPTIONS = frozenset(
    {
        "-l",
        "--line-length",
        "-t",
        "--target-version",
        "-c",
        "--config",
        "--include",
        "--exclude",
        "--extend-exclude",
        "--force-exclude",
        "-W",
        "--workers",
        "--stdin-filename",
        "--required-version",
        "--select",
        "--extend-select",
        "--ignore",
        "--extend-ignore",
        "--per-file-ignores",
        "--fixable",
        "--unfixable",
        "--output-format",
        "--cache-dir",
    }
)


@dataclass(frozen=True)
class LintRun:
    """CI에서 실제로 일어나는 lint 실행 하나 — **배선의 유일한 단위**."""

    origin: str
    tool: str
    targets: tuple[Path, ...]

    def covers(self, path: Path) -> bool:
        """`path`가 이 실행의 검사 범위 안인가.

        lint 도구는 디렉터리를 **재귀**로 훑으므로 대상이 조상이기만 하면 덮인다.
        """
        return any(_is_within(path, target) for target in self.targets)


# ── 소스 열거 ──────────────────────────────────────────────────────────────────


def _python_files(root: Path) -> list[Path]:
    """레포의 모든 파이썬 소스 파일. 캐시·가상환경·숨김 디렉터리는 제외."""
    found: list[Path] = []
    stack = [root]
    while stack:
        current = stack.pop()
        for child in sorted(current.iterdir()):
            name = child.name
            if name in _SKIP_DIRS or (name.startswith(".") and child.is_dir()):
                continue
            if child.is_dir():
                stack.append(child)
            elif child.suffix == ".py":
                found.append(child)
    return found


def _unit_of(path: Path) -> str:
    """파일이 속한 **보고·허용목록 단위**(레포 상대).

    `tests/*`·`src/*`는 한 단계 더 내려간 것이 단위이고(`tests/backend`), 그 외 최상위
    디렉터리는 그 자체가 단위다(`scripts`·`infra`). 루트 직속 파일은 `.`.
    """
    parts = PurePosixPath(_rel(path, _REPO_ROOT)).parts
    if len(parts) == 1:
        return "."
    if parts[0] in _CONTAINER_DIRS and len(parts) > 2:
        return f"{parts[0]}/{parts[1]}"
    return parts[0]


# ── lint 실행 파싱 ─────────────────────────────────────────────────────────────


def _lint_targets(command: list[str]) -> list[str] | None:
    """단순 명령이 lint 실행이면 그 **위치 인자**(경로 토큰)를, 아니면 None.

    `pip install ruff black`처럼 도구가 *인자로* 등장하는 줄을 실행으로 오인하지 않는 것이
    핵심이다(실제로 ci.yml에 그런 줄이 있다).
    """
    if not command:
        return None
    head = PurePosixPath(command[0]).name
    if head in _PYTHON_NAMES:
        if len(command) < 3 or command[1] != "-m" or command[2] not in _LINT_TOOLS:
            return None
        tool, rest = command[2], command[3:]
    elif head in _LINT_TOOLS:
        tool, rest = head, command[1:]
    else:
        return None

    if tool == "ruff":
        if not rest or rest[0] not in _RUFF_CHECKING_SUBCOMMANDS:
            return None  # `ruff clean`·`ruff version` 등은 검사가 아니다
        rest = rest[1:]

    paths: list[str] = []
    index = 0
    while index < len(rest):
        token = rest[index]
        if token.startswith("-") and token != "-":
            if "=" not in token and token in _VALUE_OPTIONS:
                index += 2  # 옵션과 그 값을 함께 건너뛴다
                continue
            index += 1
            continue
        if token != "-":  # `-` = stdin, 경로가 아니다
            paths.append(token)
        index += 1
    return paths


def _collect_lint_runs() -> list[LintRun]:
    """모든 워크플로에서 lint 실행을 수집한다.

    워크플로를 못 읽는 상황(디렉터리 부재·파일 0건·YAML 파손·lint 실행 0건)은 전부
    **예외**다 — 파서 무력화가 곧 "위반 0 통과"가 되면 안 된다(계약 ④).
    """
    if not _WORKFLOW_DIR.is_dir():
        raise AssertionError(
            f"{_WORKFLOW_DIR}: 워크플로 디렉터리가 없다 — lint 배선을 읽을 수 없다."
        )
    workflow_paths = sorted(p for p in _WORKFLOW_DIR.iterdir() if p.suffix in {".yml", ".yaml"})
    if not workflow_paths:
        raise AssertionError(f"{_WORKFLOW_DIR}: 워크플로 파일이 하나도 없다 — 배선 파싱 불가.")

    runs: list[LintRun] = []
    for workflow_path in workflow_paths:
        try:
            spec: Any = yaml.safe_load(workflow_path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            raise AssertionError(
                f"{_rel(workflow_path, _REPO_ROOT)}: YAML 파손 ({exc}) — "
                "파서가 조용히 배선을 흘리지 않도록 실패시킨다."
            ) from exc
        jobs = (spec or {}).get("jobs") or {}
        for job_name, job in jobs.items():
            if not isinstance(job, dict):
                continue
            job_workdir = _default_working_directory(job)
            for step in job.get("steps") or []:
                if not isinstance(step, dict) or not step.get("run"):
                    continue
                workdir_value = step.get("working-directory") or job_workdir or "."
                workdir = (_REPO_ROOT / str(workdir_value)).resolve()
                origin = f"{_rel(workflow_path, _REPO_ROOT)} :: {job_name}"
                for line in _logical_lines(str(step["run"])):
                    if not any(tool in line for tool in _LINT_TOOLS):
                        continue
                    for command in _simple_commands(line, origin, subject="lint"):
                        tokens = _lint_targets(command)
                        if not tokens:
                            continue
                        targets: list[Path] = []
                        for token in tokens:
                            resolved = (workdir / token).resolve()
                            # 존재하지 않거나 레포 밖인 토큰은 버린다 — 오타난 경로를
                            # 배선으로 세지 않기 위해서다(버리는 쪽이 안전한 실패).
                            if resolved.exists() and _is_within(resolved, _REPO_ROOT):
                                targets.append(resolved)
                        if targets:
                            runs.append(
                                LintRun(origin=origin, tool=command[0], targets=tuple(targets))
                            )
    if not runs:
        raise AssertionError(
            "워크플로에서 lint 실행을 하나도 찾지 못했다 — 파서가 망가졌거나 배선이 통째로 "
            "사라졌다. 어느 쪽이든 '위반 0 통과'로 넘기면 안 된다."
        )
    return runs


def _uncovered_units() -> dict[str, list[str]]:
    """어떤 lint 실행도 덮지 않는 파일들을 단위별로 묶어 돌려준다."""
    runs = _collect_lint_runs()
    uncovered: dict[str, list[str]] = {}
    for path in _python_files(_REPO_ROOT):
        if any(run.covers(path) for run in runs):
            continue
        uncovered.setdefault(_unit_of(path), []).append(_rel(path, _REPO_ROOT))
    return uncovered


# ── 계약 ①: 전수 커버리지 ──────────────────────────────────────────────────────


def test_every_python_source_is_linted() -> None:
    """계약 ① — 어떤 lint도 받지 않는 소스가 남아 있으면 실패한다.

    이 테스트가 일반화의 본체다. 새 디렉터리를 만들면 **등재를 잊어도** 여기서 걸린다.
    """
    offenders = {
        unit: files
        for unit, files in _uncovered_units().items()
        if unit not in _INTENTIONALLY_UNLINTED
    }
    if not offenders:
        return
    report = "\n".join(
        f"  - {unit}  ({len(files)}개 파일, 예: {files[0]})"
        for unit, files in sorted(offenders.items())
    )
    raise AssertionError(
        "어떤 CI lint 실행도 덮지 않는 파이썬 소스가 있다 — 그 코드의 정적 위반·포맷 "
        f"드리프트는 아무에게도 보이지 않는다:\n{report}\n\n"
        "해결: ①ci.yml의 lint 스텝 대상에 추가하고 `test_infra_lint_wiring.py`의 "
        "`_WIRINGS`에 등재하거나 ②의도적 제외라면 `_INTENTIONALLY_UNLINTED`에 "
        "**사유와 상환 태스크 ID**를 함께 등재하라."
    )


# ── 계약 ②③: 허용목록 위생 ────────────────────────────────────────────────────


@pytest.mark.parametrize("unit", sorted(_INTENTIONALLY_UNLINTED))
def test_allowlist_entry_states_a_reason(unit: str) -> None:
    """계약 ② — 빈 사유는 무효. 사유 없는 제외는 '왜 껐는지 모르는 보호 구멍'이 된다."""
    reason = _INTENTIONALLY_UNLINTED[unit]
    assert reason and reason.strip(), (
        f"`{unit}`가 사유 없이 lint에서 제외됐다 — 왜 껐는지 모르면 언제 켤지도 알 수 없다. "
        "부채면 상환 태스크 ID를, 영구 제외면 그 근거를 적어라."
    )


@pytest.mark.parametrize("unit", sorted(_INTENTIONALLY_UNLINTED))
def test_allowlist_entry_is_still_needed(unit: str) -> None:
    """계약 ③ — 이미 커버됐거나 사라진 경로가 목록에 남으면 실패(영구화 방지).

    상환(OPS-14 등)이 끝나면 이 테스트가 목록에서 지우기를 **강제한다**.
    """
    target = _REPO_ROOT / unit
    assert target.exists(), (
        f"`{unit}`가 허용목록에 있으나 경로가 없다 — 지워졌거나 이름이 바뀌었다. "
        "목록에서 제거하라(stale 항목은 다음 사람에게 거짓 지도를 준다)."
    )
    assert unit in _uncovered_units(), (
        f"`{unit}`는 이제 CI lint가 덮고 있다 — 허용목록에서 제거하라. "
        "남겨두면 '여긴 무보호'라는 거짓 신호가 영구화된다."
    )


# ── 계약 ④: 파서 위장 차단 ─────────────────────────────────────────────────────


def test_option_values_are_not_mistaken_for_paths() -> None:
    """계약 ④ — `--line-length 100`의 `100`을 경로로 세면 커버리지가 거짓으로 부푼다.

    이 저장소의 모든 black 스텝이 정확히 그 형태라, 오인하면 실제 공백이 통째로 감춰진다.
    """
    assert _lint_targets(["black", "--check", "--line-length", "100", "tests/infra"]) == [
        "tests/infra"
    ]
    assert _lint_targets(["python3", "-m", "ruff", "check", "scripts", "tests/harness"]) == [
        "scripts",
        "tests/harness",
    ]
    # 등호 형태는 값을 따로 소비하지 않는다
    assert _lint_targets(["black", "--line-length=100", "src"]) == ["src"]


def test_installer_lines_are_not_counted_as_lint_runs() -> None:
    """계약 ④ — `pip install ruff black`을 실행으로 세면 '전부 커버'로 위장된다."""
    assert _lint_targets(["pip", "install", "ruff", "black"]) is None
    assert _lint_targets(["python3", "-m", "pip", "install", "ruff"]) is None
    assert _lint_targets(["ruff", "clean"]) is None  # 검사 서브커맨드가 아니다


def test_parser_fails_loudly_when_no_lint_run_is_found(monkeypatch: pytest.MonkeyPatch) -> None:
    """계약 ④ — 배선을 하나도 못 찾으면 조용한 통과가 아니라 예외여야 한다."""
    monkeypatch.setattr(
        f"{__name__}._lint_targets", lambda command: None, raising=True  # 모든 실행을 못 본 척
    )
    with pytest.raises(AssertionError, match="lint 실행을 하나도 찾지 못했다"):
        _collect_lint_runs()


def test_known_lint_jobs_are_discovered() -> None:
    """파서가 실제 ci.yml에서 기대 잡들을 읽어내는지 — 양성 대조.

    이게 없으면 위 계약들이 '아무것도 못 읽어서' 통과하는 상태와 구별되지 않는다.
    """
    origins = {run.origin.split(" :: ")[-1] for run in _collect_lint_runs()}
    for job in ("backend", "data-pipeline", "infra-contracts", "harness-integrity"):
        assert job in origins, f"ci.yml의 `{job}` 잡에서 lint 실행을 읽지 못했다 — 파서 회귀."
