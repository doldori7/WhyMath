"""L2 — 학습시간·행동 집계 writer: `daily_learning_metrics`·`problem_solve_time_distribution`·
`user_behavior_metrics` 일별 롤업 (COLLAB-03).

배경(`collaboration_module_gap_review.md` §3 D3): 세 테이블은 ORM/Pydantic 정의·파기
(`privacy/erasure.py`)·반출(`privacy/export.py`)·보존(`privacy/retention.py`) 배관에 전부
등재돼 있으나, 프로덕션 writer가 0건이었다(적재 공급원 부재 — `visualization_module_gap_
review.md` D1과 동일 실패 유형의 재발). 이 모듈이 그 공급원이다.

설계 분리(`l2/mastery_tracking.py` `compute_mastery_record`/`record_attempt_mastery` 패턴
답습):
  - **`compute_*` 3종** — *순수*(DB 무관) 집계. 원본 활동 행(dataclass) → 적재 레코드.
    hermetic 전수 검증(퍼센타일·합계·평균 등 수치 로직을 실 PG 없이 검증).
  - **`_fetch_*`** — 얇은 async SELECT 래퍼(날짜창 필터·조인만, 계산 없음).
  - **`_upsert_*`** — 얇은 async UPSERT 래퍼(`sqlalchemy.dialects.postgresql.insert` +
    `on_conflict_do_update` — `l1/atom_probe/projection.py`·`l1/skill_graph/
    skill_node_projection.py`의 멱등 upsert 관용구를 *sync 엔진 대신 주입 AsyncSession*으로
    적용한다. 이 writer는 L1 프로젝션(JSON→DB 1방향)과 달리 *DB 활동 테이블→DB 집계 테이블*
    이라 읽기·쓰기 모두 이미 L2 전역에서 쓰는 AsyncSession이 자연스럽다 — `l2/mastery_
    tracking.py`가 `AsyncSession`으로 읽고 쓰는 것과 동형).
  - **`run_daily_rollup`** — 위 세 집계를 하루 단위로 조율하는 공개 진입점. commit은
    호출자 대신 이 함수가 담당(원자성 — 세 테이블 모두 한 트랜잭션. `record_problem_attempt_
    mastery`의 "루프 후 1회 commit" 선례와 동일 사상).

데이터 매핑 근거(백로그 태스크 COLLAB-03 명시 지시):
  - `minutes_active` — `problem_attempt`가 아니라 **`learning_session.duration_seconds`
    합/60**. `learning_session.problems_attempted`/`problems_correct` 컬럼은 실 writer가
    없어(grep 실측 — 코드베이스 어디서도 대입되지 않음) 프로덕션에서 항상 NULL이므로 그
    필드는 *쓰지 않는다*(가짜 소스 금지) — 대신 `problem_attempt` 원장에서 직접 COUNT한다.
  - `problems_attempted`/`problems_correct` — `problem_attempt`(is_correct 유무) 직접 COUNT.
  - `socratic_turns` — `dialogue.total_turns` 합(dialogue.started_at 날짜 기준).
  - `concepts_practiced` — 그날 시도한 문제의 **PRIMARY** 개념 코드(distinct). `problem_
    attempt.stuck_at_concept_id`는 "막힌 지점"만 가리키는 느슨참조라 "연습한 개념" 의미에
    맞지 않고, `learning_session.target_concept_id`는 세션 단위 *목표*(실제로 뭘 풀었는지와
    다를 수 있음)라 배제 — `problem_concept`(PRIMARY) 조인이 "이 문제의 핵심 개념"이라는
    가장 방어 가능한 소스다(`api/me.py get_my_ability`의 PRIMARY 우선 폴백 선례와 동일 근거).
  - `avg_focus_score` — `learning_session.focus_score` 평균(NULL 제외).
  - `problem_solve_time_distribution` — `problem_attempt.duration_seconds`(NULL 제외)를
    (problem_id, `user_profile.persona_primary`)로 묶어 p10/p50/p90(선형보간, 아래
    `_percentile`) + 표본수.
  - `user_behavior_metrics` — 최소 스코프(churn_risk 등 ML 모델은 범위 밖·태스크 명시).
    `session_count_last_7d`(최근 7일 `learning_session` 행수)·`days_active_last_7d`(최근
    7일 중 세션이 있었던 distinct 날짜 수) 2종만. 둘 다 `learning_session`만 봐 정직하게
    계산 가능한 지표로 한정했다(다른 활동 유형까지 합친 "활동일" 등은 후속 확장 여지로 남김).

파기·반출·보존 정합(항목 ⑥ — 신규 코드 없음·확인만):
  `privacy/erasure.py`(user_id 등재: `DailyLearningMetrics`·`UserBehaviorMetrics`)·
  `privacy/export.py`(동일 2종 user_id export 등재·`ProblemSolveTimeDistribution`은
  *의도적 미등재* — problem_id 키 교차사용자 집계라 개인 PII 아님, 이 writer는 그 설계를
  변경하지 않는다)·`privacy/retention.py`(`DailyLearningMetrics.metric_date`·
  `UserBehaviorMetrics.measured_at` 컬럼 기준 파기)는 이미 이 writer가 채우는 정확한 컬럼을
  키로 쓰고 있어 *추가 코드 불요*. 집계 주기는 **일 단위**(하루 지난 뒤 그 날짜로 1회 실행 —
  `measured_at`은 그 날짜의 00:00 UTC로 고정해 재실행이 같은 PK를 충돌·갱신하게 한다=멱등).

7계층: L2 학습자 모델의 영속 집계 writer. `learning_session`·`problem_attempt`·`dialogue`
(L1-인접 활동 테이블, `l2/ability_tracking.py`가 `problem_attempt`를 읽는 것과 동일 패턴)를
읽어 L2 소유 시계열 테이블에 쓴다. api(L5)가 이 모듈을 호출하는 것은 허용(`api/me.py`가
`l2/mastery_tracking.py`를 호출하는 것과 동형)이나 역방향(L2→api) import는 없다.
"""

