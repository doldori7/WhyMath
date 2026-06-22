"""K-12 소단원(개념) 콘텐츠 데이터 모델 (Pydantic) — **자체작성**(AI 추정·검수필요).

K-12(초·중·고) 개념별 교수학 콘텐츠 4종+α를 담는다 — 은유·오개념·정식정의(내부)·허용표현·설명 +
암기카드(앞/뒤/mnemonic). 대학 U4(`concept_content_university`)의 *K-12 짝*이며 같은 개념ID
(`N1`·`A1`·`HK01`·`10기수1-01-01` 등)로 키잉돼 원자노드DB·성취기준과 조인된다.

라이선스: 와이매스 **자체작성**(원자노드DB 종합·AI 추정). 단 **K-12 성취기준 본문(성취기준 문장·
요약)은 NCIC 저작물이라 미수록** — `standard_codes`(연결 성취기준 코드)만 다리로 보존한다(NCIC
본문 다리). **`formal_definition_internal`(정식정의)은 학생 비노출**(내부 교사/검수용)·전 콘텐츠
검수필요. 콘텐츠 4종 DB 투영(misconception_catalog·problem 등)은 Phase 3 — 이 코퍼스는 *자산
보존·캡처*다(휘발 xlsx → 커밋 코퍼스).
"""

from __future__ import annotations

from typing import Final

from pydantic import BaseModel, ConfigDict, Field, field_validator

SOURCE_CITATION: Final[str] = (
    "출처: 와이매스 자체작성 — K-12 개념 교수학 콘텐츠(은유·오개념·정식정의·허용표현·암기카드). "
    "원자노드DB 종합·AI 추정·검수필요. K-12 성취기준 본문은 NCIC 저작물이라 미수록 — "
    "연결 성취기준 코드만 다리로 보존."
)
LICENSE_NOTICE: Final[str] = (
    "본 데이터(은유·오개념·정식정의·허용표현·설명·암기카드)는 와이매스 자체 저작물입니다 — "
    "AI 추정 초안으로 검수필요. **K-12 성취기준 본문(성취기준 문장·요약)은 NCIC 저작물이라 "
    "미수록**·연결 성취기준 코드만 보존. `formal_definition_internal`(정식정의)은 학생 비노출"
    "(내부·검수용)."
)


class Flashcard(BaseModel):
    """K-12 개념 암기카드(앞/뒤/mnemonic/노출조건/등급/난이도). 노출조건=마스터 후 노출 등."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    front: str = Field(..., description="앞면")
    back: str = Field(..., description="뒷면")
    mnemonic: str | None = Field(default=None, description="암기보조 (선택)")
    exposure_condition: str | None = Field(default=None, description="노출조건(예: 이해 후 노출)")
    grade: str | None = Field(default=None, description="등급(A/B…)")
    difficulty_tier: str | None = Field(default=None, description="난이도층")


class ConceptContent(BaseModel):
    """K-12 개념 한 건의 교수학 콘텐츠 — 자체작성·검수필요. 개념ID로 원자DB와 조인.

    `formal_definition_internal`은 **학생 비노출**(내부·검수용). `standard_codes`는 연결 성취기준
    **코드만**(NCIC 본문 다리)이며 성취기준 본문은 미수록. 콘텐츠 4종은 Phase 3에서 정식 DB
    (misconception_catalog·problem 등)로 승격되며, 이 모델은 *코퍼스 캡처*다.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    code: str = Field(..., description="K-12 개념ID(예 'N1'·'A1'·'HK01'·'10기수1-01-01')")
    name: str = Field(..., description="개념명")
    subject: str = Field(..., description="과목명")
    unit: str | None = Field(default=None, description="단원(영역)")
    metaphor: str | None = Field(default=None, description="은유(직관적 비유)")
    misconception: str | None = Field(default=None, description="오개념")
    formal_definition_internal: str | None = Field(
        default=None, description="정식정의 — **학생 비노출**(내부·검수용)"
    )
    accepted_expressions: str | None = Field(default=None, description="허용표현(인정 표현)")
    explanation: str | None = Field(default=None, description="설명(연결 맥락)")
    standard_codes: list[str] = Field(
        default_factory=list,
        description="연결 성취기준 코드만(NCIC 본문 다리·본문 미수록)",
    )
    flashcards: list[Flashcard] = Field(default_factory=list, description="암기카드(0개 이상)")

    @field_validator("code")
    @classmethod
    def _check_code(cls, value: str) -> str:
        # K-12 개념ID는 형식이 다양(N1·A1·HK01·10기수1-01-01 등) → 비어있지 않은 문자열이면 통과.
        if not value.strip():
            raise ValueError("K-12 개념ID 공란 불가(비어있지 않은 문자열 필요)")
        return value


__all__ = [
    "LICENSE_NOTICE",
    "SOURCE_CITATION",
    "ConceptContent",
    "Flashcard",
]
