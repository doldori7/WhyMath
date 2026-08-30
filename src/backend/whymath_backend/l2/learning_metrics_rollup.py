"""일별 학습 지표 롤업 (COLLAB-03) — 시계열 3테이블의 *프로덕션 writer*.

`daily_learning_metrics`·`user_behavior_metrics`·`problem_solve_time_distribution` 세 테이블은
파기(`privacy/erasure.py`)·반출(`privacy/export.py`)·보존(`privacy/retention.py`) 배관에 등재돼
있으나 **적재 writer가 0건**이었다(ORM/Pydantic 정의와 테스트에만 인스턴스화 존재 — 2026-08-10
전수 grep 실측). "완비된 배관 + 미적재 공급원"은 `visualization_module_gap_review.md` D1과 같은
실패 유형이고, 이 모듈이 그 공급원이다.

────────────────────────────────────────────────────────────────────────────
집계 원천 (기존 3테이블만 — 새 인프라·새 이벤트 소스 0)
────────────────────────────────────────────────────────────────────────────
  - `learning_session` — 활동 시간(`duration_seconds`, 없으면 `ended_at−started_at` 폴백)·
    집중도(`focus_score`)·학습 목표 개념(`target_concept_id`).
  - `problem_attempt` — 시도 수·정답 수·힌트/풀이보기 의존도·문항별 풀이 소요(초).
  - `attempt_event` — 소크라테스 상호작용 턴(`막힘`·`힌트요청`·`힌트제공`).

────────────────────────────────────────────────────────────────────────────
날짜 귀속 (KST 고정 — DDL `metric_date`가 DATE라 타임존이 정의돼야 한다)
────────────────────────────────────────────────────────────────────────────
원천 타임스탬프는 전부 TIMESTAMPTZ이고 목적지 `metric_date`는 DATE다. "하루"의 경계는 **학습자
생활 시간대(KST·Asia/Seoul)** 로 정의한다 — 한국 중·고생 대상 서비스라 UTC 경계(KST 09:00)로
자르면 오전 학습이 전날로 밀려 통계가 학생 체감과 어긋난다. `tz` 인자로 주입 가능(테스트·후속
다지역). 이 결정은 `consent.py`가 KST를 UTC+9로 취급한 선례와 일관된다.

────────────────────────────────────────────────────────────────────────────
집계 주기·보존기간 (COLLAB-03 acceptance ⑥ — 이 태스크에서 확정)
────────────────────────────────────────────────────────────────────────────
  - **집계 주기 = 1일 1회**(`harness/learning_metrics_rollup_cli.py`를 운영 크론/수동 실행).
    새 스케줄러는 도입하지 않는다(acceptance ② 「새 인프라 금지」) — 기존 CLI 규약만 재사용.
  - **재집계 창 = 기본 2일**(`--days 2`: 어제·오늘). 세션 종료·채점이 자정을 넘겨 도착하는
    지연분을 흡수한다. 멱등 upsert라 재실행이 곧 정합 회복이다.
  - **보존기간 = 기존 `Settings.pii_retention_years`(기본 3년) 그대로 상속** — 새 숫자를 만들지
    않는다. `daily_learning_metrics`(metric_date)·`user_behavior_metrics`(measured_at)는 이미
    `privacy/retention.py::_RETENTION_PLAN`에 등재돼 있고, `problem_solve_time_distribution`은
    이 태스크에서 같은 플랜에 편입했다(비-PII 교차집계지만 *무기한 보존 금지* 원칙은 동일하며,
    적재가 시작된 이상 상한 없는 증가를 방치할 수 없다).
  - **파기·반출 정합**: 계정 삭제 시 `_ERASURE_PLAN`이 두 사용자 축 테이블을 지우고, 본인 반출
    (`export.py`)에 두 테이블이 포함된다. `problem_solve_time_distribution`은 `user_id`가 없는
    *교차 사용자 집계*라 삭제권·반출 대상이 아니다(export.py 모듈 docstring의 기존 결정 유지).

────────────────────────────────────────────────────────────────────────────
날조 금지 — *측정된 것만* 적재한다
────────────────────────────────────────────────────────────────────────────
`user_behavior_metrics`는 `churn_risk`(이탈 위험) 같은 *추론* 지표를 담을 수 있는 open set이나,
이 롤업은 **원천 카운트에서 직접 계산되는 비율·개수만** 생산한다. 예측 모델이 없는 지표를
그럴듯한 이름으로 채우는 것은 환각이다(CLAUDE.md 「모르면 모른다고」). `churn_risk`는 모델이
생기는 시점에 별도 writer가 적재한다.

k-익명 하한: `problem_solve_time_distribution`은 (문항, 페르소나) 교차 집계라 표본이 극소수면
개인 풀이 시간이 사실상 노출된다. `min_solve_time_sample`(기본 5) 미만 표본은 **적재하지 않는다**
(CLAUDE.md 「개인 식별 가능한 분석 결과 외부 노출 금지」의 상류 차단).

────────────────────────────────────────────────────────────────────────────
계층·트랜잭션 규약
────────────────────────────────────────────────────────────────────────────
L2(학습자 모델)이며 L1 영속(`db.models`)·`schema`만 참조한다(역방향 import 0). `AsyncSession`을
*주입*받고 **commit은 호출자**(어느 단계 실패도 전부 롤백 — `privacy/retention.py`·`erasure.py`
규약 답습). 순수 ORM/쿼리빌더만 쓰고 원시 SQL은 0이다.

집계 본체는 **순수 함수**(`aggregate_*`)로 분리해 DB 없이 hermetic 검증이 가능하게 했다. DB
어댑터는 창(window) 내 원천 행을 읽어 순수 함수에 넘기고 결과를 upsert할 뿐이다. 창이 며칠로
제한되므로 Python 집계 비용은 현 규모에서 적정하다(대규모 시 SQL 집계 이관 — 순수 함수 계약은
그대로 유지되므로 교체 지점이 명확하다).
"""

