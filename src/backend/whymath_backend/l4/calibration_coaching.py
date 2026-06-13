"""L4 보정(calibration) 코칭 결정 — 예측 확신도 ↔ 실제 정오답 불일치 → 메타인지 코칭.

`docs/architecture/04_pedagogy_engine.md` WH-1 §11.4 보정 루프: 학생이 *예측한* 확신도와
*실제* 정오답 사이의 어긋남을 코칭으로 교정한다(L4는 *결정* 계층·L3=생성·L5=노출).

핵심 통찰(측정→행동): 직전 측정 단계(⑥ Brier 보정 점수·`harness`)가 학생의 확신이 *얼마나*
어긋났는지를 잰다면, 이 모듈은 그 어긋남을 *학생별 코칭 결정*으로 잇는다. 두 구간이 값지다 —
- **과신 구간(틀렸는데 확신 높음)**: 소크라테스 강도를 올린다 — "왜 그렇게 확신했을까?"로
  자기점검·가정 재검토를 유도(ASSUMPTION). *틀렸다*고 부정 강화하지 않고 부드럽게 메타인지로
  초대한다(CLAUDE.md 톤·답 미루기). 바로 정답을 주지 않는다.
- **과소신 구간(맞았는데 확신 낮음)**: 성취를 명시해 효능감을 회복시킨다(META). "충분히 잘
  풀었다"를 분명히 짚어 자기 풀이를 믿도록 격려한다.
- 잘 보정됨(맞고 확신↑·틀리고 확신↓)이면 코칭 불요(None) — 예측과 실제가 일치한다.

레이어 경계 준수: L4는 원시 신호(confidence·is_correct)만 받는다 — DB·async·fetch 없음(순수·
결정론·`recommend_prerequisite_coaching` 동형). 데이터 fetch는 L5(api/me submit_attempt)가
이미 받은 자기보고 확신도+정오답을 그대로 주입(새 수집·마이그레이션 0). redaction: rationale·
prompt는 자체 작성 격려 문구라 개념 본문·정답이 흐를 슬롯이 없다.
"""

from __future__ import annotations

from whymath_backend.l4.metacognitive_trigger import (
    _PROMPT,
    _RATIONALE,
    _SOCRATIC_BY_FOCUS,
    CoachingFocus,
    CoachingTrigger,
)


def recommend_calibration_coaching(
    confidence: float | None,
    is_correct: bool | None,
    *,
    over_threshold: float = 0.7,
    under_threshold: float = 0.3,
) -> CoachingTrigger | None:
    """자기보고 확신도 ↔ 실제 정오답에서 보정 코칭 결정 — 순수·결정론(`recommend_*_coaching` 동형).

    보정 구간 정의:
    - `is_correct=False` **and** `confidence >= over_threshold`(기본 0.7) → **과신** →
      `calibration_overconfident`(틀렸으나 확신 높음·자기점검·가정 재검토·소크라테스 강화).
    - `is_correct=True` **and** `confidence <= under_threshold`(기본 0.3) → **과소신** →
      `calibration_underconfident`(맞았으나 확신 낮음·성취 명시·효능감 회복).
    - 그 외(잘 보정됨 — 맞고 확신↑·틀리고 확신↓·중간 확신) → **None**(코칭 불요).

    `confidence`·`is_correct` 중 하나라도 None이면 **None**(보정 평가 불가 — 확신 미제출 등).
    임계는 양끝 포함(>=·<=)이라 경계값(정확히 0.7·0.3)도 코칭 대상이다.

    측정과의 관계: 보정 *점수*(⑥ Brier·`harness`)는 코호트의 보정 *정도*를 잰다. 이 함수는
    개별 제출 1건에서 *어떤 코칭이 필요한가*를 결정한다(측정→코칭). 발화·근거는 포커스별 정본
    카탈로그(`_RATIONALE`/`_PROMPT`/`_SOCRATIC_BY_FOCUS`)에서 조회한다(드리프트 방지).
    """
    if confidence is None or is_correct is None:
        return None  # 보정 평가 불가(확신 미제출 등) → 코칭 안 함.

    if not is_correct and confidence >= over_threshold:
        return _build("calibration_overconfident")
    if is_correct and confidence <= under_threshold:
        return _build("calibration_underconfident")
    return None  # 잘 보정됨(예측↔실제 일치) → 코칭 불요.


def _build(focus: CoachingFocus) -> CoachingTrigger:
    # 포커스별 정본 카탈로그에서 근거·발화·소크라테스 카테고리 조회(metacognitive_trigger 공유).
    return CoachingTrigger(
        focus=focus,
        rationale=_RATIONALE[focus],
        prompt=_PROMPT[focus],
        socratic_category=_SOCRATIC_BY_FOCUS[focus],
    )


__all__ = ["recommend_calibration_coaching"]
