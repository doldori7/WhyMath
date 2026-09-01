"""[HARN-52] 의존 선언↔집행 게이트의 **배선 실재성** 동결.

왜 이 테스트가 있는가
--------------------
`scripts/harness/dep_declaration.py`가 저장소에 존재하는 것과 CI가 실제로 그것을 실행하는
것은 다르다(CLAUDE.md "검증 장치를 만들고 배선 확인 없이 완료 선언 금지" — `tests/infra`
199건이 어떤 잡도 실행하지 않던 OPS-03 사고, 브랜치 보호 required check가 통째 미강제였던
OPS-08). 동형 선례 = `test_declared_unwired_audit_wiring.py`.

이 게이트에는 자기모순의 위험이 특히 크다 — **"선언했는데 집행되지 않는다"를 잡는 장치가
정작 자기 자신은 선언만 되고 집행되지 않는** 상태가 되면, 그 사실을 아무도 모른다. 그래서
배선을 별도 계약으로 못박는다.

검증 계약
--------
① `harness-integrity` 잡에 `backlog.py audit-deps` 를 호출하는 `run` 스텝이 존재한다.
② 그 잡이 `needs: changes` 에 의존하지 않는다 — 이 게이트가 보는 대상은 `backlog/tasks/`
   이고, 경로 필터에 종속되면 "태스크 YAML만 바꾸는 PR"에서 skip될 수 있다(GitHub는
   skipped를 required check 충족으로 셈한다).
③ 호출이 판정을 무력화하지 않는다 — `|| true`·`continue-on-error` 로 감싸면 exit 1이
   삼켜져 fail-open이 된다(ARCH-23이 QA 게이트에서 겪은 그 결함).
④ 파서가 위장하지 않는다 — 워크플로/잡을 못 찾으면 "통과"가 아니라 **실패**.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

_REPO_ROOT = Path(__file__).resolve().parents[2]
_CI_PATH = _REPO_ROOT / ".github" / "workflows" / "ci.yml"
_JOB_KEY = "harness-integrity"
_INVOCATION = "backlog.py audit-deps"


def _job() -> dict[str, Any]:
    if not _CI_PATH.is_file():
        raise AssertionError(f"{_CI_PATH} 이(가) 없다 — 게이트 배선을 확인할 수 없다.")
    spec: Any = yaml.safe_load(_CI_PATH.read_text(encoding="utf-8"))
    jobs = (spec or {}).get("jobs") or {}
    if not isinstance(jobs, dict) or not jobs:
        raise AssertionError("ci.yml에 jobs가 없다 — 파싱이 위장 통과할 수 없다.")
    job = jobs.get(_JOB_KEY)
    if not isinstance(job, dict):
        raise AssertionError(f"ci.yml에 '{_JOB_KEY}' 잡이 없다 — 게이트가 돌 곳이 없다.")
    return job


def _steps() -> list[dict[str, Any]]:
    steps = _job().get("steps") or []
    if not isinstance(steps, list) or not steps:
        raise AssertionError(f"'{_JOB_KEY}' 잡에 steps가 없다.")
    return [s for s in steps if isinstance(s, dict)]


def _audit_steps() -> list[dict[str, Any]]:
    return [s for s in _steps() if _INVOCATION in str(s.get("run") or "")]


def test_audit_deps_step_exists() -> None:
    """① CI가 실제로 게이트를 실행한다 — 저장소에 있는 것과 도는 것은 다르다."""
    found = _audit_steps()
    assert found, (
        f"'{_JOB_KEY}' 잡에 `{_INVOCATION}` 를 실행하는 스텝이 없다 — "
        "의존 선언↔집행 게이트가 배선되지 않았다(HARN-52 ③)."
    )


def test_audit_deps_step_is_not_fail_open() -> None:
    """③ exit 1이 삼켜지지 않는다 — fail-open 보호는 보호가 아니다."""
    for step in _audit_steps():
        assert step.get("continue-on-error") is not True, (
            "audit-deps 스텝에 continue-on-error: true 가 붙어 있다 — "
            "위반이 red를 내지 못한다(ARCH-23이 겪은 fail-open 결함의 재발)."
        )
        run = str(step.get("run") or "")
        assert "|| true" not in run, "audit-deps 호출이 `|| true` 로 판정을 무력화한다."


def test_job_is_not_path_filtered() -> None:
    """② 경로 필터에 종속되지 않는다 — skip은 required check 충족으로 셈해진다."""
    needs = _job().get("needs")
    needs_list = [needs] if isinstance(needs, str) else list(needs or [])
    assert "changes" not in needs_list, (
        f"'{_JOB_KEY}' 잡이 `needs: changes` 에 종속됐다 — backlog/tasks만 바꾸는 PR에서 "
        "게이트가 skip될 수 있다(HARN-52 ②)."
    )