from __future__ import annotations

import logging
import uuid
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from whymath_backend.db.models.activity import AttemptEvent, LearningSession, ProblemAttempt
from whymath_backend.db.models.concept import Concept
from whymath_backend.db.models.timeseries import (
    DailyLearningMetrics as DailyLearningMetricsORM,
)
from whymath_backend.db.models.timeseries import (
    ProblemSolveTimeDistribution as ProblemSolveTimeDistributionORM,
)
from whymath_backend.db.models.timeseries import (
    UserBehaviorMetrics as UserBehaviorMetricsORM,
)
from whymath_backend.db.models.user import UserProfile
from whymath_backend.schema.enums import EventType, Persona
from whymath_backend.schema.timeseries import (
    DailyLearningMetrics as DailyLearningMetricsSchema,
)
from whymath_backend.schema.timeseries import (
    ProblemSolveTimeDistribution as ProblemSolveTimeDistributionSchema,
)
from whymath_backend.schema.timeseries import (
    UserBehaviorMetrics as UserBehaviorMetricsSchema,
)

__all__ = [
    "KST",
    "AttemptFact",
    "EventFact",
    "RollupReport",
    "SessionFact",
    "aggregate_daily_metrics",
    "aggregate_solve_time_distribution",
    "aggregate_user_behavior_metrics",
    "effective_event_moment",
    "metric_date_of",
    "run_daily_rollup",
]

_logger = logging.getLogger("whymath.l2.learning_metrics_rollup")

# 학습자 생활 시간대 — "하루"의 경계(모듈 docstring §날짜 귀속).
KST = ZoneInfo("Asia/Seoul")

# 소크라테스 상호작용으로 세는 이벤트 종류. `api/coach.py`가 실제로 생산하는 3종만 고른다
# (문제읽기·계산 등 휴면 enum 값은 생산자가 0이라 세어도 항상 0 — 세지 않는다).
_SOCRATIC_EVENT_TYPES: frozenset[EventType] = frozenset(
    {EventType.막힘, EventType.힌트요청, EventType.힌트제공}
)

# 풀이 시간 분포의 k-익명 하한(모듈 docstring §날조 금지). 이 표본 미만은 적재하지 않는다.
MIN_SOLVE_TIME_SAMPLE = 5

# `user_behavior_metrics.metric_name`(VARCHAR(50) open set)에 이 롤업이 쓰는 값 —
# 전부 *직접 측정치*다(추론 지표 없음). 소비처가 이름을 신뢰할 수 있도록 상수로 고정한다.
BEHAVIOR_METRIC_ACTIVE_MINUTES = "daily_active_minutes"
BEHAVIOR_METRIC_ACCURACY_RATE = "daily_accuracy_rate"
BEHAVIOR_METRIC_HINT_RELIANCE = "daily_hint_reliance_rate"
BEHAVIOR_METRIC_SOLUTION_VIEW = "daily_solution_view_rate"
BEHAVIOR_METRIC_SESSION_COUNT = "daily_session_count"
# EOS-48 병행 지표(기존 지표 재정의 금지 — daily_active_minutes는 *경과(elapsed)* 기반 의미
# 불변). measured_*는 `learning_session.active_seconds`(실측 신호)가 있는 세션만 집계하고,
# ratio는 그 계측이 *실제 작동한 비율*(측정 세션/전체 세션)을 리포트가 말할 수 있게 한다
# ("작동한 비율" 원칙 — 좌석 존재를 계측 작동으로 위장하지 않는다).
BEHAVIOR_METRIC_MEASURED_ACTIVE_MINUTES = "daily_measured_active_minutes"
BEHAVIOR_METRIC_ACTIVE_MEASURED_RATIO = "daily_active_measured_ratio"

# upsert 배치 크기 — 한 INSERT에 묶는 최대 행 수(파라미터 한도·메모리 보호).
_UPSERT_CHUNK = 500


