"""Tier1 수치 답 검산기 — WH-S 솔버 하네스 S0 슬라이스 1+2(설계 §4 Tier1).

설계안(`docs/architecture/03b_wh_s_solver_harness.md`) §4 검증기 스택의 **Tier1(수치 검증)**:
"구한 답을 *원 조건에 대입*, 랜덤 수치 샘플 + 경계값/특이점 검사". 커버리지가 가장 넓되
신뢰도가 가장 낮은 계층이다 — **단독 사용 금지**(과정이 틀려도 답만 맞으면 통과시킴, §4 한계).

`verify_step`(`l3/verify_step.py`)의 *단계 동치*(expr_before ≡ expr_after)와는 *다른 질문*을
묻는다: verify_step은 "한 변형이 동치인가", verify_answer는 "구한 답이 *원 조건을 만족하는가*".
전자는 Tier2(기호 단계 동치), 후자가 Tier1(수치 답 검산)이다. 최종 판정은 둘을 **결합**해야
하며(§4 판정 규칙), 그 combiner는 `whs/verdict.py`다 — 본 모듈은 Tier1 *단독*이라 그 자체로
최종 통과를 의미하지 않는다.

표기 계약·권위 경계(docs/architecture/notation_contract.md): SymPy(verify_step·verify_answer)는 수식
동치·정오 판정 단일 권위다. 웹 mathjs는 렌더·수치 평가 전용(동치 판정 미관여) — 공유 표기 계약은
`data/notation_contract.json` golden test로 양측 교차검증한다.

커버하는 조건 형태(Tier1 §4):
  - **등식**(`=`/`Eq`/항등식): `lhs - rhs`를 잔차로 만들어 |residual|<tol 검산.
    함수 동치 "f(x)=g(x) 항등식"(예 `sin(x)**2 + cos(x)**2 = 1`)도 이 등식 + 자유변수
    샘플링 경로로 자동 커버된다(치환 후 잔차가 자유변수로 남아 샘플링).
  - **부등식·≠ 관계**(`>`,`<`,`>=`,`<=`,`!=`): 잔차 `lhs - rhs`를 수치 평가한 뒤 *관계 연산자
    진리값*으로 판정(아래 _eval_relation). 등식 잔차 경로와 별개의 *진리값 평가 경로*다.
  - **연립(여러 조건 AND)**: `conditions`에 `Sequence[str]`을 주면 각 조건을 검산 후 AND 결합
    (전부 pass→pass·하나라도 fail→fail·fail 없고 일부 unverifiable→unverifiable·빈 시퀀스→
    unverifiable). 단일 `str`은 기존과 *완전 동일* 동작(하위호환).

핵심 설계 계약:
  - **대입·잔차**: `condition`을 관계로 sympify하고, 등식이면 `lhs - rhs`를 잔차(residual)로,
    부등식이면 (잔차, 연산자) 쌍으로 파싱한 뒤 `answer` 치환맵을 대입한다.
  - **자유변수 없는 잔차** → 직접 수치 평가: 등식은 |residual|<tol → pass·명백히 ≠0 → fail.
    부등식은 잔차를 연산자 진리값(tol 경계 감안)으로 평가 → True→pass·False→fail.
  - **자유변수 있는 잔차**(파라미터 문제·예: `2*a*x = b`, `x = b/(2*a)`) → **수치 샘플링**
    (Tier1의 핵심): *고정 시드* 난수 샘플 + 경계값을 자유변수에 대입해 수치 평가 — 전부
    만족이면 pass·어디서든 명백히 위반이면 fail·유효 샘플이 하나도 없으면 unverifiable.
  - **정직성(verify_step 상속·CLAUDE.md "확실하지 않으면 모른다")**: 파싱 불가·관계 아님·예외·
    유효 샘플 0은 *절대 pass로 위장하지 않고* `unverifiable`로 보수 처리한다. 0으로 나눔 등
    특이점 샘플은 *건너뛰되*(유효 샘플에서 제외), 유효 샘플이 0이면 unverifiable. 부등식·연립도
    동일 — 판정 불가·일부 미정은 pass로 위장하지 않는다(연립은 보수적으로 unverifiable).
  - **결정론**: 샘플은 *고정 시드*에서 뽑아 같은 입력에 같은 결과를 보장한다(재현·디버그).

Tier1 정직성(설계 §4): `pass`는 "샘플 점들에서 조건을 만족"이지 *증명이 아니다*(신뢰도 최저).
따라서 Tier1 단독 pass를 최종 통과로 쓰지 않고, 반드시 Tier2(`verify_solution`)와 결합한다
(`whs/verdict.final_verdict`). 본 모듈은 그 *재료*만 만든다. 부등식·연립도 마찬가지로 Tier1
단독으로는 최종 통과를 의미하지 않는다.

정직 스코프(범위 밖 — 후속):
  - **베이스라인 풀이율 측정**(시드 모델 Ollama·Phaiakes9 필요)은 이 환경 밖·후속이다.
  - **솔버 루프·`solution_nodes`/저장소 스키마**(S1+·향후 alembic 마이그레이션)도 범위 밖이다.
  - **Tier3 형식 검증**(Lean4·증명 문제)·**PRM**도 후속이다(§4·§9 로드맵).
  - 본 슬라이스는 *Tier1 수치 검산기*(등식·부등식·연립) + 판정 combiner(`whs/verdict.py`)만이다.
"""

