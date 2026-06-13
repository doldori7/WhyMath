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

WH-1 1단계 결선: `solution_steps`(L5가 분해한 단계 시퀀스)가 제공되면 `verify_solution`을
호출해 *단계별(전이별)* 검증을 추가한다. 단계 레벨 신호는 기존 텍스트 레벨 신호와 **추가적
(OR)** 으로 결합돼 검산 코칭을 정밀화하되 기존 신호를 *약화하지 않는다*. 단계 미제공 시
모든 기존 동작이 *완전 불변*이다(하위호환). 텍스트→단계 *분해*(NLP)는 L5 OCR·공간정보
책임으로 본 모듈 범위 밖 — 백엔드는 제공된 단계만 검증한다.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict, Field

from whymath_backend.l3.pregenerate.models import ValidationSignalKind
from whymath_backend.l3.pregenerate.validator import (
    SeedValidator,
    arithmetic_validator,
    validate_response,
)
from whymath_backend.l3.verify_solution import (
    SolutionVerificationResult,
    verify_solution,
)
from whymath_backend.l4.metacognitive_trigger import CoachingTrigger, recommend_coaching
from whymath_backend.l4.step_shadow import observe_step_breaks
from whymath_backend.schema.enums import StepType

SlipKind = ValidationSignalKind
"""검출된 슬립 종류 — L3 `ValidationSignalKind`와 동일 도메인(별칭). L5 UI 분기·L7 분석용.

L4 public 계약 보존용 별칭이다(`l4/__init__`·`api/coach`가 재노출). 종류는 검증기가
*직접* 선언한다(slice 59 — `_classify_slip` 산문 접두사 파싱 제거).

- `arithmetic`: 거짓 수치 등식("2+3=6") · `inequality`: 거짓 부등식("5<3")
- `not_equal`: 거짓 부등("12/4≠3") · `solution`: 틀린 방정식 해("2x+1=7 → x=5")
- `other`: 위 종류 외(예: 위생 신호 — BasicSeedValidator·주입 검증기).
"""


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
    error_kind: SlipKind | None = Field(
        default=None,
        description=(
            "검출된 슬립 종류(arithmetic·inequality·not_equal·solution·other) — None=오류 "
            "없음. L3 검증기가 `ValidationSignal.kind`로 *직접* 선언한 값(slice 59 — 산문 신호 "
            "파싱 제거)으로, L5가 종류별 코칭 UI를, L7이 오류 유형 분석을 할 수 있게 한다."
        ),
    )
    error_span: tuple[int, int] | None = Field(
        default=None,
        description=(
            "틀린 관계/해주장의 학생 풀이 원문 내 위치 `[start, end)`(0-based·half-open·JSON "
            "배열). None=위치 미상(오류 없음·위생 신호·유니코드 부등호 정규화로 오프셋 시프트). "
            "L5가 학생 풀이에서 *어디가 틀렸는지* 하이라이트하는 데 쓴다(slice 60 — "
            "`ValidationSignal.span` 노출)."
        ),
    )
    solution_verification: SolutionVerificationResult | None = Field(
        default=None,
        description=(
            "L5가 *분해한 단계 시퀀스*(`solution_steps`)를 `verify_solution`으로 연쇄 검증한 "
            "결과(상태 카운트·`unverified_ratio`·`first_incorrect_index`·`has_incorrect`). "
            "단계 미제공 시 None(텍스트 레벨 폴백 — 기존 동작 완전 불변). **노출 안전**: 입력은 "
            "*학생 자신의 단계*이고 `verify_step`의 `reason`('동치 아님 — SymPy: before ≠ "
            "after')은 검증 사유일 뿐 정답/본문이 아니다(verify_step은 정답을 알지도 못함). "
            "단계 레벨 incorrect는 텍스트 신호와 *추가적(OR)*으로 결합돼 검산 코칭을 정밀화한다."
        ),
    )