from __future__ import annotations

import argparse
import asyncio
import math
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from whymath_backend.db.models.activity import LearningSession, ProblemAttempt
from whymath_backend.db.models.concept import Concept, ProblemConcept
from whymath_backend.db.models.dialogue import Dialogue
from whymath_backend.db.models.timeseries import (
    DailyLearningMetrics,
    ProblemSolveTimeDistribution,
    UserBehaviorMetrics,
)
from whymath_backend.db.models.user import UserProfile
from whymath_backend.schema.enums import ConceptRole, Persona

__all__ = [
    "BEHAVIOR_METRIC_DAYS_ACTIVE_7D",
    "BEHAVIOR_METRIC_SESSION_COUNT_7D",
    "BehaviorMetricRecord",
    "DailyMetricRecord",
    "DailyRollupReport",
    "SolveTimeRecord",
    "compute_daily_learning_metrics",
    "compute_problem_solve_time_distribution",
    "compute_user_behavior_metrics",
    "main",
    "run_daily_rollup",
]

# 최근 7일 롤링 윈도우(간단 지표) — churn_risk 등 ML 모델은 범위 밖(태스크 명시 스코프 축소).
_BEHAVIOR_WINDOW_DAYS = 7
BEHAVIOR_METRIC_SESSION_COUNT_7D = "session_count_last_7d"
BEHAVIOR_METRIC_DAYS_ACTIVE_7D = "days_active_last_7d"


# ──────────────────────────────────────────────────────────────────────────
# 순수 집계 레코드(DB 무관) — 적재 레코드 shape
# ──────────────────────────────────────────────────────────────────────────
@dataclass(frozen=True, slots=True)
class DailyMetricRecord:
    """`daily_learning_metrics` 1행(적재 입력) — PK (user_id, metric_date)."""

    user_id: uuid.UUID
    metric_date: date
    minutes_active: int | None
    problems_attempted: int | None
    problems_correct: int | None
    socratic_turns: int | None
    concepts_practiced: list[str]
    avg_focus_score: float | None


@dataclass(frozen=True, slots=True)
class SolveTimeRecord:
    """`problem_solve_time_distribution` 1행 — PK (problem_id, persona, measured_at)."""

    problem_id: uuid.UUID
    persona: Persona
    measured_at: datetime
    p10_seconds: int
    p50_seconds: int
    p90_seconds: int
    sample_size: int


