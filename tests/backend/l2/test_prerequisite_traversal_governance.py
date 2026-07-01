"""거버넌스 동결 — 선수 traversal은 PREREQUISITE 관계만 따른다(약한 관계 조회 차단·retrieval Q3·Q6).

load-time skip(`test_edge_relation_governance`)이 약한 관계 *적재*를 막는 것과 짝을 이루는 *조회
계층* 동결이다. traversal 화이트리스트(`TRAVERSAL_ELIGIBLE_EDGE_TYPES`)가 PREREQUISITE만 담고,
`fetch_prerequisites` 재귀 CTE(base·recursive 두 가지)가 그 화이트리스트만 필터함을 못 박는다 —
약한/AI 관계가 회귀로 traversal에 새어들면 dense화·N² 폭발이므로 두 층(적재↔조회)에서 이중 차단한다.

hermetic: DB 불요 — capturing fake session으로 실행된 statement를 PostgreSQL dialect로 컴파일해
(literal_binds) 필터 값을 관찰한다(`test_atom_embedding`의 statement 컴파일 관찰 패턴 미러).
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

from sqlalchemy.dialects import postgresql

from whymath_backend.l2.prerequisite_recommendation import (
    TRAVERSAL_ELIGIBLE_EDGE_TYPES,
    fetch_prerequisites,
)
from whymath_backend.schema.enums import EdgeType

# 화이트리스트 밖 = 약한 관계(ANALOGOUS_TO·COMPOSED_OF·EXTENDS·CONTRASTS·TRIGGERS_DISTRACTOR).
# enum에서 도출해 새 약한 타입이 추가돼도 자동 포함(거버넌스 회귀 자동 확대).
_WEAK_EDGE_TYPES: tuple[EdgeType, ...] = tuple(
    e for e in EdgeType if e not in TRAVERSAL_ELIGIBLE_EDGE_TYPES
)


class _CapturingResult:
    """execute() 반환 흉내 — `.all()`로 빈 행(조회 결과는 검증 대상 아님·statement만 관찰)."""

    def all(self) -> list[Any]:
        return []


class _CapturingSession:
    """실행된 statement만 포착하는 최소 async 세션 흉내(DB·엔진 불요)."""

    def __init__(self) -> None:
        self.statements: list[Any] = []

    async def execute(self, statement: Any) -> _CapturingResult:
        self.statements.append(statement)
        return _CapturingResult()


def _compiled_traversal_sql(max_depth: int = 2) -> str:
    """fetch_prerequisites가 낸 traversal statement를 컴파일한 SQL(리터럴 바인딩·검사용)."""
    session = _CapturingSession()
    asyncio.run(
        fetch_prerequisites(session, uuid.uuid4(), max_depth=max_depth)  # type: ignore[arg-type]
    )
    assert len(session.statements) == 1
    return str(
        session.statements[0].compile(
            dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}
        )
    )


def test_whitelist_is_prerequisite_only() -> None:
    """traversal 화이트리스트는 정확히 {PREREQUISITE}(단일 출처·동결)."""
    assert TRAVERSAL_ELIGIBLE_EDGE_TYPES == frozenset({EdgeType.PREREQUISITE})


def test_no_weak_relation_in_whitelist() -> None:
    """약한 관계는 화이트리스트 밖(스윕 — 새 약한 타입 추가 시 자동 확대)."""
    assert len(_WEAK_EDGE_TYPES) >= 1  # 스윕 대상 존재(공허한 테스트 방지)
    for weak in _WEAK_EDGE_TYPES:
        assert weak not in TRAVERSAL_ELIGIBLE_EDGE_TYPES


def test_traversal_query_filters_prerequisite_only() -> None:
    """재귀 CTE(base·recursive)가 PREREQUISITE만 필터하고 약한 관계 값은 SQL에 없다."""
    sql = _compiled_traversal_sql()
    assert "PREREQUISITE" in sql
    for weak in _WEAK_EDGE_TYPES:
        assert weak.value not in sql
