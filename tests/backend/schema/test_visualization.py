"""Schema v1.0 Visualization 명세 모델 단위 테스트 — 슬라이스 90.

설계 정본: `docs/architecture/05_interaction.md` §5.2(선언적 시각화 `Visualization`).
커버리지:
  - VisualizationType enum 값 4종(영문, 05 §5.2 정본)
  - 생성: type만(기본값 spec={}/caption=None/interactive=True)·full roundtrip·extra forbid
  - use_enum_values 직렬화(type=문자열)
  - 불변식 _prerendered_not_interactive 분기:
      animation_prerendered+interactive=True 거부 / +False 통과 /
      interactive_graph_2d 기본 interactive=True 통과 / +False 통과(제약 없음)
"""

from __future__ import annotations

import uuid

import pytest
from pydantic import ValidationError
from whymath_backend.schema.enums import VisualizationType
from whymath_backend.schema.visualization import Visualization


# ──────────────────────────────────────────────────────────────────────
# VisualizationType enum — 값 검증(05 §5.2 정본)
# ──────────────────────────────────────────────────────────────────────
class TestVisualizationTypeEnumValues:
    def test_values_english_four(self) -> None:
        """VisualizationType — 영문 4종(05 §5.2 표기 그대로)."""
        assert {e.value for e in VisualizationType} == {
            "interactive_graph_2d",
            "interactive_surface_3d",
            "simulation_probabilistic",
            "animation_prerendered",
        }

    def test_is_str_enum(self) -> None:
        """str-Enum — 값이 문자열과 동치(use_enum_values 비교·직렬화 전제)."""
        assert VisualizationType.interactive_graph_2d == "interactive_graph_2d"


# ──────────────────────────────────────────────────────────────────────
# 생성·직렬화
# ──────────────────────────────────────────────────────────────────────
class TestVisualizationCreation:
    def test_minimal_defaults(self) -> None:
        """type만 주면 spec={}·caption=None·interactive=True, id 자동 생성."""
        v = Visualization(type=VisualizationType.interactive_graph_2d)
        assert v.spec == {}
        assert v.caption is None
        assert v.interactive is True
        assert isinstance(v.visualization_id, uuid.UUID)

    def test_full_roundtrip(self) -> None:
        """전체 필드 지정 후 model_dump roundtrip."""
        vid = uuid.uuid4()
        v = Visualization(
            visualization_id=vid,
            type=VisualizationType.interactive_surface_3d,
            spec={"surface": "z = x**2 + y**2", "rotatable": True},
            caption="회전 가능한 포물면",
            interactive=True,
        )
        dumped = v.model_dump()
        assert dumped["visualization_id"] == vid
        assert dumped["spec"]["surface"] == "z = x**2 + y**2"
        assert dumped["caption"] == "회전 가능한 포물면"

    def test_use_enum_values_serializes_string(self) -> None:
        """use_enum_values — type이 enum이 아닌 문자열 값으로 직렬화된다."""
        v = Visualization(type=VisualizationType.simulation_probabilistic)
        assert v.model_dump()["type"] == "simulation_probabilistic"

    def test_extra_forbidden(self) -> None:
        """extra='forbid' — 정의되지 않은 필드는 거부."""
        with pytest.raises(ValidationError):
            Visualization(
                type=VisualizationType.interactive_graph_2d,
                unknown_field="x",  # type: ignore[call-arg]
            )

    def test_type_required(self) -> None:
        """type은 필수 — 누락 시 ValidationError."""
        with pytest.raises(ValidationError):
            Visualization()  # type: ignore[call-arg]


# ──────────────────────────────────────────────────────────────────────
# 불변식: _prerendered_not_interactive (05 §5.2 '조작 불가')
# ──────────────────────────────────────────────────────────────────────
class TestPrerenderedNotInteractive:
    def test_prerendered_interactive_true_rejected(self) -> None:
        """animation_prerendered + interactive=True(기본) → 거부."""
        with pytest.raises(ValidationError, match="interactive=False"):
            Visualization(type=VisualizationType.animation_prerendered)

    def test_prerendered_interactive_false_ok(self) -> None:
        """animation_prerendered + interactive=False → 통과."""
        v = Visualization(
            type=VisualizationType.animation_prerendered,
            interactive=False,
        )
        assert v.interactive is False

    def test_interactive_type_default_true_ok(self) -> None:
        """interactive_graph_2d 기본 interactive=True → 통과(제약 없음)."""
        v = Visualization(type=VisualizationType.interactive_graph_2d)
        assert v.interactive is True

    def test_interactive_type_false_ok(self) -> None:
        """interactive 가능 타입도 interactive=False 허용(정적 표시)."""
        v = Visualization(
            type=VisualizationType.interactive_graph_2d,
            interactive=False,
        )
        assert v.interactive is False
