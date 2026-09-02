"""[OPS-58 후속] 병렬화가 약화시킨 **교차 파일 오염 탐지력**의 복구 배선 동결.

왜 이 테스트가 있는가
--------------------
`backend — lint·type·test`가 `-n auto --dist loadfile`로 돌게 되면서(PR #944) 탐지력 하나가
조용히 깎였다. `loadfile`은 *같은 파일*의 테스트만 한 워커에 묶을 뿐 **파일이 다르면 다른
프로세스**다. 그래서 "파일 A가 프로세스 전역을 남기고 파일 B가 그 전역의 기본값을 단언한다"
형태의 오염은 두 파일이 서로 다른 워커에 배정되는 순간 **격리되어 보이지 않는다** — 직렬
전체 스위트라면 빨강이었을 것이 초록으로 통과한다. AGENTS.md가 "전체 스위트 통과만 회귀
없음의 근거 · 부분 실행은 순서 의존 오염을 못 본다"고 못 박은 바로 그 사각이며, xdist 워커는
구조적으로 그 '부분 실행'이다. 실사고 이력도 있다(OPS-06/07 — `db.session._engine`이 파일
경계를 넘어 다른 파일의 단언을 깼고, 파일 단위 실행에서는 재현되지 않았다).

해법은 병렬화를 되돌리는 것이 아니라 **탐지 축을 옮기는 것**이다: PR 경로는 병렬로 빠르게,
직렬 전건은 야간에. 이 파일은 그 야간 축이 *실제로 배선되어 있는지*를 기계로 붙든다 —
"워크플로에 썼다"와 "그 잡이 매일 밤 직렬로 전건을 돈다"는 다르다(OPS-03/08/11/24 선례).

검증 계약 (각 항목은 결함 주입으로 변별력을 확인한 것만)
------------------------------------------------------
① 직렬 전건 스텝이 **실재**한다 — pytest를 돌면서 `-n`/`--dist`를 주지 않는 스텝.
② 그 스텝이 **전건**이다 — 특정 파일·디렉터리로 대상을 좁히지 않는다(좁히면 그게 바로
   이 잡이 막으려던 '부분 실행'이 된다).
③ 그 잡이 **schedule 발화**다(`if: github.event_name == 'schedule'`) + 워크플로에 `schedule.cron`이
   실재한다. 야간이 아니면 PR 경로의 중복일 뿐 안전망이 아니고, 그렇다고 PR 경로에 26분을
   되돌려주면 이 PR의 취지 자체가 사라진다.
④ 그 스텝이 **fail-open이 아니다** — `continue-on-error: true`면 오염이 터져도 초록이다.
⑤ 그 스텝이 **실행기를 단독 호출하지 않는다** — bare `pytest`가 아니라 `python -m pytest`
   (CLAUDE.md "실행기 단독 호출 금지").
⑥ **짝이 성립한다** — PR 경로의 backend 잡은 여전히 병렬(`-n`)이다. 이 잡만 있고 PR이
   직렬로 되돌아갔다면 야간 잡은 순수 낭비이고, 반대로 PR이 병렬인데 이 잡이 사라지면
   탐지 사각이 복원된다. 두 축은 함께여야 의미가 있으므로 함께 동결한다.
⑦ 파서가 **위장하지 않는다** — ci.yml을 못 읽거나 jobs가 비면 "통과"가 아니라 실패한다.
⑧ 판정 함수의 **변별력을 상시 봉인**한다 — 합성 워크플로에 결함을 주입해(스텝 제거 ·
   `-n` 부착 · 대상 좁힘 · schedule 아님 · continue-on-error 부착 · bare pytest) 각각이 실제로
   검출됨을 매번 재확인하고, 양성 대조(정상 배선은 위반 0)도 둔다. 정상 입력에서 초록인
   것은 보호의 증거가 아니다(CLAUDE.md 2026-09-01).

의도적으로 검증하지 않는 것 (정직한 공백)
--------------------------------------
- **오염이 실제로 있는지**는 보지 않는다 — 그건 야간 실행 자신이 판정한다. 여기서 보는 것은
  "매일 밤 그 판정이 일어나는가"뿐이다.
- **cron 시각의 적정성**은 보지 않는다(스케줄 존재만 본다).
- **탐지 확률**은 정량화하지 않는다. 직렬이어도 순서는 무작위라(pytest-randomly) 특정 쌍의
  노출은 확률적이다 — 이 잡이 복원하는 것은 "같은 프로세스에서 전건이 돈다"는 *전제*이지
  탐지 보장이 아니다.
"""

