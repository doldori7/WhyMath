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

**S3-06 자연 표기 확장(2026-07-19 자연 사용 재측정 n=6·100% unverifiable 대응)**: 학생이 실제로
쓰는 표기 3종을 *안전하게*(거짓 판정 0 최상위) 등식 형태로 읽는다 — `read_equation_step`:
  - **연쇄 등식 `a=b=c`**(`x=(1+3)/2=2`): 인접쌍 내부 동치를 `identity_status`로 검사. 어느 쌍이
    거짓으로 *증명*되면 단계 자체의 오류(violation → verify_step에서 incorrect 승격 안전). 전부
    참(바인딩 쌍 최대 1개 허용)이면 최초=최종 단일 등식으로 정규화 후 해집합 경로에 위임.
  - **근 나열/선언**(`x=2, x=3`·`x=2 또는 x=3`): 같은 변수의 등식 나열을 해집합 union으로 파싱 —
    `(x-2)(x-3)=0 → x=2, x=3` 전이가 해집합 보존으로 correct 결정(이차방정식 자연 풀이 마지막 전이).
  - **이질 형태 전이 가드**(`solset_transition_status`): 해집합 비교(correct/incorrect)는 양쪽 모두
    "해집합을 보존해야 할 변형"일 때만 — 한쪽이 항등식(ℝ)이면(항등 재작성 ↔ 값 선언) 전이는
    undecidable 유지. 없으면 `x²−4x+3=(x−1)(x−3)`(항등·ℝ) → `x=2`(축 공식 파생·{2}) 같은 옳은
    풀이가 거짓 incorrect가 난다(2026-07-19 실측·본 태스크의 핵심 함정).

**S3-08 진부분집합 전이 가드(2026-07-20 대본 측정 턴4 대응)**: finite↔finite 전이에서 after가
before의 **비어있지 않은 진부분집합**(after ⊊ before·after ≠ ∅)이면 undecidable로 보수 처리한다.
근거: 이 전이는 구조적으로 두 의미가 동일해 문맥(기대정답) 없이 구별 불가 —
  - **답 선택(정당)**: `x=2, x=3 → x=3`({2,3}→{3}·문항이 큰 근을 요구) — 실측에서 이를
    incorrect로 오판해 정당한 풀이에 "다시 살펴볼 지점이 있어요"가 노출됐다(거짓 incorrect·
    2026-07-20 대본 측정 턴4 실해악).
  - **근 유실(오류)**: `x^2=4 → x=2`({−2,2}→{2}) — 검출하고 싶지만 위와 구조 동일.
"거짓 incorrect 0" 계약(의사결정 우선순위 3 교수학 > 4 학습효과)이 근 유실 검출 이득보다
우선이므로 보수적 undecidable을 택한다. **비부분집합 변화**({2,3}→{2,4} 원소 교체·{2}→{2,5}
원소 추가·{2}→{3} 전혀 다름·{2}→∅ 전멸)는 incorrect를 유지해 검출력 대부분을 보존한다.

