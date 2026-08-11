"""[HARN-27] 원격 claim 자동 청소의 **집행 지점 실재성** 동결.

왜 이 테스트가 있는가
--------------------
`claims reap --apply`는 **CLI에 존재했지만 그것을 부르는 자동 경로가 저장소 어디에도
없었다**. ci.yml은 dry-run만 돌리고 "`--apply`로 청소 권장"이라는 경고를 냈고, 그
명령은 아무도 실행하지 않았다 — 그래서 main에서 이미 `done`인 태스크의 claim조차
(HARN-20 실측) 영구히 남아 새 세션의 착수를 막았다. CLAUDE.md "정본화를 집행으로
착각한 완료 선언 금지"가 겨냥하는 바로 그 부류다(`test_session_start_brief_wiring.py`
HARN-14 · `test_test_suite_wiring.py` OPS-10 동형 선례).

검증 계약
--------
① `harness-audit.yml`이 존재하고 `claims reap --auto`를 실제로 호출한다.
② **`on:`에 `pull_request`가 없다** — "PR에서는 절대 지우지 않는다"를 조건문이 아니라
   트리거 부재로 증명한다. 누가 PR 트리거를 추가하면 RED.
③ 쓰기 권한이 이 워크플로 **잡 레벨**에 격리돼 있다(ci.yml로 새지 않는다).
④ 청소 스텝에 `|| true`·`continue-on-error`가 없다 — 실패를 은닉하면 자동 청소가
   상시 무력화돼도 초록으로 보인다.
⑤ 안전 사유 집합이 **YAML이 아니라 파이썬 상수**에 있다. 워크플로 인자로 사유를
   넘기면 여기를 고쳐 `ttl`까지 지우게 만들 수 있다.
⑥ 파서가 위장하지 않는다 — 파일을 못 읽거나 jobs가 비면 "0건 통과"가 아니라 **실패**.
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).resolve().parents[2]
_WORKFLOW = _REPO_ROOT / ".github" / "workflows" / "harness-audit.yml"
_REAP_INVOCATION = "claims reap --auto"

sys.path.insert(0, str(_REPO_ROOT / "scripts" / "harness"))


def _load_workflow() -> dict:
    if not _WORKFLOW.is_file():
        raise AssertionError(f"{_WORKFLOW} 이(가) 없다 — 자동 청소 집행 지점이 사라졌다.")
    data = yaml.safe_load(_WORKFLOW.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not data.get("jobs"):
        raise AssertionError(
            f"{_WORKFLOW} 파싱 결과에 jobs가 없다 — 파싱 실패를 '위반 0'으로 읽으면 안 된다."
        )
    return data


def _reap_job(data: dict) -> dict:
    for job in data["jobs"].values():
        for step in job.get("steps") or []:
            if _REAP_INVOCATION in str(step.get("run") or ""):
                return job
    raise AssertionError(
        f"'{_REAP_INVOCATION}' 를 실행하는 스텝이 없다 — dry-run만 돌던 상태로 되돌아갔다."
    )


def _reap_step(job: dict) -> dict:
    for step in job.get("steps") or []:
        if _REAP_INVOCATION in str(step.get("run") or ""):
            return step
    raise AssertionError("청소 스텝을 찾지 못했다.")


def test_auto_reap_step_is_wired() -> None:
    """① 자동 청소 스텝이 실제로 배선돼 있다."""
    _reap_job(_load_workflow())


def test_workflow_has_no_pull_request_trigger() -> None:
    """② PR 트리거 부재 — 조건문이 아니라 구조로 보장한다.

    `on:`에 pull_request가 있으면 fork PR이 쓰기 권한을 요구하는 스텝을 돌릴 수 있고,
    "PR에서는 skip"이 편집 한 줄로 깨지는 약속이 된다.
    """
    data = _load_workflow()
    # PyYAML은 `on:`을 boolean True로 파싱한다(YAML 1.1) — 두 키 모두 확인한다.
    triggers = data.get("on", data.get(True))
    assert isinstance(triggers, dict), f"on: 파싱 실패({triggers!r}) — 판정 불가"
    assert (
        "pull_request" not in triggers
    ), "harness-audit에 pull_request 트리거가 생겼다 — 자동 삭제가 PR 이벤트에 노출된다"
    assert "pull_request_target" not in triggers


def test_write_permission_is_scoped_to_the_reap_job() -> None:
    """③ 쓰기 권한이 잡 레벨에 격리돼 있다."""
    data = _load_workflow()
    job = _reap_job(data)
    assert (job.get("permissions") or {}).get(
        "contents"
    ) == "write", "청소 잡에 contents: write 가 없다 — harness-claims push가 403으로 실패한다"
    assert (data.get("permissions") or {}).get(
        "contents"
    ) != "write", "워크플로 레벨에서 write를 켜면 최소권한 원칙이 깨진다 — 잡 레벨로 좁혀라"


def test_reap_step_does_not_hide_failure() -> None:
    """④ 실패 은닉 금지 — `|| true`·continue-on-error 없음.

    자동 청소가 토큰·권한 문제로 상시 실패하는데 초록으로 보이면, 그것이 바로
    "상시 실패하는 fail-open 보호를 '보호 있음'으로 신뢰"하는 상태다.
    """
    step = _reap_step(_reap_job(_load_workflow()))
    assert "|| true" not in str(step.get("run") or "")
    assert step.get("continue-on-error") in (None, False)


def test_safe_reason_set_lives_in_code_not_yaml() -> None:
    """⑤ 안전 사유 집합은 파이썬 상수가 소유한다 — YAML에서 넓힐 수 없다."""
    import remote_claims

    assert remote_claims.AUTO_REAP_REASONS == frozenset({"task_done", "branch_gone"}), (
        "자동 청소 사유 집합이 바뀌었다. ttl·task_missing은 확정 신호가 아니다 — "
        "ttl은 살아 있는 장기 세션일 수 있고, task_missing은 CI 러너가 main만 보기 때문에 "
        "다른 브랜치에서 등재된 태스크를 구조적으로 '없음'으로 본다(HARN-15 맹점)."
    )
    run = str(_reap_step(_reap_job(_load_workflow())).get("run") or "")
    for leaked in ("task_done", "task_missing", "branch_gone", "--reasons"):
        assert leaked not in run, (
            f"워크플로 run에 사유 문자열('{leaked}')이 노출됐다 — 안전 집합의 정의가 "
            "YAML로 새면 파이썬 테스트가 그것을 동결하지 못한다"
        )
