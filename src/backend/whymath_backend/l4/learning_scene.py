"""L4 LearningScene DSL — 단일 시각화 위 합성 장면 명세 + 검증 게이트. S2.

설계 정본: `docs/architecture/05a_learning_scene_dsl.md` §3(스키마)·§4(게이트). `Visualization`
(단일 시각화·S1 typed spec) **위에** 그래프·슬라이더·풀이단계·오개념 프로브·소크라테스 발화를
*한 장면*으로 조립하는 선언적 합성 계층이다. 개념(L1)·학습자상태(L2)·오개념/Polya(L4)로부터
*구조(JSON/AST)*를 만들고, L5가 *수학 로직 없이* 렌더한다(슬라이스 89 표현≠의미).

7계층 배치(왜 L4): LearningScene은 schema의 `Visualization`·`Graph2dSpec`·`VisualizationType`
**+ L4**의 `InterventionPattern`·`SocraticCategory`·`PolyaStage`·`CATALOG_BY_ID`를 *조립*한다.
schema는 L레이어 import가 0(역방향 의존 금지)이라 scene을 schema에 두면 위반 → L4(장면 조립·검증)가
정확한 좌석. 상위(L4)→하위(schema) 호출만 한다.

교수학 안전을 *스키마 불변식*으로 강제(05a §2·§4 — 외부 문서의 `warning_overlay`(붉은 강조·정답
자동 생성)를 교정해 수용):
  - 답 미루기: `socratic_prompt.hint_level ≤ answer_deferral_max_level`(불변식 ①).
  - 낙인·즉답 금지: `misconception_probe`는 *정답·수정 필드가 없다*(extra=forbid가 구조 차단) —
    반례/시각화 *유도*만(L4 InterventionPattern). `step_panel.reveal_policy="deferred"`(점층 노출).
  - 검증 게이트: `parse_learning_scene`이 참조 무결성(오개념 카탈로그)·불변식 통과한 명세만 반환
    (CLAUDE.md "LLM 응답을 검증 없이 학생에게 제공 금지").

범위(S2): 합성 스키마 + 검증 게이트만. `concept_id`의 개념그래프 존재 확인은 *DB 필요*라 S3로
연기(여기선 미수행·정직 명시). L3 `generate_learning_scene`(골격 결정론)·L5 `SceneRenderer`는 S3·S4.
"""

from __future__ import annotations

import json
from enum import Enum
from typing import Annotated, Any, Literal, Union
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from whymath_backend.l4.misconception.catalog import CATALOG_BY_ID
from whymath_backend.l4.misconception.models import InterventionPattern
from whymath_backend.l4.models import PolyaStage
from whymath_backend.l4.socratic.categories import SocraticCategory
from whymath_backend.schema.enums import CognitiveType, VisualizationType
from whymath_backend.schema.visualization import Graph2dSpec, Visualization


# ──────────────────────────────────────────────────────────────────────────
# 배치·학습자 컨텍스트
# ──────────────────────────────────────────────────────────────────────────
class SceneLayout(str, Enum):
    """장면 배치 힌트 — 선언적(픽셀 아님·L5가 해석). 05a §3.1."""

    single = "single"  # 단일 요소
    vertical_stack = "vertical_stack"  # 세로 적층
    two_panel = "two_panel"  # 2분할(예: 그래프 | 풀이)
    tabbed = "tabbed"  # 탭 전환


class SceneLearnerContext(BaseModel):
    """생성 시점 학습자 스냅샷 — *판정이 아니라 장면 적응의 입력*(05a §3.1).

    "틀렸다" 단정 근거가 아니다(CLAUDE.md 낙인 금지). `active_hypothesis_ids`는 WH-1 활성
    오개념 가설 id(근거 있는 프로브에만 쓰임). 전부 선택(없으면 비적응 장면).
    """

    model_config = ConfigDict(extra="forbid")

    mastery_level: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="L2 BKT 숙달레벨(0~1). 스냅샷·판정 아님.",
    )
    active_hypothesis_ids: list[str] = Field(
        default_factory=list,
        description="WH-1 활성 오개념 가설 id(`misconception_hypothesis`). 근거 있는 프로브 한정.",
    )
    active_hypothesis_confidences: dict[str, float] | None = Field(
        default=None,
        description=(
            "WH-1 활성 가설의 *누적 신뢰도* 맵(id→confidence·0~1). 주어지면 프로브 개입 패턴을 "
            "doc 결정트리(`intervene.select_intervention`·>0.8 반례·≥0.5 거꾸로·<0.5 보류)로 "
            "*가설별* 선택해 다양화한다(<0.5는 프로브 미생성·낙인 회피). None(기본)이면 "
            "`active_hypothesis_ids` 전부 반례(`COUNTEREXAMPLE`) 레거시 동작."
        ),
    )
    theta: float | None = Field(default=None, description="L2 IRT 능력 추정치. 스냅샷.")


