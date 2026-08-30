"""EOS-48 — 시간 귀속 계약(effective_event_moment) + active/idle 병행 지표 (hermetic).

32_learning_history §7의 두 갭을 계약으로 동결한다:

  ① **event_time/ingested_at 분리** — 오프라인 태블릿 sync에서 "어떤 값이 어느 지표에
    쓰이는가": 귀속은 발생(event_time) 우선, 시계 왜곡(발생>수신)은 수신 폴백, 미신고는
    수신(기존 동작). 정본 = `l2.learning_metrics_rollup.effective_event_moment`(순수).
    **소비 배선 완료(PR #903 P2 현행화)**: `_fetch_events`가 event_time을 SELECT하고 창
    필터를 SQL 등가식(`_effective_event_at_expr`)으로 걸며, `aggregate_daily_metrics`
    소크라테스 귀속이 `EventFact.effective_at()`을 경유한다. writer 부재로 event_time이
    전행 NULL인 현재 데이터에서는 기존 산출과 비트동일(회귀 단언 동봉) — 유보 사유였던
    "귀속 변화량"이 정의상 0이라 배선이 no-op 안전하다.

  ② **active/idle 병행 지표** — 기존 `daily_active_minutes`(경과 elapsed 기반)는 의미 불변
    (재정의 금지·회귀 단언 포함). 신규 `daily_measured_active_minutes`는 실측 세션만 합산
    ("측정된 것만 적재" — 미측정을 0으로 섞지 않음), `daily_active_measured_ratio`는 계측이
    실제 작동한 비율을 상시 보고한다("작동한 비율" 원칙 — 좌석 존재≠계측 작동).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from whymath_backend.l2.learning_metrics_rollup import (
    BEHAVIOR_METRIC_ACTIVE_MEASURED_RATIO,
    BEHAVIOR_METRIC_ACTIVE_MINUTES,
    BEHAVIOR_METRIC_MEASURED_ACTIVE_MINUTES,
    EventFact,
    SessionFact,
    _effective_event_at_expr,
    aggregate_daily_metrics,
    aggregate_user_behavior_metrics,
    effective_event_moment,
    metric_date_of,
)
from whymath_backend.schema.enums import EventType

_UID = uuid.uuid4()
_KST = ZoneInfo("Asia/Seoul")


def _kst(*args: int) -> datetime:
    return datetime(*args, tzinfo=_KST)  # type: ignore[arg-type]


# ── ① 귀속 계약 — effective_event_moment ─────────────────────────────────────


class TestEffectiveEventMoment:
    def test_late_arrival_attributes_to_occurrence(self) -> None:
        """지연 도착(event_time < ingested_at) — 오프라인 태블릿이 어제 발생분을 오늘 sync해도
        귀속은 *발생* 시각이다(수신 시각을 사건 시각으로 착각 금지 — §7)."""
        occurred = datetime(2026, 8, 30, 21, 0, tzinfo=UTC)
        ingested = datetime(2026, 8, 31, 9, 0, tzinfo=UTC)
        assert effective_event_moment(occurred, ingested) == occurred

    def test_late_arrival_lands_on_occurrence_date(self) -> None:
        """지표 날짜 귀속(metric_date_of 합성) — 어제 발생/오늘 수신 → *어제* 날짜."""
        occurred = _kst(2026, 8, 30, 23, 30)
        ingested = _kst(2026, 8, 31, 10, 0)
        moment = effective_event_moment(occurred, ingested)
        assert metric_date_of(moment) == metric_date_of(occurred)
        assert metric_date_of(moment) != metric_date_of(ingested)

    def test_clock_skew_future_occurrence_falls_back_to_ingest(self) -> None:
        """시계 왜곡(event_time > ingested_at — 발생이 수신보다 미래일 수 없다) → 서버 수신
        시각 폴백(미래 신고를 그대로 귀속하면 지표가 미래로 샌다)."""
        skewed = datetime(2026, 9, 15, 0, 0, tzinfo=UTC)  # 클라 시계가 미래로 왜곡
        ingested = datetime(2026, 8, 31, 9, 0, tzinfo=UTC)
        assert effective_event_moment(skewed, ingested) == ingested

    def test_unreported_falls_back_to_ingest(self) -> None:
        """미신고(event_time=None) → 수신 시각(기존 동작 — event_at 실측 의미와 동일)."""
        ingested = datetime(2026, 8, 31, 9, 0, tzinfo=UTC)
        assert effective_event_moment(None, ingested) == ingested

    def test_equal_times_use_occurrence(self) -> None:
        """발생==수신(온라인 즉시 제출) → 발생 사용(경계 포함 — ≤ 계약)."""
        moment = datetime(2026, 8, 31, 9, 0, tzinfo=UTC)
        assert effective_event_moment(moment, moment) == moment


# ── ①-b 소비 배선(PR #903 P2) — 롤업이 계약을 실제 경유한다 ─────────────────────


class TestRollupConsumesEffectiveMoment:
    """`effective_event_moment`가 테스트 전용 계약이 아니라 프로덕션 귀속 경로임을 동결.

    writer 부재로 event_time이 전행 NULL인 현재 데이터에서는 기존 산출과 **비트동일**이고
    (coalesce/least 축약 — 분기 1), event_time이 채워지는 순간 지연 도착이 발생일 롤업에
    잡힌다. SQL 창 필터(`_effective_event_at_expr`)와 Python 귀속(`EventFact.effective_at`)의
    분기 동치도 함께 동결한다(어긋나면 창 밖 누수·이중 계상).
    """

    @staticmethod
    def _socratic(event_at: datetime, event_time: datetime | None) -> EventFact:
        return EventFact(
            user_id=_UID, event_at=event_at, event_type=EventType.힌트요청, event_time=event_time
        )

    def test_null_event_time_bit_identical_to_legacy(self) -> None:
        """회귀 — event_time 전행 NULL 픽스처에서 산출이 레거시(EventFact 3필드)와 비트동일."""
        legacy = [
            EventFact(user_id=_UID, event_at=_kst(2026, 8, 30, 10, 0), event_type=EventType.막힘),
            EventFact(
                user_id=_UID, event_at=_kst(2026, 8, 30, 11, 0), event_type=EventType.힌트요청
            ),
        ]
        with_null = [
            EventFact(
                user_id=_UID,
                event_at=_kst(2026, 8, 30, 10, 0),
                event_type=EventType.막힘,
                event_time=None,
            ),
            EventFact(
                user_id=_UID,
                event_at=_kst(2026, 8, 30, 11, 0),
                event_type=EventType.힌트요청,
                event_time=None,
            ),
        ]
        assert aggregate_daily_metrics([], [], legacy) == aggregate_daily_metrics([], [], with_null)

    def test_late_arrival_attributed_to_occurrence_date_rollup(self) -> None:
        """지연 도착(어제 발생/오늘 수신) — 어제 날짜 행으로 귀속된다(어제 재실행이 잡는 값)."""
        rows = aggregate_daily_metrics(
            [],
            [],
            [self._socratic(_kst(2026, 8, 31, 9, 0), _kst(2026, 8, 30, 23, 30))],
        )
        assert [r.metric_date for r in rows] == [metric_date_of(_kst(2026, 8, 30, 23, 30))]
        assert rows[0].socratic_turns == 1

    def test_clock_skew_attributed_to_ingest_date_rollup(self) -> None:
        """시계 왜곡(발생>수신) — 수신일 귀속(미래로 새지 않음)."""
        rows = aggregate_daily_metrics(
            [],
            [],
            [self._socratic(_kst(2026, 8, 31, 9, 0), _kst(2026, 9, 15, 0, 0))],
        )
        assert [r.metric_date for r in rows] == [metric_date_of(_kst(2026, 8, 31, 9, 0))]

    def test_sql_window_expr_matches_python_contract(self) -> None:
        """`_fetch_events` 창 필터의 SQL 등가식 — LEAST(COALESCE(event_time, event_at),
        event_at)로 컴파일된다(Python 분기 1:1 — 창 필터/귀속 불일치 시 누수·이중 계상)."""
        from sqlalchemy.dialects import postgresql

        sql = str(_effective_event_at_expr().compile(dialect=postgresql.dialect()))
        assert sql == (
            "least(coalesce(attempt_event.event_time, attempt_event.event_at), "
            "attempt_event.event_at)"
        )


# ── ② active/idle 병행 지표 — 측정된 것만·작동 비율·기존 지표 불변 ────────────────


def _session(
    *, duration: int | None = None, active: int | None = None, idle: int | None = None
) -> SessionFact:
    return SessionFact(
        user_id=_UID,
        started_at=_kst(2026, 8, 30, 10, 0),
        duration_seconds=duration,
        active_seconds=active,
        idle_seconds=idle,
    )


class TestMeasuredActiveMetrics:
    def test_measured_only_sum_and_ratio(self) -> None:
        """실측 세션(2/3)만 measured 합산 — 미측정 세션은 0으로 섞이지 않는다. ratio=2/3."""
        rows = aggregate_user_behavior_metrics(
            [
                _session(duration=3600, active=1200, idle=600),
                _session(duration=1800, active=600),
                _session(duration=1800),  # 레거시/미계측 — active 미측정
            ],
            [],
        )
        by_name = {r.metric_name: r.metric_value for r in rows}
        assert by_name[BEHAVIOR_METRIC_MEASURED_ACTIVE_MINUTES] == 30.0  # (1200+600)//60
        assert by_name[BEHAVIOR_METRIC_ACTIVE_MEASURED_RATIO] == round(2 / 3, 4)

    def test_no_measurement_emits_no_measured_minutes(self) -> None:
        """전 세션 미측정 → measured_active_minutes 행 *없음*(0 날조 금지) — ratio만 0.0
        (계측 미작동을 리포트가 말한다: 좌석 존재≠작동)."""
        rows = aggregate_user_behavior_metrics([_session(duration=3600)], [])
        by_name = {r.metric_name: r.metric_value for r in rows}
        assert BEHAVIOR_METRIC_MEASURED_ACTIVE_MINUTES not in by_name
        assert by_name[BEHAVIOR_METRIC_ACTIVE_MEASURED_RATIO] == 0.0

    def test_existing_elapsed_metric_meaning_unchanged(self) -> None:
        """회귀 — 기존 daily_active_minutes는 *경과(elapsed)* 기반 의미 불변: 실측 active가
        있어도 값은 여전히 duration에서 나온다(재정의 금지 — 병행일 뿐)."""
        rows = aggregate_user_behavior_metrics(
            [_session(duration=3600, active=600)],  # 경과 60분·실측 10분
            [],
        )
        by_name = {r.metric_name: r.metric_value for r in rows}
        assert by_name[BEHAVIOR_METRIC_ACTIVE_MINUTES] == 60.0  # 경과 기반 그대로
        assert by_name[BEHAVIOR_METRIC_MEASURED_ACTIVE_MINUTES] == 10.0  # 실측은 병행 신규

    def test_elapsed_derivation_not_promoted_to_active(self) -> None:
        """ended_at-started_at(경과)을 active로 승격하는 백필 금지 — SessionFact에 active
        미측정이면 measured에 절대 반영되지 않는다(§7·EOS-45 판정 동형)."""
        fact = SessionFact(
            user_id=_UID,
            started_at=_kst(2026, 8, 30, 10, 0),
            ended_at=_kst(2026, 8, 30, 11, 0),  # 경과 60분 파생 가능 상태
        )
        assert fact.effective_seconds() == 3600  # 경과 파생은 기존 동작 유지
        rows = aggregate_user_behavior_metrics([fact], [])
        by_name = {r.metric_name: r.metric_value for r in rows}
        assert by_name[BEHAVIOR_METRIC_ACTIVE_MINUTES] == 60.0  # 경과 지표는 정상
        assert BEHAVIOR_METRIC_MEASURED_ACTIVE_MINUTES not in by_name  # 승격 없음
