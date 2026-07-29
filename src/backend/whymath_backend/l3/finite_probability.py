"""유한 표본공간 **전수 열거** 검산기 — SymPy 불가 영역의 *기계 가능 부분*(S4-13 ①).

정본: `docs/architecture/problem_bank_gap_review.md` §3 D7 — "가능한 부분은 기계로(확률:
유한 표본공간 전수 열거·조합 계산은 SymPy/정수 연산 가능 — **추론 서술**과 **수치 검산**을
분리해 후자는 Tier1 유지)". 이 모듈이 그 *후자*(수치 축)의 단일 원천이다.

**무엇을 증명하는가(경계를 정직하게)**:
  - ✅ 증명함: 주어진 *형식 모델*(표본공간 명세 + 사건 술어) 위에서 유리한 경우의 수·확률이
    주장값과 같다는 것. 표본공간을 **빠짐없이 열거**하고 정확 유리수(`fractions.Fraction`)로
    세므로 이 축은 표본 검산이 아니라 **전수 증명**이다(기존 `verify_answer`의 Tier1 난수
    샘플링보다 강한 등급 — `verification_tier.py` 참조).
  - ❌ 증명 못 함: 학생이 읽는 **한국어 발문**이 그 형식 모델과 같은 것을 뜻하는지. 등확률
    가정이 발문에 정당한지. 조건이 빠지지 않았는지. 이 *잔여*는 기계 불가이며
    `cross_verify.py`(독립 다관점 LLM 교차검증) + Wilson 표본 검수 게이트가 맡는다.

**왜 SymPy가 아닌가**(재구현 금지 원칙 정합): 여기서 필요한 판정은 대수 동치가 아니라 *유한
집합의 정확한 개수 세기*다. 심볼릭 대수(`symbolic_equivalence`·`equivalent/canonicalize`)의
권위를 침범하지 않으며, 그쪽이 할 수 없는 축(열거)을 stdlib 정확 유리수로 닫는다. 주장값 파싱도
`sympify`(임의 문자열 평가)가 아니라 `Fraction`(파서·평가 없음)을 쓴다 — 코퍼스 문자열을
평가 경로에 태우지 않는다.

**DSL**(`verify` 계약의 `conditions` 문자열 — 신규 필드 0):

    space=dice(n=2,faces=6); event=sum==7
    space=coin(n=3); event=count(H)==2
    space=draw(items=[R,R,R,B,B],k=2,ordered=false,replace=false); event=count(R)==2
    space=dice(n=2,faces=6); event=sum>=10; given=max>=5      ← 조건부확률

7계층: L3 지역. 동일 계층(`verify_answer.AnswerVerdict`)만 import. DB 0·네트워크 0·LLM 0.
"""

from __future__ import annotations

import itertools
import re
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from fractions import Fraction
from typing import Literal

from whymath_backend.l3.verify_answer import AnswerVerdict

__all__ = [
    "EnumerationResult",
    "FiniteProbabilityError",
    "SampleSpaceSpec",
    "describe_model_ko",
    "enumerate_model",
    "parse_finite_model",
    "verify_finite_count",
    "verify_finite_probability",
]


class FiniteProbabilityError(ValueError):
    """DSL 파싱·모델 구성 실패 — 조용한 통과 금지(호출자가 unverifiable로 변환)."""


# 전수 열거 한도 — 이를 넘으면 "유한하지만 전수 불가"로 정직히 회피한다(추정 금지).
# 30만은 5면체 7개(78125)·6면체 6개(46656)·주머니 20개 중 6개 순열(27M은 초과)을 가늠한 값으로,
# 결정론 배치가 수 초 내에 끝나는 상한이다.
MAX_OUTCOMES = 300_000

# 컨테이너 크기 상한 — DSL이 조합폭발 인자를 받는 것 자체를 막는다(열거 전 차단).
_MAX_TRIALS = 12
_MAX_FACES = 20
_MAX_ITEMS = 20

_Outcome = tuple[object, ...]
_CompareOp = Literal["==", "!=", ">=", "<=", ">", "<"]

# 술어 원자 — sum/max/min/distinct/count(라벨) 에 비교 연산자와 정수를 결합한 형태만 허용한다.
# 문법을 *닫아* 두는 것이 핵심이다(임의 표현식 평가 없음 — eval·sympify 경로 0).
_ATOM_RE = re.compile(
    r"^(?:(sum|max|min|distinct)|count\(\s*([A-Za-z0-9가-힣]+)\s*\))"
    r"\s*(==|!=|>=|<=|>|<)\s*(-?\d+)$"
)
_SPACE_RE = re.compile(r"^([a-z]+)\((.*)\)$", re.DOTALL)


