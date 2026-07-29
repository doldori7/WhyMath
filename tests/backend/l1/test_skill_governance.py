"""거버넌스 동결 — SkillNode/BehaviorArea (리치 Part 2 Phase 2a·2026-07-03).

Skill 1급 승격(ADR concept_node_layering_decision.md §2)이 CLAUDE.md 금기 안에서 사는지 동결한다:

  ① **BehaviorArea 6종 폐쇄 동결**: 확장 시 ADR 갱신 강제(무분별 증식 금지).
  ② **backend↔pipeline enum 값 정합**: 두 정의(schema/enums·data_pipeline.skill_graph)가 값이
     *정확히 일치*(프로젝션 로더가 `BehaviorArea(value)`로 왕복하므로 드리프트 = 적재 붕괴).
  ③ **신규 엣지 타입 0**: SkillNode 도입이 EdgeType/Relation/AtomRelation을 늘리지 않는다 —
     스킬 연결은 참조 키(`prerequisite_skill_ids`·개념측 `behavior_skills`)만(anti-explosion).

hermetic: DB 불요(enum·모델 import만).
"""

from __future__ import annotations

from data_pipeline.concept_graph.models import RELATION_TYPES
from data_pipeline.skill_graph.models import BEHAVIOR_AREAS
from data_pipeline.skill_graph.models import BehaviorArea as PipelineBehaviorArea
from whymath_backend.schema.enums import BehaviorArea as BackendBehaviorArea
from whymath_backend.schema.enums import EdgeType

_EXPECTED_BEHAVIOR_AREAS = frozenset(
    {"COMPUTE", "TRANSFORM", "INTERPRET", "REPRESENT", "REASON", "VERIFY"}
)


# ── ① BehaviorArea 6종 폐쇄 동결 ────────────────────────────────────────────
def test_behavior_area_exactly_six() -> None:
    """행동영역은 정확히 6종(2026-07-03 확정·폐쇄)."""
    assert len(BackendBehaviorArea) == 6
    assert len(PipelineBehaviorArea) == 6


def test_behavior_area_value_set_frozen() -> None:
    """6종 값 집합 동결 — 추가/변경 시 ADR 갱신 강제."""
    assert {a.value for a in BackendBehaviorArea} == _EXPECTED_BEHAVIOR_AREAS


# ── ② backend↔pipeline enum 값 정합 ─────────────────────────────────────────
def test_backend_pipeline_behavior_area_parity() -> None:
    """schema/enums·data_pipeline.skill_graph의 BehaviorArea 값이 *정확히 일치*.

    프로젝션 로더가 pipeline이 쓴 값을 backend `BehaviorArea(value)`로 재구성하므로, 값이
    어긋나면 적재 시 ValueError로 붕괴한다. 이 동결이 그 드리프트를 코드리뷰로 끌어낸다.
    """
    backend_values = {a.value for a in BackendBehaviorArea}
    pipeline_values = {a.value for a in PipelineBehaviorArea}
    assert backend_values == pipeline_values
    assert BEHAVIOR_AREAS == tuple(a.value for a in BackendBehaviorArea)


# ── ③ 신규 엣지 타입 0 ──────────────────────────────────────────────────────
def test_skillnode_adds_no_edge_type() -> None:
    """SkillNode 도입이 EdgeType/Relation을 늘리지 않는다 — 스킬 연결은 참조 키만.

    EdgeType(backend 6종)·RELATION_TYPES(pipeline 7종)는 SkillNode 승격과 무관하게 예산(5~8)
    안에 머문다(별도 edge_relation_governance가 값 자체를 동결·여기선 예산 불변만 확인).
    """
    assert 5 <= len(EdgeType) <= 8
    assert 5 <= len(RELATION_TYPES) <= 8
    # 스킬 관련 엣지 타입 토큰이 EdgeType/Relation에 유입되지 않았다(참조 키로만 연결).
    edge_tokens = {e.value.lower() for e in EdgeType} | {r.lower() for r in RELATION_TYPES}
    assert not any("skill" in tok or "behavior" in tok for tok in edge_tokens)
