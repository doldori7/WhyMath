"""L4 소크라테스 6카테고리 선택 — 매 발화의 질문 종류 결정.

스펙 §"소크라테스 질문 카테고리"(L63-70) + §"PRD Socratic 풀이 흐름과의 정렬"(L72-90).
Polya 단계와 *직교*하는 축(스펙 L89).
"""

from __future__ import annotations

from whymath_backend.l4.socratic.categories import (
    EXAMPLE_QUESTION,
    KOREAN_LABEL,
    SocraticCategory,
)
from whymath_backend.l4.socratic.select import select_category

__all__ = [
    "EXAMPLE_QUESTION",
    "KOREAN_LABEL",
    "SocraticCategory",
    "select_category",
]
