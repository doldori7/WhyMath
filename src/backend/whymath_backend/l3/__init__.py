"""L3 LLM 라우터 + 라이브 어댑터 (M1.2 — 결정 로직 + Protocol 구현 + 오케스트레이션).

설계 정본: `docs/architecture/03a_l3_router_design.md`.

공개 API:
  - models: enums(CostTier·ModelFamily·LocalModelTier·CallSite)·RoutingRequest·
    RoutingDecision
  - router: Router.route() — 축1(C.1) → [LOCAL이면] 축3(C.0) → 축2(C.2) 순차 결정
  - interfaces: LLMProvider·CacheBackend·TraceSink·AsyncJobQueue Protocol +
    테스트용 인메모리 스텁(InMemoryCache·RecordingTraceSink)
  - providers: OllamaProvider·AnthropicProvider·RoutingLLMProvider — LLMProvider 라이브 구현
  - cache: RedisCacheBackend — CacheBackend 라이브 구현
  - tracing: LangfuseTraceSink — TraceSink 라이브 구현
  - queue: CeleryJobQueue — AsyncJobQueue 라이브 구현(QUALITY 비동기, 03a §D.3)
  - service: GenerationService·GenerationResult — 라우팅·캐싱·큐잉·관측성 오케스트레이션

범위 메모(M1.2): SDK(ollama/anthropic/redis/langfuse/celery) import는 전부 *lazy*
(각 어댑터 함수 내부) — 모듈 로드·테스트 수집은 라이브 SDK 없이 통과한다. 실제
라이브 호출은 통합 테스트(@pytest.mark.integration, 기본 skip)로만 수행한다.
"""

from whymath_backend.l3.cache import RedisCacheBackend
from whymath_backend.l3.interfaces import (
    AsyncJobQueue,
    CacheBackend,
    InMemoryCache,
    LLMProvider,
    RecordingTraceSink,
    TraceSink,
)
from whymath_backend.l3.models import (
    CallSite,
    CostTier,
    LocalModelTier,
    ModelFamily,
    RoutingDecision,
    RoutingRequest,
)
from whymath_backend.l3.providers import (
    AnthropicProvider,
    OllamaProvider,
    RoutingLLMProvider,
)
from whymath_backend.l3.queue import CeleryJobQueue
from whymath_backend.l3.router import Router
from whymath_backend.l3.service import GenerationResult, GenerationService
from whymath_backend.l3.tracing import LangfuseTraceSink

__all__ = [
    # 스키마
    "CallSite",
    "CostTier",
    "LocalModelTier",
    "ModelFamily",
    "RoutingDecision",
    "RoutingRequest",
    # 라우터
    "Router",
    # Protocol 경계 + 스텁
    "LLMProvider",
    "CacheBackend",
    "TraceSink",
    "AsyncJobQueue",
    "InMemoryCache",
    "RecordingTraceSink",
    # 라이브 어댑터
    "OllamaProvider",
    "AnthropicProvider",
    "RoutingLLMProvider",
    "RedisCacheBackend",
    "LangfuseTraceSink",
    "CeleryJobQueue",
    # 오케스트레이션
    "GenerationService",
    "GenerationResult",
]