@dataclass(frozen=True, slots=True)
class BehaviorMetricRecord:
    """`user_behavior_metrics` 1행 — PK (user_id, metric_name, measured_at)."""

    user_id: uuid.UUID
    metric_name: str
    measured_at: datetime
    metric_value: float


@dataclass(frozen=True, slots=True)
class DailyRollupReport:
    """`run_daily_rollup` 실행 결과 — 테이블별 upsert 행수(변별력 축 ④ 판정 재료)."""

    metric_date: date
    daily_learning_metrics_rows: int
    problem_solve_time_distribution_rows: int
    user_behavior_metrics_rows: int


# ──────────────────────────────────────────────────────────────────────────
# 원본 활동 행(DB 무관 dataclass) — fetch↔compute 경계(순수 함수 입력)
# ──────────────────────────────────────────────────────────────────────────
@dataclass(frozen=True, slots=True)
class _SessionActivity:
    user_id: uuid.UUID
    duration_seconds: int | None
    focus_score: float | None


@dataclass(frozen=True, slots=True)
class _AttemptActivity:
    user_id: uuid.UUID
    is_correct: bool | None


@dataclass(frozen=True, slots=True)
class _DialogueActivity:
    user_id: uuid.UUID
    total_turns: int | None


# ──────────────────────────────────────────────────────────────────────────
# 퍼센타일(선형보간·numpy 'linear'/Excel PERCENTILE.INC와 동일 정의) — 순수 함수
# ──────────────────────────────────────────────────────────────────────────
def _percentile(sorted_values: Sequence[int], pct: float) -> int:
    """정렬된 값에서 백분위수 — 선형보간, 결과는 초 단위로 반올림한 정수.

    `sorted_values`는 오름차순 정렬·비어있지 않아야 한다(호출부가 보장). 새 의존성(numpy
    percentile 등) 없이 표준 선형보간 공식만 쓴다 — 이 코드베이스에 percentile_cont·numpy
    percentile 선례가 없어(실측) 가장 단순하고 검증 가능한 형태를 택했다(태스크 명시 지시).
    """
    n = len(sorted_values)
    if n == 1:
        return sorted_values[0]
    rank = pct * (n - 1)
    lo = math.floor(rank)
    hi = math.ceil(rank)
    if lo == hi:
        return round(sorted_values[int(rank)])
    frac = rank - lo
    value = sorted_values[lo] + (sorted_values[hi] - sorted_values[lo]) * frac
    return round(value)


# ──────────────────────────────────────────────────────────────────────────
# 순수 집계 함수 3종 — hermetic 전수 검증 대상
# ──────────────────────────────────────────────────────────────────────────
def compute_daily_learning_metrics(
    metric_date: date,
    sessions: Sequence[_SessionActivity],
    attempts: Sequence[_AttemptActivity],
    dialogues: Sequence[_DialogueActivity],
    concepts_by_user: Mapping[uuid.UUID, Sequence[str]],
) -> list[DailyMetricRecord]:
    """그날의 원본 활동 행 → 사용자별 `daily_learning_metrics` 레코드(순수·DB 무관).

    행이 하나도 없는 사용자는 결과에 없다(빈 날 행 0 — 조용한 0행 적재 방지). 세션·시도·
    대화·연습개념 중 *어느 하나*라도 있는 사용자는 결과에 포함되고(그날 활동이 있었다는
    의미), 없는 필드는 정직하게 None(퍼센타일과 달리 합계는 부재≠0 — schema Optional과 정합).
    """
    users: set[uuid.UUID] = set()
    minutes_seconds: dict[uuid.UUID, int] = {}
    focus_sum: dict[uuid.UUID, float] = {}
    focus_n: dict[uuid.UUID, int] = {}
    for s in sessions:
        users.add(s.user_id)
        if s.duration_seconds is not None:
            minutes_seconds[s.user_id] = minutes_seconds.get(s.user_id, 0) + s.duration_seconds
        if s.focus_score is not None:
            focus_sum[s.user_id] = focus_sum.get(s.user_id, 0.0) + s.focus_score
            focus_n[s.user_id] = focus_n.get(s.user_id, 0) + 1

    attempted: dict[uuid.UUID, int] = {}
    correct: dict[uuid.UUID, int] = {}
    for a in attempts:
        users.add(a.user_id)
        attempted[a.user_id] = attempted.get(a.user_id, 0) + 1
        if a.is_correct:
            correct[a.user_id] = correct.get(a.user_id, 0) + 1

    turns: dict[uuid.UUID, int] = {}
    for d in dialogues:
        users.add(d.user_id)
        if d.total_turns is not None:
            turns[d.user_id] = turns.get(d.user_id, 0) + d.total_turns

    users.update(concepts_by_user.keys())

    records: list[DailyMetricRecord] = []
    for user_id in sorted(users, key=str):  # 결정론적 순서(테스트·로그 안정)
        seconds = minutes_seconds.get(user_id)
        avg_focus = round(focus_sum[user_id] / focus_n[user_id], 2) if user_id in focus_n else None
        records.append(
            DailyMetricRecord(
                user_id=user_id,
                metric_date=metric_date,
                minutes_active=seconds // 60 if seconds is not None else None,
                problems_attempted=attempted.get(user_id),
                problems_correct=correct.get(user_id),
                socratic_turns=turns.get(user_id),
                concepts_practiced=sorted(set(concepts_by_user.get(user_id, ()))),
                avg_focus_score=avg_focus,
            )
        )
    return records


