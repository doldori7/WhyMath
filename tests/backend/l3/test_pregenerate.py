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
    SymPyNotEqualValidator,
    SymPySolutionValidator,
    arithmetic_validator,
    default_seed_validator,
    validate_response,
)
from whymath_backend.l3.pregenerate.__main__ import format_report, load_items
from whymath_backend.l3.pregenerate.validator import (
    _CHAIN_ADJACENT,
    _breaks_standalone,
    _equality_is_false,
    _inequality_is_false,
    _is_hangul,
    _not_equal_is_false,
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

    def test_inline_prose_prefixed_now_detected(self) -> None:
        """slice 54 — 한글이 공백으로 앞에 붙은 인라인 등식도 검출(한글=산문 경계).

        slice 34에서는 한글 인접이라 보수적으로 건너뛰었으나(미탐), slice 54가 한글을
        *단어 경계*로 인식해 한국어 풀이("정답은 2 + 2 = 5 입니다")의 거짓 산술도 잡는다.
        """
        reason = SymPyArithmeticValidator().validate(_item(), "정답은 2 + 2 = 5 입니다")
        assert reason is not None
        assert "arithmetic error" in reason

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

    def test_chained_inequality_checks_each_pair(self) -> None:
        """연쇄 부등식 'a < b < c'는 각 인접 쌍을 검사한다(slice 46·룩어헤드)."""
        # "2 < 5 < 3" — '2 < 5'(참)·'5 < 3'(거짓) → 거짓 쌍 탈락(이전엔 보수적 skip).
        reason = SymPyInequalityValidator().validate(_item(), "2 < 5 < 3")
        assert reason is not None and "5 < 3" in reason
        # 전부 참인 연쇄는 통과.
        assert SymPyInequalityValidator().validate(_item(), "2 < 5 < 9") is None

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


# ──────────────────────────────────────────────────────────────────────────
# SymPyNotEqualValidator — 부등(≠) 도구 검증 (관계 연산자 패밀리 완성·보수적)
# ──────────────────────────────────────────────────────────────────────────
class TestSymPyNotEqualValidator:
    def test_true_not_equal_passes(self) -> None:
        v = SymPyNotEqualValidator()
        assert v.validate(_item(), "3 != 5") is None  # 다름 → 참
        assert v.validate(_item(), "2 + 2 != 5") is None  # 4≠5 참

    def test_false_not_equal_fails(self) -> None:
        reason = SymPyNotEqualValidator().validate(_item(), "8 != 8")
        assert reason is not None
        assert "not-equal error" in reason

    def test_arithmetic_operand_false(self) -> None:
        """수치식 양변이 같으면 거짓 — '12/4 ≠ 3'(3≠3)."""
        v = SymPyNotEqualValidator()
        assert v.validate(_item(), "12/4 != 3") is not None  # 3≠3 거짓

    def test_unicode_neq_normalized(self) -> None:
        v = SymPyNotEqualValidator()
        assert v.validate(_item(), "0.5 ≠ 0.50") is not None  # 같음 → 거짓
        assert v.validate(_item(), "0.5 ≠ 0.6") is None  # 다름 → 참

    def test_symbolic_no_false_positive(self) -> None:
        """심볼릭 부등(x ≠ 2)은 통과(판정 불가)."""
        assert SymPyNotEqualValidator().validate(_item(), "x ≠ 2 이면") is None

    def test_factorial_not_misparsed(self) -> None:
        """'5! != 120'은 팩토리얼 인접('!')이라 매치되지 않아 통과(보수적 skip)."""
        assert SymPyNotEqualValidator().validate(_item(), "5! != 120 설명") is None

    def test_non_standalone_skipped(self) -> None:
        """더 큰 식의 일부('= 8 != 8')는 좌측 연산자 인접이라 떼지 않고 건너뜀(보수적)."""
        # '8 != 8'(거짓)이지만 직전 '='로 더 큰 식의 조각 → _is_standalone False → 통과
        assert SymPyNotEqualValidator().validate(_item(), "x = 8 != 8") is None

    def test_no_not_equal_passes(self) -> None:
        assert SymPyNotEqualValidator().validate(_item(), "부등 개념 설명") is None

    def test_max_checks_must_be_positive(self) -> None:
        with pytest.raises(ValueError):
            SymPyNotEqualValidator(max_checks=0)

    def test_max_checks_limits_validation(self) -> None:
        """max_checks 초과 시 break — 이후 거짓 부등을 미검사(보수적)."""
        v = SymPyNotEqualValidator(max_checks=1)
        assert v.validate(_item(), "3 != 5\n8 != 8") is None  # 첫 매치(참)만 검사

    def test_satisfies_protocol(self) -> None:
        assert isinstance(SymPyNotEqualValidator(), SeedValidator)


class TestNotEqualHelper:
    """_not_equal_is_false 직접 단위테스트 — 정규식이 못 거르는 방어 분기 커버."""

    def test_false_proven(self) -> None:
        reason = _not_equal_is_false("12/4", "3")
        assert reason is not None and "not-equal error" in reason

    def test_true_not_equal(self) -> None:
        assert _not_equal_is_false("3", "5") is None  # 다름 → 참

    def test_symbolic_skipped(self) -> None:
        assert _not_equal_is_false("x", "2") is None  # 심볼릭 판정 불가

    def test_unparseable_skipped(self) -> None:
        assert _not_equal_is_false("(1+", "2") is None  # 파싱 실패 보수적 통과


# ──────────────────────────────────────────────────────────────────────────
# 음수 피연산자 — `_NUM_TOKEN` 선두 부호([+-]?). 세 관계 검증기 공통 강화.
# ──────────────────────────────────────────────────────────────────────────
class TestNegativeOperands:
    def test_arithmetic_true_negative_passes(self) -> None:
        v = SymPyArithmeticValidator()
        assert v.validate(_item(), "3 - 10 = -7") is None  # 참
        assert v.validate(_item(), "-5 = -5") is None

    def test_arithmetic_false_negative_flagged(self) -> None:
        v = SymPyArithmeticValidator()
        assert v.validate(_item(), "3 - 10 = -8") is not None  # -7≠-8 거짓
        assert v.validate(_item(), "-5 = -4") is not None

    def test_inequality_with_negatives(self) -> None:
        v = SymPyInequalityValidator()
        assert v.validate(_item(), "5 < -3") is not None  # 거짓
        assert v.validate(_item(), "-5 < 3") is None  # 참
        assert v.validate(_item(), "-2 >= -1") is not None  # 거짓

    def test_not_equal_with_negatives(self) -> None:
        v = SymPyNotEqualValidator()
        assert v.validate(_item(), "-8 != -8") is not None  # 같음 → 거짓
        assert v.validate(_item(), "8 != -8") is None  # 다름 → 참

    def test_subtraction_not_misread_as_sign(self) -> None:
        """'x - 5 = 3'의 '- 5'는 부호가 아니라 뺄셈 — 더 큰 식의 일부라 건너뜀(오판 없음)."""
        # 좌변 'x - 5'는 심볼릭이고, '5 = 3' 조각은 좌측 '-' 인접이라 _is_standalone False.
        assert SymPyArithmeticValidator().validate(_item(), "x - 5 = 3") is None
        # 부호 뒤 공백이면 토큰 성립 안 함('- 5'는 뺄셈으로 남음) — 음수 리터럴 아님.
        assert SymPyArithmeticValidator().validate(_item(), "10 - 5 = 5") is None  # 참

    def test_plus_sign_prefix(self) -> None:
        """선두 '+' 부호도 허용 — '+3 = 3' 참, '+3 = 4' 거짓."""
        v = SymPyArithmeticValidator()
        assert v.validate(_item(), "+3 = 3") is None
        assert v.validate(_item(), "+3 = 4") is not None

    def test_default_chain_catches_negative_false(self) -> None:
        """기본 체인이 음수 결과 거짓 등식을 잡는다(통합)."""
        reason = validate_response(default_seed_validator(), "계산:\n2 - 9 = -6")
        assert reason is not None and "arithmetic error" in reason  # 2-9=-7≠-6


# ──────────────────────────────────────────────────────────────────────────
# 연쇄 등식 — "a = b = c" 각 인접 쌍 검사(룩어헤드 + `_EQ_ADJACENT`)
# ──────────────────────────────────────────────────────────────────────────
class TestChainedEquality:
    def test_chain_all_true_passes(self) -> None:
        v = SymPyArithmeticValidator()
        assert v.validate(_item(), "2 + 3 = 5 = 5") is None
        assert v.validate(_item(), "1 = 1 = 1") is None

    def test_chain_later_pair_false_flagged(self) -> None:
        """첫 쌍이 참이어도 뒤 쌍이 거짓이면 잡는다(연쇄 5=6)."""
        reason = SymPyArithmeticValidator().validate(_item(), "2 + 3 = 5 = 6")
        assert reason is not None
        assert "5 = 6" in reason  # 거짓 쌍이 사유에 명시

    def test_chain_with_symbolic_head(self) -> None:
        """'x = 2+3 = 6' — 심볼릭 좌단은 건너뛰고 수치 쌍(2+3=6)은 검사."""
        reason = SymPyArithmeticValidator().validate(_item(), "x = 2 + 3 = 6")
        assert reason is not None and "arithmetic error" in reason

    def test_three_link_chain_middle_false(self) -> None:
        assert SymPyArithmeticValidator().validate(_item(), "4 = 4 = 5 = 5") is not None

    def test_fragment_guard_still_holds(self) -> None:
        """'x + 1 = 2'의 '1 = 2'는 좌측 '+' 인접이라 여전히 skip(연쇄 아님)."""
        assert SymPyArithmeticValidator().validate(_item(), "x + 1 = 2") is None

    def test_chain_via_default_chain(self) -> None:
        reason = validate_response(default_seed_validator(), "계산: 3 = 3 = 4")
        assert reason is not None and "arithmetic error" in reason


# ──────────────────────────────────────────────────────────────────────────
# 연쇄 부등식 — "a < b < c" 각 인접 쌍 검사(룩어헤드 + `_CHAIN_ADJACENT`, slice 46)
# ──────────────────────────────────────────────────────────────────────────
class TestChainedInequality:
    def test_chain_all_true_passes(self) -> None:
        v = SymPyInequalityValidator()
        assert v.validate(_item(), "1 < 2 < 3 < 4") is None
        assert v.validate(_item(), "2 < 5 < 9") is None

    def test_chain_later_pair_false_flagged(self) -> None:
        """첫 쌍이 참이어도 뒤 쌍이 거짓이면 잡는다(2<5 참·5<3 거짓)."""
        reason = SymPyInequalityValidator().validate(_item(), "2 < 5 < 3")
        assert reason is not None and "5 < 3" in reason

    def test_four_link_chain_last_false(self) -> None:
        assert SymPyInequalityValidator().validate(_item(), "1 < 2 < 3 < 2") is not None

    def test_chain_with_le_operator(self) -> None:
        """`<=` 연쇄도 각 쌍 검사 — '3 <= 3 <= 2'의 '3<=2' 거짓."""
        reason = SymPyInequalityValidator().validate(_item(), "3 <= 3 <= 2")
        assert reason is not None and "3 <= 2" in reason

    def test_symbolic_middle_passes(self) -> None:
        """'1 < x < 3'은 수치 쌍이 없어 통과(심볼릭 구간 제약)."""
        assert SymPyInequalityValidator().validate(_item(), "1 < x < 3") is None

    def test_fragment_guard_holds(self) -> None:
        """'a + 2 < 1'의 '2 < 1'은 좌측 '+' 인접이라 skip(더 큰 식의 일부)."""
        assert SymPyInequalityValidator().validate(_item(), "a + 2 < 1") is None

    def test_chain_via_default_chain(self) -> None:
        reason = validate_response(default_seed_validator(), "범위: 2 < 5 < 3")
        assert reason is not None and "inequality error" in reason


# ──────────────────────────────────────────────────────────────────────────
# validate_response — PregenItem 없는 응답 단독 검증(런타임 재사용 진입점)
# ──────────────────────────────────────────────────────────────────────────
class TestValidateResponse:
    def test_item_optional_validators_accept_none(self) -> None:
        """모든 검증기가 item=None으로도 동작(응답 단독 검증)."""
        assert SymPyArithmeticValidator().validate(None, "2 + 2 = 5") is not None
        assert SymPyInequalityValidator().validate(None, "5 < 3") is not None
        assert SymPyNotEqualValidator().validate(None, "8 != 8") is not None
        assert BasicSeedValidator().validate(None, "") == "empty response"

    def test_clean_response_passes(self) -> None:
        assert validate_response(default_seed_validator(), "2 + 2 = 4, 3 < 5") is None

    def test_catches_false_arithmetic(self) -> None:
        reason = validate_response(default_seed_validator(), "2 + 2 = 5")
        assert reason is not None and "arithmetic error" in reason

    def test_catches_false_inequality(self) -> None:
        reason = validate_response(default_seed_validator(), "7 >= 9")
        assert reason is not None and "inequality error" in reason

    def test_catches_false_not_equal(self) -> None:
        reason = validate_response(default_seed_validator(), "12/4 ≠ 3")
        assert reason is not None and "not-equal error" in reason

    def test_works_with_single_validator(self) -> None:
        # ChainValidator뿐 아니라 임의 SeedValidator에도 동작(헬퍼는 protocol만 의존).
        assert validate_response(SymPyArithmeticValidator(), "3 × 4 = 12") is None

    def test_no_item_dependency_at_call_site(self) -> None:
        # 호출지가 PregenItem을 만들지 않고 문자열만으로 검증(레이어 결합 회피).
        assert validate_response(default_seed_validator(), "수식 없는 설명문") is None


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

    def test_catches_false_not_equal(self) -> None:
        reason = default_seed_validator().validate(_item(), "12/4 ≠ 3")
        assert reason is not None
        assert "not-equal error" in reason

    def test_hygiene_runs_first(self) -> None:
        # 위생(BasicSeedValidator)이 체인 선두 → 빈 응답은 산술/부등식 전에 탈락.
        assert default_seed_validator().validate(_item(), "") == "empty response"

    def test_min_length_threaded_through(self) -> None:
        reason = default_seed_validator(min_length=10).validate(_item(), "짧음")
        assert reason is not None
        assert "too short" in reason


# ──────────────────────────────────────────────────────────────────────────
# arithmetic_validator — 위생 없이 SymPy 관계 검증기만(학생 풀이 슬립 검출용·slice 52)
# ──────────────────────────────────────────────────────────────────────────
class TestArithmeticValidator:
    def test_returns_chain_satisfying_protocol(self) -> None:
        assert isinstance(arithmetic_validator(), ChainValidator)
        assert isinstance(arithmetic_validator(), SeedValidator)

    def test_catches_false_arithmetic(self) -> None:
        reason = arithmetic_validator().validate(_item(), "2 + 2 = 5")
        assert reason is not None
        assert "arithmetic error" in reason

    def test_catches_false_inequality(self) -> None:
        reason = arithmetic_validator().validate(_item(), "5 < 3")
        assert reason is not None
        assert "inequality error" in reason

    def test_catches_false_not_equal(self) -> None:
        reason = arithmetic_validator().validate(_item(), "12/4 ≠ 3")
        assert reason is not None
        assert "not-equal error" in reason

    def test_clean_response_passes(self) -> None:
        assert arithmetic_validator().validate(_item(), "2 + 2 = 4, 그리고 3 < 5") is None

    def test_no_hygiene_empty_passes(self) -> None:
        # 위생(BasicSeedValidator) 미포함 → 빈/짧은 응답은 *탈락하지 않는다*
        # (학생 풀이의 계산 슬립 검출이 목적 — 빈 풀이는 슬립이 아님). default_seed_validator
        # 와의 핵심 차이.
        assert arithmetic_validator().validate(_item(), "") is None
        assert arithmetic_validator().validate(_item(), "짧음") is None

    def test_symbolic_passes(self) -> None:
        # 자유변수(심볼릭)는 판정 불가 → 통과(보수적).
        assert arithmetic_validator().validate(_item(), "x + 1 = 2") is None

    def test_max_checks_threaded_through(self) -> None:
        # max_checks=0이면 ChainValidator 구성요소 생성 시 ValueError(1 이상 강제).
        try:
            arithmetic_validator(max_checks=0)
        except ValueError as exc:
            assert "max_checks" in str(exc)
        else:  # pragma: no cover
            raise AssertionError("max_checks=0이 허용됨")


# ──────────────────────────────────────────────────────────────────────────
# 한글 산문 경계 — 한글을 단어 경계로 인식해 한국어 풀이의 수치 관계 검출 (slice 54)
# ──────────────────────────────────────────────────────────────────────────
class TestHangulProseBoundary:
    def test_is_hangul_syllables_and_jamo(self) -> None:
        assert _is_hangul("가") and _is_hangul("힣") and _is_hangul("계")
        assert _is_hangul("ㄱ") and _is_hangul("ㅏ")
        assert not _is_hangul("x")
        assert not _is_hangul("2")
        assert not _is_hangul("α")  # 그리스 변수는 경계 아님(여전히 식의 일부)

    def test_breaks_standalone_hangul_and_newline_are_boundaries(self) -> None:
        # 한글·개행은 식을 끊지 않음(경계) → False
        assert _breaks_standalone("가", _CHAIN_ADJACENT) is False
        assert _breaks_standalone("\n", _CHAIN_ADJACENT) is False
        # 라틴 변수·연산자·숫자는 더 큰 식의 일부 → True
        assert _breaks_standalone("x", _CHAIN_ADJACENT) is True
        assert _breaks_standalone("+", _CHAIN_ADJACENT) is True
        assert _breaks_standalone("2", _CHAIN_ADJACENT) is True

    def test_korean_prose_false_arithmetic_caught(self) -> None:
        reason = arithmetic_validator().validate(_item(), "계산하면 2 + 3 = 6 입니다")
        assert reason is not None
        assert "arithmetic error" in reason

    def test_korean_prose_false_inequality_caught(self) -> None:
        reason = arithmetic_validator().validate(_item(), "그러므로 5 < 3 이다")
        assert reason is not None
        assert "inequality error" in reason

    def test_korean_prose_false_not_equal_caught(self) -> None:
        reason = arithmetic_validator().validate(_item(), "따라서 12 / 4 ≠ 3 이다")
        assert reason is not None
        assert "not-equal error" in reason

    def test_korean_prose_true_relation_passes(self) -> None:
        # 참인 관계는 한글 인접이어도 통과(거짓만 탈락).
        assert arithmetic_validator().validate(_item(), "계산하면 2 + 3 = 5 입니다") is None

    def test_latin_variable_adjacency_still_skipped(self) -> None:
        # "x2 = 4"는 라틴 변수 인접 → 여전히 건너뜀(false-positive 0 유지).
        assert arithmetic_validator().validate(_item(), "x2 = 4") is None

    def test_right_side_latin_adjacency_skipped(self) -> None:
        # 우변이 더 큰 식의 일부(라틴 인접 "5y")면 우측 경계 검사로 건너뜀 — 거짓 등식이어도 통과.
        assert arithmetic_validator().validate(_item(), "2 = 5y") is None

    def test_default_seed_validator_catches_korean_prose(self) -> None:
        # 빌드타임 LLM 출력 검증도 동일 혜택 — 한국어 설명의 거짓 산술 차단.
        reason = default_seed_validator().validate(_item(), "정리하면 7 − 2 = 4 이다")
        assert reason is not None
        assert "arithmetic error" in reason

    def test_hangul_both_sides(self) -> None:
        # 양옆 모두 한글 — 가운데 거짓 관계 검출.
        reason = arithmetic_validator().validate(_item(), "답은 3 × 3 = 10 입니다")
        assert reason is not None
        assert "arithmetic error" in reason


# ──────────────────────────────────────────────────────────────────────────
# SymPySolutionValidator — 단변수 방정식 + 주장된 해 대입 검증 (slice 56)
# ──────────────────────────────────────────────────────────────────────────
class TestSymPySolutionValidator:
    def test_satisfies_protocol(self) -> None:
        assert isinstance(SymPySolutionValidator(), SeedValidator)

    def test_correct_linear_solution_passes(self) -> None:
        assert SymPySolutionValidator().validate(_item(), "2x + 1 = 7 이므로 x = 3") is None

    def test_wrong_linear_solution_caught(self) -> None:
        reason = SymPySolutionValidator().validate(_item(), "2x + 1 = 7 이므로 x = 5")
        assert reason is not None
        assert "solution error" in reason
        assert "x=5" in reason

    def test_coefficient_juxtaposition_wrong_caught(self) -> None:
        # 암묵적 곱셈 "3x" 파싱(implicit_multiplication) — 틀린 해 검출.
        reason = SymPySolutionValidator().validate(_item(), "3x = 12 이므로 x = 5")
        assert reason is not None
        assert "solution error" in reason

    def test_correct_quadratic_single_root_passes(self) -> None:
        assert SymPySolutionValidator().validate(_item(), "x^2 = 9 이므로 x = 3") is None

    def test_wrong_quadratic_root_caught(self) -> None:
        reason = SymPySolutionValidator().validate(_item(), "x^2 = 9 이므로 x = 4")
        assert reason is not None
        assert "solution error" in reason

    def test_two_roots_skipped_conservatively(self) -> None:
        # 같은 줄에서 변수에 2개 값 주장(두 근) → 다중값 → 보수적 건너뜀(통과).
        assert (
            SymPySolutionValidator().validate(_item(), "x^2 = 9 이므로 x = 3 또는 x = -3")
            is None
        )

    def test_multivariable_equation_skipped(self) -> None:
        # 자유변수 2개(연립) → 단변수 아님 → 건너뜀.
        assert SymPySolutionValidator().validate(_item(), "x + y = 5 이고 x = 2") is None

    def test_cross_line_single_equation_caught(self) -> None:
        # slice 57 — 방정식과 해가 다른 줄이어도 단일 일관 방정식이면 검출(전체 텍스트).
        reason = SymPySolutionValidator().validate(_item(), "2x + 1 = 7\nx = 5")
        assert reason is not None
        assert "solution error" in reason

    def test_multistep_consistent_derivation_correct_passes(self) -> None:
        # 일관된 다단계 유도(공통 해 x=3)·정해 → 통과.
        assert (
            SymPySolutionValidator().validate(_item(), "2x + 1 = 7\n2x = 6\nx = 3") is None
        )

    def test_multistep_consistent_derivation_wrong_caught(self) -> None:
        # 일관된 다단계 유도지만 최종 해가 틀림(x=5, 정해 3) → 탈락.
        reason = SymPySolutionValidator().validate(_item(), "2x + 1 = 7\n2x = 6\nx = 5")
        assert reason is not None
        assert "solution error" in reason

    def test_inconsistent_subproblems_skipped(self) -> None:
        # 같은 변수지만 방정식 상호 모순(공통 해 없음=서로 다른 소문제) → 보수적 skip.
        assert (
            SymPySolutionValidator().validate(_item(), "2x = 6\n3x = 12\nx = 4") is None
        )

    def test_distinct_variables_each_verified(self) -> None:
        # 변수별 독립 검증 — 다른 변수의 소문제는 각자 일관성으로 판정(오해면 탈락).
        reason = SymPySolutionValidator().validate(
            _item(), "문제1: 2a = 6 이므로 a = 5\n문제2: 3b = 12 이므로 b = 4"
        )
        assert reason is not None  # a=5는 오해(정해 3)
        assert "solution error" in reason

    def test_non_polynomial_skipped(self) -> None:
        # 비다항(유리식 1/x)은 풀이 보류 → 보수적 skip(false-positive 0).
        assert SymPySolutionValidator().validate(_item(), "1/x = 2 이고 x = 5") is None

    def test_complex_roots_skipped(self) -> None:
        # 실수 해가 없는 방정식(x^2=-1·복소 근)은 보수적 skip.
        assert SymPySolutionValidator().validate(_item(), "x^2 = -1 이고 x = 1") is None

    def test_pure_numeric_skipped(self) -> None:
        # 변수 0개(순수 수치)는 이 검증기 범위 밖(산술 검증기 담당).
        assert SymPySolutionValidator().validate(_item(), "2 + 3 = 6") is None

    def test_assignment_only_passes(self) -> None:
        # 방정식 없이 해 주장만 → 대입할 식 없음 → 통과.
        assert SymPySolutionValidator().validate(_item(), "x = 5") is None

    def test_reverse_assignment_wrong_caught(self) -> None:
        # "5 = x" 역방향 할당도 인식 — 오해면 탈락.
        reason = SymPySolutionValidator().validate(_item(), "x + 1 = 6 이고 4 = x")
        assert reason is not None
        assert "solution error" in reason

    def test_different_variables_no_false_positive(self) -> None:
        # 방정식 변수(x)와 해 주장 변수(r)가 다르면 페어링 안 함.
        assert SymPySolutionValidator().validate(_item(), "반지름 r = 5, 그리고 2x = 8") is None

    def test_symbolic_without_solution_passes(self) -> None:
        # 해 주장이 없는 순수 심볼릭 식은 통과(판정 불가).
        assert SymPySolutionValidator().validate(_item(), "f(x) = 2x + 1 는 일차함수") is None

    def test_paren_expansion_wrong_caught(self) -> None:
        reason = SymPySolutionValidator().validate(_item(), "2(x + 1) = 10 이므로 x = 3")
        assert reason is not None
        assert "solution error" in reason

    def test_unparseable_token_skipped(self) -> None:
        # 정규식은 매치하나 SymPy 파싱 실패(불균형 괄호 "x)") → 보수적 건너뜀(통과).
        assert SymPySolutionValidator().validate(_item(), "x) = 5") is None

    def test_max_checks_must_be_positive(self) -> None:
        with pytest.raises(ValueError):
            SymPySolutionValidator(max_checks=0)

    def test_max_checks_limits_relations(self) -> None:
        # max_checks=1 → 첫 관계만 스캔. 이후 방정식·해는 미수집(통과).
        v = SymPySolutionValidator(max_checks=1)
        assert v.validate(_item(), "x = 3\n2x = 7 이므로 x = 5") is None


class TestSolutionValidatorInChains:
    """slice 56 — 풀이 검증기가 기본 체인 두 곳에 결선됐는지(빌드타임·학생 풀이)."""

    def test_default_seed_validator_catches_wrong_solution(self) -> None:
        reason = default_seed_validator().validate(_item(), "2x + 1 = 7 이므로 x = 5")
        assert reason is not None
        assert "solution error" in reason

    def test_arithmetic_validator_catches_wrong_solution(self) -> None:
        reason = arithmetic_validator().validate(_item(), "2x + 1 = 7 이므로 x = 5")
        assert reason is not None
        assert "solution error" in reason

    def test_arithmetic_validator_passes_correct_solution(self) -> None:
        assert arithmetic_validator().validate(_item(), "2x + 1 = 7 이므로 x = 3") is None


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
