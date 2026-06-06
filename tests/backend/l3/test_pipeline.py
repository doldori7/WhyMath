"""L3 파이프라인 단위테스트 — 라우팅→캐시→생성→관측 결선 (라이브 서비스 없음).

가짜 provider + 인메모리 스텁(InMemoryCache·RecordingTraceSink) + 가짜 큐로 캐시
적중/미스·QUALITY 비동기 큐잉·관측 기록을 검증한다.

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
from whymath_backend.l3.pregenerate.validator import default_seed_validator
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


class RecordingQueue:
    """가짜 AsyncJobQueue — enqueue payload 기록 + 정해진 job_id 반환.

    interfaces.AsyncJobQueue를 구조적으로 충족한다. `raises`를 주면 enqueue가 그 예외를
    던져 broker 다운(디스패치 실패)을 모사한다 — 파이프라인이 QualityQueueUnavailableError
    로 변환하는지 검증할 수 있게 한다.
    """

    def __init__(self, *, job_id: str = "job-123", raises: Exception | None = None) -> None:
        self._job_id = job_id
        self._raises = raises
        self.payloads: list[dict[str, object]] = []

    async def enqueue(self, payload: dict[str, object]) -> str:
        self.payloads.append(payload)
        if self._raises is not None:
            raise self._raises
        return self._job_id


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


class TestQualityAsyncQueue:
    """QUALITY(async) 비동기 큐 경로 — enqueue→job_id, provider 미호출 (03a §D.3)."""

    async def test_queue_present_enqueues_and_returns_job_id(self) -> None:
        """큐 주입 → enqueue 1회 → status=queued·job_id 반환, provider/캐시 미사용."""
        provider = RecordingProvider(text="이건 안 쓰임")
        cache = InMemoryCache()
        trace = RecordingTraceSink()
        queue = RecordingQueue(job_id="job-xyz")

        result = await generate(
            _quality_request(),
            "검증할 풀이",
            "시스템",
            provider=provider,
            cache=cache,
            trace=trace,
            queue=queue,
        )

        assert isinstance(result, GenerationResult)
        assert result.is_queued is True
        assert result.status == "queued"
        assert result.job_id == "job-xyz"
        assert result.text == ""  # 비동기 — 텍스트는 즉시 없음(폴링)
        assert result.cache_hit is False
        # QUALITY는 동기 호출 절대 금지 — provider 미호출.
        assert provider.calls == []
        # enqueue 정확히 1회, payload는 1건.
        assert len(queue.payloads) == 1
        # 결정은 QUALITY(async)여야 한다.
        assert result.decision.mode == "async"
        assert result.decision.local_model == "quality"

    async def test_enqueued_payload_is_json_safe_and_complete(self) -> None:
        """enqueue payload는 prompt·system·decision(dict) — JSON 직렬화 가능해야 한다."""
        import json

        queue = RecordingQueue()
        result = await generate(
            _quality_request(),
            "프롬프트본문",
            "시스템본문",
            provider=RecordingProvider(),
            cache=InMemoryCache(),
            trace=RecordingTraceSink(),
            queue=queue,
        )
        payload = queue.payloads[0]
        assert payload["prompt"] == "프롬프트본문"
        assert payload["system"] == "시스템본문"
        # decision은 model_dump() dict — enum이 문자열로 직렬화(use_enum_values=True).
        decision_data = payload["decision"]
        assert isinstance(decision_data, dict)
        assert decision_data["cost_tier"] == "local"
        assert decision_data["local_model"] == "quality"
        assert decision_data["mode"] == "async"
        # payload 전체가 JSON 직렬화 가능(Celery JSON 직렬화 계약).
        assert json.loads(json.dumps(payload)) == payload
        # 재구성한 결정이 반환 결정과 동치(왕복 안전).
        assert RoutingDecision.model_validate(decision_data) == result.decision

    async def test_enqueue_records_trace_with_async_mode(self) -> None:
        """enqueue도 관측 기록한다 — mode=async, cache_hit=False (03a §F.2)."""
        trace = RecordingTraceSink()
        await generate(
            _quality_request(),
            "p",
            "s",
            provider=RecordingProvider(),
            cache=InMemoryCache(),
            trace=trace,
            queue=RecordingQueue(),
        )
        assert len(trace.records) == 1
        assert trace.records[0]["mode"] == "async"
        assert trace.records[0]["cache_hit"] is False

    async def test_queue_none_raises_named_error(self) -> None:
        """큐 미주입(미구성) → QualityQueueUnavailableError, provider 미호출(동기 폴백 금지)."""
        provider = RecordingProvider()
        with pytest.raises(QualityQueueUnavailableError):
            await generate(
                _quality_request(),
                "p",
                "s",
                provider=provider,
                cache=InMemoryCache(),
                trace=RecordingTraceSink(),
                # queue 미주입 → 기본 None
            )
        assert provider.calls == []  # 동기 호출 금지

    async def test_enqueue_failure_raises_named_error(self) -> None:
        """enqueue 자체 실패(broker 다운) → QualityQueueUnavailableError로 변환(API 503)."""
        provider = RecordingProvider()
        queue = RecordingQueue(raises=ConnectionError("broker refused"))
        with pytest.raises(QualityQueueUnavailableError) as exc_info:
            await generate(
                _quality_request(),
                "p",
                "s",
                provider=provider,
                cache=InMemoryCache(),
                trace=RecordingTraceSink(),
                queue=queue,
            )
        # 원인이 보존돼야 한다(디버깅) — broker 도달 실패의 흔적.
        assert exc_info.value.__cause__ is not None
        assert provider.calls == []  # 동기 호출 금지
        assert len(queue.payloads) == 1  # 시도는 했음

    async def test_queue_satisfies_async_job_queue_protocol(self) -> None:
        """가짜 큐가 AsyncJobQueue Protocol을 구조적으로 충족하는지 확인(테스트 위생)."""
        from whymath_backend.l3.interfaces import AsyncJobQueue

        assert isinstance(RecordingQueue(), AsyncJobQueue)


class TestShadowValidation:
    """런타임 shadow 검증(비차단·opt-in) — 미스 생성물의 환각 신호를 trace에 기록.

    반환 텍스트·캐시는 *불변*(원시 출력은 검증 전이며 학생 노출 차단은 L4/L5 책임).
    """

    async def test_clean_output_records_none_signal(self) -> None:
        """검증 통과 출력 → validation_signal=None, 텍스트 불변."""
        provider = RecordingProvider(text="정답은 2 + 2 = 4 입니다")
        trace = RecordingTraceSink()
        result = await generate(
            _sync_local_request(),
            "p",
            "s",
            provider=provider,
            cache=InMemoryCache(),
            trace=trace,
            validator=default_seed_validator(),
        )
        assert result.text == "정답은 2 + 2 = 4 입니다"
        assert trace.records[0]["validation_signal"] is None
        # 호출자도 신호를 프로그램적으로 읽을 수 있다(trace와 같은 값).
        assert result.validation_signal is None

    async def test_false_output_records_signal_but_nonblocking(self) -> None:
        """거짓 산술 출력 → validation_signal에 사유 기록, 그러나 텍스트·캐시는 *그대로*."""
        provider = RecordingProvider(text="2 + 2 = 5")
        cache = InMemoryCache()
        trace = RecordingTraceSink()
        result = await generate(
            _sync_local_request(),
            "프롬프트",
            "시스템",
            provider=provider,
            cache=cache,
            trace=trace,
            validator=default_seed_validator(),
        )
        # 비차단: 반환 텍스트는 원시 출력 그대로(차단·치환 없음).
        assert result.text == "2 + 2 = 5"
        assert result.cache_hit is False
        # 캐시에도 그대로 적재(shadow는 관측 전용 — 캐시 동작 불변).
        key = cache_key_for("프롬프트", "시스템", result.decision)
        assert await cache.get(key) == "2 + 2 = 5"
        # 그러나 환각 신호는 *조용히 넘어가지 않고* 관측에 남는다(CLAUDE.md).
        signal = trace.records[0]["validation_signal"]
        assert isinstance(signal, str) and "arithmetic error" in signal
        # 그리고 호출자도 같은 신호를 GenerationResult로 직접 받는다(관측 싱크에만 의존 X).
        assert result.validation_signal == signal

    async def test_no_validator_signal_is_none(self) -> None:
        """validator 미주입(기본) → 검증 미실행 → validation_signal=None(오버헤드 0)."""
        provider = RecordingProvider(text="5 < 3 라는 거짓 부등식")
        trace = RecordingTraceSink()
        result = await generate(
            _sync_local_request(),
            "p",
            "s",
            provider=provider,
            cache=InMemoryCache(),
            trace=trace,
            # validator 미주입
        )
        assert trace.records[0]["validation_signal"] is None
        assert result.validation_signal is None

    async def test_cache_hit_not_shadow_validated(self) -> None:
        """캐시 히트 경로는 shadow 검증 대상이 아니다(미스 생성물만) — provider 미호출."""
        provider = RecordingProvider(text="안 쓰임")
        cache = InMemoryCache()
        trace = RecordingTraceSink()
        req = _sync_local_request()
        from whymath_backend.l3.router import Router

        decision = Router().route(req)
        key = cache_key_for("p", "s", decision)
        await cache.set(key, "8 != 8", 60)  # 거짓이지만 히트는 검증 안 함

        result = await generate(
            req,
            "p",
            "s",
            provider=provider,
            cache=cache,
            trace=trace,
            validator=default_seed_validator(),
        )
        assert result.cache_hit is True
        assert provider.calls == []
        assert trace.records[0]["validation_signal"] is None
        assert result.validation_signal is None

    async def test_skip_cache_on_signal_omits_flagged_output(self) -> None:
        """skip_cache_on_signal=True + 거짓 출력 → 캐시 미적재, 그러나 텍스트·신호는 반환."""
        provider = RecordingProvider(text="2 + 2 = 5")
        cache = InMemoryCache()
        result = await generate(
            _sync_local_request(),
            "프롬프트",
            "시스템",
            provider=provider,
            cache=cache,
            trace=RecordingTraceSink(),
            validator=default_seed_validator(),
            skip_cache_on_signal=True,
        )
        # 캐시에는 *남지 않는다*(증명된 거짓 콘텐츠 캐시 위생).
        key = cache_key_for("프롬프트", "시스템", result.decision)
        assert await cache.get(key) is None
        # 그러나 호출자에겐 원시 출력+신호가 그대로 간다(비차단·캐시만 건너뜀).
        assert result.text == "2 + 2 = 5"
        assert isinstance(result.validation_signal, str)
        assert "arithmetic error" in result.validation_signal

    async def test_skip_cache_on_signal_keeps_clean_output(self) -> None:
        """skip_cache_on_signal=True여도 신호 없으면(통과) 정상 적재."""
        provider = RecordingProvider(text="2 + 2 = 4")
        cache = InMemoryCache()
        result = await generate(
            _sync_local_request(),
            "프롬프트",
            "시스템",
            provider=provider,
            cache=cache,
            trace=RecordingTraceSink(),
            validator=default_seed_validator(),
            skip_cache_on_signal=True,
        )
        key = cache_key_for("프롬프트", "시스템", result.decision)
        assert await cache.get(key) == "2 + 2 = 4"  # 통과 → 적재됨
        assert result.validation_signal is None

    async def test_skip_disabled_caches_even_when_flagged(self) -> None:
        """기본(skip=False) → 신호 나도 캐시 적재(기존 동작 불변·비차단)."""
        provider = RecordingProvider(text="5 < 3")
        cache = InMemoryCache()
        result = await generate(
            _sync_local_request(),
            "프롬프트",
            "시스템",
            provider=provider,
            cache=cache,
            trace=RecordingTraceSink(),
            validator=default_seed_validator(),
            # skip_cache_on_signal 미지정 → 기본 False
        )
        key = cache_key_for("프롬프트", "시스템", result.decision)
        assert await cache.get(key) == "5 < 3"  # 적재됨(기존 동작)
        assert isinstance(result.validation_signal, str)

    async def test_skip_without_validator_no_effect(self) -> None:
        """validator 미주입 → 신호 없음 → skip=True여도 정상 적재(무효과)."""
        provider = RecordingProvider(text="8 != 8")
        cache = InMemoryCache()
        result = await generate(
            _sync_local_request(),
            "프롬프트",
            "시스템",
            provider=provider,
            cache=cache,
            trace=RecordingTraceSink(),
            skip_cache_on_signal=True,
            # validator 미주입 → 신호 None → skip 무효과
        )
        key = cache_key_for("프롬프트", "시스템", result.decision)
        assert await cache.get(key) == "8 != 8"
        assert result.validation_signal is None

    async def test_queued_result_signal_is_none(self) -> None:
        """비동기(QUALITY) 큐잉 결과는 텍스트가 없으므로 validation_signal=None."""
        result = await generate(
            _quality_request(),
            "p",
            "s",
            provider=RecordingProvider(),
            cache=InMemoryCache(),
            trace=RecordingTraceSink(),
            queue=RecordingQueue(),
            validator=default_seed_validator(),
        )
        assert result.is_queued is True
        assert result.validation_signal is None


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
