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
    get_all_verified,
    get_solutions,
    get_verified,
    solution_fingerprint,
    stream_all_verified,
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


class _FakeAsyncScalars:
    """`stream_scalars` 반환을 흉내 — 행을 *한 건씩* 비동기로 흘리는 async 이터러블."""

    def __init__(self, items: list[Any]) -> None:
        self._items = items

    async def __aiter__(self) -> Any:
        for item in self._items:
            yield item


class _FakeSession:
    def __init__(self, *, scalars_list: list[Any] | None = None) -> None:
        self.added: list[Any] = []
        self.flushes = 0
        self.refreshes = 0
        self.executed: list[Any] = []
        self.streamed: list[Any] = []
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

    async def stream_scalars(self, stmt: Any) -> _FakeAsyncScalars:
        self.streamed.append(stmt)
        return _FakeAsyncScalars(self._scalars_list)


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

    def test_get_all_verified_returns_scalars(self) -> None:
        """get_all_verified는 problem_id 인자 없이 전 문제 verified 행(scalars)을 반환한다."""
        rows = [
            VerifiedSolution(
                problem_id=uuid.uuid4(),
                grade=WhsSolutionGrade.VERIFIED,
                solution_path={"s": 1},
            )
        ]
        fake = _FakeSession(scalars_list=rows)
        out = asyncio.run(get_all_verified(cast(AsyncSession, fake)))
        assert out == rows
        assert len(fake.executed) == 1  # 단일 SELECT 발행

    def test_stream_all_verified_yields_scalars_in_order(self) -> None:
        """stream_all_verified는 서버측 커서(stream_scalars)로 행을 순서대로 1건씩 yield한다."""
        rows = [
            VerifiedSolution(
                problem_id=uuid.uuid4(),
                grade=WhsSolutionGrade.VERIFIED,
                solution_path={"s": i},
            )
            for i in range(3)
        ]
        fake = _FakeSession(scalars_list=rows)

        async def _collect() -> list[VerifiedSolution]:
            return [sol async for sol in stream_all_verified(cast(AsyncSession, fake))]

        out = asyncio.run(_collect())
        assert out == rows  # 순서 보존
        assert len(fake.streamed) == 1  # stream_scalars 단일 발행
        assert fake.executed == []  # execute(전량 적재) 미사용

    def test_stream_all_verified_empty(self) -> None:
        """verified 0건이면 빈 스트림(yield 0)."""
        fake = _FakeSession(scalars_list=[])

        async def _collect() -> list[VerifiedSolution]:
            return [sol async for sol in stream_all_verified(cast(AsyncSession, fake))]

        assert asyncio.run(_collect()) == []
        assert len(fake.streamed) == 1


class TestSolutionFingerprint:
    def test_key_order_independent(self) -> None:
        """키 순서가 달라도 내용이 같으면 같은 지문(정규 JSON·dedup 안정성)."""
        a = solution_fingerprint({"steps": ["x=2"], "k": 1})
        b = solution_fingerprint({"k": 1, "steps": ["x=2"]})
        assert a == b and len(a) == 64

    def test_different_path_differs(self) -> None:
        """경로 내용이 다르면 지문도 다르다."""
        assert solution_fingerprint({"steps": ["x=2"]}) != solution_fingerprint({"steps": ["x=3"]})


class TestBankSolutionDedup:
    def test_dedup_skips_identical_same_grade_path(self) -> None:
        """dedup=True + 같은 grade·동일 경로 기존 행 → 적재 안 하고 기존 행 반환(idempotent)."""
        pid = uuid.uuid4()
        existing = VerifiedSolution(
            problem_id=pid, grade=WhsSolutionGrade.VERIFIED, solution_path={"steps": ["x=2"]}
        )
        fake = _FakeSession(scalars_list=[existing])
        out = asyncio.run(
            bank_solution(
                cast(AsyncSession, fake),
                problem_id=pid,
                grade=WhsSolutionGrade.VERIFIED,
                solution_path={"steps": ["x=2"]},  # 동일 경로(키 순서 무관)
                dedup=True,
            )
        )
        assert out is existing  # 기존 행 반환
        assert fake.added == []  # 새 적재 0
        assert fake.flushes == 0

    def test_dedup_allows_different_path(self) -> None:
        """dedup=True여도 경로가 다르면 새로 적재한다(다중 전략 보존)."""
        pid = uuid.uuid4()
        existing = VerifiedSolution(
            problem_id=pid, grade=WhsSolutionGrade.VERIFIED, solution_path={"steps": ["x=2"]}
        )
        fake = _FakeSession(scalars_list=[existing])
        out = asyncio.run(
            bank_solution(
                cast(AsyncSession, fake),
                problem_id=pid,
                grade=WhsSolutionGrade.VERIFIED,
                solution_path={"steps": ["x=3"]},  # 다른 경로
                dedup=True,
            )
        )
        assert out is not existing and fake.added == [out]  # 새로 적재

    def test_dedup_different_grade_not_deduped(self) -> None:
        """같은 경로라도 grade가 다르면 dedup 안 함(verified vs unverified는 별개 레코드)."""
        pid = uuid.uuid4()
        existing = VerifiedSolution(
            problem_id=pid, grade=WhsSolutionGrade.UNVERIFIED, solution_path={"steps": ["x=2"]}
        )
        fake = _FakeSession(scalars_list=[existing])
        out = asyncio.run(
            bank_solution(
                cast(AsyncSession, fake),
                problem_id=pid,
                grade=WhsSolutionGrade.VERIFIED,  # 다른 grade
                solution_path={"steps": ["x=2"]},
                dedup=True,
            )
        )
        assert out is not existing and fake.added == [out]

    def test_dedup_false_always_inserts(self) -> None:
        """dedup 기본(False) → 동일 경로라도 항상 적재(하위호환·조회 안 함)."""
        pid = uuid.uuid4()
        existing = VerifiedSolution(
            problem_id=pid, grade=WhsSolutionGrade.VERIFIED, solution_path={"steps": ["x=2"]}
        )
        fake = _FakeSession(scalars_list=[existing])
        out = asyncio.run(
            bank_solution(
                cast(AsyncSession, fake),
                problem_id=pid,
                grade=WhsSolutionGrade.VERIFIED,
                solution_path={"steps": ["x=2"]},
            )
        )
        assert fake.added == [out]  # 적재됨
        assert fake.executed == []  # dedup 조회 안 함(기존 행 미조회)


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

                # get_all_verified: 전 문제 verified만(grade 전부 verified·pid+other 포함·R-S2)
                all_verified = await get_all_verified(session)
                assert all(r.grade == WhsSolutionGrade.VERIFIED for r in all_verified)
                all_ids = {r.id for r in all_verified}
                assert {r.id for r in verified} <= all_ids  # pid verified 포함
                assert {r.problem_id for r in all_verified} >= {pid, other}  # other도 수집

                # stream_all_verified: 서버측 커서 스트리밍이 get_all_verified와 동일 집합·순서
                streamed = [r async for r in stream_all_verified(session)]
                assert [r.id for r in streamed] == [r.id for r in all_verified]
                assert all(r.grade == WhsSolutionGrade.VERIFIED for r in streamed)
        finally:
            await engine.dispose()

    try:
        asyncio.run(_run())
    finally:
        asyncio.run(_cleanup([pid, other]))
