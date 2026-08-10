"""PED-13 — ⑯ 결손 복구 리드타임(첫 취약 관측 → 첫 숙달 도달 경과 일수) 계약 동결.

`docs/strategy/reclaimed_time_positioning_v1.md` §3의 증명 지표 5종 중 **오늘 계산 가능한
유일한 축**이다 — `ConceptMasteryHistory`의 `measured_at`이 복합 PK라 벽시계 간격이 신규
컬럼 없이 나온다(나머지 4종은 `ProblemAttempt` 0행 등 입력 루프 단절로 막혀 있다).

이 파일이 동결하는 것:
  ① 임계를 **재선언하지 않고 정본에서 읽는다** — 0.7은 `recommend_prerequisite_gaps_detailed`
     의 기본 인자, 0.8은 `l4/lthc/adapt._MASTERED_THRESHOLD`. 값을 베껴 적었다면 정본이
     바뀌어도 이 지표는 모른 채 남는다(드리프트).
  ② 미도달·재하락 처리 — 0.8 미도달은 분모에서 제외(가짜 0 금지), 도달 후 재하락은 *첫*
     도달 기준 고정.
  ③ **양방향 변별력** — 행을 넣으면 NO_DATA가 풀리고, 되돌리면 다시 NO_DATA가 된다.
     한쪽만 확인하면 "언제나 값이 나오는" 검사와 구별되지 않는다.
  ④ 자기 대비만 — 또래·평균·순위 파생 함수가 **없다**(부재가 계약 · 5원칙 #2 · `ARCH-27`
     게이트가 소스 스캔으로 별도 강제).

hermetic: DB 불요(순수 함수 단위 테스트).
"""

from __future__ import annotations

import inspect
import uuid
from datetime import datetime, timedelta, timezone

from whymath_backend.harness.growth_evidence_exposure import (
    ExposureTier,
    classify_metric_exposure,
)
from whymath_backend.harness.wh1_evaluation import (
    _RECOVERY_MASTERY_THRESHOLD,
    _WEAK_MASTERY_THRESHOLD,
    MetricStatus,
    SurrogateMetrics,
    _gap_recovery_leadtime_metric,
    _gap_recovery_leadtimes_from_rows,
)
from whymath_backend.l2.prerequisite_recommendation import recommend_prerequisite_gaps_detailed
from whymath_backend.l4.lthc.adapt import _MASTERED_THRESHOLD

_U = uuid.uuid4()
_C = uuid.uuid4()
_T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _row(mastery: float, day: int, *, user: uuid.UUID = _U, concept: uuid.UUID = _C):
    return (user, concept, mastery, _T0 + timedelta(days=day))


def _all_no_data_metrics() -> SurrogateMetrics:
    """전 지표를 NO_DATA로 채운 최소 `SurrogateMetrics` — 노출 *계층* 판정만 보는 용도.

    필드가 늘어도 깨지지 않도록 **애너테이션으로 값을 고른다**(하드코딩 목록 금지 — 새 지표가
    추가될 때마다 이 헬퍼가 조용히 낡는 것을 막는다).
    """
    from whymath_backend.harness.wh1_evaluation import (
        HelpReductionValidation,
        Metric,
        R15Verdict,
    )

    blank = Metric(value=None, status=MetricStatus.NO_DATA, note="테스트 고정값")
    defaults: dict[object, object] = {
        Metric: blank,
        int: 0,
        float: 0.0,
        str: "테스트 고정값",
        HelpReductionValidation: HelpReductionValidation(
            verdict=next(iter(R15Verdict)), note="테스트 고정값"
        ),
    }
    kwargs: dict[str, object] = {}
    for name, field in SurrogateMetrics.model_fields.items():
        if not field.is_required():
            continue
        if field.annotation not in defaults:  # pragma: no cover - 새 타입 유입 시 즉시 드러남
            raise AssertionError(f"미지원 필드 타입: {name}={field.annotation} — 헬퍼 갱신 필요")
        kwargs[name] = defaults[field.annotation]
    return SurrogateMetrics(**kwargs)  # type: ignore[arg-type]


class TestThresholdProvenance:
    """① 임계는 정본에서 온다 — 베껴 적기 금지(acceptance ①)."""

    def test_weak_threshold_comes_from_l2_signature(self) -> None:
        """취약_임계가_recommend_prerequisite_gaps_detailed_기본값과_동일"""
        canonical = (
            inspect.signature(recommend_prerequisite_gaps_detailed)
            .parameters["mastery_threshold"]
            .default
        )
        assert _WEAK_MASTERY_THRESHOLD == canonical

    def test_recovery_threshold_comes_from_l4_adapt(self) -> None:
        """숙달_임계가_l4_lthc_adapt_MASTERED_THRESHOLD와_동일"""
        assert _RECOVERY_MASTERY_THRESHOLD == _MASTERED_THRESHOLD

    def test_thresholds_are_ordered(self) -> None:
        """취약_임계_<_숙달_임계 — 뒤집히면 리드타임이 항상 즉시 0이 된다"""
        assert _WEAK_MASTERY_THRESHOLD < _RECOVERY_MASTERY_THRESHOLD


