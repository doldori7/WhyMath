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
    ChainValidator,
    PregenItem,
    PrewarmItemResult,
    PrewarmReport,
    SeedValidator,
    SymPyArithmeticValidator,
    SymPyInequalityValidator,
    default_seed_validator,
)
from whymath_backend.l3.pregenerate.__main__ import format_report, load_items
from whymath_backend.l3.pregenerate.validator import (
    _equality_is_false,
    _inequality_is_false,
)
from whymath_backend.l3.router import Router, cache_key_for


# ──────────────────────────────────────────────────────────────────────────
# 가짜 dependencies
# ──────────────────────────────────────────────────────────────────────────
class FakePregenProvider:
    def __init__(
        self, *, text: str = "GENERATED", raises: Exception | None = None
    ) -> None:
        self._text = text
        self._raises = raises
        self.calls: list[tuple[str, str, RoutingDecision]] = []

    async def generate(
        self, prompt: str, system: str, decision: RoutingDecision
    ) -> str:
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
                PrewarmItemResult(
                    cache_key="k4", status="failed_validation", error="r"
                ),
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
# SymPyArithmeticValidator — 산술 등식 도구 검증 (보수적, false positive 0)
# ──────────────────────────────────────────────────────────────────────────
class TestSymPyArithmeticValidator:
    def test_true_equality_passes(self) -> None:
        assert SymPyArithmeticValidator().validate(_item(), "2 + 2 = 4") is None

    def test_false_equality_fails(self) -> None:
        reason = SymPyArithmeticValidator().validate(_item(), "2 + 2 = 5")
        assert reason is not None
        assert "arithmetic error" in reason

    def test_unicode_multiplication_normalized(self) -> None:
        v = SymPyArithmeticValidator()
        assert v.validate(_item(), "3 × 4 = 12") is None
        assert v.validate(_item(), "3 × 4 = 11") is not None

    def test_unicode_division(self) -> None:
        v = SymPyArithmeticValidator()
        assert v.validate(_item(), "10 ÷ 2 = 5") is None
        assert v.validate(_item(), "10 ÷ 2 = 6") is not None

    def test_unicode_minus_sign_normalized(self) -> None:
        v = SymPyArithmeticValidator()
        # U+2212 MINUS SIGN (하이픈-마이너스 아님)
        assert v.validate(_item(), "7 − 2 = 5") is None
        assert v.validate(_item(), "7 − 2 = 4") is not None

    def test_decimals(self) -> None:
        v = SymPyArithmeticValidator()
        assert v.validate(_item(), "0.5 + 0.5 = 1.0") is None
        assert v.validate(_item(), "0.5 + 0.5 = 2") is not None

    def test_fraction_equals_decimal(self) -> None:
        assert SymPyArithmeticValidator().validate(_item(), "1/2 = 0.5") is None

    def test_power_caret(self) -> None:
        v = SymPyArithmeticValidator()
        assert v.validate(_item(), "2^3 = 8") is None
        assert v.validate(_item(), "2^3 = 9") is not None

    def test_parentheses(self) -> None:
        v = SymPyArithmeticValidator()
        assert v.validate(_item(), "(2 + 3) * 2 = 10") is None
        assert v.validate(_item(), "(2 + 3) * 2 = 11") is not None

    def test_label_prefixed_equation_validated(self) -> None:
        """콜론·공백으로 구분된 등식은 검사된다(독립 인정)."""
        reason = SymPyArithmeticValidator().validate(_item(), "답: 2 + 2 = 5")
        assert reason is not None

    def test_multiline_each_line_checked(self) -> None:
        """줄마다 독립 검사 — 둘째 줄의 거짓 등식도 잡는다."""
        reason = SymPyArithmeticValidator().validate(_item(), "2 + 2 = 4\n5 + 5 = 11")
        assert reason is not None
        assert "5 + 5 = 11" in reason

    def test_symbolic_equation_no_false_positive(self) -> None:
        """심볼릭 등식(x+1=2)은 false positive 없이 통과(건너뜀)."""
        v = SymPyArithmeticValidator()
        assert v.validate(_item(), "방정식 x + 1 = 2 를 풀면 x = 1") is None
        assert v.validate(_item(), "a*x^2 + b*x + c = 0") is None
        # 연산자 인접 숫자("+ 1 = 2")를 떼어내 거짓 판정하지 않는다.
        assert v.validate(_item(), "y + 1 = 2") is None

    def test_no_arithmetic_passes(self) -> None:
        assert (
            SymPyArithmeticValidator().validate(
                _item(), "이차방정식의 개념을 설명합니다."
            )
            is None
        )

    def test_inline_prose_prefixed_is_skipped_conservatively(self) -> None:
        """한글 단어가 공백으로 바로 앞에 붙은 인라인 등식은 보수적으로 건너뜀(통과)."""
        # 거짓이지만 한글 인접이라 추출 불가 → 통과(미탐). 보수적: false positive 0 우선.
        assert (
            SymPyArithmeticValidator().validate(_item(), "정답은 2 + 2 = 5 입니다")
            is None
        )

    def test_max_checks_must_be_positive(self) -> None:
        with pytest.raises(ValueError):
            SymPyArithmeticValidator(max_checks=0)

    def test_max_checks_limits_validation(self) -> None:
        """max_checks 초과 시 이후 등식은 검사하지 않는다(break) — 둘째 줄 거짓을 미검사."""
        v = SymPyArithmeticValidator(max_checks=1)
        assert v.validate(_item(), "1 = 1\n2 = 3") is None

    def test_satisfies_protocol(self) -> None:
        assert isinstance(SymPyArithmeticValidator(), SeedValidator)