def compute_problem_solve_time_distribution(
    measured_at: datetime,
    rows: Sequence[tuple[uuid.UUID, Persona, int]],
) -> list[SolveTimeRecord]:
    """(problem_id, persona, duration_seconds) 원본 행 → 문항·페르소나별 p10/p50/p90(순수).

    `rows`는 duration_seconds가 NULL이 아닌 것만 호출부가 필터해 넘긴다(퍼센타일은 결측을
    다루지 않음 — fetch 단계 책임). 표본 0인 (problem_id, persona) 쌍은 애초에 그룹이 생기지
    않으므로 결과에 없다(가짜 0 대신 행 부재).
    """
    groups: dict[tuple[uuid.UUID, Persona], list[int]] = {}
    for problem_id, persona, duration in rows:
        groups.setdefault((problem_id, persona), []).append(duration)

    records: list[SolveTimeRecord] = []
    for (problem_id, persona), durations in sorted(
        groups.items(), key=lambda kv: (str(kv[0][0]), kv[0][1].value)
    ):
        ordered = sorted(durations)
        records.append(
            SolveTimeRecord(
                problem_id=problem_id,
                persona=persona,
                measured_at=measured_at,
                p10_seconds=_percentile(ordered, 0.10),
                p50_seconds=_percentile(ordered, 0.50),
                p90_seconds=_percentile(ordered, 0.90),
                sample_size=len(ordered),
            )
        )
    return records


def compute_user_behavior_metrics(
    measured_at: datetime,
    session_starts: Sequence[tuple[uuid.UUID, datetime]],
) -> list[BehaviorMetricRecord]:
    """최근 `_BEHAVIOR_WINDOW_DAYS`일 세션 (user_id, started_at) → 최소 행동 지표 2종(순수).

    `session_starts`는 이미 [window_start, window_end) 범위로 필터된 세션만 담겨 있다고
    가정(fetch 단계 책임). churn_risk 등 예측 모델은 범위 밖(태스크 명시) — 정직히 셀 수
    있는 두 지표(세션 수·활동일 수)만 낸다.
    """
    counts: dict[uuid.UUID, int] = {}
    days: dict[uuid.UUID, set[date]] = {}
    for user_id, started_at in session_starts:
        counts[user_id] = counts.get(user_id, 0) + 1
        days.setdefault(user_id, set()).add(started_at.date())

    records: list[BehaviorMetricRecord] = []
    for user_id in sorted(counts, key=str):
        records.append(
            BehaviorMetricRecord(
                user_id=user_id,
                metric_name=BEHAVIOR_METRIC_SESSION_COUNT_7D,
                measured_at=measured_at,
                metric_value=float(counts[user_id]),
            )
        )
        records.append(
            BehaviorMetricRecord(
                user_id=user_id,
                metric_name=BEHAVIOR_METRIC_DAYS_ACTIVE_7D,
                measured_at=measured_at,
                metric_value=float(len(days[user_id])),
            )
        )
    return records


