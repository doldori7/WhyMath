"""L1 스킬 그래프 — 스킬 메타 PG 프로젝션 적재(리치 Part 2 Phase 2a).

data-pipeline `skill_graph`가 만든 `graph.json`(스킬 노드)의 안전 메타를 backend `skill_node`
테이블에 skill_id 키로 멱등 투영한다(검색 enrichment·필터·Phase 2b skill mastery 조인 백킹).
`l1/atom_graph`(원자 메타 프로젝션)의 스킬 그래프 짝.
"""

from __future__ import annotations

from whymath_backend.l1.skill_graph.skill_node_projection import (
    SkillNodeRecord,
    SkillNodeStore,
    load_skill_nodes_from_graph_json,
    populate_skill_nodes,
)

__all__ = [
    "SkillNodeRecord",
    "SkillNodeStore",
    "load_skill_nodes_from_graph_json",
    "populate_skill_nodes",
]