from __future__ import annotations

import random
from collections.abc import Mapping, Sequence
from typing import Literal

import sympy
from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "AnswerVerdict",
    "verify_answer",
]


# 결정론을 위한 *고정 시드* — 같은 입력에 같은 샘플(재현·디버그). 비결정 난수 금지.
_SAMPLE_SEED = 20260613

# 자유변수 샘플링 시 항상 평가하는 경계값(특이점·부호 전환·0 근방을 의도적으로 포함).
# Tier1 §4 "경계값/특이점 검사" — 0·±1·작은 값·큰 값에서 조건이 깨지는지 본다.
_BOUNDARY_VALUES: tuple[float, ...] = (
    0.0,
    1.0,
    -1.0,
    0.5,
    -0.5,
    2.0,
    -2.0,
    10.0,
    -10.0,
)

# 난수 샘플 범위 — 0 근방 특이점은 _BOUNDARY로 따로 보고, 여기선 일반적 비특이 점을 본다.
_SAMPLE_LOW = -7.0
_SAMPLE_HIGH = 7.0


class AnswerVerdict(BaseModel):
    """`verify_answer`(Tier1 수치 답 검산)의 결과 — 3상태 + 사유·평가 샘플 수.

    `state`는 항상 3상태 중 하나다. `pass`는 "샘플 점들에서 조건을 만족"이지 *증명이 아니다*
    (Tier1 신뢰도 최저·단독 사용 금지·§4). `reason`은 fail/unverifiable의 한국어 사유
    (pass이면 None). `samples_checked`는 실제 *유효하게 평가한* 샘플 수(특이점으로 건너뛴
    샘플은 제외)다 — 디버그·신뢰도 가늠용.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    state: Literal["pass", "fail", "unverifiable"] = Field(
        description=(
            "Tier1 3상태 — pass(샘플 점에서 조건 만족·증명 아님)·fail(조건 위반 확정)·"
            "unverifiable(파싱 불가·관계 아님·유효 샘플 0 등 보수적 회피)."
        ),
    )
    reason: str | None = Field(
        default=None,
        description="fail/unverifiable 사유(한국어). pass이면 None(사유 불필요).",
    )
    samples_checked: int = Field(
        description="실제 유효하게 평가한 샘플 수(특이점으로 건너뛴 샘플 제외·디버그용).",
    )


def _pass(samples_checked: int) -> AnswerVerdict:
    """pass 결과 조립(샘플 점 만족·증명 아님·Tier2 결합 필수)."""
    return AnswerVerdict(state="pass", reason=None, samples_checked=samples_checked)


def _fail(reason: str, samples_checked: int) -> AnswerVerdict:
    """fail 결과 조립 — 조건 위반이 *확정*된 경우만(보수적·거짓 fail 회피)."""
    return AnswerVerdict(state="fail", reason=reason, samples_checked=samples_checked)


def _unverifiable(reason: str, samples_checked: int = 0) -> AnswerVerdict:
    """unverifiable 결과 조립 — 정직 회피의 단일 출구(절대 pass 위장 금지)."""
    return AnswerVerdict(state="unverifiable", reason=reason, samples_checked=samples_checked)


# 부등식·≠ 관계 연산자 — 잔차(lhs-rhs) 진리값 평가 경로에서 쓰는 연산자 집합.
# 등식("==")은 잔차==0 경로(별도)라 여기 포함하지 않는다.
_RELATION_OPS: frozenset[str] = frozenset({">", "<", ">=", "<=", "!="})


def _parse_condition(condition: str) -> tuple[sympy.Expr, str]:
    """condition 문자열을 (잔차 식, 관계 연산자)로 파싱.

    반환 연산자:
      - `"=="` — 등식(조건 만족 ⇔ residual == 0). `=`/`Eq`/`Equality`, 또는 등호가 없는 단일
        식("== 0" 으로 해석). 잔차는 `lhs - rhs`(단일 식이면 식 자체).
      - `">"`,`"<"`,`">="`,`"<="`,`"!="` — 부등식·≠. 잔차는 `lhs - rhs`이며, 진리값은 잔차를
        수치 평가해 *연산자*로 판정한다(`_eval_relation`). 별도의 진리값 평가 경로다.

    파싱 불가는 예외를 일으켜 호출부가 unverifiable로 처리한다(보수적·pass 위장 금지).
    """
    text = condition.strip()
    if not text:
        raise ValueError("빈 condition")

    # `!=`(≠)는 파이썬 비교라 sympify가 bool로 접어버린다 — SymPy `Ne(lhs, rhs)`로 명시 변환.
    if "!=" in text:
        lhs_text, rhs_text = text.split("!=", 1)
        lhs = sympy.sympify(lhs_text, convert_xor=True)
        rhs = sympy.sympify(rhs_text, convert_xor=True)
        return sympy.sympify(lhs - rhs), "!="

    # `=`(단일 등호, `==`/`<=`/`>=` 아님)를 등식 잔차로 변환. `==`는 파이썬 비교라 따로 처리.
    if (
        "=" in text
        and "==" not in text
        and "<=" not in text
        and ">=" not in text
        and "<" not in text
        and ">" not in text
    ):
        lhs_text, rhs_text = text.split("=", 1)
        lhs = sympy.sympify(lhs_text, convert_xor=True)
        rhs = sympy.sympify(rhs_text, convert_xor=True)
        return sympy.sympify(lhs - rhs), "=="

    parsed = sympy.sympify(text, convert_xor=True)
    if isinstance(parsed, sympy.Equality):
        return sympy.sympify(parsed.lhs - parsed.rhs), "=="
    # 부등식(StrictGreaterThan/GreaterThan/StrictLessThan/LessThan) — 잔차 + 연산자로 환원.
    if isinstance(parsed, sympy.core.relational.Relational):
        rel_op = parsed.rel_op
        if rel_op in _RELATION_OPS:
            return sympy.sympify(parsed.lhs - parsed.rhs), rel_op
        # 그 외 관계(예상 밖) — 보수적 거부.
        raise ValueError(f"지원하지 않는 관계 연산자: {rel_op}")
    if isinstance(parsed, sympy.logic.boolalg.Boolean):
        # sympify가 이미 진리값(BooleanTrue/False)으로 접은 경우 — 자유변수 없는 관계라 잔차
        # 모델로 환원 불가(보수적 거부). 호출부가 unverifiable 처리.
        raise ValueError("관계가 상수 진리값으로 환원 — Tier1 잔차 모델 적용 불가")
    # 등식 기호가 없는 단일 식 → 식 == 0을 묻는 잔차로 본다.
    return parsed, "=="


def _eval_relation(magnitude: float, op: str, tol: float) -> bool | None:
    """부등식 잔차(lhs-rhs의 *실수값* `magnitude`)를 연산자 진리값으로 판정 — tol 경계 감안.

    True(조건 만족)·False(조건 위반)·None(경계 모호·판정 보류)의 3값을 돌린다. tol 밴드(|값|≤tol)
    는 *경계*로 보아: 엄격(`>`,`<`)은 경계에서 명백한 True/False가 아니므로 None(과도한 false 판정
    회피)·등호(`>=`,`<=`)는 경계를 만족(True)으로·`!=`는 경계(≈0)를 위반(False)으로 본다.
    """
    if op == ">":
        if magnitude > tol:
            return True
        if magnitude < -tol:
            return False
        return None  # 경계(≈0) — 엄격 부등식이라 모호·보류.
    if op == "<":
        if magnitude < -tol:
            return True
        if magnitude > tol:
            return False
        return None
    if op == ">=":
        if magnitude > -tol:
            return True  # 경계 포함(잔차 ≥ -tol).
        return False
    if op == "<=":
        if magnitude < tol:
            return True  # 경계 포함(잔차 ≤ tol).
        return False
    if op == "!=":
        return abs(magnitude) > tol  # 같으면(≈0) 위반(False)·다르면 만족(True).
    raise ValueError(f"알 수 없는 관계 연산자: {op}")


def _eval_numeric(expr: sympy.Expr, tol: float) -> bool | None:
    """자유변수 없는 잔차 식을 수치 평가 — |값|<tol→True·확정 ≠0→False·평가 불가→None.

    복소수·무한·NaN 등은 *평가 불가(None)* 로 보수 처리한다(pass/fail로 위장 금지).
    """
    try:
        value = complex(expr.evalf())
    except (TypeError, ValueError, AttributeError):
        return None
    # NaN·무한 — 평가 불가.
    if value != value or abs(value.real) == float("inf") or abs(value.imag) == float("inf"):
        return None
    # 허수부가 유의미하면 실수 조건 평가 불가(복소 — 보수적 None).
    if abs(value.imag) > tol:
        return None
    return abs(value.real) < tol


def verify_answer(
    conditions: str | Sequence[str],
    answer: Mapping[str, str],
    *,
    n_samples: int = 8,
    tol: float = 1e-9,
) -> AnswerVerdict:
    """Tier1 수치 답 검산 — 답을 원 조건(들)에 대입해 만족 여부를 3상태로 판정(순수·결정론·DB 0).

    설계 §4 Tier1. 첫 인자는 *단일 조건* `str`(하위호환·기존 동작 불변) 또는 *연립* `Sequence[str]`
    (여러 조건 AND)이다. `answer`는 치환맵(예 {"x":"3"}·{"x":"b/(2*a)"}·{"x":"2","y":"1"}).

    지원 조건 형태:
      - **등식**(예 "x**2 - 5*x + 6 = 0"·"2*a*x = b"·"Eq(x**2, 9)") — `lhs - rhs` 잔차==0 검산.
        함수 동치 항등식("f(x)=g(x)"·예 "sin(x)**2 + cos(x)**2 = 1")도 등식 + 자유변수 샘플링으로
        자동 커버(치환 후 잔차가 자유변수로 남아 샘플링 경로).
      - **부등식·≠**(예 "x > 0"·"x**2 >= 4"·"a*x <= 0"·"x != 1") — 잔차 수치값을 연산자 진리값
        (tol 경계 감안)으로 판정.
      - **연립**(예 ["x+y=3","x-y=1"]) — 각 조건 검산 후 AND: 전부 pass→pass·하나라도 fail→fail·
        fail 없고 일부 unverifiable→unverifiable(보수적)·빈 시퀀스→unverifiable(검증할 조건 없음).

    단일 조건 판정 흐름(`_verify_single`):
      1. condition을 (잔차, 연산자)로 파싱(`convert_xor=True`로 `^`=거듭제곱). 파싱 불가·미지원
         관계 → **unverifiable**(보수적·pass 위장 금지).
      2. answer 치환맵을 잔차에 대입.
      3. **잔차에 자유변수 없음** → 직접 수치 평가: 등식은 |residual|<tol→pass·≠0→fail·평가 불가
         →unverifiable. 부등식은 잔차값을 연산자 진리값으로(True→pass·False→fail·경계 모호/평가
         불가→unverifiable).
      4. **잔차에 자유변수 있음**(파라미터 문제) → **수치 샘플링**(Tier1 핵심): 자유변수에
         *고정 시드* 난수 n_samples + 경계값(0·±1·작은·큰 값)을 대입해 평가 —
         · 모든 *유효* 샘플에서 만족 → **pass**
         · 어느 유효 샘플에서든 명백히 위반 → **fail**(거짓 답을 한 점으로 반증)
         · 유효 샘플이 하나도 없음(전부 특이점·복소·경계 모호) → **unverifiable**.
         0으로 나눔 등 특이점 샘플은 *건너뛴다*(유효 샘플에서 제외).

    `samples_checked`(연립): 각 조건이 유효하게 평가한 샘플 수의 *합산*(전체 검증 노력의 척도).
    `reason`(연립): fail/unverifiable이 *어느 조건*에서 났는지 인덱스·사유를 표기(디버그).

    Tier1 정직성(§4): `pass`는 "샘플 점에서 조건 만족"이지 *증명이 아니다*(신뢰도 최저).
    Tier1 단독 pass를 최종 통과로 쓰지 않고 반드시 Tier2와 결합한다(`whs/verdict.final_verdict`).
    파싱 불가·미지원 관계·평가 불가·유효 샘플 0·연립 일부 미정은 *절대 pass로 위장하지 않고*
    unverifiable로 보수 처리한다(verify_step 정직성 상속). 부등식·연립도 동일.

    범위 밖(후속): 베이스라인 풀이율 측정(시드 모델)·솔버 루프·저장소 스키마·PRM·Tier3(§9).
    """
    # 단일 str(하위호환) — 기존 단일 조건 경로와 *완전 동일*(직전 슬라이스 회귀 0).
    if isinstance(conditions, str):
        return _verify_single(conditions, answer, n_samples=n_samples, tol=tol)

    # 연립(Sequence[str]) — 각 조건 검산 후 AND 결합.
    condition_list = list(conditions)
    if not condition_list:
        # 빈 시퀀스 — 검증할 조건이 없음. pass로 위장하지 않고 보수적 unverifiable.
        return _unverifiable("연립 조건 없음(빈 시퀀스) — 검증할 것 없음·안전 회피")

    total_samples = 0
    first_unverifiable: str | None = None
    for index, condition in enumerate(condition_list):
        verdict = _verify_single(condition, answer, n_samples=n_samples, tol=tol)
        total_samples += verdict.samples_checked
        if verdict.state == "fail":
            # 어느 한 조건이라도 위반이면 연립 전체 fail(답이 조건 하나를 깸).
            return _fail(
                f"연립 조건 {index}번 위반 — {verdict.reason}",
                samples_checked=total_samples,
            )
        if verdict.state == "unverifiable" and first_unverifiable is None:
            # 첫 미정 조건만 기록(fail이 나오면 그쪽이 우선이라 보류).
            first_unverifiable = f"연립 조건 {index}번 판정 불가 — {verdict.reason}"

    if first_unverifiable is not None:
        # fail은 없으나 일부 미정 → 보수적 unverifiable(전부 pass라고 위장하지 않음).
        return _unverifiable(first_unverifiable, samples_checked=total_samples)

    # 전부 pass — 연립 전체 pass(단, 샘플 점 만족이지 증명 아님·Tier2 결합 필수).
    return _pass(samples_checked=total_samples)


def _verify_single(
    condition: str,
    answer: Mapping[str, str],
    *,
    n_samples: int,
    tol: float,
) -> AnswerVerdict:
    """단일 조건(등식 또는 부등식) Tier1 검산 — `verify_answer`의 단일-조건 코어(순수·결정론).

    등식이면 잔차==0, 부등식이면 잔차 진리값(`_eval_relation`)으로 판정한다. 자유변수가 남으면
    고정 시드 샘플링(`_sample_parametric`). 모든 정직성 계약(파싱 불가·평가 불가·유효 샘플 0 →
    unverifiable·pass 위장 금지)을 보존한다.
    """
    # ① condition → (잔차, 연산자). 파싱 불가·미지원 관계는 보수적 unverifiable.
    try:
        residual, op = _parse_condition(condition)
    except Exception:  # noqa: BLE001 — 파싱·미지원 관계는 보수적 unverifiable(pass 위장 금지)
        return _unverifiable("condition 파싱 불가/미지원 관계 — 검증 안전 회피")

    # ② answer 치환맵 대입(키·값 모두 sympify). 치환 실패는 보수적 unverifiable.
    try:
        substitutions: dict[sympy.Symbol, sympy.Expr] = {
            sympy.Symbol(var): sympy.sympify(val_text, convert_xor=True)
            for var, val_text in answer.items()
        }
        substituted = sympy.sympify(residual.subs(substitutions))
    except Exception:  # noqa: BLE001 — 치환 실패도 보수적 unverifiable
        return _unverifiable("answer 치환 불가 — 검증 안전 회피")

    free_symbols = sorted(substituted.free_symbols, key=str)

    # ③ 자유변수 없음 → 직접 수치 평가(파라미터 없는 일반 답).
    if not free_symbols:
        if op == "==":
            verdict = _eval_numeric(substituted, tol)
            if verdict is True:
                return _pass(samples_checked=1)
            if verdict is False:
                return _fail(f"조건 위반 — 잔차 ≠ 0: {substituted}", samples_checked=1)
            return _unverifiable("수치 평가 불가(복소/NaN 등) — 검증 안전 회피")
        # 부등식 — 잔차 실수값을 연산자 진리값으로 판정.
        magnitude = _eval_relation_residual(substituted, tol)
        if magnitude is None:
            return _unverifiable("부등식 잔차 수치 평가 불가(복소/NaN 등) — 검증 안전 회피")
        truth = _eval_relation(magnitude, op, tol)
        if truth is True:
            return _pass(samples_checked=1)
        if truth is False:
            return _fail(f"부등식 조건 위반({op}) — 잔차 {magnitude}", samples_checked=1)
        return _unverifiable(f"부등식 경계 모호({op}) — 검증 안전 회피")

    # ④ 자유변수 있음(파라미터 문제) → 수치 샘플링(Tier1 핵심·고정 시드 결정론).
    return _sample_parametric(substituted, free_symbols, op, n_samples=n_samples, tol=tol)


def _eval_relation_residual(expr: sympy.Expr, tol: float) -> float | None:
    """자유변수 없는 부등식 잔차를 *실수값*으로 수치 평가 — 복소/NaN/무한이면 None(보수적).

    `_eval_numeric`(등식 bool 판정)과 달리 부등식은 부호가 필요해 *실수값 자체*를 돌린다.
    """
    try:
        value = complex(expr.evalf())
    except (TypeError, ValueError, AttributeError):
        return None
    if value != value or abs(value.real) == float("inf") or abs(value.imag) == float("inf"):
        return None
    if abs(value.imag) > tol:
        return None  # 복소 — 실수 부등식 평가 불가(보수적).
    return value.real


def _evaluate_point(
    expr: sympy.Expr,
    substitution: dict[sympy.Symbol, sympy.Float],
    tol: float,
) -> float | None:
    """한 대입점에서 잔차를 수치 평가 — *부호 있는 실수부* 반환·특이점/복소/NaN/무한이면 None.

    부호를 보존해 부등식 방향 판정(`_eval_relation`)이 가능하다. 등식 경로는 호출부에서
    `abs(...)`를 취해 기존 동작(|잔차|)을 그대로 보존한다.
    """
    try:
        value = complex(sympy.sympify(expr.subs(substitution)).evalf())
    except (TypeError, ValueError, AttributeError, ZeroDivisionError):
        return None  # 특이점(0 나눔 등)·평가 불가 — 유효 샘플 아님.
    if value != value or abs(value.real) == float("inf"):
        return None  # NaN·무한 — 특이점으로 간주(보수적).
    if abs(value.imag) > tol:
        return None  # 복소 — 실수 조건 평가 불가.
    return value.real


def _classify_point(residual: float, op: str, tol: float) -> bool | None:
    """한 점의 *부호 있는 잔차*를 (조건 만족 True·위반 False·모호 None)으로 분류.

    등식(`==`)은 |잔차|<tol → 만족·아니면 위반. 부등식은 `_eval_relation`에 위임(tol 경계 감안).
    경계 모호(None)는 유효 샘플로 세지 않고 *건너뛴다*(pass/fail 위장 금지).
    """
    if op == "==":
        return abs(residual) < tol
    return _eval_relation(residual, op, tol)


def _sample_parametric(
    expr: sympy.Expr,
    free_symbols: list[sympy.Symbol],
    op: str,
    *,
    n_samples: int,
    tol: float,
) -> AnswerVerdict:
    """파라미터(자유변수) 잔차를 *고정 시드* 샘플 + 경계값으로 평가 — Tier1 샘플링 코어.

    각 자유변수에 (경계값 전부) + (n_samples개 난수)를 대입해 수치 평가하고, `op`에 따라 한 점의
    만족/위반/모호를 분류한다(`_classify_point`). 어느 유효 샘플에서든 *위반*이면 즉시 **fail**(한
    반례로 거짓 답 반증). 0으로 나눔 등 특이점·복소·경계 모호는 *건너뛴다*(유효 샘플 아님). 모든
    유효 샘플에서 만족이면 **pass**·유효 샘플이 하나도 없으면 **unverifiable**.

    등식(`op=="=="`)은 종전과 *동일*하게 |잔차|<tol 판정이라 기존 동작이 보존된다(하위호환).

    결정론: `random.Random(_SAMPLE_SEED)`로 시드를 고정해 같은 입력에 같은 샘플을 보장한다.
    다변수일 때는 변수별 *서로 다른* 점도 평가해, 상관 잔차를 한 점이 우연히 만족시키는 위장을
    차단한다.
    """
    rng = random.Random(_SAMPLE_SEED)
    valid_samples = 0

    # (1) 단일 점 대입(모든 자유변수에 같은 값) — 경계값 + 난수.
    sample_points: list[float] = list(_BOUNDARY_VALUES)
    sample_points.extend(rng.uniform(_SAMPLE_LOW, _SAMPLE_HIGH) for _ in range(n_samples))
    for point in sample_points:
        substitution = {symbol: sympy.Float(point) for symbol in free_symbols}
        residual = _evaluate_point(expr, substitution, tol)
        if residual is None:
            continue  # 특이점·평가 불가 — 건너뜀.
        satisfied = _classify_point(residual, op, tol)
        if satisfied is None:
            continue  # 부등식 경계 모호 — 건너뜀(유효 샘플 아님).
        valid_samples += 1
        if not satisfied:
            return _fail(
                f"파라미터 샘플 {point} 에서 조건 위반({op})",
                samples_checked=valid_samples,
            )

    # (2) 다변수 — 변수별 서로 다른 점도 평가(상관 잔차의 우연한 만족 위장 차단).
    if len(free_symbols) > 1:
        for _ in range(n_samples):
            substitution = {
                symbol: sympy.Float(rng.uniform(_SAMPLE_LOW, _SAMPLE_HIGH))
                for symbol in free_symbols
            }
            residual = _evaluate_point(expr, substitution, tol)
            if residual is None:
                continue
            satisfied = _classify_point(residual, op, tol)
            if satisfied is None:
                continue
            valid_samples += 1
            if not satisfied:
                return _fail(
                    f"다변수 파라미터 샘플에서 조건 위반({op})",
                    samples_checked=valid_samples,
                )

    # 유효 샘플이 하나도 없으면 판정 불가(전부 특이점·복소·경계 모호) — pass 위장 금지.
    if valid_samples == 0:
        return _unverifiable("유효 샘플 0(전부 특이점/복소/경계 모호) — 검증 안전 회피")

    # 모든 유효 샘플에서 조건 만족 → pass(단, 샘플 점 만족이지 증명 아님·Tier2 결합 필수).
    return _pass(samples_checked=valid_samples)
