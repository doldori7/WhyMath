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
    derive_ordering_edges,
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
    assert path.ordering_edge_count == 0
    assert path.ordering_basis == "empty"


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
    assert path.ordering_edge_count == 0
    assert path.ordering_basis == "tiebreak_only"
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
    assert path.ordering_edge_count == 2  # A→B, B→C
    assert path.ordering_basis == "topological"


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
# PATH-02 — ordering_edge_count·ordering_basis (has_cycle과 대칭인 정직 표기)
# ──────────────────────────────────────────────────────────────────────────
def test_ordering_basis_topological_vs_tiebreak_only_with_identical_steps() -> None:
    """핵심 변별력: `steps` 순서가 완전히 같아도 제약 유무에 따라 두 필드가 갈라진다.

    A(weakness=0.1)가 B(weakness=0.5)보다 tiebreak상 항상 먼저다. 여기에 A→B 내부엣지를
    더해도(위상정렬도 A를 먼저 방출) `steps` 순서는 *우연히* 동일하게 나온다 — 이 결함은
    순서만 비교해서는 원리적으로 검출 불가능하고, ordering_edge_count·ordering_basis만이
    "제약이 있어서 A가 먼저였는지, tiebreak만으로 그랬는지"를 구분해낸다.
    """
    a, b = uuid.uuid4(), uuid.uuid4()
    gaps = [_gap(a, weakness=0.1), _gap(b, weakness=0.5)]

    no_edge = order_learning_path(gaps, [])
    with_edge = order_learning_path(gaps, [(a, b)])

    # steps 순서는 완전히 동일 — 순서 비교만으로는 두 경우를 구분할 수 없다.
    assert (
        [s.concept_id for s in no_edge.steps]
        == [s.concept_id for s in with_edge.steps]
        == [
            a,
            b,
        ]
    )

    assert no_edge.ordering_edge_count == 0
    assert no_edge.ordering_basis == "tiebreak_only"

    assert with_edge.ordering_edge_count == 1
    assert with_edge.ordering_basis == "topological"


def test_ordering_edge_count_excludes_outside_node_set_edges() -> None:
    # test_edge_outside_node_set_ignored와 동일 fixture — 집합 밖 엣지는 count에도 안 잡힘.
    a, b, ext = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    gaps = [_gap(a, weakness=0.5), _gap(b, weakness=0.1)]
    edges = [(a, ext), (ext, b)]
    path = order_learning_path(gaps, edges)
    assert path.ordering_edge_count == 0
    assert path.ordering_basis == "tiebreak_only"


def test_ordering_edge_count_excludes_duplicate_edges() -> None:
    # test_duplicate_edge_indeg_counted_once와 동일 fixture — 중복 (A,B)는 count 1로만.
    a, b = uuid.uuid4(), uuid.uuid4()
    gaps = [_gap(a), _gap(b)]
    edges = [(a, b), (a, b)]
    path = order_learning_path(gaps, edges)
    assert path.ordering_edge_count == 1
    assert path.ordering_basis == "topological"


def test_ordering_basis_cycle_residual_still_topological_when_edges_exist() -> None:
    # 사이클(§11 fixture)도 내부 엣지가 실제 존재하므로 topological — has_cycle과 독립 축.
    a, b = uuid.uuid4(), uuid.uuid4()
    gaps = [_gap(a), _gap(b)]
    edges = [(a, b), (b, a)]
    path = order_learning_path(gaps, edges)
    assert path.has_cycle is True
    assert path.ordering_edge_count == 2
    assert path.ordering_basis == "topological"


def test_path_ordering_fields_are_frozen() -> None:
    path = order_learning_path([_gap(uuid.uuid4())], [])
    with pytest.raises(ValidationError):
        path.ordering_basis = "empty"  # type: ignore[misc]


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


# ──────────────────────────────────────────────────────────────────────────
# PATH-03 — 전이 순서 엣지(`derive_ordering_edges`) 재현·변별력
# ──────────────────────────────────────────────────────────────────────────
# acceptance① 재현: A→X→B(X는 막힌 선수 아님) 픽스처에서 *현행(PATH-03 이전) 직접 엣지만*
# 공급하면 A·B 사이 순서를 못 잡는다 — internal_edges=[]는 옛 `fetch_internal_prerequisite_
# edges([A,B])`가 이 그래프에서 실제로 돌려줬을 값과 동일하다(X가 집합 밖이라 A→X·X→B 둘 다
# where에서 배제).
def test_pre_path03_direct_edges_only_cannot_order_transitive_pair() -> None:
    a, b = uuid.uuid4(), uuid.uuid4()
    # B가 A보다 약함(weakness 낮음) → 엣지 없이 tiebreak만 적용되면 B가 먼저 나온다.
    gaps = [_gap(a, weakness=0.5), _gap(b, weakness=0.1)]
    path = order_learning_path(gaps, [])  # 옛 경로가 A→X→B에서 실제로 공급하던 빈 엣지.
    assert path.ordering_edge_count == 0
    assert path.ordering_basis == "tiebreak_only"
    assert [s.concept_id for s in path.steps] == [b, a]  # weakness asc — B 먼저(순서 못 잡음).


