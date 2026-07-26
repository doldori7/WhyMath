"""슬라이스4 L2 evidence 라이터 테스트 — EvidenceEventStore.log/fetch (가짜 sync 엔진).

hermetic: 컴파일된 SQL 단언(PG 불요). 라이터는 암호화된 바이트만 받고 event_id는 DB autoincrement.
"""

from __future__ import annotations

from types import TracebackType
from uuid import uuid4

from whymath_backend.l2.evidence_event_store import EvidenceEventStore


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

    def execute(self, statement: object) -> _FakeResult:
        self._engine.executed.append(statement)
        return _FakeResult()


class _FakeResult:
    def __iter__(self) -> object:
        return iter([])


class _FakeEngine:
    def __init__(self) -> None:
        self.executed: list[object] = []

    def begin(self) -> _FakeConnection:
        return _FakeConnection(self)


def _compile_sql(statement: object) -> str:
    from sqlalchemy.dialects import postgresql

    return str(statement.compile(dialect=postgresql.dialect()))  # type: ignore[attr-defined]


class TestEvidenceEventStore:
    def test_log_inserts_without_event_id(self) -> None:
        engine = _FakeEngine()
        n = EvidenceEventStore(engine=engine).log(  # type: ignore[arg-type]
            session_id=uuid4(),
            objective_id="10공수1-이차함수-최대최소:OBJ-01",
            k_type="CONCEPT",
            event_type="COUNTEREXAMPLE_GEN",
            meta={"item": "diag_item:0"},
            payload_encrypted=b"ciphertext",
            payload_nonce=b"nonce12bytes",
        )
        assert n == 1
        sql = _compile_sql(engine.executed[0])
        assert "INSERT INTO evidence_event" in sql
        # INSERT 컬럼 목록(VALUES 이전)만 검사 — RETURNING의 event_id/time과 구분.
        insert_cols = sql.split(" VALUES")[0]
        # 암호 컬럼은 실린다(라이터는 바이트만 받음).
        assert "payload_encrypted" in insert_cols and "payload_nonce" in insert_cols
        # event_id는 DB autoincrement — INSERT 컬럼 목록에 없어야 한다(RETURNING엔 있어도 무방).
        assert "event_id" not in insert_cols

    def test_meta_only_log(self) -> None:
        # cipher 없을 때 경로 — 암호 컬럼 None(메타 전용). 예외 없이 INSERT.
        engine = _FakeEngine()
        n = EvidenceEventStore(engine=engine).log(  # type: ignore[arg-type]
            session_id=uuid4(),
            objective_id="U:OBJ-01",
            k_type="CONCEPT",
            event_type="COUNTEREXAMPLE_GEN",
            meta={"item": "diag_item:0"},
        )
        assert n == 1

    def test_fetch_by_objective_compiles_select(self) -> None:
        engine = _FakeEngine()
        rows = EvidenceEventStore(engine=engine).fetch_by_objective("U:OBJ-01")  # type: ignore[arg-type]
        assert rows == []
        sql = _compile_sql(engine.executed[0])
        assert "SELECT" in sql and "FROM evidence_event" in sql
