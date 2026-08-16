"""개념 콘텐츠 4종 응답 스키마 — `concept_content` PG 프로젝션의 HTTP 표면.

`formal_definition_internal`(정식정의)은 **학생 비노출** 컬럼이나, 이 스키마는 L2/L4·교사
도구가 소비하는 *내부 조회 표면*용이다. 학생 렌더 경로는 별도 게이팅을 거쳐 노출 필드를
제한해야 한다(CLAUDE.md).

스키마 필드는 `db/models/concept_content.py`의 ORM 컬럼과 1:1 대응한다.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ConceptContentSchema(BaseModel):
    """개념 콘텐츠 1건 — PG `concept_content` 행 직렬화."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    code: str = Field(..., description="K-12 개념코드/대학 소단원코드(PK).")
    scope: str = Field(..., description="K-12('K-12') 또는 대학('대학').")
    name: str = Field(..., description="개념/소단원 명칭.")
    subject: str = Field(..., description="과목(예: '초등수학', '갈루아 이론').")
    unit: str | None = Field(default=None, description="단원/영역.")
    metaphor: str | None = Field(default=None, description="은유 설명.")
    misconception: str | None = Field(default=None, description="대표 오개념.")
    formal_definition_internal: str | None = Field(
        default=None,
        description="정식정의(내부·검수·교사용 — 학생 직접 노출 금지).",
    )
    accepted_expressions: str | None = Field(default=None, description="허용/기대 표현.")
    explanation: str | None = Field(default=None, description="개념 gloss/설명.")
    standard_codes: list[str] = Field(
        default_factory=list, description="연결 NCIC 성취기준 코드 목록."
    )
    flashcards: list[dict[str, object]] = Field(
        default_factory=list, description="암기카드(JSONB dict) 목록."
    )
    review_status: str = Field(..., description="검수 상태 — 'ai_estimated' 또는 'reviewed'.")
    updated_at: datetime = Field(..., description="마지막 upsert 시각.")


__all__ = ["ConceptContentSchema"]
