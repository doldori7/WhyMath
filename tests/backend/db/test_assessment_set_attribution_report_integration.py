"""조립 세트 시행 귀속 관측 리포트 — `collect_test_set_rows` 델타 변별력 통합테스트 (실 PG,
기본 SKIP).

ASM-10 acceptance⑤: 합성 `실전모의고사` Assessment + 그 세트 문항에 대한 합성 `problem_attempt`
를 실제로 넣어 `collect_test_set_rows` → `build_report`의 `unattributable_attempt_count`가
실제로 오르는지 실측 → 삭제해 복원되는지 실측한다. **절대값 0을 어디서도 assert하지 않는다** —
오직 `insert 전/후/cleanup 후`의 **델타**만 비교한다(CLAUDE.md 변별력 원칙).

`WHYMATH_RUN_INTEGRATION=1` + 살아있는 PG에서만 실행. `tests/backend/db/
test_assessment_seat_reach_report_integration.py`의 DB 접속 판정(`_pg_reachable()`)·자체 엔진
생성·dispose 패턴을 그대로 미러링한다.
"""

from __future__ import annotations

import asyncio
import uuid

import pytest
from pydantic import SecretStr
from sqlalchemy import delete, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from whymath_backend.config import Settings
from whymath_backend.db.models.activity import ProblemAttempt
from whymath_backend.db.models.assessment import Assessment
from whymath_backend.harness.assessment_set_attribution_report import (
    build_report,
    collect_test_set_rows,
)
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


def test_unattributable_count_delta_on_synthetic_set_and_attempt_insert_and_cleanup() -> None:
    """합성 세트+시도 삽입 → 카운터 +1 실측 → 삭제 → 원복 실측(절대값 0 assert 없음)."""
    if not asyncio.run(_pg_reachable()):
        pytest.skip("PostgreSQL 미도달 — 통합 테스트 건너뜀")

    aid = uuid.uuid4()
    uid = uuid.uuid4()
    pid = uuid.uuid4()
    attempt_id = uuid.uuid4()
    pattern_diagnosis = [
        {"kind": "blueprint_test_set", "selected_item_count": 1},
        {"kind": "blueprint_item", "problem_id": str(pid), "cell_index": 0, "position": 0},
    ]

    async def _measure() -> int:
        engine = create_async_engine(_settings().database_url, poolclass=NullPool)
        try:
            sm = async_sessionmaker(engine, expire_on_commit=False)
            async with sm() as session:
                collection = await collect_test_set_rows(session)
            return build_report(collection).total_unattributable_attempts
        finally:
            await engine.dispose()

    async def _insert_set_only() -> None:
        engine = create_async_engine(_settings().database_url, poolclass=NullPool)
        try:
            sm = async_sessionmaker(engine, expire_on_commit=False)
            async with sm() as session:
                session.add(
                    Assessment(
                        assessment_id=aid,
                        user_id=uid,
                        assessment_type=AssessmentType.실전모의고사,
                        pattern_diagnosis=pattern_diagnosis,
                    )
                )
                await session.commit()
        finally:
            await engine.dispose()

    async def _insert_matching_attempt() -> None:
        engine = create_async_engine(_settings().database_url, poolclass=NullPool)
        try:
            sm = async_sessionmaker(engine, expire_on_commit=False)
            async with sm() as session:
                session.add(ProblemAttempt(attempt_id=attempt_id, user_id=uid, problem_id=pid))
                await session.commit()
        finally:
            await engine.dispose()

    async def _cleanup() -> None:
        engine = create_async_engine(_settings().database_url, poolclass=NullPool)
        try:
            async with engine.begin() as conn:
                await conn.execute(
                    delete(ProblemAttempt).where(ProblemAttempt.attempt_id == attempt_id)
                )
                await conn.execute(delete(Assessment).where(Assessment.assessment_id == aid))
        finally:
            await engine.dispose()

    try:
        before = asyncio.run(_measure())
        asyncio.run(_insert_set_only())
        after_set_only = asyncio.run(_measure())
        asyncio.run(_insert_matching_attempt())
        after_attempt = asyncio.run(_measure())

        async def _remove_attempt_only() -> None:
            engine = create_async_engine(_settings().database_url, poolclass=NullPool)
            try:
                async with engine.begin() as conn:
                    await conn.execute(
                        delete(ProblemAttempt).where(ProblemAttempt.attempt_id == attempt_id)
                    )
            finally:
                await engine.dispose()

        asyncio.run(_remove_attempt_only())
        after_attempt_removed = asyncio.run(_measure())

        # 세트만 있고 시도가 없으면 델타 0(세트 삽입 자체는 카운터를 안 올린다).
        assert after_set_only == before
        # 세트 문항과 일치하는 시도를 넣으면 정확히 +1.
        assert after_attempt == before + 1
        # 시도만 제거하면 원래 값으로 복원(세트는 아직 남아 있어도).
        assert after_attempt_removed == before
    finally:
        asyncio.run(_cleanup())


def test_attempt_for_unrelated_problem_does_not_move_the_counter() -> None:
    """세트에 없는 문항의 시도는 실 DB 조회에서도 카운터에 잡히지 않는다(acceptance⑤ 후반)."""
    if not asyncio.run(_pg_reachable()):
        pytest.skip("PostgreSQL 미도달 — 통합 테스트 건너뜀")

    aid = uuid.uuid4()
    uid = uuid.uuid4()
    pid_in_set = uuid.uuid4()
    pid_unrelated = uuid.uuid4()
    attempt_id = uuid.uuid4()
    pattern_diagnosis = [
        {"kind": "blueprint_test_set", "selected_item_count": 1},
        {"kind": "blueprint_item", "problem_id": str(pid_in_set), "cell_index": 0, "position": 0},
    ]

    async def _measure() -> int:
        engine = create_async_engine(_settings().database_url, poolclass=NullPool)
        try:
            sm = async_sessionmaker(engine, expire_on_commit=False)
            async with sm() as session:
                collection = await collect_test_set_rows(session)
            return build_report(collection).total_unattributable_attempts
        finally:
            await engine.dispose()

    async def _insert() -> None:
        engine = create_async_engine(_settings().database_url, poolclass=NullPool)
        try:
            sm = async_sessionmaker(engine, expire_on_commit=False)
            async with sm() as session:
                session.add(
                    Assessment(
                        assessment_id=aid,
                        user_id=uid,
                        assessment_type=AssessmentType.실전모의고사,
                        pattern_diagnosis=pattern_diagnosis,
                    )
                )
                session.add(
                    ProblemAttempt(attempt_id=attempt_id, user_id=uid, problem_id=pid_unrelated)
                )
                await session.commit()
        finally:
            await engine.dispose()

    async def _cleanup() -> None:
        engine = create_async_engine(_settings().database_url, poolclass=NullPool)
        try:
            async with engine.begin() as conn:
                await conn.execute(
                    delete(ProblemAttempt).where(ProblemAttempt.attempt_id == attempt_id)
                )
                await conn.execute(delete(Assessment).where(Assessment.assessment_id == aid))
        finally:
            await engine.dispose()

    try:
        before = asyncio.run(_measure())
        asyncio.run(_insert())
        after = asyncio.run(_measure())
        assert after == before
    finally:
        asyncio.run(_cleanup())
