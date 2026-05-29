"""tests/data_pipeline/conftest.py — 테스트 모듈 임포트 전에 sys.path 조정 + 통합 게이트.

pytest는 conftest.py를 *해당 디렉토리의 테스트 모듈*보다 먼저 import한다.
이 파일은 `data_pipeline` 동명 디렉토리(tests/data_pipeline 자체)와
실제 소스 패키지(src/data-pipeline/data_pipeline) 충돌을 회피하기 위해
sys.path 우선순위를 명시적으로 설정.

통합 테스트 게이트: `@pytest.mark.integration`은 라이브 서비스(실 PostgreSQL 등)를 요구하므로
CI(라이브 서비스 없음·`[postgres]` extra 미설치)에서는 기본 *skip*한다. 실행하려면 환경변수
`WHYMATH_RUN_INTEGRATION`을 truthy(1/true/yes/on)로 설정한다 — backend(tests/backend/conftest.py)
와 동일 게이트·환경변수를 공유한다(프로젝트 단일 컨벤션).
"""

from __future__ import annotations

import os
import sys
from collections.abc import Iterable
from pathlib import Path

import pytest

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_SRC_DATA_PIPELINE = _PROJECT_ROOT / "src" / "data-pipeline"

# 동명 충돌 회피: 소스 경로를 가장 앞으로
src_path_str = str(_SRC_DATA_PIPELINE)
if src_path_str in sys.path:
    sys.path.remove(src_path_str)
sys.path.insert(0, src_path_str)

# 이미 잘못 import된 data_pipeline 모듈이 있다면 강제로 비우고 재import 가능 상태
_to_purge = [
    m for m in list(sys.modules.keys()) if m == "data_pipeline" or m.startswith("data_pipeline.")
]
for m in _to_purge:
    mod = sys.modules.get(m)
    # 실제 소스 위치가 아닌 경우만 purge (안전장치)
    if (
        mod is not None
        and getattr(mod, "__file__", "")
        and not str(mod.__file__).startswith(str(_SRC_DATA_PIPELINE))
    ):
        del sys.modules[m]

_RUN_INTEGRATION_ENV = "WHYMATH_RUN_INTEGRATION"
_TRUTHY = frozenset({"1", "true", "yes", "on"})


def _integration_enabled() -> bool:
    """환경변수로 통합 테스트가 켜져 있는지 판정."""
    return os.environ.get(_RUN_INTEGRATION_ENV, "").strip().lower() in _TRUTHY


def pytest_collection_modifyitems(config: pytest.Config, items: Iterable[pytest.Item]) -> None:
    """`integration` 마크 테스트를 기본 skip (환경변수로만 활성화).

    CI는 `WHYMATH_RUN_INTEGRATION`을 설정하지 않으므로 통합 테스트가 자동으로 빠진다 →
    라이브 PostgreSQL·`[postgres]` extra 없이도 CI green. 환경변수가 켜지면 그대로 수집·실행.
    """
    if _integration_enabled():
        return
    skip_integration = pytest.mark.skip(
        reason=f"통합 테스트는 기본 skip — 실행하려면 {_RUN_INTEGRATION_ENV}=1 설정"
    )
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip_integration)
