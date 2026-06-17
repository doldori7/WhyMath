"""WH-S 검증 보조정리 저장소(`whs/lemma_store.py`) — 단위(hermetic) + 실 PG 통합.

단위(FakeSession): `log_lemma`가 멱등 INSERT 1건을 발행하는지, `find_lemma`가 scalar_one_or_none
을 전파하는지, `get_lemmas`가 scalars를 리스트로 내는지 hermetic 검증한다. 멱등성(중복 1행)·복합
UNIQUE·재사용 조회는 *실 PG 통합테스트*가 검증한다(ON CONFLICT는 실 DB라야 의미).
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
from whymath_backend.db.models.verified_lemma import VerifiedLemma
from whymath_backend.whs.lemma_store import (
    find_lemma,
    get_lemmas,
    log_lemma,
)

# ===========================================================================
# 단위 (hermetic·FakeSession)
# ===========================================================================


class _FakeScalars:
    def __init__(self, items: list[Any]) -> None:
        self._items = items

    def all(self) -> list[Any]:
        return self._items


class _FakeResult:
    def __init__(self, *, scalar_one: Any = None, scalars_list: list[Any] | None = None) -> None:
        self._scalar_one = scalar_one
        self._scalars_list = scalars_list or []

    def scalar_one_or_none(self) -> Any:
        return self._scalar_one

    def scalars(self) -> Any:
        return _FakeScalars(self._scalars_list)


class _FakeSession:
    def __init__(self, *, scalar_one: Any = None, scalars_list: list[Any] | None = None) -> None:
        self.executed: list[Any] = []
        self._scalar_one = scalar_one
        self._scalars_list = scalars_list or []

    async def execute(self, stmt: Any) -> _FakeResult:
        self.executed.append(stmt)
        return _FakeResult(scalar_one=self._scalar_one, scalars_list=self._scalars_list)


class TestLogLemmaUnit:
    def test_issues_single_insert(self) -> None:
        """log_lemma가 execute 1건(멱등 INSERT)을 발행한다."""
        fake = _FakeSession()
        asyncio.run(
            log_lemma(
                cast(AsyncSession, fake),
                problem_id=uuid.uuid4(),
                lemma_key="mono:x>0",
                lemma_repr={"fact": "increasing"},
            )
        )
        assert len(fake.executed) == 1


class TestFindLemmaUnit:
    def test_returns_scalar_one_or_none(self) -> None:
        """find_lemma는 scalar_one_or_none을 그대로 전파한다(매칭 시 행·미스 시 None)."""
        lemma = VerifiedLemma(problem_id=uuid.uuid4(), lemma_key="k", lemma_repr={})
        hit = _FakeSession(scalar_one=lemma)
        out = asyncio.run(
            find_lemma(cast(AsyncSession, hit), problem_id=uuid.uuid4(), lemma_key="k")
        )
        assert out is lemma

        miss = _FakeSession(scalar_one=None)
        out2 = asyncio.run(
            find_lemma(cast(AsyncSession, miss), problem_id=uuid.uuid4(), lemma_key="k")
        )
        assert out2 is None


class TestGetLemmasUnit:
    def test_returns_scalars_list(self) -> None:
        rows = [VerifiedLemma(problem_id=uuid.uuid4(), lemma_key="k", lemma_repr={})]
        fake = _FakeSession(scalars_list=rows)
        out = asyncio.run(get_lemmas(cast(AsyncSession, fake), uuid.uuid4()))
        assert out == rows


# ===========================================================================
# 통합 (실 PG·기본 SKIP) — 멱등성·재사용 조회·정렬
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
                text("DELETE FROM verified_lemmas WHERE problem_id = ANY(:pids)"),
                {"pids": pids},
            )
    finally:
        await engine.dispose()


@pytest.mark.integration
def test_log_idempotent_and_reuse_lookup_on_live_pg() -> None:
    """log_lemma 멱등(중복 1행·최초 보존)·find_lemma 재사용 조회·get_lemmas 격리·정렬."""
    if not asyncio.run(_pg_reachable()):
        pytest.skip("PostgreSQL 미도달 — 통합 테스트 건너뜀")

    pid = uuid.uuid4()
    other = uuid.uuid4()

    async def _run() -> None:
        engine = create_async_engine(_settings().database_url)
        try:
            sm = async_sessionmaker(engine, expire_on_commit=False)
            async with sm() as session:
                # 같은 보조정리(키) 두 번 적재 → 멱등(1행·최초 statement 보존)
                await log_lemma(
                    session,
                    problem_id=pid,
                    lemma_key="mono:x>0",
                    lemma_repr={"fact": "increasing"},
                    statement="x>0에서 단조증가",
                )
                await log_lemma(
                    session,
                    problem_id=pid,
                    lemma_key="mono:x>0",
                    lemma_repr={"fact": "무시됨"},
                    statement="무시됨",
                )
                # 다른 키는 별개 행
                await log_lemma(
                    session, problem_id=pid, lemma_key="bound:>=0", lemma_repr={"fact": "nonneg"}
                )
                # 다른 문제는 격리
                await log_lemma(
                    session, problem_id=other, lemma_key="mono:x>0", lemma_repr={"fact": "x"}
                )
                await session.commit()

                # find_lemma: 재사용 조회 — 매칭 시 최초 repr·statement 보존
                hit = await find_lemma(session, problem_id=pid, lemma_key="mono:x>0")
                assert hit is not None
                assert hit.lemma_repr == {"fact": "increasing"}
                assert hit.statement == "x>0에서 단조증가"
                # 미스
                assert await find_lemma(session, problem_id=pid, lemma_key="never") is None

                # get_lemmas(pid): 멱등으로 2개 키만(other 격리)
                rows = await get_lemmas(session, pid)
                assert len(rows) == 2
                assert {r.lemma_key for r in rows} == {"mono:x>0", "bound:>=0"}
        finally:
            await engine.dispose()

    try:
        asyncio.run(_run())
    finally:
        asyncio.run(_cleanup([pid, other]))
