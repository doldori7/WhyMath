"""수능 시그니처 패턴 결정론 태거 — 문항 구조에서 `signature_patterns`를 규칙으로 유도(S2-06).

기존 코퍼스 1,073문은 어떤 시그니처에도 해당하지 않았다(조건 나열 0·점화식 마커 0·ㄱㄴㄷ 선지 0)
— 이 태거는 **문항이 실제로 가진 구조에서만** 시그니처를 유도한다(비날조 원칙). 규칙 미해당이면
빈 배열이며, 시그니처를 채우려고 문항을 각색하지 않는다. 시그니처의 *단일 권위*는 이 태거다 —
생성기(L3)는 `signature_patterns`를 채우지 않고 빈 배열로 두며, 조성 루트(harness)가 sink 기록
직전에 `apply_signatures`를 태운다.

규칙 3종(결정론·`SignaturePattern` 10종 중 현 코퍼스 구조가 지지하는 것만):
  - T1 CONDITION_LIST — `has_condition_list=True`이고 발문에 `(가)`·`(나)`가 동시 존재.
  - T2 INDUCTIVE_SEQUENCE — 발문이 귀납 점화식 고정 표기(`aₙ₊₁ = aₙ + d`·`aₙ₊₁ = r·aₙ`)와 매치.
    표기는 `l3/equivalent/inductive_sequence_skeleton_generator.py`가 방출하는 형식과 정확히
    일치한다(생성기·태거 상호 계약 — 생성기 테스트가 교차 봉인).
  - T3 COMPOUND_CHOICES — 객관식이고 선지 전원이 ㄱㄴㄷ 조합(`^[ㄱㄴㄷ,\\s·]+$`). 현 코퍼스 해당
    0건 — 후속 합답형 밴드용 선치(규칙만 준비·날조 0).

반환은 enum 값 사전순 정렬(결정론) — 재실행·재태깅이 항상 같은 배열을 낸다(멱등).

7계층: L1 지역 순수 규칙(l1→schema 하향 import만·LLM 0·DB 0). 소비는 조성 루트(harness CLI)와
후속 L6 수능 모드가 하되 여기선 알지 못한다(역방향 의존 금지).
"""

from __future__ import annotations

import re
from enum import Enum

from whymath_backend.schema.enums import QuestionFormat, SignaturePattern
from whymath_backend.schema.problem import Problem

__all__ = ["apply_signatures", "derive_signatures"]

# T2 귀납 점화식 고정 표기 — 등차 점화(aₙ₊₁ = aₙ + d)·등비 점화(aₙ₊₁ = r·aₙ)만. 유니코드 아래첨자
# 표기는 생성기 방출 형식과 정확히 일치해야 한다(ASCII `a_1` 표기는 위생 게이트의 수치 등식 검사와
# 충돌해 생성기가 쓰지 않는다 — 아래첨자가 코퍼스 정본 표기).
_INDUCTIVE_RECURRENCE_RE = re.compile(r"aₙ₊₁ = (?:aₙ \+ \d+|\d+·aₙ)")

# T3 합답형 선지 — ㄱ/ㄴ/ㄷ와 구분 기호(쉼표·공백·가운뎃점)만으로 이뤄진 선지.
_COMPOUND_CHOICE_RE = re.compile(r"^[ㄱㄴㄷ,\s·]+$")


def _as_value(value: Enum | str | None) -> str | None:
    """enum/문자열/None을 *문자열 값*으로 정규화(use_enum_values=True 대응·acceptance 패턴)."""
    if value is None:
        return None
    if isinstance(value, Enum):
        return str(value.value)
    return value


def derive_signatures(problem: Problem) -> list[SignaturePattern]:
    """문항 구조에서 시그니처 패턴을 결정론 유도 — 미해당이면 빈 리스트(비날조).

    순수 함수다: `problem`의 어떤 필드도 변경하지 않고, `persona_fit`·`exam_type` 등 다른 축을
    조작하지 않는다. 반환은 enum 값 사전순 정렬(결정론·멱등).
    """
    text = problem.question_text or ""
    found: set[SignaturePattern] = set()

    # T1 CONDITION_LIST — 메타 플래그와 발문 표기가 *동시에* 지지할 때만(플래그 단독 오태깅 방지).
    if problem.has_condition_list and "(가)" in text and "(나)" in text:
        found.add(SignaturePattern.CONDITION_LIST)

    # T2 INDUCTIVE_SEQUENCE — 발문이 귀납 점화식 고정 표기와 매치.
    if _INDUCTIVE_RECURRENCE_RE.search(text):
        found.add(SignaturePattern.INDUCTIVE_SEQUENCE)

    # T3 COMPOUND_CHOICES — 객관식이고 선지 *전원*이 ㄱㄴㄷ 조합(부분 해당은 합답형 아님).
    choices = problem.choices or []
    if (
        _as_value(problem.question_format) == QuestionFormat.객관식.value
        and choices
        and all(_COMPOUND_CHOICE_RE.fullmatch(choice) for choice in choices)
    ):
        found.add(SignaturePattern.COMPOUND_CHOICES)

    return sorted(found, key=lambda pattern: pattern.value)


def apply_signatures(problem: Problem) -> Problem:
    """유도 시그니처를 반영한 Problem을 반환 — 이미 동일하면 **원본 객체 그대로**(멱등·무변경).

    시그니처 필드 외에는 아무것도 바꾸지 않는다(`model_copy(update=...)` — 재검증 없이 한 필드만
    교체). 기존 코퍼스처럼 규칙 미해당·빈 배열 유지인 레코드는 원본 인스턴스를 그대로 돌려줘
    직렬화 바이트가 불변임을 구조적으로 보장한다.
    """
    derived = derive_signatures(problem)
    current = [_as_value(value) for value in problem.signature_patterns]
    if current == [pattern.value for pattern in derived]:
        return problem
    return problem.model_copy(update={"signature_patterns": derived})
