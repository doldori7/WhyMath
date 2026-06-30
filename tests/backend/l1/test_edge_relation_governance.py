"""거버넌스 동결 — 개념 *엣지* 적재는 PREREQUISITE 단일 관계만(약한 관계 N² 폭발 차단·Q2).

math_dsl_risk_register.md Q2: `EdgeType` enum은 약한 관계(ANALOGOUS_TO·CONTRASTS·EXTENDS·
COMPOSED_OF·TRIGGERS_DISTRACTOR)를 *어휘로 선언*하나, 어느 적재기도 PREREQUISITE 외를 적재하지
않는다. 약한 관계가 PREREQUISITE 그래프로 새어들면 dense화·traversal 붕괴(N²)다. 두 적재기
(원자 백본·구 개념그래프)가 *모든* 약한 관계를 거부함을 단일 거버넌스 테스트로 동결한다.

기존 per-loader 테스트(`test_atom_backend_edge.py::test_non_prerequisite_skipped`·
`test_concept_backend_edge_load.py::test_non_prerequisite_relation_skipped`)는 약한 관계 *하나씩*만
확인한다. 본 테스트는 `EdgeType` enum에서 *모든* 약한 값을 스윕해(새 약한 타입이 추가돼도 자동
포함) 두 적재기가 전부 거부함을 검증한다 — enum과 적재 거버넌스를 한곳에 묶는다.

hermetic: DB 불요(로더는 graph.json 텍스트만 읽음).
"""

from __future__ import annotations

import json
from pathlib import Path

from whymath_backend.l1.atom_graph.atom_backend_edge import (
    _PREREQUISITE_RELATION as _ATOM_PREREQ_RELATION,
)
from whymath_backend.l1.atom_graph.atom_backend_edge import (
    load_atom_edges_from_graph_json,
)
from whymath_backend.l1.concept_graph.backend_edge import (
    _PREREQUISITE_RELATION as _CG_PREREQ_RELATION,
)
from whymath_backend.l1.concept_graph.backend_edge import (
    load_backend_edges_from_graph_json,
)
from whymath_backend.schema.enums import EdgeType

# graph.json `relation` 문자열은 data-pipeline Relation 값(소문자) — EdgeType 값(대문자)을
# 소문자화한 형태다(예: ANALOGOUS_TO → "analogous_to"·기존 픽스처와 동형). enum에서 PREREQUISITE
# 외 약한 관계를 *전부* 도출해 스윕한다(새 약한 타입 추가 시 자동 포함·거버넌스 회귀 자동 확대).
_WEAK_RELATIONS: tuple[str, ...] = tuple(
    e.value.lower() for e in EdgeType if e is not EdgeType.PREREQUISITE
)


def test_loaders_freeze_prerequisite_as_only_accepted_relation() -> None:
    """두 적재기 모두 수용 관계 상수가 정확히 "prerequisite"임을 동결(단일 진실)."""
    assert _ATOM_PREREQ_RELATION == "prerequisite"
    assert _CG_PREREQ_RELATION == "prerequisite"


def test_weak_relation_vocabulary_preserved() -> None:
    """약한 관계는 enum 어휘로 *보존*된다(삭제 금지) — 미래 노드화·op-code 카탈로그 용도.

    적재는 안 하되 어휘는 남긴다(TRIGGERS_DISTRACTOR docstring 명문). 스윕 대상이 비면 거버넌스
    테스트가 공허해지므로, 약한 관계가 최소 1종 이상 선언돼 있음을 함께 못 박는다.
    """
    assert len(_WEAK_RELATIONS) >= 1
    assert EdgeType.PREREQUISITE in set(EdgeType)


def test_atom_loader_loads_prerequisite_only(tmp_path: Path) -> None:
    """원자 적재기: 약한 관계를 모두 섞어도 PREREQUISITE 1건만 적재·나머지 전부 skip."""
    edges: list[dict[str, object]] = [
        {"from_code": "PRE", "to_code": "POST", "relation": "prerequisite"}
    ]
    # 각 약한 관계에 고유 양끝 부여(self-edge·dedup 회피).
    for i, rel in enumerate(_WEAK_RELATIONS):
        edges.append({"from_code": f"W{i}A", "to_code": f"W{i}B", "relation": rel})
    path = tmp_path / "graph.json"
    path.write_text(json.dumps({"concepts": [], "edges": edges}), encoding="utf-8")

    records, skipped = load_atom_edges_from_graph_json(path)

    assert len(records) == 1
    assert records[0].edge_type == EdgeType.PREREQUISITE
    # 약한 관계 수만큼 "비-선수" skip 메시지(조용한 누락 아님).
    assert sum("비-선수" in m for m in skipped) == len(_WEAK_RELATIONS)


def test_concept_graph_loader_loads_prerequisite_only(tmp_path: Path) -> None:
    """구 개념그래프 적재기: 약한 관계를 모두 섞어도 PREREQUISITE 1건만 적재·나머지 전부 skip."""
    edges: list[dict[str, object]] = [
        {"src_concept_id": "PRE", "dst_concept_id": "POST", "relation": "prerequisite"}
    ]
    for i, rel in enumerate(_WEAK_RELATIONS):
        edges.append({"src_concept_id": f"W{i}A", "dst_concept_id": f"W{i}B", "relation": rel})
    path = tmp_path / "graph.json"
    path.write_text(json.dumps({"edges": edges}), encoding="utf-8")

    records, skipped = load_backend_edges_from_graph_json(path)

    assert len(records) == 1
    assert records[0].edge_type == EdgeType.PREREQUISITE
    assert sum("비-선수" in m for m in skipped) == len(_WEAK_RELATIONS)
