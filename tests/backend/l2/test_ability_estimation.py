"""L2 IRT θ 추정 — `ability_estimation` 단위테스트 (hermetic·FakeSession).

slice 78에 api/me(L5)에서 이관. `difficulty_to_logit`(순수)·`estimate_global_ability`·
`compute_concept_abilities`(채점 이력 → θ)의 그룹핑·SE·응답수 산식을 FakeSession으로 검증한다
(WHERE/JOIN 정확성은 me 통합테스트가 실 PG로 — 여기선 stmt 무시·행 가공만).
"""

from __future__ import annotations

import uuid
from typing import Any, cast

from sqlalchemy.ext.asyncio import AsyncSession

from whymath_backend.l2 import (
    compute_concept_abilities,
    difficulty_to_logit,
    estimate_global_ability,
)

_UID = uuid.uuid4()


class _FakeResult:
    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def all(self) -> list[Any]:
        return list(self._rows)


class _FakeSession:
    """execute(stmt)를 무시하고 미리 준 행을 `.all()`로 반환(추정 산식만 검증)."""

    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    async def execute(self, _stmt: Any) -> _FakeResult:
        return _FakeResult(self._rows)


class TestDifficultyToLogit:
    """난이도(1~5) → logit b(중앙 3=0·선형)."""

    def test_midpoint_zero(self) -> None:
        assert difficulty_to_logit(3.0) == 0.0

    def test_easy_negative(self) -> None:
        assert difficulty_to_logit(1.0) == -2.0

    def test_hard_positive(self) -> None:
        assert difficulty_to_logit(5.0) == 2.0


class TestEstimateGlobalAbility:
    """전과목 θ·SE·응답수 — (is_correct, difficulty) 행 가공."""

    async def test_mixed_responses(self) -> None:
        rows = [(True, 3.0), (False, 3.0), (True, 4.0)]
        theta, se, count = await estimate_global_ability(
            cast(AsyncSession, _FakeSession(rows)), _UID
        )
        assert count == 3
        assert isinstance(theta, float)
        assert se is not None  # 혼합 → Fisher 정보 > 0 → SE 유한

    async def test_no_responses_se_none(self) -> None:
        theta, se, count = await estimate_global_ability(
            cast(AsyncSession, _FakeSession([])), _UID
        )
        assert count == 0
        assert se is None  # 정보 0 → 측정 불가

    async def test_excludes_null_difficulty(self) -> None:
        rows = [(True, 3.0), (False, None), (True, 4.0)]
        _, _, count = await estimate_global_ability(
            cast(AsyncSession, _FakeSession(rows)), _UID
        )
        assert count == 2  # 난이도 None 문항 제외

    async def test_all_correct_high_theta(self) -> None:
        rows = [(True, 3.0), (True, 4.0)]
        theta, _, count = await estimate_global_ability(
            cast(AsyncSession, _FakeSession(rows)), _UID
        )
        assert count == 2
        assert theta > 0  # 전부 정답 → 높은 θ


class TestComputeConceptAbilities:
    """개념별 θ — (concept_id, code, name, is_correct, difficulty) 행 그룹핑."""

    async def test_groups_by_concept(self) -> None:
        cid_x, cid_y = uuid.uuid4(), uuid.uuid4()
        rows = [
            (cid_x, "A", "가", True, 3.0),
            (cid_x, "A", "가", False, 4.0),
            (cid_y, "B", "나", True, 3.0),
        ]
        items = await compute_concept_abilities(
            cast(AsyncSession, _FakeSession(rows)), _UID
        )
        by_id = {i.concept_id: i for i in items}
        assert set(by_id) == {cid_x, cid_y}
        assert by_id[cid_x].response_count == 2
        assert by_id[cid_x].concept_code == "A"
        assert by_id[cid_x].concept_name == "가"
        assert by_id[cid_y].response_count == 1

    async def test_empty(self) -> None:
        items = await compute_concept_abilities(
            cast(AsyncSession, _FakeSession([])), _UID
        )
        assert items == []

    async def test_orphan_concept_null_meta(self) -> None:
        # Concept LEFT JOIN orphan → code/name None.
        cid = uuid.uuid4()
        rows = [(cid, None, None, True, 3.0), (cid, None, None, False, 4.0)]
        items = await compute_concept_abilities(
            cast(AsyncSession, _FakeSession(rows)), _UID
        )
        assert len(items) == 1
        assert items[0].concept_code is None
        assert items[0].concept_name is None
