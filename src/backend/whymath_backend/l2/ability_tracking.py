"""L2 — IRT 능력 θ 시계열(`AbilitySnapshot`)의 *현재값* 읽기.

`mastery_tracking`(BKT 개념 숙달 이력)과 *상보·대칭*: 이쪽은 IRT 능력 θ(logit)의 최신값을
읽는다. L4 coach가 서버에서 학생 능력을 *클라이언트 전송값 대신* 조회해 BKT↔θ 교차검증
코칭(`l4.metacognitive_trigger.recommend_coaching`·slice 73)에 쓴다. `ability_snapshot`
*적재*(θ 추정·write)는 IRT 추정 파이프라인(slice 31·후속) 책임 — 본 모듈은 *읽기 전용*이다
(`get_current_mastery` 대칭).

설계 분리(코드베이스 패턴): `bkt`/`irt` 추정기를 각각 `mastery_tracking`/`ability_tracking`이
영속에 잇는다(BKT/IRT 모델 혼동 방지 — `l2.__init__` "이름 충돌 메모"와 동일 취지).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from whymath_backend.db.models.assessment import AbilitySnapshot


async def get_current_theta(
    session: AsyncSession, user_id: uuid.UUID, concept_id: uuid.UUID | None = None
) -> float | None:
    """학생의 현재 IRT 능력 θ — 최신 `AbilitySnapshot` 1건의 theta(읽기 전용).

    `concept_id`로 *범위*를 고른다: None(기본)이면 *전과목*(`concept_id IS NULL`·전 과목 단일
    θ·slice 73)·특정 개념 UUID면 *그 개념*(`concept_id == X`·slice 74 개념별 교차검증)의 최신
    θ. L4 coach가 서버에서 학생 능력을 *클라 전송값 대신* 조회해 BKT↔θ 교차검증 코칭
    (`recommend_coaching`)에 쓴다 — 개념별 θ면 같은 개념 BKT와 *동일 개념끼리* 비교(정밀).
    측정 이력이 없으면 None(graceful — 교차검증 불가 → diagnose 폴백·비노출).

    정렬(measured_at DESC)·concept_id 필터(`IS NULL` vs `== X`)의 정확성은 통합테스트가 실
    PG로 검증한다(`test_ability_snapshot_integration`) — 여기 hermetic 경로는 스칼라→
    float|None 래퍼만 본다(`mastery_tracking`의 단위/통합 분리 패턴).
    """
    concept_filter = (
        AbilitySnapshot.concept_id.is_(None)
        if concept_id is None
        else AbilitySnapshot.concept_id == concept_id
    )
    stmt = (
        select(AbilitySnapshot.theta)
        .where(AbilitySnapshot.user_id == user_id, concept_filter)
        .order_by(AbilitySnapshot.measured_at.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    theta = result.scalars().first()
    return float(theta) if theta is not None else None


@dataclass(frozen=True)
class AbilityReading:
    """최신 θ 스냅샷의 값 + *신뢰도*(SE·응답수) — coach 노이즈 가드(slice 76)용.

    `get_current_theta`(θ 스칼라)와 달리 표준오차·응답수까지 *같은 행*에서 함께 읽어, 응답 1~2개의
    극단 θ(SE 큼/None)를 코칭 교차검증에서 거를 수 있게 한다(`_theta_reading_reliable`).
    """

    theta: float
    standard_error: float | None
    response_count: int


async def get_current_ability(
    session: AsyncSession, user_id: uuid.UUID, concept_id: uuid.UUID | None = None
) -> AbilityReading | None:
    """학생의 현재 θ를 *신뢰도(SE·응답수)와 함께* 읽는다 — 최신 `AbilitySnapshot` 1건(읽기 전용).

    `get_current_theta`와 동일 WHERE/정렬(concept_id None→`IS NULL`·값→`==X`)이되 theta 외
    standard_error·response_count도 *같은 스냅샷 행*에서 함께 select. slice 76 노이즈 가드가
    개념 θ의 신뢰도를 보고 쓸지/전과목 폴백할지 정한다. 측정 이력이 없으면 None.

    필터/정렬 정확성은 통합테스트가 실 PG로 검증(`test_ability_snapshot_integration`) — 여기
    hermetic 경로는 Row→AbilityReading|None 래퍼만 본다(단위/통합 분리 패턴).
    """
    concept_filter = (
        AbilitySnapshot.concept_id.is_(None)
        if concept_id is None
        else AbilitySnapshot.concept_id == concept_id
    )
    stmt = (
        select(
            AbilitySnapshot.theta,
            AbilitySnapshot.standard_error,
            AbilitySnapshot.response_count,
        )
        .where(AbilitySnapshot.user_id == user_id, concept_filter)
        .order_by(AbilitySnapshot.measured_at.desc())
        .limit(1)
    )
    row = (await session.execute(stmt)).first()
    if row is None:
        return None
    theta, standard_error, response_count = row
    return AbilityReading(
        theta=float(theta),
        standard_error=float(standard_error) if standard_error is not None else None,
        response_count=int(response_count),
    )


__all__ = ["AbilityReading", "get_current_ability", "get_current_theta"]
