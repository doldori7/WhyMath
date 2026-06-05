"""L2 — BKT 추정기 ↔ `ConceptMasteryHistory` 시계열 영속 결선.

`l2/bkt`는 *순수 추정*(prior + 관측 → 새 P(L))만 한다. 본 모듈은 그 추정을 영속 학습 곡선에
잇는다: 풀이 관측이 들어오면 ① (user, concept)의 *직전* 숙달 측정을 읽어 prior로 삼고
② BKT로 갱신해 ③ 새 `concept_mastery_history` 행을 append-only로 적재한다(특성 #16 학습 곡선).

설계 분리(코드베이스 패턴):
  - **`compute_mastery_record`** — *순수*(DB 무관) 다음-측정 계산. prior 측정값·관측·모델에서
    (mastery, confidence, sample_size)을 낸다. hermetic 전수 검증.
  - **`record_attempt_mastery`** — 얇은 async DB 래퍼(직전 측정 SELECT → 순수 계산 → INSERT).
    실 PG 통합테스트가 SELECT 정렬·INSERT를 검증.

정밀도: `concept_mastery_history.mastery`는 `Numeric(3,2)`(소수 2자리)다. prior를 다시 읽어
갱신하므로 *저장 정밀도에 맞춰* 2자리로 반올림해 hermetic↔실 PG 동작을 일치시킨다(컬럼 폭
확대·고정밀 상태 분리는 후속). confidence는 v1 휴리스틱(표본 크기 기반·아래 상수).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import NamedTuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from whymath_backend.db.models.assessment import ConceptMasteryHistory
from whymath_backend.l2.bkt import BktModel

# confidence v1 휴리스틱: 표본 n개에서 `n/(n+HALFLIFE)` — 관측이 쌓일수록 측정 신뢰↑.
# n=5에서 0.5·n=10에서 ≈0.67. BKT는 신뢰도를 직접 주지 않으므로 표본 크기로 근사(후속:
# 사후 분산 기반·베타 분포 신뢰구간).
_CONFIDENCE_HALFLIFE = 5
_MASTERY_DECIMALS = 2  # Numeric(3,2) 정합


class MasteryRecord(NamedTuple):
    """다음 숙달 측정의 영속 필드 — `ConceptMasteryHistory` 적재 입력."""

    mastery: float
    confidence: float
    sample_size: int


def compute_mastery_record(
    prior_mastery: float | None,
    prior_sample_size: int | None,
    correct: bool,
    model: BktModel,
) -> MasteryRecord:
    """직전 측정 + 관측 → 다음 측정(순수·DB 무관).

    `prior_mastery`가 None이면(첫 관측) 모델의 사전 P(L0)에서 시작한다. mastery는 저장
    정밀도(2자리)로 반올림(다음 갱신이 같은 값을 prior로 읽도록). sample_size는 직전+1.
    """
    prior = model.initial_mastery if prior_mastery is None else prior_mastery
    mastery = round(model.update(prior, correct), _MASTERY_DECIMALS)
    sample_size = (prior_sample_size or 0) + 1
    confidence = round(sample_size / (sample_size + _CONFIDENCE_HALFLIFE), _MASTERY_DECIMALS)
    return MasteryRecord(mastery=mastery, confidence=confidence, sample_size=sample_size)


async def _latest_mastery(
    session: AsyncSession, user_id: uuid.UUID, concept_id: uuid.UUID
) -> ConceptMasteryHistory | None:
    """(user, concept)의 가장 최근 측정 1건 — 없으면 None(첫 관측)."""
    stmt = (
        select(ConceptMasteryHistory)
        .where(
            ConceptMasteryHistory.user_id == user_id,
            ConceptMasteryHistory.concept_id == concept_id,
        )
        .order_by(ConceptMasteryHistory.measured_at.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    return result.scalars().first()


async def record_attempt_mastery(
    session: AsyncSession,
    user_id: uuid.UUID,
    concept_id: uuid.UUID,
    correct: bool,
    *,
    model: BktModel | None = None,
    measured_at: datetime | None = None,
) -> ConceptMasteryHistory:
    """풀이 관측 1건을 (user, concept) 학습 곡선에 반영 — 새 측정 행 적재·반환.

    직전 측정을 prior로 읽어 BKT 갱신 후 새 `concept_mastery_history` 행을 INSERT(append-only).
    `measured_at` 생략 시 현재. 같은 트랜잭션으로 commit.
    """
    model = model or BktModel()
    prior_row = await _latest_mastery(session, user_id, concept_id)
    prior_mastery = (
        float(prior_row.mastery)
        if prior_row is not None and prior_row.mastery is not None
        else None
    )
    prior_sample = prior_row.sample_size if prior_row is not None else None
    rec = compute_mastery_record(prior_mastery, prior_sample, correct, model)
    row = ConceptMasteryHistory(
        user_id=user_id,
        concept_id=concept_id,
        measured_at=measured_at or datetime.now(UTC),
        mastery=rec.mastery,
        confidence=rec.confidence,
        sample_size=rec.sample_size,
    )
    session.add(row)
    await session.commit()
    return row


__all__ = [
    "MasteryRecord",
    "compute_mastery_record",
    "record_attempt_mastery",
]
