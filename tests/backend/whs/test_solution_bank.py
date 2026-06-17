"""WH-S 검증 풀이 저장소(`whs/solution_bank.py`) — 단위(hermetic) + 실 PG 통합.

단위(FakeSession): `bank_solution`의 ORM 구성·add/flush/refresh, 조회 함수의 scalars 반환,
`WhsSolutionGrade` 라벨(verified/unverified·failed 없음)을 hermetic 검증한다. 다중 풀이·grade
필터(`get_verified`가 unverified 격리)·enum 라운드트립은 *실 PG 통합테스트*가 검증한다.
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
from whymath_backend.db.models.verified_solution import (
    VerifiedSolution,
    WhsSolutionGrade,
)
from whymath_backend.whs.solution_bank import (
    bank_solution,
    get_solutions,
    get_verified,
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
    def __init__(self, scalars_list: list[Any]) -> None:
        self._scalars_list = scalars_list

    def scalars(self) -> Any:
        return _FakeScalars(self._scalars_list)


class _FakeSession:
    def __init__(self, *, scalars_list: list[Any] | None = None) -> None:
        self.added: list[Any] = []
        self.flushes = 0
        self.refreshes = 0
        self.executed: list[Any] = []
        self._scalars_list = scalars_list or []

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    async def flush(self) -> None:
        self.flushes += 1

    async def refresh(self, _obj: Any) -> None:
        self.refreshes += 1

    async def execute(self, stmt: Any) -> _FakeResult:
        self.executed.append(stmt)
        return _FakeResult(self._scalars_list)


class TestBankSolutionUnit:
    def test_builds_solution_and_persists(self) -> None:
        """bank_solution이 인자대로 VerifiedSolution을 구성해 add·flush·refresh한다."""
        fake = _FakeSession()
        pid = uuid.uuid4()
        root = uuid.uuid4()
        sol = asyncio.run(
            bank_solution(
                cast(AsyncSession, fake),
                problem_id=pid,
                grade=WhsSolutionGrade.VERIFIED,
                solution_path={"steps": ["x=2"]},
                strategy_tag="대수적",
                answer="2",
                source_root_id=root,
            )
        )
        assert isinstance(sol, VerifiedSolution)
        assert sol.problem_id == pid
        assert sol.grade == WhsSolutionGrade.VERIFIED
        assert sol.solution_path == {"steps": ["x=2"]}
        assert sol.strategy_tag == "대수적"
        assert sol.answer == "2"
        assert sol.source_root_id == root
        assert fake.added == [sol]
        assert fake.flushes == 1
        assert fake.refreshes == 1

    def test_optional_fields_default_none(self) -> None:
        """strategy_tag·answer·source_root_id는 생략 시 None."""
        fake = _FakeSession()
        sol = asyncio.run(
            bank_solution(
                cast(AsyncSession, fake),
                problem_id=uuid.uuid4(),
                grade=WhsSolutionGrade.UNVERIFIED,
                solution_path={"steps": []},
            )
        )
        assert sol.strategy_tag is None
        assert sol.answer is None
        assert sol.source_root_id is None


class TestQueryUnit:
    def test_get_solutions_returns_scalars(self) -> None:
        rows = [
            VerifiedSolution(
                problem_id=uuid.uuid4(),
                grade=WhsSolutionGrade.VERIFIED,
                solution_path={},
            )
        ]
        fake = _FakeSession(scalars_list=rows)
        out = asyncio.run(get_solutions(cast(AsyncSession, fake), uuid.uuid4()))
        assert out == rows

    def test_get_verified_returns_scalars(self) -> None:
        fake = _FakeSession(scalars_list=[])
        out = asyncio.run(get_verified(cast(AsyncSession, fake), uuid.uuid4()))
        assert out == []
        assert len(fake.executed) == 1


class TestEnumValues:
    def test_solution_grade_labels_exclude_failed(self) -> None:
        """저장소 등급은 verified·unverified만(failed 없음 — §2.4·R-S2 구조 차단)."""
        assert [g.value for g in WhsSolutionGrade] == ["verified", "unverified"]


# ===========================================================================
# 통합 (실 PG·기본 SKIP) — 다중 풀이·grade 필터·enum 라운드트립
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
                text("DELETE FROM verified_solutions WHERE problem_id = ANY(:pids)"),
                {"pids": pids},
            )
    finally:
        await engine.dispose()


@pytest.mark.integration
def test_bank_multi_solutions_and_verified_filter_on_live_pg() -> None:
    """다중 풀이 적재·get_solutions(전체)·get_verified(verified만·unverified 격리)·enum 왕복."""
    if not asyncio.run(_pg_reachable()):
        pytest.skip("PostgreSQL 미도달 — 통합 테스트 건너뜀")

    pid = uuid.uuid4()
    other = uuid.uuid4()

    async def _run() -> None:
        engine = create_async_engine(_settings().database_url)
        try:
            sm = async_sessionmaker(engine, expire_on_commit=False)
            async with sm() as session:
                # 한 문제에 다중 풀이(verified 2 + unverified 1)
                await bank_solution(
                    session,
                    problem_id=pid,
                    grade=WhsSolutionGrade.VERIFIED,
                    solution_path={"m": "algebra"},
                    strategy_tag="대수적",
                )
                await bank_solution(
                    session,
                    problem_id=pid,
                    grade=WhsSolutionGrade.VERIFIED,
                    solution_path={"m": "geometry"},
                    strategy_tag="기하적",
                )
                await bank_solution(
                    session,
                    problem_id=pid,
                    grade=WhsSolutionGrade.UNVERIFIED,
                    solution_path={"m": "unsure"},
                )
                # 다른 문제 격리
                await bank_solution(
                    session,
                    problem_id=other,
                    grade=WhsSolutionGrade.VERIFIED,
                    solution_path={"m": "x"},
                )
                await session.commit()

                # get_solutions: 전체 3행(pid)
                all_rows = await get_solutions(session, pid)
                assert len(all_rows) == 3
                # enum 라운드트립
                assert {r.grade for r in all_rows} == {
                    WhsSolutionGrade.VERIFIED,
                    WhsSolutionGrade.UNVERIFIED,
                }

                # get_verified: verified 2행만(unverified 격리·R-S2)
                verified = await get_verified(session, pid)
                assert len(verified) == 2
                assert all(r.grade == WhsSolutionGrade.VERIFIED for r in verified)
                assert {r.strategy_tag for r in verified} == {"대수적", "기하적"}
        finally:
            await engine.dispose()

    try:
        asyncio.run(_run())
    finally:
        asyncio.run(_cleanup([pid, other]))
