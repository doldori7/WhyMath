"""거버넌스 동결 — 시각화 5상태 분리 + Renderer 독립 + 단방향 의존(구축 플레이북 Part 5).

플레이북 Part 5 법칙 세 가지를 코드로 동결한다(`test_embedding_namespace_governance.py`·
`test_concept.py::TestConceptNodeFieldGovernance` 선례 — 원칙을 CI로 강제해 조용한 침식을 차단):

  ① **5상태 분리(Math/Pedagogy/Interaction/Animation/UI)**: 코어 시각화·장면 명세(Math·Pedagogy
     상태)에 Interaction/Animation/UI *런타임* 상태(픽셀·위젯·재생·선택·호버 등)가 새어들지
     않는다 — `Visualization.spec`은 stateless 구조(JSON)이고, 명세 필드는 선언적 힌트뿐이다.
  ② **Renderer 독립(Concept→Intent→Adapter)**: `VisualizationType`의 *값*은 렌더 *의도*
     (interactive_graph_2d 등)이지 구현체 이름(Desmos·three.js·WebGL·Canvas·Manim)이 아니다 —
     구현체명은 `data/render_contract.json`·L5 어댑터에만 산다.
  ③ **단방향 의존(Math→…→UI)**은 여기서 재구현하지 않는다 — 레포의 import-linter 7계층 layers
     계약(`pyproject [tool.importlinter]`·`lint-imports` CI 잡)이 `schema<l4<api` 방향을 이미
     강제한다(자작 소스스캔 중복 제거). 본 파일은 계약이 못 잡는 *모델 필드·enum 값* 불변만 동결.

hermetic: DB 불요(Pydantic 모델 메타데이터·enum 값·소스 스캔만). 설계 정본:
`docs/architecture/05b_visualization_classification.md`.
"""

from __future__ import annotations

from pydantic import BaseModel

from whymath_backend.l4.learning_scene import (
    AnnotationElement,
    LearningScene,
    MisconceptionProbeElement,
    ParamControlElement,
    SceneLearnerContext,
    SocraticPromptElement,
    StepPanelElement,
    VisualizationElement,
)
from whymath_backend.schema.enums import VisualizationType
from whymath_backend.schema.visualization import Visualization

# Math·Pedagogy 명세에 새어들면 안 되는 *런타임/UI 상태* 부분문자열(소문자 비교). 선언적 힌트
# (value_range·step·highlight_spec·bound_*·target_*)는 상태가 아니므로 제외한다 — 여기 있는 건
# "지금 화면이 어떤 상태인가"(가변 런타임)에 해당하는 것들이다. 하나라도 필드명에 박히면 red.
_RUNTIME_STATE_SUBSTRINGS: tuple[str, ...] = (
    "current_",
    "selected",
    "hover",
    "drag",
    "scroll",
    "viewport",
    "pixel",
    "canvas",
    "webgl",
    "widget",
    "playback",
    "is_playing",
    "frame_index",
    "mouse",
    "session_id",
    "user_id",
    "dom_",
)

# 렌더러 *구현체* 이름 — 노드/명세/Intent enum에 있으면 안 된다(render_contract·L5에만).
_RENDERER_IMPL_NAMES: tuple[str, ...] = (
    "desmos",
    "geogebra",
    "three.js",
    "threejs",
    "webgl",
    "canvas",
    "d3",
    "plotly",
    "manim",
    "mathlive",
)

# Math(시각화)·Pedagogy(장면) 상태를 담는 코어 모델 — 이 집합에 런타임/UI 상태 금지.
_STATE_MODELS: tuple[type[BaseModel], ...] = (
    Visualization,
    LearningScene,
    SceneLearnerContext,
    VisualizationElement,
    ParamControlElement,
    StepPanelElement,
    MisconceptionProbeElement,
    SocraticPromptElement,
    AnnotationElement,
)


# ── ① Math 상태 statelessness ────────────────────────────────────────────────
class TestMathStateStateless:
    def test_visualization_field_set_frozen(self) -> None:
        """`Visualization` 필드 동결 — 렌더/런타임 상태 필드 추가를 의식적으로 강제.

        실패하면 추가 필드가 *선언적 명세*(Math)인지 *런타임 상태*(Interaction/Animation/UI)인지
        판단하라. 후자면 명세가 아니라 클라 런타임에 둬야 한다(표현≠의미·슬89).
        """
        assert set(Visualization.model_fields) == {
            "visualization_id",
            "type",
            "spec",
            "caption",
            "interactive",
        }

    def test_spec_is_structural_dict(self) -> None:
        """`spec`은 구조(JSON dict)다 — 가변 상태 객체가 아니라 stateless 선언 명세."""
        annotation = str(Visualization.model_fields["spec"].annotation)
        assert "dict" in annotation


# ── ② 5상태 분리(Math/Pedagogy ⊥ Interaction/Animation/UI 런타임) ─────────────
class TestFiveStateSeparation:
    def test_no_runtime_state_field_names(self) -> None:
        """코어 시각화·장면 명세 필드에 런타임/UI 상태 부분문자열이 없다(Math ⊥ 나머지)."""
        offenders: list[str] = []
        for model in _STATE_MODELS:
            for field_name in model.model_fields:
                low = field_name.lower()
                for bad in _RUNTIME_STATE_SUBSTRINGS:
                    if bad in low:
                        offenders.append(f"{model.__name__}.{field_name} (~'{bad}')")
        assert offenders == [], (
            "Math/Pedagogy 명세에 런타임/UI 상태 필드 유입 — "
            f"{offenders}. 상태는 클라 런타임에 두고 명세는 선언적으로 유지하라(5상태 분리·05b)."
        )


# ── ③ Renderer 독립(Intent ≠ Implementation) ────────────────────────────────
class TestRendererIndependence:
    def test_visualization_type_values_are_intents_not_impls(self) -> None:
        """`VisualizationType` 값은 렌더 *의도*이지 구현체 이름이 아니다(Concept→Intent→Adapter)."""
        for member in VisualizationType:
            low = member.value.lower()
            hit = [name for name in _RENDERER_IMPL_NAMES if name in low]
            assert hit == [], (
                f"VisualizationType.{member.name}='{member.value}'에 구현체 이름 {hit} 유입 — "
                "type은 intent여야 하고 구현체는 render_contract.json·L5 어댑터에만 둔다(Part 5)."
            )
