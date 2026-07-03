"""Part 7. Math UI DSL — 계층 방향·순수성 동결 거버넌스.

`docs/standards/part7_math_ui_dsl_review.md`(판정 리포트)의 항목 ③(Core로 UI/런타임 상태 역류
없음)과 항목 ②(9블록→6 element kind 크로스워크)를 *회귀 감지 테스트*로 못박는다. 검토 시점의
판정을 코드가 스스로 지키게 하는 하드 게이트다(`tests/backend/l1/test_no_import_cycle.py`의
AST 역방향-import 스캔 + `tests/data_pipeline/concept_graph/test_models.py::TestConceptPurity`의
필드 화이트리스트 freeze 두 선례를 답습).

동결 불변식(파이프라인 Knowledge Graph → UI Planner → DSL → Renderer → Flutter/Web·단방향):
  (a) LearningScene 파이프라인의 L3 좌석(`l3.visualization` 등)이 **L4를 import하지 않는다**
      — 생성기가 L4→L3 다운콜만 하도록(역의존 0). scene_generation(L4)이 L3를 부르는 건 정방향.
  (b) `schema.*`(scene DSL이 조립 재료로 쓰는 Visualization·Concept·enums)가 **어떤 L레이어도
      import하지 않는다** — 이 순수성 때문에 `LearningScene`이 schema 아닌 **L4**에 배치됐다.
  (c) `SceneElement` 6종에 **정답·수정·판정·런타임/interaction state 필드가 없다**(필드 화이트
      리스트 freeze) — 답 미루기·낙인 금지를 스키마 차원에서, "interaction state 누출 0"을 고정.
  (d) 6 element kind 집합이 판정 리포트의 9블록→6 kind 크로스워크와 일치한다(택소노미 표류 감지).

주의: 이 파일은 *설계-준수 회귀 가드*이지 DSL 동작 테스트가 아니다(동작은 `test_learning_scene.py`·
`test_scene_generation.py`). 여기 red = "새 필드/새 import가 검토 판정을 깼다"는 신호.
"""

from __future__ import annotations

import ast
import importlib.util

import pytest

from whymath_backend.l4.learning_scene import (
    AnnotationElement,
    LearningScene,
    MisconceptionProbeElement,
    ParamControlElement,
    SocraticPromptElement,
    StepPanelElement,
    VisualizationElement,
)


def _import_targets_of(module: str) -> list[str]:
    """`module`이 실제로 import하는 이름 목록(AST — 주석/docstring 언급 제외)."""
    spec = importlib.util.find_spec(module)
    assert (
        spec is not None and spec.origin is not None
    ), f"모듈 경로 해석 실패: {module}"
    with open(spec.origin, encoding="utf-8") as fh:
        tree = ast.parse(fh.read(), filename=spec.origin)
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            names.append(f"from {node.module} import ... (line {node.lineno})")
        elif isinstance(node, ast.Import):
            names.extend(f"import {a.name} (line {node.lineno})" for a in node.names)
    return names


# (a) LearningScene 파이프라인의 L3 좌석 — L4 import 0(역의존 금지·L4→L3 다운콜만 허용).
_L3_PIPELINE_SEATS: tuple[str, ...] = (
    "whymath_backend.l3.visualization",
    "whymath_backend.l3.models",
    "whymath_backend.l3.interfaces",
)

# (b) scene DSL이 조립 재료로 참조하는 schema 좌석 — 어떤 L레이어도 import 0(schema 순수성).
_SCHEMA_SEATS: tuple[str, ...] = (
    "whymath_backend.schema.visualization",
    "whymath_backend.schema.concept",
    "whymath_backend.schema.enums",
)


@pytest.mark.parametrize("module", _L3_PIPELINE_SEATS)
def test_l3_scene_pipeline_seat_has_no_l4_import(module: str) -> None:
    """(a) LearningScene가 다운콜하는 L3 좌석은 `whymath_backend.l4.*`를 import하지 않는다.

    생성기(`l4/scene_generation.py`)가 L3를 부르는 건 정방향(L4→L3)이므로 허용된다. 반대로 L3가
    L4를 끌어오면 역의존 → 순환·계층 붕괴. 재발 시 어느 import가 방향을 깼는지 이름까지 노출한다.
    """
    offending = [
        name for name in _import_targets_of(module) if "whymath_backend.l4" in name
    ]
    assert not offending, f"{module}에 L4 역방향 import(역류):\n" + "\n".join(offending)


@pytest.mark.parametrize("module", _SCHEMA_SEATS)
def test_scene_schema_seat_imports_no_layer(module: str) -> None:
    """(b) scene DSL 재료 schema는 L1~L6 어떤 레이어도 import하지 않는다(schema 순수성).

    이 순수성(schema는 L레이어 import 0)이 `LearningScene`을 schema가 아니라 **L4**에 배치하게 한
    구조적 이유다(05a §1·scene_generation ★배치 정정). 회귀하면 배치 근거가 무너진다.
    """
    offending = [
        name
        for name in _import_targets_of(module)
        for layer in ("l1", "l2", "l3", "l4", "l5", "l6")
        if f"whymath_backend.{layer}" in name
    ]
    assert (
        not offending
    ), f"{module}(schema)가 L레이어를 import(순수성 붕괴):\n" + "\n".join(offending)


