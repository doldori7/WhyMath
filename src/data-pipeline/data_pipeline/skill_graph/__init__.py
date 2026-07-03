"""스킬 그래프(Skill Graph) — L1 자체 구축 자산(cognitive-action 단위 SkillNode).

리치 Part 2 스펙 Phase 2a. Skill을 `CognitiveType` enum 속성에서 **1급 노드로 승격**한다. 노드는
개념이 *행동*으로 무엇을 하는지(6종 폐쇄 `BehaviorArea`)를 mastery 독립추정 단위로 표현한다 —
개념(무엇)과 직교하는 축(어떻게). 자체작성 `skills.jsonl`을 정형화·검증해 `graph.json`을 만든다
(스킬 연결은 참조 키만·신규 엣지 타입 0·anti-explosion).

정본: docs/data/skill_graph_v1.md · 로드맵 Phase 2a · ADR concept_node_layering_decision.md §2.
"""

from __future__ import annotations

from data_pipeline.skill_graph.models import (
    BEHAVIOR_AREAS,
    SKILL_ID_PATTERN,
    SOURCE_CITATION,
    BehaviorArea,
    SkillNode,
)
from data_pipeline.skill_graph.transform import TransformResult, transform_skills
from data_pipeline.skill_graph.validate import (
    SkillValidationReport,
    ValidationIssue,
    validate_skills,
)

__all__ = [
    "BEHAVIOR_AREAS",
    "SKILL_ID_PATTERN",
    "SOURCE_CITATION",
    "BehaviorArea",
    "SkillNode",
    "SkillValidationReport",
    "TransformResult",
    "ValidationIssue",
    "transform_skills",
    "validate_skills",
]
