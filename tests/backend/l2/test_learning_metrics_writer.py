"""L2 학습시간·행동 집계 writer(COLLAB-03) — *순수* 집계 + 조율 단위테스트(hermetic).

`compute_*` 3종(DB 무관)을 전수 검증하고, `run_daily_rollup`의 조율(fetch→compute→upsert→
commit 순서·1회 commit)을 `_QueueSession`(fake, `test_mastery_tracking.py` 패턴 답습)으로
검증한다. 실 PG SELECT/UPSERT의 SQL 정확성은 통합테스트
(`test_learning_metrics_writer_integration.py`)가 검증한다.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from typing import Any, cast

from sqlalchemy.ext.asyncio import AsyncSession

from whymath_backend.l2.learning_metrics_writer import (
    BEHAVIOR_METRIC_DAYS_ACTIVE_7D,
    BEHAVIOR_METRIC_SESSION_COUNT_7D,
    DailyRollupReport,
    _AttemptActivity,
    _DialogueActivity,
    _percentile,
    _SessionActivity,
    compute_daily_learning_metrics,
    compute_problem_solve_time_distribution,
    compute_user_behavior_metrics,
    run_daily_rollup,
)
from whymath_backend.schema.enums import Persona

_D = date(2026, 8, 1)
_U1, _U2, _U3 = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
_P1, _P2 = uuid.uuid4(), uuid.uuid4()


class TestPercentile:
    """선형보간(numpy 'linear'/Excel PERCENTILE.INC와 동일 정의) — 손계산 대조."""

    def test_single_value(self) -> None:
        assert _percentile([42], 0.5) == 42
        assert _percentile([42], 0.1) == 42
        assert _percentile([42], 0.9) == 42

    def test_known_linear_interpolation(self) -> None:
        # [10,20,30,40,50] — p50=rank2.0(정확히 30), p10=rank0.4(10+10*0.4=14),
        # p90=rank3.6(40+10*0.6=46)
        values = [10, 20, 30, 40, 50]
        assert _percentile(values, 0.50) == 30
        assert _percentile(values, 0.10) == 14
        assert _percentile(values, 0.90) == 46

    def test_two_values_midpoint(self) -> None:
        assert _percentile([10, 20], 0.5) == 15

    def test_monotonic_in_pct(self) -> None:
        values = [5, 12, 19, 33, 61, 90]
        p10 = _percentile(values, 0.10)
        p50 = _percentile(values, 0.50)
        p90 = _percentile(values, 0.90)
        assert p10 <= p50 <= p90


class TestComputeDailyLearningMetrics:
    def test_empty_inputs_yield_no_records(self) -> None:
        assert compute_daily_learning_metrics(_D, [], [], [], {}) == []

    def test_minutes_active_floors_to_whole_minutes(self) -> None:
        # 125초 세션 하나 → 2분(정수 나눗셈 floor)
        sessions = [_SessionActivity(user_id=_U1, duration_seconds=125, focus_score=None)]
        records = compute_daily_learning_metrics(_D, sessions, [], [], {})
        assert len(records) == 1
        assert records[0].minutes_active == 2

    def test_multiple_sessions_sum_duration(self) -> None:
        sessions = [
            _SessionActivity(user_id=_U1, duration_seconds=600, focus_score=None),
            _SessionActivity(user_id=_U1, duration_seconds=300, focus_score=None),
        ]
        records = compute_daily_learning_metrics(_D, sessions, [], [], {})
        assert records[0].minutes_active == 15  # 900초 = 15분

    def test_minutes_active_none_when_all_durations_null(self) -> None:
        """활동은 있으나 duration_seconds가 전부 NULL → 정직하게 None(0 아님)."""
        sessions = [_SessionActivity(user_id=_U1, duration_seconds=None, focus_score=None)]
        records = compute_daily_learning_metrics(_D, sessions, [], [], {})
        assert records[0].minutes_active is None

    def test_avg_focus_score_averages_non_null_only(self) -> None:
        sessions = [
            _SessionActivity(user_id=_U1, duration_seconds=None, focus_score=0.8),
            _SessionActivity(user_id=_U1, duration_seconds=None, focus_score=None),
            _SessionActivity(user_id=_U1, duration_seconds=None, focus_score=0.6),
        ]
        records = compute_daily_learning_metrics(_D, sessions, [], [], {})
        assert records[0].avg_focus_score == 0.7  # (0.8+0.6)/2, NULL 제외

    def test_avg_focus_score_none_when_no_scores(self) -> None:
        sessions = [_SessionActivity(user_id=_U1, duration_seconds=100, focus_score=None)]
        records = compute_daily_learning_metrics(_D, sessions, [], [], {})
        assert records[0].avg_focus_score is None

    def test_problems_attempted_counts_all_correct_counts_true_only(self) -> None:
        attempts = [
            _AttemptActivity(user_id=_U1, is_correct=True),
            _AttemptActivity(user_id=_U1, is_correct=False),
            _AttemptActivity(user_id=_U1, is_correct=None),  # 미채점 — attempted엔 포함
        ]
        records = compute_daily_learning_metrics(_D, [], attempts, [], {})
        assert records[0].problems_attempted == 3
        assert records[0].problems_correct == 1

    def test_socratic_turns_sums_skips_null(self) -> None:
        dialogues = [
            _DialogueActivity(user_id=_U1, total_turns=4),
            _DialogueActivity(user_id=_U1, total_turns=None),
            _DialogueActivity(user_id=_U1, total_turns=2),
        ]
        records = compute_daily_learning_metrics(_D, [], [], dialogues, {})
        assert records[0].socratic_turns == 6

    def test_concepts_practiced_dedup_and_sorted(self) -> None:
        records = compute_daily_learning_metrics(_D, [], [], [], {_U1: ["B-01", "A-01", "A-01"]})
        assert records[0].concepts_practiced == ["A-01", "B-01"]

    def test_concepts_practiced_default_empty_not_none(self) -> None:
        attempts = [_AttemptActivity(user_id=_U1, is_correct=True)]
        records = compute_daily_learning_metrics(_D, [], attempts, [], {})
        assert records[0].concepts_practiced == []  # NOT NULL TEXT[] 정합(None 아님)

    def test_user_present_via_dialogue_only_still_included(self) -> None:
        """세션·시도 없이 대화만 있어도 그날 활동 행이 생긴다(활동 = 셋 중 하나라도)."""
        dialogues = [_DialogueActivity(user_id=_U1, total_turns=3)]
        records = compute_daily_learning_metrics(_D, [], [], dialogues, {})
        assert len(records) == 1
        assert records[0].user_id == _U1
        assert records[0].minutes_active is None
        assert records[0].problems_attempted is None
        assert records[0].socratic_turns == 3

    def test_user_present_via_concepts_only_still_included(self) -> None:
        records = compute_daily_learning_metrics(_D, [], [], [], {_U1: ["C-01"]})
        assert len(records) == 1
        assert records[0].concepts_practiced == ["C-01"]

    def test_multi_user_independent_aggregation(self) -> None:
        sessions = [_SessionActivity(user_id=_U1, duration_seconds=600, focus_score=None)]
        attempts = [_AttemptActivity(user_id=_U2, is_correct=True)]
        records = compute_daily_learning_metrics(_D, sessions, attempts, [], {})
        by_user = {r.user_id: r for r in records}
        assert len(records) == 2
        assert by_user[_U1].minutes_active == 10
        assert by_user[_U1].problems_attempted is None
        assert by_user[_U2].problems_attempted == 1
        assert by_user[_U2].minutes_active is None

    def test_metric_date_stamped_on_every_record(self) -> None:
        sessions = [_SessionActivity(user_id=_U1, duration_seconds=1, focus_score=None)]
        records = compute_daily_learning_metrics(_D, sessions, [], [], {})
        assert records[0].metric_date == _D

    def test_deterministic_ordering_by_user_id_str(self) -> None:
        attempts = [
            _AttemptActivity(user_id=_U2, is_correct=True),
            _AttemptActivity(user_id=_U1, is_correct=True),
        ]
        records = compute_daily_learning_metrics(_D, [], attempts, [], {})
        assert [r.user_id for r in records] == sorted([_U1, _U2], key=str)


class TestComputeProblemSolveTimeDistribution:
    _T = datetime(2026, 8, 1, tzinfo=UTC)

    def test_empty_rows_yield_no_records(self) -> None:
        assert compute_problem_solve_time_distribution(self._T, []) == []

    def test_groups_by_problem_and_persona(self) -> None:
        rows = [
            (_P1, Persona.A_일반고고3, 100),
            (_P1, Persona.A_일반고고3, 200),
            (_P1, Persona.C_검정고시N수, 50),
            (_P2, Persona.A_일반고고3, 999),
        ]
        records = compute_problem_solve_time_distribution(self._T, rows)
        keys = {(r.problem_id, r.persona) for r in records}
        assert keys == {
            (_P1, Persona.A_일반고고3),
            (_P1, Persona.C_검정고시N수),
            (_P2, Persona.A_일반고고3),
        }

    def test_percentiles_and_sample_size(self) -> None:
        rows = [(_P1, Persona.A_일반고고3, d) for d in (10, 20, 30, 40, 50)]
        records = compute_problem_solve_time_distribution(self._T, rows)
        assert len(records) == 1
        rec = records[0]
        assert rec.sample_size == 5
        assert rec.p50_seconds == 30
        assert rec.p10_seconds == 14
        assert rec.p90_seconds == 46

    def test_measured_at_stamped(self) -> None:
        records = compute_problem_solve_time_distribution(self._T, [(_P1, Persona.A_일반고고3, 5)])
        assert records[0].measured_at == self._T

    def test_deterministic_ordering(self) -> None:
        rows = [
            (_P2, Persona.A_일반고고3, 1),
            (_P1, Persona.C_검정고시N수, 1),
            (_P1, Persona.A_일반고고3, 1),
        ]
        records = compute_problem_solve_time_distribution(self._T, rows)
        keys = [(str(r.problem_id), r.persona.value) for r in records]
        assert keys == sorted(keys)


class TestComputeUserBehaviorMetrics:
    _T = datetime(2026, 8, 1, tzinfo=UTC)

    def test_empty_yields_no_records(self) -> None:
        assert compute_user_behavior_metrics(self._T, []) == []

    def test_session_count_and_days_active(self) -> None:
        starts = [
            (_U1, datetime(2026, 7, 30, tzinfo=UTC)),
            (_U1, datetime(2026, 7, 30, 12, tzinfo=UTC)),  # 같은 날 2세션
            (_U1, datetime(2026, 8, 1, tzinfo=UTC)),
        ]
        records = compute_user_behavior_metrics(self._T, starts)
        by_name = {r.metric_name: r for r in records}
        assert by_name[BEHAVIOR_METRIC_SESSION_COUNT_7D].metric_value == 3.0
        assert by_name[BEHAVIOR_METRIC_DAYS_ACTIVE_7D].metric_value == 2.0  # distinct 2일

    def test_two_metric_rows_per_active_user(self) -> None:
        starts = [(_U1, self._T), (_U2, self._T)]
        records = compute_user_behavior_metrics(self._T, starts)
        assert len(records) == 4  # 사용자 2명 × 지표 2종
        assert {r.metric_name for r in records} == {
            BEHAVIOR_METRIC_SESSION_COUNT_7D,
            BEHAVIOR_METRIC_DAYS_ACTIVE_7D,
        }

    def test_measured_at_shared_across_records(self) -> None:
        records = compute_user_behavior_metrics(self._T, [(_U1, self._T)])
        assert all(r.measured_at == self._T for r in records)


# ──────────────────────────────────────────────────────────────────────────
# run_daily_rollup 조율 — _QueueSession(fake, test_mastery_tracking.py 패턴)
# ──────────────────────────────────────────────────────────────────────────
class _AllResult:
    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def all(self) -> list[Any]:
        return list(self._rows)


class _QueueSession:
    """execute 호출마다 큐잉된 rows를 순서대로 반환 — stmt 자체는 기록만(무시).

    fetch 6회(session·attempt·dialogue·concepts·solve_time·recent_sessions) + upsert 최대
    3회(레코드가 있을 때만 실행)를 시뮬한다. queued 리스트가 fetch 결과다 — upsert는
    반환값을 안 보므로 채울 필요 없다(호출 자체만 `executed_count`로 셈).
    """

    def __init__(self, fetch_results: list[list[Any]]) -> None:
        self._fetch_results = list(fetch_results)
        self._i = 0
        self.executed_count = 0
        self.commits = 0

    async def execute(self, _stmt: Any) -> _AllResult:
        self.executed_count += 1
        if self._i < len(self._fetch_results):
            rows = self._fetch_results[self._i]
            self._i += 1
        else:
            rows = []  # upsert 호출(반환 미사용) — 빈 결과로 충분
        return _AllResult(rows)

    async def commit(self) -> None:
        self.commits += 1


class TestRunDailyRollup:
    async def test_empty_day_no_upserts_but_commits_once(self) -> None:
        """활동이 하나도 없는 날 — fetch 4회(concepts 포함) + solve_time 1회 + recent 1회 =
        6회 execute, upsert는 records=[]라 execute 0회, commit은 그래도 1회(원자성 유지)."""
        fake = _QueueSession([[], [], [], [], [], []])
        report = await run_daily_rollup(cast(AsyncSession, fake), _D)
        assert report == DailyRollupReport(
            metric_date=_D,
            daily_learning_metrics_rows=0,
            problem_solve_time_distribution_rows=0,
            user_behavior_metrics_rows=0,
        )
        assert fake.executed_count == 6  # fetch만(4 daily-source + solve_time + recent)
        assert fake.commits == 1

    async def test_full_day_upserts_all_three_and_commits_once(self) -> None:
        """세 테이블 모두 레코드가 생기는 날 — fetch 6회 + upsert 3회 = execute 9회·commit 1회."""
        session_rows = [(_U1, 600, None)]  # (user_id, duration_seconds, focus_score)
        attempt_rows = [(_U1, True)]  # (user_id, is_correct)
        dialogue_rows = [(_U1, 4)]  # (user_id, total_turns)
        concept_rows = [(_U1, "A-01")]  # (user_id, code)
        solve_time_rows = [(_P1, Persona.A_일반고고3, 30)]  # (problem_id, persona, duration)
        recent_session_rows = [(_U1, datetime(2026, 8, 1, tzinfo=UTC))]  # (user_id, started_at)

        # 실행 순서(run_daily_rollup): fetch×4 → upsert(daily) → fetch(solve_time) →
        # upsert(solve_time) → fetch(recent_sessions) → upsert(behavior). upsert 호출은
        # 반환값을 안 쓰므로 그 자리는 더미([])로 채운다(자리 유지 목적 — 실제로 안 읽힘).
        fake = _QueueSession(
            [
                session_rows,
                attempt_rows,
                dialogue_rows,
                concept_rows,
                [],  # upsert(daily_learning_metrics) — 반환 미사용 더미
                solve_time_rows,
                [],  # upsert(problem_solve_time_distribution) — 반환 미사용 더미
                recent_session_rows,
                [],  # upsert(user_behavior_metrics) — 반환 미사용 더미
            ]
        )
        report = await run_daily_rollup(cast(AsyncSession, fake), _D)
        assert report.daily_learning_metrics_rows == 1
        assert report.problem_solve_time_distribution_rows == 1
        assert report.user_behavior_metrics_rows == 2  # 지표 2종 × 사용자 1명
        assert fake.executed_count == 9  # fetch 6 + upsert 3
        assert fake.commits == 1

    async def test_report_metric_date_matches_target(self) -> None:
        fake = _QueueSession([[], [], [], [], [], []])
        report = await run_daily_rollup(cast(AsyncSession, fake), _D)
        assert report.metric_date == _D
