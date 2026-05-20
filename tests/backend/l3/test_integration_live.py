"""L3 라이브 연동 통합 테스트 — 실제 Ollama·Anthropic·Redis·Celery·Langfuse 호출.

⚠️ 기본 skip. 이 컨테이너엔 GPU·Ollama·Redis·API키·Langfuse가 *없다*(라이브 E2E 불가).
실행하려면 라이브 서비스가 준비된 환경(예: Phaiakes9)에서 WHYMATH_RUN_INTEGRATION=1과
필요한 WHYMATH_* env(WHYMATH_OLLAMA_HOST·WHYMATH_ANTHROPIC_API_KEY·WHYMATH_REDIS_URL·
WHYMATH_LANGFUSE_* )를 설정한 뒤:

    WHYMATH_RUN_INTEGRATION=1 pytest -m integration tests/backend/l3/test_integration_live.py

설계 정본: docs/architecture/03a_l3_router_design.md §H 후속4(클라우드 연동)·후속6(큐 SLA).
범위 메모(M1.2): 단위테스트는 가짜 클라이언트로 *로직*을 검증하고(test_providers/cache/
queue/tracing/service.py), 이 파일은 *라이브 어댑터가 실제로 붙는지*만 별도로 확인한다.
CI·기본 실행에선 skip되어 커버리지·게이트에 영향을 주지 않는다.
"""

from __future__ import annotations

import os

import pytest

from whymath_backend.config import get_settings
from whymath_backend.l3.cache import RedisCacheBackend
from whymath_backend.l3.models import RoutingRequest
from whymath_backend.l3.providers import (
    AnthropicProvider,
    OllamaProvider,
    RoutingLLMProvider,
)
from whymath_backend.l3.router import Router
from whymath_backend.l3.service import GenerationService
from whymath_backend.l3.tracing import LangfuseTraceSink
from whymath_backend.l3.queue import CeleryJobQueue

# 모듈 전체를 통합 마커 + 환경변수 게이트로 묶는다 — 기본 실행에선 전부 skip.
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not os.getenv("WHYMATH_RUN_INTEGRATION"),
        reason="라이브 서비스 없음 (WHYMATH_RUN_INTEGRATION=1로 활성화)",
    ),
]


def _live_service() -> GenerationService:
    """settings(env)로 모든 라이브 어댑터를 조립한 GenerationService."""
    settings = get_settings()
    provider = RoutingLLMProvider(
        ollama=OllamaProvider(settings=settings),
        anthropic=AnthropicProvider(settings=settings),
    )
    return GenerationService(
        router=Router(),
        provider=provider,
        cache=RedisCacheBackend(settings=settings),
        trace=LangfuseTraceSink(settings=settings),
        queue=CeleryJobQueue(settings=settings),
        settings=settings,
    )


class TestLiveOllama:
    async def test_local_generation_returns_text(self) -> None:
        """라이브 Ollama로 LOCAL 경로 생성 — 비어있지 않은 텍스트를 받는다."""
        service = _live_service()
        req = RoutingRequest(
            task_type="explain",
            difficulty="easy",
            requires_reasoning=False,
            student_subscription="free",  # free → 항상 LOCAL
            budget_krw=0.0,
            sync=True,
            max_latency_ms=30000,
        )
        result = await service.generate(req, "2 + 3 은 얼마인가?", "너는 친절한 수학 코치다.")
        assert result.text is not None
        assert result.text.strip() != ""
        assert result.cache_hit is False


class TestLiveRedisCache:
    async def test_set_get_roundtrip(self) -> None:
        """라이브 Redis로 set 후 get 왕복."""
        cache = RedisCacheBackend(settings=get_settings())
        await cache.set("llm:cache:itest", "왕복값", ttl_seconds=60)
        assert await cache.get("llm:cache:itest") == "왕복값"