# ──────────────────────────────────────────────────────────────────────────
# fetch(얇은 async SELECT) — 날짜창 필터·조인만, 계산 0
# ──────────────────────────────────────────────────────────────────────────
async def _fetch_session_activity(
    session: AsyncSession, day_start: datetime, day_end: datetime
) -> list[_SessionActivity]:
    stmt = select(
        LearningSession.user_id,
        LearningSession.duration_seconds,
        LearningSession.focus_score,
    ).where(
        LearningSession.user_id.is_not(None),
        LearningSession.started_at >= day_start,
        LearningSession.started_at < day_end,
    )
    result = await session.execute(stmt)
    return [
        _SessionActivity(
            user_id=row[0],
            duration_seconds=row[1],
            focus_score=float(row[2]) if row[2] is not None else None,
        )
        for row in result.all()
    ]


async def _fetch_attempt_activity(
    session: AsyncSession, day_start: datetime, day_end: datetime
) -> list[_AttemptActivity]:
    stmt = select(ProblemAttempt.user_id, ProblemAttempt.is_correct).where(
        ProblemAttempt.user_id.is_not(None),
        ProblemAttempt.started_at >= day_start,
        ProblemAttempt.started_at < day_end,
    )
    result = await session.execute(stmt)
    return [_AttemptActivity(user_id=row[0], is_correct=row[1]) for row in result.all()]


async def _fetch_dialogue_activity(
    session: AsyncSession, day_start: datetime, day_end: datetime
) -> list[_DialogueActivity]:
    stmt = select(Dialogue.user_id, Dialogue.total_turns).where(
        Dialogue.user_id.is_not(None),
        Dialogue.started_at >= day_start,
        Dialogue.started_at < day_end,
    )
    result = await session.execute(stmt)
    return [_DialogueActivity(user_id=row[0], total_turns=row[1]) for row in result.all()]


async def _fetch_practiced_concepts(
    session: AsyncSession, day_start: datetime, day_end: datetime
) -> dict[uuid.UUID, list[str]]:
    """그날 시도한 문제의 PRIMARY 개념 코드 — user_id별 목록(중복 가능·`compute_*`가 dedup)."""
    stmt = (
        select(ProblemAttempt.user_id, Concept.code)
        .join(ProblemConcept, ProblemConcept.problem_id == ProblemAttempt.problem_id)
        .join(Concept, Concept.concept_id == ProblemConcept.concept_id)
        .where(
            ProblemAttempt.user_id.is_not(None),
            ProblemAttempt.problem_id.is_not(None),
            ProblemConcept.role == ConceptRole.PRIMARY,
            ProblemAttempt.started_at >= day_start,
            ProblemAttempt.started_at < day_end,
        )
        .distinct()
    )
    result = await session.execute(stmt)
    out: dict[uuid.UUID, list[str]] = {}
    for user_id, code in result.all():
        out.setdefault(user_id, []).append(code)
    return out


async def _fetch_solve_time_rows(
    session: AsyncSession, day_start: datetime, day_end: datetime
) -> list[tuple[uuid.UUID, Persona, int]]:
    stmt = (
        select(
            ProblemAttempt.problem_id,
            UserProfile.persona_primary,
            ProblemAttempt.duration_seconds,
        )
        .join(UserProfile, UserProfile.user_id == ProblemAttempt.user_id)
        .where(
            ProblemAttempt.problem_id.is_not(None),
            ProblemAttempt.duration_seconds.is_not(None),
            ProblemAttempt.started_at >= day_start,
            ProblemAttempt.started_at < day_end,
        )
    )
    result = await session.execute(stmt)
    return [(row[0], row[1], row[2]) for row in result.all()]


async def _fetch_recent_session_starts(
    session: AsyncSession, window_start: datetime, window_end: datetime
) -> list[tuple[uuid.UUID, datetime]]:
    stmt = select(LearningSession.user_id, LearningSession.started_at).where(
        LearningSession.user_id.is_not(None),
        LearningSession.started_at >= window_start,
        LearningSession.started_at < window_end,
    )
    result = await session.execute(stmt)
    return [(row[0], row[1]) for row in result.all()]


