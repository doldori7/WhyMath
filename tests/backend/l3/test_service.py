"""GenerationService(service.py) E2E 단위 테스트 — 라우팅·캐싱·큐잉·관측성 조립.

설계 정본: docs/architecture/03a_l3_router_design.md §C→§F.1→§D.3→§F.2.
범위 메모(M1.2): 라이브 서비스 없이, 4종 협력자를 손으로 짠 가짜/인메모리 스텁으로
주입해 *오케스트레이션 흐름*을 통째로 검증한다 — 캐시미스→생성→저장→trace / 캐시히트 /
async-QUALITY→enqueue / cloud 경로. 모킹 라이브러리 미사용(pyproject 의도).
"""

from __future__ import annotations

from whymath_backend.config import Settings
from whymath_backend.l3.interfaces import InMemoryCache, RecordingTraceSink
from whymath_backend.l3.models import (
    CallSite,
    CostTier,
    LocalModelTier,
    RoutingDecision,
    RoutingRequest,
)
from whymath_backend.l3.router import Router, cache_key_for
from whymath_backend.l3.service import (
    MODE_ASYNC,
    MODE_CACHE,
    MODE_SYNC,
    GenerationResult,
    GenerationService,
)


# ──────────────────────────────────────────────────────────────────────────
# 가짜 협력자 (손으로 작성)
# ──────────────────────────────────────────────────────────────────────────
class _FakeProvider:
    """가짜 LLMProvider — generate 호출을 기록하고 고정 텍스트를 돌려준다."""

    def __init__(self, text: str = "생성된 응답") -> None:
        self._text = text
        self.calls: list[tuple[str, str, RoutingDecision]] = []

    async def generate(self, prompt: str, system: str, decision: RoutingDecision) -> str:
        self.calls.append((prompt, system, decision))
        return self._text


class _FakeQueue:
    """가짜 AsyncJobQueue — enqueue payload를 기록하고 결정적 job_id를 돌려준다."""

    def __init__(self, job_id: str = "job-async-1") -> None:
        self._job_id = job_id
        self.payloads: list[dict[str, object]] = []

    async def enqueue(self, payload: dict[str, object]) -> str:
        self.payloads.append(payload)
        return self._job_id


# ──────────────────────────────────────────────────────────────────────────
# 서비스 빌더 — 가짜 4종 + InMemory 스텁 주입
# ──────────────────────────────────────────────────────────────────────────
def _service(
    *,
    provider: _FakeProvider | None = None,
    cache: InMemoryCache | None = None,
    trace: RecordingTraceSink | None = None,
    queue: _FakeQueue | None = None,
    settings: Settings | None = None,
) -> tuple[GenerationService, _FakeProvider, InMemoryCache, RecordingTraceSink, _FakeQueue]:
    provider = provider if provider is not None else _FakeProvider()
    cache = cache if cache is not None else InMemoryCache()
    trace = trace if trace is not None else RecordingTraceSink()
    queue = queue if queue is not None else _FakeQueue()
    settings = settings if settings is not None else Settings()
    service = GenerationService(
        router=Router(),
        provider=provider,
        cache=cache,
        trace=trace,
        queue=queue,
        settings=settings,
    )
    return service, provider, cache, trace, queue


def _sync_local_request() -> RoutingRequest:
    """LOCAL/동기로 떨어지는 요청 — match(GENERAL/FAST/sync), budget 0."""
    return RoutingRequest(
        task_type="match",
        difficulty="medium",
        requires_reasoning=False,
        student_subscription="premium",
        budget_krw=0.0,
        sync=True,
        call_site=CallSite.CONCEPT_ID_MATCH,
    )


def _quality_async_request() -> RoutingRequest:
    """QUALITY/async로 떨어지는 요청 — ⑤ 자기검증(축2 규칙1)."""
    return RoutingRequest(
        task_type="self_verify",
        difficulty="hard",
        requires_reasoning=True,
        student_subscription="premium",
        budget_krw=0.0,
        sync=False,
        call_site=CallSite.SELF_VERIFY,
    )


def _cloud_request() -> RoutingRequest:
    """CLOUD_HIGH로 떨어지는 요청 — killer + gifted + 예산 충분(축1 규칙3)."""
    return RoutingRequest(
        task_type="prove",
        difficulty="killer",
        requires_reasoning=True,
        student_subscription="gifted",
        budget_krw=1000.0,
        sync=True,
    )


