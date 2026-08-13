"""L5 학습 장면 오케스트레이션 서비스 단위테스트 — 진단→Concept 로드→L4 위임. S5a.

라이브 DB·LLM 없음: 가짜 session(.get) + 가짜 provider + 인메모리 스텁으로 L5 배선을 검증한다
(test_visualization_service 미러). 설계 정본: 00_overview(7계층·L5 오케스트레이션)·05a §5.
"""

from __future__ import annotations

import uuid

import pytest

from whymath_backend.api import scene as scene_mod
from whymath_backend.api.scene import scene_for_concept_diagnosis
from whymath_backend.l2.concept_diagnosis import ConceptDiagnosis
from whymath_backend.l3.interfaces import InMemoryCache, RecordingTraceSink
from whymath_backend.l3.models import GenerationResult, RoutingDecision
from whymath_backend.l3.visualization import InvalidVisualizationSpecError
from whymath_backend.l4.learning_scene import (
    LearningScene,
    MisconceptionProbeElement,
    SkillFocusElement,
    SocraticPromptElement,
    StepPanelElement,
    TutoringPromptElement,
    VisualizationElement,
)
from whymath_backend.l4.misconception.catalog import CATALOG_BY_ID
from whymath_backend.l4.misconception.hypothesis import MisconceptionHypothesis
from whymath_backend.l4.misconception.models import InterventionPattern
from whymath_backend.schema.concept import Concept
from whymath_backend.schema.enums import (
    BehaviorArea,
    CognitiveType,
    ConceptLevel,
    VisualizationStyle,
)

# 정본 오개념 카탈로그의 실 id(프로브 생성 검증용·동적 취득).
_VALID_MC_ID = next(iter(CATALOG_BY_ID))
_VALID_MC_ID2 = list(CATALOG_BY_ID)[1]


async def _no_evidence(session: object, user_id: uuid.UUID) -> dict[str, float]:
    """증거 없음 스텁 — net_support_by_misconception 대체(아무 가설도 억제 안 함)."""
    return {}


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


class _FakeStyleRow:
    """가짜 ConceptVisualStyle Overlay 행 — recommended_styles만 보유(ARCH-14 ③ 양식 이관)."""

    def __init__(self, styles: list[VisualizationStyle]) -> None:
        self.recommended_styles = styles


class _RowResult:
    """execute 결과 범용 모사 — `.all()`(행 목록)·`.scalars().all()/first()` 표면 동시 지원.

    앵커 후보 조회(`list_recent_attempted_problem_ids`)는 `.all()`을, 경로 단건 조회
    (`find_solution_path_id`)는 `.scalars().first()`를 부른다. 스칼라 select의 행은 값 그 자체로
    넣는다(예: `["sp-1"]`).
    """

    def __init__(self, rows: list[object]) -> None:
        self._rows = rows

    def all(self) -> list[object]:
        return list(self._rows)

    def scalars(self) -> _RowResult:
        return self

    def first(self) -> object | None:
        return self._rows[0] if self._rows else None


