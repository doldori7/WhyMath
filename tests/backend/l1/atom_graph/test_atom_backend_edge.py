"""원자 백본 선수엣지 → backend `concept_edge` 적재 *단위테스트*(hermetic·PG 불요).

가짜 sync 엔진으로 PG 없이 검증한다(`test_concept_backend_edge_load.py` 패턴):
  ① 로딩 — from_code/to_code/relation_subtype/strength·prerequisite만·self/누락 skip·evidence 미유입
  ② code→UUID 해석·orphan skip·N+1 0
  ③ upsert SQL — ON CONFLICT(from,to,type)·relation_subtype SET·edge_id/created_at 미-SET
  ④ populate — 멱등·orphan 제외
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from types import TracebackType

import pytest

from whymath_backend.config import Settings
from whymath_backend.l1.atom_graph.atom_backend_edge import (
    AtomBackendEdgeRecord,
    AtomBackendEdgeStore,
    load_atom_edges_from_graph_json,
    populate_atom_edges,
)
from whymath_backend.schema.enums import EdgeType

_PRE = "2수01-01-1"
_POST = "2수01-01-2"
_ORPHAN = "없는-원자"

_UUID_PRE = uuid.uuid4()
_UUID_POST = uuid.uuid4()


def _pg_dialect() -> object:
    from sqlalchemy.dialects import postgresql

    return postgresql.dialect()


def _compile(statement: object) -> str:
    return str(statement.compile(dialect=_pg_dialect()))  # type: ignore[attr-defined]


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
        compiled = _compile(statement)
        if (
            "SELECT" in compiled
            and "concept.code" in compiled
            and "INSERT" not in compiled
        ):
            return _FakeResult(self._engine.code_rows)
        return _FakeResult([])


class _FakeEngine:
    def __init__(self, code_rows: list[object] | None = None) -> None:
        self.executed: list[object] = []
        self.code_rows: list[object] = (
            code_rows
            if code_rows is not None
            else [_Row(_PRE, _UUID_PRE), _Row(_POST, _UUID_POST)]
        )

    def begin(self) -> _FakeConnection:
        return _FakeConnection(self)

    def connect(self) -> _FakeConnection:
        return _FakeConnection(self)


def _fake_store(
    code_rows: list[object] | None = None,
) -> tuple[AtomBackendEdgeStore, _FakeEngine]:
    engine = _FakeEngine(code_rows)
    store = AtomBackendEdgeStore(engine=engine)  # type: ignore[arg-type]
    return store, engine


def _record(
    src: str = _PRE,
    dst: str = _POST,
    *,
    edge_strength: float | None = 0.8,
    relation_subtype: str | None = "원본",
) -> AtomBackendEdgeRecord:
    return AtomBackendEdgeRecord(
        from_code=src,
        to_code=dst,
        edge_type=EdgeType.PREREQUISITE,
        edge_strength=edge_strength,
        relation_subtype=relation_subtype,
    )


# ──────────────────────────────────────────────────────────────────────────
# ① 로딩
# ──────────────────────────────────────────────────────────────────────────
class TestLoad:
    def _write(self, tmp_path: Path, edges: list[dict[str, object]]) -> Path:
        path = tmp_path / "graph.json"
        path.write_text(
            json.dumps({"concepts": [], "edges": edges}, ensure_ascii=False),
            encoding="utf-8",
        )
        return path

    def test_maps_direction_subtype_strength(self, tmp_path: Path) -> None:
        path = self._write(
            tmp_path,
            [
                {
                    "from_code": _PRE,
                    "to_code": _POST,
                    "relation": "prerequisite",
                    "relation_subtype": "소단원내",
                    "strength": 0.75,
                    "evidence": "원자 백본 v1",
                }
            ],
        )
        records, skipped = load_atom_edges_from_graph_json(path)
        assert len(records) == 1 and skipped == []
        rec = records[0]
        assert rec.from_code == _PRE and rec.to_code == _POST
        assert rec.edge_type == EdgeType.PREREQUISITE
        assert rec.edge_strength == 0.75
        assert rec.relation_subtype == "소단원내"

    def test_evidence_no_slot(self) -> None:
        fields = set(AtomBackendEdgeRecord.__dataclass_fields__)
        assert "evidence" not in fields and "notes" not in fields
        assert fields == {
            "from_code",
            "to_code",
            "edge_type",
            "edge_strength",
            "relation_subtype",
        }

    def test_non_prerequisite_skipped(self, tmp_path: Path) -> None:
        path = self._write(
            tmp_path,
            [{"from_code": _PRE, "to_code": _POST, "relation": "analogous_to"}],
        )
        records, skipped = load_atom_edges_from_graph_json(path)
        assert records == [] and any("비-선수" in m for m in skipped)

    def test_self_edge_skipped(self, tmp_path: Path) -> None:
        path = self._write(
            tmp_path,
            [{"from_code": _PRE, "to_code": _PRE, "relation": "prerequisite"}],
        )
        records, skipped = load_atom_edges_from_graph_json(path)
        assert records == [] and any("self-edge" in m for m in skipped)

    def test_missing_endpoint_skipped(self, tmp_path: Path) -> None:
        path = self._write(tmp_path, [{"from_code": _PRE, "relation": "prerequisite"}])
        records, skipped = load_atom_edges_from_graph_json(path)
        assert records == [] and any("양끝 code 누락" in m for m in skipped)

    @pytest.mark.parametrize("bad", ["", "  ", None])
    def test_blank_strength_none(self, tmp_path: Path, bad: object) -> None:
        path = self._write(
            tmp_path,
            [
                {
                    "from_code": _PRE,
                    "to_code": _POST,
                    "relation": "prerequisite",
                    "strength": bad,
                }
            ],
        )
        records, _ = load_atom_edges_from_graph_json(path)
        assert records[0].edge_strength is None

    def test_missing_subtype_none(self, tmp_path: Path) -> None:
        path = self._write(
            tmp_path,
            [{"from_code": _PRE, "to_code": _POST, "relation": "prerequisite"}],
        )
        records, _ = load_atom_edges_from_graph_json(path)
        assert records[0].relation_subtype is None


# ──────────────────────────────────────────────────────────────────────────
# ② 해석·orphan·N+1
# ──────────────────────────────────────────────────────────────────────────
class TestResolution:
    def test_resolves_both(self) -> None:
        store, engine = _fake_store()
        loaded, skipped = store.populate([_record()])
        assert loaded == 1 and skipped == []
        assert len(engine.executed) == 2  # SELECT + INSERT
        assert "INSERT INTO concept_edge" in _compile(engine.executed[1])

    def test_orphan_skipped(self) -> None:
        store, engine = _fake_store()
        loaded, skipped = store.populate([_record(dst=_ORPHAN)])
        assert loaded == 0 and any("orphan" in m for m in skipped)
        assert len(engine.executed) == 1  # SELECT만

    def test_no_n_plus_one(self) -> None:
        store, engine = _fake_store()
        store.populate([_record(), _record(), _record()])
        selects = [
            s
            for s in engine.executed
            if "concept.code" in _compile(s) and "INSERT" not in _compile(s)
        ]
        assert len(selects) == 1


# ──────────────────────────────────────────────────────────────────────────
# ③ upsert SQL
# ──────────────────────────────────────────────────────────────────────────
class TestUpsert:
    def test_on_conflict_composite_and_subtype_set(self) -> None:
        store, engine = _fake_store()
        store.populate([_record()])
        sql = _compile(engine.executed[1])
        assert "ON CONFLICT" in sql
        for col in ("from_concept_id", "to_concept_id", "edge_type"):
            assert col in sql
        # SET 절만 분리 — 뒤따르는 RETURNING concept_edge.edge_id는 PK 대입이 아니라
        # 신규행 PK 회신이므로 잘라낸다(구 test_concept_backend_edge_load 패턴 동일).
        set_clause = sql.split("DO UPDATE SET", 1)[1].split("RETURNING", 1)[0]
        assert "edge_strength" in set_clause
        assert "relation_subtype" in set_clause
        assert "edge_id" not in set_clause
        assert "created_at" not in set_clause

    def test_omits_gap_signal_notes(self) -> None:
        store, engine = _fake_store()
        store.populate([_record()])
        sql = _compile(engine.executed[1])
        assert "typical_gap_signal" not in sql
        assert "evidence" not in sql


# ──────────────────────────────────────────────────────────────────────────
# ④ populate
# ──────────────────────────────────────────────────────────────────────────
class TestPopulate:
    def test_excludes_orphans(self) -> None:
        store, _ = _fake_store()
        assert populate_atom_edges([_record(), _record(dst=_ORPHAN)], store=store) == 1

    def test_empty_noop(self) -> None:
        store, engine = _fake_store()
        assert populate_atom_edges([], store=store) == 0
        assert engine.executed == []

    def test_default_settings(self) -> None:
        assert isinstance(AtomBackendEdgeStore()._resolved_settings, Settings)
