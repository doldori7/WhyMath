"""L2 IRT θ 현재값 읽기 — `get_current_theta` 단위테스트 (hermetic).

`get_current_theta`(최신 전과목 `AbilitySnapshot`의 theta)의 *래퍼 로직*(스칼라→float|None)을
검증한다. WHERE(`concept_id IS NULL`)·ORDER BY(`measured_at DESC`) 정확성은 통합테스트가 실
PG로 검증(`tests/backend/db/test_ability_snapshot_integration.py`) — `mastery_tracking`의
단위/통합 분리 패턴과 동일.
"""

from __future__ import annotations

import uuid
from typing import Any, cast

from sqlalchemy.ext.asyncio import AsyncSession
from whymath_backend.l2 import get_current_ability, get_current_theta

_UID = uuid.uuid4()


class _FakeResult:
    def __init__(self, value: Any) -> None:
        self._value = value

    def scalars(self) -> _FakeResult:
        return self

    def first(self) -> Any:
        return self._value


class _FakeSession:
    """`get_current_theta`의 SELECT(최신 θ 스칼라)만 시뮬(stmt 무시).

    정렬·`concept_id IS NULL` 필터는 통합테스트가 실 PG로 검증 — 여기선 스칼라→float|None만.
    """

    def __init__(self, theta: Any) -> None:
        self._theta = theta

    async def execute(self, _stmt: Any) -> _FakeResult:
        return _FakeResult(self._theta)


class _RowSession:
    """`get_current_ability`의 SELECT(θ·SE·response_count Row 1건)만 시뮬(stmt 무시).

    `.first()`로 Row(튜플)를 받는 경로 — 필터/정렬은 통합테스트가 실 PG로 검증.
    """

    def __init__(self, row: Any) -> None:
        self._row = row

    async def execute(self, _stmt: Any) -> _FakeResult:
        return _FakeResult(self._row)


class TestGetCurrentAbility:
    """slice 76: θ + 신뢰도(SE·응답수) 읽기 — Row→AbilityReading·없으면 None(가드 입력)."""

    async def test_returns_reading(self) -> None:
        fake = _RowSession(row=(1.5, 0.4, 5))
        reading = await get_current_ability(cast(AsyncSession, fake), _UID)
        assert reading is not None
        assert reading.theta == 1.5
        assert reading.standard_error == 0.4
        assert reading.response_count == 5

    async def test_returns_none_when_no_snapshot(self) -> None:
        fake = _RowSession(row=None)
        assert await get_current_ability(cast(AsyncSession, fake), _UID) is None

    async def test_handles_null_standard_error(self) -> None:
        # 극단 θ(정보 0)면 SE가 None으로 저장 — 그대로 None 통과(가드가 불신뢰 판정).
        fake = _RowSession(row=(4.0, None, 1))
        reading = await get_current_ability(cast(AsyncSession, fake), _UID)
        assert reading is not None
        assert reading.standard_error is None
        assert reading.theta == 4.0
        assert reading.response_count == 1

    async def test_accepts_concept_id(self) -> None:
        # 개념별 조회(slice 74/76) — 래퍼는 Row 통과. WHERE(concept_id==X)는 통합 검증.
        fake = _RowSession(row=(0.8, 0.5, 7))
        cid = uuid.uuid4()
        reading = await get_current_ability(cast(AsyncSession, fake), _UID, cid)
        assert reading is not None and reading.theta == 0.8


class TestGetCurrentTheta:
    """slice 73: 학생 현재 전과목 θ 읽기 — 최신 스냅샷 theta·없으면 None."""

    async def test_returns_latest_theta(self) -> None:
        fake = _FakeSession(theta=1.5)
        assert await get_current_theta(cast(AsyncSession, fake), _UID) == 1.5

    async def test_returns_none_when_no_snapshot(self) -> None:
        fake = _FakeSession(theta=None)
        assert await get_current_theta(cast(AsyncSession, fake), _UID) is None

    async def test_casts_to_float(self) -> None:
        # 스칼라가 정수여도 float로 환산(저장 타입 대비 — float() 일관 반환).
        fake = _FakeSession(theta=2)
        result = await get_current_theta(cast(AsyncSession, fake), _UID)
        assert result == 2.0
        assert isinstance(result, float)

    async def test_accepts_concept_id(self) -> None:
        # 개념별 조회(slice 74) — 래퍼는 스칼라 통과. WHERE(concept_id==X) 정확성은 통합 검증.
        fake = _FakeSession(theta=0.8)
        cid = uuid.uuid4()
        assert await get_current_theta(cast(AsyncSession, fake), _UID, cid) == 0.8
