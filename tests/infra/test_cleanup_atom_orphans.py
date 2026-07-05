"""cleanup_atom_orphans.py 단위 테스트 (hermetic · fake connection).

가드 스크립트의 핵심 안전 계약을 실 DB 없이 검증한다:
  ① dry-run 기본 — DELETE 0 (--confirm 없으면 삭제 문구가 실행되지 않음)
  ② --confirm — orphan 코드만 삭제 (canonical은 절대 대상 아님)
  ③ FK 안전 순서 — concept orphan 삭제 전 concept_edge·problem_concept 먼저
  ④ 0-orphan — 무동작

실 DB DELETE 자체는 표준 SQL이라 fake connection이 실행 SQL을 기록하는 것으로 충분.
canonical 대조는 정본 graph.json 코드 집합을 주입(진단 스크립트 `_canonical_codes` 재사용).
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

# ---- cleanup 모듈 로드 (sys.path 의존 없이·tests/infra 관례) ----------------
_CLEANUP_PATH = Path(__file__).resolve().parents[2] / "scripts" / "cleanup_atom_orphans.py"
_spec = importlib.util.spec_from_file_location("cleanup_atom_orphans", _CLEANUP_PATH)
assert _spec is not None and _spec.loader is not None
cleanup = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cleanup)


# canonical(정본) 코드 집합 — 정상 원자 1개. orphan은 이 집합에 없는 '미적' 코드.
_CANONICAL = {"12미적Ⅰ-01-01-1"}
_ORPHAN = "미적1-raw-01"  # 정본에 없는 raw 잔재(orphan)


class _FakeResult:
    def __init__(self, rows: list[tuple[Any, ...]], rowcount: int = 0) -> None:
        self._rows = rows
        self.rowcount = rowcount

    def __iter__(self) -> Any:
        return iter(self._rows)


class _FakeConn:
    """execute를 가로채 SELECT엔 시드 행을, DELETE엔 rowcount를 돌려주고 SQL을 기록."""

    def __init__(self) -> None:
        self.executed: list[str] = []

    def execute(self, statement: Any, params: dict[str, Any] | None = None) -> _FakeResult:
        sql = str(statement).strip()
        self.executed.append(sql)
        upper = sql.upper()
        if upper.startswith("SELECT"):
            if "FROM CONCEPT " in upper and "CODE LIKE" in upper:
                # concept의 '미적' 코드: canonical 1 + orphan 1
                return _FakeResult([("12미적Ⅰ-01-01-1",), (_ORPHAN,)])
            if "CONCEPT_ID FROM CONCEPT" in upper:
                # orphan concept의 UUID 조회
                return _FakeResult([("uuid-orphan",)])
            if "CODE LIKE" in upper:
                # atom_node 등 느슨참조 테이블: orphan 1건만
                return _FakeResult([(_ORPHAN,)])
            return _FakeResult([])
        # DELETE
        return _FakeResult([], rowcount=1)

    def __enter__(self) -> _FakeConn:
        return self

    def __exit__(self, *a: Any) -> None:
        return None


class _FakeEngine:
    def __init__(self, conn: _FakeConn) -> None:
        self._conn = conn

    def begin(self) -> _FakeConn:
        return self._conn


def _delete_sqls(conn: _FakeConn) -> list[str]:
    return [s for s in conn.executed if s.upper().startswith("DELETE")]


def test_dry_run_executes_zero_deletes() -> None:
    """① dry-run 기본 — DELETE 문 0건."""
    conn = _FakeConn()
    report = cleanup._cleanup(_FakeEngine(conn), _CANONICAL, confirm=False)
    assert _delete_sqls(conn) == []
    assert report["confirm"] is False
    # 대상은 집계되되(orphan 식별), 삭제는 0
    assert _ORPHAN in report["targets"]["concept"]


def test_confirm_targets_orphan_only_not_canonical() -> None:
    """② --confirm — orphan만 삭제 대상, canonical은 제외."""
    conn = _FakeConn()
    report = cleanup._cleanup(_FakeEngine(conn), _CANONICAL, confirm=True)
    # concept 대상에 orphan 있고 canonical 없음
    assert _ORPHAN in report["targets"]["concept"]
    assert "12미적Ⅰ-01-01-1" not in report["targets"]["concept"]
    # DELETE가 실제로 실행됨
    assert _delete_sqls(conn)


def test_confirm_fk_safe_order() -> None:
    """③ FK 안전 순서 — concept 본체 삭제 전 concept_edge·problem_concept 먼저."""
    conn = _FakeConn()
    cleanup._cleanup(_FakeEngine(conn), _CANONICAL, confirm=True)
    deletes = [s.upper() for s in _delete_sqls(conn)]
    edge_idx = next(i for i, s in enumerate(deletes) if "CONCEPT_EDGE" in s)
    pc_idx = next(i for i, s in enumerate(deletes) if "PROBLEM_CONCEPT" in s)
    concept_idx = next(
        i for i, s in enumerate(deletes) if "DELETE FROM CONCEPT " in s or s.endswith("CONCEPT")
    )
    assert edge_idx < concept_idx, "concept_edge가 concept보다 먼저 삭제돼야 FK 안전"
    assert pc_idx < concept_idx, "problem_concept이 concept보다 먼저 삭제돼야 FK 안전"


def test_zero_orphan_is_noop() -> None:
    """④ orphan 0건 — 삭제 문 0(대상 없음)."""

    class _NoOrphanConn(_FakeConn):
        def execute(self, statement: Any, params: dict[str, Any] | None = None) -> _FakeResult:
            sql = str(statement).strip()
            self.executed.append(sql)
            if sql.upper().startswith("SELECT") and "CODE LIKE" in sql.upper():
                # 전부 canonical — orphan 없음
                return _FakeResult([("12미적Ⅰ-01-01-1",)])
            if sql.upper().startswith("SELECT"):
                return _FakeResult([])
            return _FakeResult([], rowcount=0)

    conn = _NoOrphanConn()
    cleanup._cleanup(_FakeEngine(conn), _CANONICAL, confirm=True)
    assert _delete_sqls(conn) == [], "orphan 0이면 DELETE 실행 0"


def test_canonical_codes_loader_reads_graph_json() -> None:
    """정본 graph.json 로더 재사용 — 미적 계열 코드가 canonical에 포함."""
    canonical = cleanup._load_canonical_codes()
    assert any("미적" in c for c in canonical)
    assert "12미적Ⅰ-01-01-1" in canonical
