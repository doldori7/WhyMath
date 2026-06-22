"""대학 소단원 콘텐츠 데이터 모델 (Pydantic) — **자체작성**(AI 추정·검수필요).

대학 소단원(개념)별 교수학 콘텐츠 4종+α를 담는다 — 은유·오개념·정식정의(내부)·허용표현·설명 +
암기카드(앞/뒤/mnemonic). `standards_university`(성취기준)의 *콘텐츠 짝*이며 같은 소단원 코드
(`CALC1-U1-S1`)로 키잉돼 원자노드DB·성취기준과 조인된다.

라이선스: 와이매스 **자체작성**(원자노드DB 종합·AI 추정) → redaction 불요(NCIC 본문 아님). 단
**`formal_definition_internal`(정식정의)은 학생 비노출**(내부 교사/검수용)·전 콘텐츠 검수필요.
콘텐츠 4종 DB 투영(misconception_catalog·problem 등)은 Phase 3 — 이 코퍼스는 *자산 보존·캡처*다
(휘발 xlsx → 커밋 코퍼스).
"""

from __future__ import annotations

import re
from typing import Final

from pydantic import BaseModel, ConfigDict, Field, field_validator

SOURCE_CITATION: Final[str] = (
    "출처: 와이매스 자체작성 — 대학 소단원 교수학 콘텐츠(은유·오개념·정식정의·허용표현·암기카드). "
    "원자노드DB 종합·AI 추정·검수필요. 소단원 코드는 대학과정 코드참조(CALC1-U1-S1 등) 재사용."
)
LICENSE_NOTICE: Final[str] = (
    "본 데이터는 와이매스 자체 저작물입니다(NCIC 공공누리 아님·redaction 불요). 전 콘텐츠는 "
    "AI 추정 초안으로 검수필요. `formal_definition_internal`(정식정의)은 학생 비노출(내부·검수용)."
)

# 소단원 코드: `<과목약자>-U<단원>-S<소단원>` (예: CALC1-U1-S1).
SUBUNIT_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[A-Z]+[0-9]*-U\d+-S\d+$")


class Flashcard(BaseModel):
    """대학 소단원 암기카드(앞/뒤/mnemonic/노출조건/등급/난이도). 노출조건=마스터 후 노출 등."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    front: str = Field(..., description="앞면")
    back: str = Field(..., description="뒷면")
    mnemonic: str | None = Field(default=None, description="암기보조 (선택)")
    exposure_condition: str | None = Field(default=None, description="노출조건(예: 이해 후 노출)")
    grade: str | None = Field(default=None, description="등급(A/B…)")
    difficulty_tier: str | None = Field(default=None, description="난이도층")


class UniversityConceptContent(BaseModel):
    """대학 소단원 한 건의 교수학 콘텐츠 — 자체작성·검수필요. 소단원 코드로 원자DB와 조인.

    `formal_definition_internal`은 **학생 비노출**(내부·검수용). 콘텐츠 4종은 Phase 3에서 정식
    DB(misconception_catalog·problem 등)로 승격되며, 이 모델은 *코퍼스 캡처*다.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    code: str = Field(..., description="대학 소단원 코드(예 'CALC1-U1-S1')")
    name: str = Field(..., description="소단원(개념)명")
    subject: str = Field(..., description="과목명")
    unit: str | None = Field(default=None, description="단원(영역)")
    metaphor: str | None = Field(default=None, description="은유(직관적 비유)")
    misconception: str | None = Field(default=None, description="오개념")
    formal_definition_internal: str | None = Field(
        default=None, description="정식정의 — **학생 비노출**(내부·검수용)"
    )
    accepted_expressions: str | None = Field(default=None, description="허용표현(인정 표현)")
    explanation: str | None = Field(default=None, description="설명(연결 맥락)")
    flashcards: list[Flashcard] = Field(default_factory=list, description="암기카드(0개 이상)")

    @field_validator("code")
    @classmethod
    def _check_code(cls, value: str) -> str:
        if not SUBUNIT_PATTERN.match(value):
            raise ValueError(f"대학 소단원 코드 형식 위반: {value!r} (예: 'CALC1-U1-S1')")
        return value


__all__ = [
    "LICENSE_NOTICE",
    "SOURCE_CITATION",
    "SUBUNIT_PATTERN",
    "Flashcard",
    "UniversityConceptContent",
]
