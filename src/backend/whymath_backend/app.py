"""FastAPI 앱 — L3 라우터 ↔ Ollama 결선의 HTTP 표면 (M1.2-live S1).

엔드포인트:
  - GET  /health      — 라이브니스(의존성 없음, 항상 200)
  - GET  /status      — 레디니스(Ollama 도달성·모델 매트릭스 설치 여부 보고)
  - POST /v1/generate — 라우팅 → 캐시 → 생성 → 결정 메타데이터 + 생성 텍스트 반환

`create_app()`은 의존성(provider·cache·trace)을 주입받는 팩토리다 — 테스트는 가짜를
넣고, 프로덕션은 OllamaProvider + 인메모리 스텁(S1)을 기본으로 쓴다. Redis 캐시·
Langfuse 싱크는 후속 슬라이스(S2)에서 기본값을 교체한다.

경계 메모 (CLAUDE.md 절대 금기): /v1/generate가 돌려주는 텍스트는 *검증 전 원시 모델
출력*이다. 03 문서 환각 방어 파이프라인 통과 전에는 학생에게 직접 노출 금지
("LLM 응답을 검증 없이 학생에게 제공 금지").
"""

from __future__ import annotations

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from whymath_backend.l3 import pipeline
from whymath_backend.l3.interfaces import (
    CacheBackend,
    InMemoryCache,
    LLMProvider,
    RecordingTraceSink,
    TraceSink,
)
from whymath_backend.l3.models import RoutingDecision, RoutingRequest
from whymath_backend.l3.pipeline import QualityQueueUnavailableError
from whymath_backend.l3.providers.ollama import OllamaProvider, OllamaStatus

# 앱 state에 의존성을 보관할 때 쓰는 키.
_PROVIDER_KEY = "llm_provider"
_CACHE_KEY = "llm_cache"
_TRACE_KEY = "trace_sink"


# ──────────────────────────────────────────────────────────────────────────
# 요청/응답 스키마 (HTTP 표면)
# ──────────────────────────────────────────────────────────────────────────
class GenerateBody(BaseModel):
    """POST /v1/generate 본문 — 라우팅 입력 + 프롬프트.

    `request`는 라우팅 신호(RoutingRequest, extra=forbid)를 그대로 받는다. 평탄화
    대신 중첩을 쓰는 이유: RoutingRequest가 추가 필드를 금지하므로 prompt·system을
    섞으면 검증이 깨진다. 중첩이 필드 드리프트도 막는다.
    """

    request: RoutingRequest = Field(..., description="라우팅 입력 신호 (03a §B.1)")
    prompt: str = Field(..., description="사용자 프롬프트(검증 전 원시 입력)")
    system: str = Field(default="", description="시스템 프롬프트")


class GenerateResponseBody(BaseModel):
    """POST /v1/generate 응답 — 생성 텍스트 + 라우팅 메타데이터.

    `text`는 검증 전 원시 출력이다(앱 docstring 경계 메모 참조).
    """

    text: str = Field(..., description="생성된 원시 텍스트(검증 전 — 학생 직접 노출 금지)")
    cache_hit: bool = Field(..., description="캐시 적중 여부 (KPI, 03a §F.1)")
    decision: RoutingDecision = Field(..., description="라우팅 결정 메타데이터 (03a §G)")


class ModelAvailabilityBody(BaseModel):
    """/status 모델 항목."""

    model_id: str
    present: bool


class StatusBody(BaseModel):
    """GET /status 응답 — Ollama 레디니스 보고."""

    ready: bool = Field(..., description="도달 가능 + 모든 라우팅 모델 설치 여부")
    reachable: bool = Field(..., description="Ollama 데몬 도달 가능 여부")
    models: list[ModelAvailabilityBody] = Field(..., description="라우팅 모델별 설치 여부")
    missing: list[str] = Field(..., description="미설치 모델 ID 목록")
    error: str | None = Field(default=None, description="도달 실패 시 사유(비크래시)")


# ──────────────────────────────────────────────────────────────────────────
# 의존성 접근자 — app.state에 주입된 구현을 꺼낸다.
# Request.app.state 경유(FastAPI 관용 패턴) — 팩토리 클로저 변수에 의존하지 않아
# TestClient/스레드풀 컨텍스트에서도 안전하다.
# ──────────────────────────────────────────────────────────────────────────
def _get_provider(request: Request) -> LLMProvider:
    provider: LLMProvider = getattr(request.app.state, _PROVIDER_KEY)
    return provider


