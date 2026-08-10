"""[OPS-22] 선언≠배선 일반 탐지기의 **배선 실재성** 동결.

왜 이 테스트가 있는가
--------------------
`ops/declared_unwired_audit.py`가 저장소에 존재하는 것과 CI가 실제로 그것을 실행하는 것은
다르다(CLAUDE.md "검증 장치를 만들고 배선 확인 없이 완료 선언 금지" — `tests/infra` 199건이
어떤 잡도 실행하지 않던 OPS-03 사고, `provenance_audit`용 동형 선례 `test_provenance_audit_
wiring.py`와 같은 계열). 이 테스트가 없으면 `ci.yml`에서 이 스텝이 조용히 삭제돼도 아무 신호가
나지 않는다 — 하필 이 감사 자신이 막으려는 "선언≠배선" 패턴을 이 감사 스스로 앓게 되는
자기모순이라 특히 중요하다.

검증 계약
--------
① `declared-unwired-audit` 잡이 `ci.yml`에 존재하고 `-m whymath_backend.ops.declared_unwired_
   audit` 형태로 호출하는 `run` 스텝을 가진다(패키지 모듈 실행 — venv·PYTHONPATH 문제 없이
   항상 도는 형태).
② 그 잡이 `needs: changes`에 의존하지 않는다 — 이 감사가 보는 4축(모바일 dart 호출·backlog
   태스크 상태·ci.yml 자신)은 `changes` 잡의 `backend` 필터가 커버하지 않는 영역이라(그 필터는
   `src/backend/`·`tests/backend/`만 본다), 필터에 종속되면 "dart 호출 삭제 PR"이나 "backlog
   태스크 done 전환 PR"에서 감사가 skip돼(GitHub가 skipped를 required check 충족으로 셈) 회귀가
   그대로 머지된다 — 이 감사가 존재하는 바로 그 이유를 스스로 무력화하는 배선이 되므로 별도
   계약으로 동결한다.
③ 파서가 위장하지 않는다 — 워크플로/잡을 못 찾으면 "위반 0 통과"가 아니라 **실패**.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

_REPO_ROOT = Path(__file__).resolve().parents[2]
_CI_PATH = _REPO_ROOT / ".github" / "workflows" / "ci.yml"
_JOB_KEY = "declared-unwired-audit"
_MODULE_INVOCATION = "-m whymath_backend.ops.declared_unwired_audit"


def _load_jobs() -> dict[str, Any]:
    if not _CI_PATH.is_file():
        raise AssertionError(f"{_CI_PATH} 이(가) 없다 — 게이트 배선을 확인할 수 없다.")
    spec: Any = yaml.safe_load(_CI_PATH.read_text(encoding="utf-8"))
    jobs = (spec or {}).get("jobs") or {}
    if not isinstance(jobs, dict) or not jobs:
        raise AssertionError("ci.yml에 jobs가 없다 — 워크플로 파싱이 위장 통과할 수 없다.")
    return jobs


def _target_job() -> dict[str, Any]:
    jobs = _load_jobs()
    if _JOB_KEY not in jobs:
        raise AssertionError(
            f"ci.yml에 `{_JOB_KEY}` 잡이 없다 — 잡을 개명했다면 이 테스트도 함께 고쳐라."
        )
    job = jobs[_JOB_KEY]
    if not isinstance(job, dict):
        raise AssertionError(f"`{_JOB_KEY}` 잡 정의가 비어 있거나 형식이 아니다.")
    return job


def _job_run_scripts(job: dict[str, Any]) -> list[str]:
    steps = job.get("steps") or []
    scripts = [str(s.get("run", "")) for s in steps if isinstance(s, dict) and s.get("run")]
    if not scripts:
        raise AssertionError(f"`{_JOB_KEY}` 잡에 `run` 스텝이 하나도 없다.")
    return scripts


def test_declared_unwired_audit_step_exists() -> None:
    scripts = _job_run_scripts(_target_job())
    assert any(_MODULE_INVOCATION in script for script in scripts), (
        f"`{_JOB_KEY}` 잡에 `{_MODULE_INVOCATION}` 호출 스텝이 없다 — 선언≠배선 감사가 CI에서 "
        "조용히 빠졌다(코드는 존재하나 실행되지 않는 상태)."
    )


def test_declared_unwired_audit_step_uses_module_invocation_not_bare_script() -> None:
    """`python path/to/declared_unwired_audit.py` 같은 변형은 cwd·PYTHONPATH에 취약하다 —
    `-m` 패키지 실행만 인정한다(다른 게이트 스텝들과 동일 관용구)."""
    scripts = _job_run_scripts(_target_job())
    matching = [s for s in scripts if "declared_unwired_audit" in s]
    assert matching, "declared_unwired_audit을 언급하는 스텝이 하나도 없다."
    assert all(
        _MODULE_INVOCATION in s for s in matching
    ), f"declared_unwired_audit 스텝이 `-m` 모듈 실행 형태가 아니다: {matching}"


def test_declared_unwired_audit_job_does_not_depend_on_changes_filter() -> None:
    """이 잡이 `needs: changes`에 걸려 있지 않은지 — 걸려 있으면 이 감사가 보는 축(모바일
    dart·backlog 상태)이 정확히 그 필터의 사각지대라 자기모순적으로 스스로를 무력화한다."""
    job = _target_job()
    needs = job.get("needs")
    if needs is None:
        return
    needs_list = [needs] if isinstance(needs, str) else list(needs)
    assert "changes" not in needs_list, (
        f"`{_JOB_KEY}` 잡이 `needs: changes`에 의존한다({needs_list}) — 이 감사가 보는 축은 "
        "`changes` 잡의 `backend` 필터(src/backend/·tests/backend/만 봄) 밖이라, 그 필터에 "
        "종속되면 감사 자신이 잡아야 할 바로 그 종류의 PR에서 skip된다."
    )
