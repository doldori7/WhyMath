"""concept-reach 회귀 가드가 **mobile-only PR에서도 발화**하도록 CI에 배선됐는지 동결.

왜 이 테스트가 있는가 (OPS-23 — 2026-08-08 사고)
-----------------------------------------------
`tests/backend/harness/test_concept_reach_report.py`의 `test_real_corpus_smoke_...`는 실제
`src/mobile/lib`를 스캔해 모바일의 `/v1/` 호출 표면 도달을 동결하는 **회귀 가드**다. 그런데 이
가드는 backend 잡 소속이라 `ci.yml`의 `changes` 필터가 매기는 **backend** 플래그
(`src/backend/|tests/backend/|conftest.py|ci.yml`)로만 켜진다. 즉 **`src/mobile/`만 건드리는
PR은 backend=false → backend 잡 스킵 → 이 가드도 함께 스킵**된다. PATH-05가 정확히 그 경로로
가드를 조용히 우회했고(모바일만 변경), 서버·클라를 동시에 건드린 다음 PR(MOB-10)에서야
`/v1/` 콜사이트 분모 증가가 드러났다.

OPS-23은 그 사각을 **경량 신규 잡**(`concept-reach-guard`)으로 닫는다 — 전체 backend 잡을
돌리지 않고 이 가드 한 파일만 `mobile==true`에서 실행한다. 이 테스트는 그 배선이 실제로 존재
하는지, 그리고 트리거가 **mobile 필터**를 참조하는지를 `ci.yml`을 파싱해 정적으로 동결한다.
`tests/infra/test_test_suite_wiring.py`(OPS-10)와 같은 사상 — "장치가 있다"와 "장치가 실제로
그 조건에서 돈다"는 다르며, 후자를 기계로 확인한다.

검증 계약 (각 항목은 변별력이 확인된 것만 — CLAUDE.md "변별력 없는 검증 스텝 금지")
--------------------------------------------------------------------------------
① 어떤 잡이 `test_concept_reach_report.py`를 실행하는 pytest 스텝을 갖는다.
② 그 잡의 `if` 조건이 `needs.changes.outputs.mobile == 'true'`(mobile 필터)를 참조한다 =
   mobile-only PR에서도 가드가 발화한다. (backend 필터에만 걸려 있으면 사고 재발 → RED.)
③ `changes` 잡의 mobile 필터가 실제로 `src/mobile/`를 포함한다 — 필터가 바뀌어 mobile을 안
   잡으면 우회가 재발하므로 함께 동결한다.
④ 파서가 위장하지 않는다 — ci.yml을 못 읽거나 잡/스텝을 하나도 못 찾으면 "0건 통과"가 아니라
   **예외로 실패**한다("0건 통과"와 "측정 실패"는 절대 같은 색이면 안 된다).

RED→GREEN 실측(배선 반증):
   이 파일을 GREEN으로 남기려면 위 ①②가 성립해야 한다. `ci.yml`에서 잡을 지우거나 `if`의
   mobile 조건을 제거하면 ①/② 단언이 RED가 된다 — 그 반증은 OPS-23 검증 로그에 기록했다.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any

import pytest
import yaml

_REPO_ROOT = Path(__file__).resolve().parents[2]
_CI_YAML = _REPO_ROOT / ".github" / "workflows" / "ci.yml"

# 가드가 감시하는 회귀 스모크 테스트 파일(배선의 판정 대상). 파일명이 바뀌면 배선도 다시
# 확인해야 하므로 여기에 상수로 박아 둔다 — 이 문자열이 ci.yml 어딘가의 pytest 스텝에 있어야 한다.
_GUARD_TEST_FILE = "test_concept_reach_report.py"


def _extract_jobs(spec: Any, source: str) -> dict[str, Any]:
    """스펙에서 jobs 매핑을 꺼낸다 — 공백/비매핑이면 예외(계약 ④: 파서 무력화 ≠ 통과)."""
    if not isinstance(spec, dict):
        raise AssertionError(f"{source}: 워크플로 YAML이 매핑으로 파싱되지 않았다.")
    jobs = spec.get("jobs")
    if not isinstance(jobs, dict) or not jobs:
        raise AssertionError(f"{source}: jobs 블록이 비었다 — 파서가 배선을 읽지 못하는 상태다.")
    return jobs


def _load_ci_jobs() -> dict[str, Any]:
    """ci.yml을 파싱해 jobs를 돌려준다 — 못 읽으면 예외(계약 ④)."""
    if not _CI_YAML.is_file():
        raise AssertionError(f"{_CI_YAML}: CI 워크플로 파일이 없다 — 배선을 읽을 수 없다.")
    spec = yaml.safe_load(_CI_YAML.read_text(encoding="utf-8"))
    return _extract_jobs(spec, str(_CI_YAML))


def _iter_run_steps(job: Mapping[str, Any]) -> Iterator[str]:
    steps = job.get("steps")
    if not isinstance(steps, list):
        return
    for step in steps:
        if isinstance(step, dict) and isinstance(step.get("run"), str):
            yield step["run"]


def _jobs_running_guard(jobs: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    """가드 테스트 파일을 실행하는 pytest 스텝을 가진 잡 → 잡 스펙."""
    matched: dict[str, dict[str, Any]] = {}
    for job_id, job in jobs.items():
        if not isinstance(job, dict):
            continue
        for run in _iter_run_steps(job):
            if "pytest" in run and _GUARD_TEST_FILE in run:
                matched[str(job_id)] = job
                break
    return matched


# ── 계약 ① · ② : 실제 ci.yml 판정 ──────────────────────────────────────────────


def test_a_job_runs_the_concept_reach_guard() -> None:
    """계약 ① — 어떤 잡이 concept_reach 회귀 가드 파일을 실행하는 pytest 스텝을 갖는다."""
    jobs = _load_ci_jobs()
    running = _jobs_running_guard(jobs)
    assert running, (
        f"{_GUARD_TEST_FILE}를 실행하는 pytest 스텝을 가진 잡이 하나도 없다 — concept_reach "
        "회귀 가드가 CI에서 돌지 않는다(OPS-23 사각 재발). ci.yml에 이 파일을 도는 잡을 배선하라."
    )


def test_guard_job_fires_on_mobile_only_pr() -> None:
    """계약 ② — 가드를 도는 잡의 `if`가 mobile 필터를 참조한다(= mobile-only PR에서도 발화).

    이 단언이 OPS-23의 핵심이다. 잡의 트리거가 backend 필터에만 걸려 있으면(또는 mobile 조건이
    빠지면) src/mobile/-only PR에서 스킵돼 PATH-05 유형의 우회가 재발한다 → RED.
    """
    jobs = _load_ci_jobs()
    running = _jobs_running_guard(jobs)
    assert running, "가드를 도는 잡이 없다 — 먼저 계약 ①을 보라."

    mobile_ref = "needs.changes.outputs.mobile"
    firing = {
        job_id: job
        for job_id, job in running.items()
        if isinstance(job.get("if"), str) and mobile_ref in job["if"]
    }
    assert firing, (
        "concept_reach 가드를 도는 잡은 있으나 그 `if`가 "
        f"`{mobile_ref}`를 참조하지 않는다 — mobile-only PR에서 발화하지 않는다(OPS-23 사각 재발). "
        "잡의 if를 `needs.changes.outputs.mobile == 'true'`로 켜라.\n"
        + "\n".join(f"  · 잡 {jid}: if={job.get('if')!r}" for jid, job in running.items())
    )


def test_changes_filter_still_matches_src_mobile() -> None:
    """계약 ③ — `changes` 잡의 mobile 필터가 `src/mobile/`를 포함한다.

    가드가 mobile==true에서 발화하도록 배선해도, mobile 플래그 자체가 src/mobile/ 변경을 잡지
    않으면 우회가 재발한다. 필터 정의(changes 잡의 run 스크립트)에 src/mobile/가 살아 있는지 동결.
    """
    jobs = _load_ci_jobs()
    changes = jobs.get("changes")
    assert isinstance(changes, dict), "changes 잡이 없다 — 경로 필터 정의를 읽을 수 없다."
    filter_scripts = [run for run in _iter_run_steps(changes) if "mobile" in run]
    assert filter_scripts, "changes 잡에서 mobile 출력을 세팅하는 스텝을 찾지 못했다."
    joined = "\n".join(filter_scripts)
    assert "src/mobile/" in joined, (
        "changes 잡의 mobile 필터가 `src/mobile/`를 포함하지 않는다 — 필터가 mobile 변경을 놓치면 "
        "concept_reach 가드 발화 배선이 있어도 우회가 재발한다."
    )


# ── 계약 ④ : 파서가 위장하지 않는지 ────────────────────────────────────────────


def test_parser_fails_loudly_on_broken_workflow() -> None:
    """계약 ④ — jobs가 비거나 없는 워크플로를 주면 '0건 통과'가 아니라 예외로 실패한다.

    실제 로더가 쓰는 `_extract_jobs`를 그대로 검증한다(중복 파서 금지) — 파서 무력화가 곧
    통과가 되면 안 되므로 결함 입력에서 실패 신호를 내는지 봉인.
    """
    with pytest.raises(AssertionError, match="jobs 블록이 비었다"):
        _extract_jobs({"name": "empty", "on": ["push"]}, source="fake.yml")
    with pytest.raises(AssertionError, match="jobs 블록이 비었다"):
        _extract_jobs({"jobs": {}}, source="fake.yml")
    with pytest.raises(AssertionError, match="매핑으로 파싱되지 않았다"):
        _extract_jobs(None, source="fake.yml")
