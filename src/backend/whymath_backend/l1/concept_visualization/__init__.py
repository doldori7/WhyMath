"""시각화 가능성 Overlay 계층 — 개념 code → 시각화 4분류(직접/동적/추상/불가).

플레이북 Part 5·ADR concept_node_layering(visualization 계층=노드 비내장). 런타임 조회
(`get_visualizability`)와 시드 적재(`populate_concept_visualization`)를 제공한다.
"""

from whymath_backend.l1.concept_visualization.overlay import (
    ConceptVisualizabilityRecord,
    ConceptVisualizationStore,
    get_visualizability,
    load_concept_visualization_from_json,
    populate_concept_visualization,
)

__all__ = [
    "ConceptVisualizabilityRecord",
    "ConceptVisualizationStore",
    "get_visualizability",
    "load_concept_visualization_from_json",
    "populate_concept_visualization",
]