class _FakeSession:
    """가짜 AsyncSession — get()을 모델별로 디스패치.

    `Concept` 조회는 concept ORM(또는 None). `ConceptVisualization`(시각화 Overlay)·`AtomNode`
    (행동영역 조인 백킹·S0-2가 원자 축으로 이전) 조회는 None — 이 테스트들은 시각화 4분류·행동영역을
    다루지 않으므로 기존 동작(중립 폴백)을 유지한다. `ConceptVisualStyle`(권장 양식 Overlay·
    ARCH-14 ③)은 concept 스키마의 declared 양식을 미러한다 — API seam이 Overlay 값을 스키마 필드에
    재주입하므로 원 값이 복원돼 결정론 골격(시각화 요소 등)이 기존과 동일하게 생성된다.
    `execute`는 SOL-02 앵커 후보 조회(student_id 있는 호출에서 1회)의 최소 표면 — 기본값은
    빈 결과(시도 이력 없음). 실재 경로 시나리오는 `_StepPanelSession`(큐 모사)이 담당한다.
    """

    def __init__(self, orm: object) -> None:
        self._orm = orm
        self.execute_calls = 0
        self._styles: list[VisualizationStyle] = (
            list(orm.to_schema().recommended_visual_styles)  # type: ignore[attr-defined]
            if orm is not None
            else []
        )

    async def get(self, model: object, key: object) -> object:
        name = getattr(model, "__name__", "")
        if name == "ConceptVisualStyle":
            return _FakeStyleRow(self._styles) if self._styles else None
        if name in {"ConceptVisualization", "AtomNode"}:
            return None
        return self._orm

    async def execute(self, _stmt: object) -> _RowResult:
        """앵커 후보 조회의 기본 응답 — 빈 결과(후보 없음 → 경로 조회·방출 0)."""
        self.execute_calls += 1
        return _RowResult([])


_VALID_JSON = (
    '{"type": "interactive_graph_2d", "spec": {"function": "a*x**2", '
    '"parameters": [{"name": "a"}]}, "interactive": true}'
)


def _concept() -> Concept:
    """이차함수 개념 — 권장 양식 함수그래프 + 인지유형 정의(시각화+소크라테스 골격)."""
    return Concept(
        code="ALG-QUAD-DEF",
        name_ko="이차함수의 그래프",
        level=ConceptLevel.세부개념,
        recommended_visual_styles=[VisualizationStyle.함수그래프],
        cognitive_type=[CognitiveType.DEFINITION],
    )


def _diagnosis(bkt: float | None = 0.3, theta: float | None = 0.5) -> ConceptDiagnosis:
    """주어진 BKT 숙달·θ의 개념 진단."""
    return ConceptDiagnosis(
        concept_id=uuid.uuid4(),
        response_count=4,
        agreement="insufficient",
        bkt_mastery=bkt,
        irt_theta=theta,
    )


@pytest.mark.asyncio
async def test_loads_concept_and_generates_scene() -> None:
    """진단 → Concept 로드 → 장면(시각화+소크라테스)·concept_id=code·name_ko 프롬프트."""
    provider = _FakeProvider(_VALID_JSON)
    session = _FakeSession(_FakeConceptOrm(_concept()))
    scene = await scene_for_concept_diagnosis(
        _diagnosis(0.3),
        session,  # type: ignore[arg-type]
        provider=provider,
        cache=InMemoryCache(),
        trace=RecordingTraceSink(),
    )
    assert isinstance(scene, LearningScene)
    assert scene.concept_id == "ALG-QUAD-DEF"
    assert any(isinstance(el, VisualizationElement) for el in scene.elements)
    assert any(isinstance(el, SocraticPromptElement) for el in scene.elements)
    assert "이차함수의 그래프" in provider.calls[0][0]


@pytest.mark.asyncio
async def test_concept_not_found_returns_none() -> None:
    """concept_id가 DB에 없으면(session.get→None) None·L3 미호출."""
    provider = _FakeProvider(_VALID_JSON)
    session = _FakeSession(None)
    scene = await scene_for_concept_diagnosis(
        _diagnosis(0.3),
        session,  # type: ignore[arg-type]
        provider=provider,
        cache=InMemoryCache(),
        trace=RecordingTraceSink(),
    )
    assert scene is None
    assert provider.calls == []


@pytest.mark.asyncio
async def test_learner_context_snapshot_carried() -> None:
    """learner_context에 진단 스냅샷(mastery·theta) 운반
    ·active_hypothesis_ids 빈 목록(프로브 미생성)."""
    provider = _FakeProvider(_VALID_JSON)
    session = _FakeSession(_FakeConceptOrm(_concept()))
    scene = await scene_for_concept_diagnosis(
        _diagnosis(0.3, 0.5),
        session,  # type: ignore[arg-type]
        provider=provider,
        cache=InMemoryCache(),
        trace=RecordingTraceSink(),
    )
    assert scene is not None
    assert scene.learner_context is not None
    assert scene.learner_context.mastery_level == 0.3
    assert scene.learner_context.theta == 0.5
    assert scene.learner_context.active_hypothesis_ids == []


