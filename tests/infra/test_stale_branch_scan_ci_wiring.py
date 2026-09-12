"""[HARN-47] 고립 브랜치 스캔의 **집행 지점 실재성** 동결.

왜 이 테스트가 있는가
--------------------
HARN-13이 만든 장기 미머지 브랜치 스캔은 **SessionStart 훅에서만 돌았다**. 사람이
대화형 세션을 열 때만 존재했고 CI에서는 한 번도 실행되지 않았다. 이 저장소는 같은
형태의 실패를 반복했다 — `tests/infra` 199건이 어떤 잡도 실행하지 않던 상태(OPS-03),
브랜치 보호 required check가 `enforcement_level=off`로 통째 미강제였던 상태(OPS-08),
`tests/infra`를 lint/format하는 잡이 없던 상태(OPS-11). "저장소에 존재함"과 "돌아감"은
다르다(CLAUDE.md "검증 장치를 만들고 배선 확인 없이 완료 선언 금지").

검증 계약
--------
① `ci.yml`의 `harness-integrity` 잡이 `backlog.py branches`를 실제로 호출한다.
② 그 잡의 checkout이 **`fetch-depth: 0`** 이다. 기본값(depth=1)이면 `is_shallow_repo`
   가드에 걸려 스캔이 **매 실행 "판정 보류"** 가 된다 — 초록으로 보이지만 상시 무력인
   상태이며, CLAUDE.md가 "상시 실패하는 fail-open 보호를 '보호 있음'으로 신뢰 금지"로
   금한 바로 그 형태다. 이 한 줄이 빠지면 스텝은 남아도 측정은 사라진다.
③ 스텝이 **측정 실패와 고립 0건을 구분**한다 — 판정 불가 경로에 별도 warning이 있다.
   두 상태가 같은 화면을 내면 검증이 아니라 위장이다.
④ 파서가 위장하지 않는다 — 파일을 못 읽거나 jobs가 비면 "0건 통과"가 아니라 **실패**.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

_REPO_ROOT = Path(__file__).resolve().parents[2]
_WORKFLOW = _REPO_ROOT / ".github" / "workflows" / "ci.yml"
_JOB = "harness-integrity"
_INVOCATION = "backlog.py branches"


def _job() -> dict:
    if not _WORKFLOW.is_file():
        pytest.fail(f"ci.yml이 없다: {_WORKFLOW}")
    data = yaml.safe_load(_WORKFLOW.read_text(encoding="utf-8"))
    jobs = (data or {}).get("jobs") or {}
    if not jobs:
        pytest.fail("ci.yml에 jobs가 없다 — 파서가 빈 결과를 통과로 위장하지 않는다")
    if _JOB not in jobs:
        pytest.fail(f"'{_JOB}' 잡이 사라졌다 — 고립 브랜치 관측의 집행 지점이 없다")
    return jobs[_JOB]


def _steps() -> list[dict]:
    steps = _job().get("steps") or []
    if not steps:
        pytest.fail(f"'{_JOB}' 잡에 steps가 없다")
    return steps


def test_scan_is_invoked_by_ci() -> None:
    """CI가_고립_브랜치_스캔을_실제로_호출한다"""
    bodies = "\n".join(str(s.get("run", "")) for s in _steps())
    assert _INVOCATION in bodies, (
        f"'{_INVOCATION}'를 호출하는 스텝이 없다 — 스캔이 다시 SessionStart 전용으로 "
        "돌아갔다(대화형 세션 밖에서는 아무도 고립을 보지 못한다)"
    )


def test_checkout_is_not_shallow() -> None:
    """스캔_잡의_checkout이_shallow가_아니다

    이 계약이 깨지면 스텝은 그대로 남고 CI도 초록인데 스캔만 영구 '판정 보류'가 된다 —
    가장 조용한 형태의 무력화라 기계로 붙든다.
    """
    checkouts = [s for s in _steps() if "actions/checkout" in str(s.get("uses", ""))]
    assert checkouts, f"'{_JOB}' 잡에 checkout 스텝이 없다"
    depths = [(s.get("with") or {}).get("fetch-depth") for s in checkouts]
    assert 0 in depths, (
        f"checkout fetch-depth가 {depths} — 0이 아니면 shallow 가드에 걸려 "
        "스캔이 매 실행 '판정 보류'가 된다(상시 무력 상태)"
    )


def test_measurement_failure_is_distinguished_from_zero() -> None:
    """측정_실패가_고립_0건과_구분된다"""
    step = next((s for s in _steps() if _INVOCATION in str(s.get("run", ""))), None)
    assert step is not None
    body = str(step["run"])
    assert "판정 불가" in body, (
        "판정 불가 경로의 별도 warning이 없다 — 인프라가 죽으면 '측정 실패'가 보여야지 "
        "'고립 0건 통과'로 위장되면 안 된다"
    )
    assert "continue-on-error" not in str(step), "실패 은닉 금지"
