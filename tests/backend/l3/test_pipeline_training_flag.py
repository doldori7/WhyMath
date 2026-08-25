"""pipeline.generate의 training_allowed 메타데이터 전파 단위테스트.

EOS §48·§50에 따라 AI inference 응답 생성 시 별도 ai_training 동의 여부를 Langfuse trace
메타데이터로 전달해야 한다. 본 테스트는 `pipeline.generate`가 `training_allowed` 인자를
받아 `trace.record`에 정확히 흘린다는 배선 계약을 검증한다. provider 동작 제어가 아닌
관측/후속 추적용 계약이다.
"""

from __future__ import annotations

from whymath_backend.l3 import pipeline
from whymath_backend.l3.interfaces import InMemoryCache, RecordingTraceSink
from whymath_backend.l3.models import GenerationResult, RoutingDecision, RoutingRequest


class _StubProvider:
    """텍스트 생성만 반환하는 최소 가짜 provider."""

    async def generate(
        self, prompt: str, system: str, decision: RoutingDecision
    ) -> GenerationResult:
        return GenerationResult(text="stub-output")


def _sync_request() -> RoutingRequest:
    """동기(LOCAL) 라우팅을 유도하는 요청."""
    return RoutingRequest(
        task_type="explain",
        difficulty="easy",
        requires_reasoning=False,
        student_subscription="free",
        sync=True,
    )


class TestPipelineTrainingFlag:
    async def test_training_allowed_true_propagates_to_trace(self) -> None:
        """training_allowed=True를 전달하면 trace 메타데이터에 True가 기록된다."""
        trace = RecordingTraceSink()
        await pipeline.generate(
            _sync_request(),
            "prompt",
            "system",
            provider=_StubProvider(),
            cache=InMemoryCache(),
            trace=trace,
            training_allowed=True,
        )
        assert len(trace.records) == 1
        assert trace.records[0]["training_allowed"] is True

    async def test_training_allowed_false_propagates_to_trace(self) -> None:
        """training_allowed=False를 전달하면 trace 메타데이터에 False가 기록된다."""
        trace = RecordingTraceSink()
        await pipeline.generate(
            _sync_request(),
            "prompt",
            "system",
            provider=_StubProvider(),
            cache=InMemoryCache(),
            trace=trace,
            training_allowed=False,
        )
        assert len(trace.records) == 1
        assert trace.records[0]["training_allowed"] is False

    async def test_training_allowed_none_propagates_to_trace(self) -> None:
        """training_allowed를 생략하면 trace 메타데이터에 None(미측정)이 기록된다."""
        trace = RecordingTraceSink()
        await pipeline.generate(
            _sync_request(),
            "prompt",
            "system",
            provider=_StubProvider(),
            cache=InMemoryCache(),
            trace=trace,
        )
        assert len(trace.records) == 1
        assert trace.records[0]["training_allowed"] is None

    async def test_cache_hit_preserves_training_allowed(self) -> None:
        """캐시 적중 시에도 training_allowed 메타데이터가 보존된다."""
        trace = RecordingTraceSink()
        cache = InMemoryCache()
        req = _sync_request()
        # 첫 호출은 캐시 미스 → 저장.
        await pipeline.generate(
            req,
            "prompt",
            "system",
            provider=_StubProvider(),
            cache=cache,
            trace=trace,
            training_allowed=True,
        )
        # 두 번째 호출은 캐시 히트 → training_allowed=True가 그대로 기록돼야 한다.
        trace2 = RecordingTraceSink()
        await pipeline.generate(
            req,
            "prompt",
            "system",
            provider=_StubProvider(),
            cache=cache,
            trace=trace2,
            training_allowed=True,
        )
        assert len(trace2.records) == 1
        assert trace2.records[0]["cache_hit"] is True
        assert trace2.records[0]["training_allowed"] is True

    async def test_async_path_propagates_training_allowed(self) -> None:
        """QUALITY 비동기 큐잉 경로에서도 training_allowed가 trace에 기록된다."""
        trace = RecordingTraceSink()

        class _StubQueue:
            async def enqueue(self, payload: dict[str, object]) -> str:
                return "job-123"

        # QUALITY로 강제 라우팅.
        request = RoutingRequest(
            task_type="prove",
            difficulty="hard",
            requires_reasoning=True,
            student_subscription="gifted",
            sync=False,
        )
        await pipeline.generate(
            request,
            "prompt",
            "system",
            provider=_StubProvider(),
            cache=InMemoryCache(),
            trace=trace,
            queue=_StubQueue(),
            training_allowed=True,
        )
        assert len(trace.records) == 1
        assert trace.records[0]["training_allowed"] is True
        assert trace.records[0]["mode"] == "async"
