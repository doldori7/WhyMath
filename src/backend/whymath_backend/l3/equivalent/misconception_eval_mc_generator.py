"""오개념 커버리지 확대용 수치평가 객관식 스켈레톤 생성기 — S2 확장(결정론·LLM 0).

`CalculusExtremumMCSkeletonGenerator`(극값 MC)의 형제다. 같은 `EquivalentProblemGenerator`
좌석을 구현하되 목적이 다르다: 기존 코퍼스가 `distractor_map`으로 커버하지 못하던 오개념 여러 종을
문항에 *등장*시켜 crosswalk 기계 게이트의 machine-decidable 커버리지(8/34→13/34)를 끌어올린다.

여덟 템플릿(각각 오개념 1종을 오답 선지로 태깅):
  - `distribution`   — (a+b)² 의 값(오개념: 제곱을 각 항에 분배해 교차항 2ab 누락 → a²+b²).
  - `chain_rule`     — f(x)=(kx+c)³ 의 f'(x₀)(오개념: 연쇄법칙 내부 도함수 k 누락 → 3(kx₀+c)²).
  - `sine_sum`       — sin(A+B) 의 값(오개념: 사인을 합에 분배 → sin A + sin B).
  - `exp_zero`       — n + a^0 의 값(오개념: a^0=0 으로 오인 → n).
  - `sqrt_pos`       — √((-a)²) 의 값(오개념: √(x²)=x 로 오인 → -a).
  - `log_dist`       — log₂(2^k + 2^k) 의 값(오개념: log₂(2^k)+log₂(2^k)=k+k → 2k).
  - `func_compose`   — f(x)=x+a, g(x)=bx 의 (f∘g)(c)(오개념: 합성 순서 뒤집어 (g∘f)(c) → bc+ab).
  - `sine_period`    — y=sin(kx) 의 주기(오개념: 계수 k 무시 주기 불변 오인 → 2π).

뒤 5종(exp_zero~sine_period)은 정본 카탈로그에는 실재하나 유발 op-code가 없다(수치평가 MC는
op-code 없이 오개념만 태깅 — `DistractorEntry.op_code` 옵셔널·`distractor_codes` op_code=None 허용).

핵심 통찰(극값 MC 미러·재구현 0): 수치평가 문항은 정답이 *하나의 닫힌 값*이라, dummy 변수 x의
등식 `x = <닫힌형 식>`(conditions)과 `{"x": <정답값>}`(answer_map)로 기존 Tier1 검산 스택
(`verify_answer`·`classify_solvability`)을 **무변경 재사용**한다 — 오케스트레이터·수용 게이트·
저장 sink 전부 그대로다. 오답 선지 오개념·op-code id는 생성자 `distractor_codes`로 주입받는다
(L4 하드코딩 0·계층 규칙·극값 MC 규약 미러).

정직성·이중 방어: 생성물은 S2-a 게이트(정확성·저작권·위생·동등성)를 통과해야 저장된다. 각 문항의
4지선다는 *4값이 서로 다른* 경우만 수록하고(정답·오개념 오답·filler 2종), 오개념 오답 1건만
`distractor_map`에 태깅한다(filler는 미태깅·스키마 계약). 산출물은 v0(사람 검수 전) —
게이트 통과 ≠ 학생 노출(§03 정본).

7계층: L3 지역(생성=LLM 라우터 도메인이나 이 구현은 LLM 0 — 좌석 계약만 공유). schema(최하위)·
동일 패키지(generator·acceptance·canonicalize)·L1 problem_bank(ConceptTag)만 import(L4 참조 0).
"""

from __future__ import annotations

import hashlib
import random
import uuid
from collections.abc import Mapping, Sequence
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from typing import Literal

import sympy

from whymath_backend.l1.problem_bank.populate import ConceptTag
from whymath_backend.l3.equivalent.acceptance import EquivalenceSpec
from whymath_backend.l3.equivalent.canonicalize import canonical_signature
from whymath_backend.l3.equivalent.generator import CandidateProblem
from whymath_backend.schema.enums import (
    AnswerFormat,
    Curriculum,
    GenerationType,
    LicenseType,
    QuestionFormat,
    SourceType,
    Subject,
)
from whymath_backend.schema.problem import DistractorEntry, Problem
from whymath_backend.schema.provenance import ContentProvenance

__all__ = [
    "MisconceptionEvalMCSkeletonGenerator",
    "TemplateKind",
]

# 풀 셔플 고정 시드 — 같은 구성은 같은 출제 순서(재현·디버그). 비결정 난수 금지(verify 규약 미러).
_POOL_SEED = 20260709

# 수치 4-상이 판정 허용치 — 두 선지 값이 이보다 가까우면 사실상 같은 값(4지선다 부적격).
_DISTINCT_TOL = 1e-9

TemplateKind = Literal[
    "distribution",
    "chain_rule",
    "sine_sum",
    "exp_zero",
    "sqrt_pos",
    "log_dist",
    "func_compose",
    "sine_period",
    "translate",
    "product_rule",
    "fraction_cancel",
    "polygon_angle_sum",
    "area_perimeter",
    "circle_radius",
]

