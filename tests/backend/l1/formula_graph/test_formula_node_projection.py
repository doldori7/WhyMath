"""수식 메타 PG 프로젝션 적재 *단위테스트* — Phase 5a (hermetic·PG 불요).

`FormulaNodeStore`의 실 라운드트립은 통합테스트로 미루고, 여기서는 PG 없이 검증 가능한 것만
못 박는다(`test_problem_type_node_projection.py` 가짜 엔진 패턴 미러):

  ① graph.json 로딩 — formula_id 키 + 안전 메타(latex/dsl/aliases/signature)
  ② 필수 필드 누락 graceful — formula_id/name_ko/family/latex/dsl 누락이면 skip
  ③ upsert SQL 구성 — ON CONFLICT(formula_id)·review_status 상수·안전 메타 컬럼(enum 없음)
  ④ populate — 전 레코드 upsert(횟수=레코드 수)
"""

from __future__ import annotations

import json
from pathlib import Path
from types import TracebackType

from whymath_backend.db.models.formula_node import FORMULA_REVIEW_STATUS_DEFAULT
from whymath_backend.l1.formula_graph.formula_node_projection import (
    FormulaNodeRecord,
    FormulaNodeStore,
    load_formulas_from_graph_json,
    populate_formula_nodes,
)


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

    def execute(self, statement: object) -> None:
        self._engine.executed.append(statement)
        return None


class _FakeEngine:
    """SQLAlchemy sync Engine 최소 흉내 — begin() + 실행 statement 기록."""

    def __init__(self) -> None:
        self.executed: list[object] = []

    def begin(self) -> _FakeConnection:
        return _FakeConnection(self)


def _fake_store() -> tuple[FormulaNodeStore, _FakeEngine]:
    engine = _FakeEngine()
    store = FormulaNodeStore(engine=engine)  # type: ignore[arg-type]
    return store, engine


def _write_graph(tmp_path: Path, formulas: list[dict[str, object]]) -> Path:
    path = tmp_path / "graph.json"
    path.write_text(json.dumps({"formulas": formulas}, ensure_ascii=False), encoding="utf-8")
    return path


def _record(formula_id: str = "formula.quadratic.roots") -> FormulaNodeRecord:
    return FormulaNodeRecord(
        formula_id=formula_id,
        name_ko="근의 공식",
        family="근의공식",
        latex="x = \\frac{-b \\pm \\sqrt{b^2-4ac}}{2a}",
        dsl="x == (-b + sqrt(b**2 - 4*a*c))/(2*a)",
        canonical_signature=None,
        aliases=(),
        standard_codes=("9수02-15",),
    )


def _compile(stmt: object) -> str:
    return str(stmt.compile(compile_kwargs={"literal_binds": False}))  # type: ignore[attr-defined]


class TestLoadFromGraphJson:
    def test_loads_safe_meta(self, tmp_path: Path) -> None:
        path = _write_graph(
            tmp_path,
            [
                {
                    "formula_id": "formula.geometry.pythagorean",
                    "name_ko": "피타고라스 정리",
                    "family": "기하공식",
                    "latex": "a^2 + b^2 = c^2",
                    "dsl": "a**2 + b**2 == c**2",
                    "aliases": ["c^2 = a^2 + b^2"],
                    "standard_codes": ["9수04-09"],
                }
            ],
        )
        rec = load_formulas_from_graph_json(path)[0]
        assert rec.formula_id == "formula.geometry.pythagorean"
        assert rec.family == "기하공식"
        assert rec.dsl == "a**2 + b**2 == c**2"
        assert rec.aliases == ("c^2 = a^2 + b^2",)
        assert rec.standard_codes == ("9수04-09",)
        assert rec.canonical_signature is None

    def test_missing_required_skipped(self, tmp_path: Path) -> None:
        path = _write_graph(
            tmp_path,
            [
                {
                    "formula_id": "formula.ok",
                    "name_ko": "x",
                    "family": "F",
                    "latex": "a=b",
                    "dsl": "a == b",
                },
                {"formula_id": "formula.no-dsl", "name_ko": "x", "family": "F", "latex": "a=b"},
            ],
        )
        loaded = load_formulas_from_graph_json(path)
        assert [r.formula_id for r in loaded] == ["formula.ok"]

    def test_signature_optional_preserved(self, tmp_path: Path) -> None:
        path = _write_graph(
            tmp_path,
            [
                {
                    "formula_id": "formula.x",
                    "name_ko": "x",
                    "family": "F",
                    "latex": "a=b",
                    "dsl": "a == b",
                    "canonical_signature": "sig123",
                }
            ],
        )
        assert load_formulas_from_graph_json(path)[0].canonical_signature == "sig123"


class TestUpsertSql:
    def test_upsert_on_conflict_formula_id(self) -> None:
        store, engine = _fake_store()
        store.upsert(_record())
        compiled = _compile(engine.executed[0])
        assert "INSERT INTO formula_node" in compiled
        assert "ON CONFLICT" in compiled
        assert "(formula_id)" in compiled or "formula_node.formula_id" in compiled

    def test_upsert_includes_safe_meta_columns(self) -> None:
        store, engine = _fake_store()
        store.upsert(_record())
        compiled = _compile(engine.executed[0])
        for col in ("formula_id", "name_ko", "family", "latex", "dsl", "review_status"):
            assert col in compiled

    def test_review_status_is_ai_estimated_constant(self) -> None:
        assert FORMULA_REVIEW_STATUS_DEFAULT == "ai_estimated"


class TestPopulate:
    def test_populate_upserts_all(self) -> None:
        store, engine = _fake_store()
        count = populate_formula_nodes([_record("formula.a"), _record("formula.b")], store=store)
        assert count == 2
        assert len(engine.executed) == 2
