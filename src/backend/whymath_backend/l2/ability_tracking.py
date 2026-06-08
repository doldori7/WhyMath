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


__all__ = ["get_current_theta"]
