"""L4 LearningScene 생성기 — 개념 메타 결정론 골격 + L3 spec 충전. S3.

설계 정본: `docs/architecture/05a_learning_scene_dsl.md` §5(L3 생성). 개념 노드(L1 `Concept`)의
구조 메타(`recommended_visual_styles`·`cognitive_type`)에서 **결정론 골격**(어떤 요소 kind를 둘지)을
코드가 만들고, `visualization` 요소의 `spec`만 L3 `generate_visualization_spec`(라우터·Langfuse·
캐시 경유)로 충전한 뒤, 학습자 상태(L2 스냅샷)로 *적응*해 `LearningScene`을 조립한다.

★7계층 배치(왜 L4인가 — 05a §5의 "L3" 표기 교정): 05a §1·§5는 generate_learning_scene을 *L3*로
표기하나, **S2가 `LearningScene`을 L4에 배치**(schema는 L레이어 import 0 → 역방향 회피)했으므로
생성기가 L3에 있으면 `LearningScene`(L4)을 import해 **역방향 의존 위반**이 된다. 따라서 생성기는
**L4**에 두고 L3 `generate_visualization_spec`을 *다운콜*한다(L4→L3 `LLMSeam` 방향·`l4/models.py`).
즉 "생성"이라는 *역할*은 L3적이나 *배치*는 LearningScene과 같은 L4여야 계층 규칙을 지킨다.

교수학 안전(CLAUDE.md 1·2·3·05a §2·§4) — 결정론·답 미루기·낙인 금지:
  - 시각화 spec만 LLM이 채우고(검증 게이트 통과), 골격·참조·발화는 *코드가 결정론적으로* 채운다
    (RS5 환각 방어). LLM 호출은 1회(스타일 있을 때만)·로컬 우선(`generate_visualization_spec`).
  - 소크라테스 발화는 정답이 아니라 *정본 유도 질문*(`EXAMPLE_QUESTION`)·`hint_level=1`(가장 은근).
  - `misconception_probe`는 **학습자 활성 가설(`active_hypothesis_ids`) ∩ 오개념 카탈로그**에만
    생성(RS2 거짓 낙인 차단) — 개념의 자유서술 `common_misconceptions`(정답/수정 텍스트)는
    카탈로그 id가 아니라 *프로브 근거로 쓰지 않는다*(낙인·즉답 금지).

범위(S3): 골격 + spec 충전 + 게이트 통과 명세 반환. `concept_id`는 `Concept.code`(개념그래프 UC).
개념그래프 *존재* 검증(DB)·다중 시각화·step_panel(SolutionPath Python 구현 후속)·L5 렌더러는 S4+.
"""

from __future__ import annotations

from typing import Literal, NamedTuple

from whymath_backend.l3.interfaces import CacheBackend, LLMProvider, TraceSink
from whymath_backend.l3.models import RoutingRequest
from whymath_backend.l3.visualization import generate_visualization_spec
from whymath_backend.l4.learning_scene import (
    LearningScene,
    MisconceptionProbeElement,
    ParamControlElement,
    SceneElement,
    SceneLayout,
    SceneLearnerContext,
    SocraticPromptElement,
    VisualizationElement,
)
from whymath_backend.l4.misconception.catalog import CATALOG_BY_ID
from whymath_backend.l4.misconception.intervene import select_intervention
from whymath_backend.l4.misconception.models import (
    InterventionPattern,
    MisconceptionMatch,
)
from whymath_backend.l4.models import PolyaStage
from whymath_backend.l4.socratic.categories import EXAMPLE_QUESTION, SocraticCategory
from whymath_backend.schema.concept import Concept
from whymath_backend.schema.enums import CognitiveType, VisualizationType
from whymath_backend.schema.visualization import Graph2dSpec