# 템플릿별 L1 데이터 메타(개념 원천 src_id·단원 코드) — L4 오개념 주입 원칙 밖(L1 데이터).
# concept_src_id는 개념그래프 원천 키, unit_code는 문항 단원 코드. 성취기준 코드는 spec이 공급한다.
_TEMPLATE_META: dict[TemplateKind, tuple[str, str]] = {
    "distribution": ("J0219", "POLY-PRODUCT"),
    "chain_rule": ("H:12미적Ⅰ02-01", "CALC-CHAIN"),
    "sine_sum": ("H:12미적Ⅱ02-02", "TRIG-ADD"),
    "exp_zero": ("J0208", "EXP-ZERO"),
    "sqrt_pos": ("J0107", "SQRT-POS"),
    "log_dist": ("H:12대수01-05", "LOG-DIST"),
    "func_compose": ("HK35", "FUNC-COMPOSE"),
    "sine_period": ("H:12미적Ⅱ02-02", "TRIG-PERIOD"),
    "translate": ("10기수2-01-06", "FUNC-TRANSLATE"),
    "product_rule": ("H:12미적Ⅰ02-01", "CALC-PRODUCT"),
    "fraction_cancel": ("J0104", "FRACTION-CANCEL"),
    "polygon_angle_sum": ("J0305", "POLYGON-ANGLE-SUM"),
    "area_perimeter": ("J0312", "AREA-PERIMETER"),
    "circle_radius": ("10공수2-01-04", "CIRCLE-RADIUS"),
}


@dataclass(frozen=True, slots=True)
class _EvalItem:
    """수치평가 MC 뼈대 — 한 문항의 전 계산 결과(수치의 단일 진실 원천·결정론).

    선지(`choices`)는 4값을 *수치 오름차순*으로 정렬한 표기 문자열이고, `answer_index`·`misc_index`
    는 그 정렬 안의 정답·오개념 오답 위치다(정렬 확정으로 결정론). `conditions`/`answer_str`은 Tier1
    검산 재료(dummy x 등식·정답값). 오개념 id·op-code는 뼈대에 담지 않는다 — 생성기가 주입한다.
    """

    conditions: str
    answer_str: str
    choices: tuple[str, str, str, str]
    answer_index: int
    misc_index: int
    question_text: str
    answer_explanation: str
    difficulty: float
    answer_format: AnswerFormat


def _difficulty(seed: int) -> float:
    """종합 난이도를 [2.5, 3.5] 밴드에 결정론 분산 — spec 난이도 3.0·tol 0.5 안이라 동등성 만점."""
    return round(2.5 + (seed % 11) * 0.1, 1)


def _answer_format_for(value: sympy.Expr) -> AnswerFormat:
    """정답값 형태 — 양의 정수=자연수·유리(비정수)=분수·그 외(무리·음수·0)=실수."""
    if value.is_integer and value > 0:
        return AnswerFormat.자연수
    if value.is_rational:
        return AnswerFormat.분수
    return AnswerFormat.실수


def _display(value: sympy.Expr) -> str:
    """선지·정답 표기 문자열 — SymPy 정확값(반올림 소수 아님·파싱 가능 형태 'sqrt(3)/2')."""
    return str(sympy.sstr(value))


def _numeric(value: sympy.Expr) -> float:
    """정렬·상이 판정용 실수 근사(SymPy 정확값을 float로)."""
    return float(value)


def _four_distinct(values: Sequence[sympy.Expr]) -> bool:
    """네 선지 값이 수치적으로 서로 다른가(4지선다 자격) + 0 값 없음(위생·filler 규약)."""
    nums = [_numeric(v) for v in values]
    if any(abs(n) < _DISTINCT_TOL for n in nums):
        return False  # 0 선지 금지(filler·정답 모두 — 위생).
    for i in range(len(nums)):
        for j in range(i + 1, len(nums)):
            if abs(nums[i] - nums[j]) < _DISTINCT_TOL:
                return False
    return True


def _assemble_item(
    *,
    values: tuple[sympy.Expr, sympy.Expr, sympy.Expr, sympy.Expr],
    conditions: str,
    answer_str: str,
    question_text: str,
    answer_explanation: str,
    difficulty: float,
    answer_format: AnswerFormat,
) -> _EvalItem | None:
    """4값(정답·오개념·filler1·filler2)을 수치 오름차순 선지로 접어 뼈대 조립 — 4-상이 아니면 None.

    `values`는 (정답, 오개념 오답, filler1, filler2) 순서다. 표기 문자열까지 서로 다른지도 확인해
    (수치는 다르나 표기가 겹치는 병리 케이스) 4지선다 자격을 이중 보장한다.
    """
    if not _four_distinct(values):
        return None
    roles = ("correct", "misc", "f1", "f2")
    entries = sorted(zip(roles, values, strict=True), key=lambda e: _numeric(e[1]))
    choices = tuple(_display(v) for _, v in entries)
    if len(set(choices)) != 4:
        return None  # 표기 충돌(수치는 달랐으나 문자열이 같음) — 안전 배제.
    ordered_roles = [role for role, _ in entries]
    return _EvalItem(
        conditions=conditions,
        answer_str=answer_str,
        choices=(choices[0], choices[1], choices[2], choices[3]),
        answer_index=ordered_roles.index("correct"),
        misc_index=ordered_roles.index("misc"),
        question_text=question_text,
        answer_explanation=answer_explanation,
        difficulty=difficulty,
        answer_format=answer_format,
    )


def _build_distribution_pool() -> tuple[_EvalItem, ...]:
    """(a+b)² 값 뼈대 풀 — 정답 (a+b)²·오개념 a²+b²(교차항 누락)·filler 2ab·a²+b²+ab.

    정답값 (a+b)²=합²으로 dedup(같은 합은 conditions 정규형이 같아 구조 dedup 충돌). a<b·a,b≥2라
    네 값 {(a+b)², a²+b², 2ab, a²+b²+ab}은 항상 서로 다르다(대수적 증명·전건 4-상이).
    """
    pool: list[_EvalItem] = []
    seen: set[int] = set()
    for a in range(2, 8):
        for b in range(a + 1, 24):
            correct_v = (a + b) ** 2
            if correct_v in seen:
                continue  # 같은 합 → 같은 정답값 → 구조 signature 충돌(회차 낭비 방지).
            correct = sympy.Integer(correct_v)
            misc = sympy.Integer(a * a + b * b)  # 교차항 2ab 누락.
            filler1 = sympy.Integer(2 * a * b)  # 교차항만.
            filler2 = sympy.Integer(
                a * a + b * b + a * b
            )  # 교차항을 1배만(2배를 1배로).
            item = _assemble_item(
                values=(correct, misc, filler1, filler2),
                conditions=f"x = ({a}+{b})**2",
                answer_str=str(correct_v),
                question_text=(
                    f"두 수 a, b에 대하여 a = {a}, b = {b} 일 때, (a+b)^2 의 값을 구하시오."
                ),
                answer_explanation=(
                    f"(a+b)^2 = a^2 + 2ab + b^2 이므로 a = {a}, b = {b} 를 대입하면 "
                    f"(a+b)^2 = {correct_v} 이다. 교차항 2ab 를 빠뜨리면 a^2+b^2 가 되어 틀린다."
                ),
                difficulty=_difficulty(a + b),
                answer_format=AnswerFormat.자연수,
            )
            if item is not None:
                seen.add(correct_v)
                pool.append(item)
    random.Random(_POOL_SEED).shuffle(pool)
    return tuple(pool)


