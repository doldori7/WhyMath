"""L3 생성 오케스트레이션 — 라우터 결정 → 캐시 → (동기 생성 | 비동기 큐) → 관측성.

설계 정본: docs/architecture/03a_l3_router_design.md
  §C(라우팅) → §F.1(캐시 키·조회) → §D.3(QUALITY 비동기 큐) → §F.2(Langfuse 기록).

이 서비스는 L3의 *단일 진입점*이다. 상위 계층(L4 교수학·L5 오케스트레이터)은 이
GenerationService.generate()만 호출하면 되고, 라우팅·캐싱·큐잉·관측성은 내부에서
조립된다. CLAUDE.md 절대 원칙 "LLM 호출은 항상 라우터 경유"·"학생 응답 생성은 PRM/
도구 검증 통과 후"를 *구조로* 강제한다 — generate()는 router.route()를 반드시 거치며,
생성된 text는 호출 측 환각 방어 파이프라인(03 문서)을 통과해야 학생에게 노출된다.

의존성은 전부 Protocol 주입(완전 테스트 가능):
  - router: Router            — 라우팅 결정(순수 로직, router.py)
  - provider: LLMProvider     — 실제 생성(Ollama/Anthropic 디스패처, providers.py)
  - cache: CacheBackend       — 응답 캐시(Redis, cache.py / 테스트는 InMemoryCache)
  - trace: TraceSink          — 관측성(Langfuse, tracing.py / 테스트는 RecordingTraceSink)
  - queue: AsyncJobQueue      — QUALITY 비동기 큐(Celery, queue.py)
  - settings: Settings        — TTL 등 구성값(config.py)
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from whymath_backend.config import Settings
from whymath_backend.l3.interfaces import (
    AsyncJobQueue,
    CacheBackend,
    LLMProvider,
    TraceSink,
)
from whymath_backend.l3.models import RoutingDecision, RoutingRequest
from whymath_backend.l3.router import Router, cache_key_for, langfuse_fields

# 생성 모드 식별자 — GenerationResult.mode. 라우터의 RoutingDecision.mode("sync"/"async")
# 와 정합하되, 캐시 히트는 별도 모드("cache")로 표기해 관측에서 구분한다.
MODE_SYNC: str = "sync"
MODE_ASYNC: str = "async"
MODE_CACHE: str = "cache"


class GenerationResult(BaseModel):
    """생성 오케스트레이션 결과 — 동기 응답·캐시 히트·비동기 큐 3경우를 한 타입으로.

    - 동기 생성/캐시 히트: text가 채워지고 job_id는 None.
    - 비동기(QUALITY) 큐잉: text는 None, job_id가 채워진다(완료는 폴링/콜백, 03a §D.3).
    decision은 항상 포함 — 상위 계층이 티어·근거·추정치를 활용·로깅할 수 있게 한다.
    """

    model_config = ConfigDict(extra="forbid")

    text: str | None = Field(
        default=None,
        description="생성/캐시된 응답 텍스트. 비동기(QUALITY) 큐잉 시 None(아직 미생성).",
    )
    decision: RoutingDecision = Field(..., description="라우터 결정(티어·근거·추정치).")
    cache_hit: bool = Field(default=False, description="캐시 히트 여부(KPI, 03a §F.2).")
    job_id: str | None = Field(
        default=None,
        description="비동기(QUALITY) 큐 작업 ID. 동기/캐시 경우 None(03a §D.3).",
    )
    mode: str = Field(
        default=MODE_SYNC,
        description="sync(동기 생성)/async(큐잉)/cache(캐시 히트) — 관측 구분용.",
    )


class GenerationService:
    """L3 생성 오케스트레이터 — 라우팅·캐싱·큐잉·관측성을 조립한다.

    모든 협력자를 Protocol로 주입받아 라이브 서비스 없이 완전 단위테스트가 가능하다
    (테스트는 InMemoryCache·RecordingTraceSink + 손으로 짠 가짜 provider/queue 주입).
    """

    def __init__(
        self,
        *,
        router: Router,
        provider: LLMProvider,
        cache: CacheBackend,
        trace: TraceSink,
        queue: AsyncJobQueue,
        settings: Settings,
    ) -> None:
        self._router = router
        self._provider = provider
        self._cache = cache
        self._trace = trace
        self._queue = queue
        self._settings = settings

    async def generate(
        self,
        req: RoutingRequest,
        prompt: str,
        system: str,
        *,
        student_id_hash: str | None = None,
    ) -> GenerationResult:
        """라우팅 → 캐시 → (동기 생성 | 비동기 큐) → 관측성 기록.

        흐름(03a §C→§F.1→§D.3→§F.2):
          1. router.route(req)로 결정(축1·축3·축2 합성).
          2. cache_key_for(prompt, system, decision)로 키 생성 후 캐시 조회.
          3. 캐시 히트 → 관측 기록(cache_hit=True) 후 즉시 반환(생성 생략).
          4. decision.mode == "async"(QUALITY) → 큐 enqueue → job_id 반환(생성은 워커).
          5. 그 외(동기) → provider.generate → 캐시 저장(TTL) → 관측 기록 → 반환.

        student_id_hash는 관측 태그에만 쓴다(직접 ID 금지, 캐시 키엔 미포함 — 03a §F).
        """
        # 1. 라우팅 결정 (항상 라우터 경유 — CLAUDE.md 절대 원칙)
        decision = self._router.route(req)
        call_site = req.call_site

        # 2. 캐시 키 + 조회 (세 축 합성 키, 03a §F.1)
        key = cache_key_for(prompt, system, decision)
        cached = await self._cache.get(key)

        # 3. 캐시 히트 → 생성 생략, 관측 기록 후 반환
        if cached is not None:
            self._trace.record(
                langfuse_fields(
                    decision,
                    cache_hit=True,
                    call_site=call_site,
                    student_id_hash=student_id_hash,
                )
            )
            return GenerationResult(
                text=cached,
                decision=decision,
                cache_hit=True,
                job_id=None,
                mode=MODE_CACHE,
            )

        # 4. 비동기(QUALITY) → 큐로 enqueue, 즉시 job_id 반환 (03a §D.3)
        if decision.mode == MODE_ASYNC:
            job_id = await self._queue.enqueue(
                self._async_payload(req, prompt, system, decision, student_id_hash)
            )
            self._trace.record(
                langfuse_fields(
                    decision,
                    cache_hit=False,
                    call_site=call_site,
                    student_id_hash=student_id_hash,
                )
            )
            return GenerationResult(
                text=None,
                decision=decision,
                cache_hit=False,
                job_id=job_id,
                mode=MODE_ASYNC,
            )

        # 5. 동기 생성 → 캐시 저장(TTL) → 관측 기록 → 반환
        text = await self._provider.generate(prompt, system, decision)
        await self._cache.set(key, text, self._settings.cache_ttl_seconds)
        self._trace.record(
            langfuse_fields(
                decision,
                cache_hit=False,
                call_site=call_site,
                student_id_hash=student_id_hash,
            )
        )
        return GenerationResult(
            text=text,
            decision=decision,
            cache_hit=False,
            job_id=None,
            mode=MODE_SYNC,
        )

    @staticmethod
    def _async_payload(
        req: RoutingRequest,
        prompt: str,
        system: str,
        decision: RoutingDecision,
        student_id_hash: str | None,
    ) -> dict[str, object]:
        """비동기 큐 작업 payload 구성 — 워커가 QUALITY 생성에 필요한 입력을 직렬화.

        Pydantic 모델은 mode="json"으로 직렬화해 Celery(JSON 직렬화 기본)와 호환시킨다.
        워커는 이 payload로 decision을 복원해 OllamaProvider(qwen3.5:27b)를 호출한다
        (실제 워커 본체는 queue.py 참조, §H 후속6).
        """
        return {
            "prompt": prompt,
            "system": system,
            "decision": decision.model_dump(mode="json"),
            "request": req.model_dump(mode="json"),
            "student_id_hash": student_id_hash,
        }