# ──────────────────────────────────────────────────────────────────────────
# 원천 사실(fact) — 순수 집계 함수의 입력. DB 행에서 필요한 컬럼만 추린 값 객체다.
# ──────────────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class SessionFact:
    """`learning_session` 1행에서 롤업에 쓰는 부분."""

    user_id: uuid.UUID
    started_at: datetime
    ended_at: datetime | None = None
    duration_seconds: int | None = None
    focus_score: float | None = None
    target_concept_id: uuid.UUID | None = None
    # EOS-48: 실측 활동/공백 시간(초) — None=미측정(0 날조 금지·경과와 별개 축). 끝에 기본값
    # 부가(additive) — 기존 생성자·소비자 무영향.
    active_seconds: int | None = None
    idle_seconds: int | None = None

    def effective_seconds(self) -> int | None:
        """활동 시간(초) — `duration_seconds` 우선, 없으면 `ended_at−started_at` 폴백.

        둘 다 없으면(미종료 세션) None — 활동 시간 미상이므로 0으로 날조하지 않는다.
        음수(시계 역행·데이터 오류)는 0으로 클램프한다.
        """
        if self.duration_seconds is not None:
            return max(0, self.duration_seconds)
        if self.ended_at is not None:
            return max(0, int((self.ended_at - self.started_at).total_seconds()))
        return None


@dataclass(frozen=True)
class AttemptFact:
    """`problem_attempt` 1행(+ 학생 페르소나 조인)에서 롤업에 쓰는 부분."""

    user_id: uuid.UUID
    started_at: datetime
    problem_id: uuid.UUID | None = None
    persona: Persona | None = None
    duration_seconds: int | None = None
    is_correct: bool | None = None
    used_hint: bool | None = None
    used_solution_view: bool | None = None


@dataclass(frozen=True)
class EventFact:
    """`attempt_event` 1행에서 롤업에 쓰는 부분."""

    user_id: uuid.UUID
    event_at: datetime
    event_type: EventType | None = None


def effective_event_moment(event_time: datetime | None, ingested_at: datetime) -> datetime:
    """지표 귀속에 쓸 이벤트 시각 — event_time(발생)/ingested_at(수신) 분리 계약(EOS-48 정본).

    오프라인 태블릿 sync 시나리오(32_learning_history §7): 어제 발생한 이벤트가 오늘 수신되면
    귀속은 *발생일*이어야 한다(수신 시각을 사건 시각으로 착각 금지). 단 클라 시계는 신뢰
    불가라 왜곡을 가드한다:

      1. `event_time is None` → `ingested_at`(기존 동작 — 미신고 이벤트는 수신 시각 귀속.
         attempt_event는 event_at이 실측상 수신 시각이므로 그대로 넘긴다).
      2. `event_time > ingested_at` → **시계 왜곡**(발생이 수신보다 미래일 수 없다) →
         `ingested_at`(서버 시각 폴백 — 미래 신고를 그대로 귀속하면 지표가 미래로 샌다).
      3. 그 외(지연 도착 포함·event_time ≤ ingested_at) → `event_time`(발생 기준 귀속).

    순수 함수(DB 무관) — 소비 배선(롤업 `_fetch_events`가 event_time 컬럼을 읽어 이 함수를
    경유하는 것)은 범위 밖 후속이다(기존 지표 의미 불변 원칙 — 배선 시점에 별도 태스크로
    귀속 변화량을 실측한 뒤 전환한다). 이 함수·테스트가 그 전환의 *계약 동결*이다.
    """
    if event_time is None:
        return ingested_at
    if event_time > ingested_at:
        return ingested_at
    return event_time


def metric_date_of(moment: datetime, *, tz: ZoneInfo = KST) -> date:
    """TIMESTAMPTZ 시각 → 집계 대상 날짜(기본 KST 기준 달력일).

    naive datetime은 UTC로 간주한다(DB에서 온 행은 항상 aware지만, 순수 함수를 직접 부르는
    테스트·호출자가 naive를 넘길 수 있어 조용한 오귀속 대신 명시 규칙을 둔다).
    """
    aware = moment if moment.tzinfo is not None else moment.replace(tzinfo=UTC)
    return aware.astimezone(tz).date()


def day_bounds_utc(
    start_date: date, end_date: date, *, tz: ZoneInfo = KST
) -> tuple[datetime, datetime]:
    """`[start_date, end_date]`(tz 달력일, 양끝 포함) → UTC 반열린 구간 `[시작, 끝)`.

    원천 테이블의 TIMESTAMPTZ 필터에 그대로 쓴다. 끝은 `end_date+1일`의 자정이라 반열린이다.
    """
    if end_date < start_date:
        raise ValueError(f"end_date({end_date})가 start_date({start_date})보다 이르다")
    start = datetime.combine(start_date, time.min, tzinfo=tz).astimezone(UTC)
    end = datetime.combine(end_date + timedelta(days=1), time.min, tzinfo=tz).astimezone(UTC)
    return start, end


def _mean_or_none(values: Sequence[float]) -> float | None:
    """평균 — 표본 0이면 None(0.0으로 날조하지 않는다)."""
    return sum(values) / len(values) if values else None


def percentile(values: Sequence[int], q: float) -> int:
    """정렬되지 않은 표본의 백분위수(선형 보간·numpy 기본 'linear'과 동형) → 정수 초.

    `q`는 0.0~1.0. 표본이 1개면 그 값 자체. 목적지 컬럼이 INTEGER(초)라 반올림한다.
    """
    if not values:
        raise ValueError("표본이 비었다 — 호출자가 사전 차단해야 한다")
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    pos = q * (len(ordered) - 1)
    low = int(pos)
    high = min(low + 1, len(ordered) - 1)
    frac = pos - low
    return int(round(ordered[low] + (ordered[high] - ordered[low]) * frac))


