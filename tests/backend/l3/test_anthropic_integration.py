"""AnthropicProvider 통합 테스트 — 실제 Anthropic API 호출 (키 보유 시 Kiki 실행).

기본 SKIP(이중 게이트):
  1. `WHYMATH_RUN_INTEGRATION=1` — 통합 테스트 활성화(tests/backend/conftest.py 게이트).
     CI는 이 변수를 설정하지 않으므로 자동으로 빠진다.
  2. `WHYMATH_ANTHROPIC_API_KEY=sk-ant-...` — 키가 없으면 개별 테스트가 skip한다.

목적: 라우터 CLOUD_MID/CLOUD_HIGH 결정 → resolve_cloud_model → 실제 Claude(Sonnet/Opus)
호출이 e2e로 동작하는지, /status 클라우드 도달성 보고가 실키에서 맞는지 Kiki가 확인.
실측 비용/지연 보정·프롬프트 캐싱은 별도 후속(03a §H 후속 4).

설계 정본: docs/architecture/03a_l3_router_design.md §A.0·§C.1·§H 후속 4.
"""

from __future__ import annotations

import pytest

from whymath_backend.config import Settings
from whymath_backend.l3.models import CostTier, RoutingDecision
from whymath_backend.l3.providers.anthropic import AnthropicProvider

pytestmark = pytest.mark.integration


def _cloud_decision(cost: CostTier) -> RoutingDecision:
    return RoutingDecision(
        cost_tier=cost,
        local_family=None,
        local_model=None,
        mode="sync",
        reason="integration",
        est_latency_ms=3000,
        est_cost_krw=10.0,
    )


async def test_check_status_reports_configured_reachable_on_live_key() -> None:
    """실제 키로 models.list가 성공해 configured·reachable=True를 보고한다."""
    provider = AnthropicProvider(settings=Settings())
    if not provider.configured:
        pytest.skip("WHYMATH_ANTHROPIC_API_KEY 미설정 — 키 필요")
    st = await provider.check_status()
    assert st.configured is True
    assert st.reachable is True, f"Anthropic 도달/인증 실패: {st.error}"


async def test_generate_cloud_mid_sonnet_e2e() -> None:
    """CLOUD_MID(Sonnet 4.6) 실호출 — 비어 있지 않은 텍스트 반환."""
    provider = AnthropicProvider(settings=Settings())
    if not provider.configured:
        pytest.skip("WHYMATH_ANTHROPIC_API_KEY 미설정 — 키 필요")
    out = await provider.generate(
        "12 + 30 은 얼마인가? 숫자만 답하라.",
        "너는 간결한 수학 도우미다.",
        _cloud_decision(CostTier.CLOUD_MID),
    )
    assert isinstance(out, str)
    assert out.strip() != ""


async def test_generate_cloud_high_opus_e2e() -> None:
    """CLOUD_HIGH(Opus 4.7) 실호출 — 비어 있지 않은 텍스트 반환."""
    provider = AnthropicProvider(settings=Settings())
    if not provider.configured:
        pytest.skip("WHYMATH_ANTHROPIC_API_KEY 미설정 — 키 필요")
    out = await provider.generate(
        "소수가 무한히 많음을 한 문장으로 설명하라.",
        "너는 엄밀하고 간결한 수학 도우미다.",
        _cloud_decision(CostTier.CLOUD_HIGH),
    )
    assert isinstance(out, str)
    assert out.strip() != ""
