"""거버넌스 동결 — 관계 어휘 단일 진실 원천 + pipeline↔backend crosswalk(Part 3 항목 ②).

관계 어휘 drift(pipeline 7종 / backend 6종·이름 상이 / atom 1종)를 방어한다. 이 테스트는
*L1 pipeline 쪽*을 동결한다(별도 스위트라 backend enum은 import 불가 — backend 동결은
`tests/backend/l1/test_edge_relation_governance.py`가 자기 enum에 대해 수행).

네 갈래:
  ① **관계 개수 예산(5~8)**: pipeline `Relation`이 핵심 관계 5~8개 범위 유지(폭발 방어).
  ② **crosswalk 전수(totality)**: 모든 `Relation` 값이 crosswalk에 1개 backend 투영 또는
     DEFERRED로 매핑된다(누락 0 — 새 관계 추가 시 crosswalk 갱신 강제).
  ③ **금지 토큰 부재**: `similar_to`/`related_to`가 어휘·crosswalk 어디에도 없다.
  ④ **backend 미러 정합**: crosswalk 투영 값이 backend EdgeType 미러 집합(±DEFERRED) 안이며,
     미러도 5~8 예산·traversal 배제 관계 정의를 지킨다.

hermetic: import·상수 단언만(DB·파일 불요).
"""

from __future__ import annotations

from data_pipeline.concept_graph.models import RELATION_TYPES
from data_pipeline.concept_graph.relation_crosswalk import (
    DEFERRED,
    FORBIDDEN_RELATION_TOKENS,
    KNOWN_BACKEND_EDGE_TYPES,
    LOADED_RELATION,
    RELATION_TO_BACKEND_EDGE_TYPE,
    TRAVERSAL_EXCLUDED_BACKEND_EDGE_TYPES,
    backend_edge_type_for,
)

# 플레이북 Part 3·CLAUDE.md: 핵심 관계 5~8개(폭발 방어). 하한·상한 모두 동결.
_MIN_RELATIONS = 5
_MAX_RELATIONS = 8


class TestRelationBudget:
    def test_pipeline_relation_count_within_budget(self) -> None:
        """pipeline Relation은 5~8개(현재 7종). 벗어나면 관계 폭발/축소 신호."""
        assert _MIN_RELATIONS <= len(RELATION_TYPES) <= _MAX_RELATIONS

    def test_backend_edge_type_mirror_within_budget(self) -> None:
        """backend EdgeType 미러도 5~8개(현재 6종)."""
        assert _MIN_RELATIONS <= len(KNOWN_BACKEND_EDGE_TYPES) <= _MAX_RELATIONS


class TestCrosswalkTotality:
    def test_every_relation_is_mapped(self) -> None:
        """모든 pipeline 관계가 crosswalk 키다(누락 0·초과 0 — 전수 매핑)."""
        assert set(RELATION_TO_BACKEND_EDGE_TYPE) == set(RELATION_TYPES)

    def test_crosswalk_targets_are_known_backend_or_deferred(self) -> None:
        """crosswalk 투영 값은 backend 미러 ∪ {DEFERRED} 안(미지 backend 타입 유입 차단)."""
        allowed = KNOWN_BACKEND_EDGE_TYPES | {DEFERRED}
        for relation, target in RELATION_TO_BACKEND_EDGE_TYPE.items():
            assert target in allowed, f"{relation}→{target} 미허용 투영"

    def test_lookup_helper_matches_table(self) -> None:
        """backend_edge_type_for가 표와 일치하고, 미지 관계엔 시끄럽게 실패."""
        for relation, target in RELATION_TO_BACKEND_EDGE_TYPE.items():
            assert backend_edge_type_for(relation) == target
        try:
            backend_edge_type_for("no_such_relation")
        except KeyError:
            pass
        else:  # pragma: no cover - 실패 시에만
            raise AssertionError("미등록 관계는 KeyError여야 함")

    def test_prerequisite_projects_to_loaded_backend_type(self) -> None:
        """실적재되는 유일 관계(prerequisite)는 backend PREREQUISITE로 투영된다."""
        assert LOADED_RELATION in RELATION_TYPES
        assert backend_edge_type_for(LOADED_RELATION) == "PREREQUISITE"


class TestForbiddenTokens:
    def test_no_forbidden_token_in_pipeline_relations(self) -> None:
        """`similar_to`/`related_to`가 pipeline 관계 어휘에 없다(약한 총칭 관계 금지)."""
        assert not (FORBIDDEN_RELATION_TOKENS & set(RELATION_TYPES))

    def test_no_forbidden_token_in_crosswalk(self) -> None:
        """금지 토큰이 crosswalk 키·값 어디에도 없다."""
        keys = set(RELATION_TO_BACKEND_EDGE_TYPE)
        values = set(RELATION_TO_BACKEND_EDGE_TYPE.values())
        assert not (FORBIDDEN_RELATION_TOKENS & (keys | values))

    def test_no_forbidden_token_in_backend_mirror(self) -> None:
        """금지 토큰이 backend 미러에도 없다(대소문자 무관 비교)."""
        lowered = {v.lower() for v in KNOWN_BACKEND_EDGE_TYPES}
        assert not (FORBIDDEN_RELATION_TOKENS & lowered)


class TestTraversalExclusion:
    def test_excluded_are_known_backend_types(self) -> None:
        """traversal 배제 관계는 backend 미러의 부분집합(허깨비 배제 금지)."""
        assert TRAVERSAL_EXCLUDED_BACKEND_EDGE_TYPES <= KNOWN_BACKEND_EDGE_TYPES

    def test_prerequisite_not_excluded(self) -> None:
        """선수(PREREQUISITE)는 traversal 대상 — 절대 배제 목록에 없다."""
        assert "PREREQUISITE" not in TRAVERSAL_EXCLUDED_BACKEND_EDGE_TYPES

    def test_weak_analogy_relation_is_excluded(self) -> None:
        """유사 관계(ANALOGOUS_TO)는 traversal에서 배제된다(N² dense화 방어)."""
        assert "ANALOGOUS_TO" in TRAVERSAL_EXCLUDED_BACKEND_EDGE_TYPES