from __future__ import annotations

import copy
import re
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest
import yaml

_REPO_ROOT = Path(__file__).resolve().parents[2]
_CI_PATH = _REPO_ROOT / ".github" / "workflows" / "ci.yml"

# 대상을 좁히는 인자로 간주할 접두 — 이게 붙으면 '전건'이 아니다(②).
_NARROWING_PREFIXES = ("tests/", "../../tests/", "./tests/")
# 병렬 분배 플래그 — 직렬 잡에 있으면 안 되고(①), PR 잡에는 있어야 한다(⑥).
_PARALLEL_FLAGS = ("-n", "--numprocesses", "--dist")
# schedule 발화 판정. **substring 금지** — 이 저장소의 PR 경로 잡들은 `if`에
# `github.event_name != 'schedule'`을 달고 있어서 `"schedule" in if`로 보면 *제외 조건*이
# *포함 조건*으로 뒤집힌다(실제로 이 가드의 첫 판을 그렇게 오작동시켰다). 등호 방향까지
# 읽는다 — 금지 문자열 열거가 아니라 구성된 의미를 보라는 CLAUDE.md 규칙의 적용.
_SCHEDULE_GATE_RE = re.compile(r"event_name\s*==\s*['\"]schedule['\"]")


def _is_schedule_gated(job: Mapping[str, Any]) -> bool:
    """`if:`가 schedule 발화를 *요구*하는가(`!= 'schedule'` 제외 조건과 구별한다)."""
    return bool(_SCHEDULE_GATE_RE.search(str(job.get("if") or "")))


def _load_workflow() -> dict[str, Any]:
    """ci.yml 파싱 — 못 읽거나 jobs가 비면 '통과'가 아니라 AssertionError(⑦)."""
    if not _CI_PATH.is_file():
        raise AssertionError(f"{_CI_PATH} 이(가) 없다 — 배선을 확인할 수 없다(위장 통과 금지).")
    spec: Any = yaml.safe_load(_CI_PATH.read_text(encoding="utf-8"))
    if not isinstance(spec, dict) or not spec.get("jobs"):
        raise AssertionError("ci.yml에 jobs가 없다 — 워크플로 파싱이 위장 통과할 수 없다.")
    return spec


def _tokens(script: str) -> list[str]:
    """줄 이음(`\\`)을 편 뒤 토큰화 — 여러 줄 `run:` 블록도 한 명령으로 본다."""
    return script.replace("\\\n", " ").split()


def _invokes_pytest_via_python_module(tokens: list[str]) -> bool:
    """`python -m pytest` 형태인가 — bare `pytest` 런처 단독 호출을 배제한다(⑤)."""
    for i, token in enumerate(tokens[:-2]):
        name = Path(token).name
        if name.startswith("python") and tokens[i + 1] == "-m" and tokens[i + 2] == "pytest":
            return True
    return False


def _is_pytest_run(tokens: list[str]) -> bool:
    """이 스크립트가 pytest를 *실행*하는가 — `pip install pytest...`를 배제한다.

    설치 줄을 실행으로 오인하면(`test_test_suite_wiring.py`가 겪은 형태) 배선이 없는데도
    있다고 판정한다. 그래서 `pytest`가 **실행 위치**(python -m 뒤 또는 첫 토큰)에 있을
    때만 실행으로 본다.
    """
    if not tokens:
        return False
    if _invokes_pytest_via_python_module(tokens):
        return True
    return Path(tokens[0]).name == "pytest"


