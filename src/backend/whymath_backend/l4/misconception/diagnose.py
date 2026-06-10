"""오개념 진단 — `docs/prompts/misconception_diagnosis.md` "매칭 알고리즘"(L60-70).

v1.1: 규칙 기반 substring 공출현(AND) + **표기 정규화**(NFKC+공백). 학생 풀이에서 각 catalog
항목의 `signals` 부분집합이 얼마나 매칭되는지로 confidence 계산. top-K 후보 반환.

v1.1 정교화(슬 101·`concept_graph_dataset_v1.md` §5.3): 매칭 직전 양변을 `_normalize`로
정규화해 공백·유니코드 표기 변이(`a² + b²`↔`a²+b²`, 위첨자 `²`↔`2`, 전각/반각)에 의한
*거짓음성*을 제거한다. `matched_signals`·confidence는 *원본 신호* 기준이라 UI·디버그 표시 불변.

후속(범위 밖, doc 명시): ① 풀이 단계별 파싱(PRM 활용) ② 처음 틀린 단계 식별 ③ 임베딩
유사도 매칭(text-embedding-3-large 등) ④ LLM-judged 패턴 추출. ③④는 짧은 공통 토큰
(`"0"`·`"다음"`)의 *거짓양성* 및 *오류 부재* 미탐지 같은 substring 구조적 한계의 정본 해법.
"""

from __future__ import annotations

import unicodedata

from whymath_backend.l4.misconception.catalog import CATALOG
from whymath_backend.l4.misconception.models import (
    Misconception,
    MisconceptionMatch,
)

_DEFAULT_TOP_K = 3


def _normalize(text: str) -> str:
    """매칭용 표기 정규화 — NFKC 유니코드 정규화 + 모든 공백 제거.

    학생 표기 변이를 흡수한다: `a² + b²`·`a²+b²`·`a 2 + b 2`가 모두 같은 정규형 `a2+b2`로,
    위첨자/아래첨자·전각 숫자도 일반 숫자로(NFKC). 비교에만 쓰며, 반환되는 신호 문자열은
    원본을 유지한다(표시·텔레메트리 일관성).
    """
    return "".join(unicodedata.normalize("NFKC", text).split())


def _match_one(misconception: Misconception, text: str) -> MisconceptionMatch | None:
    """단일 misconception 매칭 — 모든 signals 부분집합 검사(정규형 비교).

    confidence = matched / total_signals(0~1). 매칭 0이면 None.
    """
    norm_text = _normalize(text)
    matched = tuple(s for s in misconception.signals if _normalize(s) in norm_text)
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
