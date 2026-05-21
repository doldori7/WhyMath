"""L3 파이프라인 단위테스트 — 라우팅→캐시→생성→관측 결선 (라이브 서비스 없음).

가짜 provider + 인메모리 스텁(InMemoryCache·RecordingTraceSink)으로 캐시 적중/미스·
QUALITY 차단·관측 기록을 검증한다.

설계 정본: docs/architecture/03a_l3_router_design.md §F.1·§F.2·§D.3.
"""

from __future__ import annotations

import pytest

from whymath_backend.l3.interfaces import InMemoryCache, RecordingTraceSink
from whymath_backend.l3.models import RoutingDecision, RoutingRequest
from whymath_backend.l3.pipeline import (
    GenerationResult,
    QualityQueueUnavailableError,
    generate,
)
from whymath_backend.l3.router import cache_key_for


class RecordingProvider:
    """가짜 LLMProvider — 호출 기록 + 정해진 텍스트 반환."""

    def __init__(self, text: str = "원시 생성물") -> None:
        self._text = text
        self.calls: list[tuple[str, str, RoutingDecision]] = []

    async def generate(
        self,
        prompt: str,
        system: str,
        decision: RoutingDecision,
    ) -> str:
        self.calls.append((prompt, system, decision))
        return self._text


def _sync_local_request() -> RoutingRequest:
    """LOCAL·동기로 라우팅되는 평이한 요청 (FAST/MID 동기)."""
    return RoutingRequest(
        task_type="explain",
        difficulty="easy",
        requires_reasoning=False,
        student_subscription="free",  # 무료 → LOCAL 강제
        sync=True,
    )


def _quality_request() -> RoutingRequest:
    """QUALITY(비동기)로 라우팅되는 요청 — ⑤ 자기검증."""
    return RoutingRequest(
        task_type="self_verify",
        difficulty="hard",
        requires_reasoning=True,
        student_subscription="free",
        sync=False,
        call_site="self_verify",
    )


class TestCacheMissPath:
    async def test_miss_calls_provider_and_caches(self) -> None:
        """미스 → provider 호출 → 캐시 저장 → cache_hit=False 기록."""
        provider = RecordingProvider(text="결과A")
        cache = InMemoryCache()
        trace = RecordingTraceSink()

        result = await generate(
            _sync_local_request(),
            "프롬프트",
            "시스템",
            provider=provider,
            cache=cache,
            trace=trace,
            cache_ttl_s=60,
        )

        assert isinstance(result, GenerationResult)
        assert result.text == "결과A"
        assert result.cache_hit is False
        assert len(provider.calls) == 1
        # 캐시에 결정 기반 키로 저장됐는지
        key = cache_key_for("프롬프트", "시스템", result.decision)
        assert await cache.get(key) == "결과A"
        # 관측 기록 1건, cache_hit False
        assert len(trace.records) == 1
        assert trace.records[0]["cache_hit"] is False


class TestCacheHitPath:
    async def test_hit_skips_provider(self) -> None:
        """히트 → provider 미호출 → 캐시 값 반환 → cache_hit=True 기록."""
        provider = RecordingProvider(text="새값")
        cache = InMemoryCache()
        trace = RecordingTraceSink()
        req = _sync_local_request()

        # 사전 적재: 라우팅 결정 키로 캐시에 미리 넣는다.
        from whymath_backend.l3.router import Router

        decision = Router().route(req)
        key = cache_key_for("프롬프트", "시스템", decision)
        await cache.set(key, "캐시된값", 60)

        result = await generate(
            req,
            "프롬프트",
            "시스템",
            provider=provider,
            cache=cache,
            trace=trace,
        )

        assert result.text == "캐시된값"
        assert result.cache_hit is True
        assert provider.calls == []  # provider 미호출
        assert len(trace.records) == 1
        assert trace.records[0]["cache_hit"] is True

    async def test_second_call_hits_after_first_miss(self) -> None:
        """같은 입력 2회 호출 → 1회는 미스, 2회는 히트(provider 1회만)."""
        provider = RecordingProvider(text="동일결과")
        cache = InMemoryCache()
        trace = RecordingTraceSink()
        req = _sync_local_request()

        r1 = await generate(
            req, "p", "s", provider=provider, cache=cache, trace=trace
        )
        r2 = await generate(
            req, "p", "s", provider=provider, cache=cache, trace=trace
        )

        assert r1.cache_hit is False
        assert r2.cache_hit is True
        assert r2.text == "동일결과"
        assert len(provider.calls) == 1  # 두 번째는 캐시


class TestQualityBlocked:
    async def test_quality_raises_named_error(self) -> None:
        """QUALITY(async) → QualityQueueUnavailableError, provider 미호출."""
        provider = RecordingProvider()
        cache = InMemoryCache()
        trace = RecordingTraceSink()

        with pytest.raises(QualityQueueUnavailableError):
            await generate(
                _quality_request(),
                "p",
                "s",
                provider=provider,
                cache=cache,
                trace=trace,
            )
        assert provider.calls == []  # 동기 호출 금지


class TestCloudRejectedThroughProvider:
    async def test_cloud_decision_rejected_by_provider(self) -> None:
        """클라우드로 라우팅된 동기 결정은 (OllamaProvider 류) provider가 거부.

        파이프라인은 QUALITY만 차단하고 클라우드는 provider 경계로 흘려보낸다.
        여기서는 클라우드를 거부하는 가짜 provider로 그 계약을 검증한다.
        """

        class CloudRejectingProvider:
            async def generate(
                self, prompt: str, system: str, decision: RoutingDecision
            ) -> str:
                from whymath_backend.l3.models import CostTier
                from whymath_backend.l3.router import _as_cost_tier

                if _as_cost_tier(decision.cost_tier) is not CostTier.LOCAL:
                    raise ValueError("로컬 결정만 처리")
                return "ok"

        # killer 난이도 + premium → CLOUD_HIGH로 라우팅 (예산 충분).
        cloud_req = RoutingRequest(
            task_type="prove",
            difficulty="killer",
            requires_reasoning=True,
            student_subscription="gifted",
            budget_krw=10000.0,
            sync=True,
        )
        with pytest.raises(ValueError, match="로컬 결정만"):
            await generate(
                cloud_req,
                "p",
                "s",
                provider=CloudRejectingProvider(),
                cache=InMemoryCache(),
                trace=RecordingTraceSink(),
            )
