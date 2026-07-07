"""L1 문제유형 그래프 — 문제유형 메타 PG 프로젝션 적재(리치 Part 2 Phase 3).

data-pipeline `problem_type_graph`가 만든 `graph.json`(문제유형 노드)의 안전 메타를 backend
`problem_type_node` 테이블에 problem_type_id 키로 멱등 투영한다(검색 enrichment·필터·후속 문제
분류·추천 백킹). `l1/skill_graph`(스킬 메타 프로젝션)의 문제유형 그래프 짝.
"""

from __future__ import annotations

from whymath_backend.l1.problem_type_graph.problem_type_node_projection import (
    ProblemTypeNodeRecord,
    ProblemTypeNodeStore,
    load_problem_types_from_graph_json,
    populate_problem_type_nodes,
)

__all__ = [
    "ProblemTypeNodeRecord",
    "ProblemTypeNodeStore",
    "load_problem_types_from_graph_json",
    "populate_problem_type_nodes",
]
