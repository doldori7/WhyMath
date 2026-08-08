"""[OPS-16] L3 생성 프롬프트 레일 게이트의 **배선 실재성** 동결.

왜 이 테스트가 있는가
--------------------
`harness/prompt_asset_audit.py`가 저장소에 존재하는 것과 CI가 실제로 그것을 실행하는 것은
다르다(CLAUDE.md "검증 장치를 만들고 배선 확인 없이 완료 선언 금지"). 이 저장소에서 같은
사고가 반복 발생했다 — `tests/infra` 199건이 어떤 잡도 실행하지 않던 상태(OPS-03), 브랜치
보호 required check가 통째 미강제였던 상태(OPS-08), `tests/infra`를 lint하는 잡이 없던 상태
(OPS-11). 이 테스트가 없으면 `ci.yml`에서 이 게이트 스텝이 조용히 삭제돼도 아무 신호가 없다.

`test_provenance_audit_wiring.py`(ARCH-20)의 직계 미러다 — 새 규칙을 만들지 않고 **이미 있는
규칙을 그대로 한 게이트 더 적용**한다.

검증 계약
--------
① `backend` 잡에 `prompt_asset_audit` 모듈을 호출하는 `run` 스텝이 있다
② 그 스텝이 `-m whymath_backend.harness.prompt_asset_audit` 형태로 호출한다(파일 경로 직접
   실행 같은 변형이 아니라 패키지 모듈 실행 — venv·PYTHONPATH 문제 없이 항상 도는 형태)
③ 그 스텝이 **L3 축을 켠 채** 돈다 — 소크라테스 축 단독 실행(`--axis socratic`)은 언제나
   exit 0이라 게이트가 아니다. 축 인자가 잘못 바뀌면 "스텝은 있는데 아무것도 막지 않는" 상태가
   되므로 축까지 동결한다(OPS-08 `enforcement_level=off`와 같은 형태의 무력화 방지).
④ 파서가 위장하지 않는다 — 워크플로/잡을 못 찾으면 "위반 0 통과"가 아니라 **실패**
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

_REPO_ROOT = Path(__file__).resolve().parents[2]
_CI_PATH = _REPO_ROOT / ".github" / "workflows" / "ci.yml"
_JOB_KEY = "backend"
_MODULE_INVOCATION = "-m whymath_backend.harness.prompt_asset_audit"
# L3 축을 끄는 인자 — 이 값이 붙으면 게이트가 아무것도 막지 못한다.
_DISABLING_AXIS = "--axis socratic"


def _backend_job_run_scripts() -> list[str]:
    if not _CI_PATH.is_file():
        raise AssertionError(f"{_CI_PATH} 이(가) 없다 — 게이트 배선을 확인할 수 없다.")
    spec: Any = yaml.safe_load(_CI_PATH.read_text(encoding="utf-8"))
    jobs = (spec or {}).get("jobs") or {}
    if _JOB_KEY not in jobs:
        raise AssertionError(
            f"ci.yml에 `{_JOB_KEY}` 잡이 없다 — 잡을 개명했다면 이 테스트도 함께 고쳐라."
        )
    steps = (jobs[_JOB_KEY] or {}).get("steps") or []
    scripts = [str(s.get("run", "")) for s in steps if isinstance(s, dict) and s.get("run")]
    if not scripts:
        raise AssertionError(f"`{_JOB_KEY}` 잡에 `run` 스텝이 하나도 없다.")
    return scripts


def _audit_steps() -> list[str]:
    steps = [s for s in _backend_job_run_scripts() if "prompt_asset_audit" in s]
    assert steps, (
        f"`{_JOB_KEY}` 잡에 `{_MODULE_INVOCATION}` 호출 스텝이 없다 — L3 생성 프롬프트 레일 "
        "게이트(저작권·봉인·독립성)가 CI에서 조용히 빠졌다(코드는 존재하나 실행되지 않는 상태)."
    )
    return steps


def test_prompt_asset_audit_step_exists_in_backend_job() -> None:
    assert any(_MODULE_INVOCATION in script for script in _audit_steps())


def test_prompt_asset_audit_step_uses_module_invocation_not_bare_script() -> None:
    """`python path/to/prompt_asset_audit.py` 같은 변형은 cwd·PYTHONPATH에 취약하다 —
    `-m` 패키지 실행만 인정한다(다른 게이트 스텝들과 동일 관용구)."""
    steps = _audit_steps()
    assert all(
        _MODULE_INVOCATION in s for s in steps
    ), f"prompt_asset_audit 스텝이 `-m` 모듈 실행 형태가 아니다: {steps}"


def test_prompt_asset_audit_step_keeps_the_l3_axis_enabled() -> None:
    """계약 ③ — 소크라테스 축 단독 실행은 항상 exit 0이라 게이트로서 무력하다."""
    steps = _audit_steps()
    disabled = [s for s in steps if _DISABLING_AXIS in s]
    assert not disabled, (
        "prompt_asset_audit 게이트 스텝이 `--axis socratic`으로 돌고 있다 — 그 축은 항상 exit 0"
        f"이라 무엇도 막지 못한다(스텝은 있는데 게이트는 없는 상태): {disabled}"
    )