def recommend_coaching_for_solution(
    student_solution: str,
    bkt_mastery: float | None,
    irt_theta: float | None,
    *,
    problem_id: uuid.UUID | None = None,
    expected_answer: str | None = None,
    validator: SeedValidator | None = None,
    solution_steps: Sequence[str] | None = None,
    solution_step_types: Sequence[StepType | None] | None = None,
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

    **단계 결선(WH-1 1단계)**: `solution_steps`가 제공되고 전이가 1개 이상(즉 len≥2)이면
    `verify_solution(solution_steps, solution_step_types)`로 *L5가 분해한 단계 시퀀스*를
    연쇄 검증한다(텍스트→단계 *분해*는 L5 OCR·공간정보 책임으로 본 함수 범위 밖 — 백엔드는
    제공된 단계만 검증). 신호 결합은 **추가적(OR)**으로, 기존 텍스트 레벨 신호를 *약화하지
    않는다*: `arithmetic_error = (텍스트 신호 있음) or verification.has_incorrect`·`verify_steps
    = (텍스트 신호가 kind="solution") or verification.has_incorrect`(단계 레벨 incorrect는
    *단계 자가검산* 프레이밍과 자연 정합). 이 bool들을 *그대로* 기존 `recommend_coaching`에
    넘긴다(결정 함수 시그니처·로직 불변). `solution_steps` 미제공·전이 0개면 `verification=None`·
    신호는 기존 텍스트 레벨 그대로 — **모든 기존 동작 완전 불변**(하위호환).

    **redaction**: `verify_solution` 결과(`solution_verification`)의 `reason`('동치 아님 —
    SymPy: before ≠ after')은 *학생 자신의 단계*(solution_steps 입력)에 대한 검증 사유라
    노출이 안전하다 — 정답/본문이 아니다(`verify_step`은 정답을 알지도 못함). `SolutionCoaching`
    에 채워 L5가 단계별 검산 UI(has_incorrect·first_incorrect_index)를 그릴 수 있게 한다.

    `problem_id`·`expected_answer`(slice 64)는 *step shadow 진단 맥락*으로만 쓰여 반환
    `SolutionCoaching`을 *바꾸지 않는다*(비노출 불변). `expected_answer`는 호출자(api 계층)가
    서버 DB에서 조회해 넘기며 요청/응답엔 결코 싣지 않는다 — student-facing이면 정답 누출.
    """
    signal = validate_response(
        validator if validator is not None else arithmetic_validator(),
        student_solution,
    )
    # 단계 결선 — L5가 분해한 단계 시퀀스가 있고 전이가 1개 이상(len≥2)일 때만 verify_solution
    # 호출(분해는 L5 책임·범위 밖). 미제공·전이 0개면 None(기존 텍스트 레벨 동작 완전 불변).
    verification: SolutionVerificationResult | None = None
    if solution_steps is not None and len(solution_steps) >= 2:
        verification = verify_solution(solution_steps, solution_step_types)

    # 신호 결합은 *추가적(OR)* — 텍스트 레벨 신호를 약화하지 않고 단계 레벨 incorrect만 더한다.
    step_incorrect = verification is not None and verification.has_incorrect
    arithmetic_error = (signal is not None) or step_incorrect
    # 다단계 대수 슬립(kind="solution")이면 verify 발화를 *단계 자가검산*으로 변형한다(slice 61).
    # 단계 레벨 incorrect도 *단계 자가검산* 프레이밍과 자연 정합 → 같은 변형으로 OR 결합한다.
    # L3 kind→순수 bool 환산은 *오케스트레이터만* 수행(L4 recommend_coaching은 kind를 모름).
    verify_steps = (signal is not None and signal.kind == "solution") or step_incorrect
    trigger = recommend_coaching(
        bkt_mastery,
        irt_theta,
        arithmetic_error=arithmetic_error,
        verify_steps=verify_steps,
        discrepancy_tol=discrepancy_tol,
        mastery_threshold=mastery_threshold,
    )
    result = SolutionCoaching(
        trigger=trigger,
        arithmetic_error=arithmetic_error,
        validation_signal=signal.reason if signal is not None else None,
        error_kind=signal.kind if signal is not None else None,
        error_span=signal.span if signal is not None else None,
        solution_verification=verification,
    )
    # 중간 step 등가성 shadow 관측(slice 63) — fire-and-forget·반환 무반영(비노출·비차단).
    # `result`를 *바꾸지 않는다* — observe_step_breaks는 None을 반환하고 로그로만 sink한다.
    # slice 64: 문항 맥락(problem_id·expected_answer)을 *shadow 로그에만* 주입(진단 라벨 정확도
    # 측정용). `result`엔 싣지 않는다 — 특히 expected_answer는 student-facing이면 정답 누출.
    observe_step_breaks(student_solution, problem_id=problem_id, expected_answer=expected_answer)
    return result


__all__ = [
    "SlipKind",
    "SolutionCoaching",
    "recommend_coaching_for_solution",
]
