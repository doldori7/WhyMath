"""Tier1 수치 답 검산기 — WH-S 솔버 하네스 S0 슬라이스 1(설계 §4 Tier1).

설계안(`docs/architecture/03b_wh_s_solver_harness.md`) §4 검증기 스택의 **Tier1(수치 검증)**:
"구한 답을 *원 조건에 대입*, 랜덤 수치 샘플 + 경계값/특이점 검사". 커버리지가 가장 넓되
신뢰도가 가장 낮은 계층이다 — **단독 사용 금지**(과정이 틀려도 답만 맞으면 통과시킴, §4 한계).

`verify_step`(`l3/verify_step.py`)의 *단계 동치*(expr_before ≡ expr_after)와는 *다른 질문*을
묻는다: verify_step은 "한 변형이 동치인가", verify_answer는 "구한 답이 *원 조건을 만족하는가*".
전자는 Tier2(기호 단계 동치), 후자가 Tier1(수치 답 검산)이다. 최종 판정은 둘을 **결합**해야
하며(§4 판정 규칙), 그 combiner는 `whs/verdict.py`다 — 본 모듈은 Tier1 *단독*이라 그 자체로
최종 통과를 의미하지 않는다.

핵심 설계 계약:
  - **대입·잔차**: `condition`을 관계(등식)로 sympify하고, 등식이면 `lhs - rhs`를 잔차(residual)로
    만든 뒤 `answer` 치환맵을 대입한다.
  - **자유변수 없는 잔차** → 직접 수치 평가: |residual| < tol → pass·명백히 ≠0 → fail.
  - **자유변수 있는 잔차**(파라미터 문제·예: `2*a*x = b`, `x = b/(2*a)`) → **수치 샘플링**
    (Tier1의 핵심): *고정 시드* 난수 샘플 + 경계값을 자유변수에 대입해 수치 평가 — 전부
    |·|<tol이면 pass·어디서든 명백히 ≠0이면 fail·유효 샘플이 하나도 없으면 unverifiable.
  - **정직성(verify_step 상속·CLAUDE.md "확실하지 않으면 모른다")**: 파싱 불가·관계 아님·예외·
    유효 샘플 0은 *절대 pass로 위장하지 않고* `unverifiable`로 보수 처리한다. 0으로 나눔 등
    특이점 샘플은 *건너뛰되*(유효 샘플에서 제외), 유효 샘플이 0이면 unverifiable.
  - **결정론**: 샘플은 *고정 시드*에서 뽑아 같은 입력에 같은 결과를 보장한다(재현·디버그).

Tier1 정직성(설계 §4): `pass`는 "샘플 점들에서 조건을 만족"이지 *증명이 아니다*(신뢰도 최저).
따라서 Tier1 단독 pass를 최종 통과로 쓰지 않고, 반드시 Tier2(`verify_solution`)와 결합한다
(`whs/verdict.final_verdict`). 본 모듈은 그 *재료*만 만든다.

정직 스코프(범위 밖 — 후속):
  - **베이스라인 풀이율 측정**(시드 모델 Ollama·Phaiakes9 필요)은 이 환경 밖·후속이다.
  - **솔버 루프·`solution_nodes`/저장소 스키마**(S1+·향후 alembic 마이그레이션)도 범위 밖이다.
  - **Tier3 형식 검증**(Lean4·증명 문제)·**PRM**도 후속이다(§4·§9 로드맵).
  - 본 슬라이스는 *Tier1 수치 검산기* + 판정 combiner(`whs/verdict.py`)만이다.
"""

from __future__ import annotations

import random
from collections.abc import Mapping
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


