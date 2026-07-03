"""`get_behavior_areas` 단위테스트 — concept→skill 행동영역 해소 (Part 2 Phase 2b-2·S5k).

DB 없이 가짜 세션으로 로직 분기를 검증한다: concept_node 부재·매핑 없음·중복 제거·정렬·매칭 skill 0.
2-hop 조인(concept_node.behavior_skills→skill_node.behavior_area)의 실 PG 정합은 통합테스트 소관.
"""

from __future__ import annotations

import pytest

from whymath_backend.l1.skill_graph.resolve import get_behavior_areas
from whymath_backend.schema.enums import BehaviorArea


class _FakeNode:
    def __init__(self, behavior_skills: list[str]) -> None:
        self.behavior_skills = behavior_skills


class _FakeResult:
    def __init__(self, values: list[BehaviorArea]) -> None:
        self._values = values

    def scalars(self) -> "_FakeResult":
        return self

    def all(self) -> list[BehaviorArea]:
        return self._values


class _FakeSession:
    """`get`(ConceptNode 반환/None) + `execute`(behavior_area 목록) 디스패치 가짜 세션."""

    def __init__(self, node: object, areas: list[BehaviorArea]) -> None:
        self._node = node
        self._areas = areas
        self.executed = False

    async def get(self, model: object, key: object) -> object:
        return self._node

    async def execute(self, stmt: object) -> _FakeResult:
        self.executed = True
        return _FakeResult(self._areas)


@pytest.mark.asyncio
async def test_missing_concept_node_returns_empty() -> None:
    """concept_node 부재 → 빈 목록·조인 미실행(미매핑=중립)."""
    session = _FakeSession(node=None, areas=[])
    assert await get_behavior_areas(session, "UC-NONE") == []  # type: ignore[arg-type]
    assert session.executed is False


@pytest.mark.asyncio
async def test_no_behavior_skills_returns_empty() -> None:
    """behavior_skills 빈 배열 → 빈 목록·조인 미실행(조기 반환)."""
    session = _FakeSession(node=_FakeNode([]), areas=[BehaviorArea.COMPUTE])
    assert await get_behavior_areas(session, "UC-1") == []  # type: ignore[arg-type]
    assert session.executed is False


@pytest.mark.asyncio
async def test_dedup_and_sorted() -> None:
    """중복 행동영역 제거 + enum 값 정렬(결정론)."""
    session = _FakeSession(
        node=_FakeNode(["skill.a", "skill.b", "skill.c"]),
        areas=[BehaviorArea.VERIFY, BehaviorArea.COMPUTE, BehaviorArea.COMPUTE],
    )
    result = await get_behavior_areas(session, "UC-1")  # type: ignore[arg-type]
    assert result == [BehaviorArea.COMPUTE, BehaviorArea.VERIFY]  # "COMPUTE" < "VERIFY"


@pytest.mark.asyncio
async def test_no_matching_skills_returns_empty() -> None:
    """behavior_skills는 있으나 매칭 skill_node 0 → 빈 목록."""
    session = _FakeSession(node=_FakeNode(["skill.orphan"]), areas=[])
    assert await get_behavior_areas(session, "UC-1") == []  # type: ignore[arg-type]
    assert session.executed is True