def _has_parallel_flag(tokens: list[str]) -> bool:
    """`-n`/`--numprocesses`/`--dist`가 인자로 있는가(값 결합형 `-n4`·`--dist=loadfile` 포함)."""
    for token in tokens:
        if token in _PARALLEL_FLAGS:
            return True
        for flag in _PARALLEL_FLAGS:
            if (
                token.startswith(flag)
                and len(token) > len(flag)
                and token[len(flag)] in "=0123456789"
            ):
                return True
    return False


def _narrows_target(tokens: list[str]) -> bool:
    """테스트 경로 인자로 대상을 좁히는가 — 좁히면 '전건'이 아니다(②)."""
    return any(
        token.lstrip("./").startswith("tests/") for token in tokens if not token.startswith("-")
    )


def _pytest_steps(job: Mapping[str, Any]) -> list[tuple[dict[str, Any], list[str]]]:
    out: list[tuple[dict[str, Any], list[str]]] = []
    for step in job.get("steps") or []:
        if not isinstance(step, dict) or not step.get("run"):
            continue
        tokens = _tokens(str(step["run"]))
        if _is_pytest_run(tokens):
            out.append((step, tokens))
    return out


def serial_nightly_violations(spec: Mapping[str, Any]) -> list[str]:
    """야간 직렬 전건 배선의 계약 위반 목록(빈 리스트 = 정상). 순수 함수 — 합성으로 봉인 가능.

    위반은 사유 문자열로 모은다(뭉뚱그린 bool 금지 — 어느 축이 깨졌는지가 조치를 가른다).
    """
    violations: list[str] = []
    jobs = spec.get("jobs") or {}
    if not isinstance(jobs, dict) or not jobs:
        return ["ci.yml에 jobs가 없다 — 판정 불가(위장 통과 금지)."]

    # ① 직렬 전건 스텝 탐색 — pytest 실행 + 병렬 플래그 없음 + 대상 안 좁힘.
    found: list[tuple[str, dict[str, Any], dict[str, Any]]] = []
    for job_key, job in jobs.items():
        if not isinstance(job, dict):
            continue
        for step, tokens in _pytest_steps(job):
            if not _has_parallel_flag(tokens) and not _narrows_target(tokens):
                found.append((job_key, job, step))

    if not found:
        return [
            "직렬·전건 pytest 스텝이 ci.yml에 없다 — `--dist loadfile` 병렬화가 지운 교차 파일 "
            "오염 탐지력이 복구되지 않은 상태다(AGENTS.md '전체 스위트 통과만 회귀 없음의 근거')."
        ]

    # ③④⑤ — 후보 중 *하나라도* 전 계약을 만족하면 배선 성립. 만족하는 것이 없으면 각 후보의
    # 결격 사유를 모아 보고한다(어느 축이 깨졌는지 보이게).
    per_candidate: list[str] = []
    for job_key, job, step in found:
        reasons: list[str] = []
        if not _is_schedule_gated(job):
            reasons.append(
                "schedule 발화가 아니다(③) — PR 경로에 26분을 되돌려주거나 야간 안전망이 아니다"
            )
        if step.get("continue-on-error") is True:
            reasons.append("continue-on-error: true — 오염이 터져도 초록이다(④ fail-open 금지)")
        if not _invokes_pytest_via_python_module(_tokens(str(step["run"]))):
            reasons.append("bare `pytest` 단독 호출 — `python -m pytest`여야 한다(⑤)")
        if not reasons:
            break
        per_candidate.append(f"[{job_key}] " + " · ".join(reasons))
    else:
        violations.extend(per_candidate)

    # ③ 워크플로에 실제 schedule.cron이 있어야 한다 — 잡의 `if`만으로는 영원히 안 돈다.
    triggers = spec.get("on") if "on" in spec else spec.get(True)
    schedule = (triggers or {}).get("schedule") if isinstance(triggers, dict) else None
    if not schedule:
        violations.append(
            "워크플로에 schedule.cron이 없다 — schedule 발화 잡은 영원히 돌지 않는다(③)."
        )

    # ⑥ 짝 — PR 경로 backend 잡이 여전히 병렬인가.
    if not any(
        _has_parallel_flag(tokens)
        for job in jobs.values()
        if isinstance(job, dict) and not _is_schedule_gated(job)
        for _step, tokens in _pytest_steps(job)
    ):
        violations.append(
            "PR 경로에 병렬 pytest 스텝이 없다 — 야간 직렬 잡은 병렬화의 짝이다(⑥). "
            "병렬화를 되돌렸다면 이 야간 잡도 함께 정리해야 한다(순수 낭비)."
        )
    return violations


