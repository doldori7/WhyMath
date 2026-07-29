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
    생성(RS2 거짓 낙인 차단). 개념의 자유서술 오개념(`common_misconceptions`)은 Phase 1b로 런타임
    Concept에서 제거돼(컬럼 부재) 애초에 프로브 근거가 될 수 없다(낙인·즉답 구조적 차단).

범위(S3): 골격 + spec 충전 + 게이트 통과 명세 반환. `concept_id`는 `Concept.code`(개념그래프 UC).
개념그래프 *존재* 검증(DB)·다중 시각화·L5 렌더러는 S4+.

step_panel 결선(S4-09·D1 reader ②): SolutionPath가 실체화되어(`l3/solution_path.py`·
`solution_paths` 테이블·WH-S 승격 어댑터) `StepPanelElement.solution_path_id` 댕글링이
해소됐다 — `find_step_panel_solution_path_id`(아래)가 문제의 승격 경로 id를 조회한다(L4→L3
다운콜). 단, 장면 골격에 step_panel을 **자동 삽입하지는 않는다** — 신규 학생 대면 노출 0
(S4-09 경계·기존 표면 소생만). 장면 내 step_panel 배치는 검증 풀이 노출 정책과 함께 후속
(`solution_module_gap_review.md` §4-⑥ "본인 풀이 후 대안 노출" 원칙).
"""

from __future__ import annotations

import uuid
from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from whymath_backend.l3.interfaces import CacheBackend, LLMProvider, TraceSink
from whymath_backend.l3.models import RoutingRequest
from whymath_backend.l3.solution_path_store import find_solution_path_id
from whymath_backend.l3.visualization import generate_visualization_spec
from whymath_backend.l4.learning_scene import (
    LearningScene,
    MisconceptionProbeElement,
    ParamControlElement,
    SceneElement,
    SceneLayout,
    SceneLearnerContext,
    SkillFocusElement,
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
from whymath_backend.l4.visualization_policy import is_visualizable, prefers_static_visual
from whymath_backend.schema.concept import Concept
from whymath_backend.schema.enums import (
    BehaviorArea,
    CognitiveType,
    Visualizability,
    VisualizationType,
)
from whymath_backend.schema.visualization import Graph2dSpec

# ── 개념 축(CognitiveType·개념 성격) → 소크라테스 (카테고리, Polya 단계). BehaviorArea와 직교.
# 개념의 *성격*에 맞는 메타인지 발화를 코드가 고른다(LLM 추측 아님). 정답이 아니라 유도 질문.
_COGNITIVE_SOCRATIC_MAP: dict[CognitiveType, tuple[SocraticCategory, PolyaStage]] = {
    CognitiveType.DEFINITION: (SocraticCategory.CLARIFICATION, PolyaStage.UNDERSTAND),
    CognitiveType.THEOREM: (SocraticCategory.EVIDENCE, PolyaStage.PLAN),
    CognitiveType.TECHNIQUE: (SocraticCategory.PERSPECTIVE, PolyaStage.PLAN),
    CognitiveType.PATTERN: (SocraticCategory.IMPLICATION, PolyaStage.EXECUTE),
    CognitiveType.VISUAL_REASONING: (SocraticCategory.ASSUMPTION, PolyaStage.UNDERSTAND),
}
# 인지 유형이 없을 때의 기본 메타인지 발화 — 장면은 최소 한 개의 유도 질문(CLAUDE.md 메타인지 중심).
_DEFAULT_SOCRATIC: tuple[SocraticCategory, PolyaStage] = (
    SocraticCategory.META,
    PolyaStage.REVIEW,
)

# ── 행동영역 축(BehaviorArea·정본 6종·#418) — 개념과 직교. 인지 진입 순서(lead) + 가시 focus 블록.
# S5i/S5j를 정본 행동영역 축으로 재정렬(S5k). 이전엔 CognitiveType으로 근사했으나 #418이 정본
# `BehaviorArea`(SkillNode)를, #419가 concept→skill 매핑(`concept_node.behavior_skills`)을 도입했다.
# 행동영역은 개념→skill 조인으로 해소돼(L5 `get_behavior_areas`) 생성기에 주입(미매핑=중립).

# 행동영역 → 진입 순서: 표상/변형/계산=시각 진입(그림 먼저)·해석/추론/검증=탐구(질문 먼저).
_LEAD_BY_BEHAVIOR: dict[BehaviorArea, Literal["visual", "inquiry"]] = {
    BehaviorArea.COMPUTE: "visual",
    BehaviorArea.TRANSFORM: "visual",
    BehaviorArea.REPRESENT: "visual",
    BehaviorArea.INTERPRET: "inquiry",
    BehaviorArea.REASON: "inquiry",
    BehaviorArea.VERIFY: "inquiry",
}
# 미매핑(behavior_area 없음) 개념은 탐구(질문) 진입 기본값.
_DEFAULT_LEAD: Literal["visual", "inquiry"] = "inquiry"

# 다중 skill(행동영역)일 때 *주 행동영역* precedence(결정론). 값이 작을수록 우선.
_BEHAVIOR_PRECEDENCE: dict[BehaviorArea, int] = {
    BehaviorArea.REPRESENT: 0,
    BehaviorArea.TRANSFORM: 1,
    BehaviorArea.COMPUTE: 2,
    BehaviorArea.INTERPRET: 3,
    BehaviorArea.REASON: 4,
    BehaviorArea.VERIFY: 5,
}

# 행동영역별 *가시 focus 블록* 정본 지시 — 05a §3.2 SkillFocus. 정답·질문 아니라 *어떤 인지 행동을
# 하라*는 선언적 지시(EXAMPLE_QUESTION 드리프트 제어 답습). 6종 폐쇄 — 미매핑 행동영역은 미부여.
_SKILL_FOCUS_CUE: dict[BehaviorArea, str] = {
    BehaviorArea.COMPUTE: "연산 규칙과 순서를 정확히 적용해 단계적으로 계산하세요.",
    BehaviorArea.TRANSFORM: "식을 바꾸기 전에 어떤 등가 변형 규칙을 쓰는지 확인하세요.",
    BehaviorArea.INTERPRET: "주어진 조건을 먼저 수학 구조(식·관계)로 해석하세요.",
    BehaviorArea.REPRESENT: "같은 대상을 그래프·식·표 등 다른 표현으로 바꿔 살펴보세요.",
    BehaviorArea.REASON: "결론으로 가는 논리적 근거를 한 단계씩 전개하세요.",
    BehaviorArea.VERIFY: "결과가 조건을 만족하는지 반례·특수값으로 점검하세요.",
}


def _primary_behavior_area(
    behavior_areas: list[BehaviorArea] | None,
) -> BehaviorArea | None:
    """다중 행동영역에서 *주 행동영역*을 결정론적으로 고른다(precedence 최소값). 없으면 None."""
    if not behavior_areas:
        return None
    return min(behavior_areas, key=lambda a: _BEHAVIOR_PRECEDENCE[a])


def _lead_for(behavior_areas: list[BehaviorArea] | None) -> Literal["visual", "inquiry"]:
    """주 행동영역 → 인지 진입 순서(미매핑이면 기본 탐구 진입)."""
    primary = _primary_behavior_area(behavior_areas)
    return _LEAD_BY_BEHAVIOR[primary] if primary is not None else _DEFAULT_LEAD


def _skill_focus_element(
    behavior_areas: list[BehaviorArea] | None,
) -> SkillFocusElement | None:
    """주 행동영역이 있으면 그 행동영역의 focus 블록 1개. 미매핑이면 None.

    행동영역이 *블록의 유무·내용*을 자동 분기한다(체크리스트 ② "9블록이 행동영역에 따라 자동 분기").
    """
    primary = _primary_behavior_area(behavior_areas)
    if primary is None:
        return None
    return SkillFocusElement(behavior_area=primary, focus_prompt=_SKILL_FOCUS_CUE[primary])


def _socratic_elements(concept: Concept) -> list[SocraticPromptElement]:
    """개념 `cognitive_type` → 소크라테스 발화 요소(결정론·중복 카테고리 제거)."""
    elements: list[SocraticPromptElement] = []
    seen: set[SocraticCategory] = set()
    # use_enum_values=True라 concept.cognitive_type 원소는 런타임 str → CognitiveType로 정규화.
    for raw in concept.cognitive_type:
        category, stage = _COGNITIVE_SOCRATIC_MAP[CognitiveType(raw)]
        if category in seen:
            continue
        seen.add(category)
        elements.append(
            SocraticPromptElement(
                socratic_category=category,
                polya_stage=stage,
                hint_level=1,  # 가장 은근한 단계(답 미루기) — 장면 도입은 부드럽게
                prompt_text=EXAMPLE_QUESTION[category],  # 정본 유도 질문(자체 생성 아님)
            )
        )
    if not elements:
        category, stage = _DEFAULT_SOCRATIC
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
                MisconceptionMatch(misconception=misconception, confidence=confidences[mid])
            )
            if decision is None:
                continue
            intervention = decision.pattern
        else:
            intervention = InterventionPattern.COUNTEREXAMPLE  # 레거시(신뢰도 미제공).
        probes.append(MisconceptionProbeElement(misconception_id=mid, intervention=intervention))
    return probes


def _decide_layout(elements: list[SceneElement]) -> SceneLayout:
    """요소 구성 → 배치 힌트(결정론·픽셀 아님). 단일·시각+코칭 2분할·그 외 세로 적층."""
    if len(elements) <= 1:
        return SceneLayout.single
    has_visual = any(isinstance(el, VisualizationElement) for el in elements)
    return SceneLayout.two_panel if has_visual else SceneLayout.vertical_stack


async def find_step_panel_solution_path_id(
    session: AsyncSession, problem_id: uuid.UUID
) -> str | None:
    """문제에 승격된 SolutionPath가 있으면 그 id — `StepPanelElement.solution_path_id` 결선.

    S4-09(D1) reader ② 최소 결선(조회 헬퍼 수준): L3 store(`find_solution_path_id`)를
    다운콜해 실재하는 경로 id를 돌려준다 — 이 id로 만든 `StepPanelElement`는 더 이상 댕글링
    참조가 아니다. 없으면 None(step_panel을 만들 근거 없음 — 날조 금지).

    경계(학생 대면 신규 노출 0): 본 헬퍼는 *조회만* 한다 — `generate_learning_scene` 골격에
    step_panel을 자동 삽입하지 않고(코치 경로도 무변경), `StepPanelElement.reveal_policy`는
    `"deferred"` 불변이다(답 미루기 스키마 강제). 장면 내 배치는 후속(모듈 docstring).
    """
    return await find_solution_path_id(session, problem_id)


async def generate_learning_scene(
    concept: Concept,
    level: str,
    req: RoutingRequest,
    *,
    provider: LLMProvider,
    cache: CacheBackend,
    trace: TraceSink,
    learner_context: SceneLearnerContext | None = None,
    visualizability: Visualizability | None = None,
    behavior_areas: list[BehaviorArea] | None = None,
    answer_deferral_max_level: int = 4,
) -> LearningScene:
    """개념 노드 → 검증된 `LearningScene` 합성 명세(05a §5). 라우터 경유·결정론 골격.

    골격(코드 결정론): **행동영역(BehaviorArea·정본 6종)**이 *인지 진입 순서*를 결정한다(S5k) —
    표상/변형/계산은 시각화 먼저, 해석/추론/검증은 질문 먼저. 개념과 직교하므로 소크라테스
    프레이밍은 개념 축(`cognitive_type`)이 계속 담당한다. ⓪ 행동영역 focus: 주 행동영역이 있으면
    그 행동영역의 `skill_focus`를 맨 앞에 둔다(미매핑=미부여·05a §3.2). ① 시각화 블록:
    `recommended_visual_styles`가 있고 `visualizability`가 허용할 때만 `visualization`(+graph_2d·
    비정적이면 `param_control`)을 붙인다(bound index는 append 시점 계산이라 진입 순서와 무관 정합).
    ② 소크라테스 블록: `cognitive_type` → 발화(정본 유도 질문). ③ 활성 가설 ∩ 카탈로그
    → `misconception_probe`(적응·낙인 금지·항상 본문 뒤). 반환 전 `LearningScene` 불변식(답 미루기·
    param/annotation 정합)을 통과한다 — 검증 안 된 명세는 나가지 않는다(CLAUDE.md).

    LLM 호출은 시각화 spec 1회뿐(스타일 있을 때)·나머지는 결정론 — 환각 표면을 최소화한다(RS5).

    Args:
        concept: 장면이 가르치는 개념(L1). `code`=개념그래프 UC·`name_ko`=시각화 대상.
        level: 대상 수준 라벨(예: "고2") — `generate_visualization_spec`에 전달.
        req: 라우팅 입력(task_type="generate" 권장·sync 여부는 호출자). 동기 경로 전제.
        provider/cache/trace: L3 `pipeline.generate` DI(라우터·캐시·관측).
        learner_context: L2/WH-1 스냅샷(선택). 활성 가설이 있으면 프로브를 *적응적으로* 삽입.
        visualizability: 시각화 가능성 4분류(L1·05b). 추상/불가면 시각화 생략(억지 그림 방지).
        behavior_areas: 개념의 행동영역 목록(L5 `get_behavior_areas`가 concept→skill 조인으로 해소).
            진입 순서·focus 블록을 결정. 미매핑(빈 목록/None)이면 중립(탐구 진입·focus 0).
        answer_deferral_max_level: 장면 힌트 상한(1~4·기본 4). 소크라테스 발화는 1단계라 항상 충족.

    Returns:
        불변식 통과한 `LearningScene`.

    Raises:
        InvalidVisualizationSpecError: 시각화 spec LLM 출력이 검증 게이트를 통과 못 함(전파).
    """
    lead = _lead_for(behavior_areas)
    elements: list[SceneElement] = []

    # ⓪ 행동영역 focus(있으면 맨 앞·프레이밍) — 주 행동영역별 자동 분기(미매핑=미부여).
    # 정답 아님·소크라테스 질문과 구분되는 *행동 지시*(05a §3.2·S5k).
    skill_focus = _skill_focus_element(behavior_areas)
    if skill_focus is not None:
        elements.append(skill_focus)

    async def _append_visual_block() -> None:
        """시각화(+graph_2d면 param_control)를 공유 `elements`에 append.

        권장 양식이 있고 `visualizability`가 허용할 때만(추상·불가면 억지 그림 대신 폴백·05b Part 5
        게이트·CLAUDE.md 교수학 정확성). `bound_visualization_index`를 append 시점 `len(elements)`로
        계산하므로, 소크라테스가 앞서(inquiry) viz가 뒤 인덱스여도 정합(불변식 통과). LLM 호출은
        여기 1회뿐(스타일 있을 때).
        """
        if not (concept.recommended_visual_styles and is_visualizable(visualizability)):
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
        # graph_2d이고 파라미터를 선언했으면 슬라이더를 덧붙이되, *직접(정적 충분)* 개념은 조작이
        # 인지 조건이 아니므로 슬라이더를 생략한다(동적·미태깅은 허용) — 직접/동적 구분을 반영(05b).
        if VisualizationType(
            viz.type
        ) == VisualizationType.interactive_graph_2d and not prefers_static_visual(visualizability):
            params = Graph2dSpec.model_validate(viz.spec).parameters or []
            declared = [p.name for p in params if p.name]
            if declared:
                elements.append(
                    ParamControlElement(targets=declared, bound_visualization_index=viz_index)
                )

    # 행동영역(BehaviorArea)이 *인지 진입 순서*를 결정한다(S5k).
    # visual → 시각화 먼저(보고→추론) · inquiry → 소크라테스(질문) 먼저(질문→확인).
    if lead == "visual":
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