# ══════════════════════════════════════════════════════════════════════
# 경로 1: 캐시 미스 → 동기 생성 → 캐시 저장 → trace 기록
# ══════════════════════════════════════════════════════════════════════
class TestCacheMissSyncGenerate:
    async def test_generates_and_returns_text(self) -> None:
        """캐시 미스면 provider.generate로 생성하고 텍스트를 반환한다."""
        service, provider, _, _, _ = _service(provider=_FakeProvider("정답은 x=3"))
        result = await service.generate(_sync_local_request(), "프롬프트", "시스템")
        assert isinstance(result, GenerationResult)
        assert result.text == "정답은 x=3"
        assert result.cache_hit is False
        assert result.job_id is None
        assert result.mode == MODE_SYNC
        assert len(provider.calls) == 1

    async def test_stores_in_cache_with_ttl(self) -> None:
        """생성 결과를 캐시 키에 TTL과 함께 저장한다(03a §F.1)."""
        cache = InMemoryCache()
        service, _, _, _, _ = _service(cache=cache, settings=Settings(cache_ttl_seconds=7200))
        req = _sync_local_request()
        result = await service.generate(req, "p", "s")
        # 같은 결정으로 키를 재계산해 저장 여부 확인
        key = cache_key_for("p", "s", result.decision)
        assert await cache.get(key) == result.text
        # TTL이 settings 값으로 기록됐는지(InMemoryCache는 ttl을 기록)
        assert cache._store[key][1] == 7200

    async def test_records_trace_cache_miss(self) -> None:
        """trace에 cache_hit=False 필드를 기록한다(03a §F.2)."""
        trace = RecordingTraceSink()
        service, _, _, _, _ = _service(trace=trace)
        await service.generate(_sync_local_request(), "p", "s", student_id_hash="h99")
        assert len(trace.records) == 1
        rec = trace.records[0]
        assert rec["cache_hit"] is False
        assert rec["cost_tier"] == "local"
        assert rec["student_id_hash"] == "h99"

    async def test_passes_decision_to_provider(self) -> None:
        """provider에 라우터 결정(decision)을 그대로 넘긴다(직접 호출 금지, 항상 라우터 경유)."""
        service, provider, _, _, _ = _service()
        result = await service.generate(_sync_local_request(), "p", "s")
        _, _, passed_decision = provider.calls[0]
        assert passed_decision == result.decision
        assert passed_decision.cost_tier == CostTier.LOCAL


# ══════════════════════════════════════════════════════════════════════
# 경로 2: 캐시 히트 → 생성 생략
# ══════════════════════════════════════════════════════════════════════
class TestCacheHit:
    async def test_returns_cached_without_generating(self) -> None:
        """캐시 히트면 provider를 호출하지 않고 캐시 값을 반환한다."""
        cache = InMemoryCache()
        # 먼저 결정을 계산해 캐시를 선점한다
        req = _sync_local_request()
        decision = Router().route(req)
        key = cache_key_for("p", "s", decision)
        await cache.set(key, "캐시된 응답", ttl_seconds=60)

        service, provider, _, trace, _ = _service(cache=cache)
        result = await service.generate(req, "p", "s")
        assert result.text == "캐시된 응답"
        assert result.cache_hit is True
        assert result.mode == MODE_CACHE
        assert result.job_id is None
        assert len(provider.calls) == 0  # 생성 생략

    async def test_records_trace_cache_hit(self) -> None:
        """캐시 히트도 trace에 cache_hit=True로 기록된다(KPI)."""
        cache = InMemoryCache()
        req = _sync_local_request()
        decision = Router().route(req)
        await cache.set(cache_key_for("p", "s", decision), "v", ttl_seconds=60)

        trace = RecordingTraceSink()
        service, _, _, _, _ = _service(cache=cache, trace=trace)
        await service.generate(req, "p", "s")
        assert trace.records[0]["cache_hit"] is True