# ── 실 저장소 판정 ──────────────────────────────────────────────────────────


def test_serial_nightly_fullsuite_is_wired() -> None:
    """실 ci.yml이 야간 직렬 전건 배선 계약을 충족한다(①~⑥)."""
    assert serial_nightly_violations(_load_workflow()) == []


def test_parser_refuses_to_pass_on_unreadable_workflow(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ci.yml이 없으면 '통과'가 아니라 실패한다(⑦ 위장 통과 금지)."""
    monkeypatch.setattr(sys.modules[__name__], "_CI_PATH", tmp_path / "없는파일.yml")
    with pytest.raises(AssertionError):
        _load_workflow()


# ── 변별력 봉인 — 결함 주입 (⑧) ────────────────────────────────────────────


def _synthetic() -> dict[str, Any]:
    """정상 배선의 최소 합성 워크플로 — 여기에 결함을 주입해 검출을 확인한다."""
    return {
        "on": {"schedule": [{"cron": "0 18 * * *"}]},
        "jobs": {
            "backend": {
                "steps": [
                    {"name": "Pytest", "run": "python -m pytest -n auto --dist loadfile --cov=x"}
                ]
            },
            "backend-serial-nightly": {
                "if": "github.event_name == 'schedule'",
                "steps": [{"name": "Pytest", "run": "python -m pytest"}],
            },
        },
    }


def test_control_correct_wiring_has_no_violations() -> None:
    """양성 대조 — 정상 배선은 위반 0. (이게 깨지면 아래 결함 검출이 무의미하다.)"""
    assert serial_nightly_violations(_synthetic()) == []


def test_defect_serial_step_removed_is_detected() -> None:
    spec = _synthetic()
    del spec["jobs"]["backend-serial-nightly"]
    assert serial_nightly_violations(spec) != []


def test_defect_serial_step_gains_parallel_flag_is_detected() -> None:
    """야간 잡까지 병렬이 되면 직렬 축이 사라진다 — 검출돼야 한다."""
    spec = _synthetic()
    spec["jobs"]["backend-serial-nightly"]["steps"][0]["run"] = "python -m pytest -n auto"
    assert serial_nightly_violations(spec) != []


@pytest.mark.parametrize(
    "narrowed", ["python -m pytest ../../tests/backend/l4", "python -m pytest tests/backend"]
)
def test_defect_serial_step_narrowed_to_subset_is_detected(narrowed: str) -> None:
    """대상을 좁히면 그게 바로 이 잡이 막으려던 '부분 실행'이다(②)."""
    spec = _synthetic()
    spec["jobs"]["backend-serial-nightly"]["steps"][0]["run"] = narrowed
    assert serial_nightly_violations(spec) != []


def test_defect_serial_job_not_schedule_gated_is_detected() -> None:
    spec = _synthetic()
    del spec["jobs"]["backend-serial-nightly"]["if"]
    assert serial_nightly_violations(spec) != []


def test_defect_workflow_without_schedule_cron_is_detected() -> None:
    """잡은 schedule 발화인데 워크플로에 cron이 없으면 영원히 안 돈다(③)."""
    spec = _synthetic()
    del spec["on"]["schedule"]
    assert serial_nightly_violations(spec) != []


def test_defect_serial_step_fail_open_is_detected() -> None:
    spec = _synthetic()
    spec["jobs"]["backend-serial-nightly"]["steps"][0]["continue-on-error"] = True
    assert serial_nightly_violations(spec) != []


def test_defect_bare_pytest_launcher_is_detected() -> None:
    spec = _synthetic()
    spec["jobs"]["backend-serial-nightly"]["steps"][0]["run"] = "pytest"
    assert serial_nightly_violations(spec) != []


def test_defect_pr_job_reverted_to_serial_is_detected() -> None:
    """병렬화를 되돌렸는데 야간 잡만 남으면 순수 낭비 — 짝이 깨진 것을 검출한다(⑥)."""
    spec = _synthetic()
    spec["jobs"]["backend"]["steps"][0]["run"] = "python -m pytest --cov=x"
    assert serial_nightly_violations(spec) != []


def test_defect_empty_jobs_does_not_pass_vacuously() -> None:
    """스캔 0건은 실패다 — 대상을 못 찾은 전수 가드는 공허하게 통과한다(CLAUDE.md)."""
    assert (
        serial_nightly_violations({"on": {"schedule": [{"cron": "0 18 * * *"}]}, "jobs": {}}) != []
    )


def test_pip_install_line_is_not_mistaken_for_a_pytest_run() -> None:
    """`pip install pytest`가 직렬 전건 실행으로 오인되면 배선 없이도 통과한다."""
    spec = _synthetic()
    spec["jobs"]["backend-serial-nightly"]["steps"][0][
        "run"
    ] = "python -m pip install pytest pytest-xdist"
    assert serial_nightly_violations(spec) != []


def test_defect_injected_into_the_real_workflow_is_detected() -> None:
    """합성이 아니라 **실 ci.yml**에 결함을 주입해도 잡히는가 — 합성만 맞고 실물은 형태가
    달라 빠져나가는 경우를 배제한다(가드 자신이 위장일 수 있다 · 2026-09-01 PR #951 교훈)."""
    spec = copy.deepcopy(_load_workflow())
    jobs = spec["jobs"]
    for job in jobs.values():
        if isinstance(job, dict) and _is_schedule_gated(job):
            for step in job.get("steps") or []:
                if isinstance(step, dict) and step.get("run") and "pytest" in str(step["run"]):
                    step["run"] = str(step["run"]) + " -n auto"
    assert serial_nightly_violations(spec) != []


def test_schedule_gate_detection_reads_the_equality_direction() -> None:
    """`!= 'schedule'`(제외)을 `== 'schedule'`(요구)로 오판하지 않는다.

    이 가드의 첫 판이 정확히 그렇게 틀렸다 — `"schedule" in if` substring 검사가 PR 경로
    잡(`... && github.event_name != 'schedule'`)을 야간 잡으로 분류해 ⑥ 짝 판정을 뒤집었다.
    금지 문자열 열거가 아니라 **구성된 의미**를 보라는 CLAUDE.md 규칙(2026-09-01)의 사례라
    회귀로 못 박는다.
    """
    assert _is_schedule_gated({"if": "github.event_name == 'schedule'"})
    assert _is_schedule_gated({"if": 'github.event_name == "schedule"'})
    assert not _is_schedule_gated({"if": "a != 'schedule' && b == 'true'"})
    assert not _is_schedule_gated({})


def test_defect_removing_the_nightly_job_from_the_real_workflow_is_detected() -> None:
    """**실 ci.yml**에서 야간 직렬 잡을 지우면 잡히는가 — 합성만 맞고 실물은 다른 잡(예:
    data-pipeline의 직렬 pytest)이 대신 요건을 충족해 빠져나가는 경우를 배제한다."""
    spec = copy.deepcopy(_load_workflow())
    for key in [
        k for k, j in spec["jobs"].items() if isinstance(j, dict) and _is_schedule_gated(j)
    ]:
        del spec["jobs"][key]
    assert serial_nightly_violations(spec) != []
