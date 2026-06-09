"""L2 문항 난이도 b 보정 — `item_calibration` 단위테스트 (hermetic·FakeSession).

slice 79: `_compute_calibrated_b`(순수 — 인덱싱·JMLE 적합·응답수 임계 필터)와
`calibrate_item_difficulties`(SELECT→보정→UPDATE→commit 글루)를 DB 없이 검증한다. 마이그레이션
↔ORM 정합·실 SQL은 `tests/backend/db/test_problem_irt_b_integration.py`(실 PG)가 가드.
"""

from __future__ import annotations

import uuid
from typing import Any, cast

from sqlalchemy import Select, Update
from sqlalchemy.ext.asyncio import AsyncSession

from whymath_backend.l2 import calibrate_item_difficulties
from whymath_backend.l2.item_calibration import (
    _MIN_RESPONSES_FOR_CALIBRATION,
    _compute_calibrated_b,
)


def _responses(
    item: uuid.UUID, corrects: list[bool]
) -> list[tuple[uuid.UUID, uuid.UUID, bool]]:
    """문항 하나에 학생 N명(각기 다른 user_id)의 정오답 응답을 만든다."""
    return [(uuid.uuid4(), item, c) for c in corrects]


class TestComputeCalibratedB:
    """순수 보정 — 빈 입력·응답수 임계·난이도 방향."""

    def test_empty_returns_empty(self) -> None:
        assert _compute_calibrated_b([]) == {}

    def test_below_threshold_excluded(self) -> None:
        # 응답 < 임계 문항은 보정 보류(휴리스틱 유지).
        item = uuid.uuid4()
        rows = _responses(item, [True] * (_MIN_RESPONSES_FOR_CALIBRATION - 1))
        assert item not in _compute_calibrated_b(rows)

    def test_at_threshold_included(self) -> None:
        # 응답 ≥ 임계 문항은 보정 b를 채택(혼합 응답 → 유한 b).
        item = uuid.uuid4()
        corrects = [k % 2 == 0 for k in range(_MIN_RESPONSES_FOR_CALIBRATION)]
        result = _compute_calibrated_b(_responses(item, corrects))
        assert item in result
        assert isinstance(result[item], float)

    def test_easy_item_lower_b_than_hard(self) -> None:
        # 모두 맞힌 문항(쉬움)은 모두 틀린 문항(어려움)보다 낮은 b로 적합된다.
        students = [uuid.uuid4() for _ in range(_MIN_RESPONSES_FOR_CALIBRATION + 1)]
        easy, hard = uuid.uuid4(), uuid.uuid4()
        rows: list[tuple[uuid.UUID, uuid.UUID, bool]] = []
        for s in students:
            rows.append((s, easy, True))
            rows.append((s, hard, False))
        result = _compute_calibrated_b(rows)
        assert easy in result and hard in result
        assert result[easy] < result[hard]


class _FakeResult:
    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def all(self) -> list[Any]:
        return list(self._rows)


class _FakeSession:
    """SELECT엔 미리 준 응답 행을 돌려주고, UPDATE 호출·commit을 기록(글루만 검증)."""

    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows
        self.updates: list[Update] = []
        self.committed = False

    async def execute(self, stmt: Any) -> _FakeResult:
        if isinstance(stmt, Update):
            self.updates.append(stmt)
            return _FakeResult([])
        assert isinstance(stmt, Select)  # 그 외엔 채점 응답 SELECT
        return _FakeResult(self._rows)

    async def commit(self) -> None:
        self.committed = True


class TestCalibrateItemDifficulties:
    """글루 — SELECT 응답 → 보정 문항만 UPDATE → commit → 보정 수 반환."""

    async def test_updates_and_commits(self) -> None:
        item = uuid.uuid4()
        corrects = [k % 2 == 0 for k in range(_MIN_RESPONSES_FOR_CALIBRATION + 1)]
        rows = _responses(item, corrects)
        sess = _FakeSession(rows)
        n = await calibrate_item_difficulties(cast(AsyncSession, sess))
        assert n == 1  # 1 문항(응답 ≥ 임계) 보정
        assert len(sess.updates) == 1
        assert sess.committed

    async def test_empty_no_updates_still_commits(self) -> None:
        sess = _FakeSession([])
        n = await calibrate_item_difficulties(cast(AsyncSession, sess))
        assert n == 0
        assert sess.updates == []
        assert sess.committed  # 빈 입력도 commit(무해)
