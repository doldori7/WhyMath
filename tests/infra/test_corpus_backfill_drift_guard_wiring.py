"""[OPS-24] 코퍼스 후처리 백필 드리프트 가드의 **배선 실재성** 동결.

왜 이 테스트가 있는가
--------------------
`--check` 모드를 만든 것과 CI가 그것을 실제로 실행하는 것은 다르다(CLAUDE.md "검증 장치를
만들고 배선 확인 없이 완료 선언 금지"). 하필 이 두 CLI는 **바로 그 패턴으로 OPS-22 감사기에
적발된** 모듈이다 — 만들어 놓고 아무 데서도 안 돌던 상태였다. 배선이 조용히 빠지면 감사기가
다시 잡아주긴 하지만, 그때는 이미 "가드가 있다고 믿은 채로 드리프트가 머지된 뒤"다.

검증 계약
--------
① 두 CLI가 `-m whymath_backend.harness.<모듈> --all --check` 형태로 `ci.yml`에 존재한다
   (`-m` 패키지 실행 — OPS-22 감사기의 `ci_executed_modules` 정규식이 인식하는 유일한 형태이자
   cwd·PYTHONPATH에 강한 관용구).
② 그 스텝이 얹힌 잡이 **push/PR 경로**다 — `if:`가 schedule 전용(`== 'schedule'`)이 아니고
   `needs: changes` 게이팅도 없다. 드리프트는 PR에서 잡아야 하고, 코퍼스 파일만 바뀐 PR에서
   skip되면(GitHub는 skipped를 required check 충족으로 센다) 가드가 정확히 자기가 잡아야 할
   PR에서 무력해진다.
③ 스텝이 **변이형이 아니다** — `--check` 없는 백필 호출(제자리 갱신)이 CI에 있어서는 안 된다.
   CI가 레포 데이터를 재작성하면 "가드"가 아니라 "자동 커밋기"가 된다.
④ 레포 루트 기준 상대경로(`data/corpus/...`)를 읽는 CLI이므로 스텝의 실행 디렉터리가 잡
   기본값(`src/backend`)이 아니라 워크스페이스 루트로 되돌려져 있다.
⑤ 파서가 위장하지 않는다 — 워크플로/잡/스텝을 못 찾으면 "통과"가 아니라 **실패**.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

_REPO_ROOT = Path(__file__).resolve().parents[2]
_CI_PATH = _REPO_ROOT / ".github" / "workflows" / "ci.yml"

_MODULES = (
    "whymath_backend.harness.problem_corpus_review_status_backfill",
    "whymath_backend.harness.problem_corpus_persona_fit_backfill",
)
# 스텝의 실행 디렉터리로 인정하는 값 — 워크스페이스 루트를 가리키는 표기만.
_ROOT_WORKING_DIRS = {"${{ github.workspace }}", ".", "${{ github.workspace }}/"}


def _load_jobs() -> dict[str, Any]:
    if not _CI_PATH.is_file():
        raise AssertionError(f"{_CI_PATH} 이(가) 없다 — 게이트 배선을 확인할 수 없다.")
    spec: Any = yaml.safe_load(_CI_PATH.read_text(encoding="utf-8"))
    jobs = (spec or {}).get("jobs") or {}
    if not isinstance(jobs, dict) or not jobs:
        raise AssertionError("ci.yml에 jobs가 없다 — 워크플로 파싱이 위장 통과할 수 없다.")
    return jobs


def _steps_running(module: str) -> list[tuple[str, dict[str, Any], dict[str, Any]]]:
    """`-m <module>`을 실행하는 (잡 키, 잡 정의, 스텝 정의) 목록."""
    found: list[tuple[str, dict[str, Any], dict[str, Any]]] = []
    for job_key, job in _load_jobs().items():
        if not isinstance(job, dict):
            continue
        for step in job.get("steps") or []:
            if isinstance(step, dict) and step.get("run") and f"-m {module}" in str(step["run"]):
                found.append((job_key, job, step))
    return found


def _assert_single_step(module: str) -> tuple[str, dict[str, Any], dict[str, Any]]:
    steps = _steps_running(module)
    assert steps, (
        f"ci.yml에 `-m {module}` 실행 스텝이 없다 — 백필 드리프트 가드가 CI에서 조용히 빠졌다"
        "(코드는 존재하나 실행되지 않는 상태 = OPS-22가 적발했던 바로 그 패턴의 재발)."
    )
    return steps[0]


def test_both_backfill_check_steps_exist_in_ci() -> None:
    """① 두 CLI 모두 `--all --check` 형태로 배선돼 있다."""
    for module in _MODULES:
        _job_key, _job, step = _assert_single_step(module)
        script = str(step["run"])
        assert "--check" in script, (
            f"`-m {module}` 스텝에 `--check`가 없다 — `--dry-run`은 채울 게 있어도 항상 exit 0이라 "
            "게이트로 쓸 수 없다(변별력 없는 검증 스텝 금지)."
        )
        assert "--all" in script, f"`-m {module}` 스텝이 `--all`이 아니다 — 코퍼스 일부만 검사한다."


def test_ci_never_runs_the_mutating_backfill() -> None:
    """③ CI에 변이형(제자리 갱신) 호출이 없다 — CI가 레포 데이터를 재작성해서는 안 된다."""
    for module in _MODULES:
        for job_key, _job, step in _steps_running(module):
            script = str(step["run"])
            assert "--check" in script or "--dry-run" in script, (
                f"`{job_key}` 잡의 `-m {module}` 스텝이 쓰기 모드로 돈다({script!r}) — CI가 "
                "코퍼스 JSONL·감사로그를 재작성하는 배선은 금지다."
            )


def test_backfill_guard_runs_on_push_and_pr_not_schedule_only() -> None:
    """② 드리프트는 PR에서 잡아야 한다 — schedule 전용 잡·`needs: changes` 게이팅 금지."""
    for module in _MODULES:
        job_key, job, _step = _assert_single_step(module)
        condition = str(job.get("if", ""))
        assert "== 'schedule'" not in condition.replace('"', "'"), (
            f"`{job_key}` 잡이 schedule 전용이다({condition!r}) — 백필 드리프트는 머지 전에 "
            "잡혀야 하므로 push/PR 경로에 있어야 한다."
        )
        needs = job.get("needs")
        needs_list = [needs] if isinstance(needs, str) else list(needs or [])
        assert "changes" not in needs_list, (
            f"`{job_key}` 잡이 `needs: changes`에 의존한다({needs_list}) — `backend` 필터는 "
            "`src/backend/`·`tests/backend/`만 보므로 코퍼스(`data/corpus/`)만 바뀐 PR에서 "
            "가드가 skip된다(skipped는 required check 충족으로 계산된다)."
        )


def test_backfill_guard_steps_run_from_repo_root() -> None:
    """④ 두 CLI는 레포 루트 기준 상대경로를 읽는다 — 잡 기본 working-directory를 되돌려야 한다."""
    for module in _MODULES:
        job_key, job, step = _assert_single_step(module)
        job_default = str(
            ((job.get("defaults") or {}).get("run") or {}).get("working-directory", "")
        )
        step_dir = step.get("working-directory")
        if job_default in ("", ".", "${{ github.workspace }}"):
            continue  # 잡 기본값이 이미 루트 — 스텝 지정 불요
        assert step_dir is not None and str(step_dir) in _ROOT_WORKING_DIRS, (
            f"`{job_key}` 잡의 기본 working-directory는 {job_default!r}인데 `-m {module}` 스텝이 "
            f"루트로 되돌리지 않았다(step working-directory={step_dir!r}) — 이 CLI는 "
            "`data/corpus/...` 같은 레포 루트 상대경로를 읽으므로 그대로면 FileNotFoundError다."
        )
