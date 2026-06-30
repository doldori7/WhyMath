"""원자 백본 적재 진입점 `populate_atom_backbone` *단위테스트*(hermetic·PG 불요).

가짜 sync 엔진 기반 store를 주입해 노드→parent→엣지 순서·리포트 집계를 PG 없이 검증한다.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from types import TracebackType

import pytest

from whymath_backend.l1.atom_graph.atom_backend_concept import AtomBackendConceptStore
from whymath_backend.l1.atom_graph.atom_backend_edge import AtomBackendEdgeStore
from whymath_backend.l1.atom_graph.populate import (
    AtomBackboneCycleError,
    AtomBackbonePopulateReport,
    populate_atom_backbone,
)

_UNIT = "초수연-U1"
_SUBUNIT = "초수연-U1-S1"
_ATOM_A = "2수01-01-1"
_ATOM_B = "2수01-01-2"

_UUIDS = {
    _UNIT: uuid.uuid4(),
    _SUBUNIT: uuid.uuid4(),
    _ATOM_A: uuid.uuid4(),
    _ATOM_B: uuid.uuid4(),
}


def _pg_dialect() -> object:
    from sqlalchemy.dialects import postgresql

    return postgresql.dialect()


class _Row:
    def __init__(self, code: str, concept_id: uuid.UUID) -> None:
        self.code = code
        self.concept_id = concept_id


class _FakeResult:
    def __init__(self, rows: list[object]) -> None:
        self._rows = rows

    def all(self) -> list[object]:
        return self._rows


class _FakeConnection:
    def __init__(self, engine: _FakeEngine) -> None:
        self._engine = engine

    def __enter__(self) -> _FakeConnection:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        return None

    def execute(self, statement: object, parameters: object = None) -> _FakeResult:
        self._engine.executed.append(statement)
        compiled = str(statement.compile(dialect=_pg_dialect()))  # type: ignore[attr-defined]
        if "SELECT" in compiled and "concept.code" in compiled and "INSERT" not in compiled:
            return _FakeResult(self._engine.code_rows)
        return _FakeResult([])


class _FakeEngine:
    def __init__(self) -> None:
        self.executed: list[object] = []
        self.code_rows: list[object] = [_Row(c, u) for c, u in _UUIDS.items()]

    def begin(self) -> _FakeConnection:
        return _FakeConnection(self)

    def connect(self) -> _FakeConnection:
        return _FakeConnection(self)


def _write_corpus(tmp_path: Path) -> Path:
    concepts = [
        {"code": _UNIT, "name": "수와 연산", "level": "단원", "parent_code": None},
        {"code": _SUBUNIT, "name": "100까지", "level": "소단원", "parent_code": _UNIT},
        {
            "code": _ATOM_A,
            "name": "일대일 대응",
            "level": "세부개념",
            "parent_code": _SUBUNIT,
            "intrinsic_difficulty": 1,
        },
        {
            "code": _ATOM_B,
            "name": "기수 원리",
            "level": "세부개념",
            "parent_code": _SUBUNIT,
            "intrinsic_difficulty": 2,
        },
    ]
    edges = [
        {
            "from_code": _ATOM_A,
            "to_code": _ATOM_B,
            "relation": "prerequisite",
            "relation_subtype": "원본",
            "strength": 0.8,
        },
    ]
    path = tmp_path / "graph.json"
    path.write_text(
        json.dumps({"concepts": concepts, "edges": edges}, ensure_ascii=False),
        encoding="utf-8",
    )
    return path


def test_populate_atom_backbone_report(tmp_path: Path) -> None:
    path = _write_corpus(tmp_path)
    c_store = AtomBackendConceptStore(engine=_FakeEngine())  # type: ignore[arg-type]
    e_store = AtomBackendEdgeStore(engine=_FakeEngine())  # type: ignore[arg-type]
    report = populate_atom_backbone(path, concept_store=c_store, edge_store=e_store)
    assert isinstance(report, AtomBackbonePopulateReport)
    assert report.concepts_loaded == 4
    assert report.parents_skipped == 0  # 단원=root·나머지 3은 parent 해소
    assert report.edges_loaded == 1
    assert report.edges_skipped == 0


def test_populate_atom_backbone_orphan_edge(tmp_path: Path) -> None:
    # to_code가 노드에 없으면 orphan → edges_skipped로 드러남.
    concepts = [
        {
            "code": _ATOM_A,
            "name": "일대일",
            "level": "세부개념",
            "parent_code": None,
            "intrinsic_difficulty": 1,
        },
    ]
    edges = [
        {
            "from_code": _ATOM_A,
            "to_code": "없는-원자",
            "relation": "prerequisite",
            "strength": 0.5,
        },
    ]
    path = tmp_path / "graph.json"
    path.write_text(json.dumps({"concepts": concepts, "edges": edges}), encoding="utf-8")

    class _OneRowEngine(_FakeEngine):
        def __init__(self) -> None:
            super().__init__()
            self.code_rows = [_Row(_ATOM_A, _UUIDS[_ATOM_A])]

    c_store = AtomBackendConceptStore(engine=_OneRowEngine())  # type: ignore[arg-type]
    e_store = AtomBackendEdgeStore(engine=_OneRowEngine())  # type: ignore[arg-type]
    report = populate_atom_backbone(path, concept_store=c_store, edge_store=e_store)
    assert report.concepts_loaded == 1
    assert report.edges_loaded == 0
    assert report.edges_skipped == 1  # orphan(to 미적재)


def test_populate_atom_backbone_rejects_cycle(tmp_path: Path) -> None:
    # 선수엣지에 순환(A→B→A)이 있으면 적재를 거부한다(DAG 방어선·hard fail).
    concepts = [
        {"code": _ATOM_A, "name": "일대일", "level": "세부개념", "parent_code": None},
        {"code": _ATOM_B, "name": "기수", "level": "세부개념", "parent_code": None},
    ]
    edges = [
        {"from_code": _ATOM_A, "to_code": _ATOM_B, "relation": "prerequisite", "strength": 0.8},
        {"from_code": _ATOM_B, "to_code": _ATOM_A, "relation": "prerequisite", "strength": 0.8},
    ]
    path = tmp_path / "graph.json"
    path.write_text(json.dumps({"concepts": concepts, "edges": edges}), encoding="utf-8")

    c_store = AtomBackendConceptStore(engine=_FakeEngine())  # type: ignore[arg-type]
    e_store = AtomBackendEdgeStore(engine=_FakeEngine())  # type: ignore[arg-type]
    with pytest.raises(AtomBackboneCycleError) as exc_info:
        populate_atom_backbone(path, concept_store=c_store, edge_store=e_store)
    # 순환 경로가 노출돼 디버깅 가능해야 한다(닫힘 노드 반복 포함).
    assert exc_info.value.cycle[0] == exc_info.value.cycle[-1]
    assert set(exc_info.value.cycle) == {_ATOM_A, _ATOM_B}


def test_populate_atom_backbone_self_loop_not_in_records(tmp_path: Path) -> None:
    # self-edge(A→A)는 로딩 단계에서 skip되므로 cycle 검사에 도달하지 않는다(레코드 0건).
    concepts = [
        {"code": _ATOM_A, "name": "일대일", "level": "세부개념", "parent_code": None},
    ]
    edges = [
        {"from_code": _ATOM_A, "to_code": _ATOM_A, "relation": "prerequisite", "strength": 0.8},
    ]
    path = tmp_path / "graph.json"
    path.write_text(json.dumps({"concepts": concepts, "edges": edges}), encoding="utf-8")

    class _OneRowEngine(_FakeEngine):
        def __init__(self) -> None:
            super().__init__()
            self.code_rows = [_Row(_ATOM_A, _UUIDS[_ATOM_A])]

    c_store = AtomBackendConceptStore(engine=_OneRowEngine())  # type: ignore[arg-type]
    e_store = AtomBackendEdgeStore(engine=_OneRowEngine())  # type: ignore[arg-type]
    # cycle 게이트는 raise하지 않는다 — self-edge는 적재 레코드(edge_records)에 들어오지 않아
    # cycle 검사 대상이 0건이다(self-edge skip은 로딩 단계에서 처리·리포트엔 미반영).
    report = populate_atom_backbone(path, concept_store=c_store, edge_store=e_store)
    assert report.edges_loaded == 0
    assert report.edges_skipped == 0  # 레코드 0건(self-edge는 로딩에서 이미 제외)
