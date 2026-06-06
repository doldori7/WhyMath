"""사전생성 시드 검증 게이트 — Protocol + 최소 기본 구현.

설계 정본: MEMORY.md 2026-05-20 "고난도 검증·시드 품질 = Max-Claude". 슬라이스 1은
*최소 시드 위생*(비어있음·짧음·명백 오류 마커)만 본다. PRM·SymPy·Lean·LLM-judge는
후속 슬라이스(03 환각 방어 파이프라인). 본 게이트는 *시드 품질 위생*이지 학생 노출
경계가 아니다 — 학생 직접 노출 경계는 L4/L5 환각 방어가 책임진다(CLAUDE.md 금기).

검증 통과만 캐시에 적재된다 — 통과 못 한 시드는 *영원히 캐시에 안 들어가서* 런타임
이 그 요청에서 다시 provider를 호출하게 된다(즉, 실패는 안전한 폴백이지 노출 위험이
아니다).
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Protocol, runtime_checkable

import sympy

from whymath_backend.l3.pregenerate.models import PregenItem


@runtime_checkable
class SeedValidator(Protocol):
    """사전생성 응답 검증 경계 — 통과 시 None, 실패 시 짧은 사유 문자열.

    `item`은 *선택적 컨텍스트*(`PregenItem | None`)다. 현재 구현은 모두 `response`만
    보지만, 향후 item을 쓰는 검증기(예: 응답이 기대 답과 일치하는지)를 위해 인자를
    남긴다. item이 None이면 *응답 단독 검증* — 빌드타임 시드뿐 아니라 런타임 생성물에도
    같은 검증기를 재사용할 수 있다(`validate_response` 헬퍼 참조).
    """

    def validate(self, item: PregenItem | None, response: str) -> str | None:
        """응답을 검증한다. 통과 = `None`, 실패 = 사유 문자열(리포트·로그용)."""
        ...


class BasicSeedValidator:
    """최소 시드 위생 — 비어있음·최소 길이·명백 오류 마커. PRM 등은 후속.

    `min_length`는 *strip 후* 문자열 길이. `error_markers`는 응답에 포함되면 즉시
    탈락시키는 부분 문자열들(예: 모델이 토해낸 명시적 오류 표시). 케이스 무시.
    """

    def __init__(
        self,
        *,
        min_length: int = 1,
        error_markers: tuple[str, ...] = (),
    ) -> None:
        if min_length < 0:
            raise ValueError("min_length는 0 이상이어야 합니다")
        self._min_length = min_length
        # 정규화는 1회 — 비교는 lowercase로
        self._error_markers = tuple(m.lower() for m in error_markers if m)

    def validate(self, item: PregenItem | None, response: str) -> str | None:
        """비어있음·짧음·오류 마커 검사 — 통과면 None, 실패면 사유."""
        stripped = response.strip()
        if not stripped:
            return "empty response"
        if len(stripped) < self._min_length:
            return f"response too short (<{self._min_length} chars after strip)"
        if self._error_markers:
            lowered = stripped.lower()
            for marker in self._error_markers:
                if marker in lowered:
                    return f"error marker present: {marker!r}"
        return None


# ──────────────────────────────────────────────────────────────────────────
# SymPy 산술 검증 — 03 환각 방어의 *도구 검증*(스키마→SymPy/Lean→PRM→…) 첫 조각.
# 응답에 *명시된 순수 수치 등식*만 검사하고, 거짓임이 *증명*될 때만 탈락시킨다(보수적).
# ──────────────────────────────────────────────────────────────────────────
# 흔한 수학 유니코드 연산자 → ASCII 정규화 (LLM 출력이 ×·÷·−을 자주 씀).
_MATH_OP_NORMALIZE = {
    ord("×"): "*",
    ord("÷"): "/",
    ord("·"): "*",
    ord("−"): "-",  # U+2212 MINUS SIGN (하이픈-마이너스 아님)
}

# 순수 수치 산술식 토큰: 숫자/괄호로 시작·끝, 중간은 숫자·연산자·괄호·스페이스/탭·소수점.
# 변수(x)·함수·산문은 매칭하지 않는다(심볼릭·자연어 false positive 방지).
# 내부 공백은 *스페이스·탭만*(개행 제외) — 등식은 한 줄이며, 줄을 넘어 다음 등식의
# 숫자를 빨아들이지 않게 한다("2=4\n5=11"이 한 토큰으로 병합되는 버그 방지).
# 선두 부호(`[+-]?`)는 *음수 피연산자*("3 - 10 = -7"의 우변 -7)를 잡기 위함 — 이게
# 없으면 음수 결과를 가진 거짓 등식/부등식이 검사에서 누락된다(false negative). 뺄셈
# 연산자와의 혼동("x - 5 = 3"의 "- 5")은 `_is_standalone` 인접 검사가 막는다(좌측이
# alnum·연산자면 *더 큰 식의 일부*로 보고 건너뜀). 부호 뒤 공백 없이 숫자/괄호가
# 와야 토큰이 성립한다(예: "- 5"는 부호로 안 잡힘 — 뺄셈으로 남는다).
_NUM_TOKEN = r"[+-]?(?:[0-9(][0-9 \t+\-*/^().]*[0-9)]|[0-9])"
# 우변을 *룩어헤드*(소비 안 함)로 잡아 연쇄 등식 "a = b = c"의 인접 쌍(a=b, b=c)을
# 모두 검사할 수 있게 한다 — 일반 매칭은 우변을 소비해 다음 쌍을 놓친다(finditer 비중첩).
# group(1)=좌변, group(2)=우변(룩어헤드 내부). match.end(2)로 우변 끝 위치를 얻는다.
_EQUALITY_RE = re.compile(rf"({_NUM_TOKEN})[ \t]*=[ \t]*(?=({_NUM_TOKEN}))")

# 매치 양옆(스페이스·탭 건너 첫 글자)에 이게 인접하면 *더 큰 식의 일부*라 건너뛴다 —
# 예: "x + 1 = 2"에서 "1 = 2"만 떼어 거짓 판정하는 false positive를 막는다.
# 개행(\n)은 *강한 구분자*로 보아 독립으로 인정한다(연속된 등식 줄을 각각 검사).
# 소수점(.)은 제외 — 소수는 정규식 토큰이 통째로 잡으므로 인접 검사가 불필요하고,
# 문장 종지부 "= 4."를 잘못 건너뛰지 않게 한다.
_ADJACENT_MATH = frozenset("+-*/^=()")

# 연쇄 관계 인접 검사용 집합 — *순수 산술 연산자만*(관계 연산자 =·<·>는 제외).
# 인접한 관계 연산자는 *더 큰 식*이 아니라 *연쇄*("a = b = c"·"2 < 5 < 3")이므로 건너뛰지
# 않고 각 인접 쌍을 검사한다. 산술 연산자(+−*/^())는 여전히 차단 — "x + 1 = 2"의
# "1 = 2"는 좌측 `+` 인접이라 그대로 skip(더 큰 산술식의 일부). 등식·부등식 연쇄 공용.
_CHAIN_ADJACENT = frozenset("+-*/^()")


def _is_hangul(ch: str) -> bool:
    """한글 음절·자모인가 — 수식 변수가 아닌 *산문 문자*라 단어 경계로 취급(slice 54).

    한국어 풀이는 "계산하면 2 + 3 = 6 입니다"처럼 수식이 한글에 인접한다. 한글은 결코
    수식 변수(x·a)가 아니므로, 공백을 건너뛴 뒤 한글을 만나면 *더 큰 식의 일부*가 아니라
    독립 수치 식의 경계로 본다(라틴 문자 변수 "x2"는 여전히 경계로 안 봄 — false-positive
    0 유지). 음절(가–힣)·조합 자모·호환 자모를 포함한다.
    """
    return (
        "가" <= ch <= "힣"  # 한글 음절 (가–힣)
        or "ᄀ" <= ch <= "ᇿ"  # 한글 자모 (조합용)
        or "㄰" <= ch <= "㆏"  # 호환 자모 (ㄱ, ㅏ 등)
    )


def _breaks_standalone(ch: str, adjacent: frozenset[str]) -> bool:
    """인접 문자가 매치를 *더 큰 식의 일부*로 만드는가.

    개행·한글은 *산문 경계*라 식을 끊지 않는다(False). 그 외에는 연산자(`adjacent`)이거나
    영숫자(라틴 변수·이어지는 숫자)면 더 큰 식의 일부로 본다. 한글을 경계로 보는 것이
    slice 54의 핵심 — 한국어 산문에 인접한 수치 관계도 검출 대상에 들어온다.
    """
    if ch in "\r\n" or _is_hangul(ch):
        return False
    return ch in adjacent or ch.isalnum()


def _is_standalone(
    text: str, start: int, end: int, adjacent: frozenset[str] = _ADJACENT_MATH
) -> bool:
    """매치 양옆(스페이스·탭 제외 첫 글자)이 연산자·피연산자·변수가 아니면 독립 수치 식.

    스페이스·탭만 건너뛰고 개행·한글은 *산문 경계*로 취급한다 — 연산자 인접("x + 1")은
    잡되, 줄이 다른/한글 산문에 인접한 식은 독립으로 인정한다(slice 54: 한국어 풀이 지원).
    `adjacent`는 "더 큰 식의 일부"로 볼 인접 문자 집합(등식=`_ADJACENT_MATH`·연쇄는 `<>=`
    제외 — 연쇄 관계 조각 허용). 한글 경계 판정은 `_breaks_standalone`에 위임.
    """
    i = start - 1
    while i >= 0 and text[i] in " \t":
        i -= 1
    if i >= 0 and _breaks_standalone(text[i], adjacent):
        return False
    j = end
    while j < len(text) and text[j] in " \t":
        j += 1
    if j < len(text) and _breaks_standalone(text[j], adjacent):
        return False
    return True


def _equality_is_false(lhs_s: str, rhs_s: str) -> str | None:
    """수치 등식 `lhs=rhs`가 *거짓으로 증명*되면 사유, 아니면(참/미정/파싱불가) None.

    보수적 원칙: 파싱 실패·심볼릭·판정 불가는 *통과*(None)시키고, SymPy가 차이를
    *0이 아니라고 확정*할 때만 실패시킨다 — 자연어·심볼릭 표현을 잘못 탈락시키지 않게.
    """
    try:
        lhs = sympy.sympify(lhs_s, convert_xor=True)
        rhs = sympy.sympify(rhs_s, convert_xor=True)
        # 자유 변수(심볼릭)·비수치는 판정 불가 → 건너뜀(통과).
        if lhs.free_symbols or rhs.free_symbols:
            return None
        is_zero = sympy.simplify(lhs - rhs).is_zero
    except Exception:  # noqa: BLE001 — 파싱·계산 실패는 보수적으로 건너뜀(통과)
        return None
    if is_zero is False:  # 차이가 0이 *아님*이 확정 → 등식 거짓
        return f"arithmetic error: '{lhs_s} = {rhs_s}' (sympy: {lhs} != {rhs})"
    return None  # is_zero True(참) 또는 None(미정) → 통과


class SymPyArithmeticValidator:
    """응답에 명시된 순수 수치 등식을 SymPy로 검증 — 거짓이면 탈락 (SeedValidator 충족).

    수학 콘텐츠의 *산술 환각*(예: "3 × 4 = 11")을 빌드타임에 거른다. 보수적이라
    심볼릭 등식(`x+1=2`)·파싱 불가·판정 불가는 통과시키고, *거짓 증명* 시에만 실패.
    검사 수는 `max_checks`로 제한(악의적·초장문 응답의 ReDoS/과부하 방지).
    연쇄 등식("2+3 = 5 = 6")은 룩어헤드로 각 인접 쌍(2+3=5·5=6)을 모두 검사한다.
    """

    def __init__(self, *, max_checks: int = 100) -> None:
        if max_checks < 1:
            raise ValueError("max_checks는 1 이상이어야 합니다")
        self._max_checks = max_checks

    def validate(self, item: PregenItem | None, response: str) -> str | None:
        normalized = response.translate(_MATH_OP_NORMALIZE)
        checked = 0
        for match in _EQUALITY_RE.finditer(normalized):
            if checked >= self._max_checks:
                break
            # 우변은 룩어헤드(group 2)라 미소비 — 독립 검사 span은 좌변 시작~우변 끝.
            # 인접 `=`는 연쇄 등식이므로 허용(`_CHAIN_ADJACENT`), 산술 연산자는 차단.
            if not _is_standalone(normalized, match.start(1), match.end(2), _CHAIN_ADJACENT):
                continue  # 더 큰 식의 일부 → 건너뜀(false positive 방지)
            reason = _equality_is_false(match.group(1).strip(), match.group(2).strip())
            if reason is not None:
                return reason
            checked += 1
        return None


# ──────────────────────────────────────────────────────────────────────────
# SymPy 부등식 검증 — 산술 등식 검증의 *부등식 판*(거짓 부등식 "5 < 3" 환각 차단).
# 등식과 동일 보수 원칙: 심볼릭·파싱 불가·판정 불가는 통과, *거짓 증명* 시에만 탈락.
# ──────────────────────────────────────────────────────────────────────────
# 유니코드 부등호(≤·≥)를 ASCII로 정규화(LLM 출력이 자주 씀) + 기본 연산자 정규화.
_INEQ_NORMALIZE = {**_MATH_OP_NORMALIZE, ord("≤"): "<=", ord("≥"): ">="}
# 부등식 정규식 — 수치 토큰 사이의 <·>·<=·>=(긴 연산자 우선 매칭). 우변은 *룩어헤드*
# (등식 slice 45와 동형)라 연쇄 부등식 "2 < 5 < 3"의 인접 쌍(2<5, 5<3)을 모두 검사한다.
# group(1)=좌변·group(2)=연산자·group(3)=우변(룩어헤드 내)·`match.end(3)`로 우변 끝.
_INEQUALITY_RE = re.compile(rf"({_NUM_TOKEN})[ \t]*(<=|>=|<|>)[ \t]*(?=({_NUM_TOKEN}))")
# 부등호 → SymPy 관계 생성자(수치 인자면 S.true/S.false로 평가).
_INEQ_FUNC = {"<": sympy.Lt, "<=": sympy.Le, ">": sympy.Gt, ">=": sympy.Ge}


def _inequality_is_false(lhs_s: str, rhs_s: str, op: str) -> str | None:
    """수치 부등식 `lhs op rhs`가 *거짓으로 증명*되면 사유, 아니면 None(참/미정/파싱불가).

    `_equality_is_false`와 동형 보수 원칙: 자유 변수(심볼릭)·파싱 실패·판정 불가는 통과,
    SymPy가 관계를 `S.false`로 *확정*할 때만 실패.
    """
    try:
        lhs = sympy.sympify(lhs_s, convert_xor=True)
        rhs = sympy.sympify(rhs_s, convert_xor=True)
        if lhs.free_symbols or rhs.free_symbols:
            return None  # 심볼릭 → 판정 불가(통과)
        rel = _INEQ_FUNC[op](lhs, rhs)
    except Exception:  # noqa: BLE001 — 파싱·계산 실패는 보수적으로 건너뜀(통과)
        return None
    if rel is sympy.false:  # 거짓 확정
        return f"inequality error: '{lhs_s} {op} {rhs_s}' (sympy: false)"
    return None


class SymPyInequalityValidator:
    """응답에 명시된 순수 수치 부등식을 SymPy로 검증 — 거짓이면 탈락 (SeedValidator 충족).

    `SymPyArithmeticValidator`의 부등식 판: "5 < 3"·"7 ≥ 9" 같은 *부등식 환각*을 거른다.
    심볼릭(`x < 2`)·파싱 불가·판정 불가는 통과(보수적)·`max_checks`로 검사 수 상한.
    연쇄 부등식("2 < 5 < 3")은 룩어헤드로 각 인접 쌍(2<5·5<3)을 모두 검사한다.
    """

    def __init__(self, *, max_checks: int = 100) -> None:
        if max_checks < 1:
            raise ValueError("max_checks는 1 이상이어야 합니다")
        self._max_checks = max_checks

    def validate(self, item: PregenItem | None, response: str) -> str | None:
        normalized = response.translate(_INEQ_NORMALIZE)
        checked = 0
        for match in _INEQUALITY_RE.finditer(normalized):
            if checked >= self._max_checks:
                break
            # 우변은 룩어헤드(group 3)라 미소비 — 독립 검사 span은 좌변 시작~우변 끝.
            # 인접 관계 연산자(<>=)는 연쇄이므로 허용(`_CHAIN_ADJACENT`), 산술 연산자는 차단.
            if not _is_standalone(normalized, match.start(1), match.end(3), _CHAIN_ADJACENT):
                continue
            reason = _inequality_is_false(
                match.group(1).strip(), match.group(3).strip(), match.group(2)
            )
            if reason is not None:
                return reason
            checked += 1
        return None


# ──────────────────────────────────────────────────────────────────────────
# SymPy 부등(≠) 검증 — 관계 연산자 패밀리 완성(=·<·>·≤·≥ 다음 ≠). 등식 검증의 *역*:
# "a ≠ b"는 a와 b가 *같음*이 증명될 때 거짓("12/4 ≠ 3"·"0.5 ≠ 0.50" 류 환각 차단).
# ──────────────────────────────────────────────────────────────────────────
# 유니코드 ≠ → ASCII "!=" 정규화 + 기본 연산자 정규화(피연산자의 ×·÷ 등).
_NOTEQ_NORMALIZE = {**_MATH_OP_NORMALIZE, ord("≠"): "!="}
# 부등(≠) 정규식 — 수치 토큰 사이의 "!="(정규화 후 단일 표기).
_NOTEQUAL_RE = re.compile(rf"({_NUM_TOKEN})[ \t]*(!=)[ \t]*({_NUM_TOKEN})")
# 인접 판정에 "!"도 포함 — 연쇄 "5 != 3 != 5" 조각·팩토리얼("5!") 인접 오판정 차단.
_NOTEQ_ADJACENT = _ADJACENT_MATH | frozenset("!")


def _not_equal_is_false(lhs_s: str, rhs_s: str) -> str | None:
    """수치 부등 `lhs != rhs`가 *거짓으로 증명*되면 사유, 아니면 None(참/미정/파싱불가).

    `_equality_is_false`의 *역* — 등식은 차이≠0일 때 거짓이지만, 부등(≠)은 두 값이
    *같음*(차이=0)이 확정될 때 거짓이다. 보수 원칙 동일: 심볼릭·파싱 실패·판정 불가는
    통과, SymPy가 차이를 *0이라고 확정*할 때만 실패.
    """
    try:
        lhs = sympy.sympify(lhs_s, convert_xor=True)
        rhs = sympy.sympify(rhs_s, convert_xor=True)
        if lhs.free_symbols or rhs.free_symbols:
            return None  # 심볼릭 → 판정 불가(통과)
        is_zero = sympy.simplify(lhs - rhs).is_zero
    except Exception:  # noqa: BLE001 — 파싱·계산 실패는 보수적으로 건너뜀(통과)
        return None
    if is_zero is True:  # 두 값이 같음이 확정 → "a != b" 거짓
        return f"not-equal error: '{lhs_s} != {rhs_s}' (sympy: {lhs} == {rhs})"
    return None  # is_zero False(다름·참) 또는 None(미정) → 통과


class SymPyNotEqualValidator:
    """응답에 명시된 순수 수치 부등(≠)을 SymPy로 검증 — 거짓이면 탈락 (SeedValidator 충족).

    관계 연산자 패밀리(`=`·`<`·`>`·`≤`·`≥`)를 `≠`로 완성: "12/4 ≠ 3"·"8 ≠ 8" 같은
    *거짓 부등 환각*을 거른다. 심볼릭(`x ≠ 2`)·파싱 불가·판정 불가는 통과(보수적)·
    `max_checks`로 검사 수 상한. 팩토리얼("5!")·연쇄("a≠b≠c") 인접은 보수적 skip.
    """

    def __init__(self, *, max_checks: int = 100) -> None:
        if max_checks < 1:
            raise ValueError("max_checks는 1 이상이어야 합니다")
        self._max_checks = max_checks

    def validate(self, item: PregenItem | None, response: str) -> str | None:
        normalized = response.translate(_NOTEQ_NORMALIZE)
        checked = 0
        for match in _NOTEQUAL_RE.finditer(normalized):
            if checked >= self._max_checks:
                break
            if not _is_standalone(normalized, match.start(), match.end(), _NOTEQ_ADJACENT):
                continue
            reason = _not_equal_is_false(match.group(1).strip(), match.group(3).strip())
            if reason is not None:
                return reason
            checked += 1
        return None


class ChainValidator:
    """여러 SeedValidator를 순서대로 실행하는 AND 게이트 — 첫 실패 사유 반환.

    예: `ChainValidator([BasicSeedValidator(), SymPyArithmeticValidator()])` —
    위생(비어있음·길이) 통과 후 산술 검증까지 모두 통과해야 캐시에 적재된다.
    빈 체인은 항상 통과(None) — no-op.
    """

    def __init__(self, validators: Sequence[SeedValidator]) -> None:
        self._validators: tuple[SeedValidator, ...] = tuple(validators)

    def validate(self, item: PregenItem | None, response: str) -> str | None:
        for validator in self._validators:
            reason = validator.validate(item, response)
            if reason is not None:
                return reason
        return None


def default_seed_validator(*, min_length: int = 1) -> ChainValidator:
    """기본 사전적재 검증 체인 — 위생 → 산술 → 부등식 → 부등(≠) AND 게이트.

    CLI(`__main__`)와 후속 호출자가 *같은 게이트*를 쓰도록 단일 정본으로 묶는다.
    순서: `BasicSeedValidator`(비어있음·길이 위생) → `SymPyArithmeticValidator`
    (거짓 등식 "3×4=11") → `SymPyInequalityValidator`(거짓 부등식 "5<3") →
    `SymPyNotEqualValidator`(거짓 부등 "12/4≠3"). 넷 다 보수적이라 심볼릭·파싱 불가는
    통과시키고, *거짓 증명*된 수치 관계(=·<·>·≤·≥·≠)만 탈락시킨다.
    """
    return ChainValidator(
        [
            BasicSeedValidator(min_length=min_length),
            SymPyArithmeticValidator(),
            SymPyInequalityValidator(),
            SymPyNotEqualValidator(),
        ]
    )


def arithmetic_validator(*, max_checks: int = 100) -> ChainValidator:
    """수치 관계 오류 검출 전용 체인 — 위생 검사 없이 SymPy 관계 검증기만(=·<·>·≤·≥·≠).

    `default_seed_validator`와 달리 `BasicSeedValidator`(비어있음·길이·오류 마커 위생)를
    *빼고* SymPy 계산 검증기 셋만 묶는다. 용도가 *학생 풀이의 계산 슬립*("2+3=6") 검출이라
    위생 신호("empty response")는 의미가 없기 때문이다 — 빈 풀이·짧은 풀이는 *슬립이 아니다*.
    통과=None·*거짓이 증명된 수치 관계*만 사유 문자열(보수적: 심볼릭·파싱 불가·판정 불가는
    통과). L3→L4 오케스트레이터(`l4.solution_coaching.recommend_coaching_for_solution`)가
    이 신호 유무를 `arithmetic_error` bool로 환산해 L4 검산(verify) 코칭을 처방한다(slice 51).
    """
    return ChainValidator(
        [
            SymPyArithmeticValidator(max_checks=max_checks),
            SymPyInequalityValidator(max_checks=max_checks),
            SymPyNotEqualValidator(max_checks=max_checks),
        ]
    )


def validate_response(validator: SeedValidator, response: str) -> str | None:
    """`PregenItem` 없이 응답 문자열만 검증 — 런타임 재사용 진입점.

    빌드타임 검증기(`item`을 무시)를 *런타임 생성물*에 그대로 적용할 수 있게 한다.
    `validator.validate(None, response)`의 얇은 래퍼 — 호출지가 빌드타임 전용 타입
    `PregenItem`을 알 필요 없이(레이어 결합 회피) 결정론 검증을 돌린다. 통과=None·
    실패=사유. L3 런타임 shadow 검증(`pipeline.generate` 비차단 관측)의 결선 지점.
    """
    return validator.validate(None, response)
