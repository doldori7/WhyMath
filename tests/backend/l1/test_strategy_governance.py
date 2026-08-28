"""거버넌스 동결 — StrategyNode (리치 Part 2 Phase 6a·2026-07-08).

StrategyNode 1급 승격(문제 공략 heuristic·Polya 계획 단계)이 CLAUDE.md 금기·anti-explosion 경계
안에서 사는지 동결한다. StrategyNode의 최대 위험은 *축 혼동*이다 — 스텝 `ReasoningType`·풀이
`approach_type`과 섞이면 노드가 오염되고 교육 일관성이 무너진다. 그래서 경계를 코드로 강제한다:

  ① **신규 엣지 타입 0**: StrategyNode 도입이 EdgeType을 늘리지 않는다 — 전략 연결은 참조 키만
     (anti-explosion·closed 8노드 택소노미).
  ② **closed 택소노미 동결**: STRATEGY_SLUGS 8종·STRATEGY_FAMILIES 4종의 값 집합이 동결됐다
     (frozenset 하드코딩 비교·조합폭발 방지).
  ③ **축 disjoint(핵심)**: 각 strategy slug 집합이 `approach_type` 6값·`ReasoningType` 7값(소문자)과
     교집합 ∅이다 — 세 축이 문자열조차 겹치지 않아 혼동 원천이 구조적으로 차단된다.
  ④ **엣지 배열 부재**: 코퍼스에 별도 엣지 배열이 없다(canonical 노드만).
  ⑤ **Strategy 1급 노드 승격**: pipeline `StrategyNode`·backend `strategy_node` ORM이 실재한다.

hermetic: DB 불요(모델·enum import + 코퍼스 JSON 스캔).
"""

from __future__ import annotations

import json
from pathlib import Path

from data_pipeline.strategy_graph.models import (
    STRATEGY_FAMILIES,
    STRATEGY_SLUGS,
)
from data_pipeline.strategy_graph.models import (
    StrategyNode as PipelineStrategyNode,
)

from whymath_backend.db.models.strategy_node import StrategyNode as OrmStrategyNode
from whymath_backend.schema.enums import ApproachType, EdgeType, ReasoningType

# 리포지토리 루트(tests/backend/l1/ 기준 3단 상위) → 코퍼스 경로.
_REPO_ROOT = Path(__file__).resolve().parents[3]
_STRATEGY_GRAPH = _REPO_ROOT / "data" / "corpus" / "strategy_graph_v1" / "graph.json"

# 인접 축1: 풀이 전체 접근유형 6값 — S4-10 좌석 승격: 리터럴 하드코딩 → 단일 좌석
# `schema/enums.py::ApproachType` 참조. 폐쇄성(값 집합 동결)은 아래
# `test_approach_type_closed_set_frozen`이 리터럴 비교로 별도 유지한다(좌석이 바뀌면
# 그 테스트가 잡는다 — 하드코딩이 지키던 동결력 보존).
_APPROACH_TYPES = frozenset(member.value for member in ApproachType)


def test_strategy_adds_no_edge_type() -> None:
    """StrategyNode 도입이 EdgeType을 늘리지 않는다 — 전략 연결은 참조 키만(신규 엣지 0)."""
    assert 5 <= len(EdgeType) <= 8
    edge_tokens = {e.value.lower() for e in EdgeType}
    assert not any("strategy" in tok for tok in edge_tokens)


def test_strategy_closed_set_frozen() -> None:
    """STRATEGY_SLUGS 8종·STRATEGY_FAMILIES 4종의 값 집합 동결(조합폭발 방지·closed 택소노미)."""
    assert len(STRATEGY_SLUGS) == 8
    assert frozenset(STRATEGY_SLUGS) == frozenset(
        {
            "specialize",
            "work_backward",
            "analogy",
            "reformulate",
            "auxiliary_construction",
            "pattern_seeking",
            "case_exhaustion",
            "contradiction",
        }
    )
    assert len(STRATEGY_FAMILIES) == 4
    assert frozenset(STRATEGY_FAMILIES) == frozenset(
        {"reduction", "transformation", "exploration", "indirect"}
    )


def test_approach_type_closed_set_frozen() -> None:
    """`ApproachType` 6종의 값 집합 동결(조합폭발 방지·closed 택소노미 — S4-10 좌석 승격 보상).

    좌석 참조 승격으로 disjoint 검사가 enum 변경을 따라 움직이게 됐으므로, 폐쇄성 자체는
    여기서 리터럴 비교로 동결한다(`test_strategy_closed_set_frozen` 선례 동형 — yaml
    `approach_type` enum·구 Literal 6값과 1:1).
    """
    assert len(ApproachType) == 6
    assert _APPROACH_TYPES == frozenset(
        {"algebraic", "geometric", "combinatorial", "inductive", "visual", "backward"}
    )


def test_strategy_axis_disjoint_from_reasoning_and_approach() -> None:
    """각 strategy slug이 approach_type 6값·ReasoningType 7값(소문자)과 교집합 ∅(축 혼동 차단).

    strategy(공략 발상)·approach_type(완성 풀이 접근)·ReasoningType(스텝 추론)은 직교 3축이다.
    slug이 두 축의 어느 값과도 문자열로 겹치지 않아야 노드가 서로의 의미로 오염되지 않는다.
    (S4-10: approach 6값이 리터럴 → `ApproachType` 좌석 참조로 승격 — 값 집합이 동일하므로
    본 검사의 결과는 불변이다.)
    """
    slugs = frozenset(STRATEGY_SLUGS)
    reasoning_lower = frozenset(r.value.lower() for r in ReasoningType)
    assert slugs.isdisjoint(_APPROACH_TYPES), slugs & _APPROACH_TYPES
    assert slugs.isdisjoint(reasoning_lower), slugs & reasoning_lower


def test_corpus_has_no_edge_array() -> None:
    """코퍼스에 별도 엣지 배열이 없다 — canonical 노드만(연결은 참조 키)."""
    graph = json.loads(_STRATEGY_GRAPH.read_text(encoding="utf-8"))
    assert "edges" not in graph


def test_strategy_is_first_class_node() -> None:
    """Strategy — Phase 6a로 1급 노드 승격(StrategyNode 모델·ORM).

    부재에서 격상됐다: data-pipeline `StrategyNode`(빌드타임 노드·`strategy_id` 사람 관리 code·
    `family` 4종)·backend `strategy_node`(PG 프로젝션 ORM)이 실재한다. formula의 first-class 동결을
    여기서 자립적으로 수행한다(`test_five_node_connectivity_governance.py`는 별도 스코프).
    """
    assert "strategy_id" in PipelineStrategyNode.model_fields
    assert "family" in PipelineStrategyNode.model_fields
    assert OrmStrategyNode.__tablename__ == "strategy_node"
