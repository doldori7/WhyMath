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
    """사전생성 응답 검증 경계 — 통과 시 None, 실패 시 짧은 사유 문자열."""

    def validate(self, item: PregenItem, response: str) -> str | None:
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

    def validate(self, item: PregenItem, response: str) -> str | None:
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
_NUM_TOKEN = r"[0-9(][0-9 \t+\-*/^().]*[0-9)]|[0-9]"
_EQUALITY_RE = re.compile(rf"({_NUM_TOKEN})[ \t]*=[ \t]*({_NUM_TOKEN})")

# 매치 양옆(스페이스·탭 건너 첫 글자)에 이게 인접하면 *더 큰 식의 일부*라 건너뛴다 —
# 예: "x + 1 = 2"에서 "1 = 2"만 떼어 거짓 판정하는 false positive를 막는다.
# 개행(\n)은 *강한 구분자*로 보아 독립으로 인정한다(연속된 등식 줄을 각각 검사).
# 소수점(.)은 제외 — 소수는 정규식 토큰이 통째로 잡으므로 인접 검사가 불필요하고,
# 문장 종지부 "= 4."를 잘못 건너뛰지 않게 한다.
_ADJACENT_MATH = frozenset("+-*/^=()")


def _is_standalone_equality(text: str, start: int, end: int) -> bool:
    """매치 양옆(스페이스·탭 제외 첫 글자)이 연산자·피연산자·변수가 아니면 독립 수치 등식.

    스페이스·탭만 건너뛰고 개행은 구분자로 취급한다 — 연산자 인접("x + 1")은 잡되,
    줄이 다른 인접 등식의 숫자는 건너뛰지 않는다.
    """
    i = start - 1
    while i >= 0 and text[i] in " \t":
        i -= 1
    if i >= 0 and text[i] not in "\r\n" and (text[i] in _ADJACENT_MATH or text[i].isalnum()):
        return False
    j = end
    while j < len(text) and text[j] in " \t":
        j += 1
    if j < len(text) and text[j] not in "\r\n" and (text[j] in _ADJACENT_MATH or text[j].isalnum()):
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
    """

    def __init__(self, *, max_checks: int = 100) -> None:
        if max_checks < 1:
            raise ValueError("max_checks는 1 이상이어야 합니다")
        self._max_checks = max_checks

    def validate(self, item: PregenItem, response: str) -> str | None:
        normalized = response.translate(_MATH_OP_NORMALIZE)
        checked = 0
        for match in _EQUALITY_RE.finditer(normalized):
            if checked >= self._max_checks:
                break
            if not _is_standalone_equality(normalized, match.start(), match.end()):
                continue  # 더 큰 식의 일부 → 건너뜀(false positive 방지)
            reason = _equality_is_false(match.group(1).strip(), match.group(2).strip())
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

    def validate(self, item: PregenItem, response: str) -> str | None:
        for validator in self._validators:
            reason = validator.validate(item, response)
            if reason is not None:
                return reason
        return None
