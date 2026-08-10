"""PED-14 — ⑰ 시간 정규화 숙달 증가율(Δmastery/Σduration_seconds) 계약 동결.

`docs/strategy/reclaimed_time_positioning_v1.md` §3·§7. S3-32가 `ProblemAttempt`를 처음
착지시키며 분자(⑨ mastery 델타)·분모(attempt duration)가 처음으로 동시에 생겼다. 재조사 결과
(태스크 노트) Flutter writer 배선은 불필요했다 — 라이브 경로는 `api/coach.py::_apply_completion`
이며 `duration_seconds`를 서버 벽시계(ended_at−dialogue.started_at)로 채운다.

이 파일이 동결하는 것(`test_wh1_evaluation.py`의 `TestTimeNormalizedMasteryGains*`·
`TestTimeNormalizedMasteryGainIntegratedWithCompute`와 상보 — 그쪽이 계산 정확성·회귀 0을
본다면 이 파일은 *계약*(좌석·노출 계층·비교 파생 부재)을 본다):
  ① 좌석 — `SurrogateMetrics.mastery_gain_rate_time_normalized`가 존재하고, ⑨
     (`mastery_gain_rate`)는 필드 설명 문구에서도 이 신규 필드를 가리키도록 정본화됐다.
  ② 노출 계층 — `classify_metric_exposure`를 경유해 **INTERNAL_ONLY**로 분류된다(⑥ 학생 대면
     표현 제약 — 원 스칼라 속도 지표는 "정답을 빠르게"로 오독될 위험, §1-1 안전선).
  ③ 비교 파생 함수의 *부재*가 계약이다(5원칙 #2·ARCH-27 게이트와 별개로 harness 축 방어).

hermetic: DB 불요(순수 함수·모델 단위 테스트). 계산 정확성·회귀 0 assert는
`test_wh1_evaluation.py`(`TestTimeNormalizedMasteryGain*`) 참조.
"""

from __future__ import annotations

from whymath_backend.harness.growth_evidence_exposure import (
    ExposureTier,
    classify_metric_exposure,
)
from whymath_backend.harness.wh1_evaluation import (
    HelpReductionValidation,
    Metric,
    MetricStatus,
    R15Verdict,
    SurrogateMetrics,
)


def _all_no_data_metrics() -> SurrogateMetrics:
    """전 지표를 NO_DATA로 채운 최소 `SurrogateMetrics` — 노출 *계층* 판정만 보는 용도.

    필드가 늘어도 깨지지 않도록 **애너테이션으로 값을 고른다**(하드코딩 목록 금지 — 새 지표가
    추가될 때마다 이 헬퍼가 조용히 낡는 것을 막는다). `test_wh1_evaluation_gap_recovery_
    leadtime.py`(PED-13)의 동명 헬퍼를 그대로 미러(각 하네스 테스트 파일이 자기완결적).
    """
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


class TestSeatExists:
    """① 좌석 — `SurrogateMetrics`에 필드가 있고, ⑨ 문구가 이 필드를 가리키도록 정본화됐다."""

    def test_seat_exists_on_surrogate_metrics(self) -> None:
        """SurrogateMetrics에_좌석이_있다 — 좌석 없이 계산만 하면 노출 계약 밖이다."""
        assert "mastery_gain_rate_time_normalized" in SurrogateMetrics.model_fields

    def test_seat_defaults_to_no_data_for_unaware_callers(self) -> None:
        """기존(이 태스크 이전) 호출자가 이 필드를 명시 안 해도 회귀 0 — 기본값 NO_DATA."""
        field = SurrogateMetrics.model_fields["mastery_gain_rate_time_normalized"]
        assert not field.is_required(), "default_factory 없이 required면 기존 호출자가 전부 깨진다"

    def test_mastery_gain_rate_description_points_to_new_seat(self) -> None:
        """⑨(mastery_gain_rate) 필드 설명이 '후속' 대신 신규 필드명을 가리킨다(acceptance ③).

        ⑨ 자체의 계산 로직(_mastery_gains_from_rows/_mastery_gain_from_gains)은 이 파일이
        건드리지 않는다 — 여기서 보는 것은 *문서(정본화)*뿐이다.
        """
        description = SurrogateMetrics.model_fields["mastery_gain_rate"].description or ""
        assert "mastery_gain_rate_time_normalized" in description
        assert "후속" not in description, "정본화 후에도 stale '후속' 문구가 남아있으면 안 된다"


class TestExposureContract:
    """② 노출 계층 — INTERNAL_ONLY(acceptance ⑥). 계약 로직 재구현 금지(classify_metric_exposure 경유)."""

    def test_classified_internal_only(self) -> None:
        """원 스칼라 속도 지표는 학생·보호자 어디에도 노출되지 않는다.

        `_STATIC_TIER`를 직접 읽지 않고 `classify_metric_exposure`를 경유한다(⑯ 테스트와
        동형 관례 — 계약 로직 재구현 금지). 판정 함수는 `SurrogateMetrics` 전체를 받으므로
        전 지표를 NO_DATA로 채운 최소 인스턴스를 만든다(이 테스트는 계층 배정만 본다).
        """
        metrics = _all_no_data_metrics()
        table = classify_metric_exposure(metrics)
        assert "mastery_gain_rate_time_normalized" in table, "노출 판정 표에 좌석이 없다"
        exposure = table["mastery_gain_rate_time_normalized"]
        assert exposure.tier is ExposureTier.INTERNAL_ONLY
        assert exposure.exposable_now is False
        assert exposure.suppressed_reason is not None

    def test_internal_only_regardless_of_r15_verdict(self) -> None:
        """R15 결합 판정(GENUINE/GAMING)과 무관하게 항상 내부 전용 — ②·④와 동일 축."""
        for verdict in R15Verdict:
            metrics = _all_no_data_metrics().model_copy(
                update={
                    "help_reduction_validated": HelpReductionValidation(
                        verdict=verdict, note="테스트"
                    )
                }
            )
            table = classify_metric_exposure(metrics)
            assert table["mastery_gain_rate_time_normalized"].tier is ExposureTier.INTERNAL_ONLY


class TestNoComparisonDerivative:
    """③ 자기 대비만 — 비교 파생 함수의 *부재*가 계약이다(⑯ 테스트와 동형 관례)."""

    def test_module_exposes_no_peer_or_rank_helper(self) -> None:
        """시간_정규화_숙달_모듈에_또래·순위·백분위_파생_심볼이_없다

        `ARCH-27` 게이트는 학생 대면(api/·schema/)을 스캔하므로 harness/ 는 그 스코프 밖이다
        — 이 단언이 harness 축의 짝이다(5원칙 #2를 지표 생산 지점에서도 막는다).
        """
        import whymath_backend.harness.wh1_evaluation as mod

        banned = ("peer", "percentile", "leaderboard", "rank")
        offenders = [
            name
            for name in dir(mod)
            if ("time_normalized" in name.lower() or "mastery_gain_rate" in name.lower())
            and any(b in name.lower() for b in banned)
        ]
        assert offenders == []
