"""LearningScene 생성기 단위테스트 — 개념 메타 결정론 골격 + L3 spec 충전. S3(05a §5).

라이브 LLM 없음: 가짜 provider(정해진 JSON 반환) + 인메모리 스텁(`test_visualization_generator`
패턴 답습). 커버: 시각화(+param_control)·소크라테스(인지유형 결정론·기본)·오개념 프로브(적응·
카탈로그 필터)·배치 결정론·게이트 라운드트립·시각화 spec 검증 실패 전파.

설계 정본: docs/architecture/05a_learning_scene_dsl.md §5. 안전(CLAUDE.md): 결정론 골격(LLM은
spec만)·답 미루기(hint_level=1)·낙인 금지(프로브는 활성 가설 ∩ 카탈로그에서만).
"""

from __future__ import annotations

import pytest

from whymath_backend.l3.interfaces import InMemoryCache, RecordingTraceSink
from whymath_backend.l3.models import RoutingDecision, RoutingRequest
from whymath_backend.l3.visualization import InvalidVisualizationSpecError
from whymath_backend.l4.learning_scene import (
    LearningScene,
    MisconceptionProbeElement,
    ParamControlElement,
    SceneLayout,
    SceneLearnerContext,
    SkillFocusElement,
    SocraticPromptElement,
    TutoringPromptElement,
    VisualizationElement,
    parse_learning_scene,
)
from whymath_backend.l4.misconception.catalog import CATALOG_BY_ID
from whymath_backend.l4.misconception.models import InterventionPattern
from whymath_backend.l4.scene_generation import generate_learning_scene
from whymath_backend.l4.socratic.categories import SocraticCategory
from whymath_backend.schema.concept import Concept
from whymath_backend.schema.enums import (
    BehaviorArea,
    CognitiveType,
    ConceptLevel,
    Visualizability,
    VisualizationStyle,
)

_VALID_MC_ID = next(iter(CATALOG_BY_ID))
_VALID_MC_ID2 = list(CATALOG_BY_ID)[1]  # 두 번째 카탈로그 id(다중 프로브 다양화 검증용).

# 가짜 LLM 출력 — graph_2d(파라미터 선언)·graph_2d(무파라미터)·surface_3d.
_GRAPH2D_WITH_PARAMS = (
    '{"type": "interactive_graph_2d", "spec": {"function": "a*x**2", '
    '"parameters": [{"name": "a", "min": -5, "max": 5, "step": 0.1, "default": 1}]}, '
    '"interactive": true}'
)
_GRAPH2D_NO_PARAMS = (
    '{"type": "interactive_graph_2d", "spec": {"function": "x**2"}, ' '"interactive": true}'
)
_SURFACE3D = (
    '{"type": "interactive_surface_3d", "spec": {"surface": "z = x**2 + y**2"}, '
    '"interactive": true}'
)


class _FakeProvider:
    """가짜 LLMProvider — 호출 기록 + 정해진 텍스트 반환(LLMProvider 구조 충족)."""

    def __init__(self, text: str) -> None:
        self._text = text
        self.calls: list[tuple[str, str, RoutingDecision]] = []

    async def generate(self, prompt: str, system: str, decision: RoutingDecision) -> str:
        self.calls.append((prompt, system, decision))
        return self._text


def _req() -> RoutingRequest:
    """LOCAL·동기로 라우팅되는 평이한 생성 요청."""
    return RoutingRequest(
        task_type="generate",
        difficulty="medium",
        requires_reasoning=True,
        student_subscription="free",
    )


def _concept(
    *,
    styles: list[VisualizationStyle] | None = None,
    cognitive: list[CognitiveType] | None = None,
    code: str = "ALG-QUAD-DEF",
    name: str = "이차함수의 그래프",
) -> Concept:
    return Concept(
        code=code,
        name_ko=name,
        level=ConceptLevel.세부개념,
        recommended_visual_styles=styles or [],
        cognitive_type=cognitive or [],
    )


async def _generate(
    concept: Concept,
    *,
    text: str = _GRAPH2D_WITH_PARAMS,
    learner_context: SceneLearnerContext | None = None,
    visualizability: Visualizability | None = None,
    behavior_areas: list[BehaviorArea] | None = None,
    max_level: int = 4,
) -> tuple[LearningScene, _FakeProvider]:
    provider = _FakeProvider(text)
    scene = await generate_learning_scene(
        concept,
        "고1",
        _req(),
        provider=provider,
        cache=InMemoryCache(),
        trace=RecordingTraceSink(),
        learner_context=learner_context,
        visualizability=visualizability,
        behavior_areas=behavior_areas,
        answer_deferral_max_level=max_level,
    )
    return scene, provider


