"""L2 학습 경로 — `order_learning_path` 위상정렬 단위테스트 (hermetic·PG 불요·patch 0).

`order_learning_path`는 *순수 코어*(DB·async 없음·Sequence 주입)라 patch 없이 직접 호출해
검증한다. 핵심 못 박기:
  - 빈/평면/선형 체인/diamond 위상정렬(근본 먼저)
  - **depth만으론 역순인 케이스**(위상정렬의 가치 증명 — depth 정렬과 다름)
  - tie-break 완전 결정성(weakness·depth·edge_strength·concept_id 4단)·weakness None 뒤로
  - 사이클 방어(정직한 잔여·누락 0·has_cycle/is_cycle_residual 표시)
  - 집합 밖 엣지 무시·중복 엣지 방어
  - redaction(본문 슬롯 부재)·frozen·position 단조(0..n-1 연속)
"""

from __future__ import annotations

import uuid

import pytest
from pydantic import ValidationError
from whymath_backend.l2.learning_path import (
    LearningPath,
    LearningStep,
    order_learning_path,
)
from whymath_backend.l2.prerequisite_recommendation import PrerequisiteGap


def _gap(
    cid: uuid.UUID,
    code: str | None = "UC.x",
    weakness: float | None = 0.3,
    depth: int = 1,
    strength: float | None = 0.5,
) -> PrerequisiteGap:
    """막힌 선수 1건 — agreement는 유효값(insufficient) 채움(위상정렬에 무관·스키마 충족)."""
    return PrerequisiteGap(
        concept_id=cid,
        concept_code=code,
        concept_name="선수개념",
        bkt_mastery=weakness,
        irt_mastery_proxy=weakness,
        weakness=weakness,
        agreement="insufficient",
        edge_strength=strength,
        depth=depth,
    )


def _assert_monotonic(path: LearningPath) -> None:
    """position이 0..n-1 연속 단조인지 검증(모든 케이스 공통 불변식)."""
    assert [s.position for s in path.steps] == list(range(len(path.steps)))


# ──────────────────────────────────────────────────────────────────────────
# 1. 빈 입력
# ──────────────────────────────────────────────────────────────────────────
def test_empty_input_yields_empty_path() -> None:
    path = order_learning_path([], [])
    assert path.steps == ()
    assert path.has_cycle is False


# ──────────────────────────────────────────────────────────────────────────
# 2. 평면(엣지 0) — tie-break만으로 정렬
# ──────────────────────────────────────────────────────────────────────────
def test_flat_no_edges_sorts_by_tiebreak() -> None:
    # 엣지 0 → 전부 in-degree 0 → tie-break(weakness asc → depth desc → strength desc → id).
    a, b, c = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    gaps = [
        _gap(a, weakness=0.5, depth=1, strength=0.5),
        _gap(b, weakness=0.1, depth=1, strength=0.5),  # 가장 약함 → 먼저
        _gap(c, weakness=0.3, depth=1, strength=0.5),
    ]
    path = order_learning_path(gaps, [])
    assert [s.concept_id for s in path.steps] == [b, c, a]  # weakness asc
    assert path.has_cycle is False
    _assert_monotonic(path)


# ──────────────────────────────────────────────────────────────────────────
# 3. 선형 체인 — 위상정렬(A→B→C)
# ──────────────────────────────────────────────────────────────────────────
def test_linear_chain_topological_order() -> None:
    # 내부엣지 A→B, B→C(A는 B의 선수·B는 C의 선수). 위상정렬 A,B,C.
    a, b, c = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    gaps = [_gap(a), _gap(b), _gap(c)]
    edges = [(a, b), (b, c)]
    path = order_learning_path(gaps, edges)
    assert [s.concept_id for s in path.steps] == [a, b, c]
    assert [s.position for s in path.steps] == [0, 1, 2]
    assert path.has_cycle is False


# ──────────────────────────────────────────────────────────────────────────
# 4. ★ depth만으론 역순 — 위상정렬의 가치 증명
# ──────────────────────────────────────────────────────────────────────────
def test_topo_overrides_depth_when_internal_edge_exists() -> None:
    # A(depth=2)가 B(depth=1)의 선수(내부엣지 A→B). 위상정렬은 A(근본) 먼저.
    # 그러나 depth만 정렬하면 B(depth=1)가 먼저였을 것 — 위상정렬이 이를 *뒤집는다*.
    a, b = uuid.uuid4(), uuid.uuid4()
    gaps = [_gap(a, weakness=0.3, depth=2), _gap(b, weakness=0.3, depth=1)]
    edges = [(a, b)]  # A를 알아야 B를 안다 → A 먼저.
    path = order_learning_path(gaps, edges)
    topo_order = [s.concept_id for s in path.steps]
    assert topo_order == [a, b]  # 위상정렬: A(근본·depth 큼) 먼저.
    # depth asc 정렬(추천 순서)이었다면 B(depth=1) 먼저 — 위상정렬과 *다름*을 명시.
    depth_order = [g.concept_id for g in sorted(gaps, key=lambda g: g.depth)]
    assert depth_order == [b, a]
    assert topo_order != depth_order  # 위상정렬의 가치 — 집합 내부 의존이 depth를 이긴다.