# ──────────────────────────────────────────────────────────────────────────
# 술어(사건) — 닫힌 문법의 원자 + and/or 결합
# ──────────────────────────────────────────────────────────────────────────
@dataclass(frozen=True, slots=True)
class _Atom:
    """술어 원자 — 결과 튜플에서 뽑은 정수 특성값을 상수와 비교한다."""

    feature: Literal["sum", "max", "min", "distinct", "count"]
    label: str | None
    op: _CompareOp
    value: int

    def measure(self, outcome: _Outcome) -> int:
        """결과 튜플의 특성값(정수). 수치 특성인데 라벨 표본공간이면 오류(조용한 0 금지)."""
        if self.feature == "count":
            return sum(1 for item in outcome if str(item) == self.label)
        if self.feature == "distinct":
            return len(set(outcome))
        numbers = [item for item in outcome if isinstance(item, int)]
        if len(numbers) != len(outcome):
            raise FiniteProbabilityError(
                f"술어 '{self.feature}'는 수치 표본공간에서만 쓸 수 있음(라벨 결과 {outcome!r})"
            )
        if self.feature == "sum":
            return sum(numbers)
        return max(numbers) if self.feature == "max" else min(numbers)

    def holds(self, outcome: _Outcome) -> bool:
        """이 원자가 결과에서 참인가."""
        got = self.measure(outcome)
        if self.op == "==":
            return got == self.value
        if self.op == "!=":
            return got != self.value
        if self.op == ">=":
            return got >= self.value
        if self.op == "<=":
            return got <= self.value
        if self.op == ">":
            return got > self.value
        return got < self.value


@dataclass(frozen=True, slots=True)
class _Predicate:
    """원자들의 결합 — 연산자는 and 또는 or 중 *하나만*(우선순위 모호성 제거)."""

    atoms: tuple[_Atom, ...]
    connective: Literal["and", "or"]

    def holds(self, outcome: _Outcome) -> bool:
        if self.connective == "and":
            return all(atom.holds(outcome) for atom in self.atoms)
        return any(atom.holds(outcome) for atom in self.atoms)


def _parse_atom(text: str) -> _Atom:
    match = _ATOM_RE.match(text.strip())
    if match is None:
        raise FiniteProbabilityError(f"술어 원자 문법 불일치: {text!r}")
    feature_raw, label, op, value = match.groups()
    feature = feature_raw if feature_raw is not None else "count"
    return _Atom(
        feature=feature,  # type: ignore[arg-type]
        label=label,
        op=op,  # type: ignore[arg-type]
        value=int(value),
    )


def _parse_predicate(text: str) -> _Predicate:
    """술어 파싱 — ' and '/' or ' 혼용은 우선순위가 모호하므로 거부(모르면 모른다)."""
    raw = text.strip()
    if not raw:
        raise FiniteProbabilityError("술어가 비어 있음")
    has_and = " and " in raw
    has_or = " or " in raw
    if has_and and has_or:
        raise FiniteProbabilityError(f"and/or 혼용은 우선순위 모호 — 거부: {raw!r}")
    connective: Literal["and", "or"] = "or" if has_or else "and"
    parts = raw.split(" or ") if has_or else raw.split(" and ")
    return _Predicate(atoms=tuple(_parse_atom(part) for part in parts), connective=connective)


# ──────────────────────────────────────────────────────────────────────────
# 표본공간 명세
# ──────────────────────────────────────────────────────────────────────────
@dataclass(frozen=True, slots=True)
class SampleSpaceSpec:
    """표본공간 명세 — 등확률 결과의 유한 집합을 *생성 규칙*으로 표현한다.

    `kind`별 인자만 유효하다(나머지는 None). 등확률이 성립하는 구성만 허용한다 — 예컨대
    '비순서·복원'(중복조합)은 각 결과의 확률이 다르므로 파서가 거부한다(조용한 오답 방지).
    """

    kind: Literal["dice", "coin", "draw"]
    trials: int
    faces: int | None = None
    items: tuple[str, ...] = ()
    ordered: bool = True
    replace: bool = True