**보류(구현 금지 — 주석으로만 기록)**: 캐럿 없는 지수 `x2`→`x²` *재작성 휴리스틱*은 수열 표기
(`a1`,`a2`)와 충돌 위험이라 범위 밖(S3-06 ④). 해당 표기는 unverifiable 유지가 정직 — 아래
`_AMBIGUOUS_TRAILING_DIGIT_SYMBOL` 가드가 해집합 경로에서 이를 강제한다(재작성이 아니라 보수 회피).
"""

from __future__ import annotations

import logging
import re
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
    identity_status,
    split_relation_chain,
    to_sympy_source,
)

logger = logging.getLogger("whymath.l3.solution_set")

__all__ = [
    "EquationReading",
    "EquationSolset",
    "as_single_equation",
    "equation_solution_set",
    "read_equation_step",
    "roots_enumeration_solset",
    "solset_transition_status",
    "solution_set_status",
]

# 캐럿 없는 지수/수열 의심 심볼 — 영문자+숫자 꼬리(`x2`·`a1`). 학생이 `x²`를 `x2`로 치는 표기와
# 수열 항(`a1`,`a2`) 표기가 구분 불가하다(S3-06 ④ 보류 — `x2`→`x²` 재작성 휴리스틱 구현 금지).
# 이런 심볼을 방정식의 *미지수로 풀어* 해집합을 내면(Symbol('x2')=4 → {4}) 학생 의도(x²=4 →
# {−2,2})와 어긋난 *거짓 incorrect*가 난다(2026-07-19 실측: `x2=4 → x=2`가 incorrect로 오판).
# 표현식 동치 경로는 치환 논증으로 건전하지만(비항등 다항식은 치환 후에도 비항등) solve는
# 아니므로, **해집합 경로에서만** 판정 불가(None)로 보수 처리한다("unverifiable 유지가 정직").
_AMBIGUOUS_TRAILING_DIGIT_SYMBOL = re.compile(r"^[A-Za-z]+[0-9]+$")

# 근 나열 구분자 — 콤마·"또는"(한국어 OR). `x=2, x=3`·`x=2 또는 x=3`을 항으로 쪼갠다.
_ROOTS_ENUM_SEPARATOR = re.compile(r",|또는")


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

    # ⓪ 캐럿 없는 지수/수열 의심 심볼(`x2`·`a1`) — 이 심볼을 미지수로 *풀면* 학생 의도(x²=4 →
    # {−2,2})와 다른 해집합({4})이 나와 거짓 incorrect가 난다(2026-07-19 실측). 재작성 휴리스틱은
    # 보류(S3-06 ④·수열 표기 충돌)이므로 해집합 경로는 판정 불가로 보수 회피한다(정직).
    if any(_AMBIGUOUS_TRAILING_DIGIT_SYMBOL.fullmatch(str(sym)) for sym in symbols):
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


def _finite_nonempty_proper_subset(after: EquationSolset, before: EquationSolset) -> bool:
    """after가 before의 *비어있지 않은 진부분집합*(after ⊊ before·after ≠ ∅)인가 — S3-08 가드용.

    유한↔유한 전용(ℝ이 끼면 False — 이질 형태는 별도 가드가 먼저 처리). 원소 매칭은
    `_solsets_equal`과 동일하게 `_num_equal`(정수/유리/실수 타입차 흡수)을 쓴다. **∅는 제외**한다
    (∅ ⊊ 유한집합이지만 "답 선택"은 항상 1개 이상을 고르므로 ∅ 전이는 선택으로 성립 불가 —
    incorrect 검출을 유지해도 거짓 incorrect 위험이 없다·검출력 보존).
    """
    if after.all_reals or before.all_reals:
        return False
    if not after.values:
        return False  # ∅는 답 선택으로 성립 불가 — 검출(not_identity) 유지
    if len(after.values) >= len(before.values):
        return False  # 같은 크기(=동일 여부는 앞선 _solsets_equal이 판정)·초과는 진부분집합 아님
    return all(any(_num_equal(x, y) for y in before.values) for x in after.values)


def solset_transition_status(
    before: EquationSolset | None,
    after: EquationSolset | None,
) -> IdentityVerdict:
    """두 해집합 간 전이를 4상태로 판정 — 비교는 *동질 형태*(둘 다 풀이 대상 등식)일 때만.

    **S3-06 거짓 incorrect 함정 방어(태스크 설계 핵심)**: 해집합 비교(identity/not_identity)는
    양쪽 모두 "같은 해집합을 보존해야 할 변형"일 때만 유효하다. 한쪽이 항등식(ℝ)이고 다른 쪽이
    유한 해집합(∅ 포함)이면 형태가 이질적이다 — 항등 *재작성*(예: `x²−4x+3=(x−1)(x−3)`)과 값
    *선언*(예: 축 공식 파생 `x=2`)의 전이는 해집합 보존 의무가 없으므로, 비교하면 옳은 풀이가
    거짓 incorrect가 난다(2026-07-19 실측). 따라서:
      - **identity**: ℝ↔ℝ(둘 다 항등 재작성) 또는 유한↔유한(∅ 포함)이 같음 → 보존.
      - **not_identity**: 유한↔유한이 *진부분집합 아닌* 다름 → 비보존(해가 바뀜/추가/전멸 =
        잘못된 변형·예: {2,3}→{2,4}·{2}→{2,5}·{2}→{3}·{2}→∅).
      - **undecidable**: 한쪽이라도 판정 불가(None) *또는* ℝ↔유한 이질 형태 *또는* 유한↔유한
        **비어있지 않은 진부분집합**(after ⊊ before·S3-08) → 위장 없이 보수.

    **S3-08 진부분집합 가드(2026-07-20 대본 측정 턴4)**: 유한↔유한에서 after가 before의
    비어있지 않은 진부분집합이면 undecidable — "답 선택"(정당·`x=2, x=3 → x=3`·문항이 큰 근
    요구)과 "근 유실"(오류·`x^2=4 → x=2`)이 구조적으로 동일해 문맥(기대정답) 없이 구별 불가
    하므로, 거짓 incorrect 0 계약이 근 유실 검출 이득보다 우선한다(모듈 docstring 참조).

    **후속 강화(설계 노트 — 이번 범위 밖)**: 기대정답 앵커로 검출 복원이 가능하다 — 코치 경로의
    `expected_answer`(`l3/pregenerate/validator.py`의 `classify_step_break`·`_extract_answer_solset`
    선례)를 이 판정에 문맥으로 주입하면 "선택 = 기대정답과 일치하는 부분집합 → correct / 그 외
    부분집합(기대정답 불일치·근 유실) → incorrect"로 진부분집합 전이의 판정을 복원할 수 있다.
    verify_step은 문맥 없는 순수 primitive이므로 앵커는 선택 인자·상위 배선으로 후속 슬라이스에서.
    """
    if before is None or after is None:
        # 한쪽이라도 판정 불가 → correct/incorrect로 위장하지 않는다(정직).
        return IdentityVerdict.undecidable
    if before.all_reals != after.all_reals:
        # 이질 형태(항등식 ℝ ↔ 값 선언/유한) — 해집합 보존 전제가 성립하지 않음 → 보수(정직).
        return IdentityVerdict.undecidable
    if _solsets_equal(before, after):
        return IdentityVerdict.identity
    if _finite_nonempty_proper_subset(after, before):
        # S3-08: 답 선택(정당)과 근 유실(오류)이 구조 동일 — 기대정답 없이는 구별 불가 → 보수.
        return IdentityVerdict.undecidable
    return IdentityVerdict.not_identity


def solution_set_status(before: tuple[str, str], after: tuple[str, str]) -> IdentityVerdict:
    """두 등식(before → after)이 *해집합 보존 동치*인지 4상태로 판정 — 재사용 집계(SymPy 단일 권위).

    `before`·`after`는 `as_single_equation`이 낸 (lhs, rhs) 조각이다. 각각의 실수 해집합을
    `equation_solution_set`으로 구해 `solset_transition_status`로 비교한다(4상태 의미는 그쪽 참조 —
    S3-06부터 ℝ↔유한 이질 형태는 not_identity가 아니라 undecidable·거짓 incorrect 함정 방어).

    parse_error를 따로 두지 않고 undecidable로 통합한다 — `as_single_equation`이 등식 구조를 앞단
    에서 이미 검증했고, 남은 파싱 실패(식 내용)와 풀이 불가는 verify_step에서 똑같이 unverifiable로
    귀결하므로 구분 실익이 없다(정직 동일).
    """
    return solset_transition_status(
        equation_solution_set(*before),
        equation_solution_set(*after),
    )


def roots_enumeration_solset(text: str) -> EquationSolset | None:
    """근 나열/선언(`x=2, x=3`·`x=2 또는 x=3`)을 *같은 변수*의 해집합 union으로 파싱 — S3-06 ②.

    이차방정식 자연 풀이의 마지막 전이(`(x-2)(x-3)=0 → x=2, x=3`)를 해집합 보존으로 결정하기 위한
    파서다(수능 wedge 핵심). 콤마·"또는"으로 항을 나눠 각 항이 `미지수 = 실수 상수` 꼴일 때만
    값들의 union(`EquationSolset(values={2,3})`)을 낸다. 다음은 전부 **None**(근 나열 아님·보수):
      - 항이 2개 미만·빈 항·단일 등식이 아닌 항(연쇄·표현식·비교 혼입).
      - **다른 변수 혼입**(`x=2, y=3`) — 이는 연립(AND·동시 성립)이지 근 나열(OR)이 아니므로
        union으로 읽으면 의미가 뒤집힌다(거짓 판정 위험·명시 거부).
      - **수열 의심 좌변**(`a1=2, a2=4`) — 수열 항 개별 선언(AND)을 근 나열로 오해석 금지
        (S3-06 ④ 보류와 같은 근거·`_AMBIGUOUS_TRAILING_DIGIT_SYMBOL`).
      - 좌변이 순수 미지수(Symbol)가 아니거나 우변이 실수 상수가 아닌 항(파라미터·복소·파싱 불가).

    반환 None은 "근 나열로 읽지 않는다"는 뜻일 뿐 오류가 아니다 — 호출자(`read_equation_step`)가
    기존 단일 등식/연쇄 등식 경로로 폴백한다(비파괴 감지).
    """
    # 전각 콤마(，) 등을 NFKC로 접은 뒤 구분자를 찾는다(정규화는 멱등·표기 계층).
    normalized = to_sympy_source(text)
    if ("," not in normalized) and ("또는" not in normalized):
        return None
    parts = [p.strip() for p in _ROOTS_ENUM_SEPARATOR.split(normalized)]
    if len(parts) < 2 or any(not p for p in parts):
        return None

    variable: Any | None = None
    values: set[Any] = set()
    for part in parts:
        eq = as_single_equation(part)
        if eq is None:
            return None  # 항이 단일 등식이 아님(연쇄·표현식·비교 혼입) → 근 나열 아님(보수)
        lhs = _parse_expr(to_sympy_source(eq[0]))
        rhs = _parse_expr(to_sympy_source(eq[1]))
        if lhs is None or rhs is None:
            return None  # 파싱 불가 → 보수 회피
        if not isinstance(lhs, sympy.Symbol):
            return None  # 좌변이 순수 미지수가 아니면 근 나열이 아님(x^2=4, ... 등)
        if _AMBIGUOUS_TRAILING_DIGIT_SYMBOL.fullmatch(str(lhs)):
            return None  # 수열 항(a1=2, a2=4)은 개별 선언(AND) — union(OR) 오해석 금지
        if variable is None:
            variable = lhs
        elif lhs != variable:
            return None  # 다른 변수 혼입(x=2, y=3)은 연립(AND) — union(OR) 오해석 금지
        if not (getattr(rhs, "is_number", False) and getattr(rhs, "is_real", False)):
            return None  # 우변이 실수 상수가 아니면 보수 회피(_common_solution 관례 동일)
        values.add(rhs)
    return EquationSolset(all_reals=False, values=frozenset(values))


@dataclass(slots=True, frozen=True)
class EquationReading:
    """단계 텍스트를 *등식 형태*로 읽은 결과(S3-06) — 단일 등식·연쇄 등식·근 나열 통합.

    `violation`이 채워지면 연쇄 등식의 인접쌍 하나가 거짓으로 *증명*된 것(원문 조각 쌍) — 단계
    자체의 오류이므로 verify_step이 전이 비교와 무관하게 incorrect로 승격해도 안전하다. 위반이
    없으면 `solset`이 이 단계의 해집합(판정 불가면 None → unverifiable 귀결)이다.
    """

    solset: EquationSolset | None
    violation: tuple[str, str] | None = None


def read_equation_step(text: str) -> EquationReading | None:
    """단계 텍스트를 등식 형태(단일 등식·연쇄 등식·근 나열)로 읽는다 — 아니면 None(표현식 경로).

    S3-06 자연 표기 확장의 단일 진입점. 분기(순서 중요 — 근 나열의 콤마가 연쇄 분해를 오염시키지
    않도록 근 나열을 먼저 시도한다):
      1. **근 나열**(`x=2, x=3`·`또는`): `roots_enumeration_solset` — 성공 시 union 해집합.
      2. **등식 구조 분해**(`split_relation_chain`): 비교/부등 혼입·빈 항(ValueError)·등호 없음은
         등식 형태가 아니므로 None(호출자가 표현식 경로로 — 기존 `as_single_equation` 관례 동일).
      3. **단일 등식**(쌍 1개): `equation_solution_set` 해집합.
      4. **연쇄 등식 `a=b=c`**(쌍 2+·S3-06 ①): 인접쌍 내부 동치를 `identity_status`(동치 권위
         단일)로 검사한다:
         - 어느 쌍이 **not_identity**(거짓 증명·예 `x=(1+3)/2=3`의 `(1+3)/2≠3`) → violation
           (단계 자체의 오류 — verify_step에서 incorrect 승격 안전).
         - 비항등 판정 쌍(undecidable/parse_error)이 **최대 1개**(변수=값 바인딩 쌍·내부 검증
           불가가 정상)이고 나머지 전부 identity → 체인은 항등 재작성으로 접혀 *최초=최종* 단일
           등식과 동치 → `(첫 항, 끝 항)`으로 정규화해 해집합 경로에 위임(예: `x=(1+3)/2=2` →
           `x=2` → {2}).
         - 비항등 판정 쌍 2+ → 체인 결속이 증명되지 않음 → solset None(unverifiable·정직).

    `verify_relation_chain`(symbolic_equivalence)을 쓰지 않는 이유: 그쪽은 *전 쌍 항등*만 identity
    로 집계하는 표현식 체인 검증이라, 바인딩 쌍(변수=값·내부 undecidable이 정상) 1개를 허용해야
    하는 방정식 풀이 체인과 집계 규칙이 다르다. 쌍 단위 판정은 동일하게 `identity_status` 단일
    권위를 쓰므로 동치 권위 이원화가 아니다.
    """
    # ① 근 나열/선언 — 콤마·"또는" 구분의 같은 변수 등식 나열 → 해집합 union.
    enum_solset = roots_enumeration_solset(text)
    if enum_solset is not None:
        return EquationReading(solset=enum_solset)

    # ② 등식 구조 분해 — 비교/부등 혼입·빈 항은 등식 형태 아님(None → 표현식 경로·기존 관례).
    try:
        pairs = split_relation_chain(text)
    except ValueError:
        return None
    if not pairs:
        return None  # 등호 없음 — 표현식(호출자가 identity_status 경로로).

    # ③ 단일 등식 — 기존 S3-02 경로 그대로.
    if len(pairs) == 1:
        return EquationReading(solset=equation_solution_set(*pairs[0]))

    # ④ 연쇄 등식 a=b=c — 인접쌍 내부 동치검사(identity_status·동치 권위 단일).
    verdicts = [identity_status(lhs, rhs) for lhs, rhs in pairs]
    for pair, verdict in zip(pairs, verdicts, strict=True):
        if verdict is IdentityVerdict.not_identity:
            # 인접쌍 거짓 *증명* — 단계 자체의 오류(전이 무관 incorrect 승격 안전·S3-06 ①).
            return EquationReading(solset=None, violation=pair)
    non_identity_count = sum(1 for v in verdicts if v is not IdentityVerdict.identity)
    if non_identity_count <= 1:
        # 바인딩 쌍(변수=값 선언·내부 검증 불가가 정상) 최대 1개 — 나머지가 전부 항등이므로
        # 체인은 최초=최종 단일 등식으로 접힌다(항등 재작성 제거) → 해집합 경로 위임.
        return EquationReading(solset=equation_solution_set(pairs[0][0], pairs[-1][1]))
    # 비항등 판정 쌍 2+ — 체인 결속 미증명 → 판정 불가(unverifiable 귀결·정직).
    return EquationReading(solset=None)
