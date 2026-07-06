"""동등문제 *정규화(canonicalization)* — 표현 변형을 구조 signature로 접어 dedup 보완(S2-l).

동일 방정식의 표기 변형을 SymPy 정규형으로 접어 **같은 signature**를 준다:
  `x^2-10x+24=0` · `x**2-10*x+24 == 0` · `(x-4)(x-6)=0` · `2x^2-20x+48=0` · `-x^2+10x-24=0`
는 전부 canonical `x**2 - 10*x + 24`로 접혀 한 문제로 취급된다(계수 스케일·부호·인수분해·등호
표기 차이 흡수). 임베딩 dedup(S2-c·*의미* 근사)과 **상보적**인 *결정론 구조* dedup이다 — 임베딩
없이(비용 0)도 판박이 방정식을 배치에서 잡는다(Phaiakes9 실측: 같은 방정식이 표현만 바꿔 반복).

근 선택(answer_selection)이 다르면 *다른 문제*이므로 signature에 포함한다(같은 방정식이라도 큰 근
과 작은 근은 별개). 정규화 불가(비다항·초월·파싱 불가)면 `None`을 돌려 signature 없음을 알리고,
호출부는 임베딩 dedup(있으면)에 판정을 위임한다(보수적·조용한 병합 금지).

7계층: L3 지역 정규화(SymPy는 최하위 도구·import 허용). 표현≠의미(CLAUDE.md AST 중심)의 실천 —
화면 문자열이 아니라 구조로 동치를 판정한다.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence

import sympy

__all__ = ["canonical_condition", "canonical_signature"]


def canonical_condition(condition: str) -> str | None:
    """단일 조건을 SymPy 정규형 문자열로 접는다 — 정규화 불가면 None.

    등식(`=`/`==`/등호 없는 단일 식)은 잔차 `lhs - rhs`를 전개(expand)한 뒤 다항식 원시부
    (primitive part·내용 제거)로 스케일을 없애고 최고차 계수 부호를 양수로 맞춰 canonical
    다항식 문자열을 만든다. 부등식·≠는 잔차 정규형에 연산자를 접두해 구분한다(등식과 안 섞이게).
    비다항·자유변수 없음·파싱 불가는 None(보수적 — 임베딩 dedup에 위임).
    """
    text = condition.strip()
    if not text:
        return None
    op = "=="
    for rel in ("<=", ">=", "!=", "<", ">"):
        if rel in text:
            op = rel
            break
    try:
        if op == "==":
            # 등식 — `==`/`=`(단일)·등호 없는 단일 식을 모두 잔차로 환원.
            body = text.replace("==", "=")
            if "=" in body:
                lhs_text, rhs_text = body.split("=", 1)
            else:
                lhs_text, rhs_text = body, "0"
        else:
            lhs_text, rhs_text = text.split(op, 1)
        lhs = sympy.sympify(lhs_text, convert_xor=True)
        rhs = sympy.sympify(rhs_text, convert_xor=True)
        residual = sympy.expand(lhs - rhs)
    except (sympy.SympifyError, TypeError, ValueError, SyntaxError):
        return None

    symbols = sorted(residual.free_symbols, key=str)
    if not symbols:
        return None  # 상수 조건 — 문제 구조 식별 불가(보수적).
    try:
        poly = sympy.Poly(residual, *symbols)
    except (sympy.PolynomialError, sympy.GeneratorsError):
        return None  # 비다항(초월·유리식 등) — 정규화 밖.
    _, primitive = poly.primitive()  # 내용 제거(계수 스케일 정규화).
    if primitive.LC() < 0:  # 최고차 계수 부호를 양수로(부호 반전 흡수).
        primitive = -primitive
    return f"{op}:{primitive.as_expr()}"


def canonical_signature(
    conditions: str | Sequence[str],
    answer_selection: str | None,
) -> str | None:
    """조건(들)+근 선택을 결정론 구조 signature(16자 hex)로 접는다 — 정규화 불가면 None.

    연립은 각 조건을 정규화해 *정렬*(순서 무관)한 뒤 결합한다. 어느 한 조건이라도 정규화 불가면
    전체 None(보수적 — 부분 정규화로 오병합하지 않는다). 근 선택을 payload에 넣어 같은 방정식의
    큰 근/작은 근/유일을 구분한다. 같은 구조·같은 선택 → 같은 signature(판박이 dedup 키).
    """
    conds = [conditions] if isinstance(conditions, str) else list(conditions)
    if not conds:
        return None
    canon: list[str] = []
    for cond in conds:
        key = canonical_condition(cond)
        if key is None:
            return None
        canon.append(key)
    canon.sort()
    payload = "|".join(canon) + f"#sel={answer_selection or ''}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
