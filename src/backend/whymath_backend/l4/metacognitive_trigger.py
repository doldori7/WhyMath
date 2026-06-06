"""L4 메타인지 코칭 트리거 — L2 진단(BKT↔IRT) → 교수학적 코칭 포커스 결정.

`docs/architecture/04_pedagogy_engine.md`: L4는 *결정* 계층(L3=생성·L5=노출). 본 모듈은 L2
학습자 모델의 두 신호 — BKT 개념 숙달 P(L)과 IRT 능력 θ — 를 받아 *어떤 메타인지 코칭이
적절한가*를 결정한다(실제 발화 생성·UI 노출은 각각 L3·L5 책임).

핵심 통찰(slice L2-19 교차검증의 교수학적 후속): 두 신호의 *불일치*가 가장 값진 코칭 단서다.
- 문항은 맞히나(θ↑) 숙달 추정은 낮음(BKT↓) → *우연·추측 의심* → 이해 진위를 메타인지로 점검.
- 숙달했(BKT↑)으나 최근 능력은 낮음(θ↓) → *망각·슬럼프 의심* → 인출 연습으로 회복.
- 둘 다 낮으면(합의) 기초 재교육(LTHC 낮은 진입점)·둘 다 높으면 심화(LTHC 높은 천장).
- 한쪽 신호만 있으면 교차검증 불가 → 추가 진단.

레이어 경계 준수: L4는 L2(숙달·θ)를 *안다*. L5(api)·DB는 모른다 — 입력은 원시 수치(float)뿐.
순수·결정론(외부 의존 0). 발화는 *답을 주지 않는* 메타인지 유도(CLAUDE.md 답 미루기 원칙).
"""

from __future__ import annotations

import math
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from whymath_backend.l4.socratic.categories import SocraticCategory

CoachingFocus = Literal["verify", "consolidate", "retrieval", "foundation", "advance", "diagnose"]
"""메타인지 코칭 포커스 6종.

- `verify`: *검산* — 구체적 계산 오류가 감지됨(슬립). 개념 재교육 전에 스스로 계산을 다시
  짚게 한다(슬립 vs 오개념 구분 — 이해는 있는데 계산만 틀린 경우 재교육은 역효과).
- `consolidate`: 이해 *공고화* — 맞히나 숙달 낮음(추측 의심). 풀이 근거를 스스로 설명.
- `retrieval`: *인출 연습* — 숙달했으나 능력 낮음(망각·슬럼프). 핵심 아이디어 회상·복습.
- `foundation`: *기초 재교육* — 두 신호 모두 낮음. LTHC 낮은 진입점부터 비계.
- `advance`: *심화* — 두 신호 모두 높음. LTHC 높은 천장(일반화·증명·전이).
- `diagnose`: *추가 진단* — 한쪽 신호만 존재(교차검증 불가). 문항 더 풀어 데이터 확보.
"""

# 포커스별 근거(rationale)·학생 노출 코칭 발화(prompt) — 답을 주지 않는 메타인지 유도.
_RATIONALE: dict[CoachingFocus, str] = {
    "verify": "구체적 계산 오류 감지 — 개념 재교육보다 *검산*으로 어긋난 지점을 스스로 찾게.",
    "consolidate": "문항은 맞혔지만 숙달 추정이 낮음 — 우연·추측이 아닌 진짜 이해인지 점검.",
    "retrieval": "숙달했던 개념인데 최근 능력 추정이 낮음 — 망각·슬럼프 가능성, 인출로 회복.",
    "foundation": "숙달·능력 두 신호 모두 낮음 — 기초 사례부터 비계(LTHC 낮은 진입점).",
    "advance": "숙달·능력 두 신호 모두 높음 — 일반화·증명·전이로 심화(LTHC 높은 천장).",
    "diagnose": "한쪽 신호만 있어 교차검증 불가 — 문항을 더 풀어 상태를 정확히 파악.",
}
_PROMPT: dict[CoachingFocus, str] = {
    "verify": "계산을 한 단계씩 다시 짚어보면서 어디서 숫자가 어긋났는지 찾아볼래?",
    "consolidate": "방금 푼 방법을 *왜* 그렇게 했는지 한 단계씩 설명해볼래?",
    "retrieval": "이 개념의 핵심 아이디어를 먼저 떠올려 한 줄로 적어볼래?",
    "foundation": "이 개념의 *가장 기본 사례*부터 같이 차근차근 볼까?",
    "advance": "조건을 바꾸거나 *왜 항상* 성립하는지 증명에 도전해볼래?",
    "diagnose": "이 개념 문제를 몇 개 더 풀어보면 네 상태를 더 정확히 볼 수 있어.",
}
# 포커스 → 대화 진입 소크라테스 카테고리(slice 5·socratic 6분류). coach가 *어떤 질문 종류*로
# 시작할지 — verify=근거(계산 재점검)·consolidate=근거(추측 검증)·retrieval=메타(예전 풀이
# 회상)·foundation/diagnose=명료화(기초·상태 파악)·advance=관점(다른 방법·일반화).
_SOCRATIC_BY_FOCUS: dict[CoachingFocus, SocraticCategory] = {
    "verify": SocraticCategory.EVIDENCE,
    "consolidate": SocraticCategory.EVIDENCE,
    "retrieval": SocraticCategory.META,
    "foundation": SocraticCategory.CLARIFICATION,
    "advance": SocraticCategory.PERSPECTIVE,
    "diagnose": SocraticCategory.CLARIFICATION,
}


