"""SolutionPath 조회 store(`l3/solution_path_store.py`) 테스트 — S4-09 (hermetic).

FakeSession(execute 표면만)으로 결선 검증: 결정적 정렬 조회(`get_solution_paths`)·첫 경로 id
단건(`find_solution_path_id` — StepPanelElement 결선의 하부). 실 SQL·인덱스 사용은 실 PG
통합 몫(`test_solution_bank.py` 이원화 선례).
"""

from __future__ import annotations

import uuid
from typing import Any, cast

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from whymath_backend.db.models.solution_path import SolutionPath
from whymath_backend.l3.solution_path_store import (
    find_solution_path_id,
    get_solution_paths,
)


class _FakeScalars:
    def __init__(self, items: list[Any]) -> None:
        self._items = items

    def all(self) -> list[Any]:
        return self._items

    def first(self) -> Any | None:
        return self._items[0] if self._items else None


class _FakeResult:
    def __init__(self, items: list[Any]) -> None:
        self._items = items

    def scalars(self) -> _FakeScalars:
        return _FakeScalars(self._items)


class _FakeSession:
    def __init__(self, items: list[Any]) -> None:
        self._items = items
        self.executed = 0

    async def execute(self, _stmt: Any) -> _FakeResult:
        self.executed += 1
        return _FakeResult(self._items)


def _orm_path(path_id: str) -> SolutionPath:
    return SolutionPath(
        solution_path_id=path_id,
        problem_id=uuid.uuid4(),
        approach_type="algebraic",
        concept_sequence=[],
        verified_by_human=False,
    )


class TestGetSolutionPaths:
    @pytest.mark.asyncio
    async def test_returns_rows_as_list(self) -> None:
        """조회 행을 리스트로 반환(읽기 전용·commit 없음)."""
        rows = [_orm_path("sp-1"), _orm_path("sp-2")]
        session = _FakeSession(rows)
        out = await get_solution_paths(cast(AsyncSession, session), uuid.uuid4())
        assert out == rows
        assert session.executed == 1

    @pytest.mark.asyncio
    async def test_empty_when_no_paths(self) -> None:
        out = await get_solution_paths(cast(AsyncSession, _FakeSession([])), uuid.uuid4())
        assert out == []


class TestFindSolutionPathId:
    @pytest.mark.asyncio
    async def test_returns_first_id(self) -> None:
        """첫 경로 id 반환 — StepPanelElement.solution_path_id 결선 재료."""
        session = _FakeSession(["sp-first", "sp-second"])
        assert await find_solution_path_id(cast(AsyncSession, session), uuid.uuid4()) == "sp-first"

    @pytest.mark.asyncio
    async def test_none_when_no_promoted_path(self) -> None:
        """승격 경로 없으면 None — 댕글링 참조를 만들 근거 없음(날조 금지)."""
        session = cast(AsyncSession, _FakeSession([]))
        assert await find_solution_path_id(session, uuid.uuid4()) is None
