"""L2 BKT↔ConceptMasteryHistory 결선 — 실 PG 통합테스트 (기본 SKIP).

`record_attempt_mastery`가 직전 측정을 SELECT(measured_at DESC)해 prior로 쓰고 새 측정 행을
INSERT하는지 검증한다. `concept_mastery_history`는 FK 없는 hypertable 느슨참조라 user_profile
선적재 불요(임의 user_id/concept_id 사용).
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
from whymath_backend.l2 import BktModel
from whymath_backend.l2.mastery_tracking import record_attempt_mastery

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


async def _cleanup(user_id: uuid.UUID) -> None:
    engine = create_async_engine(_settings().database_url)
    try:
        async with engine.begin() as conn:
            await conn.execute(
                text("DELETE FROM concept_mastery_history WHERE user_id = :uid"),
                {"uid": str(user_id)},
            )
    finally:
        await engine.dispose()


def test_record_attempt_mastery_appends_and_reads_prior_on_live_pg() -> None:
    """첫 관측은 P(L0) 갱신·둘째는 직전 측정을 prior로 읽어 갱신(학습 곡선 누적)."""
    if not asyncio.run(_pg_reachable()):
        pytest.skip("PostgreSQL 미도달 — 통합 테스트 건너뜀")

    uid = uuid.uuid4()
    cid = uuid.uuid4()
    t1 = datetime(2026, 1, 1, tzinfo=UTC)
    t2 = t1 + timedelta(minutes=5)

    async def _run() -> None:
        engine = create_async_engine(_settings().database_url)
        try:
            sm = async_sessionmaker(engine, expire_on_commit=False)
            model = BktModel()
            async with sm() as session:
                # 첫 관측(정답): P(L0)=0.3 → 0.69·표본 1
                r1 = await record_attempt_mastery(
                    session, uid, cid, True, model=model, measured_at=t1
                )
                assert float(r1.mastery) == 0.69
                assert r1.sample_size == 1
                # 둘째 관측(정답): 직전 0.69를 prior로 → 0.92·표본 2
                r2 = await record_attempt_mastery(
                    session, uid, cid, True, model=model, measured_at=t2
                )
                assert float(r2.mastery) == 0.92
                assert r2.sample_size == 2
            # DB에 2개 행 적재 확인
            async with sm() as session:
                rows = (
                    await session.execute(
                        text(
                            "SELECT count(*) FROM concept_mastery_history "
                            "WHERE user_id = :uid AND concept_id = :cid"
                        ),
                        {"uid": str(uid), "cid": str(cid)},
                    )
                ).scalar()
                assert rows == 2
        finally:
            await engine.dispose()

    try:
        asyncio.run(_run())
    finally:
        asyncio.run(_cleanup(uid))
