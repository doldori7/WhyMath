"""WH-1 대리 지표 베이스라인 리포트 렌더 — 순수 단위테스트(hermetic·DB 무관).

`render_baseline_report`(SurrogateMetrics → 마크다운)와 `_resolve_params`(CLI 인자 파싱)만
검증한다. DB 조회 glue(`_run`·`main`의 asyncio.run)는 실 PG 통합검증 소관(pragma no cover).

핵심 불변(계산 계층과 동일 철학·CLAUDE.md "모르면 모른다"): 렌더는 "가짜 0 금지"를 표면화한다 —
MEASURED만 값을 보이고 NO_DATA는 값 대신 '—' + 사유(note)를 옮긴다. 12 지표 전부·R15 판정·
커버리지 카운트가 리포트에 나타나야 한다.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from whymath_backend.harness.surrogate_baseline_report import (
    GrowthEvidenceReachState,
    _resolve_params,
    classify_reach_state,
    render_baseline_report,
    render_growth_evidence_reach_report,
)
from whymath_backend.harness.wh1_evaluation import (
    HelpReductionValidation,
    Metric,
    MetricStatus,
    R15Verdict,
    SurrogateMetrics,
)

# 12 지표 라벨(리포트에 전부 나타나야 함).
_METRIC_LABELS = (
    "① verify 통과율",
    "② 진단정확도(오프라인)",
    "③ 세션 완주율",
    "④ 턴당 토큰",
    "⑤ 도움 감소 곡선",
    "⑥ 보정 점수(Brier)",
    "⑦ 전이 점수(근사)",
    "⑧ 답 미루기 도달 깊이",
    "⑨ BKT 숙달 증가율",
    "⑩ 오개념 해소율",
    "⑪ 스스로 풀이 도달율",
    "⑮ 도움 요청 대 제공 비",
)


def _measured(value: float) -> Metric:
    return Metric(value=value, status=MetricStatus.MEASURED, note="실측 note")


def _no_data() -> Metric:
    return Metric(value=None, status=MetricStatus.NO_DATA, note="표본 0건 — 사유 note")


def _all_measured_metrics() -> SurrogateMetrics:
    """12 지표 전부 MEASURED인 SurrogateMetrics(커버리지 12/12 검증용)."""
    m = _measured(0.5)
    return SurrogateMetrics(
        verify_pass_rate=m,
        diagnosis_agreement_rate=m,
        session_completion_rate=m,
        tokens_per_turn=_measured(42.0),
        help_reduction_slope=_measured(-1.0),
        help_demand_supply_ratio=_measured(0.2),
        calibration_brier=_measured(0.1),
        transfer_score=m,
        hint_depth_reached=_measured(2.5),
        mastery_gain_rate=_measured(0.3),
        misconception_resolution_rate=m,
        self_solve_rate=m,
        help_reduction_validated=HelpReductionValidation(
            verdict=R15Verdict.GENUINE_IMPROVEMENT,
            help_slope=-1.0,
            accuracy_slope=0.5,
            difficulty_slope=0.4,
            note="진짜 개선 note",
        ),
        sample_sessions=4,
        sample_resolved_dialogues=3,
        sample_demand_events=1,
        window_start=datetime(2026, 1, 1, tzinfo=UTC),
        window_end=datetime(2026, 3, 1, tzinfo=UTC),
        user_scoped=False,
    )


def _mixed_metrics() -> SurrogateMetrics:
    """일부 MEASURED·일부 NO_DATA(가짜 0 금지 렌더 검증용)."""
    return SurrogateMetrics(
        verify_pass_rate=_measured(0.8),
        diagnosis_agreement_rate=_no_data(),
        session_completion_rate=_measured(0.75),
        tokens_per_turn=_no_data(),
        help_reduction_slope=_no_data(),
        help_demand_supply_ratio=_no_data(),
        calibration_brier=_no_data(),
        transfer_score=_no_data(),
        hint_depth_reached=_no_data(),
        mastery_gain_rate=_no_data(),
        misconception_resolution_rate=_no_data(),
        self_solve_rate=_no_data(),
        help_reduction_validated=HelpReductionValidation(
            verdict=R15Verdict.INSUFFICIENT_DATA,
            note="표본 부족 note",
        ),
        user_scoped=True,
    )


class TestRenderBaselineReport:
    def test_all_metric_labels_present(self) -> None:
        """12 지표 라벨이 전부 리포트에 렌더된다(빠짐 없음)."""
        report = render_baseline_report(_all_measured_metrics())
        for label in _METRIC_LABELS:
            assert label in report

    def test_coverage_count_all_measured(self) -> None:
        """전부 MEASURED → 커버리지 12/12."""
        report = render_baseline_report(_all_measured_metrics())
        assert "MEASURED 12/12" in report
        assert "코호트 전체" in report  # user_scoped=False

    def test_coverage_count_mixed(self) -> None:
        """혼합(2 MEASURED) → 커버리지 2/12·본인 스코프."""
        report = render_baseline_report(_mixed_metrics())
        assert "MEASURED 2/12" in report
        assert "NO_DATA/미계측 10/12" in report
        assert "본인(user)" in report  # user_scoped=True

    def test_no_data_shows_reason_not_zero(self) -> None:
        """NO_DATA 지표는 값 대신 '—' + 사유(note) — 가짜 0 금지."""
        report = render_baseline_report(_mixed_metrics())
        # NO_DATA 지표의 값은 0이 아니라 '—'
        assert "값 —" in report
        assert "표본 0건 — 사유 note" in report
        # 0.0000 같은 가짜 0이 NO_DATA 지표에서 나오지 않는다(MEASURED만 실수 값).
        assert "값 0.8000" in report  # MEASURED verify_pass_rate

    def test_measured_value_formatted(self) -> None:
        """MEASURED 값은 4자리 소수로 렌더."""
        report = render_baseline_report(_all_measured_metrics())
        assert "값 42.0000" in report  # tokens_per_turn
        assert "값 -1.0000" in report  # help_reduction_slope(음수=도움 감소)

    def test_r15_verdict_rendered(self) -> None:
        """R15 결합 판정 verdict·note가 렌더된다."""
        report = render_baseline_report(_all_measured_metrics())
        assert "R15 결합 판정" in report
        assert R15Verdict.GENUINE_IMPROVEMENT.value in report

    def test_window_infinite_when_none(self) -> None:
        """시간창 None → '무한 과거/미래'로 정직 표기."""
        report = render_baseline_report(_mixed_metrics())  # window None
        assert "무한 과거" in report
        assert "무한 미래" in report

    def test_sample_counts_rendered(self) -> None:
        """표본 수가 지표 행에 렌더된다."""
        report = render_baseline_report(_all_measured_metrics())
        assert "표본 4" in report  # sample_sessions
        assert "표본 3" in report  # sample_resolved_dialogues


class TestResolveParams:
    def test_all_none_defaults(self) -> None:
        """전부 미지정 → 코호트 전체·전체 기간(None, None, None)."""
        assert _resolve_params(None, None, None) == (None, None, None)

    def test_parses_uuid_and_iso(self) -> None:
        uid = uuid.uuid4()
        user, since, until = _resolve_params(
            str(uid), "2026-01-01T00:00:00+00:00", "2026-03-01T00:00:00+00:00"
        )
        assert user == uid
        assert since == datetime(2026, 1, 1, tzinfo=UTC)
        assert until == datetime(2026, 3, 1, tzinfo=UTC)

    def test_invalid_uuid_raises(self) -> None:
        """잘못된 UUID는 즉시 실패(조용한 폴백 없음)."""
        with pytest.raises(ValueError):
            _resolve_params("not-a-uuid", None, None)

    def test_invalid_date_raises(self) -> None:
        with pytest.raises(ValueError):
            _resolve_params(None, "not-a-date", None)


class TestClassifyReachState:
    """`classify_reach_state` 순수 함수 — 구조적불가 > 무데이터 > 미도달/도달 우선순위(PED-06)."""

    def test_structurally_impossible_overrides_everything(self) -> None:
        """③(세션완주율)은 MEASURED·요청 있음이어도 구조적 불가로 고정(생산자 자체 부재)."""
        state = classify_reach_state("session_completion_rate", MetricStatus.MEASURED, 100)
        assert state is GrowthEvidenceReachState.STRUCTURALLY_IMPOSSIBLE

    def test_no_data_when_status_not_measured(self) -> None:
        state = classify_reach_state("verify_pass_rate", MetricStatus.NO_DATA, 0)
        assert state is GrowthEvidenceReachState.NO_DATA

    def test_unreached_when_measured_but_zero_requests(self) -> None:
        state = classify_reach_state("verify_pass_rate", MetricStatus.MEASURED, 0)
        assert state is GrowthEvidenceReachState.UNREACHED

    def test_reached_when_measured_and_requests_positive(self) -> None:
        """변별력(양방향) — 요청 수가 0→양수로 바뀌면 미도달이 실제로 해제된다."""
        unreached = classify_reach_state("verify_pass_rate", MetricStatus.MEASURED, 0)
        reached = classify_reach_state("verify_pass_rate", MetricStatus.MEASURED, 1)
        assert unreached is GrowthEvidenceReachState.UNREACHED
        assert reached is GrowthEvidenceReachState.REACHED
        assert unreached is not reached

    def test_reverts_to_unreached_when_requests_reset_to_zero(self) -> None:
        """변별력(양방향, 되돌림) — 도달 후 요청 수가 다시 0이면 미도달로 되돌아간다."""
        reached = classify_reach_state("verify_pass_rate", MetricStatus.MEASURED, 3)
        reverted = classify_reach_state("verify_pass_rate", MetricStatus.MEASURED, 0)
        assert reached is GrowthEvidenceReachState.REACHED
        assert reverted is GrowthEvidenceReachState.UNREACHED

    def test_no_data_takes_priority_over_reach_regardless_of_requests(self) -> None:
        """무데이터는 요청 수가 아무리 커도 도달로 격상되지 않는다(값이 없으니 보여줄 게 없음)."""
        state = classify_reach_state("calibration_brier", MetricStatus.NO_DATA, 1000)
        assert state is GrowthEvidenceReachState.NO_DATA


class TestRenderGrowthEvidenceReachReport:
    """`render_growth_evidence_reach_report` — 노출 계약 + 3상태를 얹은 확장 리포트(PED-06)."""

    def test_zero_requests_shown_as_unreached_not_zero_pass(self) -> None:
        """요청 0건은 '0건 통과'가 아니라 '미도달'로 표시(이중 회계 — VIZ-01·NLP-01 승계)."""
        report = render_growth_evidence_reach_report(_all_measured_metrics(), requests_total=0)
        assert "누적 요청 0건" in report
        assert "미도달" in report
        assert "0건 통과" not in report

    def test_structurally_impossible_labeled_distinctly_from_no_data(self) -> None:
        """③(구조적 불가)과 다른 NO_DATA 지표가 리포트에서 서로 다른 라벨로 나타난다."""
        report = render_growth_evidence_reach_report(_mixed_metrics(), requests_total=0)
        assert "구조적 불가" in report
        assert "무데이터" in report
        # ③ 세션 완주율 섹션에 '구조적 불가'가 붙어 있어야 한다(순서 의존 없이 섹션 단위 확인).
        section_start = report.index("## ③ 세션 완주율")
        section_end = report.index("## ④", section_start)
        assert "구조적 불가" in report[section_start:section_end]

    def test_internal_only_fields_show_suppression_reason(self) -> None:
        report = render_growth_evidence_reach_report(_all_measured_metrics(), requests_total=5)
        assert "내부 전용" in report
        assert "노출 억제 사유" in report

    def test_hint_depth_suppressed_when_gaming_suspect(self) -> None:
        metrics = _all_measured_metrics()
        gaming = metrics.model_copy(
            update={
                "help_reduction_validated": HelpReductionValidation(
                    verdict=R15Verdict.GAMING_SUSPECT,
                    help_slope=-1.0,
                    accuracy_slope=-0.5,
                    difficulty_slope=None,
                    note="게이밍 의심 note",
                )
            }
        )
        report = render_growth_evidence_reach_report(gaming, requests_total=5)
        section_start = report.index("## ⑧")
        section_end = report.index("## ⑨", section_start)
        assert "노출 억제 사유" in report[section_start:section_end]

    def test_calibration_no_data_notes_missing_input_ui_not_rec01(self) -> None:
        """⑥ NO_DATA일 때 '입력 UI 부재'를 REC-01 입력 루프 미도달과 구분해 표기한다."""
        report = render_growth_evidence_reach_report(_mixed_metrics(), requests_total=0)
        section_start = report.index("## ⑥")
        section_end = report.index("## ⑦", section_start)
        section = report[section_start:section_end]
        assert "입력 UI" in section
        assert "REC-01" in section

    def test_reached_state_appears_when_requests_positive_and_measured(self) -> None:
        report = render_growth_evidence_reach_report(_all_measured_metrics(), requests_total=7)
        assert "누적 요청 7건" in report
        assert "도달상태 도달" in report
