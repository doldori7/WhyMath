"""오개념 개입 결정 트리·프롬프트 어셈블리 — `docs/prompts/misconception_diagnosis.md` 정본.

**개입 결정 트리**(doc L75-79):
    confidence > 0.8 → 패턴 1 (반례 유도)
    0.5 ≤ confidence ≤ 0.8 → 패턴 4 (거꾸로 사고)
    confidence < 0.5 → 진단 보류(None 반환 — 학생 추가 발화 대기)

**프롬프트 어셈블리**(doc "표준 패턴" L8-22): canonical_statement·counterexample 슬롯
치환. 어셈블된 발화는 *자각 유도형*(직접 교정·라벨링 금지 — doc 절대 금지 §).
"""

from __future__ import annotations

import random
from collections.abc import Sequence

from whymath_backend.l4.misconception.catalog import CATALOG_BY_ID
from whymath_backend.l4.misconception.hypothesis import (
    _DEFAULT_EPSILON,
    MisconceptionHypothesis,
    select_focus,
)
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


def select_intervention_from_hypotheses(
    hypotheses: Sequence[MisconceptionHypothesis],
    *,
    epsilon: float = _DEFAULT_EPSILON,
    rng: random.Random | None = None,
) -> InterventionDecision | None:
    """활성 가설 세트 → ε-규칙 focus 선택 → 개입 결정(결선·재구현 0).

    WH-1 2단계 *결선* 좌석. 단일 턴 raw 매치(`select_intervention(match)`)가 아니라, 시간
    감쇠·강화로 누적된 **활성 가설 세트**가 개입을 결정하게 한다(`_apply_hypotheses` docstring이
    예고한 "select_focus 기반 intervention 변경"). 절차(전부 기존 순수 로직 재사용·재구현 0):
      1. `select_focus`(#191 ε-규칙)로 개입 대상 가설을 고른다 — 기본(rng=None)은 *최상위 활용*,
         `rng` 주입 시 ε 확률로 차순위 탐색(1위 고착·확증편향 방지·R4).
      2. focus의 `misconception_id`를 정본 카탈로그(`CATALOG_BY_ID`)로 해소한다 — 프롬프트
         어셈블(canonical_statement·counterexample)에 실 `Misconception`이 필요하다.
      3. focus의 *가설 신뢰도*(누적)로 `select_intervention` 결정 트리를 구동(>0.8 반례·≥0.5
         거꾸로·<0.5 보류). 즉 여러 턴 강화된 가설은 반례 유도로, 감쇠한 가설은 보류로 간다.

    빈 세트·focus 없음(None)·카탈로그 부재(느슨 id — 어셈블 불가)면 None(개입 보류·날조 0·낙인
    금지). **순수**: DB·LLM·전역 상태 무지(가설 세트와 주입 rng만으로 결정). 가설 세트는 confidence
    내림차순 정렬을 가정한다(`select_focus` 전제·`get_active_hypotheses`/`curate` 결과).
    """
    focus = select_focus(hypotheses, epsilon=epsilon, rng=rng)
    if focus is None:
        return None
    misconception = CATALOG_BY_ID.get(focus.misconception_id)
    if misconception is None:
        return None  # 느슨 id(카탈로그 부재) → 프롬프트 어셈블 불가 → 보류(정직).
    match = MisconceptionMatch(misconception=misconception, confidence=focus.confidence)
    return select_intervention(match)
