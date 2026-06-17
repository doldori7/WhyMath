"""L3 시각화 명세 생성기 단위테스트 — 파싱·검증 게이트 + 라우터 경유 생성. 슬라이스 92.

라이브 LLM 없음: 가짜 provider(정해진 텍스트 반환) + 인메모리 스텁으로 라우터 경유 생성과
검증 게이트를 검증한다(test_pipeline.RecordingProvider·InMemoryCache 패턴 답습).

설계 정본: docs/architecture/05_interaction.md §5.2(선언적 시각화)·03_content_generation.md
(L3 인터페이스 정합). 검증 게이트는 CLAUDE.md "LLM 응답을 검증 없이 제공 금지"의 구현.
"""

from __future__ import annotations

import pytest

from whymath_backend.l3.interfaces import InMemoryCache, RecordingTraceSink
from whymath_backend.l3.models import RoutingDecision, RoutingRequest
from whymath_backend.l3.visualization import (
    InvalidVisualizationSpecError,
    generate_visualization_spec,
    parse_visualization_spec,
    visualization_spec_for_concept,
)
from whymath_backend.schema.concept import Concept
from whymath_backend.schema.enums import (
    ConceptLevel,
    VisualizationStyle,
    VisualizationType,
)
from whymath_backend.schema.visualization import Visualization


class _FakeProvider:
    """가짜 LLMProvider — 호출 기록 + 정해진 텍스트 반환(LLMProvider 구조 충족)."""

    def __init__(self, text: str) -> None:
        self._text = text
        self.calls: list[tuple[str, str, RoutingDecision]] = []

    async def generate(self, prompt: str, system: str, decision: RoutingDecision) -> str:
        self.calls.append((prompt, system, decision))
        return self._text


_VALID_JSON = (
    '{"type": "interactive_graph_2d", "spec": {"function": "x**2", "domain": [-3, 3]}, '
    '"caption": "포물선", "interactive": true}'
)


# ──────────────────────────────────────────────────────────────────────
# parse_visualization_spec — 검증 게이트(라이브 LLM 불필요)
# ──────────────────────────────────────────────────────────────────────
class TestParseVisualizationSpec:
    def test_plain_json(self) -> None:
        """순수 JSON 객체 → Visualization."""
        v = parse_visualization_spec(_VALID_JSON)
        assert isinstance(v, Visualization)
        assert v.type == VisualizationType.interactive_graph_2d
        assert v.spec["function"] == "x**2"

    def test_markdown_fenced(self) -> None:
        """```json ... ``` 코드펜스로 감싼 출력도 추출."""
        text = f"다음은 명세입니다:\n```json\n{_VALID_JSON}\n```\n끝."
        v = parse_visualization_spec(text)
        assert v.caption == "포물선"

    def test_prose_wrapped(self) -> None:
        """산문에 둘러싸인 JSON도 첫 '{'~마지막 '}'로 추출."""
        text = f"명세: {_VALID_JSON} 이상입니다."
        v = parse_visualization_spec(text)
        assert v.type == VisualizationType.interactive_graph_2d

    def test_invalid_json_rejected(self) -> None:
        """깨진 JSON → InvalidVisualizationSpecError."""
        with pytest.raises(InvalidVisualizationSpecError):
            parse_visualization_spec('{"type": "interactive_graph_2d", ')

    def test_no_json_object_rejected(self) -> None:
        """JSON 객체가 없으면(중괄호 없음) 거부."""
        with pytest.raises(InvalidVisualizationSpecError):
            parse_visualization_spec("설명만 있고 JSON 객체가 없습니다")

    def test_array_rejected(self) -> None:
        """최상위 배열(객체 아님)은 추출 단계에서 거부."""
        with pytest.raises(InvalidVisualizationSpecError):
            parse_visualization_spec("[1, 2, 3]")

    def test_schema_invariant_violation_rejected(self) -> None:
        """슬90 불변식: animation_prerendered + interactive=true → 거부."""
        bad = '{"type": "animation_prerendered", "interactive": true}'
        with pytest.raises(InvalidVisualizationSpecError):
            parse_visualization_spec(bad)

    def test_missing_type_rejected(self) -> None:
        """필수 필드 type 누락 → 거부."""
        with pytest.raises(InvalidVisualizationSpecError):
            parse_visualization_spec('{"spec": {}, "caption": "x"}')

    def test_unknown_field_rejected(self) -> None:
        """extra='forbid' — 정의되지 않은 필드 포함 시 거부."""
        bad = '{"type": "interactive_graph_2d", "bogus": 1}'
        with pytest.raises(InvalidVisualizationSpecError):
            parse_visualization_spec(bad)

    def test_typed_spec_violation_rejected(self) -> None:
        """S1 typed spec 게이트 — graph_2d function이 문자열 아님(123) → 거부."""
        bad = '{"type": "interactive_graph_2d", "spec": {"function": 123}}'
        with pytest.raises(InvalidVisualizationSpecError):
            parse_visualization_spec(bad)