@dataclass(frozen=True, slots=True)
class FiniteModel:
    """형식 모델 = 표본공간 + 사건 술어 + (선택) 조건 술어. 발문과의 정합은 *기계 밖*이다."""

    space: SampleSpaceSpec
    event: _Predicate
    given: _Predicate | None
    source: str


def _split_top_level(text: str, sep: str) -> list[str]:
    """대괄호 깊이를 존중하는 분할 — items=[R,R,B] 안의 쉼표가 인자 구분자로 새지 않게."""
    parts: list[str] = []
    depth = 0
    current: list[str] = []
    for ch in text:
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth < 0:
                raise FiniteProbabilityError(f"대괄호 짝 불일치: {text!r}")
        if ch == sep and depth == 0:
            parts.append("".join(current))
            current = []
        else:
            current.append(ch)
    if depth != 0:
        raise FiniteProbabilityError(f"대괄호 짝 불일치: {text!r}")
    parts.append("".join(current))
    return parts


def _parse_kwargs(body: str) -> dict[str, str]:
    kwargs: dict[str, str] = {}
    for chunk in _split_top_level(body, ","):
        piece = chunk.strip()
        if not piece:
            continue
        if "=" not in piece:
            raise FiniteProbabilityError(f"표본공간 인자 형식 오류(key=value 아님): {piece!r}")
        key, _, value = piece.partition("=")
        kwargs[key.strip()] = value.strip()
    return kwargs


def _require_int(kwargs: dict[str, str], key: str, *, low: int, high: int) -> int:
    if key not in kwargs:
        raise FiniteProbabilityError(f"표본공간 인자 누락: {key}")
    try:
        value = int(kwargs[key])
    except ValueError as exc:
        raise FiniteProbabilityError(f"표본공간 인자 {key}는 정수여야 함: {kwargs[key]!r}") from exc
    if not low <= value <= high:
        raise FiniteProbabilityError(f"표본공간 인자 {key}={value}가 허용 범위[{low},{high}] 밖")
    return value


def _require_bool(kwargs: dict[str, str], key: str) -> bool:
    raw = kwargs.get(key)
    if raw not in ("true", "false"):
        raise FiniteProbabilityError(f"표본공간 인자 {key}는 true/false여야 함: {raw!r}")
    return raw == "true"


def _parse_space(text: str) -> SampleSpaceSpec:
    match = _SPACE_RE.match(text.strip())
    if match is None:
        raise FiniteProbabilityError(f"표본공간 문법 불일치: {text!r}")
    kind, body = match.group(1), match.group(2)
    kwargs = _parse_kwargs(body)
    if kind == "dice":
        return SampleSpaceSpec(
            kind="dice",
            trials=_require_int(kwargs, "n", low=1, high=_MAX_TRIALS),
            faces=_require_int(kwargs, "faces", low=2, high=_MAX_FACES),
        )
    if kind == "coin":
        return SampleSpaceSpec(
            kind="coin",
            trials=_require_int(kwargs, "n", low=1, high=_MAX_TRIALS),
        )
    if kind == "draw":
        raw_items = kwargs.get("items", "")
        if not (raw_items.startswith("[") and raw_items.endswith("]")):
            raise FiniteProbabilityError(f"draw items는 [a,b,c] 형태여야 함: {raw_items!r}")
        items = tuple(tok.strip() for tok in raw_items[1:-1].split(",") if tok.strip())
        if not 1 <= len(items) <= _MAX_ITEMS:
            raise FiniteProbabilityError(f"draw items 개수 {len(items)}가 허용 범위[1,20] 밖")
        ordered = _require_bool(kwargs, "ordered")
        replace = _require_bool(kwargs, "replace")
        k = _require_int(kwargs, "k", low=1, high=_MAX_TRIALS)
        if not replace and k > len(items):
            raise FiniteProbabilityError(f"비복원 추출인데 k={k} > items {len(items)}")
        if replace and not ordered:
            # 중복조합은 각 결과의 확률이 다르다 — 등확률 전수 열거의 전제가 깨진다.
            raise FiniteProbabilityError("복원·비순서(중복조합)는 등확률이 아니어서 거부")
        return SampleSpaceSpec(kind="draw", trials=k, items=items, ordered=ordered, replace=replace)
    raise FiniteProbabilityError(f"미지 표본공간 종류: {kind!r}")


