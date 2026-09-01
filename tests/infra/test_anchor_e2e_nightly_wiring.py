"""[EOS-64 ①] 앵커 A4 생성 E2E 관통의 **야간 배선 실재성** 동결.

왜 이 테스트가 있는가
--------------------
EOS-58은 앵커 관통(생성→SymPy 게이트→dedup→코퍼스 저장→검수 큐)을 **1회** 실증했다. 1회
실증은 "그때 됐다"이지 "지금도 된다"가 아니다 — EOS-64 ①이 그것을 야간 상시 계측으로 승격
한다. 그런데 "워크플로 파일에 썼다"와 "그 잡이 이 관통을 돈다"는 다르다. 이 저장소는 정확히
그 간극으로 **반복해서** 사고를 냈다(`tests/infra` 199건 미실행·required check 미강제·
백필 가드 미배선 — OPS-03/OPS-08/OPS-11/OPS-24). 그래서 배선은 산문이 아니라 기계가 붙든다
(OPS-10 `test_test_suite_wiring.py` 선례의 *이 관통 전용* 축).

검증 계약 (각 항목은 변별력이 확인된 것만)
----------------------------------------
① 배선 **대상이 실재**한다 — `tests/backend/harness/test_eos_anchor_e2e_a4.py`가 디스크에 있다.
   대상이 없는데 워크플로에만 경로가 적혀 있으면 그 스텝은 매일 밤 수집 0건으로 초록이다.
② `ci.yml`에 그 파일을 **pytest로 실행하는 스텝**이 있다.
③ 그 스텝이 얹힌 잡이 **schedule 발화**다(`if: github.event_name == 'schedule'`) — 그리고
   워크플로에 실제 `schedule.cron`이 있다. 상시화의 뜻이 "매일 밤"이므로, 잡이 schedule에서
   안 돌면 이 배선은 push/PR 경로의 중복일 뿐 야간 안전망이 아니다.
④ 그 스텝이 **fail-open이 아니다** — `continue-on-error: true`가 붙어 있으면 관통이 깨져도
   잡은 초록이다. 상시 실패하는 fail-open 보호를 "보호 있음"으로 신뢰하지 않는다(CLAUDE.md).
⑤ 파서가 **위장하지 않는다** — ci.yml을 못 읽거나 jobs가 비면 "통과"가 아니라 실패한다.
⑥ 판정 함수의 **변별력을 상시 봉인**한다 — 합성 워크플로에 결함을 주입(스텝 제거·schedule
   아님·continue-on-error 부착·다른 테스트 파일로 교체)해 각각이 실제로 검출됨을 매번
   재확인하고, 양성 대조(정상 배선은 위반 0)도 함께 둔다.

의도적으로 검증하지 않는 것 (정직한 공백)
--------------------------------------
- **라이브(Ollama) 회차는 이 축이 아니다.** 이 관통은 hermetic(가짜는 LLM provider 하나)이라
  CI 러너에서 돈다. 라이브 회차의 상시 계측은 `<out>.rounds.jsonl` 회차 대장 + 연속 무진전
  알람(EOS-64 ④)이 담당하며 CI 배선 대상이 아니다(자격증명·GPU를 CI에 들이지 않는다).
- **cron 시각의 적정성**은 보지 않는다(스케줄 존재만 본다).
- **그 관통이 통과하는지**는 이 파일의 관심이 아니다 — 그건 관통 테스트 자신이 판정한다.
  여기서 보는 것은 "매일 밤 그 판정이 실제로 일어나는가"뿐이다.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml

_REPO_ROOT = Path(__file__).resolve().parents[2]
_CI_PATH = _REPO_ROOT / ".github" / "workflows" / "ci.yml"

# 배선 대상 — EOS-58 앵커 관통(hermetic). 워크플로의 인자는 `src/backend` 기준 상대경로라
# `../../`가 붙는다 — 비교는 정규화 후 **접미사 일치**로 한다.
ANCHOR_TEST_PATH = "tests/backend/harness/test_eos_anchor_e2e_a4.py"


def _load_workflow() -> dict[str, Any]:
    """ci.yml 파싱 — 못 읽거나 jobs가 비면 '통과'가 아니라 AssertionError(⑤)."""
    if not _CI_PATH.is_file():
        raise AssertionError(
            f"{_CI_PATH} 이(가) 없다 — 야간 배선을 확인할 수 없다(위장 통과 금지)."
        )
    spec: Any = yaml.safe_load(_CI_PATH.read_text(encoding="utf-8"))
    if not isinstance(spec, dict) or not spec.get("jobs"):
        raise AssertionError("ci.yml에 jobs가 없다 — 워크플로 파싱이 위장 통과할 수 없다.")
    return spec


def _runs_anchor_pytest(script: str, *, test_path: str) -> bool:
    """이 `run` 스크립트가 앵커 관통 테스트를 pytest로 도는가(경로 정규화 후 접미사 일치)."""
    normalized = script.replace("\\\n", " ")
    if "pytest" not in normalized:
        return False
    for token in normalized.split():
        if token.lstrip("./").endswith(test_path) or token.endswith(test_path):
            return True
    return False


def anchor_wiring_violations(
    spec: Mapping[str, Any], *, test_path: str = ANCHOR_TEST_PATH
) -> list[str]:
    """야간 배선 계약 위반 목록(빈 리스트 = 배선 정상) — 순수 함수라 합성 워크플로로 봉인 가능.

    ②~④를 한 함수가 판정한다: 스텝 실재 → schedule 발화 → fail-open 아님. 위반은 사유
    문자열로 모은다(뭉뚱그린 bool 금지 — 어느 축이 깨졌는지가 조치를 가른다).
    """
    violations: list[str] = []
    jobs = spec.get("jobs") or {}
    if not isinstance(jobs, dict) or not jobs:
        return ["ci.yml에 jobs가 없다 — 판정 불가(위장 통과 금지)."]

    found: list[tuple[str, dict[str, Any], dict[str, Any]]] = []
    for job_key, job in jobs.items():
        if not isinstance(job, dict):
            continue
        for step in job.get("steps") or []:
            if not isinstance(step, dict) or not step.get("run"):
                continue
            if _runs_anchor_pytest(str(step["run"]), test_path=test_path):
                found.append((job_key, job, step))

    if not found:
        return [
            f"`{test_path}`를 pytest로 도는 스텝이 ci.yml에 없다 — 앵커 관통 상시화(EOS-64 ①)가 "
            "배선되지 않았다(코드는 존재하나 매일 밤 아무도 돌리지 않는 상태)."
        ]

    # ③ schedule 발화 — 하나라도 야간 잡에 얹혀 있어야 '상시화'다.
    scheduled = [
        (job_key, job, step)
        for job_key, job, step in found
        if "== 'schedule'" in str(job.get("if", "")).replace('"', "'")
    ]
    if not scheduled:
        violations.append(
            "앵커 관통 스텝이 schedule 발화 잡에 없다 — push/PR 경로의 중복 실행일 뿐 야간 "
            "안전망이 아니다(상시화의 뜻은 '매일 밤 다시 돈다')."
        )
    on_spec = spec.get("on") or spec.get(True)  # YAML 1.1에서 bare `on:`은 True로 파싱된다
    schedule = (on_spec or {}).get("schedule") if isinstance(on_spec, dict) else None
    if not schedule:
        violations.append(
            "워크플로에 schedule(cron) 트리거가 없다 — schedule 전용 잡은 영원히 발화하지 않는다."
        )

    # ④ fail-open 금지 — 관통이 깨져도 초록인 스텝은 보호가 아니다.
    for job_key, _job, step in scheduled or found:
        if str(step.get("continue-on-error", "false")).lower() == "true":
            violations.append(
                f"`{job_key}` 잡의 앵커 관통 스텝에 continue-on-error: true가 붙어 있다 — "
                "관통이 깨져도 잡이 초록이라 보호가 아니다(fail-open 상시 실패 금지)."
            )
    return violations


# ══════════════════════════════════════════════════════════════════════════
# 실 워크플로 판정
# ══════════════════════════════════════════════════════════════════════════
def test_anchor_e2e_test_file_exists() -> None:
    """① 배선 대상이 실재한다 — 없으면 야간 스텝은 매일 수집 0건으로 초록이다."""
    target = _REPO_ROOT / ANCHOR_TEST_PATH
    assert target.is_file(), (
        f"{target} 이(가) 없다 — ci.yml이 가리키는 관통 테스트가 사라지면 스텝은 조용히 "
        "'수집 0건 통과'가 된다(측정 실패가 통과로 위장되는 형태)."
    )


def test_anchor_e2e_is_wired_into_nightly_schedule() -> None:
    """②③④ 실 ci.yml이 앵커 관통을 schedule 잡에서 fail-closed로 돈다."""
    violations = anchor_wiring_violations(_load_workflow())
    assert violations == [], "야간 배선 계약 위반:\n" + "\n".join(f"- {v}" for v in violations)


def test_parser_refuses_to_pass_on_broken_workflow() -> None:
    """⑤ 파서가 위장하지 않는다 — jobs 없는 워크플로는 '위반 0'이 아니라 위반으로 잡힌다."""
    assert anchor_wiring_violations({"jobs": {}}) != []
    assert anchor_wiring_violations({}) != []


# ══════════════════════════════════════════════════════════════════════════
# ⑥ 변별력 봉인 — 결함 주입이 실제로 검출되는지 매번 재확인
# ══════════════════════════════════════════════════════════════════════════
def _synthetic_workflow(
    *,
    run: str = f"pytest ../../{ANCHOR_TEST_PATH}",
    job_if: str = "github.event_name == 'schedule'",
    continue_on_error: bool = False,
    with_schedule: bool = True,
) -> dict[str, Any]:
    """정상 배선 1건짜리 합성 워크플로 — 인자로 축 하나씩 깨뜨려 검출을 확인한다."""
    step: dict[str, Any] = {"name": "앵커 관통", "run": run}
    if continue_on_error:
        step["continue-on-error"] = True
    spec: dict[str, Any] = {
        "on": {"push": {"branches": ["main"]}},
        "jobs": {"e2e-nightly": {"if": job_if, "steps": [step]}},
    }
    if with_schedule:
        spec["on"]["schedule"] = [{"cron": "0 18 * * *"}]
    return spec


def test_positive_control_synthetic_wiring_passes() -> None:
    """양성 대조 — 정상 합성 배선은 위반 0(무차별 실패가 아님을 보인다)."""
    assert anchor_wiring_violations(_synthetic_workflow()) == []


def test_detects_missing_step() -> None:
    """결함 주입 ⓐ — 앵커 관통 스텝을 지우면 검출된다."""
    broken = _synthetic_workflow(run="pytest ../../tests/backend/api/test_something_else.py")
    assert anchor_wiring_violations(broken) != []


def test_detects_non_pytest_step() -> None:
    """결함 주입 ⓑ — 경로만 언급하고 pytest로 돌지 않으면 배선이 아니다."""
    broken = _synthetic_workflow(run=f"echo ../../{ANCHOR_TEST_PATH}")
    assert anchor_wiring_violations(broken) != []


def test_detects_non_schedule_job() -> None:
    """결함 주입 ⓒ — 스텝이 schedule 잡 밖으로 옮겨지면 '상시화'가 아니다."""
    broken = _synthetic_workflow(job_if="github.event_name != 'schedule'")
    assert anchor_wiring_violations(broken) != []


def test_detects_missing_schedule_trigger() -> None:
    """결함 주입 ⓓ — cron 트리거가 사라지면 schedule 전용 잡은 영원히 안 돈다."""
    broken = _synthetic_workflow(with_schedule=False)
    assert anchor_wiring_violations(broken) != []


def test_detects_continue_on_error_fail_open() -> None:
    """결함 주입 ⓔ — continue-on-error: true는 보호가 아니라 위장이다."""
    broken = _synthetic_workflow(continue_on_error=True)
    assert anchor_wiring_violations(broken) != []
