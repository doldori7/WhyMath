"""[OPS-11·OPS-12] 테스트·하네스 디렉터리의 **lint/format 배선** 동결.

왜 이 테스트가 있는가
--------------------
OPS-03이 `infra-contracts` 잡으로 `tests/infra`의 *실행*을 배선했지만, **코드 품질 축은
여전히 무배선이었다** — backend 잡은 `../../tests/backend`만 lint하고 이 잡엔 ruff/black
스텝이 없었다. 실측(2026-07-27): 배선 직전 `black --check`가 `test_backup_script.py`
1건에서 실패하고 있었고, 아무도 알지 못했다.

같은 구멍이 `harness-integrity` 잡에도 있었다(OPS-12) — `tests/harness`·`scripts/harness`를
lint하는 잡이 하나도 없었고, 실측(2026-07-27) 배선 직전 ruff F541 2건(test_cli.py) +
black --check 17파일이 실패 상태였다. 하네스는 backlog 대장을 판정하는 코드라
"검사하는 자를 아무도 검사하지 않는" 구멍이 특히 아프다.

이것은 이 프로젝트에서 **반복되는 부류**다 — "장치는 있는데 일부만 배선됨"(CLAUDE.md
"검증 장치를 만들고 배선 확인 없이 완료 선언 금지"가 겨냥하는 형태). 새 lint 배선을
추가하면 `_WIRINGS`에 (잡, 대상 경로들) 한 줄을 추가해 같은 계약으로 동결하라.

**이 파일만으로는 부족하다** (OPS-13): 여기 표는 *등재된 것*의 품질만 본다 — 등재 자체를
빠뜨리면 못 잡는다. 누락 축은 `test_lint_coverage.py`가 소스에서 출발해 전수로 검사한다.
두 파일은 역할이 갈리므로 계약을 중복시키지 않는다(품질 ↔ 누락).

계약 ②는 OPS-14에서 **가정이 아니라 실측된 함정**임이 드러났다. 레포 루트에 pyproject.toml이
없어서, black에 경로를 하나라도 더 주면 프로젝트 루트 탐지가 레포 루트로 올라가 설정을 못 찾고
**기본값 88자로 조용히 강등**된다. 실측(2026-07-28): data-pipeline 잡의 `black --check .`에
`--line-length 100` 없이 `../../tests/data_pipeline`만 추가하면 `src/data-pipeline` 자신까지
88자로 재검사돼 **89파일이 FAIL**한다(그 전엔 77파일 clean). 이 계약이 그 회귀를 막는다.

OPS-15가 계약 ⑤를 더했다. `src/*` 밖은 **저장소 표준이 적용된 적이 없었다** — 레포 루트에
pyproject.toml이 없어 ruff가 파일마다 조상에서 설정을 찾다 실패하고 **기본값**(88자 ·
`select E4,E7,E9,F`)으로 검사해 왔다. 배선은 켜졌는데 *기준이 달랐던* 것이라, 계약 ①~④
(배선 유무·대상·`--check`)로는 구조적으로 잡히지 않는다. 그래서 설정 자체를 동결한다.

검증 계약
--------
① 각 잡에 ruff·black 스텝이 **둘 다** 있다
② black 스텝이 저장소 표준 `--line-length 100` + `--check`를 쓴다 (규칙이 갈리면 무의미)
③ 두 스텝이 선언된 대상 경로 **전부**를 검사한다 (다른 경로를 검사하는 위장 차단)
④ 파서가 위장하지 않는다 — 워크플로/잡을 못 찾으면 "위반 0 통과"가 아니라 **실패**
⑤ 레포 루트 lint 정본이 존재하고 `src/*` 두 pyproject와 **같은 규칙**을 선언한다
   (셋이 갈리면 같은 코드가 위치에 따라 다르게 판정돼 "표준"이 무의미해진다)
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

import pytest
import yaml

_REPO_ROOT = Path(__file__).resolve().parents[2]
_CI_PATH = _REPO_ROOT / ".github" / "workflows" / "ci.yml"

# (잡 이름, 그 잡이 lint해야 하는 대상 경로들) — 배선 추가 시 여기에 등재해 동결한다.
_WIRINGS: list[tuple[str, tuple[str, ...]]] = [
    ("infra-contracts", ("tests/infra", "infra", "conftest.py")),  # OPS-11 · OPS-13
    ("harness-integrity", ("scripts", "tests/harness")),  # OPS-12 · OPS-13(harness→scripts 확대)
    ("data-pipeline", ("../../tests/data_pipeline",)),  # OPS-14
]
_WIRING_IDS = [job for job, _ in _WIRINGS]


def _job_run_scripts(job_key: str) -> list[str]:
    """해당 잡의 모든 `run` 스크립트. 못 찾으면 실패(위장 차단)."""
    if not _CI_PATH.is_file():
        raise AssertionError(f"{_CI_PATH} 이(가) 없다 — lint 배선을 확인할 수 없다.")
    spec: Any = yaml.safe_load(_CI_PATH.read_text(encoding="utf-8"))
    jobs = (spec or {}).get("jobs") or {}
    if job_key not in jobs:
        raise AssertionError(
            f"ci.yml에 `{job_key}` 잡이 없다 — 잡을 개명했다면 이 테스트의 `_WIRINGS`도 "
            "함께 고쳐라(그러지 않으면 lint 배선이 조용히 사라진다)."
        )
    steps = (jobs[job_key] or {}).get("steps") or []
    scripts = [str(s.get("run", "")) for s in steps if isinstance(s, dict) and s.get("run")]
    if not scripts:
        raise AssertionError(f"`{job_key}` 잡에 `run` 스텝이 하나도 없다.")
    return scripts


def _step_invoking(tool: str, job_key: str) -> str:
    """해당 도구를 *검사 목적*으로 실행하는 스텝을 찾는다(설치 명령은 제외)."""
    for script in _job_run_scripts(job_key):
        if "pip install" in script:
            continue
        if f"-m {tool}" in script or script.strip().startswith(tool):
            return script
    return ""


@pytest.mark.parametrize(("job_key", "targets"), _WIRINGS, ids=_WIRING_IDS)
def test_ruff_step_exists(job_key: str, targets: tuple[str, ...]) -> None:
    """계약 ① — ruff 스텝이 없으면 대상 디렉터리의 정적 위반이 CI를 통과한다."""
    assert _step_invoking("ruff", job_key), (
        f"`{job_key}` 잡에 ruff 스텝이 없다 — {', '.join(targets)}는 어떤 잡도 lint하지 "
        "않게 된다 (backend 잡은 tests/backend만 본다)."
    )


@pytest.mark.parametrize(("job_key", "targets"), _WIRINGS, ids=_WIRING_IDS)
def test_black_step_exists(job_key: str, targets: tuple[str, ...]) -> None:
    """계약 ① — black 스텝이 없으면 포맷 드리프트가 조용히 쌓인다(실측 선례 18파일)."""
    assert _step_invoking("black", job_key), f"`{job_key}` 잡에 black 스텝이 없다."


@pytest.mark.parametrize(("job_key", "targets"), _WIRINGS, ids=_WIRING_IDS)
def test_black_uses_repo_standard_line_length(job_key: str, targets: tuple[str, ...]) -> None:
    """계약 ② — 다른 잡과 다른 규칙으로 검사하면 통과해도 의미가 없다."""
    script = _step_invoking("black", job_key)
    assert script, f"`{job_key}` black 스텝 부재(위 테스트 참조)"
    assert (
        "--line-length 100" in script
    ), f"`{job_key}` black 스텝이 저장소 표준 `--line-length 100`을 쓰지 않는다: {script.strip()!r}"
    assert (
        "--check" in script
    ), "black이 `--check` 없이 실행되면 CI에서 파일을 고쳐버린다(게이트 아님)."


@pytest.mark.parametrize(("job_key", "targets"), _WIRINGS, ids=_WIRING_IDS)
def test_both_steps_cover_declared_targets(job_key: str, targets: tuple[str, ...]) -> None:
    """계약 ③ — 선언된 대상 일부만(또는 다른 경로를) 검사하며 통과하는 위장을 차단한다."""
    for tool in ("ruff", "black"):
        script = _step_invoking(tool, job_key)
        assert script, f"`{job_key}` {tool} 스텝 부재"
        for target in targets:
            assert (
                target in script
            ), f"`{job_key}` {tool} 스텝이 `{target}`를 대상으로 하지 않는다: {script.strip()!r}"


def test_parser_fails_loudly_on_unknown_job() -> None:
    """계약 ④ — 잡을 못 찾으면 조용한 통과가 아니라 예외여야 한다."""
    with pytest.raises(AssertionError, match="잡이 없다"):
        _job_run_scripts("__nonexistent_job__")


# ── 계약 ⑤ — lint 설정 정본 동결 (OPS-15) ─────────────────────────────────────

# lint 설정을 선언하는 pyproject 전부. 루트가 `src/*` 밖을, 나머지는 각자 패키지를 덮는다.
_CONFIG_FILES = ("pyproject.toml", "src/backend/pyproject.toml", "src/data-pipeline/pyproject.toml")


def _lint_config(rel_path: str) -> dict[str, Any]:
    """pyproject에서 lint 설정을 읽는다. 못 읽으면 **실패**(위장 차단).

    stdlib `tomllib`만 쓴다 — 하네스·infra 계약 테스트에 새 의존성을 들이지 않는다.
    """
    path = _REPO_ROOT / rel_path
    if not path.is_file():
        raise AssertionError(
            f"{rel_path}: lint 설정 파일이 없다. 루트 정본이 사라지면 `src/*` 밖은 다시 "
            "ruff 기본값(88자·축소 룰셋)으로 조용히 강등된다 — OPS-15가 고친 바로 그 상태다."
        )
    try:
        spec = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise AssertionError(f"{rel_path}: TOML 파손 ({exc}) — 조용히 넘기지 않는다.") from exc
    tool = spec.get("tool") or {}
    ruff = tool.get("ruff") or {}
    black = tool.get("black") or {}
    return {
        "ruff_line_length": ruff.get("line-length"),
        "ruff_select": tuple((ruff.get("lint") or {}).get("select") or ()),
        "black_line_length": black.get("line-length"),
    }


def test_repo_root_lint_config_exists() -> None:
    """계약 ⑤ — 루트 정본이 존재하고 ruff·black을 **둘 다** 선언한다."""
    cfg = _lint_config("pyproject.toml")
    assert cfg["ruff_line_length"] is not None, "루트 pyproject에 [tool.ruff] line-length가 없다."
    assert cfg["black_line_length"] is not None, "루트 pyproject에 [tool.black] line-length가 없다."
    assert cfg[
        "ruff_select"
    ], "루트 pyproject에 [tool.ruff.lint] select가 없다 — 기본 룰셋으로 강등된다."


def test_all_lint_configs_declare_the_same_rules() -> None:
    """계약 ⑤ — 세 pyproject의 규칙이 갈리면 '표준'이라는 말이 무의미해진다.

    같은 코드가 어느 디렉터리에 있느냐에 따라 다르게 판정되면, 통과는 위치의 함수이지
    품질의 함수가 아니다. OPS-15 이전이 정확히 그 상태였다.
    """
    configs = {rel: _lint_config(rel) for rel in _CONFIG_FILES}
    for key in ("ruff_line_length", "black_line_length", "ruff_select"):
        values = {rel: cfg[key] for rel, cfg in configs.items()}
        assert (
            len(set(values.values())) == 1
        ), f"{key}가 pyproject마다 다르다 — 같은 코드가 위치에 따라 다르게 판정된다:\n" + "\n".join(
            f"  {rel}: {val}" for rel, val in values.items()
        )


def test_config_reader_fails_loudly_on_missing_file() -> None:
    """계약 ⑤ — 설정 파일 부재를 '위반 0'으로 넘기지 않는다."""
    with pytest.raises(AssertionError, match="lint 설정 파일이 없다"):
        _lint_config("__nonexistent__/pyproject.toml")
