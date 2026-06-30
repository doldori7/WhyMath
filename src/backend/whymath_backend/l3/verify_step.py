"""풀이 *한 단계* 3상태 검증 도구 — WH-1 1단계 슬라이스 2 `verify_step` 도구화(§3.1).

설계안 §3.1 "verify_step": 학생 풀이의 *한 단계*(expr_before → expr_after)가 올바른 변형인지
**3상태**로 판정한다 — `correct`/`incorrect`/`unverifiable`. 기존
`l3/pregenerate/validator.py`의 게이트(`SymPyArithmeticValidator` 등)는 솔루션 텍스트 *전체*를
훑어 *거짓 등식*만 보는 **2-state**(거짓이면 신호·아니면 None)라, "한 단계가 올바른 변형인가"를
3상태로 묻는 verify_step과 *용도가 다르다*. 본 모듈은 그 격상판의 *순수 primitive*다.

표기 계약·권위 경계(math_dsl_remediation_design.md·docs/architecture/notation_contract.md): SymPy는
이 시스템의 *수식 동치·정오 판정 단일 권위*다. 웹 mathjs(`graph2dSpec.js`·`mathExpr.js`)는 렌더·수치
평가 전용이며 동치 판정에 관여하지 않는다. 두 파서가 같은 canonical 표기(명시 `*`·caret `^`)를 같은
수치로 해석함은 golden test로 교차검증한다(`tests/backend/l3/test_notation_contract.py` ↔
`src/web/graphing-calculator/test/notation_contract.test.js`·공유 `data/notation_contract.json`).

핵심 설계 계약:
  - **식 변형(대수)**: SymPy *심볼릭 동치* 검증 → `correct`/`incorrect`. 자유변수가 있어도
    된다("2(x+1)" ≡ "2x+2"). 기존 `_equality_is_false`는 *numeric-only*(free_symbols 있으면
    skip)라 verify_step에 *재사용하지 않는다* — 같은 `sympify(convert_xor=True)` +
    `simplify().is_zero` *관용구만* 차용해 fresh로 구현한다(심볼릭 동치를 *원하므로*).
  - **서술형·증명·보조선 기하·경우 나누기 등 비대수 단계**: `unverifiable`. SymPy 검증 자체가
    부적절하므로 시도하지 않고, step_type을 기록해 *검증 불가 단원에서 교착하지 않게*(정직).
  - **정직성(CLAUDE.md "확실하지 않으면 모른다")**: 판정 불가(SymPy `is_zero is None`)·파싱
    불가·예외·빈 입력은 *절대 `correct`로 위장하지 않고* `unverifiable`로 보수 처리한다.
    `unverifiable`이면 evidence_weight를 0.5로 할인한다(설계 §3.1).

정직 스코프(범위 밖 — 후속 슬라이스):
  - **PRM 점수**(PRM800K 가중치·§3.1 후반)는 *0단계 과제*라 본 슬라이스 범위 밖이다(여긴
    SymPy 결정론 3상태만).
  - **step 파싱**(학생 솔루션 텍스트 → (expr_before, expr_after) 단계 쌍 분해)도 후속이다 —
    본 모듈은 이미 분해된 *한 쌍*을 입력으로 받는 도구 primitive다.
  - **coach 파이프라인 결선**(`api/coach.py`의 `recommend_coaching_for_solution`·검산결과 적재
    등과의 배선)도 후속이다. 기존 validator/match_gate/coach/harness는 본 슬라이스에서 *불변*이며
    verify_step은 *신규 좌석*이다(기존 미접촉).
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from whymath_backend.l3.symbolic_equivalence import IdentityVerdict, identity_status
from whymath_backend.schema.enums import StepType

__all__ = [
    "VerifyStepResult",
    "VerifyStepState",
    "verify_step",
]


class VerifyStepState(str, Enum):
    """풀이 한 단계 검증의 3상태 — §3.1 verify_step.

    `str, Enum`이라 멤버가 문자열 값과 동등 비교된다(`schema/enums.py` 컨벤션 답습).
    """

    correct = "correct"
    """대수 단계가 SymPy 심볼릭 동치로 *참* — 올바른 변형(evidence_weight 1.0)."""

    incorrect = "incorrect"
    """대수 단계가 *항등식 아님*으로 증명 — 동치 아닌 변형(0-아님 확정 또는 0-아닌 다항식·1.0)."""

    unverifiable = "unverifiable"
    """검증 불가 — 비대수 단계·판정 불가·파싱 불가·빈 입력(evidence_weight 0.5·정직 회피)."""


# correct/incorrect는 결정론 검증이라 충분한 증거(가중치 1.0)·unverifiable은 *판정을 못 한*
# 상태라 절반으로 할인(설계 §3.1) — 후속 PRM·다중풀이 집계가 이 가중치를 곱해 쓴다.
_WEIGHT_DECISIVE = 1.0  # correct·incorrect — 결정론 판정 완료.
_WEIGHT_UNVERIFIABLE = 0.5  # unverifiable — 판정 불가, 증거력 할인.

# SymPy 검증을 시도하지 *않는* 비대수 step_type — 서술형·경우 나누기·보조선 기하 등.
# 이 단계들은 식 변형이 아니라 대수 동치로 옳고 그름을 가릴 수 없다(unverifiable·정직).
# `계산`·`검산`은 대수(SymPy 검증 가능)라 이 집합에 *없다*(아래 동치 경로로 간다).
_NON_ALGEBRAIC_STEP_TYPES: frozenset[StepType] = frozenset(
    {StepType.조건해석, StepType.케이스분류, StepType.그래프스케치}
)


class VerifyStepResult(BaseModel):
    """`verify_step`의 결과 — 3상태 판정 + 사유·증거 가중치 + 입력 step_type 전파.

    `state`는 항상 채워진다(3상태 중 하나). `reason`은 incorrect/unverifiable일 때 *왜*인지
    한국어 사유(correct이면 None — 사유 불필요). `evidence_weight`는 correct/incorrect=1.0·
    unverifiable=0.5(설계 §3.1 할인). `step_type`은 입력을 그대로 전파(하류가 어떤 종류의
    단계였는지 안다·None 가능).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    state: VerifyStepState = Field(
        description="3상태 판정 — correct(동치)·incorrect(거짓 증명)·unverifiable(검증 불가)."
    )
    step_type: StepType | None = Field(
        default=None,
        description="입력 step_type 전파(어떤 단계였는지). 미지정이면 None.",
    )
    reason: str | None = Field(
        default=None,
        description="incorrect/unverifiable 사유(한국어). correct이면 None(사유 불필요).",
    )
    evidence_weight: float = Field(
        description="증거 가중치 — correct/incorrect=1.0·unverifiable=0.5(설계 §3.1 할인).",
    )


