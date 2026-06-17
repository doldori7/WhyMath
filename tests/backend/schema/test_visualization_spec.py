"""타입별 Visualization.spec 계약 단위 테스트 — 슬라이스 S1(docs/architecture/05a §8).

자유 JSON → 검증 가능 계약: 타입별 spec 모델이 ① 빈 {} 통과 ② 유효 필드 통과 ③ 타입 위반
거부 ④ 미지 필드(extra="allow") 허용. Visualization 통합: 잘못된 spec 생성 시 ValidationError
(L3 `parse_visualization_spec` 게이트가 InvalidVisualizationSpecError로 래핑하는 경로의 근거).

설계 정본: 05a §3(스키마)·§8(S1). 보수 원칙(CLAUDE.md 정확성): closed/required 강제는 S3로
연기 — 지금은 *알려진 필드 타입 검증 + 미지 필드 허용*만(기존 자유 JSON 명세 거짓 거부 0).
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from whymath_backend.schema.enums import VisualizationType
from whymath_backend.schema.visualization import (
    _SPEC_MODEL_BY_TYPE,
    AnimationSpec,
    Graph2dSpec,
    SimulationSpec,
    Surface3dSpec,
    Visualization,
    validate_spec_for_type,
)


# ──────────────────────────────────────────────────────────────────────
# 매핑 완전성 — 4종 enum 전부에 spec 모델이 있어야(새 type 추가 시 누락 차단)
# ──────────────────────────────────────────────────────────────────────
def test_spec_model_mapping_covers_all_types() -> None:
    """_SPEC_MODEL_BY_TYPE이 VisualizationType 전체를 덮는다(검증 게이트 구멍 없음)."""
    assert set(_SPEC_MODEL_BY_TYPE) == set(VisualizationType)


# ──────────────────────────────────────────────────────────────────────
# 빈 spec — 모든 타입에서 {} 통과(필드 전부 Optional·골격만 생성 허용)
# ──────────────────────────────────────────────────────────────────────
class TestEmptySpec:
    @pytest.mark.parametrize("vtype", list(VisualizationType))
    def test_empty_spec_valid_for_all_types(self, vtype: VisualizationType) -> None:
        """빈 {} → 어떤 타입이든 검증 통과(raise 없음)."""
        validate_spec_for_type(vtype, {})

    @pytest.mark.parametrize("vtype", list(VisualizationType))
    def test_visualization_empty_spec_ok(self, vtype: VisualizationType) -> None:
        """Visualization(type=...) 기본 spec={} 통과
        (animation은 슬90 불변식상 interactive=False)."""
        interactive = vtype != VisualizationType.animation_prerendered
        v = Visualization(type=vtype, interactive=interactive)
        assert v.spec == {}


# ──────────────────────────────────────────────────────────────────────
# 유효 spec — 명시 필드 타입 통과
# ──────────────────────────────────────────────────────────────────────
class TestValidSpecs:
    def test_graph2d_valid(self) -> None:
        s = Graph2dSpec.model_validate(
            {
                "function": "a*x**2",
                "domain": [-3, 3],
                "parameters": [{"name": "a", "min": -5, "max": 5, "step": 0.1, "default": 1}],
            }
        )
        assert s.function == "a*x**2"
        assert s.domain == [-3.0, 3.0]
        assert s.parameters is not None
        assert s.parameters[0].name == "a"

    def test_surface3d_valid(self) -> None:
        s = Surface3dSpec.model_validate({"surface": "z = x**2 + y**2", "rotatable": True})
        assert s.surface == "z = x**2 + y**2"
        assert s.rotatable is True

    def test_simulation_valid(self) -> None:
        s = SimulationSpec.model_validate({"experiment": "동전 던지기", "trials": 100})
        assert s.trials == 100

    def test_animation_valid(self) -> None:
        s = AnimationSpec.model_validate({"asset_id": "manim-001", "duration_seconds": 12.5})
        assert s.duration_seconds == 12.5


# ──────────────────────────────────────────────────────────────────────
# 타입 위반 거부 (pydantic v2 lax 모드도 int→str 강제 안 함)
# ──────────────────────────────────────────────────────────────────────
class TestTypeViolationsRejected:
    def test_graph2d_function_not_str(self) -> None:
        with pytest.raises(ValidationError):
            Graph2dSpec.model_validate({"function": 123})

    def test_graph2d_domain_not_list(self) -> None:
        with pytest.raises(ValidationError):
            Graph2dSpec.model_validate({"domain": "x"})

    def test_surface3d_surface_not_str(self) -> None:
        with pytest.raises(ValidationError):
            Surface3dSpec.model_validate({"surface": 123})

    def test_simulation_trials_below_one(self) -> None:
        with pytest.raises(ValidationError):
            SimulationSpec.model_validate({"trials": 0})

    def test_animation_duration_not_positive(self) -> None:
        with pytest.raises(ValidationError):
            AnimationSpec.model_validate({"duration_seconds": 0})


# ──────────────────────────────────────────────────────────────────────
# 미지 필드 허용 (extra="allow") — 기존 자유 JSON 명세 호환({"model": ...})
# ──────────────────────────────────────────────────────────────────────
class TestExtraAllowed:
    def test_graph2d_unknown_field_allowed(self) -> None:
        s = Graph2dSpec.model_validate({"model": "circle"})
        assert s.model_dump().get("model") == "circle"

    def test_surface3d_extra_allowed(self) -> None:
        # 알려진 필드 + 미지 필드 혼재도 통과(미지 필드 보존).
        s = Surface3dSpec.model_validate({"surface": "z=x", "highlight": "vertex"})
        assert s.model_dump().get("highlight") == "vertex"


# ──────────────────────────────────────────────────────────────────────
# Visualization 통합 — spec dict 보존 + 잘못된 spec 거부
# ──────────────────────────────────────────────────────────────────────
class TestVisualizationTypedSpecIntegration:
    def test_bad_spec_rejected_via_visualization(self) -> None:
        """타입 위반 spec으로 Visualization 생성 → ValidationError(model_validator 게이트)."""
        with pytest.raises(ValidationError):
            Visualization(
                type=VisualizationType.interactive_graph_2d,
                spec={"function": 123},
            )

    def test_good_spec_accepted_and_dict_preserved(self) -> None:
        """유효 spec 통과 + spec은 원본 dict 그대로 보존(미교체·미강제 — 직렬화/저장 불변)."""
        v = Visualization(
            type=VisualizationType.interactive_graph_2d,
            spec={"function": "x**2", "domain": [-3, 3]},
        )
        assert v.spec == {"function": "x**2", "domain": [-3, 3]}

    def test_unknown_spec_field_ok_via_visualization(self) -> None:
        """미지 spec 필드({"model": ...})도 Visualization 통과(기존 명세 호환)."""
        v = Visualization(
            type=VisualizationType.interactive_graph_2d,
            spec={"model": "circle"},
        )
        assert v.spec["model"] == "circle"

    def test_validate_spec_for_type_helper(self) -> None:
        m = validate_spec_for_type(VisualizationType.simulation_probabilistic, {"trials": 5})
        assert isinstance(m, SimulationSpec)
