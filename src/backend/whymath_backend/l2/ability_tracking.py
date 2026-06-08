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

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from whymath_backend.db.models.assessment import AbilitySnapshot


async def get_current_theta(session: AsyncSession, user_id: uuid.UUID) -> float | None:
    """학생의 현재 *전과목* IRT 능력 θ — 최신 global `AbilitySnapshot` 1건의 theta(읽기 전용).

    `get_current_mastery`(BKT 개념 숙달)와 대칭이되 θ는 *전과목*이라 concept_id가 필요 없다:
    `concept_id IS NULL`(전 과목 단일 θ) 최신 스냅샷만 본다(개념별 θ 교차검증은 후속). L4
    coach가 서버에서 학생 능력을 *클라 전송값 대신* 조회해 BKT↔θ 교차검증 코칭(slice 73)에
    쓴다. 측정 이력이 없으면 None(graceful — 교차검증 불가 → diagnose 폴백·비노출).

    정렬(measured_at DESC)·`concept_id IS NULL` 필터의 정확성은 통합테스트가 실 PG로 검증한다
    (`test_ability_snapshot_integration`) — 여기 hermetic 경로는 스칼라→float|None 래퍼만 본다
    (`mastery_tracking`의 단위/통합 분리 패턴).
    """
    stmt = (
        select(AbilitySnapshot.theta)
        .where(
            AbilitySnapshot.user_id == user_id,
            AbilitySnapshot.concept_id.is_(None),
        )
        .order_by(AbilitySnapshot.measured_at.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    theta = result.scalars().first()
    return float(theta) if theta is not None else None


__all__ = ["get_current_theta"]