# 인지 유형(행동영역) → 요소 조합 프로파일 — 05a §5.1 구현(S5i).
# cognitive_type을 소비하는 *단일 1급 구조*: 소크라테스 프레이밍 + 인지 진입 순서(lead)를 결정.
# 행동영역을 소크라테스 매핑 *부수효과*가 아니라 planner **독립 분기 입력**으로 승격(Part 7 재검토).
# "표면 표현이 아니라 인지 행동(cognitive action) 기준"(플레이북) — 행동영역이 진입점을 가른다.
class CompositionProfile(NamedTuple):
    """행동영역별 장면 조합 프로파일 — 소크라테스 (카테고리, Polya단계) + 인지 진입 순서.

    `lead`: 장면이 시각화로 진입("visual": 보고→추론)하는지 탐구로 진입("inquiry": 질문→확인)하는지.
    정답이 아니라 *인지 진입점*을 행동영역에 맞춘다(LLM 추측 아님·결정론).
    """

    socratic: tuple[SocraticCategory, PolyaStage]
    lead: Literal["visual", "inquiry"]


# 개념 *성격*에 맞는 메타인지 발화·진입 순서를 코드가 고른다(LLM 추측 아님). 정답 아니라 유도 질문.
_COMPOSITION_PROFILE: dict[CognitiveType, CompositionProfile] = {
    # 정의·정리 = 언어/논리 진입(질문 먼저) · 기법·패턴·시각추론 = 행동/시각 진입(그림 먼저)
    CognitiveType.DEFINITION: CompositionProfile(
        (SocraticCategory.CLARIFICATION, PolyaStage.UNDERSTAND), "inquiry"
    ),
    CognitiveType.THEOREM: CompositionProfile(
        (SocraticCategory.EVIDENCE, PolyaStage.PLAN), "inquiry"
    ),
    CognitiveType.TECHNIQUE: CompositionProfile(
        (SocraticCategory.PERSPECTIVE, PolyaStage.PLAN), "visual"
    ),
    CognitiveType.PATTERN: CompositionProfile(
        (SocraticCategory.IMPLICATION, PolyaStage.EXECUTE), "visual"
    ),
    CognitiveType.VISUAL_REASONING: CompositionProfile(
        (SocraticCategory.ASSUMPTION, PolyaStage.UNDERSTAND), "visual"
    ),
}
# 인지 유형이 없을 때의 기본 프로파일 — "메타인지 중심" 정체성(CLAUDE.md)상 장면은 최소 한 개의
# 유도 질문을 가지며, 진입은 탐구(질문)가 기본값.
_DEFAULT_PROFILE = CompositionProfile(
    (SocraticCategory.META, PolyaStage.REVIEW), "inquiry"
)

# 다중 cognitive_type일 때 *주 행동영역* precedence(결정론) — 행동/시각 지향이 진입을 이끈다.
# 값이 작을수록 우선. 예: [DEFINITION, VISUAL_REASONING] → VISUAL_REASONING이 주 → visual 진입.
_COGNITIVE_PRECEDENCE: dict[CognitiveType, int] = {
    CognitiveType.VISUAL_REASONING: 0,
    CognitiveType.PATTERN: 1,
    CognitiveType.TECHNIQUE: 2,
    CognitiveType.THEOREM: 3,
    CognitiveType.DEFINITION: 4,
}


def _primary_cognitive_type(concept: Concept) -> CognitiveType | None:
    """다중 cognitive_type에서 *주 행동영역*을 결정론적으로 고른다(precedence 최소값). 없으면 None.

    use_enum_values=True라 `concept.cognitive_type` 원소는 런타임 str → `CognitiveType`로 정규화.
    """
    types = [CognitiveType(raw) for raw in concept.cognitive_type]
    if not types:
        return None
    return min(types, key=lambda t: _COGNITIVE_PRECEDENCE[t])


def _profile_for(concept: Concept) -> CompositionProfile:
    """개념의 주 행동영역 → 요소 조합 프로파일(없으면 기본 탐구 진입)."""
    primary = _primary_cognitive_type(concept)
    return _COMPOSITION_PROFILE[primary] if primary is not None else _DEFAULT_PROFILE


