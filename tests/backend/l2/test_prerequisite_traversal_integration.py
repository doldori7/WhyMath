"""L2 선수 다단계(transitive) traversal — `fetch_prerequisites` 재귀 CTE 실 PG 통합 (기본 SKIP).

`fetch_prerequisites`의 traversal은 SQLAlchemy Core **재귀 CTE**(`cte(recursive=True)`·
`union_all`·`literal`)라 실 SQL이다 — 단위테스트(`test_prerequisite_recommendation.py`)는 이
함수를 패치해 recommend 배선만 못 박으므로, 재귀 CTE 자체(depth 계산·max_depth bound·다중 경로
MIN depth dedup·origin 제외·1-hop 계약)는 *실 PG*에서만 검증된다.

체인 적재(from=선수·to=후행): C ← P1(depth1) ← P2(depth2) ← P3(depth3). 즉
  - P1은 C의 직접 선수(edge from=P1·to=C)
  - P2는 P1의 선수(from=P2·to=P1)
  - P3는 P2의 선수(from=P3·to=P2)
DAG 보장(data-pipeline validate.py prerequisite_cycle hard error)이라 재귀는 자연 종료.
concept_node·mastery·user_profile은 traversal에 불요(순수 그래프 조회)라 적재하지 않는다.
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
from whymath_backend.l2.prerequisite_recommendation import fetch_prerequisites
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


def test_fetch_prerequisites_recursive_cte_chain_on_live_pg() -> None:
    """C ← P1 ← P2 ← P3 체인에서 max_depth별 노출·depth 정확·1-hop 계약·origin 제외 검증."""
    if not asyncio.run(_pg_reachable()):
        pytest.skip("PostgreSQL 미도달 — 통합 테스트 건너뜀")

    sfx = uuid.uuid4().hex[:8]
    c, p1, p2, p3 = (uuid.uuid4() for _ in range(4))
    uc_c = f"UC.it.{sfx}.c"
    uc_p1 = f"UC.it.{sfx}.p1"
    uc_p2 = f"UC.it.{sfx}.p2"
    uc_p3 = f"UC.it.{sfx}.p3"

    async def _setup() -> None:
        engine = create_async_engine(_settings().database_url)
        try:
            sm = async_sessionmaker(engine, expire_on_commit=False)
            async with sm() as s:
                s.add_all(
                    [
                        _concept(c, uc_c, "후행"),
                        _concept(p1, uc_p1, "선수1"),
                        _concept(p2, uc_p2, "선수2"),
                        _concept(p3, uc_p3, "선수3"),
                    ]
                )
                await s.commit()
            async with sm() as s:
                s.add_all(
                    [
                        _edge(p1, c, 0.9),  # P1 = C의 직접 선수(depth1)
                        _edge(p2, p1, 0.8),  # P2 = P1의 선수(depth2)
                        _edge(p3, p2, 0.7),  # P3 = P2의 선수(depth3)
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
                # ① max_depth=1(기본) — 직접 선수 P1만(1-hop 계약 보존·recursive 가지 미실행).
                d1 = await fetch_prerequisites(session, c, max_depth=1)
                assert [(r.concept_id, r.depth) for r in d1] == [(p1, 1)]
                assert d1[0].concept_code == uc_p1
                assert d1[0].edge_strength == 0.9

                # ② max_depth=2 — P1(depth1)·P2(depth2)·P3 제외(bound).
                d2 = await fetch_prerequisites(session, c, max_depth=2)
                assert {(r.concept_id, r.depth) for r in d2} == {(p1, 1), (p2, 2)}

                # ③ max_depth=3 — P1·P2·P3 전부·depth 정확.
                d3 = await fetch_prerequisites(session, c, max_depth=3)
                assert {(r.concept_id, r.depth) for r in d3} == {(p1, 1), (p2, 2), (p3, 3)}

                # ④ max_depth=5(상한) — 체인이 3에서 끝나 P3까지만(DAG 자연 종료).
                d5 = await fetch_prerequisites(session, c, max_depth=5)
                assert {r.concept_id for r in d5} == {p1, p2, p3}

                # ⑤ origin 제외 — C 자신은 어떤 깊이에서도 결과에 없음.
                assert all(r.concept_id != c for r in d3)
        finally:
            await engine.dispose()

    try:
        asyncio.run(_setup())
        asyncio.run(_run())
    finally:
        asyncio.run(_cleanup([c, p1, p2, p3]))


def test_fetch_prerequisites_diamond_keeps_min_depth_on_live_pg() -> None:
    """다중 경로(diamond)에서 같은 선수는 MIN depth 1건만 — C←A←D 와 C←B←D 의 D는 depth2 1건.

    그래프: C의 직접 선수 A·B(depth1), A와 B의 공통 선수 D(C←A←D·C←B←D 두 경로로 depth2).
    DAG diamond라 D가 두 경로로 닿지만 dedup으로 MIN depth(=2) 1건만 남아야 한다.
    """
    if not asyncio.run(_pg_reachable()):
        pytest.skip("PostgreSQL 미도달 — 통합 테스트 건너뜀")

    sfx = uuid.uuid4().hex[:8]
    c, a, b, d = (uuid.uuid4() for _ in range(4))

    async def _setup() -> None:
        engine = create_async_engine(_settings().database_url)
        try:
            sm = async_sessionmaker(engine, expire_on_commit=False)
            async with sm() as s:
                s.add_all(
                    [
                        _concept(c, f"UC.dia.{sfx}.c", "후행"),
                        _concept(a, f"UC.dia.{sfx}.a", "선수A"),
                        _concept(b, f"UC.dia.{sfx}.b", "선수B"),
                        _concept(d, f"UC.dia.{sfx}.d", "공통선수D"),
                    ]
                )
                await s.commit()
            async with sm() as s:
                s.add_all(
                    [
                        _edge(a, c, 0.9),  # A = C의 직접 선수
                        _edge(b, c, 0.6),  # B = C의 직접 선수
                        _edge(d, a, 0.5),  # D = A의 선수(경로1: C←A←D)
                        _edge(d, b, 0.7),  # D = B의 선수(경로2: C←B←D)
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
                rows = await fetch_prerequisites(session, c, max_depth=3)
                by_id = {r.concept_id: r for r in rows}
                # A·B·D 각 1건만(D는 두 경로지만 dedup).
                assert set(by_id) == {a, b, d}
                assert len(rows) == 3  # 중복 0
                assert by_id[a].depth == 1
                assert by_id[b].depth == 1
                assert by_id[d].depth == 2  # MIN depth(두 경로 모두 depth2)
        finally:
            await engine.dispose()

    try:
        asyncio.run(_setup())
        asyncio.run(_run())
    finally:
        asyncio.run(_cleanup([c, a, b, d]))
