"""L1 수식 그래프 — canonical 수식 메타 PG 프로젝션 적재(리치 Part 2 Phase 5a).

data-pipeline `formula_graph`가 만든 `graph.json`(canonical 수식 노드)의 안전 메타를 backend
`formula_node` 테이블에 formula_id 키로 멱등 투영한다(검색 enrichment·필터·후속 5b 수식 참조 백킹).
`l1/problem_type_graph`(문제유형 메타 프로젝션)의 수식 그래프 짝. 동치 판정은 l3 SymPy(재구현 금지).
"""

from __future__ import annotations

from whymath_backend.l1.formula_graph.formula_node_projection import (
    FormulaNodeRecord,
    FormulaNodeStore,
    load_formulas_from_graph_json,
    populate_formula_nodes,
)

__all__ = [
    "FormulaNodeRecord",
    "FormulaNodeStore",
    "load_formulas_from_graph_json",
    "populate_formula_nodes",
]