# ──────────────────────────────────────────────────────────────────────────
# upsert(얇은 async, 멱등) — `l1/atom_probe/projection.py` on_conflict_do_update 관용구를
# 주입 AsyncSession으로 적용(신규 seam은 pg_insert 자체뿐 — L2 전역 AsyncSession 패턴 재사용)
# ──────────────────────────────────────────────────────────────────────────
async def _upsert_daily_learning_metrics(
    session: AsyncSession, records: Sequence[DailyMetricRecord]
) -> int:
    if not records:
        return 0
    values: list[dict[str, Any]] = [
        {
            "user_id": r.user_id,
            "metric_date": r.metric_date,
            "minutes_active": r.minutes_active,
            "problems_attempted": r.problems_attempted,
            "problems_correct": r.problems_correct,
            "socratic_turns": r.socratic_turns,
            "concepts_practiced": list(r.concepts_practiced),
            "avg_focus_score": r.avg_focus_score,
        }
        for r in records
    ]
    stmt = pg_insert(DailyLearningMetrics).values(values)
    stmt = stmt.on_conflict_do_update(
        index_elements=[DailyLearningMetrics.user_id, DailyLearningMetrics.metric_date],
        set_={
            "minutes_active": stmt.excluded.minutes_active,
            "problems_attempted": stmt.excluded.problems_attempted,
            "problems_correct": stmt.excluded.problems_correct,
            "socratic_turns": stmt.excluded.socratic_turns,
            "concepts_practiced": stmt.excluded.concepts_practiced,
            "avg_focus_score": stmt.excluded.avg_focus_score,
        },
    )
    await session.execute(stmt)
    return len(records)


async def _upsert_problem_solve_time_distribution(
    session: AsyncSession, records: Sequence[SolveTimeRecord]
) -> int:
    if not records:
        return 0
    values: list[dict[str, Any]] = [
        {
            "problem_id": r.problem_id,
            "persona": r.persona.value,
            "measured_at": r.measured_at,
            "p10_seconds": r.p10_seconds,
            "p50_seconds": r.p50_seconds,
            "p90_seconds": r.p90_seconds,
            "sample_size": r.sample_size,
        }
        for r in records
    ]
    stmt = pg_insert(ProblemSolveTimeDistribution).values(values)
    stmt = stmt.on_conflict_do_update(
        index_elements=[
            ProblemSolveTimeDistribution.problem_id,
            ProblemSolveTimeDistribution.persona,
            ProblemSolveTimeDistribution.measured_at,
        ],
        set_={
            "p10_seconds": stmt.excluded.p10_seconds,
            "p50_seconds": stmt.excluded.p50_seconds,
            "p90_seconds": stmt.excluded.p90_seconds,
            "sample_size": stmt.excluded.sample_size,
        },
    )
    await session.execute(stmt)
    return len(records)


async def _upsert_user_behavior_metrics(
    session: AsyncSession, records: Sequence[BehaviorMetricRecord]
) -> int:
    if not records:
        return 0
    values: list[dict[str, Any]] = [
        {
            "user_id": r.user_id,
            "metric_name": r.metric_name,
            "measured_at": r.measured_at,
            "metric_value": r.metric_value,
        }
        for r in records
    ]
    stmt = pg_insert(UserBehaviorMetrics).values(values)
    stmt = stmt.on_conflict_do_update(
        index_elements=[
            UserBehaviorMetrics.user_id,
            UserBehaviorMetrics.metric_name,
            UserBehaviorMetrics.measured_at,
        ],
        set_={"metric_value": stmt.excluded.metric_value},
    )
    await session.execute(stmt)
    return len(records)


