"""Wilson score 단측 신뢰경계 — 초인간 검증 게이트의 공용 통계 부품(순수·의존성 0).

`l4/step_shadow_eval.py::_wilson_lower_bound`(2026-06 해금 게이트)의 산술을 그대로
공개 API로 승격한다. harness의 검증 게이트(강등전·코퍼스 감사)는 l3/l4를 자유로이
import할 수 있으나, 반대로 l3(생성)가 이 부품을 쓰려면 harness를 import해야 하는데
그건 계층 역참조다 — 그래서 검증 게이트가 모여 있는 harness에 단일 원천으로 둔다.

**왜 점추정이 아니라 신뢰경계인가**(CLAUDE.md 검증 권위·"모르면 모른다"): 작은 표본의
5/5=1.0 같은 점추정은 과신이다. Wilson 하한은 표본 수로 보정해 크게 깎이고(5/5·95%
→ ≈0.649), 이것이 "작은 시험으로 게이트를 거짓 통과"를 막는다(슬라이스 68 정본).

  *예시 수치 정정(2026-09-01 실측)*: 이 자리에 오래 ≈0.565가 적혀 있었으나 그것은
  **양측** z=1.96의 값이다. 이 모듈은 이름대로 **단측**(z=Φ⁻¹(0.95)=1.645)이라 5/5에서
  0.6489를 낸다 — 판정은 늘 구현이 했으므로 게이트 결과에 영향은 없었고 **설명만**
  틀려 있었다. 검증 권위 모듈의 예시가 구현과 어긋나면 미래 세션이 구현 쪽을 결함으로
  오판하므로 고친다(`test_wilson.py`가 두 경계의 실제 값을 동결한다).

- **검출률·recall처럼 "높을수록 좋은" 지표는 하한**으로 본다(정직 — 실제보다 낮게).
- **오검출률·결함율처럼 "낮을수록 좋은" 지표는 상한**으로 본다(보수 — 실제보다 높게).
"""

from __future__ import annotations

import math
import statistics

__all__ = ["wilson_lower_bound", "wilson_upper_bound"]


def _wilson_center_margin(successes: int, trials: int, confidence: float) -> tuple[float, float]:
    """Wilson score 구간의 (중심, 반폭) — 단측 z=Φ⁻¹(confidence). trials>0은 호출자 보장."""
    if not 0.0 < confidence < 1.0:
        raise ValueError(f"confidence must be in (0, 1), got {confidence}")
    if trials <= 0:
        raise ValueError(f"trials must be > 0, got {trials}")
    z = statistics.NormalDist().inv_cdf(confidence)
    n = float(trials)
    phat = successes / n
    z2 = z * z
    denom = 1.0 + z2 / n
    center = (phat + z2 / (2.0 * n)) / denom
    margin = (z / denom) * math.sqrt(phat * (1.0 - phat) / n + z2 / (4.0 * n * n))
    return center, margin


def wilson_lower_bound(successes: int, trials: int, confidence: float = 0.95) -> float:
    """이항비율의 Wilson 단측 신뢰하한 — "높을수록 좋은" 지표(검출률·recall)용.

    successes=0이면 0.0이 자연 도출된다. 작은 표본일수록 점추정보다 크게 깎인다.
    """
    center, margin = _wilson_center_margin(successes, trials, confidence)
    return max(0.0, center - margin)


def wilson_upper_bound(successes: int, trials: int, confidence: float = 0.95) -> float:
    """이항비율의 Wilson 단측 신뢰상한 — "낮을수록 좋은" 지표(오검출률·결함율)용.

    successes=0이어도 상한>0이라 "관측 0 = 확정 0"으로 과신하지 않는다(모르면 모른다).
    """
    center, margin = _wilson_center_margin(successes, trials, confidence)
    return min(1.0, center + margin)