def _socratics(scene: LearningScene) -> list[SocraticPromptElement]:
    return [el for el in scene.elements if isinstance(el, SocraticPromptElement)]


# ── 시각화 + param_control ───────────────────────────────────────────────────
class TestVisualizationElement:
    @pytest.mark.asyncio
    async def test_graph2d_with_params_adds_param_control(self) -> None:
        """graph_2d + 선언 파라미터 → visualization + 그 파라미터를 타깃하는 param_control."""
        scene, provider = await _generate(_concept(styles=[VisualizationStyle.함수그래프]))
        viz = [el for el in scene.elements if isinstance(el, VisualizationElement)]
        pcs = [el for el in scene.elements if isinstance(el, ParamControlElement)]
        assert len(viz) == 1
        assert len(pcs) == 1
        assert pcs[0].targets == ["a"]
        # bound index는 절대 위치가 아니라 *그 visualization 요소*를 가리킨다(진입 순서 무관 정합).
        assert scene.elements[pcs[0].bound_visualization_index] is viz[0]
        # spec 충전이 라우터(provider) 경유로 일어났고, 개념명이 프롬프트에 들어갔다.
        assert provider.calls
        assert "이차함수의 그래프" in provider.calls[0][0]

    @pytest.mark.asyncio
    async def test_graph2d_no_params_no_param_control(self) -> None:
        """graph_2d지만 파라미터 미선언 → param_control 없음(보수적)."""
        scene, _ = await _generate(
            _concept(styles=[VisualizationStyle.함수그래프]), text=_GRAPH2D_NO_PARAMS
        )
        assert any(isinstance(el, VisualizationElement) for el in scene.elements)
        assert not any(isinstance(el, ParamControlElement) for el in scene.elements)

    @pytest.mark.asyncio
    async def test_non_graph2d_no_param_control(self) -> None:
        """비-graph_2d(surface_3d) → param_control 없음."""
        scene, _ = await _generate(_concept(styles=[VisualizationStyle.입체도형]), text=_SURFACE3D)
        assert any(isinstance(el, VisualizationElement) for el in scene.elements)
        assert not any(isinstance(el, ParamControlElement) for el in scene.elements)

    @pytest.mark.asyncio
    async def test_no_styles_no_visualization_and_no_llm_call(self) -> None:
        """권장 양식 없음 → 시각화 요소 없음 + LLM 미호출(결정론·정직한 경계)."""
        scene, provider = await _generate(_concept(styles=[], cognitive=[CognitiveType.DEFINITION]))
        assert not any(isinstance(el, VisualizationElement) for el in scene.elements)
        assert provider.calls == []  # 시각화 spec 호출이 유일한 LLM 경로

    @pytest.mark.asyncio
    async def test_invalid_spec_propagates(self) -> None:
        """시각화 spec LLM 출력이 게이트를 통과 못 하면 예외 전파(검증 안 된 명세 비반환)."""
        with pytest.raises(InvalidVisualizationSpecError):
            await _generate(
                _concept(styles=[VisualizationStyle.함수그래프]),
                text="죄송합니다, 못 만듭니다.",
            )


