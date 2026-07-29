"""achievement_standards 적재 통합테스트 — 실 PostgreSQL 왕복 (기본 SKIP).

`WHYMATH_RUN_INTEGRATION=1` + `[postgres]` extra(sqlalchemy/asyncpg) + 살아있는 PG에서만
실행한다. CI(data-pipeline `[dev]`만 — sqlalchemy 없음)는 ① conftest 게이트(env var 미설정)
② `importorskip`로 이중 skip된다. PG 미도달 시에도 graceful skip.

검증: load_to_postgres가 실 PG에 ① 신규 INSERT ② 같은 code 재적재 시 upsert=True로 UPDATE
③ upsert=False로 DO NOTHING(기존 보존)하는지. 격리를 위해 *전용 테스트 테이블*(uuid 접미사)을
쓰고 끝에 DROP한다 — 앱/staging 테이블을 건드리지 않는다.
"""

from __future__ import annotations

import asyncio
import os
import uuid

import pytest

pytest.importorskip("sqlalchemy")  # [postgres] 미설치(CI data-pipeline)면 모듈 전체 skip

from data_pipeline.ncic.load import _to_async_dsn, load_to_postgres  # noqa: E402
from data_pipeline.ncic.models import AchievementStandard  # noqa: E402
from sqlalchemy import text  # noqa: E402  (importorskip 뒤에 와야 함)
from sqlalchemy.ext.asyncio import create_async_engine  # noqa: E402

pytestmark = pytest.mark.integration

_DSN = os.environ.get("WHYMATH_DATABASE_URL", "postgresql://postgres@127.0.0.1:55432/whymath")


def _sample(statement: str) -> AchievementStandard:
    return AchievementStandard(
        norm_id="2022_9수_01_01",
        code="[9수01-01]",
        grade_band="중학교 1~3학년군",
        school_type="중학교",
        subject="수학",
        domain="수와 연산",
        sub_domain="소인수분해",
        statement=statement,
        source_url="https://www.ncic.go.kr/itest",
    )


async def _reachable() -> bool:
    engine = create_async_engine(_to_async_dsn(_DSN))
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
    finally:
        await engine.dispose()


async def _fetch_statement(table: str, code: str) -> str | None:
    engine = create_async_engine(_to_async_dsn(_DSN))
    try:
        async with engine.connect() as conn:
            res = await conn.execute(
                text(
                    f"SELECT statement FROM {table} WHERE code = :c"
                ),  # noqa: S608 (테스트 전용 테이블명, uuid)
                {"c": code},
            )
            row = res.first()
            return None if row is None else str(row[0])
    finally:
        await engine.dispose()


async def _drop(table: str) -> None:
    engine = create_async_engine(_to_async_dsn(_DSN))
    try:
        async with engine.begin() as conn:
            await conn.execute(text(f"DROP TABLE IF EXISTS {table}"))
    finally:
        await engine.dispose()


def test_load_insert_upsert_and_do_nothing_on_live_pg() -> None:
    """신규 INSERT → upsert UPDATE → upsert=False DO NOTHING 왕복이 실 PG에서 동작."""
    if not asyncio.run(_reachable()):
        pytest.skip("PostgreSQL 미도달 — 통합 테스트 건너뜀 (WHYMATH_DATABASE_URL 확인)")

    table = f"ach_std_itest_{uuid.uuid4().hex[:8]}"
    try:
        # ① 신규 INSERT (create_all로 테이블 자동 생성)
        n1 = asyncio.run(load_to_postgres([_sample("원래 문장")], dsn=_DSN, table_name=table))
        assert n1 == 1
        assert asyncio.run(_fetch_statement(table, "[9수01-01]")) == "원래 문장"

        # ② 같은 code 재적재 — upsert=True면 UPDATE
        asyncio.run(load_to_postgres([_sample("수정된 문장")], dsn=_DSN, table_name=table))
        assert asyncio.run(_fetch_statement(table, "[9수01-01]")) == "수정된 문장"

        # ③ upsert=False — DO NOTHING(기존 보존)
        asyncio.run(
            load_to_postgres([_sample("무시될 문장")], dsn=_DSN, table_name=table, upsert=False)
        )
        assert asyncio.run(_fetch_statement(table, "[9수01-01]")) == "수정된 문장"
    finally:
        asyncio.run(_drop(table))
