"""[OPS-17] 공급↔소비 도달 대장의 **배선 실재성** 동결.

왜 이 테스트가 있는가
--------------------
`ops/reach_audit.py`가 저장소에 존재하는 것과 CI가 실제로 그것을 실행하는 것은 다르다
(CLAUDE.md "검증 장치를 만들고 배선 확인 없이 완료 선언 금지" — `tests/infra` 199건이 어떤
잡도 실행하지 않던 OPS-03, required check가 `checks=[]`로 통째 미강제였던 OPS-08, `tests/infra`
를 lint하는 잡이 없던 OPS-11과 동일 계열).

이 모듈은 특히 아이러니에 취약하다 — **"만들고 켜지 않음"을 막는 장치가 정작 안 켜져 있으면**
그 자체가 그 사고의 6회차가 된다. 그래서 배선을 기계로 동결한다.

검증 계약 (각 항목은 변별력이 확인된 것만)
----------------------------------------
① `reach-audit` 잡이 실재하고 `-m whymath_backend.ops.reach_audit`를 호출한다
② 그 잡에 **변경 경로 필터(`if:`)가 없다** — 이것이 이 잡의 존재 이유다. `backend` 잡의
   필터는 `src/mobile/`·`backlog/`를 보지 않아서, 거기 얹으면 dart 호출을 지우는 모바일 전용
   PR에서 감사가 skip된다. `if:`가 붙는 순간 그 구멍이 되살아나므로 붙이지 못하게 막는다.
③ 파서가 위장하지 않는다 — 워크플로/잡을 못 찾으면 "위반 0 통과"가 아니라 **실패**
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

_REPO_ROOT = Path(__file__).resolve().parents[2]
_CI_PATH = _REPO_ROOT / ".github" / "workflows" / "ci.yml"
_JOB_KEY = "reach-audit"
_MODULE_INVOCATION = "-m whymath_backend.ops.reach_audit"


def _ci_spec() -> dict[str, Any]:
    if not _CI_PATH.is_file():
        raise AssertionError(f"{_CI_PATH} 이(가) 없다 — 게이트 배선을 확인할 수 없다.")
    spec: Any = yaml.safe_load(_CI_PATH.read_text(encoding="utf-8"))
    jobs = (spec or {}).get("jobs") or {}
    if not jobs:
        raise AssertionError("ci.yml에 jobs가 하나도 없다 — 파서가 깨졌거나 파일이 비었다.")
    return dict(jobs)


def _reach_audit_job() -> dict[str, Any]:
    jobs = _ci_spec()
    if _JOB_KEY not in jobs:
        raise AssertionError(
            f"ci.yml에 `{_JOB_KEY}` 잡이 없다 — 도달 대장이 CI에서 조용히 빠졌다"
            "(코드는 존재하나 실행되지 않는 상태). 잡을 개명했다면 이 테스트도 함께 고쳐라."
        )
    return dict(jobs[_JOB_KEY] or {})


def _run_scripts(job: dict[str, Any]) -> list[str]:
    steps = job.get("steps") or []
    scripts = [str(s.get("run", "")) for s in steps if isinstance(s, dict) and s.get("run")]
    if not scripts:
        raise AssertionError(f"`{_JOB_KEY}` 잡에 `run` 스텝이 하나도 없다.")
    return scripts


def test_reach_audit_step_exists() -> None:
    scripts = _run_scripts(_reach_audit_job())
    assert any(_MODULE_INVOCATION in script for script in scripts), (
        f"`{_JOB_KEY}` 잡에 `{_MODULE_INVOCATION}` 호출 스텝이 없다 — 공급↔소비 도달 대장이 "
        "CI에서 실행되지 않는다."
    )


def test_reach_audit_uses_module_invocation_not_bare_script() -> None:
    """`python path/to/reach_audit.py` 같은 변형은 cwd·PYTHONPATH에 취약하다 —
    `-m` 패키지 실행만 인정한다(다른 게이트 스텝들과 동일 관용구)."""
    scripts = [s for s in _run_scripts(_reach_audit_job()) if "reach_audit" in s]
    assert scripts, f"`{_JOB_KEY}` 잡에 reach_audit를 언급하는 run 스텝이 없다."
    assert all(
        _MODULE_INVOCATION in s for s in scripts
    ), "reach_audit를 파일 경로로 직접 실행하는 스텝이 있다 — `-m` 패키지 실행만 인정한다."


def test_reach_audit_job_has_no_change_filter() -> None:
    """이 잡에 `if:`가 붙으면 존재 이유가 사라진다.

    `backend` 잡의 변경 필터는 `src/mobile/`·`backlog/`를 포함하지 않는다. 그래서 도달 대장을
    조건부로 만들면 **dart 호출을 지우는 모바일 전용 PR·태스크를 done으로 바꾸는 backlog 전용
    PR에서 감사가 skip**되고, GitHub은 skipped를 required check 충족으로 세므로 회귀가 그대로
    머지된다. 상시 실행이 이 잡의 계약이다.
    """
    job = _reach_audit_job()
    assert "if" not in job, (
        f"`{_JOB_KEY}` 잡에 `if:` 조건이 붙었다 — 이 잡은 **항상** 실행돼야 한다. "
        "조건부로 만들면 모바일·backlog 전용 PR에서 skip되고(GitHub은 skipped를 required "
        "충족으로 센다) 도달 회귀가 그대로 통과한다."
    )
    assert "needs" not in job, (
        f"`{_JOB_KEY}` 잡에 `needs:`가 붙었다 — 선행 잡이 skip/실패하면 이 잡도 함께 "
        "돌지 않는다. 독립 실행을 유지하라."
    )


def test_reach_audit_installs_backend_package() -> None:
    """`create_app()` 인트로스펙션에 백엔드 패키지가 필요하다 — 설치 스텝이 빠지면
    잡이 ImportError로 죽고, 그건 '감사 통과'가 아니라 '감사 불가'다."""
    scripts = _run_scripts(_reach_audit_job())
    assert any("pip install" in s and "src/backend" in s for s in scripts), (
        f"`{_JOB_KEY}` 잡에 백엔드 설치 스텝이 없다 — reach_audit는 create_app()을 부르므로 "
        "패키지 설치 없이는 실행 자체가 불가능하다."
    )