# ── 시각화 가능성 4분류 게이트(플레이북 Part 5·05b) ──────────────────────────
class TestVisualizabilityGate:
    """개념 `visualizability`(직접/동적/부분/추상)가 시각화 요소 생성을 게이트하는지 검증."""

    @pytest.mark.asyncio
    async def test_abstract_skips_literal_visualization(self) -> None:
        """추상(군론·논리) → 리터럴 미생성·LLM 미호출, 소크라테스 폴백(StructureGraph 목표)."""
        scene, provider = await _generate(
            _concept(
                styles=[VisualizationStyle.함수그래프],
                cognitive=[CognitiveType.DEFINITION],
            ),
            visualizability=Visualizability.추상,
        )
        assert not any(isinstance(el, VisualizationElement) for el in scene.elements)
        assert not any(isinstance(el, ParamControlElement) for el in scene.elements)
        assert provider.calls == []  # 억지 리터럴 그림을 위해 LLM을 부르지 않는다
        assert _socratics(scene)  # 대체 접근(소크라테스)은 유지된다

    @pytest.mark.asyncio
    async def test_partial_visualizes(self) -> None:
        """부분(확률 등) → 부분 시각화 대상(AnalogyVisual) — 억지 아님·viz 생성."""
        scene, provider = await _generate(
            _concept(styles=[VisualizationStyle.수형도]),
            visualizability=Visualizability.부분,
        )
        assert any(isinstance(el, VisualizationElement) for el in scene.elements)
        assert provider.calls

    @pytest.mark.asyncio
    async def test_dynamic_visualizes_with_param_control(self) -> None:
        """동적 → 시각화 + 슬라이더(조작이 인지 조건) — 기존 graph_2d 동작과 동일."""
        scene, provider = await _generate(
            _concept(styles=[VisualizationStyle.함수그래프]),
            visualizability=Visualizability.동적,
        )
        assert any(isinstance(el, VisualizationElement) for el in scene.elements)
        assert any(isinstance(el, ParamControlElement) for el in scene.elements)
        assert provider.calls

    @pytest.mark.asyncio
    async def test_direct_visualizes_without_param_control(self) -> None:
        """직접 → 시각화는 하되 슬라이더 생략(정적 그림으로 충분·직접/동적 구분)."""
        scene, _ = await _generate(
            _concept(styles=[VisualizationStyle.함수그래프]),
            visualizability=Visualizability.직접,
        )
        assert any(isinstance(el, VisualizationElement) for el in scene.elements)
        assert not any(isinstance(el, ParamControlElement) for el in scene.elements)

    @pytest.mark.asyncio
    async def test_untagged_none_preserves_legacy_behavior(self) -> None:
        """미태깅(None) → 기존 동작 유지(시각화 + 슬라이더) — 하위호환."""
        scene, _ = await _generate(
            _concept(styles=[VisualizationStyle.함수그래프]),
            visualizability=None,
        )
        assert any(isinstance(el, VisualizationElement) for el in scene.elements)
        assert any(isinstance(el, ParamControlElement) for el in scene.elements)


# ── 소크라테스 발화(인지유형 결정론) ─────────────────────────────────────────
class TestSocraticElements:
    @pytest.mark.asyncio
    async def test_cognitive_type_maps_to_category(self) -> None:
        """DEFINITION → CLARIFICATION·THEOREM → EVIDENCE(결정론 매핑·hint_level=1)."""
        scene, _ = await _generate(
            _concept(styles=[], cognitive=[CognitiveType.DEFINITION, CognitiveType.THEOREM])
        )
        cats = {s.socratic_category for s in _socratics(scene)}
        assert cats == {
            SocraticCategory.CLARIFICATION.value,
            SocraticCategory.EVIDENCE.value,
        }
        assert all(s.hint_level == 1 for s in _socratics(scene))

    @pytest.mark.asyncio
    async def test_no_cognitive_type_default_meta_prompt(self) -> None:
        """인지 유형 없음 → 기본 메타인지 발화 1개(장면은 최소 한 개의 유도 질문)."""
        scene, _ = await _generate(_concept(styles=[], cognitive=[]))
        socratics = _socratics(scene)
        assert len(socratics) == 1
        assert socratics[0].socratic_category == SocraticCategory.META.value

    @pytest.mark.asyncio
    async def test_duplicate_cognitive_type_deduped(self) -> None:
        """같은 인지 유형 중복 → 동일 카테고리 발화는 1개로 중복 제거."""
        scene, _ = await _generate(
            _concept(
                styles=[],
                cognitive=[CognitiveType.DEFINITION, CognitiveType.DEFINITION],
            )
        )
        assert len(_socratics(scene)) == 1

    @pytest.mark.asyncio
    async def test_socratic_prompt_text_is_canonical(self) -> None:
        """발화 본문은 정본 유도 질문(자체 생성 아님·정답 아님)."""
        scene, _ = await _generate(_concept(styles=[], cognitive=[CognitiveType.DEFINITION]))
        assert _socratics(scene)[0].prompt_text == "어디까지 이해됐어?"


