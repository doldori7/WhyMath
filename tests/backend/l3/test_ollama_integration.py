"""OllamaProvider 통합 테스트 — 실제 Ollama 데몬 호출 (Phaiakes9 전용).

기본 SKIP. 실행하려면 환경변수 `WHYMATH_RUN_INTEGRATION=1`(+ 필요 시
`WHYMATH_OLLAMA_HOST`)를 설정한다. CI는 이 변수를 설정하지 않으므로 자동으로
빠진다(tests/backend/conftest.py의 pytest_collection_modifyitems 게이트).

목적: 라우터 결정 → resolve_model → 실제 Ollama 호출이 e2e로 동작하는지,
그리고 /status 도달성 보고가 실데몬에서 맞는지 Kiki가 Phaiakes9에서 확인.

설계 정본: docs/architecture/03a_l3_router_design.md §A.0·§A.1.
"""

from __future__ import annotations

import pytest
from whymath_backend.config import Settings
from whymath_backend.l3.models import (
    CostTier,
    LocalModelTier,
    ModelFamily,
    RoutingDecision,
)
from whymath_backend.l3.providers.ollama import OllamaProvider

pytestmark = pytest.mark.integration


async def test_status_reports_reachable_on_live_daemon() -> None:
    """실제 Ollama 데몬에 닿아 모델 매트릭스 설치 여부를 보고한다."""
    provider = OllamaProvider(settings=Settings())
    status = await provider.check_status()
    # 데몬이 살아 있으면 reachable=True. 모델 일부가 없을 수 있어 all_present은 단정 X.
    assert status.reachable is True, f"Ollama 도달 실패: {status.error}"


async def test_generate_local_fast_math_e2e() -> None:
    """LOCAL+MATH+FAST(qwen2-math:1.5b) 실호출 — 비어 있지 않은 텍스트 반환."""
    provider = OllamaProvider(settings=Settings())
    # 사전 점검: FAST 모델이 설치돼 있어야 의미 있는 호출이 된다.
    status = await provider.check_status()
    if not status.reachable:
        pytest.skip(f"Ollama 미도달: {status.error}")
    if "qwen2-math:1.5b" in status.missing:
        pytest.skip("qwen2-math:1.5b 미설치 — `ollama pull qwen2-math:1.5b` 필요")

    decision = RoutingDecision(
        cost_tier=CostTier.LOCAL,
        local_family=ModelFamily.MATH,
        local_model=LocalModelTier.FAST,
        mode="sync",
        reason="integration",
        est_latency_ms=1010,
        est_cost_krw=0.0,
    )
    out = await provider.generate(
        "12 + 30 은 얼마인가? 숫자만 답하라.",
        "너는 간결한 수학 도우미다.",
        decision,
    )
    assert isinstance(out, str)
    assert out.strip() != ""
