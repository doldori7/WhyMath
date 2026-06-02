"""Polya 단계 × 전이 → 소크라테스 카테고리 선택 — 결정론적 규칙(LLM 0회).

스펙 §"PRD Socratic 풀이 흐름과의 정렬"(L72-90)이 두 축의 직교성을 정의한다:
*Polya 단계*는 콘텐츠 전개 마디, *소크라테스 6카테고리*는 매 발화의 질문 종류.
이 모듈은 단계·전이·학생 발화 신호로 **다음 발화의 질문 종류**를 고른다.

규칙 핵심(보수적):
- next 전이 → 새 단계 *진입 발화*의 카테고리(단계별 기본)
- stay 전이 → 학생 발화 신호가 있으면 신호 우선, 없으면 단계 기본
- 단계 기본 매핑(스펙 L82-87 표 + L4 6카테고리 본문 정합):
    UNDERSTAND → CLARIFICATION ("어디까지 이해됐어?" — 명료화)
    PLAN       → PERSPECTIVE   (스펙 L84 "관점 선택" 마디 = PERSPECTIVE)
    EXECUTE    → IMPLICATION   ("그러면 다음은?" — 단계별 진전)
    REVIEW     → META          ("어떻게 도달했어?" — 메타인지)

학생 발화 신호 오버라이드(stay 한정·키워드 화이트리스트, 단계와 무관):
- "왜·이유·근거·증명" 등 → EVIDENCE (근거 질문 신호 우선)
- "가정·라고 치"·"라고 하" 등 → ASSUMPTION
"""

from __future__ import annotations

from whymath_backend.l4.models import PolyaStage, StageTransition
from whymath_backend.l4.socratic.categories import SocraticCategory

# 단계 기본 카테고리 — 스펙 L82-87 PRD 정렬표 + L4 본문(L65-70) 정합.
_STAGE_DEFAULT: dict[PolyaStage, SocraticCategory] = {
    PolyaStage.UNDERSTAND: SocraticCategory.CLARIFICATION,
    PolyaStage.PLAN: SocraticCategory.PERSPECTIVE,
    PolyaStage.EXECUTE: SocraticCategory.IMPLICATION,
    PolyaStage.REVIEW: SocraticCategory.META,
}


# 발화 신호 오버라이드(stay 한정). 단계 기본보다 *학생 발화 내용*이 더 강한 신호.
# 매핑 순서 의미 있음 — 가장 구체적인 신호(가정 탐색)를 먼저 검사.
_INPUT_SIGNAL_TOKENS: tuple[tuple[frozenset[str], SocraticCategory], ...] = (
    (
        frozenset({"가정", "라고 치", "라고 하면", "라고 두"}),
        SocraticCategory.ASSUMPTION,
    ),
    (
        frozenset({"왜", "이유", "근거", "증명", "보장"}),
        SocraticCategory.EVIDENCE,
    ),
)


def _next_stage(stage: PolyaStage) -> PolyaStage:
    """Polya 다음 단계(REVIEW는 종착 셀프루프) — 호출자 편의용 로컬 복제."""
    order = (
        PolyaStage.UNDERSTAND,
        PolyaStage.PLAN,
        PolyaStage.EXECUTE,
        PolyaStage.REVIEW,
    )
    idx = order.index(stage)
    if idx == len(order) - 1:
        return stage
    return order[idx + 1]


def select_category(
    stage: PolyaStage,
    transition: StageTransition,
    student_input: str,
) -> SocraticCategory:
    """현재 단계·전이·학생 발화에서 다음 발화의 소크라테스 카테고리를 고른다.

    - `next` → 다음 단계의 기본 카테고리(단계 진입 발화).
    - `stay`/`previous` → 학생 발화 신호(가정·근거) 우선, 없으면 현 단계 기본.
    """
    target_stage = _next_stage(stage) if transition == "next" else stage

    if transition != "next":
        # 학생 발화 신호 오버라이드 — 단계 기본보다 우선.
        for tokens, category in _INPUT_SIGNAL_TOKENS:
            if any(t in student_input for t in tokens):
                return category

    return _STAGE_DEFAULT[target_stage]
