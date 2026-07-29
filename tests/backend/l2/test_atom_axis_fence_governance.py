"""거버넌스 동결 — L2 추천 좌석의 **원자 축 울타리**·교차 엔진 조인 재유입 차단 (ARCH-13).

배경: backend `concept`/`concept_edge`에는 원자 백본(runtime truth)과 구 437 개념
(`legacy_snapshot`)이 **code로 병존**한다(MEMORY S0-1). 과거 L2 추천 좌석은 traversal·진단은 async
세션에서, 메타는 *별도 sync 엔진*에서 가져와 code 문자열로 이어 붙였다. 축이 어긋나도 그 조인은
조용히 성립했고(미스→None), `reviewed_only`에서 소리 없이 탈락했다 — 유일하게 두 진실이 런타임에
병존하던 지점이다.

ARCH-13은 축 판정을 **쿼리 안**으로 옮기고(단일 엔진·LEFT OUTER JOIN) 제외를 사유별로 계상한다.
이 테스트는 `test_legacy_snapshot_governance.py`의 정적 스캔 패턴을 미러해 그 두 성질을 동결한다
(hermetic — DB·네트워크 0):

  (i)   **울타리가 SQL 안에 있다**: `build_prerequisite_stmt`를 PG dialect로 컴파일해 `atom_node`
        LEFT OUTER JOIN이 `concept.code` 기준으로 존재함을 단언한다. 조인이 빠지면 red.
  (i-b) **그 검사에 변별력이 있다**: 조인 없는 statement에는 같은 검사가 *실패*한다(위장 검증 방지).
  (ii)  **교차 엔진 조인 재유입 0**: `l2/**` 소스를 **AST**로 파싱해 sync 메타 좌석
        (`fetch_atom_node_meta`)·`asyncio.to_thread` 참조가 0건임을 단언한다. 스코프는 `l2/**`만 —
        L1 검색 좌석(`l1/atom_graph/retrieval.py`)은 이미 블로킹 인덱스 평면이라 sync 조회가
        정당하다.
  (iii) **재귀 CTE 계약 보존**: 울타리를 붙이면서 선수 traversal 자체(재귀 CTE·PREREQUISITE·depth
        bound)가 훼손되지 않았음을 같은 컴파일 SQL에서 확인한다.
"""

from __future__ import annotations

import ast
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql.selectable import Select
from whymath_backend.db.models.concept import Concept, ConceptEdge
from whymath_backend.l2.prerequisite_recommendation import build_prerequisite_stmt

# 리포지토리 루트(tests/backend/l2/ 기준 3단 상위) → backend L2 패키지 경로.
_REPO_ROOT = Path(__file__).resolve().parents[3]
_L2_ROOT = _REPO_ROOT / "src" / "backend" / "whymath_backend" / "l2"

# 교차 엔진 조인 금지 심볼 — sync 메타 좌석과 그 격리 수단(워커 스레드 왕복).
# L2는 요청 세션(async)을 이미 들고 있으므로 둘 다 필요 없다(`l1/atom_graph/axis.py` 사용).
_CROSS_ENGINE_IDENTIFIERS = frozenset({"fetch_atom_node_meta", "to_thread"})


def _compiled(stmt: Select[Any]) -> str:
    """PG dialect 컴파일 문자열(공백 정규화·소문자) — DB 연결 없이 SQL 형태만 본다."""
    return " ".join(str(stmt.compile(dialect=postgresql.dialect())).split()).lower()


def _has_atom_axis_outerjoin(sql: str) -> bool:
    """컴파일 SQL이 `concept.code` 기준 `atom_node` LEFT OUTER JOIN을 포함하는가."""
    return "left outer join atom_node on atom_node.code = concept.code" in sql


# ──────────────────────────────────────────────────────────────────────────
# (i) 울타리가 SQL 안에 있다 — 컴파일 SQL 동결
# ──────────────────────────────────────────────────────────────────────────
def test_prerequisite_stmt_joins_atom_axis() -> None:
    """선수 traversal statement가 원자 축(`atom_node`)을 code 기준으로 OUTER JOIN한다.

    축 판정을 파이썬에서 code 접두사로 추측하거나 별도 엔진을 왕복하면 red — 축의 단일 출처는
    이 조인이다(ARCH-13). 안전 메타 3열도 같은 조인에서 함께 나온다.
    """
    sql = _compiled(build_prerequisite_stmt(uuid.uuid4(), 1))
    assert _has_atom_axis_outerjoin(sql), f"원자 축 OUTER JOIN이 SQL에 없다: {sql}"
    # 안전 메타 3열 동승(별도 조회 왕복 0). 본문 컬럼은 atom_node에 존재하지 않는다(redaction).
    for column in ("atom_node.name_ko", "atom_node.subject_area", "atom_node.review_status"):
        assert column in sql, f"안전 메타 열 누락: {column}"
    for forbidden in ("core_proposition", "description", "formal_definition"):
        assert forbidden not in sql, f"본문 근접 컬럼이 SQL에 등장: {forbidden}"


