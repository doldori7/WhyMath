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
    SocraticPromptElement,
    VisualizationElement,
    parse_learning_scene,
)
from whymath_backend.l4.misconception.catalog import CATALOG_BY_ID
from whymath_backend.l4.misconception.models import InterventionPattern
from whymath_backend.l4.scene_generation import generate_learning_scene
from whymath_backend.l4.socratic.categories import SocraticCategory
from whymath_backend.schema.concept import Concept
from whymath_backend.schema.enums import (
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
    '{"type": "interactive_graph_2d", "spec": {"function": "x**2"}, "interactive": true}'
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
        assert pcs[0].bound_visualization_index == 0
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
                _concept(styles=[VisualizationStyle.함수그래프]), text="죄송합니다, 못 만듭니다."
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
        assert cats == {SocraticCategory.CLARIFICATION.value, SocraticCategory.EVIDENCE.value}
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
            _concept(styles=[], cognitive=[CognitiveType.DEFINITION, CognitiveType.DEFINITION])
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
            _concept(styles=[], cognitive=[CognitiveType.DEFINITION]), learner_context=ctx
        )
        probes = [el for el in scene.elements if isinstance(el, MisconceptionProbeElement)]
        assert len(probes) == 1
        assert probes[0].misconception_id == _VALID_MC_ID

    @pytest.mark.asyncio
    async def test_non_catalog_hypothesis_skipped(self) -> None:
        """카탈로그에 없는 가설 id는 조용히 제외(거짓 낙인 차단·RS2)."""
        ctx = SceneLearnerContext(active_hypothesis_ids=[_VALID_MC_ID, "nonexistent-xyz"])
        scene, _ = await _generate(
            _concept(styles=[], cognitive=[CognitiveType.DEFINITION]), learner_context=ctx
        )
        probes = [el for el in scene.elements if isinstance(el, MisconceptionProbeElement)]
        assert len(probes) == 1  # 카탈로그 id 1개만

    @pytest.mark.asyncio
    async def test_no_confidences_defaults_counterexample(self) -> None:
        """신뢰도 맵 미제공(레거시) → 개입은 반례(`COUNTEREXAMPLE`) 폴백."""
        ctx = SceneLearnerContext(active_hypothesis_ids=[_VALID_MC_ID])
        scene, _ = await _generate(
            _concept(styles=[], cognitive=[CognitiveType.DEFINITION]), learner_context=ctx
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
            _concept(styles=[], cognitive=[CognitiveType.DEFINITION]), learner_context=ctx
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
            _concept(styles=[], cognitive=[CognitiveType.DEFINITION]), learner_context=ctx
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
            _concept(styles=[], cognitive=[CognitiveType.DEFINITION]), learner_context=ctx
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
            _concept(styles=[], cognitive=[CognitiveType.DEFINITION]), learner_context=ctx
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
            _concept(styles=[], cognitive=[CognitiveType.DEFINITION]), learner_context=ctx
        )
        probes = [el for el in scene.elements if isinstance(el, MisconceptionProbeElement)]
        assert len(probes) == 1
        assert probes[0].intervention == InterventionPattern.COUNTEREXAMPLE


# ── common_misconceptions 런타임 미사용 가드(Q1/Q8 — 노드 자유서술은 프로브 근거 아님) ──────
class TestCommonMisconceptionsNotConsumed:
    """노드의 자유서술 `common_misconceptions`(정답/수정 텍스트)가 *런타임 프로브 근거로 쓰이지
    않음*을 동결하는 가드.

    프로브는 학습자의 *근거 있는* 활성 가설(`active_hypothesis_ids`) ∩ 오개념 카탈로그
    (`CATALOG_BY_ID`)에서만 나와야 한다(05a RS2 거짓 낙인 차단). 자유서술 필드를 프로브로 쓰면
    검증 불가 텍스트로 낙인·즉답·날조 위험(CLAUDE.md 학생 안전 #1·교수학 #3). 현재 미사용이나
    *코드로 강제된 미사용 가드가 없어* 누군가 generate_learning_scene에서 읽으면 막을 게 없다 —
    그 회귀를 동결한다.
    """

    @staticmethod
    def _concept_with_misconceptions(
        cm: list[dict[str, str]],
    ) -> Concept:
        """common_misconceptions를 채운 개념(나머지는 _concept 기본·시각화 없음)."""
        return Concept(
            code="ALG-QUAD-DEF",
            name_ko="이차함수의 그래프",
            level=ConceptLevel.세부개념,
            cognitive_type=[CognitiveType.DEFINITION],
            common_misconceptions=cm,
        )

    @pytest.mark.asyncio
    async def test_populated_common_misconceptions_produce_no_probes(self) -> None:
        """common_misconceptions가 가득 차 있어도 *학습자 활성 가설이 없으면* 프로브 0.

        자유서술 오개념이 프로브 *원천*이라면 여기서 프로브가 생겼을 것 — 0이라는 것은 그 필드가
        프로브 경로에 *들어가지 않음*을 보인다(스파이 페이로드).
        """
        spy = [
            {"misconception": "(a+b)^2 = a^2+b^2로 전개", "correction": "교차항 2ab 누락"},
            {"misconception": "이차함수는 항상 최솟값을 갖는다", "correction": "a<0이면 최댓값"},
        ]
        scene, _ = await _generate(self._concept_with_misconceptions(spy), learner_context=None)
        probes = [el for el in scene.elements if isinstance(el, MisconceptionProbeElement)]
        assert probes == []

    @pytest.mark.asyncio
    async def test_probe_set_invariant_to_common_misconceptions(self) -> None:
        """동일 학습자 컨텍스트에서, common_misconceptions가 비었든 가득 찼든 프로브 집합이 동일.

        프로브 id 집합이 자유서술 필드 내용에 *불변*임을 보여, 프로브가 오직 활성 가설 ∩ 카탈로그
        에서만 결정됨을 동결한다.
        """
        ctx = SceneLearnerContext(active_hypothesis_ids=[_VALID_MC_ID])
        empty_scene, _ = await _generate(self._concept_with_misconceptions([]), learner_context=ctx)
        filled_scene, _ = await _generate(
            self._concept_with_misconceptions(
                [{"misconception": "스파이 오개념", "correction": "스파이 정정"}]
            ),
            learner_context=ctx,
        )

        def _probe_ids(scene: LearningScene) -> set[str]:
            return {
                el.misconception_id
                for el in scene.elements
                if isinstance(el, MisconceptionProbeElement)
            }

        assert _probe_ids(empty_scene) == _probe_ids(filled_scene) == {_VALID_MC_ID}


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
            _concept(styles=[VisualizationStyle.함수그래프], cognitive=[CognitiveType.DEFINITION])
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
            _concept(styles=[], cognitive=[CognitiveType.DEFINITION], code="UC-XYZ", name="개념명")
        )
        assert scene.concept_id == "UC-XYZ"
        assert scene.topic_label == "개념명"

    @pytest.mark.asyncio
    async def test_generated_scene_passes_gate(self) -> None:
        """생성된 명세는 parse_learning_scene 게이트(불변식 + 카탈로그 무결성)를 통과한다."""
        ctx = SceneLearnerContext(active_hypothesis_ids=[_VALID_MC_ID])
        scene, _ = await _generate(
            _concept(styles=[VisualizationStyle.함수그래프], cognitive=[CognitiveType.DEFINITION]),
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
