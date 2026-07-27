"""프로젝트 루트 conftest.

목적:
  - pytest가 *어디서 실행되든* `data_pipeline` 등 소스 패키지를 import 가능하게.
  - 테스트 디렉토리(tests/data_pipeline)와 소스 패키지(src/data-pipeline/data_pipeline)의
    이름 충돌을 sys.path 우선순위로 회피.
  - **무작위 순서 seed를 항상 노출**(OPS-09) — 아래 `pytest_configure` 참조.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_PROJECT_ROOT = Path(__file__).parent.resolve()
_SRC_DATA_PIPELINE = _PROJECT_ROOT / "src" / "data-pipeline"

# 소스 패키지 경로를 sys.path 가장 앞에 두어 동명 디렉토리 충돌 회피
if str(_SRC_DATA_PIPELINE) not in sys.path:
    sys.path.insert(0, str(_SRC_DATA_PIPELINE))


@pytest.hookimpl(trylast=True)
def pytest_configure(config: object) -> None:
    """무작위 순서 seed를 **stdout에 항상** 찍는다 (OPS-09).

    `trylast=True` 필수: pytest-randomly는 자신의 `pytest_configure`에서 `--randomly-seed`의
    기본값 문자열 `"default"`를 실제 정수로 *확정*한다. 우리 훅이 먼저 돌면 확정 전 값인
    `"default"`를 찍어 **재현에 쓸 수 없는 문자열**이 로그에 남는다(2026-07-27 실측 — 첫
    구현이 정확히 이 함정에 빠졌다). 마지막에 돌아야 확정된 정수를 본다.

    왜 pytest-randomly의 기본 헤더로 충분하지 않은가: 그 헤더(`Using --randomly-seed=N`)는
    `-q`에서 **출력되지 않는다**(2026-07-27 실측). 그런데 이 저장소의 CI는 전 스위트를 `-q`로
    돌린다 — 그대로 두면 무작위 순서로 실패했을 때 **어떤 순서였는지 알 수 없어 재현이
    불가능**하다. 재현할 수 없는 빨강은 고칠 수 없는 빨강이고, 그러면 무작위화는 이득보다
    손해가 된다(도입 전제 붕괴).

    `pytest_configure`의 `print`는 캡처 시작 전이라 `-q`에서도 살아남는다. 플러그인이 없으면
    (`randomly_seed` 부재) 조용히 아무것도 하지 않는다 — 무작위화를 쓰지 않는 실행에 소음 0.
    """
    seed = getattr(getattr(config, "option", None), "randomly_seed", None)
    if seed is not None:
        # 재현 명령을 값과 함께 출력 — 로그만 보고 바로 되먹일 수 있어야 한다.
        print(
            f"[order] randomly-seed={seed}  (재현: pytest ... -p randomly --randomly-seed={seed})"
        )
