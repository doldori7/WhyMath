"""문제유형 그래프(Problem Type Graph) — L1 자체 구축 자산(cognitive-action canonical 노드).

리치 Part 2 스펙 Phase 3. ProblemType을 `Problem` 스키마 속성에서 **1급 노드로 승격**한다. 노드는
문제가 *무슨 사고(cognitive action)를 요구하는가*를 canonical 단위로 표현한다 — 표면 구조
(`SignaturePattern`)와 직교하는 축. cognitive-action 축은 이미 `BehaviorArea`(Phase 2a)라 신규 enum
없이 유형이 exercise하는 스킬(`behavior_skills`·skill_graph_v1 참조)로 표현한다(신규 엣지 타입 0).
자체작성 `problem_types.jsonl`을 정형화·검증해 `graph.json`을 만든다.

정본: docs/data/problem_type_graph_v1.md · 로드맵 Phase 3 · ADR concept_node_layering_decision.md.
"""

from __future__ import annotations

from data_pipeline.problem_type_graph.models import (
    PROBLEM_TYPE_ID_PATTERN,
    SOURCE_CITATION,
    ProblemTypeNode,
)
from data_pipeline.problem_type_graph.transform import (
    TransformResult,
    transform_problem_types,
)
from data_pipeline.problem_type_graph.validate import (
    ProblemTypeValidationReport,
    ValidationIssue,
    validate_problem_types,
)

__all__ = [
    "PROBLEM_TYPE_ID_PATTERN",
    "SOURCE_CITATION",
    "ProblemTypeNode",
    "ProblemTypeValidationReport",
    "TransformResult",
    "ValidationIssue",
    "transform_problem_types",
    "validate_problem_types",
]
