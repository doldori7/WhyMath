"""학습 활동 PII 시계열 보존 파기 — `evidence_links` 외 *타 PII 테이블* 무기한 보존 차단.

`evidence_store.purge_expired`(증거 그래프·`retention_until` 기반)는 evidence_links만 다룬다.
그러나 *학습 활동 데이터*(대화·세션·시도·평가·시계열 지표)도 무기한 보존되면 GDPR 데이터
최소화 위반이다(미성년 학습 로그). 이 모듈은 그 테이블들을 *타임스탬프 기준*으로 파기한다 —
`timestamp < (as_of − pii_retention_years)`인 행을 지운다(retention_until 컬럼이 없으므로 적재
시각으로 만료를 계산).

설계(삭제권 `privacy.erasure` 패턴 답습):
  - `AsyncSession`을 *주입*받고 **commit은 호출자**(어느 단계 실패도 전부 롤백 — 부분 파기 0).
  - **순수 ORM/쿼리빌더만**(`delete(Model).where(ts < cutoff)`·원시 SQL 0).
  - 플랜은 삭제권 `_ERASURE_PLAN`의 *학습 데이터 시계열 부분집합*을 **child→parent** 순서로
    (FK 안전·session→attempt CASCADE 역순 방지). **계정/인증/동의/가설 테이블은 제외** — 보존
    의미가 다르다(토큰 자가만료·동의는 법적 증빙 보존·계정 상태는 현재값). evidence_links는
    `purge_expired`(retention_until)가 별도 처리(중복 0).

정직 스코프: NULL 타임스탬프(미시작 세션 등)는 `ts < cutoff`가 NULL이라 *파기 대상 아님*
(보수적). 테이블별 차등 보존기한·졸업일 기반 정밀 보존은 후속(현 균일 `pii_retention_years`).
"""

from __future__ import annotations

from datetime import date
from typing import Any, cast

from sqlalchemy import CursorResult, delete
from sqlalchemy.ext.asyncio import AsyncSession

from whymath_backend.config import get_settings
from whymath_backend.db.base import Base
from whymath_backend.db.models.activity import AttemptEvent, LearningSession, ProblemAttempt
from whymath_backend.db.models.assessment import (
    AbilitySnapshot,
    Assessment,
    ConceptMasteryHistory,
)
from whymath_backend.db.models.dialogue import Dialogue
from whymath_backend.db.models.timeseries import DailyLearningMetrics, UserBehaviorMetrics

__all__ = ["purge_expired_records", "retention_cutoff"]

# 보존 파기 플랜 — (모델, 타임스탬프 컬럼명). child→parent 순서(FK 안전·`_ERASURE_PLAN` 미러).
# dialogue→dialogue_turn·learning_session→problem_attempt는 DB CASCADE라 부모 파기가 자식
# 동반 제거(자식 타임스탬프 무관). attempt_event·시계열 지표는 느슨참조(FK 차단 없음).
_RETENTION_PLAN: tuple[tuple[type[Base], str], ...] = (
    (Dialogue, "started_at"),  # → dialogue_turn DB CASCADE
    (ProblemAttempt, "started_at"),  # learning_session보다 먼저(session→attempt CASCADE 역순 방지)
    (LearningSession, "started_at"),
    (AttemptEvent, "event_at"),  # 느슨참조·hypertable(고아 방지)
    (Assessment, "started_at"),
    (ConceptMasteryHistory, "measured_at"),  # BKT 숙달 이력·느슨참조
    (AbilitySnapshot, "measured_at"),  # IRT θ 이력·느슨참조
    (DailyLearningMetrics, "metric_date"),  # 일 집계·DATE 컬럼·느슨참조
    (UserBehaviorMetrics, "measured_at"),  # 행동 지표·느슨참조
)


def retention_cutoff(as_of: date, *, years: int) -> date:
    """보존 만료 기준일 = `as_of − years`년(순수·윤년 안전·2/29→2/28 클램프).

    이 날짜 *이전*(`< cutoff`) 타임스탬프 행이 보존기한 경과분이다. `default_retention_until`
    (적재일+years)의 역방향 — 적재일 + years ≤ as_of 인 행을 가린다.
    """
    try:
        return as_of.replace(year=as_of.year - years)
    except ValueError:  # as_of가 2/29인데 −years년이 비윤년 → 2/28로 클램프.
        return as_of.replace(year=as_of.year - years, month=2, day=28)


async def purge_expired_records(
    session: AsyncSession,
    *,
    as_of: date,
    years: int | None = None,
) -> dict[str, int]:
    """학습 활동 PII 시계열에서 보존기한 경과분을 파기 — 테이블별 삭제 행수 반환(commit은 호출자).

    `years` 미지정 시 `Settings.pii_retention_years`(기본 3). `cutoff = as_of − years`년 이전
    타임스탬프(`_RETENTION_PLAN`의 각 컬럼) 행을 child→parent 순서로 삭제한다(FK 안전·CASCADE
    동반). NULL 타임스탬프는 비교가 NULL이라 미파기(보수적). 순수 ORM·원시 SQL 0.
    """
    resolved_years = years if years is not None else get_settings().pii_retention_years
    cutoff = retention_cutoff(as_of, years=resolved_years)
    counts: dict[str, int] = {}
    for model, column in _RETENTION_PLAN:
        result = await session.execute(delete(model).where(getattr(model, column) < cutoff))
        counts[model.__tablename__] = cast("CursorResult[Any]", result).rowcount or 0
    return counts
