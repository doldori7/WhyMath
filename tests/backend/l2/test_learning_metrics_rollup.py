"""일별 학습 지표 롤업 순수 집계 테스트 (COLLAB-03) — hermetic·DB 불필요.

`l2.learning_metrics_rollup`의 집계 본체는 순수 함수라 DB 없이 전량 검증된다. DB 어댑터·
멱등 upsert·`/v1/me` 도달은 실 PG 통합테스트
(`tests/backend/api/test_learning_metrics_rollup_integration.py`)가 맡는다(변별력 ④⑤).

변별력 원칙(CLAUDE.md 「변별력 없는 검증 스텝 금지」): 각 케이스는 *잘못 구현했을 때 실제로
빨개지는* 값을 단언한다 — 특히 ① 미측정을 0으로 날조하지 않는지(None 단언) ② KST 경계에서
날짜 귀속이 UTC로 밀리지 않는지 ③ k-익명 하한 미만 표본이 실제로 *빠지는지*.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from whymath_backend.harness.learning_metrics_rollup_cli import resolve_window
from whymath_backend.l2.learning_metrics_rollup import (
    BEHAVIOR_METRIC_ACCURACY_RATE,
    BEHAVIOR_METRIC_ACTIVE_MINUTES,
    BEHAVIOR_METRIC_HINT_RELIANCE,
    BEHAVIOR_METRIC_SESSION_COUNT,
    BEHAVIOR_METRIC_SOLUTION_VIEW,
    KST,
    AttemptFact,
    EventFact,
    SessionFact,
    aggregate_daily_metrics,
    aggregate_solve_time_distribution,
    aggregate_user_behavior_metrics,
    day_bounds_utc,
    metric_date_of,
    percentile,
)
from whymath_backend.schema.enums import EventType, Persona

_USER = uuid.UUID("11111111-1111-1111-1111-111111111111")
_USER_B = uuid.UUID("22222222-2222-2222-2222-222222222222")
_PROBLEM = uuid.UUID("33333333-3333-3333-3333-333333333333")
_CONCEPT = uuid.UUID("44444444-4444-4444-4444-444444444444")


def _kst(y: int, m: int, d: int, hh: int = 12, mm: int = 0) -> datetime:
    """KST 시각 → tz-aware datetime(원천 TIMESTAMPTZ 모사)."""
    return datetime(y, m, d, hh, mm, tzinfo=KST)


# ──────────────────────────────────────────────────────────────────────────
# 날짜 귀속 — KST 경계(변별력: UTC로 구현하면 하루 밀려 빨개진다)
# ──────────────────────────────────────────────────────────────────────────
class TestMetricDateOf:
    def test_kst_early_morning_stays_same_day(self) -> None:
        """KST 08:00(= 전날 23:00 UTC)은 *그날*로 귀속된다 — UTC 기준이면 전날로 밀린다."""
        moment = datetime(2026, 8, 10, 8, 0, tzinfo=KST)
        assert moment.astimezone(UTC).date() == date(2026, 8, 9)  # UTC로는 전날
        assert metric_date_of(moment) == date(2026, 8, 10)  # KST로는 당일

    def test_kst_just_before_midnight_stays_same_day(self) -> None:
        assert metric_date_of(datetime(2026, 8, 10, 23, 59, tzinfo=KST)) == date(2026, 8, 10)

    def test_naive_datetime_treated_as_utc(self) -> None:
        """naive는 UTC로 간주 — KST 09:00이므로 같은 날."""
        assert metric_date_of(datetime(2026, 8, 10, 0, 30)) == date(2026, 8, 10)

    def test_tz_injectable(self) -> None:
        assert metric_date_of(_kst(2026, 8, 10, 8), tz=ZoneInfo("UTC")) == date(2026, 8, 9)


class TestDayBoundsUtc:
    def test_single_day_window_is_24h_halfopen(self) -> None:
        start, end = day_bounds_utc(date(2026, 8, 10), date(2026, 8, 10))
        assert start == datetime(2026, 8, 9, 15, 0, tzinfo=UTC)  # KST 자정 = UTC 15:00 전날
        assert end - start == timedelta(days=1)

    def test_reversed_range_raises(self) -> None:
        with pytest.raises(ValueError, match="이르다"):
            day_bounds_utc(date(2026, 8, 11), date(2026, 8, 10))


# ──────────────────────────────────────────────────────────────────────────
# 백분위수
# ──────────────────────────────────────────────────────────────────────────
class TestPercentile:
    def test_single_sample_returns_itself(self) -> None:
        assert percentile([42], 0.5) == 42

    def test_linear_interpolation(self) -> None:
        values = [10, 20, 30, 40, 50]
        assert percentile(values, 0.0) == 10
        assert percentile(values, 0.5) == 30
        assert percentile(values, 1.0) == 50
        assert percentile(values, 0.10) == 14  # 10 + 0.4*(20-10)

    def test_unsorted_input_is_sorted(self) -> None:
        assert percentile([50, 10, 30, 20, 40], 0.5) == 30

    def test_empty_raises(self) -> None:
        with pytest.raises(ValueError, match="표본"):
            percentile([], 0.5)


# ──────────────────────────────────────────────────────────────────────────
# ① daily_learning_metrics
# ──────────────────────────────────────────────────────────────────────────
class TestAggregateDailyMetrics:
    def test_empty_input_produces_no_rows(self) -> None:
        """활동 0 → 행 0. 빈 행을 양산하지 않는다(변별력 ④의 '전 0행' 축과 짝)."""
        assert aggregate_daily_metrics([], [], []) == []

    def test_full_day_rollup(self) -> None:
        sessions = [
            SessionFact(
                user_id=_USER,
                started_at=_kst(2026, 8, 10, 9),
                duration_seconds=1800,  # 30분
                focus_score=0.8,
                target_concept_id=_CONCEPT,
            ),
            SessionFact(
                user_id=_USER,
                started_at=_kst(2026, 8, 10, 14),
                duration_seconds=900,  # 15분
                focus_score=0.6,
            ),
        ]
        attempts = [
            AttemptFact(user_id=_USER, started_at=_kst(2026, 8, 10, 9, 10), is_correct=True),
            AttemptFact(user_id=_USER, started_at=_kst(2026, 8, 10, 9, 20), is_correct=False),
            AttemptFact(user_id=_USER, started_at=_kst(2026, 8, 10, 9, 30), is_correct=None),
        ]
        events = [
            EventFact(user_id=_USER, event_at=_kst(2026, 8, 10, 9, 15), event_type=EventType.막힘),
            EventFact(
                user_id=_USER, event_at=_kst(2026, 8, 10, 9, 16), event_type=EventType.힌트요청
            ),
            # 소크라테스 아님 — 세지 않는다(변별력: 세면 3이 되어 빨개진다).
            EventFact(user_id=_USER, event_at=_kst(2026, 8, 10, 9, 17), event_type=EventType.계산),
        ]
        rows = aggregate_daily_metrics(
            sessions, attempts, events, concept_codes={_CONCEPT: "MATH-II-01"}
        )
        assert len(rows) == 1
        row = rows[0]
        assert row.user_id == _USER
        assert row.metric_date == date(2026, 8, 10)
        assert row.minutes_active == 45  # (1800+900)//60
        assert row.problems_attempted == 3
        assert row.problems_correct == 1  # NULL(미채점)은 정답으로 세지 않는다
        assert row.socratic_turns == 2  # 계산 이벤트 제외
        assert row.concepts_practiced == ["MATH-II-01"]
        assert row.avg_focus_score == 0.7

    def test_unresolved_concept_falls_back_to_uuid_string(self) -> None:
        """개념 코드 미해석분은 UUID 문자열 폴백 — 조용히 누락하지 않는다."""
        rows = aggregate_daily_metrics(
            [SessionFact(user_id=_USER, started_at=_kst(2026, 8, 10), target_concept_id=_CONCEPT)],
            [],
            [],
            concept_codes={},
        )
        assert rows[0].concepts_practiced == [str(_CONCEPT)]

    def test_unfinished_session_yields_none_minutes_not_zero(self) -> None:
        """미종료 세션만 있으면 `minutes_active`는 None — 0으로 날조하면 '0분 학습'이 된다."""
        rows = aggregate_daily_metrics(
            [SessionFact(user_id=_USER, started_at=_kst(2026, 8, 10))], [], []
        )
        assert rows[0].minutes_active is None

    def test_duration_falls_back_to_ended_at(self) -> None:
        rows = aggregate_daily_metrics(
            [
                SessionFact(
                    user_id=_USER,
                    started_at=_kst(2026, 8, 10, 9),
                    ended_at=_kst(2026, 8, 10, 10),
                )
            ],
            [],
            [],
        )
        assert rows[0].minutes_active == 60

    def test_days_and_users_are_separated(self) -> None:
        """(user, date)별로 나뉜다 — 한 행으로 뭉치면 빨개진다."""
        rows = aggregate_daily_metrics(
            [
                SessionFact(user_id=_USER, started_at=_kst(2026, 8, 10), duration_seconds=600),
                SessionFact(user_id=_USER, started_at=_kst(2026, 8, 11), duration_seconds=600),
                SessionFact(user_id=_USER_B, started_at=_kst(2026, 8, 10), duration_seconds=600),
            ],
            [],
            [],
        )
        assert {(r.user_id, r.metric_date) for r in rows} == {
            (_USER, date(2026, 8, 10)),
            (_USER, date(2026, 8, 11)),
            (_USER_B, date(2026, 8, 10)),
        }

    def test_kst_early_morning_attributed_to_same_kst_day(self) -> None:
        """KST 08:00 학습이 전날로 밀리지 않는다(UTC 귀속 구현이면 2일치로 갈라져 빨개진다)."""
        rows = aggregate_daily_metrics(
            [
                SessionFact(user_id=_USER, started_at=_kst(2026, 8, 10, 8), duration_seconds=600),
                SessionFact(user_id=_USER, started_at=_kst(2026, 8, 10, 20), duration_seconds=600),
            ],
            [],
            [],
        )
        assert len(rows) == 1
        assert rows[0].metric_date == date(2026, 8, 10)
        assert rows[0].minutes_active == 20

    def test_deterministic_ordering(self) -> None:
        """같은 입력 → 같은 순서(멱등 upsert·재현성)."""
        facts = [
            SessionFact(user_id=_USER_B, started_at=_kst(2026, 8, 11), duration_seconds=60),
            SessionFact(user_id=_USER, started_at=_kst(2026, 8, 10), duration_seconds=60),
        ]
        first = [(r.user_id, r.metric_date) for r in aggregate_daily_metrics(facts, [], [])]
        second = [
            (r.user_id, r.metric_date)
            for r in aggregate_daily_metrics(list(reversed(facts)), [], [])
        ]
        assert first == second


# ──────────────────────────────────────────────────────────────────────────
# ② user_behavior_metrics
# ──────────────────────────────────────────────────────────────────────────
class TestAggregateUserBehaviorMetrics:
    def test_measured_metrics_only(self) -> None:
        rows = aggregate_user_behavior_metrics(
            [SessionFact(user_id=_USER, started_at=_kst(2026, 8, 10), duration_seconds=1200)],
            [
                AttemptFact(
                    user_id=_USER,
                    started_at=_kst(2026, 8, 10),
                    is_correct=True,
                    used_hint=True,
                    used_solution_view=False,
                ),
                AttemptFact(
                    user_id=_USER,
                    started_at=_kst(2026, 8, 10),
                    is_correct=False,
                    used_hint=False,
                    used_solution_view=False,
                ),
            ],
        )
        by_name = {r.metric_name: r.metric_value for r in rows}
        assert by_name == {
            BEHAVIOR_METRIC_SESSION_COUNT: 1.0,
            BEHAVIOR_METRIC_ACTIVE_MINUTES: 20.0,
            BEHAVIOR_METRIC_ACCURACY_RATE: 0.5,
            BEHAVIOR_METRIC_HINT_RELIANCE: 0.5,
            BEHAVIOR_METRIC_SOLUTION_VIEW: 0.0,
        }

    def test_no_inferred_metrics_produced(self) -> None:
        """churn_risk 등 *추론* 지표는 생산하지 않는다(모델 부재·날조 금지)."""
        rows = aggregate_user_behavior_metrics(
            [SessionFact(user_id=_USER, started_at=_kst(2026, 8, 10), duration_seconds=600)],
            [AttemptFact(user_id=_USER, started_at=_kst(2026, 8, 10), is_correct=True)],
        )
        assert all(r.metric_name.startswith("daily_") for r in rows)
        assert "churn_risk" not in {r.metric_name for r in rows}

    def test_rate_metrics_absent_without_attempts(self) -> None:
        """시도 0이면 비율 지표를 만들지 않는다 — 0.0은 '힌트 안 씀'이라는 거짓 신호."""
        names = {
            r.metric_name
            for r in aggregate_user_behavior_metrics(
                [SessionFact(user_id=_USER, started_at=_kst(2026, 8, 10), duration_seconds=600)],
                [],
            )
        }
        assert BEHAVIOR_METRIC_HINT_RELIANCE not in names
        assert BEHAVIOR_METRIC_ACCURACY_RATE not in names

    def test_measured_at_is_kst_midnight_in_utc(self) -> None:
        """`measured_at`은 KST 자정(UTC 15:00 전날) — 재집계가 같은 PK에 떨어져야 멱등."""
        rows = aggregate_user_behavior_metrics(
            [SessionFact(user_id=_USER, started_at=_kst(2026, 8, 10, 20), duration_seconds=600)],
            [],
        )
        assert rows[0].measured_at == datetime(2026, 8, 9, 15, 0, tzinfo=UTC)


# ──────────────────────────────────────────────────────────────────────────
# ③ problem_solve_time_distribution — k-익명 하한
# ──────────────────────────────────────────────────────────────────────────
def _attempt(seconds: int) -> AttemptFact:
    return AttemptFact(
        user_id=uuid.uuid4(),
        started_at=_kst(2026, 8, 10),
        problem_id=_PROBLEM,
        persona=Persona.A_일반고고3,
        duration_seconds=seconds,
    )


class TestAggregateSolveTimeDistribution:
    def test_below_k_anonymity_threshold_is_dropped(self) -> None:
        """표본 4개(<5)는 적재하지 않는다 — 소표본 분위수는 개인 풀이 시간 노출."""
        assert aggregate_solve_time_distribution([_attempt(s) for s in (10, 20, 30, 40)]) == []

    def test_at_threshold_is_kept(self) -> None:
        """표본 5개면 적재 — 위 케이스와 값이 갈려야 변별력이 있다."""
        rows = aggregate_solve_time_distribution([_attempt(s) for s in (10, 20, 30, 40, 50)])
        assert len(rows) == 1
        row = rows[0]
        assert row.problem_id == _PROBLEM
        assert row.sample_size == 5
        assert (row.p10_seconds, row.p50_seconds, row.p90_seconds) == (14, 30, 46)

    def test_threshold_is_injectable(self) -> None:
        assert len(aggregate_solve_time_distribution([_attempt(10)], min_sample=1)) == 1

    def test_rows_without_duration_or_persona_are_excluded(self) -> None:
        """duration/persona/problem_id NULL은 분포 표본이 될 수 없다."""
        base = [_attempt(s) for s in (10, 20, 30, 40, 50)]
        noise = [
            AttemptFact(
                user_id=uuid.uuid4(),
                started_at=_kst(2026, 8, 10),
                problem_id=_PROBLEM,
                persona=Persona.A_일반고고3,
                duration_seconds=None,
            ),
            AttemptFact(
                user_id=uuid.uuid4(),
                started_at=_kst(2026, 8, 10),
                problem_id=None,
                persona=Persona.A_일반고고3,
                duration_seconds=99,
            ),
            AttemptFact(
                user_id=uuid.uuid4(),
                started_at=_kst(2026, 8, 10),
                problem_id=_PROBLEM,
                persona=None,
                duration_seconds=99,
            ),
        ]
        rows = aggregate_solve_time_distribution(base + noise)
        assert len(rows) == 1
        assert rows[0].sample_size == 5  # 잡음 3건이 섞이면 8이 되어 빨개진다

    def test_personas_are_separate_buckets(self) -> None:
        a = [_attempt(s) for s in (10, 20, 30, 40, 50)]
        b = [
            AttemptFact(
                user_id=uuid.uuid4(),
                started_at=_kst(2026, 8, 10),
                problem_id=_PROBLEM,
                persona=Persona.C_검정고시N수,
                duration_seconds=s,
            )
            for s in (100, 200, 300, 400, 500)
        ]
        rows = aggregate_solve_time_distribution(a + b)
        assert {r.persona for r in rows} == {Persona.A_일반고고3, Persona.C_검정고시N수}


# ──────────────────────────────────────────────────────────────────────────
# CLI 창 계산 (순수)
# ──────────────────────────────────────────────────────────────────────────
class TestResolveWindow:
    _TODAY = date(2026, 8, 10)

    def test_default_two_day_window(self) -> None:
        """기본 창 = 어제·오늘(지연 도착 흡수·모듈 docstring §집계 주기)."""
        assert resolve_window(since=None, until=None, days=2, today=self._TODAY) == (
            date(2026, 8, 9),
            date(2026, 8, 10),
        )

    def test_explicit_range(self) -> None:
        assert resolve_window(
            since=date(2026, 8, 1), until=date(2026, 8, 5), days=2, today=self._TODAY
        ) == (date(2026, 8, 1), date(2026, 8, 5))

    def test_since_only_extends_to_today(self) -> None:
        assert resolve_window(since=date(2026, 8, 1), until=None, days=2, today=self._TODAY) == (
            date(2026, 8, 1),
            self._TODAY,
        )

    def test_reversed_range_raises(self) -> None:
        with pytest.raises(ValueError, match="늦다"):
            resolve_window(
                since=date(2026, 8, 11), until=date(2026, 8, 1), days=2, today=self._TODAY
            )

    def test_zero_days_raises(self) -> None:
        with pytest.raises(ValueError, match="1 이상"):
            resolve_window(since=None, until=None, days=0, today=self._TODAY)


# ──────────────────────────────────────────────────────────────────────────
# DB 어댑터 배선 (FakeSession — hermetic. 실 PG 거동은 통합테스트 영역)
#
# 여기서 보는 것은 *배선*이다: run_daily_rollup이 ① 창을 읽고 ② 순수 집계를 태우고
# ③ 세 테이블에 **올바른 충돌키(index_elements)로** upsert를 발행하는가. 충돌키가 PK와
# 어긋나면 멱등이 깨져 재실행마다 행이 늘어나는데, 그 오배선은 실 PG 없이도 여기서 잡힌다
# (`privacy/test_retention.py`의 FakeSession 선례).
# ──────────────────────────────────────────────────────────────────────────
from typing import Any, cast  # noqa: E402

from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

from whymath_backend.l2.learning_metrics_rollup import run_daily_rollup  # noqa: E402


class _Row:
    """`session.execute(...)` 결과 행 흉내 — 속성 접근만 지원."""

    def __init__(self, **kwargs: Any) -> None:
        self.__dict__.update(kwargs)


class _FakeSession:
    """SELECT는 미리 정한 행을, INSERT/DELETE는 캡처만 하는 세션 대역."""

    def __init__(self, selects: list[list[_Row]]) -> None:
        self._selects = list(selects)
        self.executed: list[Any] = []

    async def execute(self, stmt: Any) -> Any:
        self.executed.append(stmt)
        if stmt.__visit_name__ == "select":
            return self._selects.pop(0) if self._selects else []
        return _Row(rowcount=0)


def _fake_session_with_activity() -> _FakeSession:
    """세션 1건·시도 2건(문항/페르소나 있음)·이벤트 1건 + 개념 조회 0건."""
    return _FakeSession(
        [
            [  # _fetch_sessions
                _Row(
                    user_id=_USER,
                    started_at=_kst(2026, 8, 10, 9),
                    ended_at=_kst(2026, 8, 10, 10),
                    duration_seconds=3600,
                    focus_score=0.9,
                    target_concept_id=None,
                )
            ],
            [  # _fetch_attempts
                _Row(
                    user_id=_USER,
                    started_at=_kst(2026, 8, 10, 9, 5),
                    problem_id=_PROBLEM,
                    duration_seconds=120,
                    is_correct=True,
                    used_hint=False,
                    used_solution_view=False,
                    persona_primary=Persona.A_일반고고3,
                ),
                _Row(
                    user_id=_USER,
                    started_at=_kst(2026, 8, 10, 9, 8),
                    problem_id=_PROBLEM,
                    duration_seconds=240,
                    is_correct=False,
                    used_hint=True,
                    used_solution_view=False,
                    persona_primary=Persona.A_일반고고3,
                ),
            ],
            [  # _fetch_events
                _Row(
                    user_id=_USER,
                    event_at=_kst(2026, 8, 10, 9, 6),
                    event_type=EventType.힌트요청,
                )
            ],
        ]
    )


def _run(session: _FakeSession, **kwargs: Any) -> Any:
    import asyncio

    return asyncio.run(
        run_daily_rollup(
            cast("AsyncSession", session),
            start_date=date(2026, 8, 10),
            end_date=date(2026, 8, 10),
            min_solve_time_sample=1,
            **kwargs,
        )
    )


class TestRunDailyRollupWiring:
    def test_report_counts_scanned_and_upserted_rows(self) -> None:
        report = _run(_fake_session_with_activity())
        payload = report.to_json()
        assert payload["scanned"] == {
            "learning_session": 1,
            "problem_attempt": 2,
            "attempt_event": 1,
        }
        assert payload["upserted"]["daily_learning_metrics"] == 1
        assert payload["upserted"]["user_behavior_metrics"] == 5
        assert payload["upserted"]["problem_solve_time_distribution"] == 1

    def test_report_carries_no_pii(self) -> None:
        """리포트는 카운트·좌석명만 — 사용자 식별자가 새면 로그로 흘러간다."""
        payload = _run(_fake_session_with_activity()).to_json()
        assert str(_USER) not in str(payload)

    def test_dry_run_issues_no_writes(self) -> None:
        """`--dry-run`은 SELECT만 — INSERT/DELETE가 하나라도 있으면 빨개진다."""
        session = _fake_session_with_activity()
        _run(session, dry_run=True)
        kinds = {stmt.__visit_name__ for stmt in session.executed}
        assert kinds == {"select"}, kinds

    def test_upsert_conflict_targets_match_primary_keys(self) -> None:
        """충돌키가 각 테이블 PK와 일치해야 재실행이 멱등하다(어긋나면 행이 계속 늘어난다)."""
        session = _fake_session_with_activity()
        _run(session)
        inserts = [s for s in session.executed if s.__visit_name__ == "insert"]
        targets = {
            s.table.name: {c.name for c in s._post_values_clause.inferred_target_elements}
            for s in inserts
        }
        assert targets["daily_learning_metrics"] == {"user_id", "metric_date"}
        assert targets["user_behavior_metrics"] == {"user_id", "metric_name", "measured_at"}
        assert targets["problem_solve_time_distribution"] == {
            "problem_id",
            "persona",
            "measured_at",
        }

    def test_no_activity_issues_no_writes(self) -> None:
        """빈 창 → 쓰기 0(빈 행 양산·불필요 트래픽 금지)."""
        session = _FakeSession([[], [], []])
        report = _run(session)
        assert report.daily_rows == 0
        assert {s.__visit_name__ for s in session.executed} == {"select"}

    def test_prune_scans_whole_window_not_only_result_dates(self) -> None:
        """정리 범위는 *창 전체*다 — 결과에 없는 날짜의 스테일 행도 조회 대상에 들어와야 한다.

        변별력: 정리 범위를 '재집계 결과에 등장한 날짜'로 좁히면(구 구현) 활동이 통째로 사라진
        날짜가 범위 밖으로 빠져 스테일 행이 영영 남는다. 이 케이스는 DELETE 대상을 찾는 SELECT의
        *날짜 조건*을 검사해 그 회귀를 잡는다.
        """
        session = _fake_session_with_activity()
        import asyncio

        asyncio.run(
            run_daily_rollup(
                cast("AsyncSession", session),
                start_date=date(2026, 8, 1),
                end_date=date(2026, 8, 31),  # 결과는 8/10 하루뿐인 넓은 창
                min_solve_time_sample=1,
            )
        )
        # 정리 대상 조회 SELECT(daily 테이블 대상)의 WHERE에 창 양끝이 실려야 한다.
        prune_selects = [
            s
            for s in session.executed
            if s.__visit_name__ == "select"
            and "daily_learning_metrics" in str(s.get_final_froms()[0])
        ]
        assert prune_selects, "스테일 정리 조회가 발행되지 않았다"
        where = str(prune_selects[-1].whereclause.compile(compile_kwargs={"literal_binds": True}))
        assert "2026-08-01" in where and "2026-08-31" in where, where