def parse_finite_model(conditions: str | Sequence[str]) -> FiniteModel:
    """`verify.conditions` 문자열 → 형식 모델. 실패는 `FiniteProbabilityError`(조용한 통과 0).

    형식: `space=...; event=...[; given=...]`. 리스트가 오면 단일 원소만 허용한다(연립 조건은
    이 도메인에 없다 — 있으면 파싱 오류로 정직히 드러난다).
    """
    if not isinstance(conditions, str):
        seq = list(conditions)
        if len(seq) != 1:
            raise FiniteProbabilityError("유한 확률 조건은 단일 문자열이어야 함")
        conditions = seq[0]
    parts = _split_top_level(conditions, ";")
    kwargs: dict[str, str] = {}
    for chunk in parts:
        piece = chunk.strip()
        if not piece:
            continue
        key, sep, value = piece.partition("=")
        if not sep:
            raise FiniteProbabilityError(f"조건 절 형식 오류(key=value 아님): {piece!r}")
        name = key.strip()
        if name in kwargs:
            raise FiniteProbabilityError(f"조건 절 중복: {name}")
        kwargs[name] = value.strip()
    unknown = set(kwargs) - {"space", "event", "given"}
    if unknown:
        raise FiniteProbabilityError(f"미지 조건 절: {sorted(unknown)}")
    if "space" not in kwargs or "event" not in kwargs:
        raise FiniteProbabilityError("space·event 절은 필수")
    given_raw = kwargs.get("given")
    return FiniteModel(
        space=_parse_space(kwargs["space"]),
        event=_parse_predicate(kwargs["event"]),
        given=_parse_predicate(given_raw) if given_raw is not None else None,
        source=conditions,
    )


# ──────────────────────────────────────────────────────────────────────────
# 전수 열거
# ──────────────────────────────────────────────────────────────────────────
def _dice_faces(space: SampleSpaceSpec) -> int:
    """dice 공간의 면 수 — 파서가 항상 채우지만 계약을 명시적으로 지킨다(조용한 None 금지)."""
    if space.faces is None:  # pragma: no cover — 파서 계약상 도달 불가(방어적 명시)
        raise FiniteProbabilityError("dice 표본공간에 faces가 없음")
    return space.faces


def _space_size(space: SampleSpaceSpec) -> int:
    """열거 전에 크기를 *먼저* 계산 — 한도 초과를 열거 시작 전에 차단한다."""
    if space.kind == "dice":
        return int(_dice_faces(space) ** space.trials)
    if space.kind == "coin":
        return int(2**space.trials)
    n, k = len(space.items), space.trials
    if space.replace:  # ordered·replace(중복순열)
        return int(n**k)
    size = 1
    for i in range(k):  # ordered·비복원 = nPk, 비순서·비복원 = nCk
        size *= n - i
    if not space.ordered:
        for i in range(1, k + 1):
            size //= i
    return size


def _iter_outcomes(space: SampleSpaceSpec) -> Iterator[_Outcome]:
    """등확률 결과 전수 생성.

    `draw`는 **라벨이 아니라 물체 인덱스**를 열거한 뒤 라벨로 사상한다 — 같은 색 공이 여러
    개일 때 '색 조합'을 세면 등확률이 깨지기 때문이다(빨강2·파랑3에서 {빨,파}는 {빨,빨}보다
    많다). 인덱스 열거가 이 도메인의 정확성 핵심이다.
    """
    if space.kind == "dice":
        yield from itertools.product(range(1, _dice_faces(space) + 1), repeat=space.trials)
        return
    if space.kind == "coin":
        yield from itertools.product(("H", "T"), repeat=space.trials)
        return
    idx = range(len(space.items))
    if space.replace:
        combos: Iterator[tuple[int, ...]] = itertools.product(idx, repeat=space.trials)
    elif space.ordered:
        combos = itertools.permutations(idx, space.trials)
    else:
        combos = itertools.combinations(idx, space.trials)
    for combo in combos:
        yield tuple(space.items[i] for i in combo)


@dataclass(frozen=True, slots=True)
class EnumerationResult:
    """전수 열거 결과 — 표본공간 크기·조건 만족 수·유리한 경우 수·정확 확률(유리수).

    `given`이 없으면 `conditioned == total`이다. `probability`는 `favorable/conditioned`의
    정확 유리수(부동소수 반올림 없음). `conditioned == 0`이면 확률이 정의되지 않아 None.
    """

    total: int
    conditioned: int
    favorable: int
    probability: Fraction | None