@pytest.mark.asyncio
async def test_mastery_threads_to_tutoring_prompt() -> None:
    """진단 BKT 숙달이 LTHC 튜터링 프롬프트로 장면에 반영된다(S5l·학습자모델 축·끝단 배선).

    bkt=0.3(초보)·개념 인지유형 DEFINITION → 주 Polya UNDERSTAND → 진입점+비계 역할 방출.
    """
    provider = _FakeProvider(_VALID_JSON)
    session = _FakeSession(_FakeConceptOrm(_concept()))
    scene = await scene_for_concept_diagnosis(
        _diagnosis(0.3),
        session,  # type: ignore[arg-type]
        provider=provider,
        cache=InMemoryCache(),
        trace=RecordingTraceSink(),
    )
    assert scene is not None
    tutoring = [el for el in scene.elements if isinstance(el, TutoringPromptElement)]
    assert tutoring
    assert {t.role for t in tutoring} == {"entry", "scaffold"}  # 초보 → 진입+비계


@pytest.mark.asyncio
async def test_none_mastery_no_tutoring_prompt() -> None:
    """bkt·irt 숙달 모두 None(신호 없음) → 튜터링 프롬프트 미방출(비계 날조 금지·낙인 회피)."""
    provider = _FakeProvider(_VALID_JSON)
    session = _FakeSession(_FakeConceptOrm(_concept()))
    scene = await scene_for_concept_diagnosis(
        _diagnosis(None, None),
        session,  # type: ignore[arg-type]
        provider=provider,
        cache=InMemoryCache(),
        trace=RecordingTraceSink(),
    )
    assert scene is not None
    assert not any(isinstance(el, TutoringPromptElement) for el in scene.elements)


@pytest.mark.asyncio
async def test_none_mastery_defaults_level_chobo() -> None:
    """bkt·irt 숙달 모두 None → level 기본 '초보'가 프롬프트에 반영."""
    provider = _FakeProvider(_VALID_JSON)
    session = _FakeSession(_FakeConceptOrm(_concept()))
    scene = await scene_for_concept_diagnosis(
        _diagnosis(None, None),
        session,  # type: ignore[arg-type]
        provider=provider,
        cache=InMemoryCache(),
        trace=RecordingTraceSink(),
    )
    assert isinstance(scene, LearningScene)
    assert "초보" in provider.calls[0][0]


@pytest.mark.asyncio
async def test_active_hypotheses_become_probes(monkeypatch: pytest.MonkeyPatch) -> None:
    """student_id 제공 → WH-1 가설 store 조회 → 활성 가설이 적응형 오개념 프로브로 생성."""

    async def _fake_active(session: object, user_id: uuid.UUID) -> list[MisconceptionHypothesis]:
        return [
            MisconceptionHypothesis(
                misconception_id=_VALID_MC_ID,
                confidence=0.8,
                turns_since_evidence=0,
                evidence_count=2,
            )
        ]

    monkeypatch.setattr(scene_mod, "get_active_hypotheses", _fake_active)
    monkeypatch.setattr(scene_mod, "net_support_by_misconception", _no_evidence)
    provider = _FakeProvider(_VALID_JSON)
    session = _FakeSession(_FakeConceptOrm(_concept()))
    scene = await scene_for_concept_diagnosis(
        _diagnosis(0.3),
        session,  # type: ignore[arg-type]
        provider=provider,
        cache=InMemoryCache(),
        trace=RecordingTraceSink(),
        student_id=uuid.uuid4(),
    )
    assert scene is not None
    assert scene.learner_context is not None
    assert scene.learner_context.active_hypothesis_ids == [_VALID_MC_ID]
    probes = [el for el in scene.elements if isinstance(el, MisconceptionProbeElement)]
    assert len(probes) == 1
    assert probes[0].misconception_id == _VALID_MC_ID