# ──────────────────────────────────────────────────────────────────────────
# 조율 진입점
# ──────────────────────────────────────────────────────────────────────────
async def run_daily_rollup(session: AsyncSession, target_date: date) -> DailyRollupReport:
    """`target_date`(UTC 기준 하루) 활동을 세 테이블에 멱등 upsert — 공개 진입점.

    `learning_session`·`problem_attempt`·`dialogue`(+ `problem_concept`·`user_profile`
    조인)에서 그날 행을 읽어(fetch) 순수 함수로 집계(compute)한 뒤 upsert한다. 세 테이블
    upsert가 끝난 뒤 **한 번만 commit**(원자성 — 부분 적재 방지, `record_problem_attempt_
    mastery` "루프 후 1회 commit" 선례). `measured_at`은 그날 00:00 UTC로 고정해 같은 날짜
    재실행이 같은 PK를 충돌·갱신(멱등)하게 한다.
    """
    day_start = datetime.combine(target_date, time.min, tzinfo=UTC)
    day_end = day_start + timedelta(days=1)

    sessions = await _fetch_session_activity(session, day_start, day_end)
    attempts = await _fetch_attempt_activity(session, day_start, day_end)
    dialogues = await _fetch_dialogue_activity(session, day_start, day_end)
    concepts_by_user = await _fetch_practiced_concepts(session, day_start, day_end)
    daily_records = compute_daily_learning_metrics(
        target_date, sessions, attempts, dialogues, concepts_by_user
    )
    daily_n = await _upsert_daily_learning_metrics(session, daily_records)

    solve_time_rows = await _fetch_solve_time_rows(session, day_start, day_end)
    solve_time_records = compute_problem_solve_time_distribution(day_start, solve_time_rows)
    solve_time_n = await _upsert_problem_solve_time_distribution(session, solve_time_records)

    window_start = day_start - timedelta(days=_BEHAVIOR_WINDOW_DAYS - 1)
    recent_starts = await _fetch_recent_session_starts(session, window_start, day_end)
    behavior_records = compute_user_behavior_metrics(day_start, recent_starts)
    behavior_n = await _upsert_user_behavior_metrics(session, behavior_records)

    await session.commit()
    return DailyRollupReport(
        metric_date=target_date,
        daily_learning_metrics_rows=daily_n,
        problem_solve_time_distribution_rows=solve_time_n,
        user_behavior_metrics_rows=behavior_n,
    )


# ──────────────────────────────────────────────────────────────────────────
# CLI(신규 스케줄러 도입 금지 — cron/수동 실행 관용구, `ops/dialogue_encryption_preflight.py`
# 의 `async_sessionmaker(create_async_engine(...))` + `asyncio.run` 패턴 미러)
# ──────────────────────────────────────────────────────────────────────────
def main(argv: list[str] | None = None) -> int:
    """CLI 진입 — 지정 날짜(기본 어제·UTC) 롤업 실행 후 리포트 출력. 항상 0 반환(예외는 전파).

    새 스케줄러(Celery beat 등)를 도입하지 않는다 — 태스크 명시 지시대로 기존 populate/CLI
    관용구를 재사용한다(운영에서는 Kiki가 cron/수동으로 이 커맨드를 하루 1회 실행).
    """
    parser = argparse.ArgumentParser(
        prog="python -m whymath_backend.l2.learning_metrics_writer",
        description=(
            "daily_learning_metrics·problem_solve_time_distribution·user_behavior_metrics "
            "일별 롤업(멱등 upsert). 새 스케줄러 도입 없음 — cron/수동 실행."
        ),
    )
    parser.add_argument(
        "--date",
        type=date.fromisoformat,
        default=None,
        help="집계 대상 날짜(YYYY-MM-DD). 생략 시 어제(UTC) — 그날이 완전히 끝난 뒤 집계.",
    )
    args = parser.parse_args(argv)
    target_date: date = args.date or (datetime.now(UTC).date() - timedelta(days=1))

    async def _run() -> DailyRollupReport:
        from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

        from whymath_backend.config import get_settings

        settings = get_settings()
        engine = create_async_engine(settings.database_url)
        sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
        try:
            async with sessionmaker() as session:
                return await run_daily_rollup(session, target_date)
        finally:
            await engine.dispose()

    report = asyncio.run(_run())
    print(
        f"일별 학습 지표 롤업 완료 — {report.metric_date.isoformat()}: "
        f"daily_learning_metrics {report.daily_learning_metrics_rows}행 · "
        f"problem_solve_time_distribution {report.problem_solve_time_distribution_rows}행 · "
        f"user_behavior_metrics {report.user_behavior_metrics_rows}행"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI 진입
    raise SystemExit(main())
