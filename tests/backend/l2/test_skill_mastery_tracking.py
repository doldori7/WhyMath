"""L2 BKT↔SkillMasteryHistory 결선 — 스킬 축 단위테스트 (hermetic·Part 2 Phase 2b-2).

순수 커널(`compute_mastery_record`)은 `mastery_tracking`(개념 축)과 *동일 재사용*이라 여기선
스킬 축 고유 로직만 본다: ① `get_current_skill_mastery` 읽기 ② `_assessed_skill_ids` 해소
③ `record_problem_attempt_skill_mastery`의 모델 B 전파(정답=전체 개념 스킬·오답=PRIMARY 스킬·
TESTED 폴백). 실 PG 조인(concept→skill·mastery_estimable 게이트)은 통합테스트가 검증.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy.ext.asyncio import AsyncSession
from whymath_backend.db.models.assessment import SkillMasteryHistory
from whymath_backend.l2 import BktModel
from whymath_backend.l2.skill_mastery_tracking import (
    get_current_skill_mastery,
    record_problem_attempt_skill_mastery,
)

_M = BktModel()
_UID = uuid.uuid4()
_SID = "skill.compute-fraction"


class _FakeResult:
    def __init__(self, row: Any) -> None:
        self._row = row

    def scalars(self) -> _FakeResult:
        return self

    def first(self) -> Any:
        return self._row


class _FakeSession:
    """`_latest_skill_mastery` 단건 SELECT·add·commit 시뮬(stmt 무시)."""

    def __init__(self, prior: SkillMasteryHistory | None = None) -> None:
        self._prior = prior
        self.added: list[Any] = []
        self.commits = 0

    async def execute(self, _stmt: Any) -> _FakeResult:
        return _FakeResult(self._prior)

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    async def commit(self) -> None:
        self.commits += 1


class _QResult:
    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def scalars(self) -> _QResult:
        return self

    def all(self) -> list[Any]:
        return self._rows

    def first(self) -> Any:
        return self._rows[0] if self._rows else None


class _QueueSession:
    """execute 호출마다 미리 큐잉한 결과를 순서대로 반환 — 다중 쿼리(개념 → 스킬 → 스킬별 prior)."""

    def __init__(self, results: list[_QResult]) -> None:
        self._results = results
        self._i = 0
        self.added: list[Any] = []
        self.commits = 0

    async def execute(self, _stmt: Any) -> _QResult:
        result = self._results[self._i]
        self._i += 1
        return result

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    async def commit(self) -> None:
        self.commits += 1


def _prior_row(mastery: float | None, sample_size: int | None) -> SkillMasteryHistory:
    return SkillMasteryHistory(
        user_id=_UID,
        skill_id=_SID,
        measured_at=datetime(2026, 1, 1, tzinfo=UTC),
        mastery=mastery,
        confidence=None,
        sample_size=sample_size,
    )


class TestGetCurrentSkillMastery:
    """(user, skill) 현재 숙달도 — 최신 측정 mastery·없거나 NULL이면 None."""

    async def test_returns_latest_mastery(self) -> None:
        fake = _FakeSession(prior=_prior_row(0.75, 5))
        assert await get_current_skill_mastery(cast(AsyncSession, fake), _UID, _SID) == 0.75

    async def test_returns_none_when_no_history(self) -> None:
        fake = _FakeSession(prior=None)
        assert await get_current_skill_mastery(cast(AsyncSession, fake), _UID, _SID) is None

    async def test_returns_none_when_mastery_null(self) -> None:
        fake = _FakeSession(prior=_prior_row(None, None))
        assert await get_current_skill_mastery(cast(AsyncSession, fake), _UID, _SID) is None


class TestRecordProblemAttemptSkillMastery:
    """채점 풀이 → concept→skill 해소 → 스킬별 전파(모델 B·순수 커널 재사용)."""

    async def test_correct_propagates_to_all_resolved_skills(self) -> None:
        """정답: 평가 개념 전체 → 해소된 스킬 전부 지지(합동 증거·첫 관측 상승)."""
        c1, c2 = uuid.uuid4(), uuid.uuid4()
        s1, s2 = "skill.a", "skill.b"
        ts = datetime(2026, 3, 1, tzinfo=UTC)
        # execute: #1 개념[c1,c2] → #2 스킬[s1,s2] → #3 s1 prior[] → #4 s2 prior[]
        fake = _QueueSession([_QResult([c1, c2]), _QResult([s1, s2]), _QResult([]), _QResult([])])
        records = await record_problem_attempt_skill_mastery(
            cast(AsyncSession, fake), _UID, uuid.uuid4(), True, model=_M, measured_at=ts
        )
        assert [r.skill_id for r in records] == [s1, s2]
        assert all(float(r.mastery) == 0.69 for r in records)  # 정답·첫 관측
        assert all(r.measured_at == ts for r in records)  # 한 풀이=같은 시각
        assert len(fake.added) == 2
        assert fake.commits == 1  # 다스킬 = 단일 트랜잭션(원자성)

    async def test_incorrect_blames_primary_skills_only(self) -> None:
        """오답: PRIMARY 개념 스킬만 감점(PRIMARY 존재 시 TESTED 폴백 미발생·거짓 약점 0)."""
        c_p = uuid.uuid4()
        s1 = "skill.a"
        # execute: #1 PRIMARY[c_p] → #2 스킬[s1] → #3 s1 prior[]
        fake = _QueueSession([_QResult([c_p]), _QResult([s1]), _QResult([])])
        records = await record_problem_attempt_skill_mastery(
            cast(AsyncSession, fake), _UID, uuid.uuid4(), False, model=_M
        )
        assert [r.skill_id for r in records] == [s1]
        assert records[0].mastery == 0.15  # 오답·첫 관측
        assert fake.commits == 1

    async def test_incorrect_falls_back_to_tested_when_no_primary(self) -> None:
        """오답·PRIMARY 미매핑 퇴화 문항은 TESTED 개념 스킬로 폴백(신호 손실 방지)."""
        c_t = uuid.uuid4()
        s1 = "skill.a"
        # execute: #1 PRIMARY[] → #2 TESTED[c_t] → #3 스킬[s1] → #4 s1 prior[]
        fake = _QueueSession([_QResult([]), _QResult([c_t]), _QResult([s1]), _QResult([])])
        records = await record_problem_attempt_skill_mastery(
            cast(AsyncSession, fake), _UID, uuid.uuid4(), False, model=_M
        )
        assert [r.skill_id for r in records] == [s1]
        assert fake.commits == 1

    async def test_no_mapped_concepts_returns_empty(self) -> None:
        """문제↔개념 매핑이 없으면 스킬 해소·갱신 0(_assessed_skill_ids 조기반환·쿼리 0)."""
        # execute: #1 개념[] — 이후 _assessed_skill_ids는 빈 입력이라 쿼리 없음.
        fake = _QueueSession([_QResult([])])
        records = await record_problem_attempt_skill_mastery(
            cast(AsyncSession, fake), _UID, uuid.uuid4(), True
        )
        assert records == []
        assert fake.added == []
        assert fake.commits == 0

    async def test_concepts_but_no_estimable_skills_returns_empty(self) -> None:
        """개념은 있으나 mastery-estimable 스킬 해소가 0이면 갱신 0(빈 리스트·커밋 0)."""
        c1 = uuid.uuid4()
        # execute: #1 개념[c1] → #2 스킬[] (해소 0)
        fake = _QueueSession([_QResult([c1]), _QResult([])])
        records = await record_problem_attempt_skill_mastery(
            cast(AsyncSession, fake), _UID, uuid.uuid4(), True
        )
        assert records == []
        assert fake.added == []
        assert fake.commits == 0

    async def test_reads_prior_and_updates(self) -> None:
        """스킬 직전 측정(0.69·표본1)을 prior로 → 0.92·표본 2(순수 커널 재사용·개념 축과 동일)."""
        c1 = uuid.uuid4()
        s1 = "skill.a"
        fake = _QueueSession([_QResult([c1]), _QResult([s1]), _QResult([_prior_row(0.69, 1)])])
        records = await record_problem_attempt_skill_mastery(
            cast(AsyncSession, fake), _UID, uuid.uuid4(), True, model=_M
        )
        assert records[0].mastery == 0.92
        assert records[0].sample_size == 2
