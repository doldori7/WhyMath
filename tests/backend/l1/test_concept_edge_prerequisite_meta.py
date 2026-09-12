"""ConceptEdge prerequisite 메타 확장 검증 (CUR-16) — hermetic·PG 불요.

EOS 6_개념 DB 검토 §13에 따른 prerequisite 엣지 메타를 Pydantic 스키마 레벨에서 검증한다.
DB 적재 없이 모델 validator만 테스트한다.
"""

from __future__ import annotations

import uuid

import pytest

from whymath_backend.schema.concept import ConceptEdge
from whymath_backend.schema.enums import DependencyLevel, EdgeType, RequiredStrength


def _make_edge(edge_type: EdgeType, **overrides: object) -> ConceptEdge:
    defaults = {
        "from_concept_id": uuid.uuid4(),
        "to_concept_id": uuid.uuid4(),
        "edge_type": edge_type,
    }
    defaults.update(overrides)
    return ConceptEdge(**defaults)


class TestPrerequisiteMeta:
    """PREREQUISITE 엣지에서만 prerequisite 메타를 허용."""

    def test_prerequisite_with_all_meta_ok(self) -> None:
        edge = _make_edge(
            EdgeType.PREREQUISITE,
            required_strength=RequiredStrength.STRONG,
            dependency_level=DependencyLevel.REQUIRED,
            minimum_mastery=0.7,
            curriculum_context=["2022_KR_Math_9"],
            evidence_source_id="src_curriculum_2022",
        )
        assert edge.required_strength == RequiredStrength.STRONG
        assert edge.dependency_level == DependencyLevel.REQUIRED
        assert edge.minimum_mastery == pytest.approx(0.7)
        assert edge.curriculum_context == ["2022_KR_Math_9"]
        assert edge.evidence_source_id == "src_curriculum_2022"

    def test_prerequisite_without_meta_ok(self) -> None:
        edge = _make_edge(EdgeType.PREREQUISITE)
        assert edge.required_strength is None
        assert edge.dependency_level is None
        assert edge.minimum_mastery is None
        assert edge.curriculum_context == []

    def test_non_prerequisite_required_strength_rejected(self) -> None:
        with pytest.raises(ValueError, match="required_strength"):
            _make_edge(
                EdgeType.COMPOSED_OF,
                required_strength=RequiredStrength.MODERATE,
            )

    def test_non_prerequisite_dependency_level_rejected(self) -> None:
        with pytest.raises(ValueError, match="dependency_level"):
            _make_edge(
                EdgeType.ANALOGOUS_TO,
                dependency_level=DependencyLevel.EXPECTED,
            )

    def test_non_prerequisite_minimum_mastery_rejected(self) -> None:
        with pytest.raises(ValueError, match="minimum_mastery"):
            _make_edge(
                EdgeType.EXTENDS,
                minimum_mastery=0.5,
            )

    def test_minimum_mastery_range(self) -> None:
        with pytest.raises(ValueError):
            _make_edge(
                EdgeType.PREREQUISITE,
                minimum_mastery=1.5,
            )
        with pytest.raises(ValueError):
            _make_edge(
                EdgeType.PREREQUISITE,
                minimum_mastery=-0.1,
            )


class TestSelfEdge:
    """자기 자신을 가리키는 엣지 금지."""

    def test_self_edge_rejected(self) -> None:
        concept_id = uuid.uuid4()
        with pytest.raises(ValueError, match="from_concept_id"):
            _make_edge(
                EdgeType.PREREQUISITE,
                from_concept_id=concept_id,
                to_concept_id=concept_id,
            )
