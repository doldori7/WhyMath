"""LearningScene DSL 합성 스키마 + parse_learning_scene 게이트 단위 테스트 — S2(05a §3·§4).

커버: 6종 변형 생성·dict→변형 판별 유니온·3 구조 불변식(위반/통과·보수적 통과)·게이트
(JSON/스키마/카탈로그 참조 무결성)·misconception_probe 정답/수정 필드 부재(extra=forbid).

설계 정본: docs/architecture/05a_learning_scene_dsl.md §3(스키마)·§4(게이트). 안전 원칙
(CLAUDE.md): 답 미루기·낙인 금지를 *스키마 불변식*으로 강제. test_visualization_spec.py 스타일 미러.
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from pydantic import ValidationError

from whymath_backend.l4.learning_scene import (
    AnnotationElement,
    LearningScene,
    LearningSceneValidationError,
    MisconceptionProbeElement,
    ParamControlElement,
    SceneLayout,
    SceneLearnerContext,
    SocraticPromptElement,
    StepPanelElement,
    VisualizationElement,
    parse_learning_scene,
)
from whymath_backend.l4.misconception.catalog import CATALOG_BY_ID
from whymath_backend.l4.misconception.models import InterventionPattern
from whymath_backend.l4.models import PolyaStage
from whymath_backend.l4.socratic.categories import SocraticCategory

# 유효 오개념 id — 카탈로그에서 동적 취득(하드코딩 회피·카탈로그 변동에 강건).
_VALID_MC_ID = next(iter(CATALOG_BY_ID))


# ── 헬퍼: 최소 유효 요소·장면 dict ──────────────────────────────────────────
def _graph2d_viz(params: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """graph_2d visualization 요소 dict(params 선언 선택)."""
    spec: dict[str, Any] = {"function": "a*x**2"}
    if params is not None:
        spec["parameters"] = params
    return {
        "kind": "visualization",
        "ref": {"type": "interactive_graph_2d", "spec": spec},
    }


def _surface3d_viz() -> dict[str, Any]:
    """surface_3d visualization 요소 dict(비-graph_2d — 보수적 통과 경로 검증용)."""
    return {
        "kind": "visualization",
        "ref": {"type": "interactive_surface_3d", "spec": {"surface": "z = x"}},
    }


def _socratic(hint_level: int = 1) -> dict[str, Any]:
    return {
        "kind": "socratic_prompt",
        "socratic_category": "clarification",
        "polya_stage": "understand",
        "hint_level": hint_level,
        "prompt_text": "어디까지 이해됐어?",
    }


def _scene(elements: list[dict[str, Any]], *, max_level: int = 4) -> dict[str, Any]:
    return {
        "concept_id": "UC-ALG-001",
        "layout": "single",
        "answer_deferral_max_level": max_level,
        "elements": elements,
    }


# ── 6종 변형 생성 + 판별 유니온 ──────────────────────────────────────────────
class TestElementConstruction:
    def test_visualization_element(self) -> None:
        el = VisualizationElement.model_validate(_graph2d_viz())
        assert el.kind == "visualization"
        assert el.ref.type == "interactive_graph_2d"

    def test_param_control_element(self) -> None:
        el = ParamControlElement(targets=["a"], bound_visualization_index=0, step=0.1)
        assert el.targets == ["a"]
        assert el.step == 0.1

    def test_step_panel_defaults_deferred(self) -> None:
        el = StepPanelElement(solution_path_id="sp-1")
        assert el.reveal_policy == "deferred"  # 답 미루기 — 유일 허용값

    def test_step_panel_rejects_non_deferred(self) -> None:
        with pytest.raises(ValidationError):
            StepPanelElement.model_validate(
                {
                    "kind": "step_panel",
                    "solution_path_id": "sp-1",
                    "reveal_policy": "immediate",
                }
            )

    def test_misconception_probe_element(self) -> None:
        el = MisconceptionProbeElement(
            misconception_id=_VALID_MC_ID,
            intervention=InterventionPattern.COUNTEREXAMPLE,
        )
        assert el.misconception_id == _VALID_MC_ID
        assert el.intervention == InterventionPattern.COUNTEREXAMPLE.value  # use_enum_values

    def test_socratic_prompt_element(self) -> None:
        el = SocraticPromptElement(
            socratic_category=SocraticCategory.ASSUMPTION,
            polya_stage=PolyaStage.PLAN,
            hint_level=2,
            prompt_text="왜 그렇게 가정했어?",
        )
        assert el.hint_level == 2
        assert el.polya_stage == PolyaStage.PLAN.value

    def test_annotation_element(self) -> None:
        el = AnnotationElement(target_element_index=0, highlight_spec={"color": "blue"})
        assert el.target_element_index == 0

    def test_discriminated_union_resolution(self) -> None:
        """dict elements가 kind로 6 변형 각각에 올바로 해소되는지(판별 유니온)."""
        scene = LearningScene.model_validate(
            _scene(
                [
                    _graph2d_viz([{"name": "a"}]),
                    {
                        "kind": "param_control",
                        "targets": ["a"],
                        "bound_visualization_index": 0,
                    },
                    {"kind": "step_panel", "solution_path_id": "sp-1"},
                    {
                        "kind": "misconception_probe",
                        "misconception_id": _VALID_MC_ID,
                        "intervention": "counterexample",
                    },
                    _socratic(1),
                    {"kind": "annotation", "target_element_index": 0},
                ]
            )
        )
        kinds = [
            VisualizationElement,
            ParamControlElement,
            StepPanelElement,
            MisconceptionProbeElement,
            SocraticPromptElement,
            AnnotationElement,
        ]
        for el, cls in zip(scene.elements, kinds, strict=True):
            assert isinstance(el, cls)


# ── LearningScene 기본 ──────────────────────────────────────────────────────
class TestLearningSceneBasics:
    def test_minimal_scene(self) -> None:
        scene = LearningScene.model_validate(_scene([_graph2d_viz()]))
        assert scene.layout == SceneLayout.single.value
        assert scene.scene_id is not None  # UUID 자동 생성
        assert scene.learner_context is None

    def test_learner_context_snapshot(self) -> None:
        ctx = SceneLearnerContext(mastery_level=0.4, active_hypothesis_ids=["h1"], theta=0.2)
        scene = LearningScene(
            concept_id="UC-ALG-001",
            layout=SceneLayout.two_panel,
            answer_deferral_max_level=3,
            learner_context=ctx,
            elements=[VisualizationElement.model_validate(_graph2d_viz())],
        )
        assert scene.learner_context is not None
        assert scene.learner_context.mastery_level == 0.4

    def test_mastery_level_out_of_range_rejected(self) -> None:
        with pytest.raises(ValidationError):
            SceneLearnerContext(mastery_level=1.5)

    def test_max_level_out_of_range_rejected(self) -> None:
        with pytest.raises(ValidationError):
            LearningScene.model_validate(_scene([_graph2d_viz()], max_level=5))


# ── 불변식 ① 답 미루기 (hint_level ≤ max) ───────────────────────────────────
class TestAnswerDeferralInvariant:
    def test_hint_level_within_max_passes(self) -> None:
        LearningScene.model_validate(_scene([_socratic(2)], max_level=3))

    def test_hint_level_equal_max_passes(self) -> None:
        LearningScene.model_validate(_scene([_socratic(3)], max_level=3))

    def test_hint_level_exceeds_max_rejected(self) -> None:
        with pytest.raises(ValidationError, match="답 미루기"):
            LearningScene.model_validate(_scene([_socratic(4)], max_level=2))


# ── 불변식 ② param_control 정합 ─────────────────────────────────────────────
class TestParamControlInvariant:
    def test_target_in_declared_params_passes(self) -> None:
        LearningScene.model_validate(
            _scene(
                [
                    _graph2d_viz([{"name": "a"}, {"name": "b"}]),
                    {
                        "kind": "param_control",
                        "targets": ["a"],
                        "bound_visualization_index": 0,
                    },
                ]
            )
        )

    def test_target_not_declared_rejected(self) -> None:
        with pytest.raises(ValidationError, match="선언 파라미터"):
            LearningScene.model_validate(
                _scene(
                    [
                        _graph2d_viz([{"name": "a"}]),
                        {
                            "kind": "param_control",
                            "targets": ["b"],
                            "bound_visualization_index": 0,
                        },
                    ]
                )
            )

    def test_no_declared_params_conservative_pass(self) -> None:
        """graph_2d지만 parameters 미선언 → 보수적 통과(false reject 0)."""
        LearningScene.model_validate(
            _scene(
                [
                    _graph2d_viz(),  # parameters 키 없음
                    {
                        "kind": "param_control",
                        "targets": ["a"],
                        "bound_visualization_index": 0,
                    },
                ]
            )
        )

    def test_non_graph2d_bound_conservative_pass(self) -> None:
        """bound가 비-graph_2d(surface_3d) → 멤버십 검증 생략·보수적 통과."""
        LearningScene.model_validate(
            _scene(
                [
                    _surface3d_viz(),
                    {
                        "kind": "param_control",
                        "targets": ["theta"],
                        "bound_visualization_index": 0,
                    },
                ]
            )
        )

    def test_bound_index_out_of_range_rejected(self) -> None:
        with pytest.raises(ValidationError, match="visualization 요소를 가리키지 않는다"):
            LearningScene.model_validate(
                _scene(
                    [
                        {
                            "kind": "param_control",
                            "targets": ["a"],
                            "bound_visualization_index": 9,
                        }
                    ]
                )
            )

    def test_bound_index_not_visualization_rejected(self) -> None:
        """bound가 visualization이 아닌 요소(socratic)를 가리키면 거부."""
        with pytest.raises(ValidationError, match="visualization 요소를 가리키지 않는다"):
            LearningScene.model_validate(
                _scene(
                    [
                        _socratic(1),
                        {
                            "kind": "param_control",
                            "targets": ["a"],
                            "bound_visualization_index": 0,
                        },
                    ]
                )
            )


# ── 불변식 ③ annotation 정합 ────────────────────────────────────────────────
class TestAnnotationInvariant:
    def test_valid_target_passes(self) -> None:
        LearningScene.model_validate(
            _scene([_graph2d_viz(), {"kind": "annotation", "target_element_index": 0}])
        )

    def test_self_reference_rejected(self) -> None:
        with pytest.raises(ValidationError, match="자기 외 유효 인덱스"):
            LearningScene.model_validate(
                _scene([{"kind": "annotation", "target_element_index": 0}])
            )

    def test_out_of_range_target_rejected(self) -> None:
        with pytest.raises(ValidationError, match="자기 외 유효 인덱스"):
            LearningScene.model_validate(
                _scene([_graph2d_viz(), {"kind": "annotation", "target_element_index": 9}])
            )


# ── 게이트 parse_learning_scene ─────────────────────────────────────────────
class TestParseGate:
    def test_parse_from_dict(self) -> None:
        scene = parse_learning_scene(_scene([_graph2d_viz()]))
        assert isinstance(scene, LearningScene)

    def test_parse_from_json_string(self) -> None:
        scene = parse_learning_scene(json.dumps(_scene([_graph2d_viz()])))
        assert isinstance(scene, LearningScene)

    def test_invalid_json_rejected(self) -> None:
        with pytest.raises(LearningSceneValidationError, match="JSON 파싱 실패"):
            parse_learning_scene("{not valid json")

    def test_schema_violation_wrapped(self) -> None:
        """필드 위반(max_level=5)이 ValidationError → LearningSceneValidationError로 래핑."""
        with pytest.raises(LearningSceneValidationError, match="스키마/불변식 위반"):
            parse_learning_scene(_scene([_graph2d_viz()], max_level=5))

    def test_invariant_violation_wrapped(self) -> None:
        """불변식 위반(hint>max)도 게이트가 LearningSceneValidationError로 래핑."""
        with pytest.raises(LearningSceneValidationError, match="스키마/불변식 위반"):
            parse_learning_scene(_scene([_socratic(4)], max_level=1))

    def test_valid_misconception_id_passes(self) -> None:
        scene = parse_learning_scene(
            _scene(
                [
                    {
                        "kind": "misconception_probe",
                        "misconception_id": _VALID_MC_ID,
                        "intervention": "counterexample",
                    }
                ]
            )
        )
        assert isinstance(scene.elements[0], MisconceptionProbeElement)

    def test_unknown_misconception_id_rejected(self) -> None:
        with pytest.raises(LearningSceneValidationError, match="오개념 카탈로그에 없다"):
            parse_learning_scene(
                _scene(
                    [
                        {
                            "kind": "misconception_probe",
                            "misconception_id": "nonexistent-misconception-xyz",
                            "intervention": "counterexample",
                        }
                    ]
                )
            )


# ── misconception_probe 정답/수정 필드 부재 (extra=forbid 구조 차단) ─────────
class TestNoAnswerFields:
    @pytest.mark.parametrize("forbidden_field", ["correction", "answer", "fix", "solution"])
    def test_misconception_probe_rejects_answer_like_fields(self, forbidden_field: str) -> None:
        """정답·수정류 필드는 스키마에 *없으므로* extra=forbid가 구조적으로 차단(낙인/즉답 금지)."""
        with pytest.raises(ValidationError):
            MisconceptionProbeElement.model_validate(
                {
                    "kind": "misconception_probe",
                    "misconception_id": _VALID_MC_ID,
                    "intervention": "counterexample",
                    forbidden_field: "정답을 여기 밀반입",
                }
            )