# ── 오개념 프로브(적응·카탈로그 필터) ───────────────────────────────────────
class TestMisconceptionProbes:
    @pytest.mark.asyncio
    async def test_no_learner_context_no_probes(self) -> None:
        scene, _ = await _generate(_concept(styles=[], cognitive=[CognitiveType.DEFINITION]))
        assert not any(isinstance(el, MisconceptionProbeElement) for el in scene.elements)

    @pytest.mark.asyncio
    async def test_catalog_hypothesis_becomes_probe(self) -> None:
        """활성 가설이 카탈로그에 있으면 프로브 생성(반례 개입)."""
        ctx = SceneLearnerContext(active_hypothesis_ids=[_VALID_MC_ID])
        scene, _ = await _generate(
            _concept(styles=[], cognitive=[CognitiveType.DEFINITION]),
            learner_context=ctx,
        )
        probes = [el for el in scene.elements if isinstance(el, MisconceptionProbeElement)]
        assert len(probes) == 1
        assert probes[0].misconception_id == _VALID_MC_ID

    @pytest.mark.asyncio
    async def test_non_catalog_hypothesis_skipped(self) -> None:
        """카탈로그에 없는 가설 id는 조용히 제외(거짓 낙인 차단·RS2)."""
        ctx = SceneLearnerContext(active_hypothesis_ids=[_VALID_MC_ID, "nonexistent-xyz"])
        scene, _ = await _generate(
            _concept(styles=[], cognitive=[CognitiveType.DEFINITION]),
            learner_context=ctx,
        )
        probes = [el for el in scene.elements if isinstance(el, MisconceptionProbeElement)]
        assert len(probes) == 1  # 카탈로그 id 1개만

    @pytest.mark.asyncio
    async def test_no_confidences_defaults_counterexample(self) -> None:
        """신뢰도 맵 미제공(레거시) → 개입은 반례(`COUNTEREXAMPLE`) 폴백."""
        ctx = SceneLearnerContext(active_hypothesis_ids=[_VALID_MC_ID])
        scene, _ = await _generate(
            _concept(styles=[], cognitive=[CognitiveType.DEFINITION]),
            learner_context=ctx,
        )
        probes = [el for el in scene.elements if isinstance(el, MisconceptionProbeElement)]
        assert len(probes) == 1
        assert probes[0].intervention == InterventionPattern.COUNTEREXAMPLE

    @pytest.mark.asyncio
    async def test_high_confidence_counterexample(self) -> None:
        """신뢰도 >0.8 → 반례 유도(doc 결정트리 패턴1)."""
        ctx = SceneLearnerContext(
            active_hypothesis_ids=[_VALID_MC_ID],
            active_hypothesis_confidences={_VALID_MC_ID: 0.9},
        )
        scene, _ = await _generate(
            _concept(styles=[], cognitive=[CognitiveType.DEFINITION]),
            learner_context=ctx,
        )
        probes = [el for el in scene.elements if isinstance(el, MisconceptionProbeElement)]
        assert len(probes) == 1
        assert probes[0].intervention == InterventionPattern.COUNTEREXAMPLE

    @pytest.mark.asyncio
    async def test_mid_confidence_reverse_reasoning(self) -> None:
        """0.5 ≤ 신뢰도 ≤ 0.8 → 거꾸로 사고(doc 결정트리 패턴4)."""
        ctx = SceneLearnerContext(
            active_hypothesis_ids=[_VALID_MC_ID],
            active_hypothesis_confidences={_VALID_MC_ID: 0.6},
        )
        scene, _ = await _generate(
            _concept(styles=[], cognitive=[CognitiveType.DEFINITION]),
            learner_context=ctx,
        )
        probes = [el for el in scene.elements if isinstance(el, MisconceptionProbeElement)]
        assert len(probes) == 1
        assert probes[0].intervention == InterventionPattern.REVERSE_REASONING

    @pytest.mark.asyncio
    async def test_low_confidence_probe_withheld(self) -> None:
        """신뢰도 <0.5 → 프로브 미생성(보류·낙인 회피·doc 결정트리)."""
        ctx = SceneLearnerContext(
            active_hypothesis_ids=[_VALID_MC_ID],
            active_hypothesis_confidences={_VALID_MC_ID: 0.3},
        )
        scene, _ = await _generate(
            _concept(styles=[], cognitive=[CognitiveType.DEFINITION]),
            learner_context=ctx,
        )
        assert not any(isinstance(el, MisconceptionProbeElement) for el in scene.elements)

    @pytest.mark.asyncio
    async def test_mixed_confidences_diversified(self) -> None:
        """다중 가설 → 신뢰도별 개입 다양화 + <0.5 보류(반례·거꾸로 공존)."""
        ctx = SceneLearnerContext(
            active_hypothesis_ids=[_VALID_MC_ID, _VALID_MC_ID2],
            active_hypothesis_confidences={_VALID_MC_ID: 0.9, _VALID_MC_ID2: 0.6},
        )
        scene, _ = await _generate(
            _concept(styles=[], cognitive=[CognitiveType.DEFINITION]),
            learner_context=ctx,
        )
        probes = [el for el in scene.elements if isinstance(el, MisconceptionProbeElement)]
        by_id = {p.misconception_id: p.intervention for p in probes}
        assert by_id == {
            _VALID_MC_ID: InterventionPattern.COUNTEREXAMPLE,
            _VALID_MC_ID2: InterventionPattern.REVERSE_REASONING,
        }

    @pytest.mark.asyncio
    async def test_missing_confidence_entry_falls_back(self) -> None:
        """신뢰도 맵에 없는 id는 레거시 반례로 폴백(맵 부분 제공 방어)."""
        ctx = SceneLearnerContext(
            active_hypothesis_ids=[_VALID_MC_ID],
            active_hypothesis_confidences={},  # 맵 제공되었으나 해당 id 부재
        )
        scene, _ = await _generate(
            _concept(styles=[], cognitive=[CognitiveType.DEFINITION]),
            learner_context=ctx,
        )
        probes = [el for el in scene.elements if isinstance(el, MisconceptionProbeElement)]
        assert len(probes) == 1
        assert probes[0].intervention == InterventionPattern.COUNTEREXAMPLE


