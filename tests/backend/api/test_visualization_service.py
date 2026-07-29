"""L5 시각화 오케스트레이션 서비스 단위테스트 — 진단→Concept 로드→L3 위임. 슬라이스 95.

라이브 DB·LLM 없음: 가짜 session(.get) + 가짜 provider + 인메모리 스텁으로 L5 배선을 검증한다.
설계 정본: docs/architecture/00_overview.md(7계층·L5 오케스트레이션)·05 §5.2(선언적 시각화).
"""

from __future__ import annotations

import uuid

import pytest
from whymath_backend.api.visualization import visualize_for_concept_diagnosis
from whymath_backend.l2.concept_diagnosis import ConceptDiagnosis
from whymath_backend.l3.interfaces import InMemoryCache, RecordingTraceSink
from whymath_backend.l3.models import GenerationResult, RoutingDecision
from whymath_backend.schema.concept import Concept
from whymath_backend.schema.enums import (
    ConceptLevel,
    Visualizability,
    VisualizationStyle,
    VisualizationType,
)
from whymath_backend.schema.visualization import Visualization


class _FakeProvider:
    """가짜 LLMProvider — 정해진 텍스트 반환 + 호출 기록(LLMProvider 구조 충족)."""

    def __init__(self, text: str) -> None:
        self._text = text
        self.calls: list[tuple[str, str, RoutingDecision]] = []

    async def generate(
        self, prompt: str, system: str, decision: RoutingDecision
    ) -> GenerationResult:
        self.calls.append((prompt, system, decision))
        return GenerationResult(self._text)


class _FakeConceptOrm:
    """가짜 Concept ORM — to_schema()만 제공(session.get 반환값 모사)."""

    def __init__(self, schema: Concept) -> None:
        self._schema = schema
        self.code = schema.code

    def to_schema(self) -> Concept:
        return self._schema


class _FakeVizRow:
    """가짜 ConceptVisualization Overlay 행 — visualizability만 보유."""

    def __init__(self, visualizability: Visualizability) -> None:
        self.visualizability = visualizability


class _FakeStyleRow:
    """가짜 ConceptVisualStyle Overlay 행 — recommended_styles만 보유(ARCH-14 ③ 양식 이관)."""

    def __init__(self, styles: list[VisualizationStyle]) -> None:
        self.recommended_styles = styles


class _FakeSession:
    """가짜 AsyncSession — get()을 모델별로 디스패치.

    `Concept` 조회는 concept ORM(또는 None), `ConceptVisualization` 조회는 code→4분류 맵에서
    행(또는 None·미태깅)을 돌려준다(시각화 계층 Overlay 조회·노드 비내장). `ConceptVisualStyle`
    (권장 양식 Overlay·ARCH-14 ③)은 concept 스키마의 declared 양식을 미러한다 — API seam이
    Overlay 값을 스키마 필드에 재주입하므로 원 값이 복원된다(미태깅이면 빈 행→[]).
    """

    def __init__(self, orm: object, *, viz: dict[str, Visualizability] | None = None) -> None:
        self._orm = orm
        self._viz = viz or {}
        self._styles: list[VisualizationStyle] = (
            list(orm.to_schema().recommended_visual_styles)  # type: ignore[attr-defined]
            if orm is not None
            else []
        )

    async def get(self, model: object, key: object) -> object:
        name = getattr(model, "__name__", "")
        if name == "ConceptVisualStyle":
            return _FakeStyleRow(self._styles) if self._styles else None
        if name == "ConceptVisualization":
            value = self._viz.get(str(key))
            return _FakeVizRow(value) if value is not None else None
        return self._orm


_VALID_JSON = (
    '{"type": "interactive_graph_2d", "spec": {"model": "circle"}, '
    '"caption": "단위원", "interactive": true}'
)


def _concept() -> Concept:
    """삼각함수 개념 — 권장 양식 단위원(슬88)."""
    return Concept(
        code="TRIG-PERIOD",
        name_ko="삼각함수의 주기성",
        level=ConceptLevel.세부개념,
        recommended_visual_styles=[VisualizationStyle.단위원],
    )


def _diagnosis(bkt: float | None = 0.3) -> ConceptDiagnosis:
    """주어진 BKT 숙달의 개념 진단."""
    return ConceptDiagnosis(
        concept_id=uuid.uuid4(),
        response_count=4,
        agreement="insufficient",
        bkt_mastery=bkt,
    )


@pytest.mark.asyncio
async def test_loads_concept_and_generates_with_style_hint() -> None:
    """진단 → Concept 로드 → 시각화 생성; 프롬프트에 name_ko + recommended_visual_styles(슬88)."""
    provider = _FakeProvider(_VALID_JSON)
    session = _FakeSession(_FakeConceptOrm(_concept()))
    v = await visualize_for_concept_diagnosis(
        _diagnosis(0.3),
        session,  # type: ignore[arg-type]
        provider=provider,
        cache=InMemoryCache(),
        trace=RecordingTraceSink(),
    )
    assert isinstance(v, Visualization)
    assert v.type == VisualizationType.interactive_graph_2d
    prompt = provider.calls[0][0]
    assert "삼각함수의 주기성" in prompt  # name_ko가 개념으로
    assert "단위원" in prompt  # recommended_visual_styles(슬88) 힌트


@pytest.mark.asyncio
async def test_concept_not_found_returns_none() -> None:
    """concept_id가 DB에 없으면(session.get→None) None·L3 미호출."""
    provider = _FakeProvider(_VALID_JSON)
    session = _FakeSession(None)
    v = await visualize_for_concept_diagnosis(
        _diagnosis(0.3),
        session,  # type: ignore[arg-type]
        provider=provider,
        cache=InMemoryCache(),
        trace=RecordingTraceSink(),
    )
    assert v is None
    assert provider.calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize("v", [Visualizability.추상])
async def test_abstract_or_impossible_concept_returns_none(v: Visualizability) -> None:
    """Overlay 4분류가 추상이면 억지 리터럴 시각화 대신 None·L3 미호출(Part 5 게이트·05b)."""
    concept = Concept(
        code="LOGIC-FORMAL",
        name_ko="극한의 엄밀한 정의",
        level=ConceptLevel.세부개념,
        recommended_visual_styles=[VisualizationStyle.함수그래프],
    )
    provider = _FakeProvider(_VALID_JSON)
    # 시각화 계층 Overlay에 code→4분류 태깅(노드 비내장).
    session = _FakeSession(_FakeConceptOrm(concept), viz={"LOGIC-FORMAL": v})
    result = await visualize_for_concept_diagnosis(
        _diagnosis(0.3),
        session,  # type: ignore[arg-type]
        provider=provider,
        cache=InMemoryCache(),
        trace=RecordingTraceSink(),
    )
    assert result is None
    assert provider.calls == []  # 억지 그림을 위해 LLM을 부르지 않는다


@pytest.mark.asyncio
async def test_none_mastery_defaults_level_chobo() -> None:
    """bkt·irt 숙달 모두 None → level 기본 '초보'로 생성 진행."""
    provider = _FakeProvider(_VALID_JSON)
    session = _FakeSession(_FakeConceptOrm(_concept()))
    v = await visualize_for_concept_diagnosis(
        _diagnosis(None),
        session,  # type: ignore[arg-type]
        provider=provider,
        cache=InMemoryCache(),
        trace=RecordingTraceSink(),
    )
    assert isinstance(v, Visualization)
    assert "초보" in provider.calls[0][0]  # level='초보'가 프롬프트에 반영
