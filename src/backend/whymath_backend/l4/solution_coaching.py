"""L3→L4 오케스트레이터 — 학생 풀이 계산오류(L3 결정론 검증) → L4 검산 코칭 처방.

slice 51이 `recommend_coaching`에 `arithmetic_error` 신호를 받을 자리를 만들었으나
*미결선*이었고(L4 함수는 bool 받을 준비만), 본 모듈이 그 **결선**이다 — L3의 결정론 관계
검증기(=·<·>·≤·≥·≠, slice 36~46)를 *학생 풀이 텍스트*에 적용해 "2+3=6" 같은 계산 슬립을
검출하고, 그 bool을 L4 `recommend_coaching`에 전달한다.

레이어 경계(CLAUDE.md "L_n은 L_{n-1}을 *호출*할 수 있지만 *구현*하지 않는다"): L4(교수학
결정)가 L3 도구(`validate_response`)를 *호출*해 신호를 얻고, *순수* L4 결정 함수
(`recommend_coaching`)에 bool로 넘긴다. SymPy 검증을 재구현하지 않으며(L3 책임),
`recommend_coaching` 자체는 L3를 모르는 순수 함수로 남는다(slice 51 "L4는 원시 신호만 받음").
*본 오케스트레이터만* 양쪽 계층을 안다(이미 `l4.models`가 `l3.models`를 import하는 기존
L4→L3 결합과 동형).

비차단·보수적: 검증기는 *거짓이 증명된* 수치 관계만 신호로 내고(심볼릭·파싱 불가·빈 풀이는
통과), 신호가 없으면 기존 BKT↔IRT 기반 코칭으로 자연 폴백한다(slice 51 backward-compat).
답을 *직접* 주지 않는 검산 유도가 목적이다(CLAUDE.md 답 미루기 원칙).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from whymath_backend.l3.pregenerate.validator import (
    SeedValidator,
    arithmetic_validator,
    validate_response,
)
from whymath_backend.l4.metacognitive_trigger import CoachingTrigger, recommend_coaching


class SolutionCoaching(BaseModel):
    """학생 풀이 기반 코칭 결정 — 코칭 트리거 + 계산오류 신호. 불변(frozen).

    `trigger`는 항상 채워진다(`recommend_coaching`은 항상 결정 반환). `arithmetic_error`가
    True면 `trigger.focus == "verify"`(검산)이고 `validation_signal`에 *구체적 거짓 관계*가
    담긴다(예: "arithmetic error: '2 + 3 = 6' (sympy: 5 != 6)") — L5가 학생에게 검산 코칭과
    함께 *어디가 어긋났는지* 단서로 쓸 수 있다(단, 정답을 직접 주지 않음, CLAUDE.md).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    trigger: CoachingTrigger = Field(description="L4 메타인지 코칭 결정(focus·근거·발화).")
    arithmetic_error: bool = Field(
        description="학생 풀이에서 거짓 수치 관계(=·<·>·≤·≥·≠)가 결정론으로 검출됐는가."
    )
    validation_signal: str | None = Field(
        default=None,
        description=(
            "검출된 거짓 관계 사유(L3 검증기 출력). None=계산오류 없음(통과·심볼릭·빈 풀이). "
            "trace의 validation_signal과 같은 형식(slice 40·50)."
        ),
    )


def recommend_coaching_for_solution(
    student_solution: str,
    bkt_mastery: float | None,
    irt_theta: float | None,
    *,
    validator: SeedValidator | None = None,
    discrepancy_tol: float = 0.2,
    mastery_threshold: float = 0.6,
) -> SolutionCoaching:
    """학생 풀이 + L2 두 신호 → 코칭 처방. L3 결정론 검증을 거쳐 검산 코칭을 우선한다.

    ① L3 도구(`validate_response`)로 풀이의 *거짓 수치 관계*를 검출한다(기본 검증기는
    `arithmetic_validator` — 위생 검사 없이 SymPy 관계 검증기만). ② 신호 유무를
    `arithmetic_error` bool로 환산. ③ L4 *순수* 결정 `recommend_coaching`에 전달 —
    계산오류면 `verify`(검산)를 최우선으로, 아니면 BKT↔IRT 기반 코칭(slice 51 우선순위).

    `validator`를 주입하면 다른 결정론 검증기(예: 향후 방정식 풀이 검증)를 끼울 수 있다.
    순수·결정론(같은 입력 → 같은 결정). `student_solution`이 비었거나 심볼릭이면 신호가
    없어 자연히 BKT↔IRT 경로로 폴백한다(false positive 0·보수적). `discrepancy_tol`·
    `mastery_threshold`는 `recommend_coaching`에 그대로 위임한다.
    """
    signal = validate_response(
        validator if validator is not None else arithmetic_validator(),
        student_solution,
    )
    arithmetic_error = signal is not None
    trigger = recommend_coaching(
        bkt_mastery,
        irt_theta,
        arithmetic_error=arithmetic_error,
        discrepancy_tol=discrepancy_tol,
        mastery_threshold=mastery_threshold,
    )
    return SolutionCoaching(
        trigger=trigger,
        arithmetic_error=arithmetic_error,
        validation_signal=signal,
    )


__all__ = [
    "SolutionCoaching",
    "recommend_coaching_for_solution",
]