def test_atom_axis_join_check_is_discriminative() -> None:
    """**변별력** — 조인 없는 statement에는 같은 검사가 실패한다(항상 통과하는 검사가 아님).

    (i)이 위장 검증이 되지 않게 못 박는다: 검사기가 실패 상태에서 실제로 실패 신호를 내는지
    확인한다(CLAUDE.md "변별력 없는 검증 스텝 금지").
    """
    without_join = select(Concept.code, Concept.name_ko).join(
        ConceptEdge, ConceptEdge.from_concept_id == Concept.concept_id
    )
    assert not _has_atom_axis_outerjoin(_compiled(without_join))


# ──────────────────────────────────────────────────────────────────────────
# (iii) 재귀 CTE 계약 보존 — 울타리가 traversal을 훼손하지 않았다
# ──────────────────────────────────────────────────────────────────────────
def test_recursive_traversal_contract_preserved() -> None:
    """울타리를 붙인 뒤에도 선수 traversal(재귀 CTE·PREREQUISITE·depth bound)이 그대로다."""
    sql = _compiled(build_prerequisite_stmt(uuid.uuid4(), 3))
    assert "with recursive prereq_traversal" in sql
    assert "union all" in sql
    assert "concept_edge" in sql
    # depth bound(재귀 종료 방어)와 안정 정렬(dedup MIN depth 결정론)이 남아 있다.
    assert "prereq_traversal.depth <" in sql
    assert "order by prereq_traversal.depth asc" in sql


# ──────────────────────────────────────────────────────────────────────────
# (ii) 교차 엔진 조인 재유입 0 — l2/** AST 스캔
# ──────────────────────────────────────────────────────────────────────────
def _iter_py(root: Path) -> list[Path]:
    return sorted(p for p in root.rglob("*.py") if p.is_file())


def _cross_engine_references(tree: ast.Module) -> set[str]:
    """AST에서 교차 엔진 조인 심볼의 *실제* 참조를 수집(주석·docstring·문자열 제외).

    `test_legacy_snapshot_governance._reader_data_references`와 동일 규약 — import-name·Name.id·
    Attribute.attr만 본다. docstring이 "예전엔 to_thread를 썼다"고 설명해도 Constant라 잡히지 않는다
    (오탐 차단·REND-01에서 배운 것).
    """
    hits: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name in _CROSS_ENGINE_IDENTIFIERS:
                    hits.add(f"import-name:{alias.name}")
        elif isinstance(node, ast.Name) and node.id in _CROSS_ENGINE_IDENTIFIERS:
            hits.add(f"name:{node.id}")
        elif isinstance(node, ast.Attribute) and node.attr in _CROSS_ENGINE_IDENTIFIERS:
            hits.add(f"attr:{node.attr}")
    return hits


def test_l2_has_zero_cross_engine_meta_joins() -> None:
    """L2 추천 계층에 sync 메타 좌석·워커 스레드 왕복 참조가 0건이어야 한다.

    신규 유입(예: `await asyncio.to_thread(fetch_atom_node_meta, codes)`)이 생기면 red — 한 요청
    안에서 두 엔진이 code 문자열로 이어지는 이중 진실 조인이 되살아난다(ARCH-13 위반).
    L2는 요청 세션을 들고 있으므로 `l1.atom_graph.axis.fetch_atom_axis_meta`를 쓴다.
    """
    assert _L2_ROOT.is_dir(), f"L2 패키지 부재 — 경로 확인: {_L2_ROOT}"
    violations: dict[str, set[str]] = {}
    scanned = 0
    for path in _iter_py(_L2_ROOT):
        scanned += 1
        hits = _cross_engine_references(ast.parse(path.read_text(encoding="utf-8")))
        if hits:
            violations[path.relative_to(_L2_ROOT).as_posix()] = hits

    # sanity: 스캐너가 실제로 파일을 읽었다(빈 스캔으로 인한 무력화 방지).
    assert scanned > 5, f"L2 스캔 파일 수가 비정상적으로 적다({scanned}) — 스캐너 무력화 확인"
    assert not violations, (
        "L2에서 교차 엔진 메타 조인이 발견됨 — 요청 세션의 async 좌석"
        "(`l1.atom_graph.axis.fetch_atom_axis_meta`)을 쓰라. "
        f"위반: {dict(sorted((k, sorted(v)) for k, v in violations.items()))}"
    )


def test_cross_engine_scanner_is_discriminative() -> None:
    """**변별력** — 스캐너가 실제 위반 코드를 잡고, 산문(docstring)은 잡지 않는다."""
    violating = ast.parse(
        "import asyncio\n"
        "from whymath_backend.l1.atom_graph.atom_node_projection import fetch_atom_node_meta\n"
        "async def f(codes):\n"
        "    return await asyncio.to_thread(fetch_atom_node_meta, codes)\n"
    )
    assert _cross_engine_references(violating)

    prose_only = ast.parse('"""예전엔 fetch_atom_node_meta를 asyncio.to_thread로 감쌌다."""\n')
    assert not _cross_engine_references(prose_only)
