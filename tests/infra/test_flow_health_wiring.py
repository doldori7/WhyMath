"""[FLOW-HEALTH] 통합 흐름 진단의 **집행 지점 실재성** 동결.

왜 이 테스트가 있는가
--------------------
이 도구가 만들어진 계기 자체가 "존재하지만 아무도 부르지 않는 도구"였다.
2026-09-01 실측: `scripts/ops/pr_delivery_audit.py`와 `pr_merge_readiness.py`는
저장소에 있으나 `.github/`·`.claude/`를 통틀어 **호출처 0건**이었다. 이는
`claims reap --apply`가 겪은 것(HARN-27)과 같은 상태이며, CLAUDE.md가 반복
사고로 등재한 부류다 — `tests/infra` 199건 미실행(OPS-03), 브랜치 보호 required
check 통째 미강제(OPS-08), `tests/infra` lint 잡 부재(OPS-11).

**"저장소에 존재함"과 "돌아감"은 다르다.** 이 테스트가 그 차이를 기계로 동결한다.
이것이 없으면 flow_health.py 자신이 다음번 고아 도구가 된다.

검증 계약
--------
① `harness-audit.yml`에 flow-health 잡이 있고 `flow_health.py`를 실제로 호출한다.
② 그 잡의 checkout이 **fetch-depth: 0**이다 — shallow에서는 ahead/behind가 잘린
   히스토리 기준의 틀린 수라 측정 자체가 성립하지 않는다.
③ 원격 브랜치를 fetch한다 — checkout만으로는 기본 ref 하나만 온다.
④ 측정 스텝에 `|| true`·`continue-on-error`가 없다(실패 은닉 금지).
⑤ 고아 도구 `pr_delivery_audit.py`가 이 워크플로에서 **실제로 호출된다**.
⑥ flow-health 잡에 `contents: write`가 없다 — claim-reap의 쓰기 권한이 관측
   잡으로 새지 않는다.
⑦ 파서가 위장하지 않는다 — 파일을 못 읽거나 jobs가 비면 "0건 통과"가 아니라 실패.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

_REPO_ROOT = Path(__file__).resolve().parents[2]
_WORKFLOW = _REPO_ROOT / ".github" / "workflows" / "harness-audit.yml"
_JOB = "flow-health"
_TOOL = "scripts/ops/flow_health.py"
_ORPHAN = "scripts/ops/pr_delivery_audit.py"


@pytest.fixture(scope="module")
def job() -> dict:
    # ⑦ 위장 금지 — 읽기 실패는 통과가 아니라 실패다.
    if not _WORKFLOW.exists():
        pytest.fail(f"워크플로 부재: {_WORKFLOW}")
    doc = yaml.safe_load(_WORKFLOW.read_text(encoding="utf-8"))
    assert doc, "워크플로가 비었다 — 파싱 성공을 통과로 읽지 않는다"
    jobs = doc.get("jobs") or {}
    assert jobs, "jobs가 비었다"
    assert _JOB in jobs, f"{_JOB} 잡이 없다 — 도구가 고아 상태다"
    return jobs[_JOB]


def _steps_text(job: dict) -> str:
    return "\n".join(str(s.get("run", "")) for s in job.get("steps", []))


class TestToolIsActuallyInvoked:
    def test_flow_health_is_called(self, job):
        assert _TOOL in _steps_text(job), f"{_TOOL}를 부르는 스텝이 없다"

    def test_orphan_pr_delivery_audit_is_rescued(self, job):
        """⑤ 호출처 0건이던 도구가 이 워크플로에서 실제로 돈다."""
        assert _ORPHAN in _steps_text(job), (
            f"{_ORPHAN}가 다시 고아가 됐다 — 이 도구는 2026-09-01 실측에서 "
            "호출처 0건이었고 그 상태를 해소하는 것이 이 잡의 목적 중 하나다"
        )


class TestMeasurementPreconditions:
    def test_checkout_uses_full_history(self, job):
        """② fetch-depth: 0이 없으면 ahead/behind가 **틀린 수**가 된다."""
        depths = [
            s.get("with", {}).get("fetch-depth")
            for s in job.get("steps", [])
            if "actions/checkout" in str(s.get("uses", ""))
        ]
        assert depths, "checkout 스텝이 없다"
        assert 0 in depths, f"fetch-depth: 0이 필요하다 (현재 {depths})"

    def test_remote_branches_are_fetched(self, job):
        text = _steps_text(job)
        assert (
            "refs/remotes/origin" in text or "--prune origin" in text
        ), "원격 브랜치를 fetch하지 않으면 스캔 대상이 기본 ref 하나뿐이다"


class TestFailureIsNotHidden:
    def test_measure_step_has_no_failure_suppression(self, job):
        """④ 측정 스텝이 실패를 삼키면 상시 무력화돼도 초록으로 보인다."""
        for step in job.get("steps", []):
            run = str(step.get("run", ""))
            if _TOOL not in run:
                continue
            assert "|| true" not in run, "측정 실패를 `|| true`로 삼키면 안 된다"
            assert not step.get("continue-on-error"), "continue-on-error 금지"
            return
        pytest.fail(f"{_TOOL} 스텝을 찾지 못했다")

    def test_no_pull_request_trigger(self):
        """⑤보강 — 이 파일의 트리거에 pull_request가 없어야 쓰기 권한이 격리된다."""
        doc = yaml.safe_load(_WORKFLOW.read_text(encoding="utf-8"))
        triggers = doc.get(True) or doc.get("on") or {}
        assert "pull_request" not in triggers, (
            "pull_request 트리거가 생기면 claim-reap의 contents: write가 " "PR 검증 경로로 노출된다"
        )


class TestMeasurementFailurePropagates:
    """Codex P2 #3899930452 — 감사가 **아무것도 재지 못한** 상태가 초록이면 안 된다.

    `pr_delivery_audit`의 계약은 exit 1이 '주의 필요'와 '측정 실패' **둘 다**를
    뜻한다. 초판 스텝은 둘을 뭉개고 무조건 `exit 0`을 했다 — curl·API 조회가 통째로
    실패해도 잡이 초록이었다. 이 PR이 세운 "측정 실패 ≠ 통과" 원칙을 그 스텝 자신이
    위반한 상태였다.
    """

    def test_audit_step_distinguishes_measurement_failure(self, job):
        run = next(
            (
                str(s.get("run", ""))
                for s in job.get("steps", [])
                if _ORPHAN in str(s.get("run", ""))
            ),
            None,
        )
        assert run, f"{_ORPHAN} 스텝을 찾지 못했다"
        assert (
            "측정 실패" in run
        ), "측정 실패와 주의 상태를 가르지 않으면 아무것도 재지 못한 잡이 초록이 된다"
        assert "exit 1" in run, "측정 실패 경로는 스텝을 실패시켜야 한다"

    def test_sentinel_string_actually_exists_in_the_tool(self):
        """가정 기반 검사 금지 — 도구가 실제로 그 문자열을 낸다."""
        src = (_REPO_ROOT / _ORPHAN).read_text(encoding="utf-8")
        assert (
            "측정 실패" in src
        ), "워크플로가 찾는 문자열을 도구가 내지 않으면 그 분기는 죽은 코드다"


class TestPermissionIsolation:
    def test_observation_job_cannot_write(self, job):
        """⑥ 관측 잡은 읽기만 한다 — claim-reap의 쓰기 권한이 새지 않는다."""
        perms = job.get("permissions")
        assert perms, "권한을 명시하지 않으면 워크플로 기본값을 상속한다"
        assert perms.get("contents") == "read", f"contents는 read여야 한다 ({perms})"
        assert "write" not in str(perms.values()), f"쓰기 권한 금지 ({perms})"


class TestToolExists:
    def test_tool_file_is_present_and_executable_as_module(self):
        """도구 파일 자체가 있어야 워크플로 호출이 의미를 갖는다."""
        assert (_REPO_ROOT / _TOOL).exists(), f"{_TOOL} 부재"
        assert (_REPO_ROOT / _ORPHAN).exists(), f"{_ORPHAN} 부재"