# ──────────────────────────────────────────────────────────────────────────
# SceneElement — kind 판별 유니온 6종(각 변형은 *기존 좌석*을 참조·신규 엔진 0)
# ──────────────────────────────────────────────────────────────────────────
class _ElementBase(BaseModel):
    """장면 요소 공통 베이스 — extra=forbid(미지 필드·정답 밀반입 차단)·enum 값 직렬화."""

    model_config = ConfigDict(extra="forbid", use_enum_values=True)


class VisualizationElement(_ElementBase):
    """단일 시각화 요소 — 기존 `Visualization` 명세(S1 typed spec)를 *참조*. 검증 상속."""

    kind: Literal["visualization"] = "visualization"
    ref: Visualization = Field(description="조립할 단일 시각화 명세(05 §5.2·S1).")


class ParamControlElement(_ElementBase):
    """파라미터 컨트롤(슬라이더) — bound 시각화의 선언 파라미터를 학생이 조작.

    `bound_visualization_index`는 같은 elements 안의 `visualization` 요소를 가리키고,
    `targets`는 그 graph_2d spec이 *선언한* 파라미터 이름의 부분집합이어야 한다(불변식 ②).
    """

    kind: Literal["param_control"] = "param_control"
    targets: list[str] = Field(
        min_length=1,
        description="조작 대상 파라미터 이름(≥1) — bound graph_2d spec의 선언 파라미터.",
    )
    bound_visualization_index: int = Field(
        ge=0, description="조작 대상 `visualization` 요소의 elements 인덱스."
    )
    value_range: list[float] | None = Field(
        default=None, description="슬라이더 범위 [min, max](선택·UI 힌트)."
    )
    step: float | None = Field(default=None, description="슬라이더 증분(선택·UI 힌트).")


class StepPanelElement(_ElementBase):
    """풀이 단계 패널 — `SolutionPath`(검증 풀이) 참조. *점층 노출*(답 미루기).

    `reveal_policy`는 `"deferred"` 한 값만 허용(스키마 차원 답 미루기 강제) — 한 번에 전체
    풀이를 노출하는 정책을 *담을 수 없다*(05a §2·§4 답 미루기).
    """

    kind: Literal["step_panel"] = "step_panel"
    solution_path_id: str = Field(
        description="참조할 검증 풀이 경로 id(`SolutionPath`)."
    )
    reveal_policy: Literal["deferred"] = Field(
        default="deferred", description="점층 노출만 허용(답 미루기·다른 값 불가)."
    )


class MisconceptionProbeElement(_ElementBase):
    """오개념 프로브 — 카탈로그 오개념 + 개입 패턴(반례/구체사례/시각화/거꾸로).

    ★*정답·수정 필드가 없다*(extra=forbid가 구조 차단) — 이것은 **가설·소크라테스 트리거이지
    판정이 아니다**(05a §4·CLAUDE.md 낙인/즉답 금지). `intervention`은 *수정법이 아니라 사고 유도*.
    `correction`·`answer` 같은 필드를 밀어 넣으면 ValidationError(불변식의 스키마 차원 강제).
    """

    kind: Literal["misconception_probe"] = "misconception_probe"
    misconception_id: str = Field(
        description="오개념 카탈로그 id(`CATALOG_BY_ID` 참조·게이트가 무결성 검증)."
    )
    intervention: InterventionPattern = Field(
        description="개입 패턴 4종(반례/구체사례/시각화/거꾸로) — 사고 유도·수정법 아님."
    )


class SocraticPromptElement(_ElementBase):
    """소크라테스 발화 — 6카테고리 × Polya 단계 × 힌트 단계(답 미루기).

    `hint_level`은 `answer_deferral_max_level`을 넘을 수 없다(불변식 ① 답 미루기).
    """

    kind: Literal["socratic_prompt"] = "socratic_prompt"
    socratic_category: SocraticCategory = Field(description="소크라테스 6카테고리(L4).")
    polya_stage: PolyaStage = Field(description="Polya 4단계.")
    hint_level: int = Field(
        ge=1,
        le=4,
        description="답 미루기 단계(1=은근, 4=전체). ≤ answer_deferral_max_level.",
    )
    prompt_text: str = Field(description="학생에게 던질 발화(정답 아님·유도 질문).")


