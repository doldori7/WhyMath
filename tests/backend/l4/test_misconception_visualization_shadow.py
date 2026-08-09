"""L4 오개념 교정 시각화 would-be shadow 단위테스트 — MISC-01(비노출·비차단·never-break·프라이버시).

`observe_misconception_visualization_shadow`를 `asyncio.run`으로 *직접* 호출하고 가짜
`LLMProvider`(정해진 텍스트 반환)로 `visualize_misconception`의 결과를 제어해, 성공/보류/실패
분류·레코드 JSON을 라이브 LLM 없이 검증한다(`test_misconception_shadow.py`의
record_logger 필터 + `model_validate_json` 패턴, `test_misconception_visualize.py`의
`_FakeProvider`/카탈로그 fixture를 답습).

핵심 단언:
- 확정 진단(confidence>0.5) + 유효 L3 출력 → success=True·pattern/level/visualization_type 기록.
- 진단 보류(confidence<0.5) → success=False·error_type=None(실패 아님 — 애초에 L3 미호출).
- L3 검증 실패(InvalidVisualizationSpecError) → error_type에 예외 타입명(침묵 실패 금지)·레코드는
  *여전히* 남는다(judge_shadow의 "실패면 레코드 0"과 의도적으로 다르다 — 이 shadow는 생성
  성공률 자체가 관측 대상이므로 실패도 기록해야 신호가 된다).
- **프라이버시**: 레코드에 학생 원문·spec·caption 없음(id·도메인·패턴·수준 라벨·성공 여부·타입
  라벨·예외 타입명만).
- 반환은 항상 `None`(비노출 — 호출자가 신호 받을 변수 없음).
"""

from __future__ import annotations

import asyncio
import json
import logging

import pytest

from whymath_backend.l3.interfaces import InMemoryCache, RecordingTraceSink
from whymath_backend.l3.models import GenerationResult, RoutingDecision
from whymath_backend.l4.misconception.models import Misconception, MisconceptionMatch
from whymath_backend.l4.misconception.shadow import (
    MisconceptionVisualizationShadowObservation,
    observe_misconception_visualization_shadow,
)

_RECORD_LOGGER = "whymath.l4.misconception.visualization_shadow.record"

_M = Misconception(
    id="distribution-over-power",
    name_kr="제곱 분배",
    domain="대수",
    canonical_statement="(a+b)² = a²+b²",
    counterexample="a=1, b=1",
    signals=("(a+b)²", "a²+b²"),
)

_VALID_JSON = (
    '{"type": "interactive_graph_2d", "spec": {"model": "area"}, '
    '"caption": "(a+b)² 넓이 모델", "interactive": true}'
)
# 학생 원문(레코드에 절대 새지 않아야 함 — 프라이버시 단언 토큰). visualize_misconception의
# concept 프롬프트에는 실려도(L3 입력) shadow 레코드에는 안 실려야 한다.
_LEVEL = "고1"


class _FakeProvider:
    """가짜 LLMProvider — 정해진 텍스트 반환(`test_misconception_visualize.py` 동형)."""

    def __init__(self, text: str) -> None:
        self._text = text
        self.calls = 0

    async def generate(
        self, prompt: str, system: str, decision: RoutingDecision
    ) -> GenerationResult:
        self.calls += 1
        return GenerationResult(self._text)


class _BoomProvider:
    """generate가 항상 raise — never-break(예외 타입명 기록) 검증용."""

    async def generate(
        self, prompt: str, system: str, decision: RoutingDecision
    ) -> GenerationResult:
        raise RuntimeError("provider 강제 실패(never-break 테스트)")


def _match(confidence: float) -> MisconceptionMatch:
    return MisconceptionMatch(misconception=_M, confidence=confidence, matched_signals=())