@pytest.mark.asyncio
async def test_probe_intervention_diversified_by_confidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """가설 신뢰도가 프로브 개입을 다양화한다(>0.8 반례·≥0.5 거꾸로·<0.5 보류) — 끝단 배선."""

    async def _fake_active(session: object, user_id: uuid.UUID) -> list[MisconceptionHypothesis]:
        return [
            MisconceptionHypothesis(
                misconception_id=_VALID_MC_ID,
                confidence=0.9,  # >0.8 → 반례
                turns_since_evidence=0,
                evidence_count=3,
            ),
            MisconceptionHypothesis(
                misconception_id=_VALID_MC_ID2,
                confidence=0.6,  # 0.5~0.8 → 거꾸로
                turns_since_evidence=1,
                evidence_count=1,
            ),
        ]

    monkeypatch.setattr(scene_mod, "get_active_hypotheses", _fake_active)
    monkeypatch.setattr(scene_mod, "net_support_by_misconception", _no_evidence)
    provider = _FakeProvider(_VALID_JSON)
    session = _FakeSession(_FakeConceptOrm(_concept()))
    scene = await scene_for_concept_diagnosis(
        _diagnosis(0.3),
        session,  # type: ignore[arg-type]
        provider=provider,
        cache=InMemoryCache(),
        trace=RecordingTraceSink(),
        student_id=uuid.uuid4(),
    )
    assert scene is not None
    probes = [el for el in scene.elements if isinstance(el, MisconceptionProbeElement)]
    by_id = {p.misconception_id: p.intervention for p in probes}
    assert by_id == {
        _VALID_MC_ID: InterventionPattern.COUNTEREXAMPLE,
        _VALID_MC_ID2: InterventionPattern.REVERSE_REASONING,
    }


@pytest.mark.asyncio
async def test_refuted_hypothesis_probe_suppressed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """evidence_links 순지지도<0(반박 우세)인 가설은 렌더 시점에 프로브에서 제외(RS2 낙인 회피)."""

    async def _fake_active(session: object, user_id: uuid.UUID) -> list[MisconceptionHypothesis]:
        return [
            MisconceptionHypothesis(
                misconception_id=_VALID_MC_ID,  # 증거 반박(net_support<0) → 제외
                confidence=0.9,
                turns_since_evidence=0,
                evidence_count=2,
            ),
            MisconceptionHypothesis(
                misconception_id=_VALID_MC_ID2,  # 증거 지지(net_support>0) → 유지
                confidence=0.9,
                turns_since_evidence=0,
                evidence_count=2,
            ),
        ]

    async def _net_support(session: object, user_id: uuid.UUID) -> dict[str, float]:
        return {_VALID_MC_ID: -1.5, _VALID_MC_ID2: 2.0}

    monkeypatch.setattr(scene_mod, "get_active_hypotheses", _fake_active)
    monkeypatch.setattr(scene_mod, "net_support_by_misconception", _net_support)
    provider = _FakeProvider(_VALID_JSON)
    session = _FakeSession(_FakeConceptOrm(_concept()))
    scene = await scene_for_concept_diagnosis(
        _diagnosis(0.3),
        session,  # type: ignore[arg-type]
        provider=provider,
        cache=InMemoryCache(),
        trace=RecordingTraceSink(),
        student_id=uuid.uuid4(),
    )
    assert scene is not None
    assert scene.learner_context is not None
    # 반박된 가설은 빠지고 지지된 가설만 남는다.
    assert scene.learner_context.active_hypothesis_ids == [_VALID_MC_ID2]
    probes = [el for el in scene.elements if isinstance(el, MisconceptionProbeElement)]
    assert [p.misconception_id for p in probes] == [_VALID_MC_ID2]