def _build_chain_rule_pool() -> tuple[_EvalItem, ...]:
    """f(x)=(kx+c)³ 의 f'(x₀) 뼈대 풀 — 정답 3k(kx₀+c)²·오개념 3(kx₀+c)²(내부 도함수 k 누락).

    filler: 3k²(kx₀+c)²(k 이중 적용)·k(kx₀+c)²(거듭제곱 계수 3 누락). k≥2·k≠3라 네 계수
    {3k, 3, 3k², k}가 서로 달라(대수적 증명) 전건 4-상이. 정답값으로 dedup(구조 signature 충돌↓).
    """
    pool: list[_EvalItem] = []
    seen: set[int] = set()
    for k in (2, 4, 5):  # k≥2(3k≠3)·k≠3(3≠k, 즉 오개념≠filler2 계수 충돌 회피).
        for x0 in range(1, 4):
            for c in range(1, 5):
                inner = k * x0 + c  # ≥3 > 0.
                correct_v = 3 * k * inner * inner
                if correct_v in seen:
                    continue
                inner_sq = sympy.Integer(inner * inner)
                correct = sympy.Integer(correct_v)
                misc = sympy.Integer(3) * inner_sq  # 내부 도함수 k 누락.
                filler1 = sympy.Integer(3 * k * k) * inner_sq  # k 이중 적용.
                filler2 = sympy.Integer(k) * inner_sq  # 거듭제곱 계수 3 누락.
                item = _assemble_item(
                    values=(correct, misc, filler1, filler2),
                    conditions=f"x = 3*{k}*({k}*{x0}+{c})**2",
                    answer_str=str(correct_v),
                    question_text=(
                        f"함수 f(x) = ({k}x + {c})^3 의 x = {x0} 에서의 미분계수 "
                        f"f'({x0}) 의 값을 구하시오."
                    ),
                    answer_explanation=(
                        f"연쇄법칙으로 도함수를 구하면 내부 함수의 도함수 {k} 를 곱해야 한다. "
                        f"x = {x0} 을 대입하면 미분계수는 {correct_v} 이다. "
                        f"내부 도함수 {k} 를 곱하지 않으면 틀린 값이 된다."
                    ),
                    difficulty=_difficulty(k + inner),
                    answer_format=AnswerFormat.자연수,
                )
                if item is not None:
                    seen.add(correct_v)
                    pool.append(item)
    random.Random(_POOL_SEED).shuffle(pool)
    return tuple(pool)


def _build_sine_pool() -> tuple[_EvalItem, ...]:
    """sin(A+B) 값 뼈대 풀 — 정답 k·sin(A+B)·오개념 k·(sinA+sinB)(사인을 합에 분배).

    filler: k·sinA·cosB(덧셈정리 한 항만)·k·cosA·cosB(코사인 정리와 혼동). A=aπ/12·B=bπ/12(15°
    격자)라 sin(A+B)는 덧셈정리의 정본 산출값(sin15°·sin45°·sin75° 등 표준 특수각)이다 — 이 오개념
    (sin의 합 분배)이 정확히 겨냥하는 문항 유형. 15° 격자만으론 서로 다른 sin(A+B) 값이 12종뿐이라,
    작은 정수 배수 k(1~3)를 곱해 서로 다른 정답값을 넉넉히 확보한다(k배는 오개념 충실도를 보존 —
    학생이 sin을 합에 분배하면 k(sinA+sinB)가 됨). 정답값으로 dedup(sin 특수각은 대수 상수로 접혀
    conditions가 다항 signature를 가지므로 값 dedup=구조 dedup 정합). 0 값·4-비상이는 배제.
    """
    pi = sympy.pi
    pool: list[_EvalItem] = []
    seen: set[float] = set()
    for a in range(1, 12):
        for b in range(a, 12):  # a ≤ b(대칭 중복 축소)·A,B ∈ (0, π).
            a_ang = sympy.Rational(a, 12) * pi
            b_ang = sympy.Rational(b, 12) * pi
            base = sympy.sin(a_ang + b_ang)
            base_misc = sympy.sin(a_ang) + sympy.sin(b_ang)
            base_f1 = sympy.sin(a_ang) * sympy.cos(b_ang)
            base_f2 = sympy.cos(a_ang) * sympy.cos(b_ang)
            for k in (1, 2, 3):
                correct = sympy.Integer(k) * base
                key = round(_numeric(correct), 9)
                if abs(key) < _DISTINCT_TOL or key in seen:
                    continue  # 0(위생)·정답값 중복(구조 dedup 충돌) 배제.
                coeff = "" if k == 1 else f"{k} "
                item = _assemble_item(
                    values=(
                        correct,
                        sympy.Integer(k) * base_misc,  # 사인 합 분배(오개념).
                        sympy.Integer(k) * base_f1,  # 덧셈정리 한 항만.
                        sympy.Integer(k) * base_f2,  # 코사인 정리와 혼동.
                    ),
                    conditions=f"x = {k}*sin({a}*pi/12 + {b}*pi/12)",
                    answer_str=_display(correct),
                    question_text=(
                        f"두 각 A = {a}π/12, B = {b}π/12 에 대하여 "
                        f"{coeff}sin(A + B) 의 값을 구하시오."
                    ),
                    answer_explanation=(
                        "삼각함수의 덧셈정리에 의해 sin(A + B) = sin A cos B + cos A sin B 이다. "
                        "사인을 합에 분배하여 sin A + sin B 로 계산하면 틀린 값이 된다."
                    ),
                    difficulty=_difficulty(a + b + k),
                    answer_format=_answer_format_for(correct),
                )
                if item is not None:
                    seen.add(key)
                    pool.append(item)
    random.Random(_POOL_SEED).shuffle(pool)
    return tuple(pool)


