"""슬라이스5 런타임 배선 테스트 — k_type_query SQL·KTypeResolver.resolve (가짜 sync 엔진).

hermetic: SQL 컴파일 + 가짜 결과. 변별력: 매칭 없으면 None(fail-soft)·있으면 k_type 문자열.
"""

from __future__ import annotations

from types import TracebackType

from whymath_backend.l4.pedagogy.k_type_resolver import KTypeResolver, k_type_query


class _FakeResult:
    def __init__(self, row: tuple[object] | None) -> None:
        self._row = row

    def first(self) -> tuple[object] | None:
        return self._row


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
        return _FakeResult(self._engine.row)


class _FakeEngine:
    def __init__(self, row: tuple[object] | None) -> None:
        self.row = row
        self.executed: list[object] = []

    def begin(self) -> _FakeConnection:
        return _FakeConnection(self)


def _compile_sql(statement: object) -> str:
    from sqlalchemy.dialects import postgresql

    return str(statement.compile(dialect=postgresql.dialect()))  # type: ignore[attr-defined]


class TestKTypeQuery:
    def test_query_shape(self) -> None:
        sql = _compile_sql(k_type_query("10공수1-02-06-1"))
        assert "learning_objective" in sql
        assert "k_type" in sql
        # 배열 멤버십 + 확정 우선 tie-break + 단건.
        assert "ANY" in sql
        assert "ORDER BY" in sql and "k_type_verified" in sql
        assert "LIMIT" in sql


class TestKTypeResolver:
    def test_resolve_returns_k_type_string(self) -> None:
        # native enum이 str 값으로 오는 경우.
        engine = _FakeEngine(row=("CONCEPT",))
        assert KTypeResolver(engine=engine).resolve("10공수1-02-06-1") == "CONCEPT"  # type: ignore[arg-type]

    def test_resolve_normalizes_enum_value(self) -> None:
        # KnowledgeType(.value 보유)로 오는 경우도 문자열로 접힌다.
        from whymath_backend.schema.enums import KnowledgeType

        engine = _FakeEngine(row=(KnowledgeType.PROCEDURE,))
        assert KTypeResolver(engine=engine).resolve("10공수1-02-06-2") == "PROCEDURE"  # type: ignore[arg-type]

    def test_resolve_none_when_no_match(self) -> None:
        engine = _FakeEngine(row=None)
        assert KTypeResolver(engine=engine).resolve("미존재-코드") is None  # type: ignore[arg-type]
