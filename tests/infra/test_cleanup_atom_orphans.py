"""cleanup_atom_orphans.py 단위 테스트 (hermetic · fake connection).

가드 스크립트의 핵심 안전 계약을 실 DB 없이 검증한다:
  ① dry-run 기본 — DELETE 0 (--confirm 없으면 삭제 문구가 실행되지 않음)
  ② --confirm — orphan 코드만 삭제 (canonical은 절대 대상 아님)
  ③ FK 안전 순서 — concept orphan 삭제 전 concept_edge·problem_concept 먼저
  ④ 0-orphan — 무동작
  ⑤ 은퇴 모드(--retired-from-ledger) — ledger 코드 정확 일치·canonical 충돌 시 전체 거부
  ⑥ M-series 보호 — misconception_catalog 스캔·삭제가 ATOM: 행으로 한정

실 DB DELETE 자체는 표준 SQL이라 fake connection이 실행 SQL을 기록하는 것으로 충분.
canonical 대조는 정본 graph.json 코드 집합을 주입(진단 스크립트 `_canonical_codes` 재사용).
은퇴 코드 로더는 실 커밋 ledger(dedup_merges_v1.json)로 ground truth를 확인한다.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

import pytest

# ---- cleanup 모듈 로드 (sys.path 의존 없이·tests/infra 관례) ----------------
_CLEANUP_PATH = Path(__file__).resolve().parents[2] / "scripts" / "cleanup_atom_orphans.py"
_spec = importlib.util.spec_from_file_location("cleanup_atom_orphans", _CLEANUP_PATH)
assert _spec is not None and _spec.loader is not None
cleanup = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cleanup)


# canonical(정본) 코드 집합 — 정상 원자 1개. orphan은 이 집합에 없는 '미적' 코드.
_CANONICAL = {"12미적Ⅰ-01-01-1"}
_ORPHAN = "미적1-raw-01"  # 정본에 없는 raw 잔재(orphan)
_RETIRED = ["10기수1-04-02-1", "NUMER-C05"]  # 은퇴 모드 표본(마커 '미적' 미포함 코드)


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
            if "FROM CONCEPT " in upper and "= ANY" in upper and "CONCEPT_ID" not in upper:
                # 은퇴 모드: ledger 코드 정확 일치 — prod에 잔존하는 은퇴 행
                return _FakeResult([(c,) for c in (params or {}).get("codes", [])])
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


# ── ⑤ 은퇴 모드 (--retired-from-ledger · S4-08) ─────────────────────────────


def test_retired_mode_uses_exact_match_not_like() -> None:
    """은퇴 모드 스캔은 정확 일치(= ANY)만 — '미적' LIKE 마커 스캔 0(기수/NUMER 커버)."""
    conn = _FakeConn()
    report = cleanup._cleanup(_FakeEngine(conn), _CANONICAL, confirm=False, retired=_RETIRED)
    selects = [s.upper() for s in conn.executed if s.upper().startswith("SELECT")]
    assert selects, "스캔이 실행돼야 함"
    assert all("LIKE :MARKER" not in s for s in selects), "은퇴 모드에 LIKE 마커 스캔 금지"
    # concept 대상 = ledger 코드 그대로(마커 '미적' 없는 기수/NUMER 포함)
    assert report["targets"]["concept"] == sorted(_RETIRED)
    assert _delete_sqls(conn) == []  # dry-run 기본은 은퇴 모드에도 동일


def test_retired_mode_confirm_deletes_ledger_codes() -> None:
    """은퇴 모드 --confirm — ledger 코드가 삭제 대상으로 실행(FK 순서 계약 공유)."""
    conn = _FakeConn()
    report = cleanup._cleanup(_FakeEngine(conn), _CANONICAL, confirm=True, retired=_RETIRED)
    assert report["targets"]["concept"] == sorted(_RETIRED)
    deletes = [s.upper() for s in _delete_sqls(conn)]
    assert any("CONCEPT_EDGE" in s for s in deletes)
    assert any("DELETE FROM CONCEPT " in s or s.endswith("CONCEPT") for s in deletes)


def test_retired_mode_rejects_canonical_overlap() -> None:
    """은퇴 코드가 정본에 존재(병합 미반영 코퍼스) — 스캔 전 전체 거부(ValueError)."""
    conn = _FakeConn()
    with pytest.raises(ValueError, match="불일치"):
        cleanup._cleanup(
            _FakeEngine(conn),
            _CANONICAL,
            confirm=True,
            retired=["12미적Ⅰ-01-01-1"],  # canonical과 충돌
        )
    assert conn.executed == [], "거부 시 어떤 SQL도 실행되지 않아야 함"


def test_load_retired_codes_from_real_ledger() -> None:
    """실 커밋 ledger ground truth — applied 14건·기수/NUMER 포함·정본과 서로소."""
    retired = cleanup._load_retired_codes()
    assert len(retired) == 14
    assert "10기수1-04-02-1" in retired  # '미적' 마커가 못 보던 기수 트랙
    assert "NUMER-C05" in retired  # 대학 NUMER 트랙
    canonical = cleanup._load_canonical_codes()
    assert not set(retired) & canonical, "은퇴 코드가 정본에 남아 있으면 병합 회귀"


# ── ⑥ M-series 보호 (misconception_catalog ATOM: 한정) ──────────────────────


def test_misconception_scan_and_delete_scoped_to_atom_rows() -> None:
    """misconception_catalog 스캔·삭제 SQL이 mis_id LIKE 'ATOM:%'로 한정(H: 오탐·오삭제 방지).

    diagnose의 2026-07-16 오탐 필터와 정합 — cleanup에 누락돼 있던 잠재 결함의 회귀 동결.
    """

    class _MisconceptionConn(_FakeConn):
        def execute(self, statement: Any, params: dict[str, Any] | None = None) -> _FakeResult:
            sql = str(statement).strip()
            if "misconception_catalog" in sql and sql.upper().startswith("SELECT"):
                self.executed.append(sql)
                return _FakeResult([(_ORPHAN,)])  # 스캔에 걸린 orphan 1건 → 삭제 유도
            return super().execute(statement, params)

    conn = _MisconceptionConn()
    cleanup._cleanup(_FakeEngine(conn), _CANONICAL, confirm=True)
    mis_sqls = [s for s in conn.executed if "misconception_catalog" in s]
    assert mis_sqls, "misconception_catalog 스캔·삭제가 실행돼야 함"
    for sql in mis_sqls:
        assert "ATOM:" in sql, f"ATOM: 한정 누락 — M-series 오삭제 위험: {sql}"
