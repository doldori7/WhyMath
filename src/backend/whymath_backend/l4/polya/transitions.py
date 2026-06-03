"""Polya 단계 전이 휴리스틱 — `docs/prompts/polya_4step.md` L73-94 의사코드 구현.

**보수적 설계**: 모호 시 항상 `stay`(생산적 막힘 우선 — CLAUDE.md "정답을 빠르게 KPI 금지").
*자동* `previous`는 절대 없음(스펙 L101: 학생 *명시* 후퇴 신호로만, `request_backtrack`로 분리).

v1은 한국어 키워드 화이트리스트 + 길이 임계값. LLM-judged 전이는 v2(별도 슬라이스, 비용↑).
False-negative(stay 과다)는 교수학적으로 *안전*, false-positive(잘못 next)는 *유해* — 이 비대칭이
설계의 핵심.
"""

from __future__ import annotations

from whymath_backend.l4.models import PolyaStage, PolyaState, StageTransition

# UNDERSTAND→PLAN: 학생이 자기 언어로 *재진술*했는가의 신호.
# 길이 ≥20자(짧은 단답·"네"·"음"은 재진술 아님)·문장 구조 표시(마침표·물음표·쉼표 중 1+).
_RESTATE_MIN_LEN = 20

# PLAN→EXECUTE: 전략·접근 키워드 화이트리스트(한국어). 학생 발화에 *이 중 하나라도* 출현하면
# "전략을 떠올렸다"의 신호로 본다.
_STRATEGY_TOKENS: frozenset[str] = frozenset(
    {
        "공식",
        "정리",
        "접근",
        "방법",
        "전략",
        "생각",
        "시도",
        "그려",
        "그림",
        "표",
        "도형",
        "예시",
        "작은",
        "비슷한",
        "유사",
        "대입",
        "치환",
        "인수",
        "전개",
        "양변",
    }
)

# EXECUTE→REVIEW: 답에 도달한 신호. 결과·결론 토큰 + 등호 사용 + 다중 줄(단계 흔적).
_ANSWER_TOKENS: frozenset[str] = frozenset(
    {
        "답",
        "따라서",
        "그러므로",
        "결론",
        "정답",
        "최종",
    }
)


def _any_token(text: str, tokens: frozenset[str]) -> bool:
    return any(t in text for t in tokens)


def should_advance(state: PolyaState, student_input: str) -> StageTransition:
    """현재 단계와 학생 발화에서 다음 전이를 판정한다.

    - UNDERSTAND: 자기 언어 재진술(길이 + 문장 부호) → `next`
    - PLAN: 전략 키워드 1+ → `next`
    - EXECUTE: 결과 토큰 + 등호 + 다중 줄 → `next`
    - REVIEW: 메타 토큰 있어도 *전이 없음* (마지막 단계, 종착)
    - 모호: 항상 `stay`

    `previous`는 이 함수가 반환하지 않는다(스펙 L101 명시 후퇴는 별도 신호).
    """
    text = student_input.strip()

    if state.current_stage is PolyaStage.UNDERSTAND:
        if len(text) >= _RESTATE_MIN_LEN and any(p in text for p in ".?,"):
            return "next"
        return "stay"

    if state.current_stage is PolyaStage.PLAN:
        if _any_token(text, _STRATEGY_TOKENS):
            return "next"
        return "stay"

    if state.current_stage is PolyaStage.EXECUTE:
        has_equals = "=" in text
        has_answer = _any_token(text, _ANSWER_TOKENS)
        is_multiline = text.count("\n") >= 1
        if has_equals and has_answer and is_multiline:
            return "next"
        return "stay"

    # REVIEW는 종착 — 추가 전이 없음(메타 토큰은 단계 *내* 충실 신호).
    return "stay"
