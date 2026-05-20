"""L3 LLM 라우터 (M1.2 — 결정 로직 + 타입 인터페이스).

설계 정본: `docs/architecture/03a_l3_router_design.md`.

공개 API:
  - models: enums(CostTier·ModelFamily·LocalModelTier·CallSite)·RoutingRequest·
    RoutingDecision
  - router: Router.route() — 축1(C.1) → [LOCAL이면] 축3(C.0) → 축2(C.2) 순차 결정
  - interfaces: LLMProvider·CacheBackend 등 Protocol(미구현) + 테스트용 인메모리 스텁

범위 메모: 본 모듈은 *결정 로직*과 *타입*만 구현한다. 실제 LLM 클라이언트
(Ollama/Anthropic)·Redis·Langfuse·비동기 큐는 Protocol/스텁으로만 두며 라이브
호출은 후속 마일스톤에서 연동한다(03a §H 후속 4·6).
"""

from whymath_backend.l3.models import (
    CallSite,
    CostTier,
    LocalModelTier,
    ModelFamily,
    RoutingDecision,
    RoutingRequest,
)
from whymath_backend.l3.router import Router

__all__ = [
    "CallSite",
    "CostTier",
    "LocalModelTier",
    "ModelFamily",
    "RoutingDecision",
    "RoutingRequest",
    "Router",
]
