"""L2 학습 경로 — `fetch_ordering_subgraph` 실 PG 통합 (기본 SKIP).

`fetch_ordering_subgraph`는 bounded 재귀 CTE(`build_prerequisite_stmt` 패턴 답습)라 실
SQL이다 — 단위테스트(`test_learning_path.py`)는 `derive_ordering_edges`(순수 함수)만
in-memory subgraph로 검증하므로, *전이* 조회(A→X→B, X가 갭 집합 밖의 비-막힌 중간 노드)는
실 PG에서만 검증된다.

적재(from=선수·to=후행): A→X(내부 아님·X는 갭 집합 밖)·X→B(내부 아님). PATH-03 acceptance①의
"A→X→B(X 비-막힌) 재현" fixture — `fetch_ordering_subgraph([A,B])`는 B(descendant)에서
역방향 탐색해 X를 거쳐 A(ancestor)까지 2홉에 도달해야 한다. `test_learning_path_internal_
edges_integration.py`의 `_settings`·`_pg_reachable`·`_concept`·`_edge`·`_cleanup` 패턴 답습.
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
from whymath_backend.l2.learning_path import derive_ordering_edges, fetch_ordering_subgraph
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


def test_fetch_ordering_subgraph_traverses_non_blocked_intermediate_on_live_pg() -> None:
    """A→X→B(X 갭 집합 밖·비-막힌 중간노드) — B에서 역방향 2홉에 A 도달 검증(acceptance①④)."""
    if not asyncio.run(_pg_reachable()):
        pytest.skip("PostgreSQL 미도달 — 통합 테스트 건너뜀")

    sfx = uuid.uuid4().hex[:8]
    a, x, b = (uuid.uuid4() for _ in range(3))

    async def _setup() -> None:
        engine = create_async_engine(_settings().database_url)
        try:
            sm = async_sessionmaker(engine, expire_on_commit=False)
            async with sm() as s:
                s.add_all(
                    [
                        _concept(a, f"UC.lp.ord.{sfx}.a", "선행A"),
                        _concept(x, f"UC.lp.ord.{sfx}.x", "중간X(갭밖)"),
                        _concept(b, f"UC.lp.ord.{sfx}.b", "후행B"),
                    ]
                )
                await s.commit()
            async with sm() as s:
                s.add_all(
                    [
                        _edge(a, x, 0.9),  # A는 X의 선수
                        _edge(x, b, 0.9),  # X는 B의 선수
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
                # 갭 집합 = {A, B}(X는 갭 집합 밖 — "비-막힌 중간 노드").
                subgraph = await fetch_ordering_subgraph(session, [a, b])
                # B(descendant)에서 역방향 탐색 시 1홉=X, 2홉=A.
                assert (b, x, 1) in subgraph
                assert (b, a, 2) in subgraph

                # derive_ordering_edges가 X를 걸러내고 (A, B) 전이 순서 엣지만 남긴다.
                edges = derive_ordering_edges([a, b], subgraph)
                assert edges == [(a, b)]

                # 노드 1개면 단락(전이 탐색 불가).
                assert await fetch_ordering_subgraph(session, [a]) == []
        finally:
            await engine.dispose()

    try:
        asyncio.run(_setup())
        asyncio.run(_run())
    finally:
        asyncio.run(_cleanup([a, x, b]))