# (c) SceneElement 6종 필드 화이트리스트(동결) — 새 필드 추가 시 red → "이 필드가 정답/판정/런타임
# 상태인가?"를 의식적으로 판정하게 강제하는 하드 게이트. 정답·수정·판정·interaction state 부재 고정.
_ELEMENT_ALLOWED_FIELDS: dict[type, frozenset[str]] = {
    VisualizationElement: frozenset({"kind", "ref"}),
    ParamControlElement: frozenset(
        {"kind", "targets", "bound_visualization_index", "value_range", "step"}
    ),
    StepPanelElement: frozenset({"kind", "solution_path_id", "reveal_policy"}),
    MisconceptionProbeElement: frozenset({"kind", "misconception_id", "intervention"}),
    SocraticPromptElement: frozenset(
        {"kind", "socratic_category", "polya_stage", "hint_level", "prompt_text"}
    ),
    AnnotationElement: frozenset({"kind", "target_element_index", "highlight_spec"}),
}

# 정답 유출(낙인·즉답)·런타임/interaction state 관심사 토큰 — 어떤 요소 필드명에도 등장 금지.
# (참조 키 예외: `solution_path_id`는 검증 풀이 *참조*이지 정답 본문이 아니다 — 토큰 'solution'을
#  금지 목록에 넣지 않는다. 'answer'/'correction'/'verdict' 등 판정·정답 본문 토큰만 막는다.)
_FORBIDDEN_ELEMENT_TOKENS: tuple[str, ...] = (
    "answer",
    "correction",
    "is_correct",
    "verdict",
    "score",
    "grade",
    "session",
    "runtime",
    "click",
    "tap",
    "user_input",
)


@pytest.mark.parametrize("element_cls, allowed", _ELEMENT_ALLOWED_FIELDS.items())
def test_scene_element_field_set_frozen(
    element_cls: type, allowed: frozenset[str]
) -> None:
    """(c-1) 각 SceneElement 변형의 필드 집합이 화이트리스트와 정확히 일치(순수 장면 요소만)."""
    got = sorted(element_cls.model_fields)
    assert set(element_cls.model_fields) == allowed, (
        f"{element_cls.__name__} 필드 표류: {got} != {sorted(allowed)} "
        "(새 필드는 정답/판정/런타임 상태가 아닌지 판정 후 화이트리스트에 반영)"
    )


@pytest.mark.parametrize("element_cls", list(_ELEMENT_ALLOWED_FIELDS))
def test_scene_element_no_answer_or_runtime_field(element_cls: type) -> None:
    """(c-2) 어떤 요소 필드명도 정답/판정/런타임·interaction state 토큰을 담지 않는다.

    답 미루기·낙인 금지(05a §4)·"interaction state 누출 0"(risk_register)을 필드명 수준에서 동결.
    """
    for name in element_cls.model_fields:
        low = name.lower()
        for token in _FORBIDDEN_ELEMENT_TOKENS:
            assert (
                token not in low
            ), f"{element_cls.__name__}.{name}: 금지 토큰 '{token}'(역류/낙인 의심)"


# (d) 9블록(플레이북 Part 7) → 현 구현 6 kind 크로스워크. 판정 리포트와 코드의 단일 진실 원천을
# 대조해 택소노미 표류를 감지한다(블록 추가/삭제 시 리포트 갱신을 강제).
_EXPECTED_SCENE_KINDS: frozenset[str] = frozenset(
    {
        "visualization",  # 9블록 Visualization
        "param_control",  # 9블록 Interaction(조작)
        "step_panel",  # 9블록 Tutoring(단계 풀이·답 미루기)
        "misconception_probe",  # 9블록 Misconception
        "socratic_prompt",  # 9블록 Tutoring(소크라테스)
        "annotation",  # 9블록 Interaction(강조/라벨)
    }
)


def test_scene_kind_taxonomy_matches_crosswalk() -> None:
    """(d) SceneElement 판별 kind 집합이 검토 크로스워크의 6종과 일치한다.

    Scene=LearningScene 자체, Concept=L1 참조(`concept_id`), Skill=CognitiveType 속성+L2,
    Assessment=schema/assessment+gating, AIExplanation=같은 장면의 렌더 타깃 — 이 셋은 *의도적으로*
    전용 scene 블록이 아니다(anti-explosion·Concept Purity). kind가 늘거나 줄면 이 테스트가 red →
    `part7_math_ui_dsl_review.md` 크로스워크를 함께 갱신하도록 강제한다.
    """
    # LearningScene.elements의 판별자 유니온에서 각 변형의 kind 기본값을 수집.
    actual = {cls.model_fields["kind"].default for cls in _ELEMENT_ALLOWED_FIELDS}
    assert actual == _EXPECTED_SCENE_KINDS, (
        f"scene kind 택소노미 표류: {sorted(actual)} != {sorted(_EXPECTED_SCENE_KINDS)} "
        "(9블록→6 kind 크로스워크·판정 리포트 동반 갱신 필요)"
    )
    # LearningScene 최상위에도 런타임/UI 상태 필드가 새어들지 않았는지 동시 확인(항목 ③).
    scene_forbidden = {"session", "runtime", "pixel", "widget", "current_value"}
    leaked = [
        f for f in LearningScene.model_fields for t in scene_forbidden if t in f.lower()
    ]
    assert not leaked, f"LearningScene에 런타임/UI 상태 필드 누수: {leaked}"
