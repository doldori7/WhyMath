"""L1 전략 그래프 — canonical 전략 메타 PG 프로젝션 적재(리치 Part 2 Phase 6a).

data-pipeline `strategy_graph`가 만든 `graph.json`(canonical 전략 노드)의 안전 메타를 backend
`strategy_node` 테이블에 strategy_id 키로 멱등 투영한다(검색 enrichment·필터·후속 전략 참조 백킹).
`l1/formula_graph`(수식 메타 프로젝션)의 전략 그래프 짝. 전략은 Polya 계획 단계의 공략 heuristic이며
스텝 `ReasoningType`·풀이 `approach_type`과 직교하는 축이다(축 혼동 금지).
"""

from __future__ import annotations

from whymath_backend.l1.strategy_graph.strategy_node_projection import (
    StrategyNodeRecord,
    StrategyNodeStore,
    load_strategies_from_graph_json,
    populate_strategy_nodes,
)

__all__ = [
    "StrategyNodeRecord",
    "StrategyNodeStore",
    "load_strategies_from_graph_json",
    "populate_strategy_nodes",
]