def _socratic_elements(concept: Concept) -> list[SocraticPromptElement]:
    """개념 `cognitive_type` → 소크라테스 발화 요소(결정론·중복 카테고리 제거)."""
    elements: list[SocraticPromptElement] = []
    seen: set[SocraticCategory] = set()
    # use_enum_values=True라 concept.cognitive_type 원소는 런타임 str → CognitiveType로 정규화.
    for raw in concept.cognitive_type:
        category, stage = _COMPOSITION_PROFILE[CognitiveType(raw)].socratic
        if category in seen:
            continue
        seen.add(category)
        elements.append(
            SocraticPromptElement(
                socratic_category=category,
                polya_stage=stage,
                hint_level=1,  # 가장 은근한 단계(답 미루기) — 장면 도입은 부드럽게
                prompt_text=EXAMPLE_QUESTION[
                    category
                ],  # 정본 유도 질문(자체 생성 아님)
            )
        )
    if not elements:
        category, stage = _DEFAULT_PROFILE.socratic
        elements.append(
            SocraticPromptElement(
                socratic_category=category,
                polya_stage=stage,
                hint_level=1,
                prompt_text=EXAMPLE_QUESTION[category],
            )
        )
    return elements


def _misconception_probes(
    learner_context: SceneLearnerContext | None,
) -> list[MisconceptionProbeElement]:
    """활성 오개념 가설 ∩ 카탈로그 → 프로브(적응·05a §5.3). 카탈로그 밖 id는 *조용히 제외*.

    RS2(거짓 낙인 차단): 프로브는 학습자의 *근거 있는* 활성 가설(`active_hypothesis_ids`)에서만
    나온다.

    **개입 다양화**(05a S5+ 잔여): `active_hypothesis_confidences`가 주어지면 가설별 *누적
    신뢰도*로 doc 결정트리(`select_intervention`·>0.8 반례·≥0.5 거꾸로·<0.5 보류)를 구동해
    개입 패턴을 고른다 — 신뢰도 <0.5 가설은 프로브를 *만들지 않는다*(보류·낙인 회피·재구현 0).
    신뢰도 맵 미제공(None) 또는 그 맵에 없는 id는 레거시 반례(`COUNTEREXAMPLE`)로 폴백한다.
    """
    if learner_context is None:
        return []
    confidences = learner_context.active_hypothesis_confidences
    probes: list[MisconceptionProbeElement] = []
    for mid in learner_context.active_hypothesis_ids:
        misconception = CATALOG_BY_ID.get(mid)
        if misconception is None:
            continue  # 카탈로그 밖 id(느슨) → 제외(RS2).
        if confidences is not None and mid in confidences:
            # 가설 신뢰도로 doc 결정트리 구동(재사용) — <0.5는 None(보류) → 프로브 미생성.
            decision = select_intervention(
                MisconceptionMatch(
                    misconception=misconception, confidence=confidences[mid]
                )
            )
            if decision is None:
                continue
            intervention = decision.pattern
        else:
            intervention = InterventionPattern.COUNTEREXAMPLE  # 레거시(신뢰도 미제공).
        probes.append(
            MisconceptionProbeElement(misconception_id=mid, intervention=intervention)
        )
    return probes


def _decide_layout(elements: list[SceneElement]) -> SceneLayout:
    """요소 구성 → 배치 힌트(결정론·픽셀 아님). 단일·시각+코칭 2분할·그 외 세로 적층."""
    if len(elements) <= 1:
        return SceneLayout.single
    has_visual = any(isinstance(el, VisualizationElement) for el in elements)
    return SceneLayout.two_panel if has_visual else SceneLayout.vertical_stack