# acceptance④ 변별력: 같은 A·B 픽스처에 `derive_ordering_edges`가 도출한 전이 엣지를 공급하면
# 순서가 *실제로 역전*된다(A가 X를 경유해 B의 선수이므로 위상정렬은 A를 먼저 방출해야 한다).
def test_derive_ordering_edges_reverses_order_for_transitive_pair() -> None:
    a, b, x = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    # fetch_ordering_subgraph가 이 A→X→B 그래프에서 실제로 돌려줄 raw 삼중항 — B에서 시작해
    # 선수 방향으로 X(1홉)·A(2홉)까지 도달.
    subgraph = [(b, x, 1), (b, a, 2)]
    edges = derive_ordering_edges([a, b], subgraph)
    assert edges == [(a, b)]  # X는 집합 밖이라 걸러지고 A→B만 남는다.

    gaps = [_gap(a, weakness=0.5), _gap(b, weakness=0.1)]
    path = order_learning_path(gaps, edges)
    assert path.ordering_edge_count == 1
    assert path.ordering_basis == "topological"
    # before(위 테스트)는 [b, a](tiebreak) — after는 [a, b](위상정렬이 tiebreak를 뒤집는다).
    assert [s.concept_id for s in path.steps] == [a, b]


class TestDeriveOrderingEdges:
    """`derive_ordering_edges` 순수 함수 단위(hermetic·DB 무관) — 필터·dedup·날조 방지."""

    def test_ancestor_outside_gap_set_filtered_out(self) -> None:
        a, x = uuid.uuid4(), uuid.uuid4()
        # ancestor(x)가 concept_ids 밖 — 순서 엣지 아님(경유지일 뿐, 조상 자체가 아님).
        assert derive_ordering_edges([a], [(a, x, 1)]) == []

    def test_descendant_outside_gap_set_filtered_out(self) -> None:
        a, b = uuid.uuid4(), uuid.uuid4()
        # descendant(b)가 concept_ids 밖 — 호출부 계약상 발생 안 하나 방어적으로 걸러진다.
        assert derive_ordering_edges([a], [(b, a, 1)]) == []

    def test_self_loop_excluded_defensively(self) -> None:
        a = uuid.uuid4()
        assert derive_ordering_edges([a], [(a, a, 3)]) == []

    def test_multiple_paths_to_same_pair_dedup_to_one_edge(self) -> None:
        a, b = uuid.uuid4(), uuid.uuid4()
        # 서로 다른 경로/깊이로 같은 (a,b) 쌍에 두 번 도달해도 결과는 1건.
        edges = derive_ordering_edges([a, b], [(b, a, 2), (b, a, 4)])
        assert edges == [(a, b)]

    def test_no_synthetic_edge_strength_in_output(self) -> None:
        """acceptance⑤ — 반환 튜플은 항상 (from, to) 2요소뿐, hops·강도 합성값이 섞이지 않는다."""
        a, b = uuid.uuid4(), uuid.uuid4()
        edges = derive_ordering_edges([a, b], [(b, a, 3)])
        assert edges == [(a, b)]
        assert all(len(e) == 2 for e in edges)

    def test_empty_subgraph_yields_no_edges(self) -> None:
        assert derive_ordering_edges([uuid.uuid4(), uuid.uuid4()], []) == []

    def test_deterministic_sort_order(self) -> None:
        """반환 순서가 (str(ancestor), str(descendant)) 정렬 — 호출 재현성."""
        a, b, c, d = uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        subgraph = [(b, a, 1), (d, c, 1)]
        edges = derive_ordering_edges([a, b, c, d], subgraph)
        assert edges == sorted(edges, key=lambda e: (str(e[0]), str(e[1])))


# ──────────────────────────────────────────────────────────────────────────
# PATH-03 acceptance③ — 후보 집합 불변(순서만 바뀌고 gap 개수·구성은 그대로)
# ──────────────────────────────────────────────────────────────────────────
class TestGapCandidateSetInvariant:
    """`derive_ordering_edges`가 공급하는 엣지가 무엇이든 `order_learning_path`의 출력
    concept_id 집합은 입력 `gaps`의 concept_id 집합과 항상 같다 — 순서만 바뀌고
    `recommend_prerequisite_gaps`가 고른 막힌 선수의 개수·구성 자체는 이 태스크로 바뀌지
    않는다(학생에게 제시되는 후보 집합 불변)."""

    def test_transitive_edges_reorder_but_do_not_change_membership(self) -> None:
        a, b, c = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        gaps = [_gap(a), _gap(b), _gap(c)]
        subgraph = [(c, b, 1), (c, a, 2), (b, a, 1)]  # A→B→C 전이 체인.
        edges = derive_ordering_edges([a, b, c], subgraph)
        path = order_learning_path(gaps, edges)
        assert {s.concept_id for s in path.steps} == {a, b, c}
        assert len(path.steps) == len(gaps)

    def test_edges_referencing_ids_outside_gaps_do_not_leak_extra_steps(self) -> None:
        """`derive_ordering_edges`가 실수로 집합 밖 concept_id를 담아도(방어적 케이스)
        `order_learning_path`는 `gaps`에 없는 노드를 스텝으로 만들지 않는다."""
        a, b, outside = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        gaps = [_gap(a), _gap(b)]
        # outside를 억지로 섞은 엣지 리스트 — order_learning_path의 기존 "집합 밖 엣지 무시"
        # 방어(구현 변경 0)가 그대로 적용되는지 회귀 확인.
        edges = [(a, b), (b, outside)]
        path = order_learning_path(gaps, edges)
        assert {s.concept_id for s in path.steps} == {a, b}
