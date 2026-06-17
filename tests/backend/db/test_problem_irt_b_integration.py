"""problem.irt_difficulty_b 마이그레이션↔ORM 정합 통합테스트 — 실 PG (기본 SKIP).

slice 79: 마이그레이션이 `problem`에 추가한 `irt_difficulty_b`(Float·nullable)를 ORM으로
INSERT·UPDATE·SELECT 왕복해 *마이그레이션 DDL과 ORM 매핑의 정합*을 검증한다(둘은 별도 정의라
분기 가능 — 통합테스트만 포착). UPDATE 경로는 `calibrate_item_difficulties`가 쓰는
`update().values(irt_difficulty_b=)`와 동형. `WHYMATH_RUN_INTEGRATION` + 살아있는 PG에서만.
"""

from __future__ import annotations

import asyncio
import uuid

import pytest
from pydantic import SecretStr
from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from whymath_backend.config import Settings
from whymath_backend.db.models.problem import Problem
from whymath_backend.schema.enums import Curriculum, SourceType, Subject
from whymath_backend.schema.problem import Problem as ProblemSchema

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


def test_irt_difficulty_b_insert_update_select_roundtrip_on_live_pg() -> None:
    """보정 b를 INSERT·SELECT 왕복(컬럼 정합)·UPDATE(calibrate 쓰기 경로)·재조회 검증."""
    if not asyncio.run(_pg_reachable()):
        pytest.skip("PostgreSQL 미도달 — 통합 테스트 건너뜀")

    pid = uuid.uuid4()
    suffix = pid.hex[:8]

    def _problem(b: float | None) -> Problem:
        return Problem.from_schema(
            ProblemSchema(
                problem_id=pid,
                source_type=SourceType.자체생성,
                curriculum_version=Curriculum.REVISION_2022,
                valid_from_year=2022,
                subject=Subject.공통,
                unit_codes=[f"U-{suffix}"],
                irt_difficulty_b=b,
            )
        )

    async def _select_b(sm: async_sessionmaker[AsyncSession]) -> float | None:
        async with sm() as session:
            return (
                await session.execute(
                    select(Problem.irt_difficulty_b).where(Problem.problem_id == pid)
                )
            ).scalar_one()

    async def _run() -> None:
        engine = create_async_engine(_settings().database_url, poolclass=NullPool)
        try:
            sm = async_sessionmaker(engine, expire_on_commit=False)
            # INSERT — 보정 b 보유.
            async with sm() as session:
                session.add(_problem(2.5))
                await session.commit()
            assert await _select_b(sm) == pytest.approx(2.5)  # 컬럼 왕복 보존
            # UPDATE — calibrate가 쓰는 update().values(irt_difficulty_b=) 경로.
            async with sm() as session:
                await session.execute(
                    update(Problem).where(Problem.problem_id == pid).values(irt_difficulty_b=-1.25)
                )
                await session.commit()
            assert await _select_b(sm) == pytest.approx(-1.25)
        finally:
            await engine.dispose()

    async def _cleanup() -> None:
        engine = create_async_engine(_settings().database_url, poolclass=NullPool)
        try:
            async with engine.begin() as conn:
                await conn.execute(
                    text("DELETE FROM problem WHERE problem_id = :pid"),
                    {"pid": str(pid)},
                )
        finally:
            await engine.dispose()

    try:
        asyncio.run(_run())
    finally:
        asyncio.run(_cleanup())