# ──────────────────────────────────────────────────────────────────────────
# 순수 집계 ① daily_learning_metrics
# ──────────────────────────────────────────────────────────────────────────
def aggregate_daily_metrics(
    sessions: Iterable[SessionFact],
    attempts: Iterable[AttemptFact],
    events: Iterable[EventFact],
    *,
    tz: ZoneInfo = KST,
    concept_codes: dict[uuid.UUID, str] | None = None,
) -> list[DailyLearningMetricsSchema]:
    """원천 사실 → `(user_id, metric_date)`별 일일 집계(순수·결정론·DB 무관).

    컬럼별 산출 규칙:
      - `minutes_active`: 그날 시작된 세션들의 활동 시간 합(초)을 분으로 내림. 활동 시간이
        미상인 세션(미종료)만 있으면 None(0 아님 — 미측정과 0 활동은 다르다).
      - `problems_attempted`: 그날 시작된 시도 수. `problems_correct`: `is_correct is True` 수
        (미채점 NULL은 정답으로 세지 않는다).
      - `socratic_turns`: 그날의 `막힘`·`힌트요청`·`힌트제공` 이벤트 수.
      - `concepts_practiced`: 그날 세션의 `target_concept_id`를 개념 코드로 해석한 정렬 집합
        (`concept_codes` 미해석분은 UUID 문자열로 폴백 — 조용한 누락 대신 원시 식별자 노출).
      - `avg_focus_score`: 그날 세션 `focus_score`(NULL 제외)의 평균, 소수 2자리(DECIMAL(3,2)).

    활동이 하나도 없는 (사용자, 날짜)는 행을 만들지 않는다(빈 행 양산 금지).
    """
    codes = concept_codes or {}
    keys: set[tuple[uuid.UUID, date]] = set()
    session_by_key: dict[tuple[uuid.UUID, date], list[SessionFact]] = defaultdict(list)
    attempt_by_key: dict[tuple[uuid.UUID, date], list[AttemptFact]] = defaultdict(list)
    socratic_by_key: dict[tuple[uuid.UUID, date], int] = defaultdict(int)

    for fact in sessions:
        key = (fact.user_id, metric_date_of(fact.started_at, tz=tz))
        session_by_key[key].append(fact)
        keys.add(key)
    for attempt in attempts:
        key = (attempt.user_id, metric_date_of(attempt.started_at, tz=tz))
        attempt_by_key[key].append(attempt)
        keys.add(key)
    for event in events:
        if event.event_type not in _SOCRATIC_EVENT_TYPES:
            continue
        key = (event.user_id, metric_date_of(event.event_at, tz=tz))
        socratic_by_key[key] += 1
        keys.add(key)

    rows: list[DailyLearningMetricsSchema] = []
    for user_id, metric_date in sorted(keys, key=lambda k: (str(k[0]), k[1])):
        key = (user_id, metric_date)
        day_sessions = session_by_key.get(key, [])
        day_attempts = attempt_by_key.get(key, [])

        measured_seconds = [
            s for s in (f.effective_seconds() for f in day_sessions) if s is not None
        ]
        minutes_active = sum(measured_seconds) // 60 if measured_seconds else None

        focus_scores = [float(f.focus_score) for f in day_sessions if f.focus_score is not None]
        avg_focus = _mean_or_none(focus_scores)

        concept_ids = {f.target_concept_id for f in day_sessions if f.target_concept_id is not None}
        practiced = sorted(codes.get(cid, str(cid)) for cid in concept_ids)

        rows.append(
            DailyLearningMetricsSchema(
                user_id=user_id,
                metric_date=metric_date,
                minutes_active=minutes_active,
                problems_attempted=len(day_attempts) or None,
                problems_correct=(
                    sum(1 for a in day_attempts if a.is_correct is True) if day_attempts else None
                ),
                socratic_turns=socratic_by_key.get(key) or None,
                concepts_practiced=practiced,
                # DECIMAL(3,2) — 저장 정밀도에 맞춰 반올림(DB가 조용히 자르는 대신 명시).
                avg_focus_score=(
                    None if avg_focus is None else round(min(1.0, max(0.0, avg_focus)), 2)
                ),
            )
        )
    return rows


