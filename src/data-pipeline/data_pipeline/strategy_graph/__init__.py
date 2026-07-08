"""전략 그래프(Strategy Graph) — L1 자체 구축 자산(문제 공략 heuristic canonical 노드).

리치 Part 2 스펙 Phase 6a. 문제를 만났을 때의 *공략 전략*(Polya 계획 단계 heuristic)을 1급 노드로
승격한다. 스텝 단위 `ReasoningType`·풀이 전체 `approach_type`과 **직교하는 축**(무엇으로 접근하는가)
이며, closed 8노드 택소노미다(4 family). 전략은 특정 성취기준에 종속되지 않는다(`standard_codes`
기본 []). 자체작성 `strategies.jsonl`을 정형화·검증해 `graph.json`을 만든다. 소비처 연동(참조 키
채움·resolution)은 Phase 6b.

정본: docs/data/strategy_graph_v1.md · 로드맵 Phase 6a · formula_graph_v1(선례)·
problem_type_graph_v1(선례·enum-free 순수 TEXT).
"""

from __future__ import annotations

from data_pipeline.strategy_graph.models import (
    SOURCE_CITATION,
    STRATEGY_FAMILIES,
    STRATEGY_ID_PATTERN,
    STRATEGY_SLUGS,
    StrategyNode,
)
from data_pipeline.strategy_graph.transform import (
    TransformResult,
    transform_strategies,
)
from data_pipeline.strategy_graph.validate import (
    StrategyValidationReport,
    ValidationIssue,
    validate_strategies,
)

__all__ = [
    "SOURCE_CITATION",
    "STRATEGY_FAMILIES",
    "STRATEGY_ID_PATTERN",
    "STRATEGY_SLUGS",
    "StrategyNode",
    "StrategyValidationReport",
    "TransformResult",
    "ValidationIssue",
    "transform_strategies",
    "validate_strategies",
]
