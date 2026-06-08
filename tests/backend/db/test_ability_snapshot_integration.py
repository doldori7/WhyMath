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
from whymath_backend.l2.ability_tracking import get_current_theta

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


def test_get_current_theta_global_and_concept_scoped_on_live_pg() -> None:
    """`get_current_theta` — 전과목(concept_id IS NULL)·개념별(concept_id==X) θ 분리 조회.

    slice 73·74: L4 coach가 BKT↔θ 교차검증에 쓰는 θ 리더의 WHERE(IS NULL vs ==X)·ORDER BY
    (measured_at DESC) 정확성을 실 PG로 검증(hermetic 단위는 스칼라 래퍼만 봄).
    """
    if not asyncio.run(_pg_reachable()):
        pytest.skip("PostgreSQL 미도달 — 통합 테스트 건너뜀")

    uid = uuid.uuid4()
    cid_x = uuid.uuid4()
    cid_y = uuid.uuid4()

    async def _run() -> None:
        engine = create_async_engine(_settings().database_url, poolclass=NullPool)
        try:
            sm = async_sessionmaker(engine, expire_on_commit=False)
            async with sm() as session:
                # 전과목 2건(시간순)·개념 X 2건(시간순)·개념 Y 1건
                session.add_all(
                    [
                        AbilitySnapshot(
                            user_id=uid,
                            theta=0.5,
                            response_count=3,
                            measured_at=datetime(2026, 1, 1, tzinfo=UTC),
                        ),
                        AbilitySnapshot(
                            user_id=uid,
                            theta=1.8,
                            response_count=9,
                            measured_at=datetime(2026, 2, 1, tzinfo=UTC),
                        ),
                        AbilitySnapshot(
                            user_id=uid,
                            concept_id=cid_x,
                            theta=-3.0,
                            response_count=4,
                            measured_at=datetime(2026, 3, 1, tzinfo=UTC),
                        ),
                        AbilitySnapshot(
                            user_id=uid,
                            concept_id=cid_x,
                            theta=-1.0,
                            response_count=6,
                            measured_at=datetime(2026, 4, 1, tzinfo=UTC),
                        ),
                        AbilitySnapshot(
                            user_id=uid,
                            concept_id=cid_y,
                            theta=0.9,
                            response_count=5,
                            measured_at=datetime(2026, 3, 1, tzinfo=UTC),
                        ),
                    ]
                )
                await session.commit()
            async with sm() as session:
                global_theta = await get_current_theta(session, uid)
                theta_x = await get_current_theta(session, uid, cid_x)
                theta_y = await get_current_theta(session, uid, cid_y)
            # 전과목: 최신 global 1.8(개념 행은 무시·전과목 0.5는 더 옛날)
            assert global_theta == pytest.approx(1.8)
            # 개념 X: 최신 X 행 -1.0(구 -3.0·전과목·Y 아님 — concept_id 필터+정렬)
            assert theta_x == pytest.approx(-1.0)
            # 개념 Y: 0.9(X와 분리 — concept_id 필터 정확성)
            assert theta_y == pytest.approx(0.9)
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
    finally:
        asyncio.run(_cleanup())