# ──────────────────────────────────────────────────────────────────────────
# SymPyInequalityValidator — 부등식 도구 검증 (slice 35·보수적, false positive 0)
# ──────────────────────────────────────────────────────────────────────────
class TestSymPyInequalityValidator:
    def test_true_inequality_passes(self) -> None:
        v = SymPyInequalityValidator()
        assert v.validate(_item(), "3 < 5") is None
        assert v.validate(_item(), "9 > 2") is None
        assert v.validate(_item(), "3 <= 3") is None  # 경계 참

    def test_false_inequality_fails(self) -> None:
        reason = SymPyInequalityValidator().validate(_item(), "5 < 3")
        assert reason is not None
        assert "inequality error" in reason

    def test_all_operators(self) -> None:
        v = SymPyInequalityValidator()
        assert v.validate(_item(), "7 > 9") is not None  # 거짓
        assert v.validate(_item(), "9 >= 10") is not None
        assert v.validate(_item(), "5 <= 4") is not None
        assert v.validate(_item(), "2 < 1") is not None

    def test_unicode_le_ge_normalized(self) -> None:
        v = SymPyInequalityValidator()
        assert v.validate(_item(), "5 ≤ 3") is not None  # 거짓
        assert v.validate(_item(), "2 ≥ 9") is not None
        assert v.validate(_item(), "3 ≤ 5") is None  # 참

    def test_arithmetic_operand_inequality(self) -> None:
        v = SymPyInequalityValidator()
        assert v.validate(_item(), "2 + 2 < 3") is not None  # 4<3 거짓
        assert v.validate(_item(), "2 + 2 > 3") is None  # 4>3 참

    def test_symbolic_no_false_positive(self) -> None:
        """심볼릭 부등식(x < 2)은 통과(판정 불가)."""
        assert SymPyInequalityValidator().validate(_item(), "x < 2 이면") is None

    def test_chained_fragment_skipped(self) -> None:
        """연쇄 부등식 'a < b < c'의 조각을 떼어 거짓 판정하지 않는다(보수적)."""
        # "2 < 5 < 3" — 첫 매치 '2 < 5'(참)만 검사·'5 < 3' 조각은 인접 <로 건너뜀
        assert SymPyInequalityValidator().validate(_item(), "2 < 5 < 3") is None

    def test_no_inequality_passes(self) -> None:
        assert SymPyInequalityValidator().validate(_item(), "부등식 개념 설명") is None

    def test_max_checks_must_be_positive(self) -> None:
        with pytest.raises(ValueError):
            SymPyInequalityValidator(max_checks=0)

    def test_max_checks_limits_validation(self) -> None:
        """max_checks 초과 시 break — 이후 거짓 부등식을 미검사(보수적)."""
        v = SymPyInequalityValidator(max_checks=1)
        assert v.validate(_item(), "1 < 2\n5 < 3") is None

    def test_chain_with_arithmetic(self) -> None:
        """등식·부등식 검증을 ChainValidator로 묶어 둘 다 적용(줄 독립으로 표면화)."""
        chain = ChainValidator([SymPyArithmeticValidator(), SymPyInequalityValidator()])
        assert chain.validate(_item(), "2 + 2 = 4\n3 < 5") is None  # 둘 다 참
        assert chain.validate(_item(), "2 + 2 = 4\n5 < 3") is not None  # 부등식 거짓
        assert chain.validate(_item(), "2 + 2 = 5\n3 < 5") is not None  # 등식 거짓

    def test_satisfies_protocol(self) -> None:
        assert isinstance(SymPyInequalityValidator(), SeedValidator)


class TestInequalityHelper:
    """_inequality_is_false 직접 단위테스트 — 정규식이 못 거르는 방어 분기 커버."""

    def test_false_proven(self) -> None:
        assert _inequality_is_false("5", "3", "<") is not None
        assert _inequality_is_false("3", "5", "<") is None  # 참

    def test_symbolic_skipped(self) -> None:
        assert _inequality_is_false("x", "2", "<") is None  # 심볼릭 판정 불가

    def test_unparseable_skipped(self) -> None:
        assert _inequality_is_false("(", "2", "<") is None  # 파싱 실패 보수적 통과