def focus_to_socratic_category(focus: CoachingFocus) -> SocraticCategory:
    """코칭 포커스 → 대화 진입 소크라테스 카테고리 — 순수 매핑(coach 발화 종류 결정 입력)."""
    return _SOCRATIC_BY_FOCUS[focus]


class CoachingTrigger(BaseModel):
    """메타인지 코칭 결정 — 포커스 + 근거 + 학생 노출 발화. 불변(frozen)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    focus: CoachingFocus = Field(description="코칭 포커스 5종.")
    rationale: str = Field(description="결정 근거(교사/학생 노출 가능 한국어).")
    prompt: str = Field(description="학생에게 보일 수 있는 메타인지 유도 발화(답 미제공).")
    socratic_category: SocraticCategory = Field(
        description="대화 진입 소크라테스 카테고리(coach 발화 종류·slice 5)."
    )


def _mastery_proxy(theta: float) -> float:
    """IRT θ → [0,1] 숙달 프록시 — 중앙 난이도(b=0) 정답확률 logistic(θ). BKT 숙달과 비교용."""
    return 1.0 / (1.0 + math.exp(-theta))


def recommend_coaching(
    bkt_mastery: float | None,
    irt_theta: float | None,
    *,
    arithmetic_error: bool = False,
    discrepancy_tol: float = 0.2,
    mastery_threshold: float = 0.6,
) -> CoachingTrigger:
    """L2 두 신호(BKT 숙달·IRT θ)+선택적 계산 오류 신호에서 코칭 포커스 결정 — 순수·결정론.

    **우선순위**: `arithmetic_error=True`(구체적 계산 오류가 결정론으로 감지됨·예: L3 관계
    검증기가 학생 풀이의 "2+3=6"을 탐지)면 다른 신호와 무관하게 `verify`(검산) — 슬립 vs
    오개념 구분 원칙: 이해는 있는데 *계산만* 틀린 경우 개념 재교육은 역효과, 구체적 오류는
    스스로 검산하게 하는 것이 직접·효과적이다. 구체적 오류 신호는 θ/숙달 추정(추상)보다
    *즉시 코칭*에 우선한다(데이터가 없어도 작동).

    그 외: 한쪽이라도 없으면 `diagnose`(교차검증 불가). 둘 다 있으면 θ를 숙달 프록시(logistic)로
    환산해 BKT 숙달과 비교: 프록시-숙달 > `discrepancy_tol` → `consolidate`(맞히나 숙달 낮음)·
    < -tol → `retrieval`(숙달했으나 능력 낮음). 차가 tol 이내면 *합의* — 두 신호 평균이
    `mastery_threshold` 미만이면 `foundation`(기초)·이상이면 `advance`(심화).

    `arithmetic_error`는 *L4가 직접 검출하지 않는다* — 호출자(오케스트레이터)가 L3 결정론
    검증 결과를 bool로 전달(레이어 경계: L4는 원시 신호만 받음). 발화·근거는 포커스별 정본
    카탈로그에서 조회(답 미제공·메타인지 유도).
    """
    if arithmetic_error:
        return _build("verify")
    if bkt_mastery is None or irt_theta is None:
        return _build("diagnose")

    proxy = _mastery_proxy(irt_theta)
    diff = proxy - bkt_mastery
    if diff > discrepancy_tol:
        return _build("consolidate")
    if diff < -discrepancy_tol:
        return _build("retrieval")
    # 합의 — 수준으로 기초/심화 분기.
    level = (bkt_mastery + proxy) / 2.0
    return _build("foundation" if level < mastery_threshold else "advance")


def _build(focus: CoachingFocus) -> CoachingTrigger:
    return CoachingTrigger(
        focus=focus,
        rationale=_RATIONALE[focus],
        prompt=_PROMPT[focus],
        socratic_category=_SOCRATIC_BY_FOCUS[focus],
    )


__all__ = [
    "CoachingFocus",
    "CoachingTrigger",
    "focus_to_socratic_category",
    "recommend_coaching",
]
