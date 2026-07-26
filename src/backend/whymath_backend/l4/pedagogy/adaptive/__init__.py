"""L4 Adaptive Pedagogy Engine — 교수법 효과 측정 + 학습 가능한 policy (04d §3·PED-03).

두 좌석으로 나뉜다:
  - `effectiveness` — (전략 × k_type × objective)별 성과를 `evidence_event`에서 집계. 판정치는
    Wilson 하한이며 **표본 0은 `None`**(미상을 0%로 위장하지 않는다).
  - `policy` — Thompson sampling + **하드 안전제약**(교수학 #3 위반 전략은 행동공간에서 배제).

⚠️ **policy는 아직 규칙표를 대체하지 않는다.** 런타임 선택의 정본은 `runtime_selector.decide()`이며,
승격은 `harness/pedagogy_policy_eval.py`의 오프폴리시 평가 + 강등전 통과를 전제로 한다(04d §3.3).
실 트래픽이 없는 현재는 표본 미달로 승격되지 않는다 — 그 사실이 게이트 exit 1로 드러난다.
"""

from __future__ import annotations

from whymath_backend.l4.pedagogy.adaptive.effectiveness import (
    EffectivenessKey,
    EffectivenessReport,
    EffectivenessStat,
    aggregate_effectiveness,
    load_pedagogy_events,
)
from whymath_backend.l4.pedagogy.adaptive.policy import (
    ArmPosterior,
    PolicyDecision,
    allowed_actions,
    posteriors_from_report,
    select_policy_action,
)

__all__ = [
    "ArmPosterior",
    "EffectivenessKey",
    "EffectivenessReport",
    "EffectivenessStat",
    "PolicyDecision",
    "aggregate_effectiveness",
    "allowed_actions",
    "load_pedagogy_events",
    "posteriors_from_report",
    "select_policy_action",
]