# common_misconceptions 런타임 미사용 가드는 Phase 1b(2026-07-03)로 제거했다 — 자유서술
# `common_misconceptions` 컬럼 자체가 런타임 Concept에서 삭제돼(schema/db 슬롯 부재·extra="forbid")
# "프로브가 자유서술을 근거로 삼는" 회귀 경로가 *구조적으로 불가능*해졌다(스파이 페이로드 주입
# 불가). 프로브가 오직 활성 가설 ∩ 오개념 카탈로그에서만 나옴은 아래 TestMisconceptionProbe가
# 계속 동결한다(05a RS2 거짓 낙인 차단·CLAUDE.md 학생 안전 #1).


# ── 배치·메타·게이트 라운드트립 ──────────────────────────────────────────────
class TestSceneAssembly:
    @pytest.mark.asyncio
    async def test_single_layout(self) -> None:
        """요소 1개 → single."""
        scene, _ = await _generate(_concept(styles=[], cognitive=[CognitiveType.DEFINITION]))
        assert len(scene.elements) == 1
        assert scene.layout == SceneLayout.single.value

    @pytest.mark.asyncio
    async def test_two_panel_when_visual_present(self) -> None:
        """시각화 + 코칭 → two_panel."""
        scene, _ = await _generate(
            _concept(
                styles=[VisualizationStyle.함수그래프],
                cognitive=[CognitiveType.DEFINITION],
            )
        )
        assert scene.layout == SceneLayout.two_panel.value

    @pytest.mark.asyncio
    async def test_vertical_stack_when_no_visual_multi(self) -> None:
        """시각화 없고 요소 2+ → vertical_stack."""
        scene, _ = await _generate(
            _concept(styles=[], cognitive=[CognitiveType.DEFINITION, CognitiveType.THEOREM])
        )
        assert not any(isinstance(el, VisualizationElement) for el in scene.elements)
        assert scene.layout == SceneLayout.vertical_stack.value

    @pytest.mark.asyncio
    async def test_concept_id_and_topic_label(self) -> None:
        scene, _ = await _generate(
            _concept(
                styles=[],
                cognitive=[CognitiveType.DEFINITION],
                code="UC-XYZ",
                name="개념명",
            )
        )
        assert scene.concept_id == "UC-XYZ"
        assert scene.topic_label == "개념명"

    @pytest.mark.asyncio
    async def test_generated_scene_passes_gate(self) -> None:
        """생성된 명세는 parse_learning_scene 게이트(불변식 + 카탈로그 무결성)를 통과한다."""
        ctx = SceneLearnerContext(active_hypothesis_ids=[_VALID_MC_ID])
        scene, _ = await _generate(
            _concept(
                styles=[VisualizationStyle.함수그래프],
                cognitive=[CognitiveType.DEFINITION],
            ),
            learner_context=ctx,
        )
        # dump → 게이트 재검증(엔드투엔드: 골격 산출물이 게이트 호환)
        reparsed = parse_learning_scene(scene.model_dump(mode="json"))
        assert isinstance(reparsed, LearningScene)

    @pytest.mark.asyncio
    async def test_socratic_hint_within_max_level(self) -> None:
        """answer_deferral_max_level=1이어도 소크라테스 hint_level=1이라 불변식 충족(답 미루기)."""
        scene, _ = await _generate(
            _concept(styles=[], cognitive=[CognitiveType.PATTERN]), max_level=1
        )
        assert all(s.hint_level <= 1 for s in _socratics(scene))