# ──────────────────────────────────────────────────────────────────────────
# 5. diamond multi-path — A 먼저·D 마지막·결정론
# ──────────────────────────────────────────────────────────────────────────
def test_diamond_multipath_deterministic() -> None:
    # A→B, A→C, B→D, C→D. A가 근본·D가 말단.
    a, b, c, d = uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    gaps = [_gap(a), _gap(b), _gap(c), _gap(d)]
    edges = [(a, b), (a, c), (b, d), (c, d)]
    path = order_learning_path(gaps, edges)
    order = [s.concept_id for s in path.steps]
    assert order[0] == a  # 근본 먼저
    assert order[-1] == d  # 말단 마지막
    assert set(order) == {a, b, c, d}
    assert path.has_cycle is False
    # 결정론 — 같은 입력 재실행 시 동일.
    path2 = order_learning_path(gaps, edges)
    assert [s.concept_id for s in path2.steps] == order


# ──────────────────────────────────────────────────────────────────────────
# 6~9. tie-break 결정성 (weakness·depth·edge_strength·concept_id)
# ──────────────────────────────────────────────────────────────────────────
def test_tiebreak_weakness_asc() -> None:
    a, b = uuid.uuid4(), uuid.uuid4()
    gaps = [_gap(a, weakness=0.6), _gap(b, weakness=0.2)]
    path = order_learning_path(gaps, [])
    assert [s.concept_id for s in path.steps] == [b, a]  # 약한 것 먼저


def test_tiebreak_depth_desc_when_same_weakness() -> None:
    # 동 weakness → depth desc(깊은=근본 먼저·추천의 asc와 반대).
    a, b = uuid.uuid4(), uuid.uuid4()
    gaps = [_gap(a, weakness=0.3, depth=1), _gap(b, weakness=0.3, depth=3)]
    path = order_learning_path(gaps, [])
    assert [s.concept_id for s in path.steps] == [b, a]  # depth 3(근본) 먼저


def test_tiebreak_edge_strength_desc_when_same_weakness_depth() -> None:
    # 동 weakness·depth → edge_strength desc(강한 선수 먼저).
    a, b = uuid.uuid4(), uuid.uuid4()
    gaps = [
        _gap(a, weakness=0.3, depth=1, strength=0.2),
        _gap(b, weakness=0.3, depth=1, strength=0.9),
    ]
    path = order_learning_path(gaps, [])
    assert [s.concept_id for s in path.steps] == [b, a]  # 강도 0.9 먼저


def test_tiebreak_concept_id_when_all_tied() -> None:
    # 전부 동률 → str(concept_id) 정렬(완전 결정론).
    a, b = uuid.uuid4(), uuid.uuid4()
    gaps = [
        _gap(a, weakness=0.3, depth=1, strength=0.5),
        _gap(b, weakness=0.3, depth=1, strength=0.5),
    ]
    path = order_learning_path(gaps, [])
    expected = sorted([a, b], key=str)
    assert [s.concept_id for s in path.steps] == expected


# ──────────────────────────────────────────────────────────────────────────
# 10. 결정론 반복 — 같은 입력 2회 동일
# ──────────────────────────────────────────────────────────────────────────
def test_determinism_repeated() -> None:
    ids = [uuid.uuid4() for _ in range(5)]
    gaps = [_gap(cid, weakness=0.3, depth=1, strength=0.5) for cid in ids]
    edges = [(ids[0], ids[1]), (ids[2], ids[3])]
    p1 = order_learning_path(gaps, edges)
    p2 = order_learning_path(gaps, edges)
    assert [s.concept_id for s in p1.steps] == [s.concept_id for s in p2.steps]


# ──────────────────────────────────────────────────────────────────────────
# 11. 사이클 방어 — 정직한 잔여
# ──────────────────────────────────────────────────────────────────────────
def test_cycle_honest_residual() -> None:
    # A→B→A(사이클) → Kahn 0건 방출 → 전부 잔여(누락 0·has_cycle·is_cycle_residual).
    a, b = uuid.uuid4(), uuid.uuid4()
    gaps = [_gap(a), _gap(b)]
    edges = [(a, b), (b, a)]
    path = order_learning_path(gaps, edges)
    assert path.has_cycle is True
    assert {s.concept_id for s in path.steps} == {a, b}  # 누락 0 — 전 노드 등장
    assert all(s.is_cycle_residual for s in path.steps)  # 전부 잔여 표시
    _assert_monotonic(path)


