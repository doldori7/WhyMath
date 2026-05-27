"""빌드타임 사전적재(pre-warm) 하니스 단위테스트 — InMemoryCache + 가짜 deps.

핵심 검증(슬라이스 1 위험 표면):
  - **킬러 e2e**: pre-warm 후 동일 (req, prompt, system)으로 `pipeline.generate` 호출 시
    `cache_hit=True` (런타임 키와 정합 — 사전생성 가치의 전부).
  - 두 모드: 인제스트(precomputed_response) vs 생성(provider 호출).
  - 검증 게이트: 통과 시드만 캐시에 적재.
  - QUALITY async는 런타임이 캐시를 안 치므로 사전적재 의미 없음 → error 표시.
  - 단일 항목 실패가 배치 전체를 깨지 않음.
  - JSONL 로더·리포트 포매터.

설계 정본: MEMORY.md 2026-05-20 + 03a §F.1 캐시 키.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from whymath_backend.l3 import pipeline
from whymath_backend.l3.interfaces import InMemoryCache, RecordingTraceSink
from whymath_backend.l3.models import RoutingDecision, RoutingRequest
from whymath_backend.l3.pregenerate import (
    BasicSeedValidator,
    CachePrewarmer,
    PregenItem,
    PrewarmItemResult,
    PrewarmReport,
    SeedValidator,
)
from whymath_backend.l3.pregenerate.__main__ import format_report, load_items
from whymath_backend.l3.router import Router, cache_key_for


# ──────────────────────────────────────────────────────────────────────────
# 가짜 dependencies
# ──────────────────────────────────────────────────────────────────────────
class FakePregenProvider:
    def __init__(self, *, text: str = "GENERATED", raises: Exception | None = None) -> None:
        self._text = text
        self._raises = raises
        self.calls: list[tuple[str, str, RoutingDecision]] = []

    async def generate(self, prompt: str, system: str, decision: RoutingDecision) -> str:
        self.calls.append((prompt, system, decision))
        if self._raises is not None:
            raise self._raises
        return self._text


class AlwaysFailValidator:
    def validate(self, item: PregenItem, response: str) -> str | None:
        return "always fail"


class AlwaysPassValidator:
    def validate(self, item: PregenItem, response: str) -> str | None:
        return None


class RaisingCache:
    """get/set에서 예외를 던지는 가짜 캐시 — prewarmer의 캐시 오류 경로 검증용."""

    def __init__(
        self,
        *,
        raise_on_get: Exception | None = None,
        raise_on_set: Exception | None = None,
    ) -> None:
        self._raise_on_get = raise_on_get
        self._raise_on_set = raise_on_set

    async def get(self, key: str) -> str | None:
        if self._raise_on_get is not None:
            raise self._raise_on_get
        return None

    async def set(self, key: str, value: str, ttl_seconds: int) -> None:
        if self._raise_on_set is not None:
            raise self._raise_on_set


# ── 결정·항목 헬퍼 ──
def _local_sync_request(**overrides: Any) -> RoutingRequest:
    """LOCAL/sync로 라우팅되는 기본 요청 (free + 기본 신호)."""
    base: dict[str, Any] = {
        "task_type": "explain",
        "difficulty": "easy",
        "requires_reasoning": False,
        "student_subscription": "free",
        "sync": True,
    }
    base.update(overrides)
    return RoutingRequest(**base)


def _quality_async_request() -> RoutingRequest:
    """QUALITY/async로 라우팅되는 요청 (call_site=self_verify)."""
    return RoutingRequest(
        task_type="self_verify",
        difficulty="hard",
        requires_reasoning=True,
        student_subscription="free",
        sync=False,
        call_site="self_verify",
    )


def _item(
    *,
    prompt: str = "p",
    system: str = "s",
    request: RoutingRequest | None = None,
    precomputed: str | None = None,
) -> PregenItem:
    return PregenItem(
        prompt=prompt,
        system=system,
        request=request if request is not None else _local_sync_request(),
        precomputed_response=precomputed,
    )


def _expected_key(item: PregenItem) -> str:
    """런타임이 계산할 cache_key를 똑같이 산출 — 키 정합 단정용."""
    decision = Router().route(item.request)
    return cache_key_for(item.prompt, item.system, decision)


# ──────────────────────────────────────────────────────────────────────────
# 리포트 집계
# ──────────────────────────────────────────────────────────────────────────
class TestPrewarmReport:
    def test_aggregates_counts_from_items(self) -> None:
        report = PrewarmReport(
            items=(
                PrewarmItemResult(cache_key="k1", status="written"),
                PrewarmItemResult(cache_key="k2", status="written"),
                PrewarmItemResult(cache_key="k3", status="skipped_exists"),
                PrewarmItemResult(cache_key="k4", status="failed_validation", error="r"),
                PrewarmItemResult(cache_key="", status="error", error="e"),
            )
        )
        assert report.total == 5
        assert report.written == 2
        assert report.skipped_exists == 1
        assert report.failed_validation == 1
        assert report.errored == 1


# ──────────────────────────────────────────────────────────────────────────
# BasicSeedValidator — 최소 시드 위생
# ──────────────────────────────────────────────────────────────────────────
class TestBasicSeedValidator:
    def test_empty_or_whitespace_fails(self) -> None:
        v = BasicSeedValidator()
        assert v.validate(_item(), "") == "empty response"
        assert v.validate(_item(), "   \n\t") == "empty response"

    def test_short_response_fails(self) -> None:
        v = BasicSeedValidator(min_length=10)
        failure = v.validate(_item(), "short")
        assert failure is not None
        assert "too short" in failure

    def test_pass_normal_response(self) -> None:
        v = BasicSeedValidator(min_length=3)
        assert v.validate(_item(), "ok answer") is None

    def test_error_marker_present_fails_case_insensitive(self) -> None:
        v = BasicSeedValidator(error_markers=("ERROR", "<error>"))
        failure = v.validate(_item(), "something <ERROR> in here")
        assert failure is not None and "error marker" in failure
        # 다른 케이스의 marker도 잡힘
        assert v.validate(_item(), "all good <Error>") is not None
        assert v.validate(_item(), "all good") is None

    def test_negative_min_length_rejected(self) -> None:
        with pytest.raises(ValueError):
            BasicSeedValidator(min_length=-1)

    def test_satisfies_seed_validator_protocol(self) -> None:
        assert isinstance(BasicSeedValidator(), SeedValidator)


# ──────────────────────────────────────────────────────────────────────────
# CachePrewarmer
# ──────────────────────────────────────────────────────────────────────────
class TestCachePrewarmer:
    async def test_ingest_mode_writes_without_provider_call(self) -> None:
        cache = InMemoryCache()
        provider = FakePregenProvider()
        prewarmer = CachePrewarmer(
            provider=provider, cache=cache, validator=AlwaysPassValidator()
        )
        item = _item(precomputed="INGESTED")

        report = await prewarmer.prewarm([item])

        assert report.written == 1
        assert provider.calls == []  # 인제스트 모드 → provider 미호출
        assert await cache.get(_expected_key(item)) == "INGESTED"

    async def test_generate_mode_calls_provider_and_writes(self) -> None:
        cache = InMemoryCache()
        provider = FakePregenProvider(text="FROM_PROVIDER")
        prewarmer = CachePrewarmer(
            provider=provider, cache=cache, validator=AlwaysPassValidator()
        )
        item = _item()  # precomputed=None → 생성 모드

        report = await prewarmer.prewarm([item])

        assert report.written == 1
        assert len(provider.calls) == 1
        assert await cache.get(_expected_key(item)) == "FROM_PROVIDER"

    async def test_validation_failure_does_not_write_to_cache(self) -> None:
        cache = InMemoryCache()
        prewarmer = CachePrewarmer(
            provider=FakePregenProvider(text="bad"),
            cache=cache,
            validator=AlwaysFailValidator(),
        )
        item = _item()

        report = await prewarmer.prewarm([item])

        assert report.failed_validation == 1
        assert report.written == 0
        assert await cache.get(_expected_key(item)) is None

    async def test_overwrite_false_skips_existing_key(self) -> None:
        cache = InMemoryCache()
        prewarmer = CachePrewarmer(
            provider=FakePregenProvider(), cache=cache, validator=AlwaysPassValidator()
        )
        item = _item(precomputed="V1")
        await prewarmer.prewarm([item])

        # 두번째: 같은 키, 다른 값 → 스킵, V1 유지
        report = await prewarmer.prewarm([_item(precomputed="V2")])

        assert report.skipped_exists == 1
        assert report.written == 0
        assert await cache.get(_expected_key(item)) == "V1"

    async def test_overwrite_true_replaces_existing(self) -> None:
        cache = InMemoryCache()
        prewarmer = CachePrewarmer(
            provider=FakePregenProvider(), cache=cache, validator=AlwaysPassValidator()
        )
        await prewarmer.prewarm([_item(precomputed="V1")])

        report = await prewarmer.prewarm([_item(precomputed="V2")], overwrite=True)

        assert report.written == 1
        assert await cache.get(_expected_key(_item())) == "V2"

    async def test_quality_async_decision_returns_error_no_cache_write(self) -> None:
        """QUALITY async는 런타임이 캐시를 안 치므로 사전적재 의미 없음 → 명시 error."""
        cache = InMemoryCache()
        provider = FakePregenProvider()
        prewarmer = CachePrewarmer(
            provider=provider, cache=cache, validator=AlwaysPassValidator()
        )

        report = await prewarmer.prewarm(
            [_item(request=_quality_async_request(), precomputed="X")]
        )

        assert report.errored == 1
        assert "QUALITY async" in (report.items[0].error or "")
        assert provider.calls == []

    async def test_provider_error_recorded_as_error_item(self) -> None:
        cache = InMemoryCache()
        prewarmer = CachePrewarmer(
            provider=FakePregenProvider(raises=RuntimeError("boom")),
            cache=cache,
            validator=AlwaysPassValidator(),
        )

        report = await prewarmer.prewarm([_item()])  # 생성 모드

        assert report.errored == 1
        assert "provider.generate failed" in (report.items[0].error or "")

    async def test_batch_continues_past_single_failure(self) -> None:
        """단일 항목 실패가 배치 전체를 깨지 않음 — 나머지는 계속 처리."""
        cache = InMemoryCache()
        prewarmer = CachePrewarmer(
            provider=FakePregenProvider(raises=RuntimeError("boom")),
            cache=cache,
            validator=AlwaysPassValidator(),
        )

        report = await prewarmer.prewarm(
            [
                _item(prompt="bad"),  # 생성 모드 → provider 오류
                _item(prompt="good", precomputed="OK"),  # 인제스트 → 성공
            ]
        )

        assert report.total == 2
        assert report.errored == 1
        assert report.written == 1

    async def test_cache_get_error_recorded(self) -> None:
        """overwrite=False 경로에서 cache.get 예외 → 항목 status=error로 흡수."""
        prewarmer = CachePrewarmer(
            provider=FakePregenProvider(),
            cache=RaisingCache(raise_on_get=ConnectionError("redis down")),
            validator=AlwaysPassValidator(),
        )
        report = await prewarmer.prewarm([_item(precomputed="X")])
        assert report.errored == 1
        assert "cache.get failed" in (report.items[0].error or "")

    async def test_cache_set_error_recorded(self) -> None:
        """cache.set 예외 → 항목 status=error로 흡수(overwrite=True로 get은 건너뜀)."""
        prewarmer = CachePrewarmer(
            provider=FakePregenProvider(),
            cache=RaisingCache(raise_on_set=ConnectionError("redis down")),
            validator=AlwaysPassValidator(),
        )
        report = await prewarmer.prewarm([_item(precomputed="X")], overwrite=True)
        assert report.errored == 1
        assert "cache.set failed" in (report.items[0].error or "")


# ──────────────────────────────────────────────────────────────────────────
# 킬러 테스트 — 사전적재 ↔ pipeline.generate 키 정합 e2e
# ──────────────────────────────────────────────────────────────────────────
class TestPrewarmHitsRuntimeCache:
    async def test_prewarmed_item_becomes_runtime_cache_hit(self) -> None:
        """사전적재 후 같은 (req, prompt, system)으로 pipeline.generate 호출 시
        cache_hit=True, runtime provider 미호출, 텍스트=사전적재 값 — *키 정합 증명*."""
        cache = InMemoryCache()
        req = _local_sync_request()
        prompt = "이차방정식이 뭐야?"
        system = "너는 수학 코치다"

        # 1) 사전적재 — 인제스트로 PREWARMED를 캐시에 넣는다.
        prewarmer = CachePrewarmer(
            provider=FakePregenProvider(text="UNUSED_PREWARM"),
            cache=cache,
            validator=AlwaysPassValidator(),
        )
        report = await prewarmer.prewarm(
            [PregenItem(prompt=prompt, system=system, request=req, precomputed_response="PREWARMED")]
        )
        assert report.written == 1

        # 2) 런타임 pipeline.generate — *다른* provider 주입(호출되면 안 됨).
        runtime_provider = FakePregenProvider(text="UNUSED_RUNTIME")
        result = await pipeline.generate(
            req,
            prompt,
            system,
            provider=runtime_provider,
            cache=cache,  # 같은 인스턴스
            trace=RecordingTraceSink(),
        )

        assert result.cache_hit is True
        assert result.text == "PREWARMED"
        assert runtime_provider.calls == []  # 키 정합으로 provider 미호출


# ──────────────────────────────────────────────────────────────────────────
# CLI 로더 / 포매터
# ──────────────────────────────────────────────────────────────────────────
_REQ_JSON = (
    '{"task_type":"explain","difficulty":"easy","requires_reasoning":false,'
    '"student_subscription":"free","sync":true}'
)


class TestLoadItems:
    def test_parses_single_line(self) -> None:
        line = f'{{"prompt":"p","system":"s","request":{_REQ_JSON},"precomputed_response":"X"}}'
        items = load_items(line + "\n")
        assert len(items) == 1
        assert items[0].prompt == "p"
        assert items[0].precomputed_response == "X"

    def test_skips_blank_lines_and_comments(self) -> None:
        text = (
            "# 주석은 무시\n"
            "\n"
            "   \n"
            f'{{"prompt":"p","system":"s","request":{_REQ_JSON}}}\n'
        )
        items = load_items(text)
        assert len(items) == 1
        assert items[0].precomputed_response is None  # 없으면 None 기본값

    def test_invalid_json_raises_with_line_number(self) -> None:
        text = (
            f'{{"prompt":"p","system":"s","request":{_REQ_JSON}}}\n'
            "not-json-here\n"
        )
        with pytest.raises(ValueError, match="line 2"):
            load_items(text)


class TestFormatReport:
    def test_summary_includes_counts(self) -> None:
        report = PrewarmReport(
            items=(
                PrewarmItemResult(cache_key="k1", status="written"),
                PrewarmItemResult(cache_key="", status="error", error="boom"),
            )
        )
        out = format_report(report)
        assert "total=2" in out
        assert "written=1" in out
        assert "errored=1" in out
        # 실패 사유는 상세 줄에 노출
        assert "boom" in out

    def test_written_items_not_individually_listed(self) -> None:
        report = PrewarmReport(items=(PrewarmItemResult(cache_key="k1", status="written"),))
        out = format_report(report)
        assert "[written]" not in out  # 정상 항목은 요약만


# ──────────────────────────────────────────────────────────────────────────
# CLI (main / _run) — 빈 스펙으로 deps 지연성 활용 (네트워크 없이)
# ──────────────────────────────────────────────────────────────────────────
class TestCli:
    def test_main_help_exits_zero(self) -> None:
        """--help → argparse가 SystemExit(0)."""
        from whymath_backend.l3.pregenerate.__main__ import main

        with pytest.raises(SystemExit) as exc_info:
            main(["--help"])
        assert exc_info.value.code == 0

    def test_main_with_empty_specs_returns_zero(self, tmp_path: Path) -> None:
        """빈 스펙(주석·빈줄만) → main이 0 종료. 기본 deps는 지연이라 네트워크 안 탐.

        CompositeProvider(Ollama+Anthropic)·RedisCache·BasicSeedValidator를 구성하지만
        항목이 0개라 provider/cache 호출이 일어나지 않는다 → 실 Ollama·Anthropic·Redis
        없이도 통과(생성자 자체는 네트워크를 안 탐).
        """
        from whymath_backend.l3.pregenerate.__main__ import main

        spec_file = tmp_path / "empty.jsonl"
        spec_file.write_text("# 주석만\n\n", encoding="utf-8")
        assert main([str(spec_file)]) == 0
