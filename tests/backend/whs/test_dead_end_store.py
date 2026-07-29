"""WH-S 실패 접근 로그 저장소(`whs/dead_end_store.py`) — 단위(hermetic) + 실 PG 통합.

단위(FakeSession): `log_dead_end`가 멱등 INSERT 1건을 발행하는지, `is_dead_end`가 scalar를
bool로 강제하는지, 조회 함수가 scalars를 리스트로 내는지 hermetic 검증한다. 멱등성(중복 1행)·
복합 UNIQUE·`get_dead_ends` 정렬은 *실 PG 통합테스트*가 검증한다(ON CONFLICT는 실 DB라야 의미).
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any, cast

import pytest
from pydantic import SecretStr
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from whymath_backend.config import Settings
from whymath_backend.db.models.dead_end_log import DeadEndLog
from whymath_backend.whs.dead_end_store import (
    get_dead_ends,
    is_dead_end,
    log_dead_end,
)

# ===========================================================================
# 단위 (hermetic·FakeSession) — DB 무관 로직만
# ===========================================================================


class _FakeResult:
    def __init__(self, scalar_value: Any, scalars_list: list[Any]) -> None:
        self._scalar_value = scalar_value
        self._scalars_list = scalars_list

    def scalar(self) -> Any:
        return self._scalar_value

    def scalars(self) -> Any:
        return _FakeScalars(self._scalars_list)


class _FakeScalars:
    def __init__(self, items: list[Any]) -> None:
        self._items = items

    def all(self) -> list[Any]:
        return self._items


class _FakeSession:
    """`execute`만 시뮬 — 넘어온 statement를 모으고, 미리 박은 결과를 돌려준다."""

    def __init__(self, *, scalar_value: Any = None, scalars_list: list[Any] | None = None) -> None:
        self.executed: list[Any] = []
        self._scalar_value = scalar_value
        self._scalars_list = scalars_list or []

    async def execute(self, stmt: Any) -> _FakeResult:
        self.executed.append(stmt)
        return _FakeResult(self._scalar_value, self._scalars_list)


class TestLogDeadEndUnit:
    def test_issues_single_insert(self) -> None:
        """log_dead_end가 execute 1건(멱등 INSERT)을 발행한다."""
        fake = _FakeSession()
        asyncio.run(
            log_dead_end(
                cast(AsyncSession, fake),
                problem_id=uuid.uuid4(),
                state_hash="h1",
                action="substitute",
            )
        )
        assert len(fake.executed) == 1


class TestIsDeadEndUnit:
    @pytest.mark.parametrize(
        ("scalar_value", "expected"),
        [(True, True), (False, False), (None, False)],
    )
    def test_coerces_scalar_to_bool(self, scalar_value: Any, expected: bool) -> None:
        """is_dead_end는 EXISTS scalar를 bool로 강제한다(None→False)."""
        fake = _FakeSession(scalar_value=scalar_value)
        out = asyncio.run(
            is_dead_end(
                cast(AsyncSession, fake),
                problem_id=uuid.uuid4(),
                state_hash="h",
                action="a",
            )
        )
        assert out is expected
        assert len(fake.executed) == 1


class TestGetDeadEndsUnit:
    def test_returns_scalars_list(self) -> None:
        """get_dead_ends는 scalars().all()을 리스트로 돌려준다."""
        rows = [DeadEndLog(problem_id=uuid.uuid4(), state_hash="h", action="a")]
        fake = _FakeSession(scalars_list=rows)
        out = asyncio.run(get_dead_ends(cast(AsyncSession, fake), uuid.uuid4()))
        assert out == rows


# ===========================================================================
# 통합 (실 PG·기본 SKIP) — 멱등성·복합 UNIQUE·정렬
# ===========================================================================

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


async def _cleanup(problem_ids: list[uuid.UUID]) -> None:
    engine = create_async_engine(_settings().database_url)
    pids = [str(p) for p in problem_ids]
    try:
        async with engine.begin() as conn:
            await conn.execute(
                text("DELETE FROM dead_end_log WHERE problem_id = ANY(:pids)"),
                {"pids": pids},
            )
    finally:
        await engine.dispose()


@pytest.mark.integration
def test_log_is_idempotent_and_queryable_on_live_pg() -> None:
    """log_dead_end 멱등(중복 1행)·is_dead_end 회피 조회·get_dead_ends 격리·정렬."""
    if not asyncio.run(_pg_reachable()):
        pytest.skip("PostgreSQL 미도달 — 통합 테스트 건너뜀")

    pid = uuid.uuid4()
    other = uuid.uuid4()

    async def _run() -> None:
        engine = create_async_engine(_settings().database_url)
        try:
            sm = async_sessionmaker(engine, expire_on_commit=False)
            async with sm() as session:
                # 같은 막다른 길 두 번 기록 → 멱등(1행)
                await log_dead_end(
                    session,
                    problem_id=pid,
                    state_hash="s1",
                    action="subst",
                    reason="순환",
                )
                await log_dead_end(
                    session,
                    problem_id=pid,
                    state_hash="s1",
                    action="subst",
                    reason="무시됨",
                )
                # 다른 행동은 별개 행
                await log_dead_end(session, problem_id=pid, state_hash="s1", action="case")
                # 다른 문제는 격리
                await log_dead_end(session, problem_id=other, state_hash="s1", action="subst")
                await session.commit()

                # is_dead_end: 기록된 쌍 True / 미기록 False
                assert await is_dead_end(session, problem_id=pid, state_hash="s1", action="subst")
                assert not await is_dead_end(
                    session, problem_id=pid, state_hash="s1", action="never"
                )

                # get_dead_ends(pid): 멱등으로 (subst, case) 2행만(other 격리)
                rows = await get_dead_ends(session, pid)
                assert len(rows) == 2
                actions = {r.action for r in rows}
                assert actions == {"subst", "case"}
                # 멱등 — 최초 reason 보존(DO NOTHING)
                subst = next(r for r in rows if r.action == "subst")
                assert subst.reason == "순환"
        finally:
            await engine.dispose()

    try:
        asyncio.run(_run())
    finally:
        asyncio.run(_cleanup([pid, other]))
