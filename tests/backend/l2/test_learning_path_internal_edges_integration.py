"""L2 학습 경로 — `fetch_internal_prerequisite_edges` 실 PG 통합 (기본 SKIP).

`fetch_internal_prerequisite_edges`는 SQLAlchemy Core IN 조회라 실 SQL이다 — 단위테스트
(`test_learning_path.py`)는 순수 `order_learning_path`만 직접 검증하므로, 집합 *내부* 엣지
조회(양 끝점이 집합 안인 PREREQUISITE 엣지만·집합 밖 끝점 제외)는 *실 PG*에서만 검증된다.

적재(from=선수·to=후행): 내부 A→B·B→C + 집합 밖 X 끝점 엣지(A→X). `fetch_internal_
prerequisite_edges([A,B,C])`는 내부(A→B·B→C)만·집합 밖(X 끝점)은 SQL where에서 배제.
`test_prerequisite_traversal_integration.py`의 `_settings`·`_pg_reachable`·`_concept`·
`_edge`·`_cleanup` 패턴 답습.
"""

from __future__ import annotations

import asyncio
import uuid

import pytest
from pydantic import SecretStr
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from whymath_backend.config import Settings
from whymath_backend.db.models.concept import Concept, ConceptEdge
from whymath_backend.l2.learning_path import fetch_internal_prerequisite_edges
from whymath_backend.schema.concept import Concept as ConceptSchema
from whymath_backend.schema.enums import ConceptLevel, EdgeType

pytestmark = pytest.mark.integration

_SECRET = "integration-jwt-secret-0123456789abcdef"


def _settings() -> Settings:
    return Settings(jwt_secret_key=SecretStr(_SECRET))


async def _pg_reachable() -> bool:
    engine = create_async_engine(_settings().database_url)
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
    finally:
        await engine.dispose()


def _concept(cid: uuid.UUID, code: str, name: str) -> Concept:
    return Concept.from_schema(
        ConceptSchema(
            concept_id=cid,
            code=code,
            name_ko=name,
            level=ConceptLevel.세부개념,
        )
    )


def _edge(from_id: uuid.UUID, to_id: uuid.UUID, strength: float) -> ConceptEdge:
    """선수 엣지 — from(선수)이 to(후행)의 선수(PREREQUISITE·.value 바인딩)."""
    return ConceptEdge(
        from_concept_id=from_id,
        to_concept_id=to_id,
        edge_type=EdgeType.PREREQUISITE.value,
        edge_strength=strength,
    )


async def _cleanup(concept_ids: list[uuid.UUID]) -> None:
    """concept_edge(엣지) → concept(노드) 순 정리(FK 순서)."""
    engine = create_async_engine(_settings().database_url)
    cids = [str(c) for c in concept_ids]
    try:
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    "DELETE FROM concept_edge WHERE from_concept_id = ANY(:cids) "
                    "OR to_concept_id = ANY(:cids)"
                ),
                {"cids": cids},
            )
            await conn.execute(
                text("DELETE FROM concept WHERE concept_id = ANY(:cids)"),
                {"cids": cids},
            )
    finally:
        await engine.dispose()


def test_fetch_internal_edges_excludes_out_of_set_on_live_pg() -> None:
    """[A,B,C] 내부 엣지(A→B·B→C)만 반환·집합 밖 X 끝점(A→X) 제외 검증."""
    if not asyncio.run(_pg_reachable()):
        pytest.skip("PostgreSQL 미도달 — 통합 테스트 건너뜀")

    sfx = uuid.uuid4().hex[:8]
    a, b, c, x = (uuid.uuid4() for _ in range(4))

    async def _setup() -> None:
        engine = create_async_engine(_settings().database_url)
        try:
            sm = async_sessionmaker(engine, expire_on_commit=False)
            async with sm() as s:
                s.add_all(
                    [
                        _concept(a, f"UC.lp.{sfx}.a", "선수A"),
                        _concept(b, f"UC.lp.{sfx}.b", "선수B"),
                        _concept(c, f"UC.lp.{sfx}.c", "선수C"),
                        _concept(x, f"UC.lp.{sfx}.x", "집합밖X"),
                    ]
                )
                await s.commit()
            async with sm() as s:
                s.add_all(
                    [
                        _edge(a, b, 0.9),  # 내부 A→B
                        _edge(b, c, 0.8),  # 내부 B→C
                        _edge(a, x, 0.5),  # 집합 밖(X 끝점) — 제외돼야 함
                    ]
                )
                await s.commit()
        finally:
            await engine.dispose()

    async def _run() -> None:
        engine = create_async_engine(_settings().database_url)
        try:
            sm = async_sessionmaker(engine, expire_on_commit=False)
            async with sm() as session:
                edges = await fetch_internal_prerequisite_edges(session, [a, b, c])
                # 내부 엣지(A→B·B→C)만·집합 밖(A→X) 제외.
                assert set(edges) == {(a, b), (b, c)}
                assert (a, x) not in edges
                # 노드 1개면 단락(내부 엣지 불가).
                assert await fetch_internal_prerequisite_edges(session, [a]) == []
        finally:
            await engine.dispose()

    try:
        asyncio.run(_setup())
        asyncio.run(_run())
    finally:
        asyncio.run(_cleanup([a, b, c, x]))
