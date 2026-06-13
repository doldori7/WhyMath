"""WH-1 0단계 대리 지표 — *순수* 계산 단위테스트 (hermetic·FakeSession).

`compute_wh1_surrogate_metrics`의 집계 로직(③ 세션 완주율·④ 턴당 토큰)과 미계측 5종
(①②⑤⑥⑦)의 status·note·value None 불변을 전수 검증한다. 집계 SQL의 *실 정확성*(GROUP BY·
AVG)은 통합테스트(`test_me_integration` 류·실 PG)가 검증 — 여기선 FakeSession이 execute
큐로 count/AVG 결과를 주입해 *래퍼 로직*(분기·status 결정·None 보존)만 본다.

핵심 불변(설계안 04a §8.4·CLAUDE.md "모르면 모른다"): 미계측 지표는 *절대* 0/stub을 내지
않는다 — value=None + status enum + 한국어 note. 표본 0이면 NO_DATA(가짜 0 아님).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy.ext.asyncio import AsyncSession

from whymath_backend.harness.wh1_evaluation import (
    Metric,
    MetricStatus,
    SurrogateMetrics,
    compute_wh1_surrogate_metrics,
)


class _FakeScalarResult:
    """`.scalar()`(count) 또는 `.one()`(AVG, count) 튜플을 반환하는 execute 결과."""

    def __init__(self, scalar: Any = None, one: Any = None) -> None:
        self._scalar = scalar
        self._one = one

    def scalar(self) -> Any:
        return self._scalar

    def one(self) -> Any:
        return self._one


class _FakeSession:
    """execute 호출 순서대로 미리 큐에 넣은 결과를 돌려준다(stmt 무시).

    `compute_wh1_surrogate_metrics`의 execute 순서:
      1) total_sessions(count·scalar)
      2) completed_sessions(count·scalar)
      3) token row(AVG, count·one 튜플)
      4) verify row(passed_count, total·one 튜플)
    이 4개를 큐로 주입한다 — 정렬·실 SQL은 통합테스트가 실 PG로 검증.
    """

    def __init__(self, results: list[_FakeScalarResult]) -> None:
        self._results = list(results)
        self.execute_count = 0

    async def execute(self, _stmt: Any) -> _FakeScalarResult:
        result = self._results[self.execute_count]
        self.execute_count += 1
        return result


def _make_session(
    *,
    total_sessions: int,
    completed_sessions: int,
    avg_tokens: float | None,
    token_sample: int,
    verify_passed: int = 0,
    verify_total: int = 0,
) -> AsyncSession:
    return cast(
        AsyncSession,
        _FakeSession(
            [
                _FakeScalarResult(scalar=total_sessions),
                _FakeScalarResult(scalar=completed_sessions),
                _FakeScalarResult(one=(avg_tokens, token_sample)),
                _FakeScalarResult(one=(verify_passed, verify_total)),
            ]
        ),
    )


# ── ③ 세션 완주율 ────────────────────────────────────────────────────────────
class TestSessionCompletionRate:
    async def test_measured_ratio(self) -> None:
        """완주(ended_at NOT NULL) 3/4 → MEASURED·value 0.75·표본 4."""
        session = _make_session(
            total_sessions=4, completed_sessions=3, avg_tokens=None, token_sample=0
        )
        m = await compute_wh1_surrogate_metrics(session)
        assert m.session_completion_rate.status is MetricStatus.MEASURED
        assert m.session_completion_rate.value == 0.75
        assert m.sample_sessions == 4

    async def test_all_completed(self) -> None:
        session = _make_session(
            total_sessions=2, completed_sessions=2, avg_tokens=None, token_sample=0
        )
        m = await compute_wh1_surrogate_metrics(session)
        assert m.session_completion_rate.value == 1.0
        assert m.session_completion_rate.status is MetricStatus.MEASURED

    async def test_none_completed(self) -> None:
        session = _make_session(
            total_sessions=3, completed_sessions=0, avg_tokens=None, token_sample=0
        )
        m = await compute_wh1_surrogate_metrics(session)
        assert m.session_completion_rate.value == 0.0
        assert m.session_completion_rate.status is MetricStatus.MEASURED

    async def test_zero_total_is_no_data_not_zero(self) -> None:
        """표본 0 → NO_DATA·value None(가짜 0 금지·날조 회피 핵심)."""
        session = _make_session(
            total_sessions=0, completed_sessions=0, avg_tokens=None, token_sample=0
        )
        m = await compute_wh1_surrogate_metrics(session)
        assert m.session_completion_rate.status is MetricStatus.NO_DATA
        assert m.session_completion_rate.value is None  # 0이 아님!
        assert m.sample_sessions == 0
        assert "0건" in m.session_completion_rate.note


# ── ④ 턴당 토큰 ──────────────────────────────────────────────────────────────
class TestTokensPerTurn:
    async def test_measured(self) -> None:
        """토큰 채워진 대화 있음 → MEASURED·AVG 값·표본 수."""
        session = _make_session(
            total_sessions=1, completed_sessions=1, avg_tokens=42.5, token_sample=10
        )
        m = await compute_wh1_surrogate_metrics(session)
        assert m.tokens_per_turn.status is MetricStatus.MEASURED
        assert m.tokens_per_turn.value == 42.5
        assert m.sample_dialogues == 10

    async def test_no_qualifying_rows_is_no_data(self) -> None:
        """토큰·턴 채워진 행 0 → NO_DATA·value None(토큰 미적재면 정직하게 NO_DATA)."""
        session = _make_session(
            total_sessions=1, completed_sessions=1, avg_tokens=None, token_sample=0
        )
        m = await compute_wh1_surrogate_metrics(session)
        assert m.tokens_per_turn.status is MetricStatus.NO_DATA
        assert m.tokens_per_turn.value is None  # 0이 아님!
        assert m.sample_dialogues == 0
        assert "미적재" in m.tokens_per_turn.note

    async def test_avg_none_with_sample_still_no_data(self) -> None:
        """count>0이나 AVG가 None(이론적 경계)이면 NO_DATA로 안전 처리."""
        session = _make_session(
            total_sessions=1, completed_sessions=1, avg_tokens=None, token_sample=3
        )
        m = await compute_wh1_surrogate_metrics(session)
        assert m.tokens_per_turn.status is MetricStatus.NO_DATA
        assert m.tokens_per_turn.value is None


# ── ① verify 통과율 ──────────────────────────────────────────────────────────
class TestVerifyPassRate:
    async def test_measured_ratio(self) -> None:
        """검산결과 이벤트 passed 3/4 → MEASURED·value 0.75·표본 4."""
        session = _make_session(
            total_sessions=1,
            completed_sessions=1,
            avg_tokens=None,
            token_sample=0,
            verify_passed=3,
            verify_total=4,
        )
        m = await compute_wh1_surrogate_metrics(session)
        assert m.verify_pass_rate.status is MetricStatus.MEASURED
        assert m.verify_pass_rate.value == 0.75
        assert m.sample_verify_events == 4

    async def test_all_passed(self) -> None:
        session = _make_session(
            total_sessions=1,
            completed_sessions=1,
            avg_tokens=None,
            token_sample=0,
            verify_passed=2,
            verify_total=2,
        )
        m = await compute_wh1_surrogate_metrics(session)
        assert m.verify_pass_rate.value == 1.0
        assert m.verify_pass_rate.status is MetricStatus.MEASURED

    async def test_none_passed(self) -> None:
        session = _make_session(
            total_sessions=1,
            completed_sessions=1,
            avg_tokens=None,
            token_sample=0,
            verify_passed=0,
            verify_total=5,
        )
        m = await compute_wh1_surrogate_metrics(session)
        assert m.verify_pass_rate.value == 0.0
        assert m.verify_pass_rate.status is MetricStatus.MEASURED

    async def test_zero_events_is_no_data_not_zero(self) -> None:
        """검산결과 이벤트 0건 → NO_DATA·value None(가짜 0 금지)."""
        session = _make_session(
            total_sessions=1,
            completed_sessions=1,
            avg_tokens=None,
            token_sample=0,
            verify_passed=0,
            verify_total=0,
        )
        m = await compute_wh1_surrogate_metrics(session)
        assert m.verify_pass_rate.status is MetricStatus.NO_DATA
        assert m.verify_pass_rate.value is None  # 0이 아님!
        assert m.sample_verify_events == 0

    async def test_note_is_honest_binary_verify(self) -> None:
        """MEASURED note에 '미적발'·'unverifiable 미구분'(binary·3-state 아님) 정직 표기."""
        session = _make_session(
            total_sessions=1,
            completed_sessions=1,
            avg_tokens=None,
            token_sample=0,
            verify_passed=1,
            verify_total=2,
        )
        m = await compute_wh1_surrogate_metrics(session)
        assert "미적발" in m.verify_pass_rate.note
        assert "unverifiable 미구분" in m.verify_pass_rate.note


# ── ②⑤⑥⑦ 미계측 4종 ────────────────────────────────────────────────────────
class TestUnmeasuredMetrics:
    async def _metrics(self) -> SurrogateMetrics:
        session = _make_session(
            total_sessions=1, completed_sessions=1, avg_tokens=10.0, token_sample=5
        )
        return await compute_wh1_surrogate_metrics(session)

    async def test_diagnosis_agreement_requires_data(self) -> None:
        m = (await self._metrics()).diagnosis_agreement_rate
        assert m.status is MetricStatus.REQUIRES_DATA
        assert m.value is None
        assert "ground-truth" in m.note

    async def test_help_reduction_not_instrumented(self) -> None:
        m = (await self._metrics()).help_reduction_slope
        assert m.status is MetricStatus.NOT_INSTRUMENTED
        assert m.value is None
        assert "used_hint" in m.note

    async def test_calibration_requires_tool(self) -> None:
        m = (await self._metrics()).calibration_brier
        assert m.status is MetricStatus.REQUIRES_TOOL
        assert m.value is None
        assert "elicit_prediction" in m.note

    async def test_transfer_requires_tool(self) -> None:
        m = (await self._metrics()).transfer_score
        assert m.status is MetricStatus.REQUIRES_TOOL
        assert m.value is None
        assert "전이" in m.note

    async def test_all_unmeasured_value_none(self) -> None:
        """미계측 4종 *전부* value None — 단 하나도 0/stub이 아님(날조 0 불변)."""
        m = await self._metrics()
        for metric in (
            m.diagnosis_agreement_rate,
            m.help_reduction_slope,
            m.calibration_brier,
            m.transfer_score,
        ):
            assert isinstance(metric, Metric)
            assert metric.value is None
            assert metric.status is not MetricStatus.MEASURED
            assert metric.note  # 한국어 note 비어있지 않음


# ── 메타·필드셋·스코핑 ───────────────────────────────────────────────────────
class TestMetaAndFieldSet:
    async def test_field_set_complete(self) -> None:
        """SurrogateMetrics가 7 지표 + 메타 5개를 모두 보유."""
        session = _make_session(
            total_sessions=2, completed_sessions=1, avg_tokens=12.0, token_sample=4
        )
        m = await compute_wh1_surrogate_metrics(session)
        for name in (
            "verify_pass_rate",
            "diagnosis_agreement_rate",
            "session_completion_rate",
            "tokens_per_turn",
            "help_reduction_slope",
            "calibration_brier",
            "transfer_score",
        ):
            assert isinstance(getattr(m, name), Metric)
        assert m.sample_sessions == 2
        assert m.sample_dialogues == 4

    async def test_user_scoped_true_when_user_id(self) -> None:
        session = _make_session(
            total_sessions=1, completed_sessions=1, avg_tokens=None, token_sample=0
        )
        m = await compute_wh1_surrogate_metrics(session, user_id=uuid.uuid4())
        assert m.user_scoped is True

    async def test_user_scoped_false_for_cohort(self) -> None:
        session = _make_session(
            total_sessions=1, completed_sessions=1, avg_tokens=None, token_sample=0
        )
        m = await compute_wh1_surrogate_metrics(session, user_id=None)
        assert m.user_scoped is False

    async def test_window_passthrough(self) -> None:
        """since/until이 메타(window_start/end)에 그대로 반영."""
        since = datetime(2026, 1, 1, tzinfo=UTC)
        until = datetime(2026, 3, 1, tzinfo=UTC)
        session = _make_session(
            total_sessions=1, completed_sessions=1, avg_tokens=None, token_sample=0
        )
        m = await compute_wh1_surrogate_metrics(session, since=since, until=until)
        assert m.window_start == since
        assert m.window_end == until