def enumerate_model(model: FiniteModel) -> EnumerationResult:
    """형식 모델을 전수 열거해 정확 개수·확률을 낸다. 한도 초과·모델 오류는 예외."""
    size = _space_size(model.space)
    if size > MAX_OUTCOMES:
        raise FiniteProbabilityError(
            f"표본공간 크기 {size}가 전수 열거 한도 {MAX_OUTCOMES} 초과 — 전수 증명 불가"
        )
    total = 0
    conditioned = 0
    favorable = 0
    for outcome in _iter_outcomes(model.space):
        total += 1
        if model.given is not None and not model.given.holds(outcome):
            continue
        conditioned += 1
        if model.event.holds(outcome):
            favorable += 1
    probability = Fraction(favorable, conditioned) if conditioned else None
    return EnumerationResult(
        total=total, conditioned=conditioned, favorable=favorable, probability=probability
    )


# ──────────────────────────────────────────────────────────────────────────
# 한국어 풀어쓰기 — 교차검증 ③(서술-형식모델 정합) 관점의 입력
# ──────────────────────────────────────────────────────────────────────────
_FEATURE_KO = {
    "sum": "값들의 합",
    "max": "값들의 최댓값",
    "min": "값들의 최솟값",
    "distinct": "서로 다른 값의 개수",
}
_OP_KO = {
    "==": "가 {v}와 같다",
    "!=": "가 {v}와 같지 않다",
    ">=": "가 {v} 이상이다",
    "<=": "가 {v} 이하이다",
    ">": "가 {v}보다 크다",
    "<": "가 {v}보다 작다",
}


def _atom_ko(atom: _Atom) -> str:
    subject = (
        f"'{atom.label}'이(가) 나온 횟수" if atom.feature == "count" else _FEATURE_KO[atom.feature]
    )
    return subject + _OP_KO[atom.op].format(v=atom.value)


def _predicate_ko(pred: _Predicate) -> str:
    joiner = " 그리고 " if pred.connective == "and" else " 또는 "
    return joiner.join(_atom_ko(atom) for atom in pred.atoms)


def _space_ko(space: SampleSpaceSpec) -> str:
    if space.kind == "dice":
        return (
            f"서로 구별되는 {space.faces}면 주사위 {space.trials}개를 던져 나온 눈의 "
            f"순서쌍 전체(각 경우의 확률이 모두 같다고 본다)"
        )
    if space.kind == "coin":
        return (
            f"동전을 {space.trials}번 던져 나온 앞뒤(H/T) 순서쌍 전체"
            "(각 경우의 확률이 모두 같다고 본다)"
        )
    order = "순서를 구별하여" if space.ordered else "순서를 구별하지 않고"
    how = "꺼낸 것을 다시 넣으며" if space.replace else "꺼낸 것을 다시 넣지 않고"
    items = ", ".join(space.items)
    return (
        f"물체 {len(space.items)}개([{items}], 같은 라벨이라도 서로 다른 개체로 본다)에서 "
        f"{how} {space.trials}개를 {order} 뽑는 모든 경우"
        "(각 경우의 확률이 모두 같다고 본다)"
    )


def describe_model_ko(model: FiniteModel, result: EnumerationResult) -> str:
    """형식 모델 + 열거 결과를 한국어 산문으로 — LLM 교차검증 ③ 관점이 발문과 대조할 대상.

    *발문을 참조하지 않는다*. 오직 기계가 실제로 검산한 모델만을 서술하므로, 이 산문과 발문이
    어긋나면 "기계가 다른 문제를 풀었다"는 뜻이 된다(검증자가 잡아야 할 결함).
    """
    lines = [
        f"표본공간: {_space_ko(model.space)}. 총 경우의 수 {result.total}가지.",
        f"사건 A: {_predicate_ko(model.event)}.",
    ]
    if model.given is not None:
        lines.append(
            f"조건 B: {_predicate_ko(model.given)}. "
            f"조건 B를 만족하는 경우 {result.conditioned}가지 중 A도 만족하는 경우 "
            f"{result.favorable}가지."
        )
    else:
        lines.append(f"사건 A를 만족하는 경우 {result.favorable}가지.")
    if result.probability is not None:
        lines.append(
            f"따라서 확률 = {result.probability.numerator}/{result.probability.denominator}."
        )
    return "\n".join(lines)