# ══════════════════════════════════════════════════════════════════════
# 경로 3: async QUALITY → 큐 enqueue → job_id 반환 (생성·캐시 저장 없음)
# ══════════════════════════════════════════════════════════════════════
class TestAsyncQualityQueue:
    async def test_enqueues_and_returns_job_id(self) -> None:
        """QUALITY(async) 결정 → 큐 enqueue, job_id 반환, text는 None(03a §D.3)."""
        queue = _FakeQueue(job_id="quality-job-7")
        service, provider, _, _, _ = _service(queue=queue)
        result = await service.generate(_quality_async_request(), "p", "s")
        assert result.decision.local_model == LocalModelTier.QUALITY
        assert result.decision.mode == "async"
        assert result.mode == MODE_ASYNC
        assert result.text is None
        assert result.job_id == "quality-job-7"
        assert len(queue.payloads) == 1
        assert len(provider.calls) == 0  # 동기 생성 안 함

    async def test_payload_contains_decision_and_prompt(self) -> None:
        """큐 payload에 prompt·system·decision·request가 직렬화돼 담긴다(워커 입력)."""
        queue = _FakeQueue()
        service, _, _, _, _ = _service(queue=queue)
        await service.generate(
            _quality_async_request(), "내 프롬프트", "내 시스템", student_id_hash="h1"
        )
        payload = queue.payloads[0]
        assert payload["prompt"] == "내 프롬프트"
        assert payload["system"] == "내 시스템"
        assert payload["student_id_hash"] == "h1"
        # decision은 JSON 직렬화된 dict
        assert isinstance(payload["decision"], dict)
        assert payload["decision"]["local_model"] == "quality"
        assert isinstance(payload["request"], dict)

    async def test_async_does_not_store_cache(self) -> None:
        """async 경로는 캐시에 저장하지 않는다(아직 응답이 없으므로)."""
        cache = InMemoryCache()
        service, _, _, _, _ = _service(cache=cache)
        await service.generate(_quality_async_request(), "p", "s")
        assert len(cache._store) == 0

    async def test_async_records_trace(self) -> None:
        """async 경로도 trace를 기록한다(cache_hit=False)."""
        trace = RecordingTraceSink()
        service, _, _, _, _ = _service(trace=trace)
        await service.generate(_quality_async_request(), "p", "s")
        assert len(trace.records) == 1
        assert trace.records[0]["mode"] == "async"
        assert trace.records[0]["cache_hit"] is False


# ══════════════════════════════════════════════════════════════════════
# 경로 4: 클라우드 (동기 생성 경로를 클라우드 결정으로)
# ══════════════════════════════════════════════════════════════════════
class TestCloudPath:
    async def test_cloud_decision_generates_sync(self) -> None:
        """CLOUD_HIGH 결정도 동기 생성 경로로 처리된다(provider가 디스패치)."""
        service, provider, _, _, _ = _service(provider=_FakeProvider("클라우드 증명"))
        result = await service.generate(_cloud_request(), "p", "s")
        assert result.decision.cost_tier == CostTier.CLOUD_HIGH
        assert result.text == "클라우드 증명"
        assert result.mode == MODE_SYNC
        assert result.job_id is None
        assert len(provider.calls) == 1

    async def test_cloud_result_cached(self) -> None:
        """클라우드 응답도 캐시에 저장된다(축1 포함 키, 03a §F.1)."""
        cache = InMemoryCache()
        service, _, _, _, _ = _service(cache=cache)
        result = await service.generate(_cloud_request(), "p", "s")
        key = cache_key_for("p", "s", result.decision)
        assert await cache.get(key) == result.text

    async def test_cloud_trace_records_tier(self) -> None:
        """클라우드 경로 trace에 cost_tier=cloud_high 기록(80/18/2 모니터링)."""
        trace = RecordingTraceSink()
        service, _, _, _, _ = _service(trace=trace)
        await service.generate(_cloud_request(), "p", "s")
        assert trace.records[0]["cost_tier"] == "cloud_high"
        assert trace.records[0]["local_family"] is None
        assert trace.records[0]["local_model"] is None


# ══════════════════════════════════════════════════════════════════════
# 캐시 정체성 — 다른 티어는 캐시를 공유하지 않는다 (03a §F.1)
# ══════════════════════════════════════════════════════════════════════
class TestCacheIdentity:
    async def test_local_and_cloud_do_not_share_cache(self) -> None:
        """같은 프롬프트라도 LOCAL 결정과 CLOUD 결정은 키가 달라 캐시를 안 섞는다."""
        cache = InMemoryCache()
        service, provider, _, _, _ = _service(cache=cache, provider=_FakeProvider("로컬값"))
        # 1) LOCAL 경로로 생성·저장
        await service.generate(_sync_local_request(), "동일프롬프트", "동일시스템")
        # 2) CLOUD 경로로 같은 프롬프트 — 캐시 미스여야 하므로 provider 재호출
        await service.generate(_cloud_request(), "동일프롬프트", "동일시스템")
        assert len(provider.calls) == 2  # 두 번 다 생성(캐시 공유 안 됨)
