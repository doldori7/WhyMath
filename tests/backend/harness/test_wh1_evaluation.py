"""WH-1 0단계 대리 지표 — *순수* 계산 단위테스트 (hermetic·FakeSession).

`compute_wh1_surrogate_metrics`의 집계 로직(① verify 통과율·③ 세션 완주율·④ 턴당 토큰·
⑤ 도움 감소 곡선 OLS 기울기)과 미계측 3종(②⑥⑦)의 status·note·value None 불변을 전수
검증한다. 집계 SQL의 *실 정확성*(GROUP BY·AVG·JSONB 캐스팅·정렬)은 통합테스트
(`test_me_integration` 류·실 PG)가 검증 — 여기선 FakeSession이 execute 큐로 count/AVG/
hint_level 행을 주입해 *래퍼 로직*(분기·status 결정·OLS 기울기·None 보존)만 본다.

핵심 불변(설계안 04a §8.4·CLAUDE.md "모르면 모른다"): 미계측 지표는 *절대* 0/stub을 내지
않는다 — value=None + status enum + 한국어 note. 표본 0이면 NO_DATA(가짜 0 아님). ⑤는
종단 표본이 _MIN_SLOPE_POINTS 미만이면 NO_DATA(가짜 기울기 금지).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy.ext.asyncio import AsyncSession

from whymath_backend.harness.wh1_evaluation import (
    HelpReductionValidation,
    Metric,
    MetricStatus,
    R15Verdict,
    SurrogateMetrics,
    _judge_r15,
    _ols_slope,
    compute_wh1_surrogate_metrics,
)


class _FakeScalarResult:
    """`.scalar()`(count)·`.one()`(AVG, count)·`.all()`(행 목록)을 반환하는 execute 결과."""

    def __init__(
        self, scalar: Any = None, one: Any = None, all_rows: Any = None
    ) -> None:
        self._scalar = scalar
        self._one = one
        self._all = all_rows if all_rows is not None else []

    def scalar(self) -> Any:
        return self._scalar

    def one(self) -> Any:
        return self._one

    def all(self) -> Any:
        return self._all


class _FakeSession:
    """execute 호출 순서대로 미리 큐에 넣은 결과를 돌려준다(stmt 무시).

    `compute_wh1_surrogate_metrics`의 execute 순서:
      1) total_sessions(count·scalar)
      2) completed_sessions(count·scalar)
      3) token row(AVG, count·one 튜플)
      4) verify row(passed_count, total·one 튜플)
      5) hint rows(event_at 오름차순 hint_level 행 목록·all)
      6) accuracy rows(started_at 오름차순 is_correct 행 목록·all)
    이 6개를 큐로 주입한다 — 정렬·실 SQL은 통합테스트가 실 PG로 검증.
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
    hint_levels: list[int | None] | None = None,
    accuracy_correct: list[bool | None] | None = None,
) -> AsyncSession:
    # ⑤ 힌트 쿼리는 단일 컬럼(.as_integer())을 event_at 오름차순으로 뽑으므로 행은 (level,) 튜플.
    # None(JSONB 파싱 실패)도 섞일 수 있게 그대로 (None,)으로 주입 — 본문이 None을 걸러낸다.
    hint_rows = [(lvl,) for lvl in (hint_levels or [])]
    # R15 정답률 쿼리는 단일 컬럼(is_correct)을 started_at 오름차순으로 뽑으므로 행은 (bool,) 튜플.
    accuracy_rows = [(c,) for c in (accuracy_correct or [])]
    return cast(
        AsyncSession,
        _FakeSession(
            [
                _FakeScalarResult(scalar=total_sessions),
                _FakeScalarResult(scalar=completed_sessions),
                _FakeScalarResult(one=(avg_tokens, token_sample)),
                _FakeScalarResult(one=(verify_passed, verify_total)),
                _FakeScalarResult(all_rows=hint_rows),
                _FakeScalarResult(all_rows=accuracy_rows),
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


# ── ⑤ 도움 감소 곡선(OLS 기울기) ─────────────────────────────────────────────
class TestHelpReductionSlope:
    async def _slope(self, hint_levels: list[int | None]) -> Metric:
        session = _make_session(
            total_sessions=1,
            completed_sessions=1,
            avg_tokens=None,
            token_sample=0,
            hint_levels=hint_levels,
        )
        return (await compute_wh1_surrogate_metrics(session)).help_reduction_slope

    async def test_decreasing_trend_negative_slope_measured(self) -> None:
        """감소 추세(4→3→2→1) → MEASURED·음수 기울기(도움 감소=개선)."""
        m = await self._slope([4, 3, 2, 1])
        assert m.status is MetricStatus.MEASURED
        assert m.value is not None
        assert m.value < 0
        assert m.value == -1.0  # 완전 등차 −1

    async def test_increasing_trend_positive_slope_measured(self) -> None:
        """증가 추세(1→2→3) → MEASURED·양수 기울기(도움 증가=악화)."""
        m = await self._slope([1, 2, 3])
        assert m.status is MetricStatus.MEASURED
        assert m.value is not None
        assert m.value > 0
        assert m.value == 1.0

    async def test_too_few_points_is_no_data_not_fake_slope(self) -> None:
        """포인트 < _MIN_SLOPE_POINTS(3) → NO_DATA·value None(가짜 기울기/0 금지)."""
        m = await self._slope([4, 2])  # 2점 < 3
        assert m.status is MetricStatus.NO_DATA
        assert m.value is None  # 0도, 기울기도 아님!
        assert "표본 부족" in m.note

    async def test_zero_points_is_no_data(self) -> None:
        m = await self._slope([])
        assert m.status is MetricStatus.NO_DATA
        assert m.value is None

    async def test_constant_levels_zero_variance_is_no_data(self) -> None:
        """동일 레벨(3,3,3) — y 분산 0이지만 x 분산은 양수라 기울기 0(MEASURED·평탄).

        x(0,1,2) 분산은 양수이므로 OLS는 정의되고 기울기는 정확히 0(평탄=도움 불변). 0 분산
        NO_DATA 가드는 *x축* 분산이 0일 때만(이론적 경계)이라 동일 레벨은 MEASURED 0이다 —
        이건 날조 0이 아니라 *실측된 평탄*이다(입력이 실제로 평평).
        """
        m = await self._slope([3, 3, 3])
        assert m.status is MetricStatus.MEASURED
        assert m.value == 0.0

    async def test_none_levels_filtered_then_too_few(self) -> None:
        """JSONB 파싱 실패(None) 행은 걸러져 유효 포인트만 카운트 — 2개만 유효→NO_DATA."""
        m = await self._slope([4, None, 2, None])  # 유효 2점 < 3
        assert m.status is MetricStatus.NO_DATA
        assert m.value is None

    async def test_note_honest_r15_and_longitudinal(self) -> None:
        """MEASURED note에 'R15'(정확률 교차검증 미반영)·'종단' 정직 표기."""
        m = await self._slope([4, 3, 2, 1])
        assert "R15" in m.note
        assert "종단" in m.note


# ── ②⑥⑦ 미계측 3종 ──────────────────────────────────────────────────────────
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
        """미계측 3종(②⑥⑦) *전부* value None — 단 하나도 0/stub이 아님(날조 0 불변)."""
        m = await self._metrics()
        for metric in (
            m.diagnosis_agreement_rate,
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
        """SurrogateMetrics가 7 지표 + R15 결합 판정 + 메타(표본 수 포함)를 모두 보유."""
        session = _make_session(
            total_sessions=2,
            completed_sessions=1,
            avg_tokens=12.0,
            token_sample=4,
            hint_levels=[4, 3, 2],
            accuracy_correct=[True, True, True],
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
        assert isinstance(m.help_reduction_validated, HelpReductionValidation)
        assert m.sample_sessions == 2
        assert m.sample_dialogues == 4
        assert m.sample_hint_events == 3  # 유효 hint_level 행 수
        assert m.sample_accuracy_attempts == 3  # is_correct NOT NULL 행 수

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


# ── _ols_slope 공유 헬퍼(⑤ 리팩터 후 ⑤·R15 공유 코어) ───────────────────────────
class TestOlsSlope:
    def test_decreasing_slope(self) -> None:
        """완전 등차 하강(4,3,2,1) → 기울기 −1.0."""
        assert _ols_slope([4.0, 3.0, 2.0, 1.0]) == -1.0

    def test_increasing_slope(self) -> None:
        """완전 등차 상승(1,2,3) → 기울기 +1.0."""
        assert _ols_slope([1.0, 2.0, 3.0]) == 1.0

    def test_flat_is_zero_not_none(self) -> None:
        """동일값(3,3,3) → x 분산 양수라 기울기 0.0(실측 평탄·날조 0 아님)."""
        assert _ols_slope([3.0, 3.0, 3.0]) == 0.0

    def test_too_few_points_is_none(self) -> None:
        """포인트 < _MIN_SLOPE_POINTS(3) → None(가짜 기울기/0 금지)."""
        assert _ols_slope([4.0, 2.0]) is None
        assert _ols_slope([1.0]) is None
        assert _ols_slope([]) is None


# ── _judge_r15 결합 판정(R15 4분기) ──────────────────────────────────────────────
class TestJudgeR15:
    def test_genuine_improvement_help_down_accuracy_up(self) -> None:
        """도움↓(−1)·정답률↑(+0.5) → GENUINE_IMPROVEMENT(진짜 개선)."""
        v = _judge_r15(-1.0, 0.5)
        assert v.verdict is R15Verdict.GENUINE_IMPROVEMENT
        assert v.help_slope == -1.0
        assert v.accuracy_slope == 0.5
        assert "진짜 개선" in v.note

    def test_genuine_improvement_accuracy_flat_boundary(self) -> None:
        """도움↓·정답률 유지(0·경계 포함) → GENUINE_IMPROVEMENT(slope 0 임계)."""
        v = _judge_r15(-0.3, 0.0)
        assert v.verdict is R15Verdict.GENUINE_IMPROVEMENT

    def test_gaming_suspect_help_down_accuracy_down(self) -> None:
        """도움↓(−1)이나 정답률↓(−0.5) → GAMING_SUSPECT(교정기 함정·힌트 회피 의심)."""
        v = _judge_r15(-1.0, -0.5)
        assert v.verdict is R15Verdict.GAMING_SUSPECT
        assert "교정기 함정" in v.note

    def test_no_help_reduction_positive_help_slope(self) -> None:
        """도움 기울기 >= 0(안 줄어듦) → NO_HELP_REDUCTION(개선 신호 아님)."""
        assert _judge_r15(0.5, -1.0).verdict is R15Verdict.NO_HELP_REDUCTION
        # 경계 0도 도움 안 줄어듦(>= 0) — 정답률 부호 무관.
        assert _judge_r15(0.0, 0.9).verdict is R15Verdict.NO_HELP_REDUCTION

    def test_insufficient_data_when_help_none(self) -> None:
        """도움 기울기 None(표본 부족) → INSUFFICIENT_DATA(날조 판정 금지)."""
        v = _judge_r15(None, 0.5)
        assert v.verdict is R15Verdict.INSUFFICIENT_DATA
        assert v.help_slope is None
        assert v.accuracy_slope == 0.5

    def test_insufficient_data_when_accuracy_none(self) -> None:
        """정답률 기울기 None(표본 부족) → INSUFFICIENT_DATA(한쪽이라도 부족이면)."""
        v = _judge_r15(-1.0, None)
        assert v.verdict is R15Verdict.INSUFFICIENT_DATA

    def test_insufficient_data_when_both_none(self) -> None:
        assert _judge_r15(None, None).verdict is R15Verdict.INSUFFICIENT_DATA


# ── R15 결합 판정 — compute_wh1_surrogate_metrics 통합(FakeSession is_correct 주입) ──
class TestHelpReductionValidatedIntegratedWithCompute:
    async def _validate(
        self,
        *,
        hint_levels: list[int | None] | None,
        accuracy_correct: list[bool | None] | None,
    ) -> HelpReductionValidation:
        session = _make_session(
            total_sessions=1,
            completed_sessions=1,
            avg_tokens=None,
            token_sample=0,
            hint_levels=hint_levels,
            accuracy_correct=accuracy_correct,
        )
        return (await compute_wh1_surrogate_metrics(session)).help_reduction_validated

    async def test_genuine_improvement(self) -> None:
        """도움↓(4→3→2→1)·정답률↑(F→T→T→T) → GENUINE_IMPROVEMENT."""
        v = await self._validate(
            hint_levels=[4, 3, 2, 1],
            accuracy_correct=[False, True, True, True],
        )
        assert v.verdict is R15Verdict.GENUINE_IMPROVEMENT
        assert v.help_slope is not None and v.help_slope < 0
        assert v.accuracy_slope is not None and v.accuracy_slope > 0

    async def test_gaming_suspect(self) -> None:
        """도움↓(4→3→2→1)이나 정답률↓(T→T→F→F) → GAMING_SUSPECT(힌트 회피 의심)."""
        v = await self._validate(
            hint_levels=[4, 3, 2, 1],
            accuracy_correct=[True, True, False, False],
        )
        assert v.verdict is R15Verdict.GAMING_SUSPECT
        assert v.help_slope is not None and v.help_slope < 0
        assert v.accuracy_slope is not None and v.accuracy_slope < 0

    async def test_no_help_reduction(self) -> None:
        """도움↑(1→2→3) → NO_HELP_REDUCTION(정답률 무관)."""
        v = await self._validate(
            hint_levels=[1, 2, 3],
            accuracy_correct=[True, True, True],
        )
        assert v.verdict is R15Verdict.NO_HELP_REDUCTION

    async def test_insufficient_when_accuracy_too_few(self) -> None:
        """도움↓ 충분하나 정답률 표본 부족(2점<3) → INSUFFICIENT_DATA(날조 판정 금지)."""
        v = await self._validate(
            hint_levels=[4, 3, 2, 1],
            accuracy_correct=[True, False],
        )
        assert v.verdict is R15Verdict.INSUFFICIENT_DATA
        assert v.accuracy_slope is None

    async def test_insufficient_when_hint_too_few(self) -> None:
        """정답률 충분하나 도움 표본 부족(2점<3) → INSUFFICIENT_DATA."""
        v = await self._validate(
            hint_levels=[4, 2],
            accuracy_correct=[True, True, True],
        )
        assert v.verdict is R15Verdict.INSUFFICIENT_DATA
        assert v.help_slope is None

    async def test_accuracy_none_rows_filtered(self) -> None:
        """is_correct None 행은 본문이 거르므로 sample_accuracy_attempts에서 제외(방어적)."""
        session = _make_session(
            total_sessions=1,
            completed_sessions=1,
            avg_tokens=None,
            token_sample=0,
            hint_levels=[4, 3, 2, 1],
            accuracy_correct=[True, None, True, True],
        )
        m = await compute_wh1_surrogate_metrics(session)
        # None 1개 제외 → 유효 3개.
        assert m.sample_accuracy_attempts == 3


# ── ⑤ 리팩터 회귀(비트동일) — _help_reduction_from_levels는 _ols_slope 위임 후도 불변 ──
class TestHelpReductionRefactorRegression:
    async def _slope(self, hint_levels: list[int | None]) -> Metric:
        session = _make_session(
            total_sessions=1,
            completed_sessions=1,
            avg_tokens=None,
            token_sample=0,
            hint_levels=hint_levels,
        )
        return (await compute_wh1_surrogate_metrics(session)).help_reduction_slope

    async def test_measured_value_unchanged(self) -> None:
        """리팩터 후도 4→3→2→1 기울기 −1.0·MEASURED(⑤ 동작 비트동일)."""
        m = await self._slope([4, 3, 2, 1])
        assert m.status is MetricStatus.MEASURED
        assert m.value == -1.0

    async def test_too_few_note_unchanged(self) -> None:
        """표본 부족 NO_DATA·'표본 부족' note 보존(가드 분기 비트동일)."""
        m = await self._slope([4, 2])
        assert m.status is MetricStatus.NO_DATA
        assert m.value is None
        assert "표본 부족" in m.note