def _records(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [r.getMessage() for r in caplog.records if r.name == _RECORD_LOGGER]


async def _observe(match: MisconceptionMatch, provider: object) -> None:
    return await observe_misconception_visualization_shadow(
        match,
        _LEVEL,
        provider=provider,  # type: ignore[arg-type]
        cache=InMemoryCache(),
        trace=RecordingTraceSink(),
    )


# ──────────────────────────────────────────────────────────────────────────
# ① 확정 진단(반례/거꾸로 임계 둘 다) → 성공 기록
# ──────────────────────────────────────────────────────────────────────────
class TestConfirmedDiagnosisRecordsSuccess:
    def test_high_confidence_counterexample_success(self, caplog: pytest.LogCaptureFixture) -> None:
        provider = _FakeProvider(_VALID_JSON)
        with caplog.at_level(logging.INFO, logger=_RECORD_LOGGER):
            result = asyncio.run(_observe(_match(0.95), provider))
        assert result is None  # 비노출 — 호출자가 신호 받을 변수 없음
        assert provider.calls == 1  # L3까지 실제로 갔다(생성 성공률 관측이 목적)
        records = _records(caplog)
        assert len(records) == 1
        obs = MisconceptionVisualizationShadowObservation.model_validate_json(records[0])
        assert obs.misconception_id == "distribution-over-power"
        assert obs.domain == "대수"
        assert obs.pattern == "counterexample"  # confidence>0.8 → select_intervention 패턴1
        assert obs.level == "고1"
        assert obs.success is True
        assert obs.visualization_type == "interactive_graph_2d"
        assert obs.error_type is None

    def test_mid_confidence_reverse_reasoning_success(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        provider = _FakeProvider(_VALID_JSON)
        with caplog.at_level(logging.INFO, logger=_RECORD_LOGGER):
            asyncio.run(_observe(_match(0.6), provider))
        obs = MisconceptionVisualizationShadowObservation.model_validate_json(_records(caplog)[0])
        assert obs.pattern == "reverse_reasoning"  # 0.5≤c≤0.8 → 패턴4
        assert obs.success is True


# ──────────────────────────────────────────────────────────────────────────
# ② 진단 보류(confidence<0.5) → 실패 아님(L3 미호출·error_type None)
# ──────────────────────────────────────────────────────────────────────────
class TestHeldDiagnosisSkipsWithoutError:
    def test_low_confidence_no_l3_call_success_false(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        provider = _FakeProvider(_VALID_JSON)
        with caplog.at_level(logging.INFO, logger=_RECORD_LOGGER):
            result = asyncio.run(_observe(_match(0.3), provider))
        assert result is None
        assert provider.calls == 0  # 임계 일관 — visualize_misconception 내부 게이트가 L3 차단
        obs = MisconceptionVisualizationShadowObservation.model_validate_json(_records(caplog)[0])
        assert obs.success is False
        assert obs.error_type is None  # 실패가 아니라 애초에 대상이 아니었다는 뜻
        assert obs.pattern == "unknown"  # select_intervention도 None(match 자체 임계 미만)


# ──────────────────────────────────────────────────────────────────────────
# ③ L3 검증 실패 — 예외 타입명 기록(침묵 실패 금지) + 레코드는 남는다
# ──────────────────────────────────────────────────────────────────────────
class TestGenerationFailureRecordsErrorType:
    def test_invalid_l3_output_records_error_type(self, caplog: pytest.LogCaptureFixture) -> None:
        provider = _FakeProvider("죄송합니다, 만들 수 없습니다.")
        with caplog.at_level(logging.INFO, logger=_RECORD_LOGGER):
            result = asyncio.run(_observe(_match(0.95), provider))
        assert result is None  # never-break — 예외 전파 0
        obs = MisconceptionVisualizationShadowObservation.model_validate_json(_records(caplog)[0])
        assert obs.success is False
        assert obs.error_type == "InvalidVisualizationSpecError"
        assert obs.visualization_type is None
        assert obs.pattern == "counterexample"  # match 자체는 확정 진단(패턴 라벨은 유지)

    def test_provider_exception_records_error_type(self, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level(logging.INFO, logger=_RECORD_LOGGER):
            result = asyncio.run(_observe(_match(0.95), _BoomProvider()))
        assert result is None
        obs = MisconceptionVisualizationShadowObservation.model_validate_json(_records(caplog)[0])
        assert obs.success is False
        assert obs.error_type == "RuntimeError"


# ──────────────────────────────────────────────────────────────────────────
# ④ 프라이버시 — 학생 원문·spec·caption 미저장
# ──────────────────────────────────────────────────────────────────────────
class TestPrivacyNoContentNoStudentText:
    def test_record_omits_spec_and_caption(self, caplog: pytest.LogCaptureFixture) -> None:
        provider = _FakeProvider(_VALID_JSON)
        with caplog.at_level(logging.INFO, logger=_RECORD_LOGGER):
            asyncio.run(_observe(_match(0.95), provider))
        raw = _records(caplog)[0]
        parsed = json.loads(raw)
        assert "spec" not in parsed
        assert "caption" not in parsed
        assert "area" not in raw  # 생성된 spec 내용 미포함
        assert "넓이 모델" not in raw  # 생성된 caption 내용 미포함

    def test_model_forbids_extra_fields(self) -> None:
        with pytest.raises(Exception):  # noqa: B017,PT011 — pydantic ValidationError
            MisconceptionVisualizationShadowObservation(
                misconception_id="x",
                domain="대수",
                pattern="counterexample",
                level="고1",
                success=True,
                spec={"model": "area"},  # type: ignore[call-arg]
            )
