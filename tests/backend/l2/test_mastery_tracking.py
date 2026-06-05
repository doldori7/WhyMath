"""L2 BKT↔ConceptMasteryHistory 결선 — *순수* 측정 계산 단위테스트 (hermetic).

`compute_mastery_record`(prior + 관측 → 다음 측정)를 전수 검증한다. DB 래퍼
`record_attempt_mastery`(SELECT 정렬·INSERT)는 통합테스트(`*_integration.py`)가 실 PG로 검증.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy.ext.asyncio import AsyncSession

from whymath_backend.db.models.assessment import ConceptMasteryHistory
from whymath_backend.l2 import BktModel, BktParameters, compute_mastery_record, update_mastery
from whymath_backend.l2.mastery_tracking import record_attempt_mastery

_M = BktModel()  # 기본 파라미터(p_init=0.3 등)
_UID = uuid.uuid4()
_CID = uuid.uuid4()


class _FakeResult:
    def __init__(self, row: Any) -> None:
        self._row = row

    def scalars(self) -> _FakeResult:
        return self

    def first(self) -> Any:
        return self._row


class _FakeSession:
    """`record_attempt_mastery`의 SELECT(직전 측정)·add·commit만 시뮬(stmt 무시).

    정렬 정확성(measured_at DESC)은 통합테스트가 실 PG로 검증 — 여기선 래퍼 로직(prior→계산
    →INSERT)만 본다. `prior` 인자가 직전 측정 행(또는 None).
    """

    def __init__(self, prior: ConceptMasteryHistory | None = None) -> None:
        self._prior = prior
        self.added: list[Any] = []
        self.commits = 0

    async def execute(self, _stmt: Any) -> _FakeResult:
        return _FakeResult(self._prior)

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    async def commit(self) -> None:
        self.commits += 1


class TestComputeMasteryRecord:
    def test_first_observation_uses_p_init(self) -> None:
        """prior None(첫 관측)이면 사전 P(L0)에서 갱신·표본 1."""
        rec = compute_mastery_record(None, None, True, _M)
        assert rec.mastery == round(update_mastery(_M.initial_mastery, True, _M.params), 2)
        assert rec.mastery == 0.69
        assert rec.sample_size == 1

    def test_first_observation_incorrect(self) -> None:
        rec = compute_mastery_record(None, None, False, _M)
        assert rec.mastery == 0.15
        assert rec.sample_size == 1

    def test_uses_prior_not_p_init(self) -> None:
        """prior가 주어지면 그 값에서 갱신(P(L0) 무시)."""
        rec = compute_mastery_record(0.69, 1, True, _M)
        assert rec.mastery == round(update_mastery(0.69, True, _M.params), 2)
        assert rec.mastery == 0.92

    def test_sample_size_increments(self) -> None:
        assert compute_mastery_record(0.5, 4, True, _M).sample_size == 5
        assert compute_mastery_record(0.5, None, True, _M).sample_size == 1

    def test_confidence_monotonic_in_sample_size(self) -> None:
        c1 = compute_mastery_record(0.5, 0, True, _M).confidence
        c10 = compute_mastery_record(0.5, 9, True, _M).confidence
        assert c10 > c1
        # n=5 → 5/(5+5)=0.5
        assert compute_mastery_record(0.5, 4, True, _M).confidence == 0.5

    def test_mastery_rounded_to_two_decimals(self) -> None:
        """Numeric(3,2) 정합 — 저장 정밀도(2자리)로 반올림."""
        rec = compute_mastery_record(0.3, 0, True, _M)
        assert rec.mastery == round(rec.mastery, 2)
        assert 0.0 <= rec.mastery <= 1.0

    def test_custom_model_params(self) -> None:
        params = BktParameters(p_init=0.6, p_slip=0.05, p_guess=0.1, p_transit=0.2)
        model = BktModel(params)
        rec = compute_mastery_record(None, None, True, model)
        assert rec.mastery == round(update_mastery(0.6, True, params), 2)

    def test_repeated_correct_increases_mastery(self) -> None:
        """연속 정답을 prior로 이어주면 숙달도가 단조 증가(학습 곡선)."""
        r1 = compute_mastery_record(None, None, True, _M)
        r2 = compute_mastery_record(r1.mastery, r1.sample_size, True, _M)
        r3 = compute_mastery_record(r2.mastery, r2.sample_size, True, _M)
        assert r1.mastery < r2.mastery < r3.mastery
        assert r3.sample_size == 3


def _prior_row(mastery: float | None, sample_size: int | None) -> ConceptMasteryHistory:
    return ConceptMasteryHistory(
        user_id=_UID,
        concept_id=_CID,
        measured_at=datetime(2026, 1, 1, tzinfo=UTC),
        mastery=mastery,
        confidence=None,
        sample_size=sample_size,
    )


class TestRecordAttemptMastery:
    """DB 래퍼 — 직전 측정 읽기→계산→INSERT(fake session·stmt 무시)."""

    async def test_first_observation_no_prior(self) -> None:
        """직전 측정 없으면 P(L0)에서 갱신·표본 1·새 행 add·commit."""
        fake = _FakeSession(prior=None)
        row = await record_attempt_mastery(cast(AsyncSession, fake), _UID, _CID, True, model=_M)
        assert row.mastery == 0.69
        assert row.sample_size == 1
        assert row.user_id == _UID and row.concept_id == _CID
        assert fake.added == [row]
        assert fake.commits == 1

    async def test_reads_prior_and_updates(self) -> None:
        """직전 측정(0.69·표본1)을 prior로 → 0.92·표본 2."""
        fake = _FakeSession(prior=_prior_row(0.69, 1))
        row = await record_attempt_mastery(cast(AsyncSession, fake), _UID, _CID, True, model=_M)
        assert row.mastery == 0.92
        assert row.sample_size == 2

    async def test_prior_with_null_mastery_falls_back_to_p_init(self) -> None:
        """직전 행은 있으나 mastery=NULL이면 P(L0)에서 시작."""
        fake = _FakeSession(prior=_prior_row(None, None))
        row = await record_attempt_mastery(cast(AsyncSession, fake), _UID, _CID, True, model=_M)
        assert row.mastery == 0.69

    async def test_explicit_measured_at(self) -> None:
        ts = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)
        fake = _FakeSession(prior=None)
        row = await record_attempt_mastery(
            cast(AsyncSession, fake), _UID, _CID, False, measured_at=ts
        )
        assert row.measured_at == ts
        assert row.mastery == 0.15  # 기본 모델·오답

    async def test_default_model_when_omitted(self) -> None:
        """model 생략 시 기본 BktModel 사용."""
        fake = _FakeSession(prior=None)
        row = await record_attempt_mastery(cast(AsyncSession, fake), _UID, _CID, True)
        assert row.mastery == 0.69
