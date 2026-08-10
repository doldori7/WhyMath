"""L2 복습 우선순위 큐 — `fetch_review_queue` 실 PG 통합 (기본 SKIP).

`fetch_review_queue`는 `ConceptMasteryHistory` DISTINCT ON 실 SQL이라 단위테스트
(`test_review_queue.py`)는 순수 `_rank_items`만 검증한다. 여기서는 ①개념당 *최신* 측정
1건만 뽑히는지(관측 이력이 여러 건인 개념에서 오래된 측정이 섞이지 않는지) ②관측 이력이
전혀 없는 개념이 자동 제외되는지를 실 PG로 검증한다.

`test_learning_path_internal_edges_integration.py`의 `_settings`·`_pg_reachable`·cleanup
패턴 답습. **이 샌드박스엔 live PG가 없어 실행은 못 한다 — 작성만 하고 실행은 시도하지
않는다(이 환경의 알려진 제약, 에러 아님).**
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import SecretStr
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from whymath_backend.config import Settings
from whymath_backend.db.models.assessment import ConceptMasteryHistory
from whymath_backend.db.models.concept import Concept
from whymath_backend.l2.review_queue import fetch_review_queue
from whymath_backend.schema.assessment import ConceptMasteryHistory as MasteryHistorySchema
from whymath_backend.schema.concept import Concept as ConceptSchema
from whymath_backend.schema.enums import ConceptLevel

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
        ConceptSchema(concept_id=cid, code=code, name_ko=name, level=ConceptLevel.세부개념)
    )


def _mastery(
    user_id: uuid.UUID, concept_id: uuid.UUID, measured_at: datetime, mastery: float
) -> ConceptMasteryHistory:
    return ConceptMasteryHistory.from_schema(
        MasteryHistorySchema(
            user_id=user_id,
            concept_id=concept_id,
            measured_at=measured_at,
            mastery=mastery,
        )
    )


async def _cleanup(user_id: uuid.UUID, concept_ids: list[uuid.UUID]) -> None:
    """concept_mastery_history(관측) → concept(노드) 순 정리(FK 순서 무관이나 관례 답습)."""
    engine = create_async_engine(_settings().database_url)
    cids = [str(c) for c in concept_ids]
    try:
        async with engine.begin() as conn:
            await conn.execute(
                text("DELETE FROM concept_mastery_history WHERE user_id = :uid"),
                {"uid": str(user_id)},
            )
            await conn.execute(
                text("DELETE FROM concept WHERE concept_id = ANY(:cids)"),
                {"cids": cids},
            )
    finally:
        await engine.dispose()


def test_only_latest_measurement_used_and_unobserved_concepts_excluded() -> None:
    """개념 A는 신·구 2측정 중 최신만·개념 B는 관측 이력 없어 자동 제외·개념 C는 옛 고숙달."""
    if not asyncio.run(_pg_reachable()):
        pytest.skip("PostgreSQL 미도달 — 통합 테스트 건너뜀")

    sfx = uuid.uuid4().hex[:8]
    uid = uuid.uuid4()
    a, b, c = (uuid.uuid4() for _ in range(3))
    now = datetime.now(UTC)

    async def _setup() -> None:
        engine = create_async_engine(_settings().database_url)
        try:
            sm = async_sessionmaker(engine, expire_on_commit=False)
            async with sm() as s:
                s.add_all(
                    [
                        _concept(a, f"UC.rq.{sfx}.a", "복습A"),
                        _concept(b, f"UC.rq.{sfx}.b", "복습B(미관측)"),
                        _concept(c, f"UC.rq.{sfx}.c", "복습C(오래됨)"),
                    ]
                )
                await s.commit()
            async with sm() as s:
                s.add_all(
                    [
                        # A: 오래된 낮은 측정(0.2) + 최신 높은 측정(0.9) — 최신만 채택돼야 함.
                        _mastery(uid, a, now - timedelta(days=30), 0.2),
                        _mastery(uid, a, now - timedelta(hours=1), 0.9),
                        # B: 관측 이력 없음(insert 안 함) — 결과에 등장하면 안 됨.
                        # C: 60일 전 고숙달(0.9) — 감쇠로 급해져야 함.
                        _mastery(uid, c, now - timedelta(days=60), 0.9),
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
                queue = await fetch_review_queue(session, uid, as_of=now)
                by_id = {item.concept_id: item for item in queue.items}

                # B(미관측)는 애초에 결과 집합에 없다.
                assert b not in by_id

                # A는 최신 측정(0.9)만 반영 — 오래된 0.2가 섞이지 않는다.
                assert a in by_id
                assert by_id[a].raw_mastery == pytest.approx(0.9)
                assert by_id[a].days_since_practice == pytest.approx(1.0 / 24.0, abs=1e-3)

                # C는 60일 경과로 크게 감쇠 — A(1시간 경과)보다 decayed_mastery가 낮다(더 급함).
                assert c in by_id
                assert by_id[c].decayed_mastery < by_id[a].decayed_mastery
        finally:
            await engine.dispose()

    try:
        asyncio.run(_setup())
        asyncio.run(_run())
    finally:
        asyncio.run(_cleanup(uid, [a, b, c]))
