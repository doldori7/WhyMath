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
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import NamedTuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from whymath_backend.db.models.assessment import ConceptMasteryHistory
from whymath_backend.db.models.concept import ProblemConcept
from whymath_backend.l2.bkt import BktModel
from whymath_backend.schema.enums import ConceptRole

# slice 3: 채점된 풀이 정/오답이 *직접 평가*하는 개념 역할 — PRIMARY(주된 개념)·TESTED(평가
# 대상). SUPPORTING(계산 부수)·IMPLICIT(무의식 사용)는 정/오답이 그 개념 숙달의 직접 증거가
# 아니라 제외(오답이 보조 개념 탓일 수도·정답이 보조 개념 숙달을 확증하지 않음). 후속: role/
# relevance 가중 부분 크레딧.
_ASSESSED_ROLES: tuple[ConceptRole, ...] = (ConceptRole.PRIMARY, ConceptRole.TESTED)

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
    elapsed_days: float = 0.0,
) -> MasteryRecord:
    """직전 측정 + 관측 → 다음 측정(순수·DB 무관).

    `prior_mastery`가 None이면(첫 관측) 모델의 사전 P(L0)에서 시작한다. mastery는 저장
    정밀도(2자리)로 반올림(다음 갱신이 같은 값을 prior로 읽도록). sample_size는 직전+1.

    slice L2-6: `elapsed_days`(직전 측정 이후 경과일)만큼 *관측 갱신 전* prior에 망각 감쇠를
    적용한다(`model.apply_forgetting`). p_forget=0(기본)이면 무영향(하위 호환). 첫 관측은
    elapsed 무관(prior=P(L0)·감쇠 대상 없음).
    """
    prior = model.initial_mastery if prior_mastery is None else prior_mastery
    prior = model.apply_forgetting(prior, elapsed_days)
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


async def get_current_mastery(
    session: AsyncSession, user_id: uuid.UUID, concept_id: uuid.UUID
) -> float | None:
    """(user, concept)의 현재 숙달도 — 최신 측정 1건의 mastery 값(읽기 전용).

    L4 coach가 서버에서 학생의 특정 개념 숙달도를 *클라이언트 전송값 대신* 조회할 때 쓴다
    (slice 70·L2↔L4 서버 진실원천). 측정 이력이 없거나 mastery가 NULL이면 None(미학습 폴백).
    """
    row = await _latest_mastery(session, user_id, concept_id)
    return float(row.mastery) if row is not None and row.mastery is not None else None


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
    now = measured_at or datetime.now(UTC)
    prior_row = await _latest_mastery(session, user_id, concept_id)
    prior_mastery = (
        float(prior_row.mastery)
        if prior_row is not None and prior_row.mastery is not None
        else None
    )
    prior_sample = prior_row.sample_size if prior_row is not None else None
    # slice L2-6: 직전 측정 이후 경과일(망각 감쇠 입력). 직전 없으면 0.
    elapsed_days = (
        (now - prior_row.measured_at).total_seconds() / 86400.0 if prior_row is not None else 0.0
    )
    rec = compute_mastery_record(prior_mastery, prior_sample, correct, model, elapsed_days)
    row = ConceptMasteryHistory(
        user_id=user_id,
        concept_id=concept_id,
        measured_at=now,
        mastery=rec.mastery,
        confidence=rec.confidence,
        sample_size=rec.sample_size,
    )
    session.add(row)
    await session.commit()
    return row


async def _assessed_concept_ids(
    session: AsyncSession,
    problem_id: uuid.UUID,
    assessed_roles: Sequence[ConceptRole],
) -> list[uuid.UUID]:
    """문제가 *평가*하는 distinct 개념 id — `problem_concept` 중 role∈assessed_roles."""
    stmt = (
        select(ProblemConcept.concept_id)
        .where(
            ProblemConcept.problem_id == problem_id,
            ProblemConcept.role.in_(list(assessed_roles)),
        )
        .distinct()
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_primary_concept_id(session: AsyncSession, problem_id: uuid.UUID) -> uuid.UUID | None:
    """문항의 *대표* 개념 1개 — coach가 "어느 개념 숙달도를 볼지" 정할 때(slice 70).

    PRIMARY(주된 개념) 우선·없으면 TESTED 폴백·둘 다 없으면 None(문항-개념 미매핑). PRIMARY가
    복수면 첫째(문항당 PRIMARY 1개 보장이 설계 전제·후속에서 가중). 기존 `_assessed_concept_ids`
    재사용(role 필터·distinct).
    """
    primary = await _assessed_concept_ids(session, problem_id, [ConceptRole.PRIMARY])
    if primary:
        return primary[0]
    tested = await _assessed_concept_ids(session, problem_id, [ConceptRole.TESTED])
    return tested[0] if tested else None


async def record_problem_attempt_mastery(
    session: AsyncSession,
    user_id: uuid.UUID,
    problem_id: uuid.UUID,
    correct: bool,
    *,
    model: BktModel | None = None,
    measured_at: datetime | None = None,
    assessed_roles: Sequence[ConceptRole] = _ASSESSED_ROLES,
) -> list[ConceptMasteryHistory]:
    """채점된 풀이(정/오답)를 문제가 평가하는 *모든 개념*의 숙달 갱신으로 전파 — 풀이 채점
    파이프라인의 자동 결선 진입점.

    `problem_concept`에서 role이 `assessed_roles`(기본 PRIMARY·TESTED)인 distinct 개념마다
    `record_attempt_mastery`를 호출해 학습 곡선에 측정 1건씩 적재한다. 매핑이 없으면 빈 리스트
    (숙달 갱신 0). 한 풀이의 모든 개념은 *같은 `measured_at`*(생략 시 현재)을 공유한다.

    v1: 평가 개념 각각에 *동일* 정/오답 신호를 적용(role/relevance 가중 부분 크레딧은 후속).
    개념별로 독립 commit(record_attempt_mastery 계약) — 다개념 원자성은 후속.
    """
    model = model or BktModel()
    timestamp = measured_at or datetime.now(UTC)
    concept_ids = await _assessed_concept_ids(session, problem_id, assessed_roles)
    records: list[ConceptMasteryHistory] = []
    for concept_id in concept_ids:
        record = await record_attempt_mastery(
            session, user_id, concept_id, correct, model=model, measured_at=timestamp
        )
        records.append(record)
    return records


__all__ = [
    "MasteryRecord",
    "compute_mastery_record",
    "get_current_mastery",
    "get_primary_concept_id",
    "record_attempt_mastery",
    "record_problem_attempt_mastery",
]
