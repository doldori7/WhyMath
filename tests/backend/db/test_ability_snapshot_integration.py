"""ability_snapshot 마이그레이션↔ORM 정합 통합테스트 — 실 PG (기본 SKIP).

slice 31: 마이그레이션이 만든 `ability_snapshot` 테이블에 ORM으로 행을 INSERT·SELECT 왕복해
*마이그레이션 DDL과 ORM 매핑의 정합*을 검증한다(둘은 별도 정의라 분기 가능 — 통합테스트만
포착). `WHYMATH_RUN_INTEGRATION=1` + 살아있는 PG(슬라이스 29/30 CI 잡)에서만 실행.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime

import pytest
from pydantic import SecretStr
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from whymath_backend.config import Settings
from whymath_backend.db.models.assessment import AbilitySnapshot

pytestmark = pytest.mark.integration


def _settings() -> Settings:
    return Settings(jwt_secret_key=SecretStr("integration-jwt-secret-0123456789abcdef"))


async def _pg_reachable() -> bool:
    engine = create_async_engine(_settings().database_url, poolclass=NullPool)
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
    finally:
        await engine.dispose()


def test_ability_snapshot_insert_select_roundtrip_on_live_pg() -> None:
    if not asyncio.run(_pg_reachable()):
        pytest.skip("PostgreSQL 미도달 — 통합 테스트 건너뜀")

    uid = uuid.uuid4()
    captured: dict[str, object] = {}

    async def _run() -> None:
        engine = create_async_engine(_settings().database_url, poolclass=NullPool)
        try:
            sm = async_sessionmaker(engine, expire_on_commit=False)
            # INSERT — measured_at 미설정 → server_default now() 적용 검증
            async with sm() as session:
                snap = AbilitySnapshot(
                    user_id=uid, theta=1.25, standard_error=0.4, response_count=7
                )
                session.add(snap)
                await session.commit()
                await session.refresh(snap)
                captured["sid"] = snap.snapshot_id
                captured["measured_at"] = snap.measured_at  # server_default 채워짐
            # SELECT back
            async with sm() as session:
                rows = (
                    (
                        await session.execute(
                            select(AbilitySnapshot).where(
                                AbilitySnapshot.user_id == uid
                            )
                        )
                    )
                    .scalars()
                    .all()
                )
                assert len(rows) == 1
                row = rows[0]
                assert float(row.theta) == 1.25
                assert float(row.standard_error) == 0.4
                assert row.response_count == 7
                assert row.concept_id is None  # 전 과목 단일 θ
                assert row.measured_at is not None  # server_default now()
        finally:
            await engine.dispose()

    async def _cleanup() -> None:
        engine = create_async_engine(_settings().database_url, poolclass=NullPool)
        try:
            async with engine.begin() as conn:
                await conn.execute(
                    text("DELETE FROM ability_snapshot WHERE user_id = :u"),
                    {"u": str(uid)},
                )
        finally:
            await engine.dispose()

    try:
        asyncio.run(_run())
        assert captured["measured_at"] is not None
    finally:
        asyncio.run(_cleanup())