# ──────────────────────────────────────────────────────────────────────
# generate_visualization_spec — 라우터 경유(pipeline.generate) + 게이트
# ──────────────────────────────────────────────────────────────────────
def _req() -> RoutingRequest:
    """LOCAL·동기로 라우팅되는 평이한 생성 요청."""
    return RoutingRequest(
        task_type="generate",
        difficulty="medium",
        requires_reasoning=True,
        student_subscription="free",
    )


@pytest.mark.asyncio
async def test_generate_returns_validated_visualization() -> None:
    """provider가 유효 JSON을 내면 검증된 Visualization 반환 + provider가 라우터 경유 호출."""
    provider = _FakeProvider(_VALID_JSON)
    v = await generate_visualization_spec(
        "이차함수의 그래프",
        "고1",
        _req(),
        provider=provider,
        cache=InMemoryCache(),
        trace=RecordingTraceSink(),
    )
    assert isinstance(v, Visualization)
    assert v.type == VisualizationType.interactive_graph_2d
    # 라우터 경유로 provider가 호출됐고, 사용자 프롬프트에 개념이 들어갔다.
    assert provider.calls
    assert "이차함수의 그래프" in provider.calls[0][0]


@pytest.mark.asyncio
async def test_generate_rejects_invalid_output() -> None:
    """provider가 명세가 아닌 산문을 내면 검증 게이트가 거부(검증 안 된 명세 비통과)."""
    provider = _FakeProvider("죄송합니다, 명세를 만들 수 없습니다.")
    with pytest.raises(InvalidVisualizationSpecError):
        await generate_visualization_spec(
            "원의 방정식",
            "고2",
            _req(),
            provider=provider,
            cache=InMemoryCache(),
            trace=RecordingTraceSink(),
        )


# ──────────────────────────────────────────────────────────────────────
# recommended_styles 힌트 주입 + Concept 래퍼 (슬88↔슬92 연결)
# ──────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_recommended_styles_injected_into_prompt() -> None:
    """recommended_styles → 사용자 프롬프트에 '권장 시각화 양식' 힌트로 주입."""
    provider = _FakeProvider(_VALID_JSON)
    await generate_visualization_spec(
        "삼각함수의 주기성",
        "고2",
        _req(),
        provider=provider,
        cache=InMemoryCache(),
        trace=RecordingTraceSink(),
        recommended_styles=["단위원", "함수그래프"],
    )
    prompt = provider.calls[0][0]
    assert "권장 시각화 양식" in prompt
    assert "단위원" in prompt


@pytest.mark.asyncio
async def test_no_styles_no_hint_line() -> None:
    """recommended_styles 미지정 → 힌트 줄 없음(기존 동작 보존)."""
    provider = _FakeProvider(_VALID_JSON)
    await generate_visualization_spec(
        "원의 방정식",
        "고2",
        _req(),
        provider=provider,
        cache=InMemoryCache(),
        trace=RecordingTraceSink(),
    )
    assert "권장 시각화 양식" not in provider.calls[0][0]


@pytest.mark.asyncio
async def test_for_concept_injects_recommended_visual_styles() -> None:
    """visualization_spec_for_concept → Concept.recommended_visual_styles(슬88)를 자동 주입."""
    concept = Concept(
        code="TRIG-PERIOD",
        name_ko="삼각함수의 주기성",
        level=ConceptLevel.세부개념,
        recommended_visual_styles=[
            VisualizationStyle.단위원,
            VisualizationStyle.함수그래프,
        ],
    )
    provider = _FakeProvider(_VALID_JSON)
    v = await visualization_spec_for_concept(
        concept,
        "고2",
        _req(),
        provider=provider,
        cache=InMemoryCache(),
        trace=RecordingTraceSink(),
    )
    assert isinstance(v, Visualization)
    prompt = provider.calls[0][0]
    assert "삼각함수의 주기성" in prompt  # name_ko가 개념으로
    assert "단위원" in prompt  # recommended_visual_styles 힌트


@pytest.mark.asyncio
async def test_for_concept_empty_styles_no_hint() -> None:
    """recommended_visual_styles 빈 Concept → 힌트 줄 없음(no-hint 분기)."""
    concept = Concept(
        code="CIRC-EQ",
        name_ko="원의 방정식",
        level=ConceptLevel.세부개념,
    )
    provider = _FakeProvider(_VALID_JSON)
    await visualization_spec_for_concept(
        concept,
        "고2",
        _req(),
        provider=provider,
        cache=InMemoryCache(),
        trace=RecordingTraceSink(),
    )
    assert "권장 시각화 양식" not in provider.calls[0][0]
