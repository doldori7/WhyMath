"""FastAPI 앱 — L3 라우터 ↔ Ollama·Celery 결선의 HTTP 표면 (M1.2-live S1·S4).

엔드포인트:
  - GET  /health         — 라이브니스(의존성 없음, 항상 200)
  - GET  /status         — 레디니스(Ollama 도달성·모델 매트릭스 설치 여부 보고)
  - POST /v1/generate    — 라우팅 → (동기) 캐시·생성 텍스트 / (비동기 QUALITY) 202 + job_id
  - GET  /v1/jobs/{id}   — QUALITY 비동기 작업 폴링(상태 + 완료 시 텍스트, S4)

`create_app()`은 의존성(provider·cache·trace·queue)을 주입받는 팩토리다 — 테스트는
가짜를 넣고, 프로덕션은 OllamaProvider + RedisCache(S2) + LangfuseSink(S3) +
CeleryJobQueue(S4)를 기본으로 쓴다. 넷 모두 *지연*이라 앱 구성만으로 라이브 Redis·
Langfuse·Celery broker가 필요하지 않다(첫 사용 시 연결). LangfuseSink는 키 미설정 시
영구 no-op이라 CI에서도 안전하다 — 트레이싱 장애는 학생 생성을 절대 깨뜨리지 않는다
(CLAUDE.md 우선순위 #1 ≫ #6).

경계 메모 (CLAUDE.md 절대 금기): /v1/generate·/v1/jobs가 돌려주는 텍스트는 *검증 전
원시 모델 출력*이다. 03 문서 환각 방어 파이프라인 통과 전에는 학생에게 직접 노출 금지
("LLM 응답을 검증 없이 학생에게 제공 금지").
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from whymath_backend.api._device_store import (
    build_device_store_from_settings,
    ping_device_store_health,
    set_device_store,
)
from whymath_backend.api.coach import router as coach_router
from whymath_backend.api.concepts import router as concepts_router
from whymath_backend.api.devices import router as devices_router
from whymath_backend.api.me import router as me_router
from whymath_backend.api.problems import router as problems_router
from whymath_backend.api.users import router as users_router
from whymath_backend.config import get_settings
from whymath_backend.db.session import dispose_engine
from whymath_backend.l3 import pipeline
from whymath_backend.l3.cache import RedisCache
from whymath_backend.l3.interfaces import (
    AsyncJobQueue,
    CacheBackend,
    LLMProvider,
    TraceSink,
)
from whymath_backend.l3.models import RoutingDecision, RoutingRequest
from whymath_backend.l3.pipeline import QualityQueueUnavailableError
from whymath_backend.l3.pregenerate.validator import default_seed_validator
from whymath_backend.l3.providers.anthropic import AnthropicProvider, AnthropicStatus
from whymath_backend.l3.providers.composite import CompositeProvider
from whymath_backend.l3.providers.ollama import OllamaProvider, OllamaStatus
from whymath_backend.l3.queue import CeleryJobQueue
from whymath_backend.l3.trace import LangfuseSink

# 앱 state에 의존성을 보관할 때 쓰는 키.
_PROVIDER_KEY = "llm_provider"
_CACHE_KEY = "llm_cache"
_TRACE_KEY = "trace_sink"
_QUEUE_KEY = "job_queue"

# /v1/generate의 런타임 shadow 검증기 — 결정론 관계 검증(=·<·>·≤·≥·≠·연쇄). 모듈 1회
# 생성(I/O 없음·재사용). 비차단(반환 텍스트·캐시 불변)이라 default-on이 안전 — 워커
# (`_WORKER_SHADOW_VALIDATOR`, slice 43)와 같은 관측 정책을 동기 HTTP 경로에 적용한다.
_SHADOW_VALIDATOR = default_seed_validator()


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
    """POST /v1/generate 응답(동기 완료) — 생성 텍스트 + 라우팅 메타데이터.

    `text`는 검증 전 원시 출력이다(앱 docstring 경계 메모 참조).
    """

    text: str = Field(..., description="생성된 원시 텍스트(검증 전 — 학생 직접 노출 금지)")
    cache_hit: bool = Field(..., description="캐시 적중 여부 (KPI, 03a §F.1)")
    decision: RoutingDecision = Field(..., description="라우팅 결정 메타데이터 (03a §G)")
    validation_signal: str | None = Field(
        default=None,
        description=(
            "런타임 shadow 검증 환각 신호(비차단·관측). None=통과/미검증(캐시 히트 포함), "
            "문자열=거짓 수치 관계 등 사유. 상위 계층이 재생성·L4/L5 라우팅 결정에 활용."
        ),
    )


class GenerateQueuedBody(BaseModel):
    """POST /v1/generate 응답(비동기 QUALITY 큐잉, HTTP 202) — job_id + 결정 메타데이터.

    QUALITY(27b)는 동기 호출 불가(03a §D.3)라 즉시 텍스트를 주지 않는다. job_id로
    GET /v1/jobs/{job_id}를 폴링해 결과를 받는다. `decision.mode`는 "async"다.
    """

    job_id: str = Field(..., description="비동기 작업 ID — /v1/jobs/{job_id}로 폴링")
    status: str = Field(default="queued", description="작업 적재 상태('queued')")
    decision: RoutingDecision = Field(..., description="라우팅 결정 메타데이터 (03a §G)")


class JobStatusBody(BaseModel):
    """GET /v1/jobs/{job_id} 응답 — 비동기 작업 상태 + (완료 시) 텍스트.

    `state`: pending(진행 중)/success(완료)/failure(실패)/unknown(상태 판정 불가).
    `text`는 success일 때만 채워지며 *검증 전 원시 출력*이다(앱 docstring 경계 메모).
    `error`는 failure/unknown일 때 사유(스택트레이스 아님).
    """

    job_id: str = Field(..., description="조회한 작업 ID")
    state: str = Field(..., description="pending/success/failure/unknown")
    text: str | None = Field(default=None, description="완료 시 원시 텍스트(검증 전)")
    error: str | None = Field(default=None, description="실패/판정불가 사유(스택트레이스 X)")


class ModelAvailabilityBody(BaseModel):
    """/status 모델 항목."""

    model_id: str
    present: bool


class StatusBody(BaseModel):
    """GET /status 응답 — Ollama(로컬) 레디니스 + 클라우드(Anthropic) 구성 보고.

    로컬 필드(ready/reachable/models/missing/error)는 S1 계약 그대로다. S5가 클라우드
    필드(cloud_*)를 *선택적으로* 덧붙인다 — 기본 None이라 기존 응답·테스트와 호환된다.
    클라우드 미노출 provider(가짜·로컬전용)면 cloud_* 필드는 None으로 남는다.
    """

    ready: bool = Field(..., description="도달 가능 + 모든 라우팅 모델 설치 여부(로컬)")
    reachable: bool = Field(..., description="Ollama 데몬 도달 가능 여부")
    models: list[ModelAvailabilityBody] = Field(..., description="라우팅 모델별 설치 여부")
    missing: list[str] = Field(..., description="미설치 모델 ID 목록")
    error: str | None = Field(default=None, description="도달 실패 시 사유(비크래시)")
    # ── 클라우드(Anthropic, S5) — 선택적. None이면 클라우드 상태 미노출 ──
    cloud_configured: bool | None = Field(
        default=None, description="Anthropic API 키 설정 여부(전송 가능). None=미노출"
    )
    cloud_reachable: bool | None = Field(
        default=None, description="Anthropic 도달·인증 확인(models.list). None=미노출"
    )
    cloud_error: str | None = Field(
        default=None, description="클라우드 도달/인증 실패 사유(비크래시). None=미노출"
    )


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


def _get_queue(request: Request) -> AsyncJobQueue:
    queue: AsyncJobQueue = getattr(request.app.state, _QUEUE_KEY)
    return queue


@asynccontextmanager
async def _lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """앱 수명 — 시작 시 device store 활성(slice 27), 종료 시 store 해제 + DB 엔진 풀 반납.

    **시작**: `Settings.device_store_mode`(none/pg/pg_cached) 기반으로 store 구성·
    `set_device_store(store)`. `none`(기본)은 slice 21 폴백 그대로(set_device_store(None) 호출).

    **종료**: store 해제(set_device_store(None) + Redis 클라이언트 닫기)·`dispose_engine`으로
    PG async 엔진 풀 반납.

    get_session이 첫 쿼리에서 *지연* 생성한 async 엔진/연결 풀을 앱 종료 시 반납한다.
    엔진이 만들어진 적 없으면(DB 미사용 경로·의존성 오버라이드된 단위테스트) dispose_engine은
    no-op이라 안전하다.

    주의: `TestClient(app)`를 컨텍스트매니저 없이 쓰면 lifespan이 발화하지 않는다(Starlette
    기본) — 기존 L3 단위테스트(가짜 의존성)는 영향받지 않는다.
    """
    settings = get_settings()
    # 슬라이스 30: store 의존성(PG/Redis) 부팅 시 ping → 미도달이면 fail-fast.
    await ping_device_store_health(settings)
    store, cleanup_fn = build_device_store_from_settings(settings)
    set_device_store(store)
    try:
        yield
    finally:
        set_device_store(None)
        await cleanup_fn()
        await dispose_engine()


def create_app(
    *,
    provider: LLMProvider | None = None,
    cache: CacheBackend | None = None,
    trace: TraceSink | None = None,
    queue: AsyncJobQueue | None = None,
) -> FastAPI:
    """FastAPI 앱 팩토리 — 의존성 주입 가능.

    기본값: OllamaProvider + RedisCache(S2) + LangfuseSink(S3) + CeleryJobQueue(S4). 넷
    모두 *지연*이라 앱 구성 시 라이브 Redis·Langfuse·Celery broker가 필요 없다(첫 사용
    때 연결). LangfuseSink는 키(WHYMATH_LANGFUSE_*) 미설정 시 영구 no-op이므로 CI(키
    없음)에서도 네트워크를 타지 않는다. 테스트는 가짜 provider/cache(InMemoryCache)/
    trace/queue를 주입해 hermetic을 유지한다.
    """
    app = FastAPI(
        title="WhyMath Backend — L3 생성 표면",
        version="0.1.0",
        summary="L3 라우터 ↔ Ollama·Celery 결선 (M1.2-live S1·S4)",
        lifespan=_lifespan,
    )
    # 기본 provider는 CompositeProvider — cost_tier로 로컬(Ollama)↔클라우드(Anthropic)
    # 디스패치(S5). 둘 다 지연이라 구성 시 라이브 Ollama·Anthropic 키가 필요 없다.
    app.state.__setattr__(
        _PROVIDER_KEY,
        (
            provider
            if provider is not None
            else CompositeProvider(local=OllamaProvider(), cloud=AnthropicProvider())
        ),
    )
    # 기본 캐시는 RedisCache(지연 연결) — 구성 시 라이브 Redis 불필요(첫 접근 때 연결).
    app.state.__setattr__(_CACHE_KEY, cache if cache is not None else RedisCache())
    # 기본 트레이스는 LangfuseSink(지연·자기비활성) — 키 미설정 시 영구 no-op(S3).
    app.state.__setattr__(_TRACE_KEY, trace if trace is not None else LangfuseSink())
    # 기본 큐는 CeleryJobQueue(지연 연결) — 구성 시 broker 불필요(첫 디스패치 때 연결, S4).
    app.state.__setattr__(_QUEUE_KEY, queue if queue is not None else CeleryJobQueue())

    @app.get("/health", tags=["ops"])
    async def health() -> dict[str, str]:
        """라이브니스 — 의존성 없이 프로세스 생존만 확인."""
        return {"status": "ok"}

    @app.get("/status", tags=["ops"], response_model=StatusBody)
    async def get_status(request: Request) -> StatusBody:
        """레디니스 — Ollama(로컬) 도달성·모델 매트릭스 + 클라우드(Anthropic) 구성 보고.

        Ollama·클라우드가 죽어 있어도 500을 던지지 않는다 — 상태로 *보고*한다. 로컬
        도달성은 provider.check_status로, 클라우드 구성/도달성은 provider.check_cloud_status
        (CompositeProvider만 노출)로 점검한다. provider가 해당 메서드를 노출하지 않으면
        (가짜·로컬전용) 로컬은 도달 불가로, 클라우드는 미노출(None)로 간주한다.
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

        # 클라우드 상태(선택) — CompositeProvider만 check_cloud_status를 노출한다.
        # 없으면(가짜·로컬전용 provider) cloud_* 필드는 None으로 남는다(기존 응답 호환).
        cloud_configured: bool | None = None
        cloud_reachable: bool | None = None
        cloud_error: str | None = None
        cloud_check = getattr(provider, "check_cloud_status", None)
        if cloud_check is not None:
            cloud_status: AnthropicStatus | None = await cloud_check()
            if cloud_status is not None:
                cloud_configured = cloud_status.configured
                cloud_reachable = cloud_status.reachable
                cloud_error = cloud_status.error

        return StatusBody(
            ready=ollama_status.all_present,
            reachable=ollama_status.reachable,
            models=[
                ModelAvailabilityBody(model_id=m.model_id, present=m.present)
                for m in ollama_status.models
            ],
            missing=list(ollama_status.missing),
            error=ollama_status.error,
            cloud_configured=cloud_configured,
            cloud_reachable=cloud_reachable,
            cloud_error=cloud_error,
        )

    @app.post("/v1/generate", tags=["l3"])
    async def post_generate(body: GenerateBody, request: Request) -> JSONResponse:
        """라우팅 → (동기) 캐시·생성 / (비동기 QUALITY) 큐잉. 메타데이터 + 결과 반환.

        반환 텍스트(동기·완료)는 *검증 전 원시 출력*이다 — 03 문서 환각 방어 파이프라인을
        통과하기 전에는 학생에게 직접 노출 금지 (CLAUDE.md 절대 금기). 환각 방어·학생
        표면화는 상위 계층(L4/L5 오케스트레이터)의 책임이다.

        QUALITY(27b)로 라우팅되면 동기 호출이 불가하므로(03a §D.3) 작업 큐에 적재하고
        **HTTP 202 Accepted**로 job_id를 반환한다 — 호출자는 /v1/jobs/{job_id}로 폴링한다.
        큐가 미구성이거나 broker가 죽어 enqueue가 실패하면 **503**으로 명확히 보고한다
        (500 스택트레이스 노출 금지 — 가용성 우선, '잠시 후 재시도'가 정직·안전).
        """
        provider = _get_provider(request)
        cache = _get_cache(request)
        trace = _get_trace(request)
        queue = _get_queue(request)
        try:
            result = await pipeline.generate(
                body.request,
                body.prompt,
                body.system,
                provider=provider,
                cache=cache,
                trace=trace,
                queue=queue,
                validator=_SHADOW_VALIDATOR,
            )
        except QualityQueueUnavailableError as exc:
            # 큐 미구성/ broker 도달 실패 — 명확한 503 JSON(스택트레이스 금지).
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={
                    "error": "quality_queue_unavailable",
                    "message": str(exc),
                    "detail": (
                        "QUALITY(27b) 비동기 큐를 사용할 수 없습니다 — 잠시 후 재시도(03a §D.3)."
                    ),
                },
            )

        if result.is_queued:
            # 비동기 QUALITY 큐잉 → 202 Accepted + job_id(폴링 안내).
            queued = GenerateQueuedBody(
                job_id=result.job_id or "",
                status=result.status,
                decision=result.decision,
            )
            return JSONResponse(
                status_code=status.HTTP_202_ACCEPTED,
                content=queued.model_dump(mode="json"),
            )

        # 동기 완료 → 200 + 텍스트(+ shadow 검증 신호·비차단 관측).
        completed = GenerateResponseBody(
            text=result.text,
            cache_hit=result.cache_hit,
            decision=result.decision,
            validation_signal=result.validation_signal,
        )
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content=completed.model_dump(mode="json"),
        )

    @app.get("/v1/jobs/{job_id}", tags=["l3"], response_model=JobStatusBody)
    async def get_job(job_id: str, request: Request) -> JobStatusBody:
        """QUALITY 비동기 작업 폴링 — 상태 + (완료 시) 생성 텍스트 (03a §D.3).

        완료(success) 시 `text`는 *검증 전 원시 출력*이다(앱 docstring 경계 메모) —
        학생 직접 노출 금지. 진행 중(pending)·실패(failure)·판정 불가(unknown)는 모두
        명확한 상태로 200을 돌려준다(폴링은 500 스택트레이스를 내지 않는다 — 가용성
        우선). result backend 도달 실패도 unknown으로 흡수된다(CeleryJobQueue.result).

        큐가 폴링(result)을 지원하지 않으면(가짜·미지원 구현) unknown으로 보고한다 —
        ollama check_status 기능 탐지와 동일한 방어 패턴.
        """
        queue = _get_queue(request)
        result_fn = getattr(queue, "result", None)
        if result_fn is None:
            # 폴링 미지원 큐 — 비크래시로 unknown 보고(상태 판정 불가).
            return JobStatusBody(
                job_id=job_id,
                state="unknown",
                error="queue does not support result polling",
            )
        job_status = result_fn(job_id)
        return JobStatusBody(
            job_id=job_status.job_id,
            state=job_status.state,
            text=job_status.text,
            error=job_status.error,
        )

    # DB-backed 라우터 결선 — get_session 의존성으로 PostgreSQL을 읽고 쓴다(영속 레이어 →
    # HTTP). L3 인라인 엔드포인트와 달리 살아있는 PG를 요구하므로 통합테스트(@integration)와
    # 메인의 실 PG 검증으로 동작을 확인한다.
    app.include_router(concepts_router)
    app.include_router(problems_router)
    app.include_router(users_router)
    app.include_router(me_router)
    app.include_router(coach_router)
    app.include_router(devices_router)

    return app
