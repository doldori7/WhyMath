"""[OPS-11] `tests/infra`의 **lint/format 배선** 동결.

왜 이 테스트가 있는가
--------------------
OPS-03이 `infra-contracts` 잡으로 `tests/infra`의 *실행*을 배선했지만, **코드 품질 축은
여전히 무배선이었다** — backend 잡은 `../../tests/backend`만 lint하고 이 잡엔 ruff/black
스텝이 없었다. 실측(2026-07-27): 배선 직전 `black --check`가 `test_backup_script.py`
1건에서 실패하고 있었고, 아무도 알지 못했다.

이것은 이 프로젝트에서 **반복되는 부류**다 — "장치는 있는데 일부만 배선됨"(CLAUDE.md
"검증 장치를 만들고 배선 확인 없이 완료 선언 금지"가 겨냥하는 형태). `tests/infra`는
운영 자산의 계약을 동결하는 디렉터리라, 그 자신의 품질이 검사되지 않는 상태는
"검사하는 자를 아무도 검사하지 않는" 구멍이다.

검증 계약
--------
① `infra-contracts` 잡에 ruff·black 스텝이 **둘 다** 있다
② black 스텝이 저장소 표준 `--line-length 100`을 쓴다 (다른 잡과 규칙이 갈리면 무의미)
③ 두 스텝이 `tests/infra`를 대상으로 한다 (다른 경로를 검사하는 위장 차단)
④ 파서가 위장하지 않는다 — 워크플로/잡을 못 찾으면 "위반 0 통과"가 아니라 **실패**
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

_REPO_ROOT = Path(__file__).resolve().parents[2]
_CI_PATH = _REPO_ROOT / ".github" / "workflows" / "ci.yml"
_JOB_KEY = "infra-contracts"
_TARGET = "tests/infra"


def _job_run_scripts() -> list[str]:
    """`infra-contracts` 잡의 모든 `run` 스크립트. 못 찾으면 실패(위장 차단)."""
    if not _CI_PATH.is_file():
        raise AssertionError(f"{_CI_PATH} 이(가) 없다 — lint 배선을 확인할 수 없다.")
    spec: Any = yaml.safe_load(_CI_PATH.read_text(encoding="utf-8"))
    jobs = (spec or {}).get("jobs") or {}
    if _JOB_KEY not in jobs:
        raise AssertionError(
            f"ci.yml에 `{_JOB_KEY}` 잡이 없다 — 잡을 개명했다면 이 테스트의 `_JOB_KEY`도 "
            "함께 고쳐라(그러지 않으면 lint 배선이 조용히 사라진다)."
        )
    steps = (jobs[_JOB_KEY] or {}).get("steps") or []
    scripts = [str(s.get("run", "")) for s in steps if isinstance(s, dict) and s.get("run")]
    if not scripts:
        raise AssertionError(f"`{_JOB_KEY}` 잡에 `run` 스텝이 하나도 없다.")
    return scripts


def _step_invoking(tool: str) -> str:
    """해당 도구를 *검사 목적*으로 실행하는 스텝을 찾는다(설치 명령은 제외)."""
    for script in _job_run_scripts():
        if "pip install" in script:
            continue
        if f"-m {tool}" in script or script.strip().startswith(tool):
            return script
    return ""


def test_ruff_step_exists() -> None:
    """계약 ① — ruff 스텝이 없으면 tests/infra의 정적 위반이 CI를 통과한다."""
    assert _step_invoking("ruff"), (
        f"`{_JOB_KEY}` 잡에 ruff 스텝이 없다 — {_TARGET}는 어떤 잡도 lint하지 않게 된다 "
        "(backend 잡은 tests/backend만 본다)."
    )


def test_black_step_exists() -> None:
    """계약 ① — black 스텝이 없으면 포맷 드리프트가 조용히 쌓인다(실측 선례 1건)."""
    assert _step_invoking("black"), f"`{_JOB_KEY}` 잡에 black 스텝이 없다."


def test_black_uses_repo_standard_line_length() -> None:
    """계약 ② — 다른 잡과 다른 규칙으로 검사하면 통과해도 의미가 없다."""
    script = _step_invoking("black")
    assert script, "black 스텝 부재(위 테스트 참조)"
    assert (
        "--line-length 100" in script
    ), f"black 스텝이 저장소 표준 `--line-length 100`을 쓰지 않는다: {script.strip()!r}"
    assert (
        "--check" in script
    ), "black이 `--check` 없이 실행되면 CI에서 파일을 고쳐버린다(게이트 아님)."


def test_both_steps_target_tests_infra() -> None:
    """계약 ③ — 다른 경로를 검사하며 통과하는 위장을 차단한다."""
    for tool in ("ruff", "black"):
        script = _step_invoking(tool)
        assert script, f"{tool} 스텝 부재"
        assert (
            _TARGET in script
        ), f"{tool} 스텝이 `{_TARGET}`를 대상으로 하지 않는다: {script.strip()!r}"


def test_parser_fails_loudly_on_unknown_job(monkeypatch: Any) -> None:
    """계약 ④ — 잡을 못 찾으면 조용한 통과가 아니라 예외여야 한다."""
    import pytest as _pytest

    monkeypatch.setitem(globals(), "_JOB_KEY", "__nonexistent_job__")
    with _pytest.raises(AssertionError, match="잡이 없다"):
        _job_run_scripts()