def _unverifiable(reason: str, step_type: StepType | None) -> VerifyStepResult:
    """unverifiable 결과 조립 — 사유·step_type 전파·가중치 0.5(정직 회피의 단일 출구)."""
    return VerifyStepResult(
        state=VerifyStepState.unverifiable,
        step_type=step_type,
        reason=reason,
        evidence_weight=_WEIGHT_UNVERIFIABLE,
    )


def verify_step(
    expr_before: str,
    expr_after: str,
    step_type: StepType | None = None,
) -> VerifyStepResult:
    """풀이 한 단계(expr_before → expr_after)가 올바른 변형인지 *3상태*로 판정 — 순수·결정론·DB 0.

    설계안 §3.1 verify_step의 도구 primitive. 입력은 이미 분해된 *한 단계 쌍*(step 파싱은 후속).

    판정 로직:
      1. **비대수 step_type**(조건해석·케이스분류·그래프스케치) → 즉시 `unverifiable`. SymPy를
         *시도하지 않는다*(식 변형이 아니라 동치로 가릴 수 없음·검증 불가 단원 교착 방지·정직).
      2. **그 외**(계산·검산·step_type 미지정) → SymPy 심볼릭 동치 검증(자유변수 OK — "2(x+1)" ≡
         "2x+2"·`convert_xor=True`라 `^`=거듭제곱). 차이 `diff = before - after`에서:
         - **correct**: `expand(diff) == 0`(다항식 항등식이 0으로 환원) *또는*
           `simplify(diff).is_zero is True`(삼각 등 비다항 항등식)이면 올바른 변형(가중치 1.0).
         - **incorrect**: `simplify(diff).is_zero is False`(상수 차 등 0-아님 확정) *또는* `diff`가
           *같은 자유변수*의 다항식(`before.free_symbols == after.free_symbols`)인데 전개가 0이
           아니면 — 0-아닌 다항식은 영함수가 아니므로 *항등식 아님이 증명*된다(예: `(a+b)² ≠
           a²+b²`·`2ab`는 `a=b=1`에서 거짓). 가장 흔한 대수 오류를 잡는다(가중치 1.0).
         - **unverifiable**: 비다항이고 simplify 미정(예: `√(x²)` vs `x`는 정의역 의존)·**변수
           집합이 달라 맥락 의존**(예: 치환 `a`→`b+1`·산문이 심볼로 강제)·sympify 예외(파싱
           불가)·빈 입력 → *위장 없이* 보수 처리(거짓 incorrect 금지·가중치 0.5).

    정직성(CLAUDE.md "확실하지 않으면 모른다"): 판정 불가·파싱 불가·예외·빈 입력은 *절대*
    `correct`로 위장하지 않고 보수적으로 `unverifiable`로 떨어뜨린다(가중치 0.5 할인).

    범위 밖(후속): PRM 점수(PRM800K 가중치)·step 파싱(솔루션→단계 분해)·coach 파이프라인 결선.
    """
    # ① 비대수 단계 — SymPy 시도 없이 unverifiable(검증 불가 단원 교착 방지·정직).
    if step_type in _NON_ALGEBRAIC_STEP_TYPES:
        return _unverifiable(
            "비대수 단계(서술형/경우나누기/기하) — SymPy 검증 불가",
            step_type,
        )

    # 빈 입력은 동치 판정 불가 — 파싱 전에 보수적 unverifiable(빈 문자열을 0으로 오인 회피).
    if not expr_before.strip() or not expr_after.strip():
        return _unverifiable("빈 입력 — 검증 안전 회피", step_type)

    # ② 대수 단계(계산·검산·None) — 동치 권위 단일 primitive(`identity_status`·SymPy)에 위임한다.
    # 자유변수 OK·convert_xor로 ^=거듭제곱·같은 변수 다항 비항등식은 not_identity로 *증명*된다
    # ((a+b)²−(a²+b²)=2ab는 a=b=1에서 거짓·freshman's dream). 변수 집합이 다른 치환 등은 primitive
    # 가 undecidable로 보수 처리해 거짓 incorrect를 회피한다(정확성 #1).
    verdict = identity_status(expr_before, expr_after)
    if verdict is IdentityVerdict.identity:
        return VerifyStepResult(
            state=VerifyStepState.correct,
            step_type=step_type,
            reason=None,
            evidence_weight=_WEIGHT_DECISIVE,
        )
    if verdict is IdentityVerdict.not_identity:
        return VerifyStepResult(
            state=VerifyStepState.incorrect,
            step_type=step_type,
            reason=f"동치 아님 — SymPy: {expr_before} ≠ {expr_after}",
            evidence_weight=_WEIGHT_DECISIVE,
        )
    # parse_error(빈 입력은 위에서 거름·sympify 예외) → "파싱 불가" 표기로 보수.
    if verdict is IdentityVerdict.parse_error:
        return _unverifiable("SymPy 판정 불가/파싱 불가 — 검증 안전 회피", step_type)
    # undecidable — 항등성을 *증명도 반증도* 못 함(예: √(x²) vs x는 정의역 의존)·correct 위장 금지.
    return _unverifiable("SymPy 판정 불가 — 검증 안전 회피", step_type)