def _to_residual(condition: str) -> sympy.Expr:
    """condition 문자열을 *잔차 식*(조건 만족 ⇔ residual == 0)으로 파싱.

    등식(`=`/`Eq`/`Equality`)이면 `lhs - rhs`를 잔차로 한다. 등식 기호가 없는 단일 식이면
    그 식 자체를 잔차로 본다(예: 이미 "x**2 - 5*x + 6" 형태로 0과 비교됨을 가정). 부등식 등
    *등식이 아닌 관계*나 파싱 불가는 예외를 일으켜 호출부가 unverifiable로 처리한다(보수적).
    """
    text = condition.strip()
    if not text:
        raise ValueError("빈 condition")

    # `=`(단일 등호)를 SymPy가 이해하는 잔차로 변환 — `==`는 파이썬 비교라 sympify가 오해 가능.
    # 부등호(<,>,<=,>=)가 섞이면 등식 아닌 관계이므로 아래 일반 파싱으로 보내 거부한다.
    if "=" in text and "==" not in text and "<" not in text and ">" not in text:
        lhs_text, rhs_text = text.split("=", 1)
        lhs = sympy.sympify(lhs_text, convert_xor=True)
        rhs = sympy.sympify(rhs_text, convert_xor=True)
        return sympy.sympify(lhs - rhs)

    parsed = sympy.sympify(text, convert_xor=True)
    if isinstance(parsed, sympy.Equality):
        return sympy.sympify(parsed.lhs - parsed.rhs)
    if getattr(parsed, "is_Relational", False) or isinstance(parsed, sympy.logic.boolalg.Boolean):
        # 부등식 등 등식 아닌 관계 — Tier1 답 검산은 등식 잔차 모델만 다룬다(보수적 회피).
        raise ValueError("등식이 아닌 관계(부등식 등) — Tier1 잔차 모델 적용 불가")
    # 등식 기호가 없는 단일 식 → 식 == 0을 묻는 잔차로 본다.
    return parsed


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
    condition: str,
    answer: Mapping[str, str],
    *,
    n_samples: int = 8,
    tol: float = 1e-9,
) -> AnswerVerdict:
    """Tier1 수치 답 검산 — 답을 원 조건에 대입해 만족 여부를 3상태로 판정(순수·결정론·DB 0).

    설계 §4 Tier1. `condition`은 답이 만족해야 할 *관계*(등식 문자열·예 "x**2 - 5*x + 6 = 0"·
    "2*a*x = b"), `answer`는 치환맵(예 {"x":"3"}·{"x":"b/(2*a)"})이다.

    판정 흐름:
      1. condition을 잔차 식으로 파싱(등식이면 `lhs - rhs`·`convert_xor=True`로 `^`=거듭제곱).
         부등식 등 *등식 아닌 관계*·파싱 불가 → **unverifiable**(보수적·위장 금지).
      2. answer 치환맵을 잔차에 대입.
      3. **잔차에 자유변수 없음** → 직접 수치 평가: |residual|<tol→**pass**·확정 ≠0→**fail**·
         평가 불가(복소·NaN 등)→**unverifiable**.
      4. **잔차에 자유변수 있음**(파라미터 문제) → **수치 샘플링**(Tier1 핵심): 자유변수에
         *고정 시드* 난수 n_samples + 경계값(0·±1·작은·큰 값)을 대입해 수치 평가 —
         · 모든 *유효* 샘플에서 |·|<tol → **pass**
         · 어느 유효 샘플에서든 확정 ≠0 → **fail**(거짓 답을 한 점으로 반증)
         · 유효 샘플이 하나도 없음(전부 특이점·복소 등) → **unverifiable**.
         0으로 나눔 등 특이점 샘플은 *건너뛴다*(유효 샘플에서 제외).

    Tier1 정직성(§4): `pass`는 "샘플 점에서 조건 만족"이지 *증명이 아니다*(신뢰도 최저).
    Tier1 단독 pass를 최종 통과로 쓰지 않고 반드시 Tier2와 결합한다(`whs/verdict.final_verdict`).
    파싱 불가·관계 아님·평가 불가·유효 샘플 0은 *절대 pass로 위장하지 않고* unverifiable로
    보수 처리한다(verify_step 정직성 상속).

    범위 밖(후속): 베이스라인 풀이율 측정(시드 모델)·솔버 루프·저장소 스키마·PRM·Tier3(§9).
    """
    # ① condition → 잔차 식. 파싱 불가·등식 아닌 관계는 보수적 unverifiable.
    try:
        residual = _to_residual(condition)
    except Exception:  # noqa: BLE001 — 파싱·관계 실패는 보수적 unverifiable(pass 위장 금지)
        return _unverifiable("condition 파싱 불가/등식 아님 — 검증 안전 회피")

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
        verdict = _eval_numeric(substituted, tol)
        if verdict is True:
            return _pass(samples_checked=1)
        if verdict is False:
            return _fail(f"조건 위반 — 잔차 ≠ 0: {substituted}", samples_checked=1)
        return _unverifiable("수치 평가 불가(복소/NaN 등) — 검증 안전 회피")

    # ④ 자유변수 있음(파라미터 문제) → 수치 샘플링(Tier1 핵심·고정 시드 결정론).
    return _sample_parametric(substituted, free_symbols, n_samples=n_samples, tol=tol)


