"""오개념 개입 결정 트리·프롬프트 어셈블리 — `docs/prompts/misconception_diagnosis.md` 정본.

**개입 결정 트리**(doc L75-79):
    confidence > 0.8 → 패턴 1 (반례 유도)
    0.5 ≤ confidence ≤ 0.8 → 패턴 4 (거꾸로 사고)
    confidence < 0.5 → 진단 보류(None 반환 — 학생 추가 발화 대기)

**프롬프트 어셈블리**(doc "표준 패턴" L8-22): canonical_statement·counterexample 슬롯
치환. 어셈블된 발화는 *자각 유도형*(직접 교정·라벨링 금지 — doc 절대 금지 §).
"""

from __future__ import annotations

from whymath_backend.l4.misconception.models import (
    InterventionDecision,
    InterventionPattern,
    MisconceptionMatch,
)

# 결정 트리 임계 — doc L75-79 정본.
_HIGH_CONFIDENCE = 0.8
_LOW_CONFIDENCE = 0.5


def _assemble_counterexample(match: MisconceptionMatch) -> str:
    """패턴 1 — doc L8-10 정본 형식.

    "{학생 가정}이 항상 맞다고 했지. 잠깐, {반례 케이스}일 때는 어떻게 돼?"
    """
    m = match.misconception
    return (
        f"{m.canonical_statement}이 항상 맞다고 했지. "
        f"잠깐, {m.counterexample}일 때는 어떻게 돼?"
    )


def _assemble_reverse(match: MisconceptionMatch) -> str:
    """패턴 4 — doc L20-22 정본 형식.

    "이 결과가 맞다면, *원래 조건*에 어떻게 부합하는지 거꾸로 확인할 수 있을까?"
    학생 가정을 명시해 무엇을 거꾸로 검산할지 안내한다.
    """
    m = match.misconception
    return (
        f"{m.canonical_statement}이라고 했지. 이 결과가 맞다면, "
        "원래 조건에 어떻게 부합하는지 거꾸로 확인할 수 있을까?"
    )


def select_intervention(
    match: MisconceptionMatch,
) -> InterventionDecision | None:
    """결정 트리(doc L75-79) — 신뢰도에 따라 패턴 선택·프롬프트 어셈블.

    낮은 신뢰도(<0.5)는 *진단 보류* — None 반환(학생 추가 발화 대기, 라벨링 회피).
    """
    if match.confidence > _HIGH_CONFIDENCE:
        return InterventionDecision(
            pattern=InterventionPattern.COUNTEREXAMPLE,
            prompt=_assemble_counterexample(match),
            misconception_id=match.misconception.id,
        )
    if match.confidence >= _LOW_CONFIDENCE:
        return InterventionDecision(
            pattern=InterventionPattern.REVERSE_REASONING,
            prompt=_assemble_reverse(match),
            misconception_id=match.misconception.id,
        )
    return None