# ── 행동영역 분기 축(BehaviorArea·정본 6종·S5k) ──────────────────────────────
def _first_index(scene: LearningScene, cls: type) -> int:
    """장면에서 `cls` 요소의 첫 인덱스(없으면 -1)."""
    return next((i for i, el in enumerate(scene.elements) if isinstance(el, cls)), -1)


class TestBehaviorDomainAxis:
    """행동영역(BehaviorArea)이 *인지 진입 순서*를 결정한다(S5k·정본 축).

    행동영역이 planner 독립 분기 입력임을 검증(Part 7 재검토·#418 BehaviorArea로 재정렬).
    소크라테스는 개념 축(cognitive_type)이 담당하므로 여기선 진입 순서만 본다.
    """

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "area",
        [BehaviorArea.COMPUTE, BehaviorArea.TRANSFORM, BehaviorArea.REPRESENT],
    )
    async def test_visual_lead_puts_visualization_first(self, area: BehaviorArea) -> None:
        """visual 진입(계산·변형·표상) → 시각화 요소가 소크라테스보다 앞에 온다."""
        scene, _ = await _generate(
            _concept(styles=[VisualizationStyle.함수그래프]), behavior_areas=[area]
        )
        viz_i = _first_index(scene, VisualizationElement)
        soc_i = _first_index(scene, SocraticPromptElement)
        assert viz_i >= 0 and soc_i >= 0
        assert viz_i < soc_i

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "area", [BehaviorArea.INTERPRET, BehaviorArea.REASON, BehaviorArea.VERIFY]
    )
    async def test_inquiry_lead_puts_socratic_first(self, area: BehaviorArea) -> None:
        """inquiry 진입(해석·추론·검증) → 소크라테스(질문)가 시각화보다 앞에 온다."""
        scene, _ = await _generate(
            _concept(styles=[VisualizationStyle.함수그래프]), behavior_areas=[area]
        )
        viz_i = _first_index(scene, VisualizationElement)
        soc_i = _first_index(scene, SocraticPromptElement)
        assert viz_i >= 0 and soc_i >= 0
        assert soc_i < viz_i

    @pytest.mark.asyncio
    async def test_primary_behavior_area_precedence(self) -> None:
        """다중 행동영역 precedence — [VERIFY, REPRESENT] → REPRESENT 주 → visual 진입."""
        scene, _ = await _generate(
            _concept(styles=[VisualizationStyle.함수그래프]),
            behavior_areas=[BehaviorArea.VERIFY, BehaviorArea.REPRESENT],
        )
        assert _first_index(scene, VisualizationElement) < _first_index(
            scene, SocraticPromptElement
        )

    @pytest.mark.asyncio
    async def test_no_behavior_area_defaults_inquiry(self) -> None:
        """behavior_area 미매핑 → 기본(inquiry) → 소크라테스 먼저."""
        scene, _ = await _generate(
            _concept(styles=[VisualizationStyle.함수그래프]), behavior_areas=None
        )
        assert _first_index(scene, SocraticPromptElement) < _first_index(
            scene, VisualizationElement
        )

    @pytest.mark.asyncio
    async def test_inquiry_lead_param_control_index_valid(self) -> None:
        """★인덱스 정합: inquiry 진입으로 viz가 뒤 index여도 param_control이 그 viz를 가리키고
        게이트를 통과한다(순서 변경이 불변식을 깨지 않음)."""
        scene, _ = await _generate(
            _concept(styles=[VisualizationStyle.함수그래프]),
            behavior_areas=[BehaviorArea.VERIFY],
        )
        pcs = [el for el in scene.elements if isinstance(el, ParamControlElement)]
        viz = [el for el in scene.elements if isinstance(el, VisualizationElement)]
        assert len(pcs) == 1 and len(viz) == 1
        # 소크라테스·skill_focus가 앞서므로 viz는 index 0이 아님(진입 순서 실제 변화 확인)
        assert scene.elements.index(viz[0]) > 0
        # 그럼에도 bound index는 그 visualization을 가리킨다
        assert scene.elements[pcs[0].bound_visualization_index] is viz[0]
        # 게이트(불변식 + 카탈로그 무결성) 라운드트립 통과
        reparsed = parse_learning_scene(scene.model_dump(mode="json"))
        assert isinstance(reparsed, LearningScene)