@pytest.mark.asyncio
async def test_no_student_id_skips_hypothesis_query(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """student_id 미제공 → 가설 store 조회 생략·active_hypothesis_ids 빈 목록(프로브 0)."""

    async def _boom(session: object, user_id: uuid.UUID) -> list[MisconceptionHypothesis]:
        raise AssertionError("student_id None이면 가설 store를 조회하면 안 된다")

    monkeypatch.setattr(scene_mod, "get_active_hypotheses", _boom)
    provider = _FakeProvider(_VALID_JSON)
    session = _FakeSession(_FakeConceptOrm(_concept()))
    scene = await scene_for_concept_diagnosis(
        _diagnosis(0.3),
        session,  # type: ignore[arg-type]
        provider=provider,
        cache=InMemoryCache(),
        trace=RecordingTraceSink(),
    )
    assert scene is not None
    assert scene.learner_context is not None
    assert scene.learner_context.active_hypothesis_ids == []
    assert not any(isinstance(el, MisconceptionProbeElement) for el in scene.elements)


@pytest.mark.asyncio
async def test_invalid_spec_propagates() -> None:
    """시각화 spec LLM 출력이 게이트를 통과 못 하면 예외 전파(검증 안 된 명세 비반환)."""
    provider = _FakeProvider("죄송합니다, 명세를 만들 수 없습니다.")
    session = _FakeSession(_FakeConceptOrm(_concept()))
    with pytest.raises(InvalidVisualizationSpecError):
        await scene_for_concept_diagnosis(
            _diagnosis(0.3),
            session,  # type: ignore[arg-type]
            provider=provider,
            cache=InMemoryCache(),
            trace=RecordingTraceSink(),
        )


# ── 행동영역 스레딩(concept→skill → skill_focus·S5k) ────────────────────────────
class _FakeResult:
    def __init__(self, values: list[BehaviorArea]) -> None:
        self._values = values

    def scalars(self) -> "_FakeResult":
        return self

    def all(self) -> list[BehaviorArea]:
        return self._values


class _FakeNode:
    def __init__(self, behavior_skills: list[str]) -> None:
        self.behavior_skills = behavior_skills


class _BehaviorSession:
    """concept ORM + AtomNode(behavior_skills) + execute(behavior_area) 디스패치 가짜 세션.

    behavior_skills는 S0-2가 원자 축(`atom_node`)으로 이전했고 resolve.py가
    `session.get(AtomNode, ...)`로 읽으므로, 행동영역 백킹 노드는 AtomNode 디스패치로 반환한다.
    """

    def __init__(self, orm: object, node: object, areas: list[BehaviorArea]) -> None:
        self._orm = orm
        self._node = node
        self._areas = areas
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
            return None
        if name == "AtomNode":
            return self._node
        return self._orm

    async def execute(self, stmt: object) -> _FakeResult:
        return _FakeResult(self._areas)


@pytest.mark.asyncio
async def test_behavior_area_threads_to_skill_focus() -> None:
    """concept→skill 매핑이 있으면 해소된 행동영역이 skill_focus로 장면에 반영된다(S5k)."""
    provider = _FakeProvider(_VALID_JSON)
    session = _BehaviorSession(
        _FakeConceptOrm(_concept()),
        _FakeNode(["skill.polynomial-arithmetic"]),
        [BehaviorArea.COMPUTE],
    )
    scene = await scene_for_concept_diagnosis(
        _diagnosis(0.3),
        session,  # type: ignore[arg-type]
        provider=provider,
        cache=InMemoryCache(),
        trace=RecordingTraceSink(),
    )
    assert scene is not None
    focus = [el for el in scene.elements if isinstance(el, SkillFocusElement)]
    assert len(focus) == 1
    assert focus[0].behavior_area == BehaviorArea.COMPUTE.value


@pytest.mark.asyncio
async def test_no_behavior_mapping_no_skill_focus() -> None:
    """concept→skill 매핑 부재(AtomNode None) → skill_focus 0(중립 폴백)."""
    provider = _FakeProvider(_VALID_JSON)
    session = _BehaviorSession(_FakeConceptOrm(_concept()), None, [])
    scene = await scene_for_concept_diagnosis(
        _diagnosis(0.3),
        session,  # type: ignore[arg-type]
        provider=provider,
        cache=InMemoryCache(),
        trace=RecordingTraceSink(),
    )
    assert scene is not None
    assert not any(isinstance(el, SkillFocusElement) for el in scene.elements)


# ── step_panel 앵커 배선(SOL-02 — 서비스 끝단) ──────────────────────────────
async def _no_hypotheses(session: object, user_id: uuid.UUID) -> list[object]:
    """가설 없음 스텁 — get_active_hypotheses 대체(프로브 축을 step_panel 축과 분리)."""
    return []


class _StepPanelSession(_FakeSession):
    """`_FakeSession` + execute 큐 — SOL-02 step_panel 앵커·경로 조회 순서 모사.

    쿼리 순서(서비스 코드 기준): ① 앵커 후보(`list_recent_attempted_problem_ids`) →
    ②~ 경로 단건(`find_solution_path_id`, 후보마다·실재하면 중단). 가설·증거 쿼리는
    monkeypatch로 분리돼 큐에 들어오지 않는다.
    """

    def __init__(self, orm: object, queue: list[list[object]]) -> None:
        super().__init__(orm)
        self._queue = list(queue)

    async def execute(self, _stmt: object) -> _RowResult:
        self.execute_calls += 1
        return _RowResult(self._queue.pop(0))


def _step_panels(scene: LearningScene) -> list[StepPanelElement]:
    return [el for el in scene.elements if isinstance(el, StepPanelElement)]


@pytest.mark.asyncio
async def test_step_panel_emitted_when_attempted_problem_has_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """시도 문항에 승격 경로 실재 → 장면에 step_panel이 실린다(③ 서비스 끝단 배선)."""
    monkeypatch.setattr(scene_mod, "get_active_hypotheses", _no_hypotheses)
    monkeypatch.setattr(scene_mod, "net_support_by_misconception", _no_evidence)
    provider = _FakeProvider(_VALID_JSON)
    session = _StepPanelSession(
        _FakeConceptOrm(_concept()),
        queue=[[(uuid.uuid4(), uuid.uuid4())], ["sp-anchor-1"]],  # 앵커 1건 → 경로 실재
    )
    scene = await scene_for_concept_diagnosis(
        _diagnosis(0.3),
        session,  # type: ignore[arg-type]
        provider=provider,
        cache=InMemoryCache(),
        trace=RecordingTraceSink(),
        student_id=uuid.uuid4(),
    )
    assert scene is not None
    panels = _step_panels(scene)
    assert len(panels) == 1
    assert panels[0].solution_path_id == "sp-anchor-1"
    # 답 미루기 스키마 강제 불변 — deferred 한 값만.
    assert panels[0].reveal_policy == "deferred"


@pytest.mark.asyncio
async def test_step_panel_scans_until_first_real_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """첫 후보 문항에 경로가 없으면 다음 후보를 훑는다 — 실재하는 첫 경로를 단다."""
    monkeypatch.setattr(scene_mod, "get_active_hypotheses", _no_hypotheses)
    monkeypatch.setattr(scene_mod, "net_support_by_misconception", _no_evidence)
    provider = _FakeProvider(_VALID_JSON)
    session = _StepPanelSession(
        _FakeConceptOrm(_concept()),
        # 앵커 2건 → 첫 문항 경로 없음(None) → 둘째 문항 경로 실재.
        queue=[
            [(uuid.uuid4(), uuid.uuid4()), (uuid.uuid4(), uuid.uuid4())],
            [],
            ["sp-second"],
        ],
    )
    scene = await scene_for_concept_diagnosis(
        _diagnosis(0.3),
        session,  # type: ignore[arg-type]
        provider=provider,
        cache=InMemoryCache(),
        trace=RecordingTraceSink(),
        student_id=uuid.uuid4(),
    )
    assert scene is not None
    panels = _step_panels(scene)
    assert len(panels) == 1
    assert panels[0].solution_path_id == "sp-second"
    assert session.execute_calls == 3  # 앵커 1 + 경로 2(첫 None→둘 실재에서 중단)


@pytest.mark.asyncio
async def test_no_step_panel_when_no_attempts(monkeypatch: pytest.MonkeyPatch) -> None:
    """시도 이력 0(앵커 후보 빈 목록) → 경로 조회 자체를 하지 않고 방출 0(빈 껍데기 금지)."""
    monkeypatch.setattr(scene_mod, "get_active_hypotheses", _no_hypotheses)
    monkeypatch.setattr(scene_mod, "net_support_by_misconception", _no_evidence)
    provider = _FakeProvider(_VALID_JSON)
    session = _StepPanelSession(_FakeConceptOrm(_concept()), queue=[[]])
    scene = await scene_for_concept_diagnosis(
        _diagnosis(0.3),
        session,  # type: ignore[arg-type]
        provider=provider,
        cache=InMemoryCache(),
        trace=RecordingTraceSink(),
        student_id=uuid.uuid4(),
    )
    assert scene is not None
    assert _step_panels(scene) == []
    assert session.execute_calls == 1  # 앵커 조회 1회뿐 — 경로 조회 0


@pytest.mark.asyncio
async def test_no_step_panel_when_no_path_exists(monkeypatch: pytest.MonkeyPatch) -> None:
    """시도 문항은 있으나 승격 경로가 하나도 없으면 방출 0(데이터 없음 방향)."""
    monkeypatch.setattr(scene_mod, "get_active_hypotheses", _no_hypotheses)
    monkeypatch.setattr(scene_mod, "net_support_by_misconception", _no_evidence)
    provider = _FakeProvider(_VALID_JSON)
    session = _StepPanelSession(
        _FakeConceptOrm(_concept()),
        queue=[[(uuid.uuid4(), uuid.uuid4())], []],  # 앵커 1건 → 경로 없음
    )
    scene = await scene_for_concept_diagnosis(
        _diagnosis(0.3),
        session,  # type: ignore[arg-type]
        provider=provider,
        cache=InMemoryCache(),
        trace=RecordingTraceSink(),
        student_id=uuid.uuid4(),
    )
    assert scene is not None
    assert _step_panels(scene) == []


@pytest.mark.asyncio
async def test_no_student_id_skips_anchor_query(monkeypatch: pytest.MonkeyPatch) -> None:
    """student_id 미제공 → 앵커 해소 생략(익명은 시도 이력 없음·정직한 경계) → 방출 0.

    execute 호출 카운터가 0이어야 한다 — 앵커 조회가 실행됐다면 1 이상으로 잡힌다.
    """

    async def _boom(session: object, user_id: uuid.UUID) -> list[object]:
        raise AssertionError("student_id None이면 가설 store를 조회하면 안 된다")

    monkeypatch.setattr(scene_mod, "get_active_hypotheses", _boom)
    provider = _FakeProvider(_VALID_JSON)
    session = _FakeSession(_FakeConceptOrm(_concept()))
    scene = await scene_for_concept_diagnosis(
        _diagnosis(0.3),
        session,  # type: ignore[arg-type]
        provider=provider,
        cache=InMemoryCache(),
        trace=RecordingTraceSink(),
    )
    assert scene is not None
    assert _step_panels(scene) == []
    assert session.execute_calls == 0
