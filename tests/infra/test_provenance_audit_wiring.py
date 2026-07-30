"""[ARCH-20] 콘텐츠 출처·라이선스 집행 게이트의 **배선 실재성** 동결.

왜 이 테스트가 있는가
--------------------
`ops/provenance_audit.py`가 저장소에 존재하는 것과 CI가 실제로 그것을 실행하는 것은
다르다(CLAUDE.md "검증 장치를 만들고 배선 확인 없이 완료 선언 금지" — `tests/infra` 199건이
어떤 잡도 실행하지 않던 OPS-03 사고, required check가 `checks=[]`로 통째 미강제였던 OPS-08
사고와 동일 계열). 이 테스트가 없으면 `ci.yml`에서 이 스텝이 조용히 삭제돼도 아무 신호가
나지 않는다.

검증 계약
--------
① `backend` 잡에 `provenance_audit` 모듈을 호출하는 `run` 스텝이 있다
② 그 스텝이 `-m whymath_backend.ops.provenance_audit` 형태로 호출한다(파일 경로 직접 실행
   같은 변형이 아니라 패키지 모듈 실행 — venv·PYTHONPATH 문제 없이 항상 도는 형태)
③ 파서가 위장하지 않는다 — 워크플로/잡을 못 찾으면 "위반 0 통과"가 아니라 **실패**
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

_REPO_ROOT = Path(__file__).resolve().parents[2]
_CI_PATH = _REPO_ROOT / ".github" / "workflows" / "ci.yml"
_JOB_KEY = "backend"
_MODULE_INVOCATION = "-m whymath_backend.ops.provenance_audit"


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


def test_provenance_audit_step_exists_in_backend_job() -> None:
    scripts = _backend_job_run_scripts()
    assert any(_MODULE_INVOCATION in script for script in scripts), (
        f"`{_JOB_KEY}` 잡에 `{_MODULE_INVOCATION}` 호출 스텝이 없다 — 콘텐츠 출처·라이선스 "
        "집행 게이트가 CI에서 조용히 빠졌다(코드는 존재하나 실행되지 않는 상태)."
    )


def test_provenance_audit_step_uses_module_invocation_not_bare_script() -> None:
    """`python path/to/provenance_audit.py` 같은 변형은 cwd·PYTHONPATH에 취약하다 —
    `-m` 패키지 실행만 인정한다(다른 게이트 스텝들과 동일 관용구)."""
    scripts = _backend_job_run_scripts()
    matching = [s for s in scripts if "provenance_audit" in s]
    assert matching, "provenance_audit을 언급하는 스텝이 하나도 없다."
    assert all(
        _MODULE_INVOCATION in s for s in matching
    ), f"provenance_audit 스텝이 `-m` 모듈 실행 형태가 아니다: {matching}"
