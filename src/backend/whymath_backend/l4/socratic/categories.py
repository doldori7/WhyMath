"""소크라테스 6카테고리 — `docs/architecture/04_pedagogy_engine.md` L63-70 정본.

`PedagogyDecision.socratic_category`를 채우는 카테고리 enum + 정본 한국어 라벨 + 카테고리별
정본 예시 질문(스펙 L65-70 그대로 인용·드리프트 방지).

**스키마 `SocraticStrategy`와의 구분**(`schema/enums.py:555`): 스키마는 *발문 전략*(조건확인·
반례제시·…) — `dialogue_turn` DB 행에 기록되는 *형식 전략*. 여기 `SocraticCategory`는
*질문 종류*(스펙 L4 6분류) — 매 발화에서 무엇을 묻는가의 직교 축. 둘은 서로 다른 축이며
함께 쓰일 수 있다(스펙 L89: "둘은 직교한다").
"""

from __future__ import annotations

from enum import Enum


class SocraticCategory(str, Enum):
    """L4 소크라테스 6카테고리 — 스펙 L65-70 영어 식별자·한글 라벨 정본."""

    CLARIFICATION = "clarification"
    """명료화 — "어디까지 이해됐어?" (스펙 L65)"""

    ASSUMPTION = "assumption"
    """가정 탐색 — "왜 그렇게 가정했어?" (스펙 L66)"""

    EVIDENCE = "evidence"
    """근거·증거 — "어떻게 알아?" (스펙 L67)"""

    PERSPECTIVE = "perspective"
    """관점 — "다른 방법은?" (스펙 L68)"""

    IMPLICATION = "implication"
    """함의 — "그러면 다음은?" (스펙 L69)"""

    META = "meta"
    """메타인지 — "어떻게 도달했어?" (스펙 L70)"""


# 한국어 라벨 — 스펙 L65-70 정본(괄호 영문 식별자 제거한 표시명).
KOREAN_LABEL: dict[SocraticCategory, str] = {
    SocraticCategory.CLARIFICATION: "명료화",
    SocraticCategory.ASSUMPTION: "가정 탐색",
    SocraticCategory.EVIDENCE: "근거·증거",
    SocraticCategory.PERSPECTIVE: "관점",
    SocraticCategory.IMPLICATION: "함의",
    SocraticCategory.META: "메타인지",
}


# 카테고리별 정본 예시 질문 — 스펙 L65-70 그대로. 학생에게 직접 노출되는 *짧은* 질문 한 줄.
EXAMPLE_QUESTION: dict[SocraticCategory, str] = {
    SocraticCategory.CLARIFICATION: "어디까지 이해됐어?",
    SocraticCategory.ASSUMPTION: "왜 그렇게 가정했어?",
    SocraticCategory.EVIDENCE: "어떻게 알아?",
    SocraticCategory.PERSPECTIVE: "다른 방법은?",
    SocraticCategory.IMPLICATION: "그러면 다음은?",
    SocraticCategory.META: "어떻게 도달했어?",
}