class TestLeadtimeComputation:
    """② 미도달·재하락 처리 규약."""

    def test_simple_recovery_is_measured_in_days(self) -> None:
        """취약_후_숙달_도달까지_경과_일수"""
        days, unrecovered = _gap_recovery_leadtimes_from_rows(
            [_row(0.5, 0), _row(0.65, 3), _row(0.85, 10)]
        )
        assert days == [10.0]
        assert unrecovered == 0

    def test_unrecovered_group_excluded_not_zero(self) -> None:
        """0.8_미도달_그룹은_분모에서_제외되고_0으로_세지_않는다"""
        days, unrecovered = _gap_recovery_leadtimes_from_rows(
            [_row(0.5, 0), _row(0.7, 5), _row(0.79, 9)]
        )
        assert days == []
        assert unrecovered == 1

    def test_first_attainment_is_fixed_on_relapse(self) -> None:
        """도달_후_재하락해도_첫_도달_기준이_고정된다"""
        days, _ = _gap_recovery_leadtimes_from_rows(
            [_row(0.5, 0), _row(0.85, 4), _row(0.3, 8), _row(0.9, 30)]
        )
        assert days == [4.0], "재하락 후 재도달이 리드타임을 늘리면 '회복이 오래 걸렸다'로 오독된다"

    def test_never_weak_group_is_not_a_subject(self) -> None:
        """줄곧_숙달인_그룹은_결손이_없어_대상이_아니다"""
        days, unrecovered = _gap_recovery_leadtimes_from_rows([_row(0.9, 0), _row(0.95, 5)])
        assert days == []
        assert unrecovered == 0

    def test_recovery_before_weakness_does_not_count(self) -> None:
        """결손_이전의_숙달_관측은_기산점이_아니다"""
        days, unrecovered = _gap_recovery_leadtimes_from_rows(
            [_row(0.9, 0), _row(0.4, 10), _row(0.85, 12)]
        )
        assert days == [2.0]
        assert unrecovered == 0

    def test_groups_are_independent(self) -> None:
        """서로_다른_(user,concept)_그룹은_독립_집계"""
        other = uuid.uuid4()
        days, unrecovered = _gap_recovery_leadtimes_from_rows(
            [
                _row(0.5, 0),
                _row(0.85, 2),
                _row(0.5, 0, concept=other),
                _row(0.6, 20, concept=other),
            ]
        )
        assert sorted(days) == [2.0]
        assert unrecovered == 1


class TestNoDataBidirectional:
    """③ 양방향 변별력 — 넣으면 풀리고 빼면 다시 NO_DATA(acceptance ⑥)."""

    def test_empty_is_no_data_not_zero(self) -> None:
        """자격_그룹_0이면_NO_DATA이고_value는_None"""
        metric = _gap_recovery_leadtime_metric(*_gap_recovery_leadtimes_from_rows([]))
        assert metric.status is MetricStatus.NO_DATA
        assert metric.value is None

    def test_injection_releases_no_data_and_removal_restores_it(self) -> None:
        """행_주입시_MEASURED_전환·되돌리면_다시_NO_DATA

        한 방향만 보면 "무엇을 넣어도 값이 나오는" 검사와 구별되지 않는다.
        """
        rows = [_row(0.5, 0), _row(0.85, 6)]
        released = _gap_recovery_leadtime_metric(*_gap_recovery_leadtimes_from_rows(rows))
        assert released.status is MetricStatus.MEASURED
        assert released.value == 6.0

        restored = _gap_recovery_leadtime_metric(*_gap_recovery_leadtimes_from_rows(rows[:1]))
        assert restored.status is MetricStatus.NO_DATA
        assert restored.value is None

    def test_no_data_note_reports_unrecovered_count(self) -> None:
        """미도달_건수를_note에_정직하게_보고 — 침묵 제외 금지"""
        metric = _gap_recovery_leadtime_metric(*_gap_recovery_leadtimes_from_rows([_row(0.5, 0)]))
        assert "미도달 1" in metric.note


class TestExposureContract:
    """③ 노출 계층 — 계약 로직 재구현 금지(classify_metric_exposure 경유)."""

    def test_seat_exists_on_surrogate_metrics(self) -> None:
        """SurrogateMetrics에_좌석이_있다 — 좌석 없이 계산만 하면 노출 계약 밖이다"""
        assert "gap_recovery_leadtime_days" in SurrogateMetrics.model_fields

    def test_classified_student_visible(self) -> None:
        """학생_노출_계층으로_분류된다(자기 대비 축)

        `_STATIC_TIER`를 직접 읽지 않고 `classify_metric_exposure`를 경유한다 — 계약 로직
        재구현 금지(acceptance ③). 판정 함수는 `SurrogateMetrics` 전체를 받으므로 전 지표를
        NO_DATA로 채운 최소 인스턴스를 만든다(이 테스트는 계층 배정만 본다).
        """
        metrics = _all_no_data_metrics()
        table = classify_metric_exposure(metrics)
        assert "gap_recovery_leadtime_days" in table, "노출 판정 표에 좌석이 없다"
        assert table["gap_recovery_leadtime_days"].tier is ExposureTier.STUDENT_VISIBLE


class TestNoComparisonDerivative:
    """④ 자기 대비만 — 비교 파생 함수의 *부재*가 계약이다."""

    def test_module_exposes_no_peer_or_rank_helper(self) -> None:
        """리드타임_모듈에_또래·순위·백분위_파생_심볼이_없다

        `ARCH-27` 게이트는 학생 대면(api/·schema/)을 스캔하므로 harness/ 는 그 스코프 밖이다
        — 이 단언이 harness 축의 짝이다(5원칙 #2를 지표 생산 지점에서도 막는다).
        """
        import whymath_backend.harness.wh1_evaluation as mod

        banned = ("peer", "percentile", "leaderboard")
        offenders = [
            name
            for name in dir(mod)
            if "leadtime" in name.lower() and any(b in name.lower() for b in banned)
        ]
        assert offenders == []