# ──────────────────────────────────────────────────────────────────────────
# 12. 부분 사이클 — 비사이클 먼저 위상·사이클 잔여
# ──────────────────────────────────────────────────────────────────────────
def test_partial_cycle_acyclic_first_then_residual() -> None:
    # X(독립 비사이클)·A↔B(사이클). X는 위상정렬·A·B는 잔여.
    x, a, b = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    gaps = [_gap(x), _gap(a), _gap(b)]
    edges = [(a, b), (b, a)]  # X는 엣지 없음(in-degree 0).
    path = order_learning_path(gaps, edges)
    assert path.has_cycle is True
    assert path.steps[0].concept_id == x  # 비사이클 X 먼저(위상정렬)
    assert path.steps[0].is_cycle_residual is False
    residual_ids = {s.concept_id for s in path.steps if s.is_cycle_residual}
    assert residual_ids == {a, b}  # 사이클 노드만 잔여
    assert {s.concept_id for s in path.steps} == {x, a, b}  # 누락 0
    _assert_monotonic(path)


# ──────────────────────────────────────────────────────────────────────────
# 13. 집합 밖 엣지 무시
# ──────────────────────────────────────────────────────────────────────────
def test_edge_outside_node_set_ignored() -> None:
    # 엣지 끝점(외부 ext)이 gaps에 없음 → 무시되고 정상 정렬.
    a, b, ext = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    gaps = [_gap(a, weakness=0.5), _gap(b, weakness=0.1)]
    edges = [(a, ext), (ext, b)]  # ext는 노드 집합 밖 → 둘 다 무시.
    path = order_learning_path(gaps, edges)
    # 내부 엣지 0 → tie-break(weakness asc) — b(0.1) 먼저.
    assert [s.concept_id for s in path.steps] == [b, a]
    assert path.has_cycle is False


# ──────────────────────────────────────────────────────────────────────────
# 14. 중복 엣지 방어 — indeg 한 번만
# ──────────────────────────────────────────────────────────────────────────
def test_duplicate_edge_indeg_counted_once() -> None:
    # 같은 (A,B) 2회 → indeg 한 번만 올라 B가 정상 방출(중복으로 잔여되지 않음).
    a, b = uuid.uuid4(), uuid.uuid4()
    gaps = [_gap(a), _gap(b)]
    edges = [(a, b), (a, b)]  # 중복.
    path = order_learning_path(gaps, edges)
    assert [s.concept_id for s in path.steps] == [a, b]  # 정상 위상(B 누락 0)
    assert path.has_cycle is False


# ──────────────────────────────────────────────────────────────────────────
# weakness None — tie-break 뒤로
# ──────────────────────────────────────────────────────────────────────────
def test_weakness_none_sorted_last() -> None:
    # 측정 없는(weakness None) 선수는 tie-break에서 가장 뒤로.
    a, b = uuid.uuid4(), uuid.uuid4()
    gaps = [_gap(a, weakness=None), _gap(b, weakness=0.5)]
    path = order_learning_path(gaps, [])
    assert [s.concept_id for s in path.steps] == [b, a]  # 측정 있는 b 먼저·None은 뒤


# ──────────────────────────────────────────────────────────────────────────
# redaction — 본문 슬롯 부재
# ──────────────────────────────────────────────────────────────────────────
def test_step_schema_has_no_body_fields() -> None:
    fields = set(LearningStep.model_fields)
    assert "description" not in fields
    assert "formal_definition" not in fields
    assert "intuitive_explanation" not in fields
    expected = {
        "position",
        "concept_id",
        "concept_code",
        "concept_name",
        "weakness",
        "depth",
        "edge_strength",
        "is_cycle_residual",
    }
    assert fields == expected


# ──────────────────────────────────────────────────────────────────────────
# frozen — 속성 대입 거부
# ──────────────────────────────────────────────────────────────────────────
def test_step_is_frozen() -> None:
    step = order_learning_path([_gap(uuid.uuid4())], []).steps[0]
    with pytest.raises(ValidationError):
        step.position = 99  # type: ignore[misc]


def test_path_is_frozen() -> None:
    path = order_learning_path([], [])
    with pytest.raises(ValidationError):
        path.has_cycle = True  # type: ignore[misc]