def _build_exp_zero_pool() -> tuple[_EvalItem, ...]:
    """n + a^0 값 뼈대 풀 — 정답 n+1(a^0=1)·오개념 n(a^0=0)·filler n+a(a^0=a)·n+2.

    a≥2·n≥1. 정답값 n+1로 dedup(같은 n은 정답 signature 동일). filler1=n+a가 a=2일 때
    filler2=n+2와 충돌하므로 그런 조합은 4-상이 검사에서 배제되고, 같은 n의 다른 a(≥3)로 채운다.
    n≥1이라 네 값 {n+1, n, n+a, n+2}은 모두 양(0 값 위생 통과).
    """
    pool: list[_EvalItem] = []
    seen: set[int] = set()
    for n in range(1, 31):
        for a in range(2, 8):
            correct_v = n + 1
            if correct_v in seen:
                continue  # 같은 n → 같은 정답값 → 구조 signature 충돌(회차 낭비 방지).
            correct = sympy.Integer(correct_v)
            misc = sympy.Integer(n)  # a^0=0 오인.
            filler1 = sympy.Integer(n + a)  # a^0=a 오인.
            filler2 = sympy.Integer(n + 2)  # 근접 오답(a^0=2 등).
            item = _assemble_item(
                values=(correct, misc, filler1, filler2),
                conditions=f"x = {n} + {a}**0",
                answer_str=str(correct_v),
                question_text=f"자연수 a = {a} 에 대하여 {n} + a^0 의 값을 구하시오.",
                answer_explanation=(
                    f"a^0 = 1 이므로 {n} + a^0 = {n} + 1 = {correct_v} 이다. "
                    f"a^0 을 0 으로 잘못 계산하면 {n} 이 되어 틀린다."
                ),
                difficulty=_difficulty(n + a),
                answer_format=AnswerFormat.자연수,
            )
            if item is not None:
                seen.add(correct_v)
                pool.append(item)
    random.Random(_POOL_SEED).shuffle(pool)
    return tuple(pool)


def _build_sqrt_pos_pool() -> tuple[_EvalItem, ...]:
    """√((-a)²) 값 뼈대 풀 — 정답 a(=|−a|)·오개념 -a(√(x²)=x 오인)·filler a²·2a.

    a≥3(a=2 스킵: 2a=a²=4 충돌). 네 값 {a, -a, a², 2a}은 a≥3에서 서로 다르다(a²≠2a·a≠2a·
    a≠a²·음수 -a는 양수들과 분리). 정답값 a로 dedup(각 a 유일). -a는 음수 선지(위생 0 값 아님).
    """
    pool: list[_EvalItem] = []
    seen: set[int] = set()
    for a in range(3, 30):
        correct_v = a
        if correct_v in seen:
            continue
        correct = sympy.Integer(a)
        misc = sympy.Integer(-a)  # √(x²)=x 오인(절댓값 누락).
        filler1 = sympy.Integer(a * a)  # 제곱을 안 벗김.
        filler2 = sympy.Integer(2 * a)  # √를 ×2로 혼동.
        item = _assemble_item(
            values=(correct, misc, filler1, filler2),
            conditions=f"x = sqrt((-{a})**2)",
            answer_str=str(correct_v),
            question_text=f"√((-{a})^2) 의 값을 구하시오.",
            answer_explanation=(
                f"√(x²) = |x| 이므로 √((-{a})²) = |-{a}| = {a} 이다. "
                f"√(x²) = x 로 오인하면 -{a} 가 되어 틀린다."
            ),
            difficulty=_difficulty(a),
            answer_format=AnswerFormat.자연수,
        )
        if item is not None:
            seen.add(correct_v)
            pool.append(item)
    random.Random(_POOL_SEED).shuffle(pool)
    return tuple(pool)


def _build_log_dist_pool() -> tuple[_EvalItem, ...]:
    """log₂(2^k + 2^k) 값 뼈대 풀 — 정답 k+1(2^k+2^k=2^{k+1})·오개념 2k(log 분배)·filler 2k+1·k.

    k≥2(k=1 스킵: k+1=2k=2 충돌). 네 값 {k+1, 2k, 2k+1, k}은 k≥2에서 서로 다르다(대수적 증명).
    정답값 k+1로 dedup(각 k 유일). k≥2라 모두 양(0 값 위생 통과).
    """
    pool: list[_EvalItem] = []
    seen: set[int] = set()
    for k in range(2, 28):
        correct_v = k + 1
        if correct_v in seen:
            continue
        correct = sympy.Integer(correct_v)
        misc = sympy.Integer(2 * k)  # log₂(2^k)+log₂(2^k)=k+k 오인(로그 합 분배).
        filler1 = sympy.Integer(2 * k + 1)  # 근접 오답.
        filler2 = sympy.Integer(k)  # 지수만 취함.
        item = _assemble_item(
            values=(correct, misc, filler1, filler2),
            conditions=f"x = log(2**{k} + 2**{k}, 2)",
            answer_str=str(correct_v),
            question_text=f"log_2(2^{k} + 2^{k}) 의 값을 구하시오.",
            answer_explanation=(
                f"2^{k} + 2^{k} = 2·2^{k} = 2^{k + 1} 이므로 값은 {correct_v} 이다. "
                f"로그를 합에 분배해 {k}+{k} = {2 * k} 로 하면 틀린다."
            ),
            difficulty=_difficulty(k),
            answer_format=AnswerFormat.자연수,
        )
        if item is not None:
            seen.add(correct_v)
            pool.append(item)
    random.Random(_POOL_SEED).shuffle(pool)
    return tuple(pool)