async def generate_learning_scene(
    concept: Concept,
    level: str,
    req: RoutingRequest,
    *,
    provider: LLMProvider,
    cache: CacheBackend,
    trace: TraceSink,
    learner_context: SceneLearnerContext | None = None,
    answer_deferral_max_level: int = 4,
) -> LearningScene:
    """개념 노드 → 검증된 `LearningScene` 합성 명세(05a §5). 라우터 경유·결정론 골격.

    골격(코드 결정론): 주 행동영역(`_primary_cognitive_type`)의 **요소 조합 프로파일**(05a §5.1)이
    *인지 진입 순서*를 결정한다 — `visual` 진입(기법·패턴·시각추론)은 시각화 먼저, `inquiry` 진입
    (정의·정리)은 소크라테스(질문) 먼저. ① 시각화 블록: `recommended_visual_styles`가 있으면
    `visualization` 요소 1개(`generate_visualization_spec`·L3), 결과가 graph_2d이고
    파라미터를 선언하면 그를 타깃하는 `param_control`을 덧붙인다(bound index는 append 시점
    계산이라 진입 순서와 무관하게 정합). ② 소크라테스 블록: `cognitive_type` → 발화(프로파일
    소싱·정본 유도 질문·`hint_level=1`). ③ 활성 가설 ∩ 카탈로그 → `misconception_probe`
    (적응·낙인 금지·항상 본문 뒤). 반환 전 `LearningScene` 불변식(답 미루기·param/annotation 정합)을
    통과한다 — 검증 안 된 명세는 나가지 않는다(CLAUDE.md).

    LLM 호출은 시각화 spec 1회뿐(스타일 있을 때)·나머지는 결정론 — 환각 표면을 최소화한다(RS5).

    Args:
        concept: 장면이 가르치는 개념(L1). `code`=개념그래프 UC·`name_ko`=시각화 대상.
        level: 대상 수준 라벨(예: "고2") — `generate_visualization_spec`에 전달.
        req: 라우팅 입력(task_type="generate" 권장·sync 여부는 호출자). 동기 경로 전제.
        provider/cache/trace: L3 `pipeline.generate` DI(라우터·캐시·관측).
        learner_context: L2/WH-1 스냅샷(선택). 활성 가설이 있으면 프로브를 *적응적으로* 삽입.
        answer_deferral_max_level: 장면 힌트 상한(1~4·기본 4). 소크라테스 발화는 1단계라 항상 충족.

    Returns:
        불변식 통과한 `LearningScene`.

    Raises:
        InvalidVisualizationSpecError: 시각화 spec LLM 출력이 검증 게이트를 통과 못 함(전파).
    """
    profile = _profile_for(concept)
    elements: list[SceneElement] = []

    async def _append_visual_block() -> None:
        """시각화(+graph_2d면 param_control)를 공유 `elements`에 append.

        `bound_visualization_index`를 append 시점 `len(elements)`로 계산하므로, 소크라테스가 앞서
        진입(inquiry)해 viz가 뒤 인덱스에 놓여도 항상 정합한다(불변식 통과). 권장 양식 없으면 강제
        안 함(정직한 경계). LLM 호출은 여기 1회뿐(스타일 있을 때)·나머지는 결정론(RS5).
        """
        if not concept.recommended_visual_styles:
            return
        viz = await generate_visualization_spec(
            concept.name_ko,
            level,
            req,
            provider=provider,
            cache=cache,
            trace=trace,
            recommended_styles=concept.recommended_visual_styles,
        )
        viz_index = len(elements)
        elements.append(VisualizationElement(ref=viz))
        # graph_2d이고 파라미터를 선언했으면 그 파라미터를 조작하는 슬라이더를 결정론적으로 덧붙임
        if VisualizationType(viz.type) == VisualizationType.interactive_graph_2d:
            params = Graph2dSpec.model_validate(viz.spec).parameters or []
            declared = [p.name for p in params if p.name]
            if declared:
                elements.append(
                    ParamControlElement(
                        targets=declared, bound_visualization_index=viz_index
                    )
                )

    # 행동영역(주 cognitive_type) 프로파일이 *인지 진입 순서*를 결정한다(05a §5.1).
    # visual → 시각화 먼저(보고→추론) · inquiry → 소크라테스(질문) 먼저(질문→확인).
    if profile.lead == "visual":
        await _append_visual_block()
        elements.extend(_socratic_elements(concept))
    else:  # "inquiry"
        elements.extend(_socratic_elements(concept))
        await _append_visual_block()

    # ③ 오개념 프로브(적응·reactive) — 항상 본문 뒤
    elements.extend(_misconception_probes(learner_context))

    # 조립 + 불변식 통과(미통과 명세는 반환 안 됨). misconception_id는 카탈로그로 사전 필터됨.
    return LearningScene(
        concept_id=concept.code,
        topic_label=concept.name_ko,
        layout=_decide_layout(elements),
        answer_deferral_max_level=answer_deferral_max_level,
        learner_context=learner_context,
        elements=elements,
    )