class TestEqualityHelper:
    """_equality_is_false 직접 단위테스트 — 정규식이 거르지 못하는 방어 분기 커버."""

    def test_true_equality(self) -> None:
        assert _equality_is_false("2+2", "4") is None

    def test_false_equality(self) -> None:
        reason = _equality_is_false("2+2", "5")
        assert reason is not None and "arithmetic error" in reason

    def test_symbolic_skipped(self) -> None:
        """자유 변수가 있으면 판정 불가 → None (free_symbols 분기)."""
        assert _equality_is_false("x", "1") is None

    def test_parse_error_skipped(self) -> None:
        """sympify 파싱 실패는 보수적으로 None (except 분기)."""
        assert _equality_is_false("(1+", "2") is None


# ──────────────────────────────────────────────────────────────────────────
# ChainValidator — AND 게이트
# ──────────────────────────────────────────────────────────────────────────
class TestChainValidator:
    def test_all_pass_returns_none(self) -> None:
        chain = ChainValidator([BasicSeedValidator(), SymPyArithmeticValidator()])
        assert chain.validate(_item(), "2 + 2 = 4 입니다") is None

    def test_first_failure_returned_in_order(self) -> None:
        chain = ChainValidator([AlwaysFailValidator(), SymPyArithmeticValidator()])
        assert chain.validate(_item(), "2 + 2 = 4") == "always fail"

    def test_basic_then_sympy_basic_fails_first(self) -> None:
        chain = ChainValidator([BasicSeedValidator(), SymPyArithmeticValidator()])
        # 빈 응답 → Basic이 먼저 탈락
        assert chain.validate(_item(), "") == "empty response"

    def test_basic_passes_sympy_catches_arithmetic(self) -> None:
        chain = ChainValidator([BasicSeedValidator(), SymPyArithmeticValidator()])
        reason = chain.validate(_item(), "2 + 2 = 5")
        assert reason is not None
        assert "arithmetic error" in reason

    def test_empty_chain_passes(self) -> None:
        assert ChainValidator([]).validate(_item(), "anything") is None

    def test_satisfies_protocol(self) -> None:
        assert isinstance(ChainValidator([]), SeedValidator)


# ──────────────────────────────────────────────────────────────────────────
# default_seed_validator — CLI·호출자 공용 기본 게이트(위생→산술→부등식)
# ──────────────────────────────────────────────────────────────────────────
class TestDefaultSeedValidator:
    def test_returns_chain_satisfying_protocol(self) -> None:
        assert isinstance(default_seed_validator(), ChainValidator)
        assert isinstance(default_seed_validator(), SeedValidator)

    def test_clean_response_passes(self) -> None:
        assert (
            default_seed_validator().validate(_item(), "2 + 2 = 4, 그리고 3 < 5")
            is None
        )

    def test_catches_false_arithmetic(self) -> None:
        reason = default_seed_validator().validate(_item(), "2 + 2 = 5")
        assert reason is not None
        assert "arithmetic error" in reason

    def test_catches_false_inequality(self) -> None:
        reason = default_seed_validator().validate(_item(), "5 < 3")
        assert reason is not None
        assert "inequality error" in reason

    def test_hygiene_runs_first(self) -> None:
        # 위생(BasicSeedValidator)이 체인 선두 → 빈 응답은 산술/부등식 전에 탈락.
        assert default_seed_validator().validate(_item(), "") == "empty response"

    def test_min_length_threaded_through(self) -> None:
        reason = default_seed_validator(min_length=10).validate(_item(), "짧음")
        assert reason is not None
        assert "too short" in reason


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

    async def test_sympy_validator_rejects_bad_arithmetic_seed(self) -> None:
        """프리워머 + SymPy 검증기: 산술 거짓 시드는 캐시에 적재되지 않는다."""
        cache = InMemoryCache()
        prewarmer = CachePrewarmer(
            provider=FakePregenProvider(),
            cache=cache,
            validator=SymPyArithmeticValidator(),
        )
        item = _item(precomputed="답: 2 + 2 = 5")

        report = await prewarmer.prewarm([item])

        assert report.failed_validation == 1
        assert report.written == 0
        assert await cache.get(_expected_key(item)) is None


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
            [
                PregenItem(
                    prompt=prompt,
                    system=system,
                    request=req,
                    precomputed_response="PREWARMED",
                )
            ]
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
            f'{{"prompt":"p","system":"s","request":{_REQ_JSON}}}\n' "not-json-here\n"
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
        report = PrewarmReport(
            items=(PrewarmItemResult(cache_key="k1", status="written"),)
        )
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