def _build_func_compose_pool() -> tuple[_EvalItem, ...]:
    """(f∘g)(c) 값 뼈대 풀 — f(x)=x+a, g(x)=bx. 정답 f(g(c))=bc+a·오개념 (g∘f)(c)=bc+ab.

    filler: bc(합성 +a 누락)·bc+a+b. b≥2·a≥1·c≥1. 유일 충돌 (a,b)=(2,2)에서 오개념 bc+ab가
    filler2 bc+a+b와 겹치나 4-상이 검사가 배제한다. 정답값 bc+a로 dedup. 모두 양(0 값 위생 통과).
    """
    pool: list[_EvalItem] = []
    seen: set[int] = set()
    for a in range(1, 6):
        for b in range(2, 6):
            for c in range(1, 7):
                correct_v = b * c + a
                if correct_v in seen:
                    continue
                correct = sympy.Integer(correct_v)
                misc = sympy.Integer(
                    b * c + a * b
                )  # (g∘f)(c)=g(c+a)=bc+ab(합성 순서 뒤집음).
                filler1 = sympy.Integer(b * c)  # +a 누락.
                filler2 = sympy.Integer(b * c + a + b)  # 계수 오합.
                item = _assemble_item(
                    values=(correct, misc, filler1, filler2),
                    conditions=f"x = {b}*{c} + {a}",
                    answer_str=str(correct_v),
                    question_text=(
                        f"두 함수 f(x) = x + {a}, g(x) = {b}x 에 대하여 "
                        f"(f∘g)({c}) 의 값을 구하시오."
                    ),
                    answer_explanation=(
                        f"(f∘g)({c}) = f(g({c})) = f({b * c}) = {b * c} + {a} = {correct_v} 이다. "
                        f"순서를 뒤집어 (g∘f)({c}) = g({c}+{a}) = {b * c + a * b} 로 하면 틀린다."
                    ),
                    difficulty=_difficulty(a + b + c),
                    answer_format=AnswerFormat.자연수,
                )
                if item is not None:
                    seen.add(correct_v)
                    pool.append(item)
    random.Random(_POOL_SEED).shuffle(pool)
    return tuple(pool)


def _build_sine_period_pool() -> tuple[_EvalItem, ...]:
    """y = sin(kx) 주기 뼈대 풀 — 정답 2π/k·오개념 2π(계수 무시 주기 불변)·filler π/k·2πk.

    k≥2. 네 값 {2π/k, 2π, π/k, 2πk}은 k≥2에서 서로 다르다(대수적 증명). 정답값(실수 근사)으로
    dedup(각 k 유일). 모두 양(0 값 위생 통과). 정답은 무리수(2π/k)라 answer_format=실수.
    """
    pi = sympy.pi
    pool: list[_EvalItem] = []
    seen: set[float] = set()
    for k in range(2, 28):
        correct = sympy.Integer(2) * pi / k
        key = round(_numeric(correct), 9)
        if key in seen:
            continue
        misc = sympy.Integer(2) * pi  # 계수 k 무시(주기 불변 오인).
        filler1 = pi / k  # 반주기 혼동.
        filler2 = sympy.Integer(2) * pi * k  # 계수 역적용.
        item = _assemble_item(
            values=(correct, misc, filler1, filler2),
            conditions=f"x = 2*pi/{k}",
            answer_str=_display(correct),
            question_text=f"함수 y = sin({k}x) 의 주기를 구하시오.",
            answer_explanation=(
                f"y = sin(bx) 의 주기는 2π/b 이므로 y = sin({k}x) 의 주기는 2π/{k} 이다. "
                f"계수 {k} 를 무시하면 주기를 2π 로 잘못 구한다."
            ),
            difficulty=_difficulty(k),
            answer_format=_answer_format_for(correct),
        )
        if item is not None:
            seen.add(key)
            pool.append(item)
    random.Random(_POOL_SEED).shuffle(pool)
    return tuple(pool)


def _build_translate_pool() -> tuple[_EvalItem, ...]:
    """g(x)=f(x-1)(우로 1 평행이동)의 g(c) 뼈대 풀 — f(x)=x²+bx. 정답 f(c-1)·오개념 f(c+1).

    평행이동 y=f(x-a)는 그래프를 *오른쪽*으로 a 이동(부호 반대). 오개념은 부호를 뒤집어
    f(x+a)로 봐 g(c)=f(c+1)로 계산한다. a=1 고정·b·d(=c-1)를 순회해 정답값 f(d)=d²+bd로 다수
    확보(정답값 dedup). filler: f(c)(이동 미적용)·d²(선형항 누락). 전부 양(0 값 위생).
    """
    pool: list[_EvalItem] = []
    seen: set[int] = set()
    for b in range(1, 5):
        for d in range(1, 8):  # d = c - 1 ≥ 1.
            c = d + 1
            correct_v = d * d + b * d  # f(d) = f(c-1).
            if correct_v in seen:
                continue
            correct = sympy.Integer(correct_v)
            misc = sympy.Integer(
                (d + 2) ** 2 + b * (d + 2)
            )  # f(c+1)=f(d+2)(부호 뒤집음).
            filler1 = sympy.Integer(c * c + b * c)  # f(c)(이동 미적용).
            filler2 = sympy.Integer(d * d)  # 선형항 bx 누락.
            item = _assemble_item(
                values=(correct, misc, filler1, filler2),
                conditions=f"x = {d}**2 + {b}*{d}",
                answer_str=str(correct_v),
                question_text=(
                    f"함수 f(x) = x^2 + {b}x 에 대하여 g(x) = f(x - 1) 일 때, "
                    f"g({c}) 의 값을 구하시오."
                ),
                answer_explanation=(
                    f"y = f(x-1) 은 그래프를 오른쪽으로 1 평행이동한 것이므로 "
                    f"g({c}) = f({c}-1) = f({d}) = {correct_v} 이다. 부호를 뒤집어 f({c}+1) 로 "
                    f"계산하면 틀린다."
                ),
                difficulty=_difficulty(b + d),
                answer_format=AnswerFormat.자연수,
            )
            if item is not None:
                seen.add(correct_v)
                pool.append(item)
    random.Random(_POOL_SEED).shuffle(pool)
    return tuple(pool)


