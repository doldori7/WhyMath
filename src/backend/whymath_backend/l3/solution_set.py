"""등호 방정식 단계의 *해집합 보존 동치* 판정 — verify 경로 L3 primitive (S3-02).

`verify_step`(l3/verify_step.py)는 지금까지 *표현식 동치*("2(x+1)"≡"2x+2")만 결정론으로 판정하고,
등호가 든 *방정식 변형 단계*("2x+3=7 → 2x=4")는 `identity_status`가 등식을 파싱하지 못해 전부
`unverifiable`로 떨어졌다 — 실사용 shadow에서 89%가 unverifiable(2026-07-17 n=9)이 된 근본원인이다.
방향 B(Kiki 2026-07-18): 방정식 단계를 **해집합 보존 동치(solution-set-preserving equivalence)** 로
판정한다 — before/after 방정식의 *실수 해집합*을 SymPy로 구해 보존이면 correct·변화면 incorrect·
풀이 불가면 unverifiable(정직).

**재사용(재구현 금지·S3-02 "승격")**: 해집합 *계산*은 `l3/pregenerate/validator.py`의 검증된 자산을
그대로 호출한다 — `classify_step_break`(A/B shadow 분류·slice 65)·`detect_step_breaks`가 쓰는 바로
그 solset 로직이다(L3 내부 자산이므로 verify 경로에서 호출 가능):
  - `_common_solution` — 단변수 다항 방정식의 유한 실근(비다항·복소·매개변수는 None).
  - `_num_equal` — 두 수치의 동일성(정수/유리/실수 타입차를 simplify로 흡수).
  - `_parse_expr` — 암묵곱·`^`거듭제곱 파싱(실패 시 None).
파싱 정규화는 동치 권위 모듈의 `to_sympy_source`(위첨자·전각·연산자·그리스·NFKC), 등식 구조 분해는
같은 모듈의 `split_relation_chain`을 재사용한다. verdict는 동치 권위의 `IdentityVerdict`(4상태)로
통일해 verify_step이 표현식 경로와 *같은 매핑*으로 흡수하게 한다.

**정직성 계약(CLAUDE.md "확실하지 않으면 모른다"·거짓 incorrect 0)**: SymPy 단일 권위. 다변수·
비다항·복소해·파싱 불가·미정은 *절대 correct/incorrect로 위장하지 않고* `undecidable`/`parse_error`
로 보수 처리한다(→ verify_step에서 unverifiable·evidence_weight 0.5 할인). 특히 **항등 방정식**
(`(x+1)^2=x^2+2x+1`·모든 실수)은 SymPy `solve`가 빈 리스트를 돌려 "해 없음(∅)"과 구분되지 않으므로,
전개가 0인지 *먼저* 판별해 ℝ(모든 실수)로 명시한다 — 이 구분이 없으면 정당한 항등 단계가 ∅↔ℝ로
오판돼 *거짓 incorrect*가 난다(계약 위반 방지의 핵심). 침묵 실패 금지: SymPy 내부 예외는 예외
타입명을 로그에 남기고(필드값 제외) 보수적으로 판정 불가 처리한다.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import sympy

from whymath_backend.l3.pregenerate.validator import (
    _common_solution,  # 단변수 다항 방정식 유한 실근(검증된 자산 재사용·재구현 금지)
    _num_equal,  # 수치 동일성(정수/유리/실수 타입차 simplify 흡수)
    _parse_expr,  # 암묵곱·^거듭제곱 파싱(실패 시 None)
)
from whymath_backend.l3.symbolic_equivalence import (
    IdentityVerdict,
    split_relation_chain,
    to_sympy_source,
)

logger = logging.getLogger("whymath.l3.solution_set")

__all__ = [
    "EquationSolset",
    "as_single_equation",
    "equation_solution_set",
    "solution_set_status",
]


def as_single_equation(text: str) -> tuple[str, str] | None:
    """`text`가 *정확히 하나의 등식*(lhs=rhs)이면 (lhs, rhs) 원문 조각, 아니면 None.

    등식 구조 분해는 `split_relation_chain`(동치 권위 모듈)을 재사용한다 — 비교/부등 연산
    (`==`·`<=`·`<`·`>`·`!=`)이 섞이거나 빈 항이면 등식이 아니므로 None(ValueError 흡수), `=`가
    0개면 표현식(None), 2개 이상(연쇄 `a=b=c`)이면 단일 방정식이 아니므로 None(보수적). 정확히
    1개일 때만 방정식 단계로 취급한다 — verify_step이 표현식·방정식 경로를 이 판정으로 가른다.
    """
    try:
        pairs = split_relation_chain(text)
    except ValueError:
        # 비교/부등 연산 혼입·빈 항 — 단일 등식이 아니다(보수적 비검출).
        return None
    if len(pairs) == 1:
        return pairs[0]
    # 0개(등호 없음=표현식) 또는 2개 이상(연쇄 등식) → 단일 방정식 아님.
    return None


@dataclass(slots=True, frozen=True)
class EquationSolset:
    """단변수/무변수 방정식의 *실수* 해집합 표현 — 해집합 비교용(불변·frozen).

    `all_reals=True`면 항등 방정식(모든 실수 해)이고 `values`는 무시된다. 그 외엔 `values`가 유한
    실근 집합(빈 집합=해 없음 ∅). *판정 불가*(다변수·비다항·복소·파싱·미정)는 이 타입으로 표현하지
    않고 `equation_solution_set`이 **None**으로 표기한다(정직 — correct/incorrect로 위장 금지).
    """

    all_reals: bool
    values: frozenset[Any]


def equation_solution_set(lhs_raw: str, rhs_raw: str) -> EquationSolset | None:
    """단일 등식 `lhs=rhs`의 *실수 해집합*을 구한다 — 판정 불가면 None(정직·보수).

    재사용: 파싱은 `to_sympy_source`+`_parse_expr`, 유한 실근은 `_common_solution`(단변수 다항·
    비다항/복소/매개변수는 None). 분기:
      - **무변수**(순수 수치 등식): 참=모든 실수(ℝ)·거짓=해 없음(∅)·미정=None.
      - **다변수**(자유변수 2+): None — 단변수 해집합 개념이 성립하지 않으므로 정직하게 판정 불가.
      - **항등 방정식**(전개가 0): all_reals — `solve`가 항등식에 빈 리스트를 돌려 ∅과 구분되지
        않으므로 *먼저* 판별한다(거짓 incorrect 회피의 핵심).
      - **그 외 단변수**: `_common_solution`으로 유한 실근(비다항·복소·매개변수는 None).

    반환 None = 판정 불가(파싱 불가·다변수·비다항·복소·미정) → 호출자가 unverifiable로 귀결한다.
    """
    lhs = _parse_expr(to_sympy_source(lhs_raw))
    rhs = _parse_expr(to_sympy_source(rhs_raw))
    if lhs is None or rhs is None:
        # 파싱 불가 → 판정 불가(보수적·correct/incorrect 위장 금지).
        return None
    try:
        diff = lhs - rhs
        symbols = diff.free_symbols
    except Exception as exc:  # noqa: BLE001  # pragma: no cover — 예외 타입명 로그 후 보수 skip
        logger.debug("해집합 계산 실패(diff): %s: %s", type(exc).__name__, exc)
        return None

    # ① 무변수 — 순수 수치 등식. 참이면 모든 실수(ℝ)·거짓이면 해 없음(∅)·미정이면 판정 불가.
    if len(symbols) == 0:
        try:
            is_zero = sympy.simplify(diff).is_zero
        except Exception as exc:  # noqa: BLE001  # pragma: no cover — 예외 타입명 로그 후 보수 skip
            logger.debug("해집합 계산 실패(무변수 is_zero): %s: %s", type(exc).__name__, exc)
            return None
        if is_zero is True:
            return EquationSolset(all_reals=True, values=frozenset())
        if is_zero is False:
            return EquationSolset(all_reals=False, values=frozenset())
        return None  # is_zero None(미정) → 판정 불가

    # ② 다변수 — 단변수 해집합 개념이 성립하지 않음 → 정직하게 판정 불가(거짓 판정 회피).
    if len(symbols) >= 2:
        return None

    (var,) = tuple(symbols)
    # ③ 항등 방정식(모든 실수) 먼저 — `solve`가 항등식에 [] 를 돌려 ∅과 구분 안 되는 문제 방어.
    # 예: (x+1)^2=x^2+2x+1 은 diff.free_symbols={x}지만 expand(diff)==0(항등)이라, 프리체크 없이는
    # _common_solution이 set()(=∅)을 돌려 정당한 단계가 거짓 incorrect로 오판된다(계약 위반 방지).
    try:
        if diff.is_polynomial(var) and sympy.expand(diff) == 0:
            return EquationSolset(all_reals=True, values=frozenset())
    except Exception as exc:  # noqa: BLE001  # pragma: no cover — 예외 타입명 로그 후 보수 skip
        logger.debug("해집합 계산 실패(항등 판별): %s: %s", type(exc).__name__, exc)
        return None

    # ④ 그 외 단변수 — 검증된 자산 재사용(단변수 다항 유한 실근·비다항/복소/매개변수는 None).
    solset = _common_solution(var, [(lhs, rhs, "")])
    if solset is None:
        return None  # 비다항·복소·매개변수 → 판정 불가(정직)
    return EquationSolset(all_reals=False, values=frozenset(solset))


def _solsets_equal(a: EquationSolset, b: EquationSolset) -> bool:
    """두 실수 해집합이 같은가 — 모든 실수(ℝ)는 서로만 같고, 유한 집합은 `_num_equal` 원소 매칭.

    ℝ vs 유한/∅ = 다름. ∅ vs ∅ = 같음(둘 다 해 없음·보존). 유한 vs 유한은 크기 + 원소 수치 동일성
    (`_num_equal`·정수/유리/실수 타입차 흡수)으로 비교한다.
    """
    if a.all_reals or b.all_reals:
        return a.all_reals and b.all_reals
    if len(a.values) != len(b.values):
        return False
    return all(any(_num_equal(x, y) for y in b.values) for x in a.values)


def solution_set_status(before: tuple[str, str], after: tuple[str, str]) -> IdentityVerdict:
    """두 등식(before → after)이 *해집합 보존 동치*인지 4상태로 판정 — 재사용 집계(SymPy 단일 권위).

    `before`·`after`는 `as_single_equation`이 낸 (lhs, rhs) 조각이다. 각각의 실수 해집합을
    `equation_solution_set`으로 구해 비교한다:
      - **identity**: 두 해집합이 같음(ℝ↔ℝ 포함) → 해집합 보존(올바른 변형).
      - **not_identity**: 두 해집합이 다름 → 해집합 비보존(해가 바뀜/유실/추가 = 잘못된 변형).
      - **undecidable**: 한쪽이라도 판정 불가(다변수·비다항·복소·미정·파싱 불가) → 위장 없이 보수.

    parse_error를 따로 두지 않고 undecidable로 통합한다 — `as_single_equation`이 등식 구조를 앞단
    에서 이미 검증했고, 남은 파싱 실패(식 내용)와 풀이 불가는 verify_step에서 똑같이 unverifiable로
    귀결하므로 구분 실익이 없다(정직 동일).
    """
    solset_before = equation_solution_set(*before)
    solset_after = equation_solution_set(*after)
    if solset_before is None or solset_after is None:
        # 한쪽이라도 판정 불가 → correct/incorrect로 위장하지 않는다(정직).
        return IdentityVerdict.undecidable
    if _solsets_equal(solset_before, solset_after):
        return IdentityVerdict.identity
    return IdentityVerdict.not_identity