class AnnotationElement(_ElementBase):
    """주석·강조 오버레이 — 다른 요소를 강조/라벨링. 대상은 *자기 외* 유효 인덱스(불변식 ③)."""

    kind: Literal["annotation"] = "annotation"
    target_element_index: int = Field(
        ge=0, description="강조 대상 요소의 elements 인덱스(자기 제외)."
    )
    highlight_spec: dict[str, Any] = Field(
        default_factory=dict, description="강조/라벨 선언 명세(렌더는 L5). 자유 JSON."
    )


class SkillFocusElement(_ElementBase):
    """행동영역 focus 블록 — 개념의 *행동영역*(cognitive_type)이 요구하는 인지 행동을 드러낸다.

    관점 문서의 SkillBlock("조건 강조") 선언적 형태 — S5i 요소 조합 프로파일이 *어느 행동영역에서
    이 블록을 낼지 자동 분기*(THEOREM/TECHNIQUE/PATTERN)한다. `focus_prompt`는 *행동 focus 지시*
    (정본·질문 아님·**정답 아님**) — `misconception_probe`처럼 정답/수정 필드 부재(extra=forbid가
    구조 차단·answer-deferral·낙인 금지). interactive 경우분할 트리는 WH-S Tier3 종속(초기 제외).
    """

    kind: Literal["skill_focus"] = "skill_focus"
    cognitive_type: CognitiveType = Field(
        description="이 블록이 드러내는 행동영역(개념 cognitive_type·S5i 축 참조)."
    )
    focus_prompt: str = Field(
        min_length=1, description="선언적 행동 focus 지시(정본·정답/질문 아님)."
    )


SceneElement = Annotated[
    Union[
        VisualizationElement,
        ParamControlElement,
        StepPanelElement,
        MisconceptionProbeElement,
        SocraticPromptElement,
        AnnotationElement,
        SkillFocusElement,
    ],
    Field(discriminator="kind"),
]
"""장면 요소 7종 판별 유니온 — `kind`로 변형 선택(05a §3.2)."""