def _build_product_rule_pool() -> tuple[_EvalItem, ...]:
    """f(x)=x^m, g(x)=x^n 의 곱의 미분계수 (fg)'(c) 뼈대 풀 — 정답 (m+n)c^(m+n-1)·오개념 f'(c)g'(c).

    곱의 미분은 (fg)'=f'g+fg'인데, 오개념은 (fg)'=f'g'로 오인해 f'(c)g'(c)=mn·c^(m+n-2)로
    계산한다. fg=x^(m+n)이라 정답은 (m+n)c^(m+n-1). (m,n,c) 순회·정답값 dedup. filler:
    (m+n)c^(m+n)(지수 오차)·mn·c^(m+n-1)(계수 오차). 전부 양(0 값 위생).
    """
    pool: list[_EvalItem] = []
    seen: set[int] = set()
    for m in range(1, 4):
        for n in range(1, 4):
            for c in range(2, 9):
                correct_v = (m + n) * c ** (m + n - 1)
                if correct_v in seen:
                    continue
                correct = sympy.Integer(correct_v)
                misc = sympy.Integer(
                    m * n * c ** (m + n - 2)
                )  # f'(c)g'(c)(곱미분 오인).
                filler1 = sympy.Integer((m + n) * c ** (m + n))  # 지수 미하강.
                filler2 = sympy.Integer(m * n * c ** (m + n - 1))  # 계수 오합.
                item = _assemble_item(
                    values=(correct, misc, filler1, filler2),
                    conditions=f"x = {m + n}*{c}**{m + n - 1}",
                    answer_str=str(correct_v),
                    question_text=(
                        f"두 함수 f(x) = x^{m}, g(x) = x^{n} 에 대하여 함수 f(x)g(x) 의 "
                        f"x = {c} 에서의 미분계수를 구하시오."
                    ),
                    answer_explanation=(
                        f"f(x)g(x) = x^{m + n} 이므로 미분계수는 {m + n}·{c}^{m + n - 1} "
                        f"= {correct_v} 이다. (fg)' = f'g' 로 오인하면 틀린 값이 된다."
                    ),
                    difficulty=_difficulty(m + n + c),
                    answer_format=AnswerFormat.자연수,
                )
                if item is not None:
                    seen.add(correct_v)
                    pool.append(item)
    random.Random(_POOL_SEED).shuffle(pool)
    return tuple(pool)


def _build_fraction_cancel_pool() -> tuple[_EvalItem, ...]:
    """(a+b)/a 값 뼈대 풀 — 정답 (a+b)/a·오개념 b(분모 a만 약분해 b로 남김)·filler a·a+b.

    (a+b)/a = 1 + b/a 인데, 분자의 a와 분모의 a를 지워 b로 오인한다(잘못된 약분). 네 값
    {(a+b)/a, b, a, a+b}는 대체로 서로 다르며 4-상이 검사로 이중 보장한다. 정답값(실수 근사)으로
    dedup. 값이 정수면 자연수·아니면 분수 answer_format.
    """
    pool: list[_EvalItem] = []
    seen: set[float] = set()
    for a in range(2, 8):
        for b in range(2, 16):
            correct = sympy.Rational(a + b, a)
            key = round(_numeric(correct), 9)
            if key in seen:
                continue
            item = _assemble_item(
                values=(
                    correct,
                    sympy.Integer(b),  # 분모 a만 약분해 b로 오인(잘못된 약분).
                    sympy.Integer(a),  # 분모.
                    sympy.Integer(a + b),  # 분자.
                ),
                conditions=f"x = ({a}+{b})/{a}",
                answer_str=_display(correct),
                question_text=(
                    f"두 자연수 a = {a}, b = {b} 에 대하여 (a + b) / a 의 값을 구하시오."
                ),
                answer_explanation=(
                    f"(a + b) / a = 1 + b/a 이므로 a = {a}, b = {b} 를 대입하면 "
                    f"{_display(correct)} 이다. 분자와 분모의 a 를 지워 b 로 약분하면 틀린다."
                ),
                difficulty=_difficulty(a + b),
                answer_format=_answer_format_for(correct),
            )
            if item is not None:
                seen.add(key)
                pool.append(item)
    random.Random(_POOL_SEED).shuffle(pool)
    return tuple(pool)


