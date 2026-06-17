"""tests/backend/conftest.py — 백엔드 테스트 임포트 경로 + 통합 테스트 게이트.

`whymath_backend`는 `pip install -e ".[dev]"`로 editable 설치되므로 보통은
import 경로 조정이 불필요하다. 다만 editable 설치 없이(예: 로컬에서 venv 미설치)
테스트를 돌릴 때도 동작하도록 소스 경로를 sys.path 앞에 둔다.

data-pipeline(tests/data_pipeline/conftest.py)과 달리 *동명 충돌이 없다*:
테스트 디렉토리는 `tests/backend`, 패키지는 `whymath_backend`로 이름이 다르다.
따라서 모듈 purge 로직은 불필요하고, 경로 보장만 한다.

통합 테스트 게이트 (M1.2-live S1 신규):
`@pytest.mark.integration`은 *라이브 서비스*(실제 Ollama 데몬 등)를 요구하므로
CI(라이브 서비스 없음)에서는 기본 *skip*한다. 실행하려면 환경변수
`WHYMATH_RUN_INTEGRATION`을 truthy(1/true/yes/on)로 설정한다 — Phaiakes9에서
Kiki가 켜고 돌린다. 프로젝트에 통합 게이트 선례가 없어 이 패턴을 여기서 확립한다.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Iterable
from pathlib import Path

import pytest

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_SRC_BACKEND = _PROJECT_ROOT / "src" / "backend"

# editable 설치가 없을 때를 대비한 안전장치: 소스 경로를 가장 앞으로
_src_path_str = str(_SRC_BACKEND)
if _src_path_str in sys.path:
    sys.path.remove(_src_path_str)
sys.path.insert(0, _src_path_str)

_RUN_INTEGRATION_ENV = "WHYMATH_RUN_INTEGRATION"
_TRUTHY = frozenset({"1", "true", "yes", "on"})


def _integration_enabled() -> bool:
    """환경변수로 통합 테스트가 켜져 있는지 판정."""
    return os.environ.get(_RUN_INTEGRATION_ENV, "").strip().lower() in _TRUTHY


def pytest_collection_modifyitems(config: pytest.Config, items: Iterable[pytest.Item]) -> None:
    """`integration` 마크 테스트를 기본 skip (환경변수로만 활성화).

    CI는 `WHYMATH_RUN_INTEGRATION`을 설정하지 않으므로 통합 테스트가 자동으로
    빠진다 → 라이브 Ollama 없이도 CI green. 환경변수가 켜지면 그대로 수집·실행.
    """
    if _integration_enabled():
        return
    skip_integration = pytest.mark.skip(
        reason=f"통합 테스트는 기본 skip — 실행하려면 {_RUN_INTEGRATION_ENV}=1 설정"
    )
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip_integration)