# ──────────────────────────────────────────────────────────────────────────
# LearningScene — 합성 장면 명세(구조/JSON·화면 픽셀 아님)
# ──────────────────────────────────────────────────────────────────────────
class LearningScene(BaseModel):
    """학습 장면 한 장의 선언적 합성 명세 — 05a §3.1.

    개념(`concept_id`)을 가르치는 요소들의 조립이며, 3 불변식(`@model_validator`)으로 교수학
    안전을 강제한다 — ① 답 미루기(hint_level 상한) ② param_control 정합 ③ annotation 정합.
    화면 픽셀이 아니라 *명세*다(슬라이스 89) — 같은 명세를 Flutter·웹·PDF·AI가 각자 렌더.
    """

    model_config = ConfigDict(extra="forbid", use_enum_values=True)

    scene_id: UUID = Field(default_factory=uuid4, description="장면 PK(UUID).")
    concept_id: str = Field(
        description="이 장면이 가르치는 개념 code(UC·L1). *그래프 존재 확인은 S3*(DB 필요)."
    )
    topic_label: str | None = Field(
        default=None, description="다국어 캡션·라벨(표현 레이어·의미 아님)."
    )
    layout: SceneLayout = Field(description="선언적 배치 힌트(픽셀 아님·L5 해석).")
    answer_deferral_max_level: int = Field(
        ge=1,
        le=4,
        description="장면이 허용하는 최대 힌트 단계(답 미루기 상한·불변식 ①).",
    )
    learner_context: SceneLearnerContext | None = Field(
        default=None, description="생성 시점 학습자 스냅샷(읽기전용·판정 아님)."
    )
    elements: list[SceneElement] = Field(
        description="합성 요소(순서 = 렌더/레이아웃 순서)."
    )

    @model_validator(mode="after")
    def _validate_invariants(self) -> LearningScene:
        """3 구조 불변식(05a §4). 위반은 ValueError → 게이트가 LearningSceneValidationError 래핑."""
        n = len(self.elements)
        graph2d = VisualizationType.interactive_graph_2d

        for idx, el in enumerate(self.elements):
            # ① 답 미루기 — 소크라테스 힌트 단계 ≤ 장면 상한
            if isinstance(el, SocraticPromptElement):
                if el.hint_level > self.answer_deferral_max_level:
                    raise ValueError(
                        f"socratic_prompt[{idx}] hint_level={el.hint_level} > "
                        f"max_level={self.answer_deferral_max_level} (답 미루기)"
                    )

            # ② param_control 정합 — bound가 범위 내 visualization, targets ⊆ 선언 파라미터
            elif isinstance(el, ParamControlElement):
                j = el.bound_visualization_index
                bound = self.elements[j] if 0 <= j < n else None
                # 변수 바인딩으로 타입 좁힘(mypy) — 재인덱싱 금지
                if not isinstance(bound, VisualizationElement):
                    raise ValueError(
                        f"param_control[{idx}].bound_visualization_index={j}가 "
                        "범위 내 visualization 요소를 가리키지 않는다"
                    )
                viz = bound.ref
                # 보수적(false reject 0): graph_2d가 아니거나 파라미터 미선언이면 멤버십 검증 생략.
                # graph_2d spec은 ref 생성 시 S1 게이트가 이미 검증 → 재파싱 성공 보장.
                if VisualizationType(viz.type) == graph2d:
                    declared = {
                        p.name
                        for p in (Graph2dSpec.model_validate(viz.spec).parameters or [])
                        if p.name
                    }
                    if declared:
                        unknown = [t for t in el.targets if t not in declared]
                        if unknown:
                            raise ValueError(
                                f"param_control[{idx}].targets {unknown}가 bound graph_2d spec의 "
                                f"선언 파라미터 {sorted(declared)}에 없다"
                            )

            # ③ annotation 정합 — 자기 외 유효 인덱스
            elif isinstance(el, AnnotationElement):
                t = el.target_element_index
                if not (0 <= t < n) or t == idx:
                    raise ValueError(
                        f"annotation[{idx}].target_element_index={t}가 자기 외 유효 인덱스가 아니다"
                    )

        return self


# ──────────────────────────────────────────────────────────────────────────
# 검증 게이트 — parse_learning_scene (05a §4)
# ──────────────────────────────────────────────────────────────────────────
class LearningSceneValidationError(ValueError):
    """LearningScene 명세가 유효하지 않음 — 파싱 실패·스키마/불변식 위반·참조 무결성 위반.

    검증 게이트가 *검증 안 된 명세*를 학생에게 통과시키지 않기 위해 던진다(CLAUDE.md "LLM 응답을
    검증 없이 제공 금지"·05a §4). `l3.visualization.InvalidVisualizationSpecError` 미러.
    """


def parse_learning_scene(data: dict[str, Any] | str) -> LearningScene:
    """LearningScene 명세(dict 또는 JSON 문자열) → 검증된 `LearningScene` (검증 게이트).

    05a §4 게이트: ① JSON 파싱(str일 때) ② 스키마·구조 불변식(`LearningScene.model_validate` —
    답 미루기·param_control·annotation 불변식 포함) ③ 참조 무결성(`misconception_id ∈
    CATALOG_BY_ID`). 통과 못 하면 `LearningSceneValidationError`(학생 미노출).

    ★범위(S2): `concept_id`의 개념그래프 존재 확인은 *DB 필요*라 **여기서 수행하지 않는다**(S3로
    연기) — 카탈로그 참조 무결성만 인메모리로 검증한다(정직한 경계).
    """
    if isinstance(data, str):
        try:
            payload = json.loads(data)
        except json.JSONDecodeError as exc:
            raise LearningSceneValidationError(f"JSON 파싱 실패: {exc}") from exc
    else:
        payload = data

    try:
        scene = LearningScene.model_validate(payload)
    except ValidationError as exc:
        raise LearningSceneValidationError(
            f"LearningScene 스키마/불변식 위반: {exc}"
        ) from exc

    # 참조 무결성 — 오개념 카탈로그(30종). concept_id 개념그래프 검증은 S3(DB 필요).
    for idx, el in enumerate(scene.elements):
        if (
            isinstance(el, MisconceptionProbeElement)
            and el.misconception_id not in CATALOG_BY_ID
        ):
            raise LearningSceneValidationError(
                f"elements[{idx}].misconception_id='{el.misconception_id}'가 오개념 카탈로그에 없다"
            )

    return scene