# ──────────────────────────────────────────────────────────────────────────
# 순수 집계 ② user_behavior_metrics
# ──────────────────────────────────────────────────────────────────────────
def aggregate_user_behavior_metrics(
    sessions: Iterable[SessionFact],
    attempts: Iterable[AttemptFact],
    *,
    tz: ZoneInfo = KST,
) -> list[UserBehaviorMetricsSchema]:
    """원천 사실 → `(user_id, metric_name, measured_at)` 행동 지표(순수·측정치만).

    `measured_at`은 그 집계일의 **tz 자정(UTC 환산)** 이다 — 하루 1점의 시계열이 되어 재집계가
    같은 PK에 떨어진다(멱등). 지표는 전부 원천 카운트에서 직접 계산되며 *추론 지표(churn_risk
    등)는 생산하지 않는다*(모듈 docstring §날조 금지).

    비율 지표는 분모(시도 수)가 0이면 만들지 않는다 — 0/0을 0.0으로 적으면 "힌트를 전혀 안 썼다"는
    거짓 신호가 된다.
    """
    session_by_key: dict[tuple[uuid.UUID, date], list[SessionFact]] = defaultdict(list)
    attempt_by_key: dict[tuple[uuid.UUID, date], list[AttemptFact]] = defaultdict(list)
    keys: set[tuple[uuid.UUID, date]] = set()

    for fact in sessions:
        key = (fact.user_id, metric_date_of(fact.started_at, tz=tz))
        session_by_key[key].append(fact)
        keys.add(key)
    for attempt in attempts:
        key = (attempt.user_id, metric_date_of(attempt.started_at, tz=tz))
        attempt_by_key[key].append(attempt)
        keys.add(key)

    rows: list[UserBehaviorMetricsSchema] = []
    for user_id, metric_date in sorted(keys, key=lambda k: (str(k[0]), k[1])):
        key = (user_id, metric_date)
        day_sessions = session_by_key.get(key, [])
        day_attempts = attempt_by_key.get(key, [])
        measured_at = datetime.combine(metric_date, time.min, tzinfo=tz).astimezone(UTC)

        pairs: list[tuple[str, float]] = []
        if day_sessions:
            pairs.append((BEHAVIOR_METRIC_SESSION_COUNT, float(len(day_sessions))))
            seconds = [s for s in (f.effective_seconds() for f in day_sessions) if s is not None]
            if seconds:
                pairs.append((BEHAVIOR_METRIC_ACTIVE_MINUTES, float(sum(seconds) // 60)))
            # EOS-48 병행 지표 — 기존 daily_active_minutes(경과 기반)는 의미 불변. 실측
            # active_seconds가 있는 세션만 measured로 합산하고("측정된 것만 적재" — 미측정
            # 세션을 0으로 섞지 않는다), ratio는 계측이 실제 작동한 비율을 항상 보고한다
            # (측정 0건인 날도 0.0 — 셈이라 사실·좌석≠작동을 드러내는 신호).
            measured = [f.active_seconds for f in day_sessions if f.active_seconds is not None]
            if measured:
                pairs.append((BEHAVIOR_METRIC_MEASURED_ACTIVE_MINUTES, float(sum(measured) // 60)))
            pairs.append((BEHAVIOR_METRIC_ACTIVE_MEASURED_RATIO, len(measured) / len(day_sessions)))
        if day_attempts:
            total = len(day_attempts)
            correct = sum(1 for a in day_attempts if a.is_correct is True)
            hinted = sum(1 for a in day_attempts if a.used_hint is True)
            viewed = sum(1 for a in day_attempts if a.used_solution_view is True)
            pairs.append((BEHAVIOR_METRIC_ACCURACY_RATE, correct / total))
            pairs.append((BEHAVIOR_METRIC_HINT_RELIANCE, hinted / total))
            pairs.append((BEHAVIOR_METRIC_SOLUTION_VIEW, viewed / total))

        for metric_name, value in pairs:
            rows.append(
                UserBehaviorMetricsSchema(
                    user_id=user_id,
                    metric_name=metric_name,
                    measured_at=measured_at,
                    # DECIMAL(10,4) — 저장 정밀도에 맞춰 반올림.
                    metric_value=round(value, 4),
                )
            )
    return rows


# ──────────────────────────────────────────────────────────────────────────
# 순수 집계 ③ problem_solve_time_distribution
# ──────────────────────────────────────────────────────────────────────────
def aggregate_solve_time_distribution(
    attempts: Iterable[AttemptFact],
    *,
    tz: ZoneInfo = KST,
    min_sample: int = MIN_SOLVE_TIME_SAMPLE,
) -> list[ProblemSolveTimeDistributionSchema]:
    """원천 시도 → `(problem_id, persona, measured_at)`별 풀이 시간 분위수(순수·k-익명 하한 적용).

    `problem_id`·`persona`·`duration_seconds`가 모두 있는 시도만 표본이 된다(NULL은 분포에
    기여할 수 없다). 표본 수가 `min_sample` 미만인 조합은 **행을 만들지 않는다** — 소표본
    분위수는 개인 풀이 시간을 그대로 드러내기 때문이다(모듈 docstring §k-익명 하한).

    `measured_at`은 그 집계일의 tz 자정(UTC 환산)이라 재집계가 같은 PK에 떨어진다(멱등).
    """
    buckets: dict[tuple[uuid.UUID, Persona, datetime], list[int]] = defaultdict(list)
    for attempt in attempts:
        if attempt.problem_id is None or attempt.persona is None:
            continue
        if attempt.duration_seconds is None or attempt.duration_seconds < 0:
            continue
        metric_date = metric_date_of(attempt.started_at, tz=tz)
        measured_at = datetime.combine(metric_date, time.min, tzinfo=tz).astimezone(UTC)
        buckets[(attempt.problem_id, Persona(attempt.persona), measured_at)].append(
            attempt.duration_seconds
        )

    rows: list[ProblemSolveTimeDistributionSchema] = []
    for (problem_id, persona, measured_at), samples in sorted(
        buckets.items(), key=lambda kv: (str(kv[0][0]), kv[0][1].value, kv[0][2])
    ):
        if len(samples) < min_sample:
            continue
        rows.append(
            ProblemSolveTimeDistributionSchema(
                problem_id=problem_id,
                persona=persona,
                measured_at=measured_at,
                p10_seconds=percentile(samples, 0.10),
                p50_seconds=percentile(samples, 0.50),
                p90_seconds=percentile(samples, 0.90),
                sample_size=len(samples),
            )
        )
    return rows


# ──────────────────────────────────────────────────────────────────────────
# 리포트 — PII 0(카운트·좌석명만). CLAUDE.md 「PII를 로그에 싣지 말 것」.
# ──────────────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class RollupReport:
    """롤업 1회 실행 결과 요약 — 사용자 식별자·개념명 등 PII를 담지 않는다."""

    start_date: date
    end_date: date
    timezone: str
    dry_run: bool
    sessions_scanned: int
    attempts_scanned: int
    events_scanned: int
    daily_rows: int
    behavior_rows: int
    solve_time_rows: int
    daily_rows_pruned: int
    behavior_rows_pruned: int

    def to_json(self) -> dict[str, Any]:
        """CLI stdout용 JSON(결정론·PII 0)."""
        return {
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "timezone": self.timezone,
            "dry_run": self.dry_run,
            "scanned": {
                "learning_session": self.sessions_scanned,
                "problem_attempt": self.attempts_scanned,
                "attempt_event": self.events_scanned,
            },
            "upserted": {
                "daily_learning_metrics": self.daily_rows,
                "user_behavior_metrics": self.behavior_rows,
                "problem_solve_time_distribution": self.solve_time_rows,
            },
            "pruned": {
                "daily_learning_metrics": self.daily_rows_pruned,
                "user_behavior_metrics": self.behavior_rows_pruned,
            },
        }


# ──────────────────────────────────────────────────────────────────────────
# DB 어댑터 — 창 내 원천 행 읽기 → 순수 집계 → 멱등 upsert (+ 스테일 정리)
# ──────────────────────────────────────────────────────────────────────────
async def _fetch_sessions(
    session: AsyncSession, start: datetime, end: datetime
) -> list[SessionFact]:
    """창 내 `learning_session` — `user_id`/`started_at`이 NULL인 행은 귀속 불가라 제외."""
    stmt = select(
        LearningSession.user_id,
        LearningSession.started_at,
        LearningSession.ended_at,
        LearningSession.duration_seconds,
        LearningSession.focus_score,
        LearningSession.target_concept_id,
        LearningSession.active_seconds,  # EOS-48: 실측 활동(측정된 것만 — 병행 지표 입력)
        LearningSession.idle_seconds,
    ).where(
        LearningSession.user_id.is_not(None),
        LearningSession.started_at.is_not(None),
        LearningSession.started_at >= start,
        LearningSession.started_at < end,
    )
    result = await session.execute(stmt)
    return [
        SessionFact(
            user_id=row.user_id,
            started_at=row.started_at,
            ended_at=row.ended_at,
            duration_seconds=row.duration_seconds,
            focus_score=None if row.focus_score is None else float(row.focus_score),
            target_concept_id=row.target_concept_id,
            active_seconds=row.active_seconds,  # EOS-48: NULL=미측정 그대로(0 날조 금지)
            idle_seconds=row.idle_seconds,
        )
        for row in result
    ]


async def _fetch_attempts(
    session: AsyncSession, start: datetime, end: datetime
) -> list[AttemptFact]:
    """창 내 `problem_attempt` + 학생 페르소나(inner join).

    `user_profile`이 없는 시도(고아)는 페르소나를 알 수 없어 제외된다 — 일일 집계의 PK가
    `user_id`이므로 사용자 없는 시도는 어차피 귀속처가 없다.
    """
    stmt = (
        select(
            ProblemAttempt.user_id,
            ProblemAttempt.started_at,
            ProblemAttempt.problem_id,
            ProblemAttempt.duration_seconds,
            ProblemAttempt.is_correct,
            ProblemAttempt.used_hint,
            ProblemAttempt.used_solution_view,
            UserProfile.persona_primary,
        )
        .join(UserProfile, ProblemAttempt.user_id == UserProfile.user_id)
        .where(
            ProblemAttempt.started_at.is_not(None),
            ProblemAttempt.started_at >= start,
            ProblemAttempt.started_at < end,
        )
    )
    result = await session.execute(stmt)
    return [
        AttemptFact(
            user_id=row.user_id,
            started_at=row.started_at,
            problem_id=row.problem_id,
            persona=row.persona_primary,
            duration_seconds=row.duration_seconds,
            is_correct=row.is_correct,
            used_hint=row.used_hint,
            used_solution_view=row.used_solution_view,
        )
        for row in result
    ]


async def _fetch_events(session: AsyncSession, start: datetime, end: datetime) -> list[EventFact]:
    """창 내 `attempt_event` 중 소크라테스 3종만(전량 적재 회피)."""
    stmt = select(AttemptEvent.user_id, AttemptEvent.event_at, AttemptEvent.event_type).where(
        AttemptEvent.user_id.is_not(None),
        AttemptEvent.event_at >= start,
        AttemptEvent.event_at < end,
        AttemptEvent.event_type.in_(sorted(t.value for t in _SOCRATIC_EVENT_TYPES)),
    )
    result = await session.execute(stmt)
    return [
        EventFact(user_id=row.user_id, event_at=row.event_at, event_type=row.event_type)
        for row in result
    ]


async def _resolve_concept_codes(
    session: AsyncSession, concept_ids: set[uuid.UUID]
) -> dict[uuid.UUID, str]:
    """개념 UUID → `concept.code` 단일 조회. 미적재 개념은 맵에서 빠진다(호출자가 UUID 폴백)."""
    if not concept_ids:
        return {}
    result = await session.execute(
        select(Concept.concept_id, Concept.code).where(Concept.concept_id.in_(sorted(concept_ids)))
    )
    return {row.concept_id: row.code for row in result if row.code}


async def _upsert(
    session: AsyncSession,
    orm_model: type[Any],
    rows: Sequence[dict[str, Any]],
    *,
    index_elements: Sequence[Any],
    update_keys: Sequence[str],
) -> None:
    """PG `INSERT ... ON CONFLICT DO UPDATE` 멱등 upsert(청크 분할·`populate.py` 규약)."""
    for offset in range(0, len(rows), _UPSERT_CHUNK):
        chunk = list(rows[offset : offset + _UPSERT_CHUNK])
        stmt = pg_insert(orm_model).values(chunk)
        stmt = stmt.on_conflict_do_update(
            index_elements=list(index_elements),
            set_={key: stmt.excluded[key] for key in update_keys},
        )
        await session.execute(stmt)


async def run_daily_rollup(
    session: AsyncSession,
    *,
    start_date: date,
    end_date: date,
    tz: ZoneInfo = KST,
    min_solve_time_sample: int = MIN_SOLVE_TIME_SAMPLE,
    dry_run: bool = False,
) -> RollupReport:
    """`[start_date, end_date]`(tz 달력일) 구간을 재집계해 시계열 3테이블에 멱등 upsert.

    **commit은 호출자**(어느 단계 실패도 전부 롤백 — 부분 적재 0). `dry_run=True`면 읽기·집계만
    하고 쓰기를 건너뛴다(리포트의 행수는 *쓰였을* 행수).

    스테일 정리(reconcile): 창 안에서 활동이 관측된 사용자에 한해, 이번 재집계 결과에 없는
    `(user_id, metric_date)` 행을 삭제한다 — 원천 시도가 지워진 뒤 지표만 남는 것을 막는다.
    창 안에 활동이 *전무해진* 사용자의 잔여 행은 이 경로가 지우지 못하며, 삭제권
    (`privacy/erasure.py`)·보존 파기(`privacy/retention.py`)가 담당한다(정직한 스코프).
    """
    start_utc, end_utc = day_bounds_utc(start_date, end_date, tz=tz)

    sessions = await _fetch_sessions(session, start_utc, end_utc)
    attempts = await _fetch_attempts(session, start_utc, end_utc)
    events = await _fetch_events(session, start_utc, end_utc)

    concept_codes = await _resolve_concept_codes(
        session, {f.target_concept_id for f in sessions if f.target_concept_id is not None}
    )

    daily = aggregate_daily_metrics(sessions, attempts, events, tz=tz, concept_codes=concept_codes)
    behavior = aggregate_user_behavior_metrics(sessions, attempts, tz=tz)
    solve_time = aggregate_solve_time_distribution(
        attempts, tz=tz, min_sample=min_solve_time_sample
    )

    daily_pruned = 0
    behavior_pruned = 0
    if not dry_run:
        if daily:
            await _upsert(
                session,
                DailyLearningMetricsORM,
                [row.model_dump() for row in daily],
                index_elements=[
                    DailyLearningMetricsORM.user_id,
                    DailyLearningMetricsORM.metric_date,
                ],
                update_keys=(
                    "minutes_active",
                    "problems_attempted",
                    "problems_correct",
                    "socratic_turns",
                    "concepts_practiced",
                    "avg_focus_score",
                ),
            )
        if behavior:
            await _upsert(
                session,
                UserBehaviorMetricsORM,
                [row.model_dump() for row in behavior],
                index_elements=[
                    UserBehaviorMetricsORM.user_id,
                    UserBehaviorMetricsORM.metric_name,
                    UserBehaviorMetricsORM.measured_at,
                ],
                update_keys=("metric_value",),
            )
        if solve_time:
            await _upsert(
                session,
                ProblemSolveTimeDistributionORM,
                [row.model_dump() for row in solve_time],
                index_elements=[
                    ProblemSolveTimeDistributionORM.problem_id,
                    ProblemSolveTimeDistributionORM.persona,
                    ProblemSolveTimeDistributionORM.measured_at,
                ],
                update_keys=("p10_seconds", "p50_seconds", "p90_seconds", "sample_size"),
            )
        daily_pruned = await _prune_stale_daily(
            session,
            daily,
            sessions,
            attempts,
            events,
            start_date=start_date,
            end_date=end_date,
        )
        behavior_pruned = await _prune_stale_behavior(
            session, behavior, sessions, attempts, start_utc=start_utc, end_utc=end_utc
        )

    report = RollupReport(
        start_date=start_date,
        end_date=end_date,
        timezone=str(tz),
        dry_run=dry_run,
        sessions_scanned=len(sessions),
        attempts_scanned=len(attempts),
        events_scanned=len(events),
        daily_rows=len(daily),
        behavior_rows=len(behavior),
        solve_time_rows=len(solve_time),
        daily_rows_pruned=daily_pruned,
        behavior_rows_pruned=behavior_pruned,
    )
    # 로그에는 카운트만(사용자 식별자·개념 코드 0) — CLAUDE.md PII 로그 금지.
    _logger.info(
        "learning_metrics_rollup done: %s",
        report.to_json(),
    )
    return report


def _observed_user_ids(
    sessions: Sequence[SessionFact],
    attempts: Sequence[AttemptFact],
    events: Sequence[EventFact],
) -> set[uuid.UUID]:
    """창 안에서 활동이 관측된 사용자 집합(스테일 정리 대상 스코프)."""
    ids = {f.user_id for f in sessions}
    ids |= {a.user_id for a in attempts}
    ids |= {e.user_id for e in events}
    return ids


async def _prune_stale_daily(
    session: AsyncSession,
    daily: Sequence[DailyLearningMetricsSchema],
    sessions_facts: Sequence[SessionFact],
    attempts: Sequence[AttemptFact],
    events: Sequence[EventFact],
    *,
    start_date: date,
    end_date: date,
) -> int:
    """재집계 결과에 없는 `daily_learning_metrics` 행 삭제 — 관측된 사용자·창 범위 한정.

    정리 범위는 *재집계 결과에 등장한 날짜*가 아니라 **창 전체**(`start_date`~`end_date`)다.
    창 안의 어떤 날은 활동이 통째로 사라져 결과 행이 0일 수 있는데, 그 날짜만 범위에서 빠지면
    바로 그 스테일 행이 영영 남는다(정리해야 할 대상이 정리 범위 밖으로 나가는 자기모순).
    """
    users = _observed_user_ids(sessions_facts, attempts, events)
    if not users:
        return 0
    keep = {(row.user_id, row.metric_date) for row in daily}
    result = await session.execute(
        select(DailyLearningMetricsORM.user_id, DailyLearningMetricsORM.metric_date).where(
            DailyLearningMetricsORM.user_id.in_(sorted(users)),
            DailyLearningMetricsORM.metric_date >= start_date,
            DailyLearningMetricsORM.metric_date <= end_date,
        )
    )
    stale = [
        (row.user_id, row.metric_date)
        for row in result
        if (row.user_id, row.metric_date) not in keep
    ]
    for user_id, metric_date in stale:
        await session.execute(
            delete(DailyLearningMetricsORM).where(
                DailyLearningMetricsORM.user_id == user_id,
                DailyLearningMetricsORM.metric_date == metric_date,
            )
        )
    return len(stale)


async def _prune_stale_behavior(
    session: AsyncSession,
    behavior: Sequence[UserBehaviorMetricsSchema],
    sessions_facts: Sequence[SessionFact],
    attempts: Sequence[AttemptFact],
    *,
    start_utc: datetime,
    end_utc: datetime,
) -> int:
    """재집계 결과에 없는 `user_behavior_metrics` 행 삭제 — 관측된 사용자·창 범위 한정.

    이 롤업이 쓰는 `metric_name` 5종만 대상이다 — 다른 writer(후속 churn_risk 모델 등)가
    적재한 지표를 이 정리가 지우면 안 된다.
    """
    users = {f.user_id for f in sessions_facts} | {a.user_id for a in attempts}
    if not users:
        return 0
    owned = sorted(
        {
            BEHAVIOR_METRIC_ACTIVE_MINUTES,
            BEHAVIOR_METRIC_ACCURACY_RATE,
            BEHAVIOR_METRIC_HINT_RELIANCE,
            BEHAVIOR_METRIC_SOLUTION_VIEW,
            BEHAVIOR_METRIC_SESSION_COUNT,
        }
    )
    keep = {(row.user_id, row.metric_name, row.measured_at) for row in behavior}
    result = await session.execute(
        select(
            UserBehaviorMetricsORM.user_id,
            UserBehaviorMetricsORM.metric_name,
            UserBehaviorMetricsORM.measured_at,
        ).where(
            UserBehaviorMetricsORM.user_id.in_(sorted(users)),
            UserBehaviorMetricsORM.metric_name.in_(owned),
            UserBehaviorMetricsORM.measured_at >= start_utc,
            UserBehaviorMetricsORM.measured_at < end_utc,
        )
    )
    stale = [
        (row.user_id, row.metric_name, row.measured_at)
        for row in result
        if (row.user_id, row.metric_name, row.measured_at) not in keep
    ]
    for user_id, metric_name, measured_at in stale:
        await session.execute(
            delete(UserBehaviorMetricsORM).where(
                UserBehaviorMetricsORM.user_id == user_id,
                UserBehaviorMetricsORM.metric_name == metric_name,
                UserBehaviorMetricsORM.measured_at == measured_at,
            )
        )
    return len(stale)