# ──────────────────────────────────────────────────────────────────────────
# 검산기 — 수용 게이트(`acceptance._CONCEPTUAL_VERIFIERS`)가 부르는 좌석
# ──────────────────────────────────────────────────────────────────────────
def _parse_claimed_fraction(claimed: str) -> Fraction | None:
    """주장 확률 파싱 — 'a/b'·정수·유한소수만. 평가기(eval/sympify) 경로 0.

    근삿값(0.1389 같은 반올림)은 정확 유리수와 다르므로 *통과하지 않는다* — 확률 문항의 정답은
    기약분수·정확값이어야 한다는 계약을 기계가 강제한다(코퍼스 저작 규약).
    """
    text = claimed.strip().replace(" ", "")
    if not text:
        return None
    try:
        return Fraction(text)
    except (ValueError, ZeroDivisionError):
        return None


def _load(conditions: str | Sequence[str]) -> tuple[FiniteModel, EnumerationResult] | str:
    """모델 파싱 + 전수 열거. 실패 시 *사유 문자열*을 돌려 호출자가 unverifiable로 바꾼다."""
    try:
        model = parse_finite_model(conditions)
        return model, enumerate_model(model)
    except FiniteProbabilityError as exc:
        # 침묵 실패 금지 — 예외 타입명과 사유를 사유 문자열에 함께 싣는다.
        return f"{type(exc).__name__}: {exc}"


def verify_finite_probability(
    conditions: str | Sequence[str],
    claimed: str,
) -> AnswerVerdict:
    """유한 표본공간 확률을 **전수 열거**로 검산(answer_kind='finite_probability').

    - pass: 열거한 정확 확률 == 주장값(유리수 동치). `samples_checked`는 열거한 결과 수
      (= 표본공간 크기)라 "전수"임이 수치로 드러난다.
    - fail: 확률 불일치(오답 확정).
    - unverifiable: DSL 파싱 불가·열거 한도 초과·주장값 파싱 불가·조건 사건 확률 0(보수적 회피).
    """
    loaded = _load(conditions)
    if isinstance(loaded, str):
        return AnswerVerdict(state="unverifiable", reason=f"유한확률 — {loaded}", samples_checked=0)
    model, result = loaded
    if result.probability is None:
        return AnswerVerdict(
            state="unverifiable",
            reason="유한확률 — 조건 사건을 만족하는 경우가 0가지라 조건부확률 미정의·안전 회피",
            samples_checked=result.total,
        )
    value = _parse_claimed_fraction(claimed)
    if value is None:
        return AnswerVerdict(
            state="unverifiable",
            reason=f"유한확률 — 주장값 {claimed!r}을 정확 유리수로 읽을 수 없음·안전 회피",
            samples_checked=result.total,
        )
    if value == result.probability:
        return AnswerVerdict(state="pass", reason=None, samples_checked=result.total)
    exact = result.probability
    return AnswerVerdict(
        state="fail",
        reason=(
            f"유한확률 — 전수 열거 결과 {result.favorable}/{result.conditioned}"
            f"={exact.numerator}/{exact.denominator}이나 주장 {claimed!r}"
            f"(모델: {model.source})"
        ),
        samples_checked=result.total,
    )


def verify_finite_count(
    conditions: str | Sequence[str],
    claimed: str,
) -> AnswerVerdict:
    """유한 표본공간의 *경우의 수*를 전수 열거로 검산(answer_kind='finite_count').

    확률형과 같은 모델·같은 열거를 쓰되 답이 유리한 경우의 수(정수)다. 조합 계산 공식을
    쓰지 않고 **직접 세므로** 공식 오적용(중복조합 오용 등)이 검산 쪽에서 재현되지 않는다.
    """
    loaded = _load(conditions)
    if isinstance(loaded, str):
        return AnswerVerdict(state="unverifiable", reason=f"경우의수 — {loaded}", samples_checked=0)
    model, result = loaded
    text = claimed.strip()
    try:
        value = int(text)
    except ValueError:
        return AnswerVerdict(
            state="unverifiable",
            reason=f"경우의수 — 주장값 {claimed!r}이 정수가 아님·안전 회피",
            samples_checked=result.total,
        )
    if value == result.favorable:
        return AnswerVerdict(state="pass", reason=None, samples_checked=result.total)
    return AnswerVerdict(
        state="fail",
        reason=(
            f"경우의수 — 전수 열거 결과 {result.favorable}가지이나 주장 {value}가지"
            f"(모델: {model.source})"
        ),
        samples_checked=result.total,
    )