def _get_cache(request: Request) -> CacheBackend:
    cache: CacheBackend = getattr(request.app.state, _CACHE_KEY)
    return cache


def _get_trace(request: Request) -> TraceSink:
    trace: TraceSink = getattr(request.app.state, _TRACE_KEY)
    return trace


def create_app(
    *,
    provider: LLMProvider | None = None,
    cache: CacheBackend | None = None,
    trace: TraceSink | None = None,
) -> FastAPI:
    """FastAPI 앱 팩토리 — 의존성 주입 가능.

    기본값(S1): OllamaProvider + InMemoryCache + RecordingTraceSink. 테스트는
    가짜 provider/cache/trace를 주입한다. Redis·Langfuse 기본값 교체는 S2.
    """
    app = FastAPI(
        title="WhyMath Backend — L3 생성 표면",
        version="0.1.0",
        summary="L3 라우터 ↔ Ollama 결선 (M1.2-live S1)",
    )
    app.state.__setattr__(_PROVIDER_KEY, provider if provider is not None else OllamaProvider())
    app.state.__setattr__(_CACHE_KEY, cache if cache is not None else InMemoryCache())
    app.state.__setattr__(_TRACE_KEY, trace if trace is not None else RecordingTraceSink())

    @app.get("/health", tags=["ops"])
    async def health() -> dict[str, str]:
        """라이브니스 — 의존성 없이 프로세스 생존만 확인."""
        return {"status": "ok"}

    @app.get("/status", tags=["ops"], response_model=StatusBody)
    async def get_status(request: Request) -> StatusBody:
        """레디니스 — Ollama 도달성 + 라우팅 모델 매트릭스 설치 여부 보고.

        Ollama가 죽어 있어도 500을 던지지 않는다 — `reachable=false`로 *보고*한다.
        도달성 점검은 OllamaProvider만 노출하므로, 주입된 provider가 점검 메서드를
        제공하지 않으면(가짜 등) 도달 불가로 간주한다.
        """
        provider = _get_provider(request)
        ollama_status: OllamaStatus
        check = getattr(provider, "check_status", None)
        if check is None:
            ollama_status = OllamaStatus(
                reachable=False, models=(), error="provider has no status check"
            )
        else:
            ollama_status = await check()
        return StatusBody(
            ready=ollama_status.all_present,
            reachable=ollama_status.reachable,
            models=[
                ModelAvailabilityBody(model_id=m.model_id, present=m.present)
                for m in ollama_status.models
            ],
            missing=list(ollama_status.missing),
            error=ollama_status.error,
        )

    @app.post("/v1/generate", tags=["l3"], response_model=GenerateResponseBody)
    async def post_generate(
        body: GenerateBody, request: Request
    ) -> GenerateResponseBody | JSONResponse:
        """라우팅 → 캐시 → 생성. 라우팅 메타데이터 + 생성 텍스트 반환.

        반환 텍스트는 *검증 전 원시 출력*이다 — 03 문서 환각 방어 파이프라인을 통과하기
        전에는 학생에게 직접 노출 금지 (CLAUDE.md 절대 금기). 환각 방어·학생 표면화는
        상위 계층(L4/L5 오케스트레이터)의 책임이다.

        QUALITY(27b)로 라우팅되면 동기 호출이 불가하므로(03a §D.3) 503으로 명확히
        보고한다(500 스택트레이스 노출 금지). 비동기 큐 경로는 슬라이스 S4.
        """
        provider = _get_provider(request)
        cache = _get_cache(request)
        trace = _get_trace(request)
        try:
            result = await pipeline.generate(
                body.request,
                body.prompt,
                body.system,
                provider=provider,
                cache=cache,
                trace=trace,
            )
        except QualityQueueUnavailableError as exc:
            # QUALITY 비동기 전용 — 명확한 4xx/5xx JSON(스택트레이스 금지).
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={
                    "error": "quality_queue_unavailable",
                    "message": str(exc),
                    "detail": "QUALITY(27b)는 비동기 큐 전용입니다 — 슬라이스 S4 (03a §D.3).",
                },
            )
        return GenerateResponseBody(
            text=result.text,
            cache_hit=result.cache_hit,
            decision=result.decision,
        )

    return app
