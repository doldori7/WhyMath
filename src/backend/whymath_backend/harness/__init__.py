"""WH-1 튜터링 하네스 — 횡단(cross-cutting) 평가 인프라 패키지.

설계 정본: `docs/architecture/04a_wh1_tutoring_harness.md` §8.4·§11.6. WH-1(소크라테스
튜터링 하네스) 도입의 **0단계**는 "측정 없는 도입 없음"(설계안 v0.2 제1원칙)에 따라 *대리
지표 7종*을 계측하는 것이다. 본 패키지는 그 0단계 **베이스라인 좌석**이다.

계층 메모(설계안 §1·CLAUDE.md 7계층):
  WH-1 하네스는 *새 계층이 아니라 횡단 인프라*다. 따라서 L1~L7 어디에도 속하지 않고
  `harness/` 패키지로 분리한다. 이 패키지는 L1(활동 로그)·L2(학습자 모델) 데이터를 *조회만*
  하고(역방향 의존 없음), 노출은 L5(api/me)가 담당한다 — 하네스가 상위 계층을 알지 못한다.

정직성 원칙(CLAUDE.md "확실하지 않을 때 자신 있게 말함 금지"·설계안 "측정 없는 도입 없음"):
  현재 코드/데이터로 *계측 가능한* 지표만 실값으로 내고, *미계측* 지표는 **가짜 0/stub을
  내지 않는다** — 상태 enum(`MetricStatus`) + "무엇이 필요한지" note로 갭을 가시화한다. 이
  좌석 자체가 *측정 인프라의 골격*이며, 무엇이 아직 계측 불가인지를 정직하게 드러내는 게
  목적이다.
"""

from __future__ import annotations

from whymath_backend.harness.wh1_evaluation import (
    HelpReductionValidation,
    Metric,
    MetricStatus,
    R15Verdict,
    SurrogateMetrics,
    compute_wh1_surrogate_metrics,
)

__all__ = [
    "HelpReductionValidation",
    "Metric",
    "MetricStatus",
    "R15Verdict",
    "SurrogateMetrics",
    "compute_wh1_surrogate_metrics",
]
