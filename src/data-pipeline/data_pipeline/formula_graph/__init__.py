"""수식 그래프(Formula Graph) — L1 자체 구축 자산(canonical-only 수식 노드).

리치 Part 2 스펙 Phase 5a. 수식을 1급 노드로 승격하되 **canonical 표현만** 노드화한다 — 변형식은
노드화하지 않고(조합폭발 방지) 변형↔canonical 동치는 런타임 SymPy에 위임한다(SymPy 재구현 금지).
`formula_id`는 사람 관리 안정 code(`formula.<slug>`)이고 `canonical_signature`는 검색·dedup 보조
메타일 뿐 정체성이 아니다(ID≠Signature). 자체작성 `formulas.jsonl`을 정형화·검증해 `graph.json`을
만든다. 소비처 연동(`formula_refs` 채움·resolution)은 Phase 5b.

정본: docs/data/formula_graph_v1.md · 로드맵 Phase 5a · ADR concept_node_layering_decision.md ·
위험문서 개정(math_dsl_evolution·risk_register).
"""

from __future__ import annotations

from data_pipeline.formula_graph.models import (
    FORMULA_ID_PATTERN,
    SOURCE_CITATION,
    FormulaNode,
)
from data_pipeline.formula_graph.transform import (
    TransformResult,
    transform_formulas,
)
from data_pipeline.formula_graph.validate import (
    FormulaValidationReport,
    ValidationIssue,
    validate_formulas,
)

__all__ = [
    "FORMULA_ID_PATTERN",
    "SOURCE_CITATION",
    "FormulaNode",
    "FormulaValidationReport",
    "TransformResult",
    "ValidationIssue",
    "transform_formulas",
    "validate_formulas",
]
