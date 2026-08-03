"""평가 결과 영속 좌석 도달 관측 리포트 — 4테이블 델타 변별력 통합테스트 (실 PG, 기본 SKIP).

ASM-01 acceptance④: 각 테이블에 의도적으로 row를 만들어 `collect_seat_counts`의 카운터가 실제로
오르는지 실측 → 삭제해 복원되는지 실측한다. **절대값 0을 어디서도 assert하지 않는다** — 특히
`ability_snapshot`은 `POST /v1/me/ability/snapshots`를 통해 실사용 중일 수 있어(writer 존재),
테스트 시점의 절대 행 수를 가정하는 것 자체가 위험하다. 오직 `insert 전/후/cleanup 후`의
**델타**만 비교한다(성공/실패가 같은 값을 내면 검증이 아니다 — CLAUDE.md 변별력 원칙).

`WHYMATH_RUN_INTEGRATION=1` + 살아있는 PG에서만 실행. `tests/backend/db/
test_ability_snapshot_integration.py`의 DB 접속 판정(`_pg_reachable()`)·자체 엔진 생성·dispose
패턴을 그대로 미러링한다.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime

import pytest
from pydantic import SecretStr
from sqlalchemy import delete, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from whymath_backend.config import Settings
from whymath_backend.db.models.assessment import (
    AbilitySnapshot,
    Assessment,
    ConceptMasteryHistory,
    SkillMasteryHistory,
)
from whymath_backend.harness.assessment_seat_reach_report import collect_seat_counts
from whymath_backend.schema.enums import AssessmentType

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


def test_assessment_row_delta_increases_on_insert_and_restores_on_delete() -> None:
    """assessment 테이블 — writer 0(§D1 핵심). insert→델타+1 확인→delete→델타 0 복원."""
    if not asyncio.run(_pg_reachable()):
        pytest.skip("PostgreSQL 미도달 — 통합 테스트 건너뜀")

    aid = uuid.uuid4()

    async def _before() -> int:
        engine = create_async_engine(_settings().database_url, poolclass=NullPool)
        try:
            sm = async_sessionmaker(engine, expire_on_commit=False)
            async with sm() as session:
                counts = await collect_seat_counts(session)
            return counts.table_row_counts["assessment"]
        finally:
            await engine.dispose()

    async def _insert_and_measure() -> int:
        engine = create_async_engine(_settings().database_url, poolclass=NullPool)
        try:
            sm = async_sessionmaker(engine, expire_on_commit=False)
            async with sm() as session:
                session.add(
                    Assessment(
                        assessment_id=aid, assessment_type=AssessmentType.초기진단
                    )
                )
                await session.commit()
            async with sm() as session:
                counts = await collect_seat_counts(session)
            return counts.table_row_counts["assessment"]
        finally:
            await engine.dispose()

    async def _cleanup_and_measure() -> int:
        engine = create_async_engine(_settings().database_url, poolclass=NullPool)
        try:
            async with engine.begin() as conn:
                await conn.execute(
                    delete(Assessment).where(Assessment.assessment_id == aid)
                )
            sm = async_sessionmaker(engine, expire_on_commit=False)
            async with sm() as session:
                counts = await collect_seat_counts(session)
            return counts.table_row_counts["assessment"]
        finally:
            await engine.dispose()

    try:
        before = asyncio.run(_before())
        after_insert = asyncio.run(_insert_and_measure())
        after_cleanup = asyncio.run(_cleanup_and_measure())
        assert after_insert == before + 1  # 델타만 비교 — 절대값 0 assert 없음
        assert after_cleanup == before
    finally:
        # 테스트 실패로 위 cleanup이 스킵됐을 경우를 대비한 안전망.
        async def _force_cleanup() -> None:
            engine = create_async_engine(_settings().database_url, poolclass=NullPool)
            try:
                async with engine.begin() as conn:
                    await conn.execute(
                        delete(Assessment).where(Assessment.assessment_id == aid)
                    )
            finally:
                await engine.dispose()

        asyncio.run(_force_cleanup())


def test_concept_mastery_history_row_delta_increases_on_insert_and_restores_on_delete() -> (
    None
):
    """concept_mastery_history — 복합 PK(user_id, concept_id, measured_at). writer 0(§D1)."""
    if not asyncio.run(_pg_reachable()):
        pytest.skip("PostgreSQL 미도달 — 통합 테스트 건너뜀")

    uid = uuid.uuid4()
    cid = uuid.uuid4()
    measured_at = datetime(2026, 1, 1, tzinfo=UTC)

    async def _measure() -> int:
        engine = create_async_engine(_settings().database_url, poolclass=NullPool)
        try:
            sm = async_sessionmaker(engine, expire_on_commit=False)
            async with sm() as session:
                counts = await collect_seat_counts(session)
            return counts.table_row_counts["concept_mastery_history"]
        finally:
            await engine.dispose()

    async def _insert() -> None:
        engine = create_async_engine(_settings().database_url, poolclass=NullPool)
        try:
            sm = async_sessionmaker(engine, expire_on_commit=False)
            async with sm() as session:
                session.add(
                    ConceptMasteryHistory(
                        user_id=uid,
                        concept_id=cid,
                        measured_at=measured_at,
                        mastery=0.5,
                    )
                )
                await session.commit()
        finally:
            await engine.dispose()

    async def _cleanup() -> None:
        engine = create_async_engine(_settings().database_url, poolclass=NullPool)
        try:
            async with engine.begin() as conn:
                # 복합 PK 전체로 정리(사이드이펙트 0 보장).
                await conn.execute(
                    delete(ConceptMasteryHistory).where(
                        ConceptMasteryHistory.user_id == uid,
                        ConceptMasteryHistory.concept_id == cid,
                        ConceptMasteryHistory.measured_at == measured_at,
                    )
                )
        finally:
            await engine.dispose()

    try:
        before = asyncio.run(_measure())
        asyncio.run(_insert())
        after_insert = asyncio.run(_measure())
        asyncio.run(_cleanup())
        after_cleanup = asyncio.run(_measure())
        assert after_insert == before + 1
        assert after_cleanup == before
    finally:
        asyncio.run(_cleanup())


def test_skill_mastery_history_row_delta_increases_on_insert_and_restores_on_delete() -> (
    None
):
    """skill_mastery_history — 복합 PK(user_id, skill_id[Text], measured_at). writer 0(§D1)."""
    if not asyncio.run(_pg_reachable()):
        pytest.skip("PostgreSQL 미도달 — 통합 테스트 건너뜀")

    uid = uuid.uuid4()
    skill_id = f"skill.__asm01_test_{uuid.uuid4().hex}"
    measured_at = datetime(2026, 1, 1, tzinfo=UTC)

    async def _measure() -> int:
        engine = create_async_engine(_settings().database_url, poolclass=NullPool)
        try:
            sm = async_sessionmaker(engine, expire_on_commit=False)
            async with sm() as session:
                counts = await collect_seat_counts(session)
            return counts.table_row_counts["skill_mastery_history"]
        finally:
            await engine.dispose()

    async def _insert() -> None:
        engine = create_async_engine(_settings().database_url, poolclass=NullPool)
        try:
            sm = async_sessionmaker(engine, expire_on_commit=False)
            async with sm() as session:
                session.add(
                    SkillMasteryHistory(
                        user_id=uid,
                        skill_id=skill_id,
                        measured_at=measured_at,
                        mastery=0.5,
                    )
                )
                await session.commit()
        finally:
            await engine.dispose()

    async def _cleanup() -> None:
        engine = create_async_engine(_settings().database_url, poolclass=NullPool)
        try:
            async with engine.begin() as conn:
                await conn.execute(
                    delete(SkillMasteryHistory).where(
                        SkillMasteryHistory.user_id == uid,
                        SkillMasteryHistory.skill_id == skill_id,
                        SkillMasteryHistory.measured_at == measured_at,
                    )
                )
        finally:
            await engine.dispose()

    try:
        before = asyncio.run(_measure())
        asyncio.run(_insert())
        after_insert = asyncio.run(_measure())
        asyncio.run(_cleanup())
        after_cleanup = asyncio.run(_measure())
        assert after_insert == before + 1
        assert after_cleanup == before
    finally:
        asyncio.run(_cleanup())


def test_ability_snapshot_row_delta_increases_on_insert_and_restores_on_delete() -> (
    None
):
    """ability_snapshot — 유일하게 실제 writer가 있는 테이블(POST /v1/me/ability/snapshots).

    실사용 중일 수 있어 절대값 0을 가정하지 않는다 — 다른 프로세스가 동시에 행을 추가해도
    이 테스트는 델타(+1 → 복원)만 확인하므로 흔들리지 않는다.
    """
    if not asyncio.run(_pg_reachable()):
        pytest.skip("PostgreSQL 미도달 — 통합 테스트 건너뜀")

    uid = uuid.uuid4()
    sid = uuid.uuid4()

    async def _measure() -> int:
        engine = create_async_engine(_settings().database_url, poolclass=NullPool)
        try:
            sm = async_sessionmaker(engine, expire_on_commit=False)
            async with sm() as session:
                counts = await collect_seat_counts(session)
            return counts.table_row_counts["ability_snapshot"]
        finally:
            await engine.dispose()

    async def _insert() -> None:
        engine = create_async_engine(_settings().database_url, poolclass=NullPool)
        try:
            sm = async_sessionmaker(engine, expire_on_commit=False)
            async with sm() as session:
                session.add(
                    AbilitySnapshot(
                        snapshot_id=sid, user_id=uid, theta=0.0, response_count=0
                    )
                )
                await session.commit()
        finally:
            await engine.dispose()

    async def _cleanup() -> None:
        engine = create_async_engine(_settings().database_url, poolclass=NullPool)
        try:
            async with engine.begin() as conn:
                await conn.execute(
                    delete(AbilitySnapshot).where(AbilitySnapshot.snapshot_id == sid)
                )
        finally:
            await engine.dispose()

    try:
        before = asyncio.run(_measure())
        asyncio.run(_insert())
        after_insert = asyncio.run(_measure())
        asyncio.run(_cleanup())
        after_cleanup = asyncio.run(_measure())
        assert after_insert == before + 1
        assert after_cleanup == before
    finally:
        asyncio.run(_cleanup())


def test_assessment_type_distribution_reflects_live_insert() -> None:
    """assessment_type GROUP BY가 실 DB에서 정확한 분포를 내는지(D-100예측 하이픈 표기 포함)."""
    if not asyncio.run(_pg_reachable()):
        pytest.skip("PostgreSQL 미도달 — 통합 테스트 건너뜀")

    aid = uuid.uuid4()

    async def _insert_and_measure() -> dict[str, int]:
        engine = create_async_engine(_settings().database_url, poolclass=NullPool)
        try:
            sm = async_sessionmaker(engine, expire_on_commit=False)
            async with sm() as session:
                session.add(
                    Assessment(
                        assessment_id=aid, assessment_type=AssessmentType.D_100예측
                    )
                )
                await session.commit()
            async with sm() as session:
                counts = await collect_seat_counts(session)
            return counts.assessment_type_counts
        finally:
            await engine.dispose()

    async def _cleanup() -> None:
        engine = create_async_engine(_settings().database_url, poolclass=NullPool)
        try:
            async with engine.begin() as conn:
                await conn.execute(
                    delete(Assessment).where(Assessment.assessment_id == aid)
                )
        finally:
            await engine.dispose()

    try:
        type_counts = asyncio.run(_insert_and_measure())
        assert type_counts.get("D-100예측", 0) >= 1
    finally:
        asyncio.run(_cleanup())