def _build_polygon_angle_sum_pool() -> tuple[_EvalItem, ...]:
    """n각형 내각의 합 뼈대 풀 — 정답 (n-2)·180·오개념 180(삼각형 값 고정)·filler n·180·(n-1)·180.

    n각형 내각의 합은 (n-2)·180° 인데, 모든 다각형에서 180° 로 고정 오인한다. n≥4라 네 값
    {(n-2)·180, 180, n·180, (n-1)·180}는 서로 다르다. 정답값으로 dedup. 모두 자연수.
    """
    pool: list[_EvalItem] = []
    seen: set[int] = set()
    for n in range(4, 30):
        correct_v = (n - 2) * 180
        if correct_v in seen:
            continue
        item = _assemble_item(
            values=(
                sympy.Integer(correct_v),
                sympy.Integer(180),  # 다각형 무관 180° 고정 오인.
                sympy.Integer(n * 180),  # -2 누락.
                sympy.Integer((n - 1) * 180),  # 한 변 오차.
            ),
            conditions=f"x = ({n}-2)*180",
            answer_str=str(correct_v),
            question_text=f"{n}각형의 내각의 크기의 합을 구하시오. (단위: 도)",
            answer_explanation=(
                f"n각형의 내각의 합은 (n - 2)·180° 이므로 {n}각형은 "
                f"({n} - 2)·180 = {correct_v}° 이다. 모든 다각형의 내각의 합을 180° 로 여기면 "
                "틀린다."
            ),
            difficulty=_difficulty(n),
            answer_format=AnswerFormat.자연수,
        )
        if item is not None:
            seen.add(correct_v)
            pool.append(item)
    random.Random(_POOL_SEED).shuffle(pool)
    return tuple(pool)


def _build_area_perimeter_pool() -> tuple[_EvalItem, ...]:
    """직사각형 넓이 뼈대 풀 — 정답 a·b·오개념 2(a+b)(넓이-둘레 혼동)·filler a+b·2ab.

    가로 a·세로 b 직사각형의 넓이는 a·b 인데, 둘레 2(a+b)와 혼동한다("둘레가 크면 넓이도 크다"류).
    네 값 {ab, 2(a+b), a+b, 2ab}는 4-상이 검사로 이중 보장한다. 정답값 ab로 dedup. 모두 자연수.
    """
    pool: list[_EvalItem] = []
    seen: set[int] = set()
    for a in range(2, 12):
        for b in range(a + 1, 16):
            correct_v = a * b
            if correct_v in seen:
                continue
            item = _assemble_item(
                values=(
                    sympy.Integer(correct_v),
                    sympy.Integer(2 * (a + b)),  # 둘레와 혼동.
                    sympy.Integer(a + b),  # 반둘레.
                    sympy.Integer(2 * a * b),  # 넓이 2배.
                ),
                conditions=f"x = {a}*{b}",
                answer_str=str(correct_v),
                question_text=(
                    f"가로가 {a}, 세로가 {b} 인 직사각형의 넓이를 구하시오."
                ),
                answer_explanation=(
                    f"직사각형의 넓이는 가로×세로 = {a}×{b} = {correct_v} 이다. "
                    f"둘레 2×({a}+{b}) = {2 * (a + b)} 와 혼동하면 틀린다."
                ),
                difficulty=_difficulty(a + b),
                answer_format=AnswerFormat.자연수,
            )
            if item is not None:
                seen.add(correct_v)
                pool.append(item)
    random.Random(_POOL_SEED).shuffle(pool)
    return tuple(pool)


def _build_circle_radius_pool() -> tuple[_EvalItem, ...]:
    """원 x²+y²=r² 반지름 뼈대 풀 — 정답 r·오개념 r²(r²을 반지름으로 오인)·filler 2r·r²+r.

    x² + y² = r² 의 반지름은 r 인데, 우변 r² 을 곧 반지름으로 오인한다(제곱을 안 벗김). r≥3라 네 값
    {r, r², 2r, r²+r}는 서로 다르다. 문항 우변은 r² 을 정수로 제시(완전제곱). 정답값 r로 dedup.
    """
    pool: list[_EvalItem] = []
    seen: set[int] = set()
    for r in range(3, 30):
        r_sq = r * r
        if r in seen:
            continue
        item = _assemble_item(
            values=(
                sympy.Integer(r),
                sympy.Integer(r_sq),  # r² 을 반지름으로 오인.
                sympy.Integer(2 * r),  # 지름과 혼동.
                sympy.Integer(r_sq + r),  # 근접 오답.
            ),
            conditions=f"x = sqrt({r_sq})",
            answer_str=str(r),
            question_text=f"원 x^2 + y^2 = {r_sq} 의 반지름의 길이를 구하시오.",
            answer_explanation=(
                f"x² + y² = r² 에서 반지름은 r 이므로 r² = {r_sq} 이면 반지름은 {r} 이다. "
                f"우변 {r_sq} 을 반지름으로 여기면 틀린다."
            ),
            difficulty=_difficulty(r),
            answer_format=AnswerFormat.자연수,
        )
        if item is not None:
            seen.add(r)
            pool.append(item)
    random.Random(_POOL_SEED).shuffle(pool)
    return tuple(pool)


_POOL_FACTORY = {
    "distribution": _build_distribution_pool,
    "chain_rule": _build_chain_rule_pool,
    "sine_sum": _build_sine_pool,
    "exp_zero": _build_exp_zero_pool,
    "sqrt_pos": _build_sqrt_pos_pool,
    "log_dist": _build_log_dist_pool,
    "func_compose": _build_func_compose_pool,
    "sine_period": _build_sine_period_pool,
    "translate": _build_translate_pool,
    "product_rule": _build_product_rule_pool,
    "fraction_cancel": _build_fraction_cancel_pool,
    "polygon_angle_sum": _build_polygon_angle_sum_pool,
    "area_perimeter": _build_area_perimeter_pool,
    "circle_radius": _build_circle_radius_pool,
}