# ── 가시 SkillBlock(행동영역 focus·05a §3.2·S5k) ──────────────────────────────
def _skill_focus(scene: LearningScene) -> list[SkillFocusElement]:
    return [el for el in scene.elements if isinstance(el, SkillFocusElement)]


class TestSkillFocusBlock:
    """행동영역 focus 블록 — BehaviorArea 매핑 유무가 블록 유무를 자동 분기(체크리스트 ②)."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("area", list(BehaviorArea))
    async def test_mapped_behavior_area_emits_skill_focus_first(self, area: BehaviorArea) -> None:
        """행동영역이 매핑되면 → skill_focus 1개·맨 앞·해당 behavior_area."""
        scene, _ = await _generate(_concept(styles=[]), behavior_areas=[area])
        focus = _skill_focus(scene)
        assert len(focus) == 1
        assert scene.elements[0] is focus[0]  # 맨 앞(행동영역 프레이밍)
        assert focus[0].behavior_area == area.value
        assert focus[0].focus_prompt  # 정본 지시 비어있지 않음

    @pytest.mark.asyncio
    async def test_no_behavior_area_no_skill_focus(self) -> None:
        """behavior_area 미매핑 → skill_focus 미생성(행동영역별 자동 분기·중립 폴백)."""
        scene, _ = await _generate(_concept(styles=[]), behavior_areas=None)
        assert _skill_focus(scene) == []

    @pytest.mark.asyncio
    async def test_skill_focus_has_no_answer_fields(self) -> None:
        """skill_focus는 정답/수정 필드를 담을 수 없다(answer-deferral·낙인 금지·스키마 차단)."""
        assert set(SkillFocusElement.model_fields) == {
            "kind",
            "behavior_area",
            "focus_prompt",
        }

    @pytest.mark.asyncio
    async def test_scene_with_skill_focus_passes_gate(self) -> None:
        """skill_focus 포함 장면이 parse_learning_scene 게이트 라운드트립을 통과한다."""
        scene, _ = await _generate(
            _concept(styles=[VisualizationStyle.함수그래프]),
            behavior_areas=[BehaviorArea.COMPUTE],
        )
        assert _skill_focus(scene)  # 매핑 있으므로 존재
        reparsed = parse_learning_scene(scene.model_dump(mode="json"))
        assert isinstance(reparsed, LearningScene)


# ── LTHC 학생적응 튜터링 프롬프트(mastery 축·S5l) ─────────────────────────────
def _tutoring(scene: LearningScene) -> list[TutoringPromptElement]:
    return [el for el in scene.elements if isinstance(el, TutoringPromptElement)]


class TestTutoringAdapter:
    """숙달도(mastery)가 LTHC 튜터링 프롬프트를 자동 분기(체크리스트 ② 학습자모델 축·S5l).

    초보=진입+비계·숙달=확장·발전중=균형(`adapt_lthc` 재사용). mastery 없으면 미부여(중립·정직한
    경계). tutoring_prompt엔 hint_level이 없어 답 미루기 불변식과 무관(정답 아닌 유도 가이드).
    """

    @pytest.mark.asyncio
    async def test_no_learner_context_no_tutoring(self) -> None:
        """learner_context 없음 → 튜터링 프롬프트 0(중립·정직한 경계)."""
        scene, _ = await _generate(_concept(styles=[], cognitive=[CognitiveType.DEFINITION]))
        assert _tutoring(scene) == []

    @pytest.mark.asyncio
    async def test_none_mastery_no_tutoring(self) -> None:
        """mastery_level None(가설만 있음) → 튜터링 프롬프트 0."""
        ctx = SceneLearnerContext(active_hypothesis_ids=[_VALID_MC_ID])
        scene, _ = await _generate(
            _concept(styles=[], cognitive=[CognitiveType.DEFINITION]),
            learner_context=ctx,
        )
        assert _tutoring(scene) == []

    @pytest.mark.asyncio
    async def test_beginner_entry_and_scaffold(self) -> None:
        """초보(mastery<0.4) → 진입(entry)+비계(scaffold), 확장 없음."""
        ctx = SceneLearnerContext(mastery_level=0.2)
        scene, _ = await _generate(
            _concept(styles=[], cognitive=[CognitiveType.DEFINITION]),
            learner_context=ctx,
        )
        assert {t.role for t in _tutoring(scene)} == {"entry", "scaffold"}

    @pytest.mark.asyncio
    async def test_mastered_extension_only(self) -> None:
        """숙달(mastery≥0.8) → 확장(extension)만."""
        ctx = SceneLearnerContext(mastery_level=0.9)
        scene, _ = await _generate(
            _concept(styles=[], cognitive=[CognitiveType.DEFINITION]),
            learner_context=ctx,
        )
        assert {t.role for t in _tutoring(scene)} == {"extension"}

    @pytest.mark.asyncio
    async def test_developing_balanced(self) -> None:
        """발전 중(0.4≤mastery<0.8) → 진입+비계+확장 균형(3개)."""
        ctx = SceneLearnerContext(mastery_level=0.5)
        scene, _ = await _generate(
            _concept(styles=[], cognitive=[CognitiveType.DEFINITION]),
            learner_context=ctx,
        )
        tutoring = _tutoring(scene)
        assert {t.role for t in tutoring} == {"entry", "scaffold", "extension"}
        assert len(tutoring) == 3

    @pytest.mark.asyncio
    @pytest.mark.parametrize("mastery", [0.1, 0.2, 0.5, 0.8, 0.95])
    async def test_volume_cap_per_axis(self, mastery: float) -> None:
        """어느 숙달도 밴드에서도 축당 ≤1·총 ≤3(장면 비대 방지)."""
        ctx = SceneLearnerContext(mastery_level=mastery)
        scene, _ = await _generate(
            _concept(styles=[], cognitive=[CognitiveType.PATTERN]),
            learner_context=ctx,
        )
        tutoring = _tutoring(scene)
        assert len(tutoring) <= 3
        role_counts: dict[str, int] = {}
        for t in tutoring:
            role_counts[t.role] = role_counts.get(t.role, 0) + 1
        assert all(c <= 1 for c in role_counts.values())

    @pytest.mark.asyncio
    async def test_placement_after_socratic_before_probes(self) -> None:
        """튜터링 프롬프트는 소크라테스 뒤·오개념 프로브 앞 고정 슬롯(lead 무관)."""
        ctx = SceneLearnerContext(mastery_level=0.2, active_hypothesis_ids=[_VALID_MC_ID])
        scene, _ = await _generate(
            _concept(styles=[], cognitive=[CognitiveType.DEFINITION]),
            learner_context=ctx,
        )
        tut_idx = [
            i for i, el in enumerate(scene.elements) if isinstance(el, TutoringPromptElement)
        ]
        soc_last = max(
            i for i, el in enumerate(scene.elements) if isinstance(el, SocraticPromptElement)
        )
        probe_first = _first_index(scene, MisconceptionProbeElement)
        assert tut_idx  # 존재
        assert min(tut_idx) > soc_last  # 소크라테스 뒤
        assert probe_first >= 0 and max(tut_idx) < probe_first  # 프로브 앞

    @pytest.mark.asyncio
    async def test_tutoring_scene_passes_gate(self) -> None:
        """튜터링 프롬프트 포함 장면이 parse_learning_scene 게이트 라운드트립을 통과한다."""
        ctx = SceneLearnerContext(mastery_level=0.5)
        scene, _ = await _generate(
            _concept(styles=[VisualizationStyle.함수그래프], cognitive=[CognitiveType.DEFINITION]),
            learner_context=ctx,
        )
        assert _tutoring(scene)
        reparsed = parse_learning_scene(scene.model_dump(mode="json"))
        assert isinstance(reparsed, LearningScene)

    @pytest.mark.asyncio
    async def test_tutoring_prompt_has_no_answer_fields(self) -> None:
        """tutoring_prompt는 정답/수정/hint_level 필드 부재(answer-deferral·낙인 금지)."""
        assert set(TutoringPromptElement.model_fields) == {"kind", "role", "prompt_text"}
