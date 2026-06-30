"""기호 항등성 판정 — 동치 권위 *단일 primitive* (SymPy·순수·결정론·DB 0).

`math_dsl_risk_register.md` Q10-⑦ "동치 권위는 SymPy 단일". 두 식이 *항등적으로 같은지*를
판정하는 SymPy 관용구(`sympify(convert_xor=True)` + `expand` + `simplify().is_zero` +
다항/변수집합 보강)를 **한 곳**에 둔다. 과거엔 이 관용구가 `verify_step`(단계 검증) 안에 인라인돼
있었고, 오개념 카탈로그는 *문자열 매칭*으로 거짓 항등식을 다뤄 "동치 권위가 둘"이 되는 부채였다
(math_dsl 감사 §7). 본 모듈이 그 권위를 일원화한다 — `verify_step`(단계 3상태 판정)도, 오개념
카탈로그 무결성(거짓 항등식이 *실제로* 거짓인지)도 모두 이 primitive를 거친다.

정직성(CLAUDE.md "확실하지 않으면 모른다"): 판정 불가(SymPy `is_zero is None`·비다항·정의역
의존)·파싱 불가는 *절대* identity/not_identity로 위장하지 않고 `undecidable`/`parse_error`로
보수 처리한다. 예: `√(x²)=x`·`log(a+b)=log a+log b`는 정의역·초월이라 가정 없이 단정 불가 →
`undecidable`(카탈로그가 머신 검증 가능 항등식만 `canonical_wrong_form`을 갖게 하는 근거).
"""

from __future__ import annotations

from enum import Enum

import sympy


class IdentityVerdict(str, Enum):
    """두 식의 항등성 4상태 — identity/not_identity는 *확정*, undecidable/parse_error는 보수."""

    identity = "identity"  # lhs ≡ rhs 확정(전개 0 환원 또는 simplify가 0 판정).
    not_identity = "not_identity"  # lhs ≢ rhs 확정(0-아님 확정·또는 같은 변수 다항 비항등).
    undecidable = "undecidable"  # 비다항·정의역 의존 등 SymPy 미결정(증명도 반증도 못 함).
    parse_error = "parse_error"  # sympify 실패·빈 입력(검증 안전 회피).


def identity_status(lhs: str, rhs: str) -> IdentityVerdict:
    """`lhs`와 `rhs`가 *항등적으로 같은지* SymPy로 판정한다 — 동치 권위 단일 primitive.

    `convert_xor=True`라 `^`=거듭제곱. 자유변수 OK("2(x+1)" ≡ "2x+2"). 차이 `diff = lhs - rhs`에서:
      - **identity**: `expand(diff) == 0`(다항 항등식이 0으로 환원) 또는 `simplify(diff).is_zero
        is True`(삼각 등 비다항 항등식).
      - **not_identity**: `simplify(diff).is_zero is False`(상수 차 등 0-아님 확정) 또는 `diff`가
        *같은 자유변수*의 다항식인데 전개가 0이 아님 — 0-아닌 다항식은 영함수가 아니므로 항등식
        아님이 *증명*된다(예: `(a+b)²−(a²+b²)=2ab`는 `a=b=1`에서 거짓). 변수 집합이 다르면(치환
        맥락) 거짓 not_identity를 피하려 undecidable로 둔다.
      - **undecidable**: 비다항·simplify 미정(예: `√(x²)` vs `x`는 정의역 의존) — 위장 없이 보수.
      - **parse_error**: 빈 입력·sympify 예외.
    """
    if not lhs.strip() or not rhs.strip():
        return IdentityVerdict.parse_error
    try:
        left = sympy.sympify(lhs, convert_xor=True)
        right = sympy.sympify(rhs, convert_xor=True)
        diff = sympy.sympify(left - right)
        expanded = sympy.expand(diff)  # 다항식은 전개가 완전한 정규형(항등식이면 0).
        is_zero = sympy.simplify(diff).is_zero  # 비다항 항등식(삼각 등)까지 보강 판정.
        is_poly = bool(diff.is_polynomial())  # 다항식이면 전개 0-여부로 결정 가능.
        same_symbols = left.free_symbols == right.free_symbols
    except Exception:  # noqa: BLE001 — 파싱·계산 실패는 보수적으로 parse_error(위장 금지)
        return IdentityVerdict.parse_error

    if expanded == 0 or is_zero is True:
        return IdentityVerdict.identity
    if is_zero is False or (is_poly and same_symbols):
        return IdentityVerdict.not_identity
    return IdentityVerdict.undecidable


__all__ = ["IdentityVerdict", "identity_status"]
