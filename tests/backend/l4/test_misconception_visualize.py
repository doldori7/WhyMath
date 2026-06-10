"""L4 오개념 → 맞춤 시각화 배선 단위테스트 — 게이트(임계)·L3 위임·검증 전파. 슬라이스 93.

라이브 LLM 없음: 가짜 provider(정해진 텍스트 반환) + 인메모리 스텁으로 L4→L3 배선을
검증한다. 설계 정본: docs/architecture/04_pedagogy_engine.md(오개념 진단·개입)·
05_interaction.md §5.2(선언적 시각화).
"""

from __future__ import annotations

import pytest

from whymath_backend.l3.interfaces import InMemoryCache, RecordingTraceSink
from whymath_backend.l3.models import RoutingDecision
from whymath_backend.l3.visualization import InvalidVisualizationSpecError
from whymath_backend.l4.misconception.models import Misconception, MisconceptionMatch
from whymath_backend.l4.misconception.visualize import visualize_misconception
from whymath_backend.schema.enums import VisualizationType
from whymath_backend.schema.visualization import Visualization


class _FakeProvider:
    """가짜 LLMProvider — 정해진 텍스트 반환 + 호출 기록(LLMProvider 구조 충족)."""

    def __init__(self, text: str) -> None:
        self._text = text
        self.calls: list[tuple[str, str, RoutingDecision]] = []

    async def generate(
        self, prompt: str, system: str, decision: RoutingDecision
    ) -> str:
        self.calls.append((prompt, system, decision))
        return self._text


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


def _match(confidence: float) -> MisconceptionMatch:
    """주어진 신뢰도의 진단 결과(_M 고정)."""
    return MisconceptionMatch(
        misconception=_M, confidence=confidence, matched_signals=()
    )


@pytest.mark.asyncio
async def test_confident_match_generates_visualization() -> None:
    """확정 진단(confidence>0.8) → L3 위임으로 맞춤 시각화 생성·프롬프트에 오개념 반영."""
    provider = _FakeProvider(_VALID_JSON)
    v = await visualize_misconception(
        _match(0.95),
        "고1",
        provider=provider,
        cache=InMemoryCache(),
        trace=RecordingTraceSink(),
    )
    assert isinstance(v, Visualization)
    assert v.type == VisualizationType.interactive_graph_2d
    # L3로 위임됐고, 사용자 프롬프트에 학생의 잘못된 가정이 들어갔다(맞춤).
    assert provider.calls
    assert "(a+b)² = a²+b²" in provider.calls[0][0]


@pytest.mark.asyncio
async def test_mid_confidence_match_also_generates() -> None:
    """중간 신뢰도(0.5≤c≤0.8·거꾸로 사고 확정)도 보완 시각화 생성."""
    provider = _FakeProvider(_VALID_JSON)
    v = await visualize_misconception(
        _match(0.6),
        "고1",
        provider=provider,
        cache=InMemoryCache(),
        trace=RecordingTraceSink(),
    )
    assert isinstance(v, Visualization)
    assert provider.calls


@pytest.mark.asyncio
async def test_held_diagnosis_returns_none_without_calling_l3() -> None:
    """진단 보류(confidence<0.5) → None·L3 미호출(과개입 회피·임계 일관)."""
    provider = _FakeProvider(_VALID_JSON)
    v = await visualize_misconception(
        _match(0.3),
        "고1",
        provider=provider,
        cache=InMemoryCache(),
        trace=RecordingTraceSink(),
    )
    assert v is None
    assert provider.calls == []


@pytest.mark.asyncio
async def test_invalid_l3_output_propagates() -> None:
    """확정 진단인데 L3 출력이 명세가 아니면 검증 게이트 예외가 전파(삼키지 않음)."""
    provider = _FakeProvider("죄송합니다, 만들 수 없습니다.")
    with pytest.raises(InvalidVisualizationSpecError):
        await visualize_misconception(
            _match(0.95),
            "고1",
            provider=provider,
            cache=InMemoryCache(),
            trace=RecordingTraceSink(),
        )