class MisconceptionEvalMCSkeletonGenerator:
    """오개념 수치평가 객관식 결정론 스켈레톤 생성기 — `EquivalentProblemGenerator` 좌석(LLM 0).

    `template`(distribution/chain_rule/sine_sum/exp_zero/sqrt_pos/log_dist/func_compose/
    sine_period)이 수학 실체를, 생성자 `distractor_codes`가 오답 선지의 오개념·op-code id를 정한다
    (극값 MC 규약 미러·L4 하드코딩 0). `distractor_codes`는 단일 엔트리
    `{kebab: (misconception_id, op_code)}`를 기대한다(op_code는 None 허용 — op-code 없는 오개념은
    오개념만 태깅) — 각 문항이 오개념 오답 *1건*만
    태깅하기 때문(filler는 미태깅). 풀을 순서대로 소비하며 후보를 낸다(소진 시 None —
    generation_failed로 정직 기록). `skip_signatures`에 이미 코퍼스에 있는 구조 signature를 주면
    해당 뼈대를 건너뛴다(배치 재실행 dedup 낭비 방지·오케스트레이터 signature_index 공유).
    """

    def __init__(
        self,
        template: TemplateKind,
        distractor_codes: Mapping[str, tuple[str, str | None]],
        *,
        skip_signatures: AbstractSet[str] | None = None,
        slug_prefix: str = "wm-misc-eval-mc",
        subject: Subject = Subject.공통,
        curriculum_version: Curriculum = Curriculum.REVISION_2022,
        valid_from_year: int = 2022,
        concept_relevance: float = 0.95,
    ) -> None:
        if template not in _POOL_FACTORY:
            raise ValueError(
                f"미지원 template: {template!r} (distribution/chain_rule/sine_sum/exp_zero/"
                "sqrt_pos/log_dist/func_compose/sine_period/translate/product_rule/"
                "fraction_cancel/polygon_angle_sum/area_perimeter/circle_radius)"
            )
        if not distractor_codes:
            raise ValueError(
                "distractor_codes 주입 누락 — 오개념 오답 태깅용 (misconception_id, op_code)가 "
                "최소 1건 필요하다(L4 정본에서 조성 루트가 주입)."
            )
        # 각 문항이 오개념 오답 1건만 태깅하므로 단일 (misconception_id, op_code)만 쓴다.
        self._misconception_id, self._op_code = next(iter(distractor_codes.values()))
        self._template: TemplateKind = template
        self._pool = _POOL_FACTORY[template]()
        self._index = 0
        self._skip = skip_signatures
        self._slug_prefix = slug_prefix
        self._subject = subject
        self._curriculum_version = curriculum_version
        self._valid_from_year = valid_from_year
        concept_src_id, unit_code = _TEMPLATE_META[template]
        self._unit_codes = [unit_code]
        self._concept_tags = [
            ConceptTag(
                concept_src_id=concept_src_id,
                role="PRIMARY",
                relevance=concept_relevance,
            )
        ]

    # ── EquivalentProblemGenerator 좌석 ────────────────────────────────────
    def generate(self, spec: EquivalenceSpec) -> CandidateProblem | None:
        """다음 뼈대를 후보로 조립 — skip 집합에 있는 구조는 건너뛰고, 풀 소진 시 None."""
        while self._index < len(self._pool):
            item = self._pool[self._index]
            self._index += 1
            if self._skip is not None:
                signature = canonical_signature(item.conditions, None)
                if signature is not None and signature in self._skip:
                    continue  # 이미 코퍼스에 있는 구조 — 회차 낭비 없이 다음 뼈대로.
            return self._assemble(spec, item)
        return None

    # ── 조립(전부 결정론·수치의 단일 진실 원천은 뼈대) ─────────────────────
    def _assemble(self, spec: EquivalenceSpec, item: _EvalItem) -> CandidateProblem:
        standard_codes = sorted(spec.achievement_standard_codes)
        answer_text = item.choices[item.answer_index]
        slug = self._stable_slug(item.question_text, answer_text, standard_codes)

        # 오개념 오답 1건만 태깅(filler는 미태깅·스키마 계약: 정답 선지 제외).
        distractor_map = [
            DistractorEntry(
                choice_index=item.misc_index,
                misconception_id=self._misconception_id,
                op_code=self._op_code,
            )
        ]

        problem = Problem(
            problem_id=uuid.uuid5(uuid.NAMESPACE_URL, f"whymath:problem:{slug}"),
            slug=slug,
            source_type=SourceType.자체생성,  # 저작권 구조적 강제(자작 뼈대·본문성 원본 0)
            curriculum_version=self._curriculum_version,
            valid_from_year=self._valid_from_year,
            subject=self._subject,
            unit_codes=list(self._unit_codes),
            difficulty_overall=item.difficulty,
            question_format=QuestionFormat.객관식,
            answer_format=item.answer_format,
            achievement_standard_codes=standard_codes,
            question_text=item.question_text,
            choices=list(item.choices),
            answer=answer_text,
            answer_explanation=item.answer_explanation,
            distractor_map=distractor_map,
        )
        provenance = ContentProvenance(
            generation_type=GenerationType.FULLY_GENERATED,
            license=LicenseType.WHYMATH_GENERATED,
            original_source=None,
            transformation_pipeline={
                "steps": [
                    "결정론 수치평가 MC 스켈레톤 조립(닫힌 값 4지선다·오개념 오답 태깅)",
                    "S2-a 수용 게이트",
                    "사람 검수 큐(오개념 귀속 교수학 검수)",
                ],
            },
        )
        return CandidateProblem(
            problem=problem,
            provenance=provenance,
            conditions=item.conditions,  # dummy x 등식(정답 검산용·호출자 제공)
            answer_map={"x": item.answer_str},
            answer_selection=None,  # 유일해(닫힌 값)라 근 선택 불요.
            answer_aggregate=None,
            solution_steps=None,
            concept_tags=list(self._concept_tags),
        )

    def _stable_slug(
        self, question_text: str, answer: str, codes: Sequence[str]
    ) -> str:
        """결정론 안정 slug — 내용 해시(멱등 upsert 키·극값 MC 규약 미러)."""
        payload = "|".join([question_text, answer, ",".join(sorted(codes))])
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]
        return f"{self._slug_prefix}-{digest}"