def _evaluate_point(
    expr: sympy.Expr,
    substitution: dict[sympy.Symbol, sympy.Float],
    tol: float,
) -> float | None:
    """한 대입점에서 잔차를 수치 평가 — |실수부| 반환·특이점/복소/NaN/무한이면 None(건너뜀)."""
    try:
        value = complex(sympy.sympify(expr.subs(substitution)).evalf())
    except (TypeError, ValueError, AttributeError, ZeroDivisionError):
        return None  # 특이점(0 나눔 등)·평가 불가 — 유효 샘플 아님.
    if value != value or abs(value.real) == float("inf"):
        return None  # NaN·무한 — 특이점으로 간주(보수적).
    if abs(value.imag) > tol:
        return None  # 복소 — 실수 조건 평가 불가.
    return abs(value.real)


def _sample_parametric(
    expr: sympy.Expr,
    free_symbols: list[sympy.Symbol],
    *,
    n_samples: int,
    tol: float,
) -> AnswerVerdict:
    """파라미터(자유변수) 잔차를 *고정 시드* 샘플 + 경계값으로 평가 — Tier1 샘플링 코어.

    각 자유변수에 (경계값 전부) + (n_samples개 난수)를 대입해 수치 평가한다. 어느 유효 샘플에서든
    확정 ≠0이면 즉시 **fail**(한 반례로 거짓 답 반증). 0으로 나눔 등 특이점은 평가 불가(None)로
    *건너뛴다*. 모든 유효 샘플에서 |·|<tol이면 **pass**·유효 샘플이 하나도 없으면 **unverifiable**.

    결정론: `random.Random(_SAMPLE_SEED)`로 시드를 고정해 같은 입력에 같은 샘플을 보장한다.
    다변수일 때는 변수별 *서로 다른* 점도 평가해, 상관 잔차를 한 점이 우연히 0으로 만드는 위장을
    차단한다.
    """
    rng = random.Random(_SAMPLE_SEED)
    valid_samples = 0

    # (1) 단일 점 대입(모든 자유변수에 같은 값) — 경계값 + 난수.
    sample_points: list[float] = list(_BOUNDARY_VALUES)
    sample_points.extend(rng.uniform(_SAMPLE_LOW, _SAMPLE_HIGH) for _ in range(n_samples))
    for point in sample_points:
        substitution = {symbol: sympy.Float(point) for symbol in free_symbols}
        magnitude = _evaluate_point(expr, substitution, tol)
        if magnitude is None:
            continue  # 특이점·평가 불가 — 건너뜀.
        valid_samples += 1
        if magnitude >= tol:
            return _fail(
                f"파라미터 샘플 {point} 에서 조건 위반 — 잔차 ≠ 0",
                samples_checked=valid_samples,
            )

    # (2) 다변수 — 변수별 서로 다른 점도 평가(상관 잔차의 우연한 0 위장 차단).
    if len(free_symbols) > 1:
        for _ in range(n_samples):
            substitution = {
                symbol: sympy.Float(rng.uniform(_SAMPLE_LOW, _SAMPLE_HIGH))
                for symbol in free_symbols
            }
            magnitude = _evaluate_point(expr, substitution, tol)
            if magnitude is None:
                continue
            valid_samples += 1
            if magnitude >= tol:
                return _fail(
                    "다변수 파라미터 샘플에서 조건 위반 — 잔차 ≠ 0",
                    samples_checked=valid_samples,
                )

    # 유효 샘플이 하나도 없으면 판정 불가(전부 특이점·복소 등) — pass 위장 금지.
    if valid_samples == 0:
        return _unverifiable("유효 샘플 0(전부 특이점/복소) — 검증 안전 회피")

    # 모든 유효 샘플에서 잔차 ≈ 0 → pass(단, 샘플 점 만족이지 증명 아님·Tier2 결합 필수).
    return _pass(samples_checked=valid_samples)
