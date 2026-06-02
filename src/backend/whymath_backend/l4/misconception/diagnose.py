"""오개념 진단 — `docs/prompts/misconception_diagnosis.md` "매칭 알고리즘"(L60-70).

v1: 규칙 기반 substring 공출현(AND). 학생 풀이에서 각 catalog 항목의 `signals` 부분집합이
얼마나 매칭되는지로 confidence 계산. top-K 후보 반환.

후속(범위 밖, doc 명시): ① 풀이 단계별 파싱(PRM 활용) ② 처음 틀린 단계 식별 ③ 임베딩
유사도 매칭(text-embedding-3-large 등) ④ LLM-judged 패턴 추출.
"""

from __future__ import annotations

from whymath_backend.l4.misconception.catalog import CATALOG
from whymath_backend.l4.misconception.models import (
    Misconception,
    MisconceptionMatch,
)

_DEFAULT_TOP_K = 3


def _match_one(misconception: Misconception, text: str) -> MisconceptionMatch | None:
    """단일 misconception 매칭 — 모든 signals 부분집합 검사.

    confidence = matched / total_signals(0~1). 매칭 0이면 None.
    """
    matched = tuple(s for s in misconception.signals if s in text)
    if not matched:
        return None
    confidence = len(matched) / len(misconception.signals)
    return MisconceptionMatch(
        misconception=misconception,
        confidence=confidence,
        matched_signals=matched,
    )


def diagnose(student_solution: str, *, top_k: int = _DEFAULT_TOP_K) -> list[MisconceptionMatch]:
    """학생 풀이에서 오개념 후보 top-K를 confidence 내림차순으로 반환한다.

    매칭 0이면 빈 리스트. 동률은 catalog 순서(=doc 명시 순서) 안정 유지.
    """
    matches: list[MisconceptionMatch] = []
    for m in CATALOG:
        result = _match_one(m, student_solution)
        if result is not None:
            matches.append(result)
    matches.sort(key=lambda x: x.confidence, reverse=True)
    return matches[:top_k]
