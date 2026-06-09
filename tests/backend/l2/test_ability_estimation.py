"""L2 IRT θ 추정 — `ability_estimation` 단위테스트 (hermetic·FakeSession).

slice 78에 api/me(L5)에서 이관. `difficulty_to_logit`(순수)·`resolve_item_difficulty_b`(보정
b 우선·휴리스틱 폴백)·`estimate_global_ability`·`compute_concept_abilities`(채점 이력 → θ)의
그룹핑·SE·응답수·b 결정 산식을 FakeSession으로 검증한다(WHERE/JOIN 정확성은 me 통합테스트가
실 PG로 — 여기선 stmt 무시·행 가공만). slice 79: 보정 b(`irt_difficulty_b`) 소비 추가.
"""

from __future__ import annotations

import uuid
from typing import Any, cast

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from whymath_backend.l2 import (
    compute_concept_abilities,
    difficulty_to_logit,
    estimate_global_ability,
    resolve_item_difficulty_b,
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


class TestResolveItemDifficultyB:
    """문항 b 결정 — 보정값(irt_difficulty_b) 우선·휴리스틱 폴백·둘 다 없으면 None."""

    def test_calibrated_preferred(self) -> None:
        # 보정값이 있으면 그대로(휴리스틱 0=difficulty 3은 무시).
        assert resolve_item_difficulty_b(2.0, 3.0) == 2.0

    def test_heuristic_fallback(self) -> None:
        # 보정 없음 → difficulty_to_logit(5.0)=2.0.
        assert resolve_item_difficulty_b(None, 5.0) == 2.0

    def test_calibrated_without_expert_difficulty(self) -> None:
        # 전문가 난이도 없어도 보정 b만 있으면 사용(보정 낭비 방지).
        assert resolve_item_difficulty_b(-1.5, None) == -1.5

    def test_both_none_returns_none(self) -> None:
        assert resolve_item_difficulty_b(None, None) is None


class TestEstimateGlobalAbility:
    """전과목 θ·SE·응답수 — (is_correct, difficulty, irt_b) 행 가공."""

    async def test_mixed_responses(self) -> None:
        rows = [(True, 3.0, None), (False, 3.0, None), (True, 4.0, None)]
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

    async def test_excludes_when_no_b_source(self) -> None:
        # 보정 b·전문가 난이도 둘 다 없는 문항 제외.
        rows = [(True, 3.0, None), (False, None, None), (True, 4.0, None)]
        _, _, count = await estimate_global_ability(
            cast(AsyncSession, _FakeSession(rows)), _UID
        )
        assert count == 2

    async def test_includes_calibrated_item_without_expert_difficulty(self) -> None:
        # 전문가 난이도 None이어도 보정 b가 있으면 포함.
        rows = [(True, None, -1.0), (False, None, 1.0)]
        _, _, count = await estimate_global_ability(
            cast(AsyncSession, _FakeSession(rows)), _UID
        )
        assert count == 2

    async def test_all_correct_high_theta(self) -> None:
        rows = [(True, 3.0, None), (True, 4.0, None)]
        theta, _, count = await estimate_global_ability(
            cast(AsyncSession, _FakeSession(rows)), _UID
        )
        assert count == 2
        assert theta > 0  # 전부 정답 → 높은 θ

    async def test_calibrated_b_shifts_theta(self) -> None:
        # 동일 정오답 패턴(맞음·틀림 1개씩)인데 보정 b가 있으면 θ가 이동(보정 b 소비 증거).
        heuristic = await estimate_global_ability(
            cast(AsyncSession, _FakeSession([(True, 3.0, None), (False, 3.0, None)])),
            _UID,
        )
        # 휴리스틱: 두 문항 b=0·한 개 맞고 한 개 틀림 → θ=0(대칭).
        assert heuristic[0] == pytest.approx(0.0)
        # 보정: 어려운 문항(b=3)을 맞힘·중간(b=0)을 틀림 → θ가 양으로 이동.
        calibrated = await estimate_global_ability(
            cast(AsyncSession, _FakeSession([(True, 3.0, 3.0), (False, 3.0, 0.0)])),
            _UID,
        )
        assert calibrated[0] > heuristic[0]


class TestComputeConceptAbilities:
    """개념별 θ — (concept_id, code, name, is_correct, difficulty, irt_b) 행 그룹핑."""

    async def test_groups_by_concept(self) -> None:
        cid_x, cid_y = uuid.uuid4(), uuid.uuid4()
        rows = [
            (cid_x, "A", "가", True, 3.0, None),
            (cid_x, "A", "가", False, 4.0, None),
            (cid_y, "B", "나", True, 3.0, None),
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
        rows = [(cid, None, None, True, 3.0, None), (cid, None, None, False, 4.0, None)]
        items = await compute_concept_abilities(
            cast(AsyncSession, _FakeSession(rows)), _UID
        )
        assert len(items) == 1
        assert items[0].concept_code is None
        assert items[0].concept_name is None

    async def test_calibrated_item_without_expert_difficulty_grouped(self) -> None:
        # 전문가 난이도 None·보정 b 有 문항도 개념 추정에 포함.
        cid = uuid.uuid4()
        rows = [(cid, "C", "다", True, None, -1.0), (cid, "C", "다", False, None, 1.0)]
        items = await compute_concept_abilities(
            cast(AsyncSession, _FakeSession(rows)), _UID
        )
        assert len(items) == 1
        assert items[0].response_count == 2

    async def test_skips_row_without_b_source(self) -> None:
        # 보정 b·전문가 난이도 둘 다 없는 행은 건너뜀(개념 미포함).
        cid = uuid.uuid4()
        rows = [(cid, "C", "다", True, None, None)]
        items = await compute_concept_abilities(
            cast(AsyncSession, _FakeSession(rows)), _UID
        )
        assert items == []
