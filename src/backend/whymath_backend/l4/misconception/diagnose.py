"""오개념 진단 — `docs/prompts/misconception_diagnosis.md` "매칭 알고리즘"(L60-70).

v1.1: 규칙 기반 substring 공출현(AND) + **표기 정규화**(NFKC+공백). 학생 풀이에서 각 catalog
항목의 `signals` 부분집합이 얼마나 매칭되는지로 confidence 계산. top-K 후보 반환.

v1.1 정교화(슬 101·`concept_graph_dataset_v1.md` §5.3): 매칭 직전 양변을 `_normalize`로
정규화해 공백·유니코드 표기 변이(`a² + b²`↔`a²+b²`, 위첨자 `²`↔`2`, 전각/반각)에 의한
*거짓음성*을 제거한다. `matched_signals`·confidence는 *원본 신호* 기준이라 UI·디버그 표시 불변.

v1.2 정교화(슬 102): substring AND를 넘어 **정규식 보조 탐지 경로**(`regex_signals`, OR)를
추가한다. 헤드라인 역량은 *거짓 항등식의 수치 대입* 탐지 — 학생이 `(3+4)²=3²+4²`,
`√((-3)²)=-3`, `(2+4)/2=4`처럼 *틀린 항등식에 수를 대입한 흔적*을 잡는다. substring은
기호식(`(a+b)²=a²+b²`)은 잡지만 학생이 *구체 수치로* 계산해버린 흔적은 못 잡던 한계(§5.3·슬
101에서 문서화)를 줄인다. 정규식은 *정규화된 텍스트*에 `re.search`로 검사한다.

confidence 의미 보존(중요): 분모는 substring `signals` 개수로 *유지*하고, 정규식 매치는
분자에 *가산*하되 상한 1.0으로 캡한다 — `min(1.0, (substr매치 + regex매치)/len(signals))`.
따라서 substring만으로의 기존 confidence(1.0/0.5)는 불변이고 정규식은 *추가* 탐지가 된다.
수치 정규식은 기호 substring 케이스와 *겹치지 않게*(disjoint) 작성해 `matched_signals`
집합·기존 confidence를 보존한다(예: distribution 정규식은 `(3+4)²=3²+4²` *숫자*만 매치,
기호 `(a+b)²=a²+b²`엔 매치되지 않음).

후속(범위 밖, doc 명시): ① 풀이 단계별 파싱(PRM 활용) ② 처음 틀린 단계 식별 ③ 임베딩
유사도 매칭(text-embedding-3-large 등) ④ LLM-judged 패턴 추출. ③④는 짧은 공통 토큰
(`"0"`·`"다음"`)의 *거짓양성* 및 *오류 부재* 미탐지 같은 substring 구조적 한계의 정본 해법.
"""

from __future__ import annotations

import re
import unicodedata
from functools import lru_cache

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

    참고: NFKC는 위첨자 `²`→`2`로 펴므로 정규식은 *지수 표기를 평문으로* 작성한다
    (예: `(3+4)²=3²+4²`의 정규형은 `(3+4)2=32+42`). 정규식 패턴은 이 정규형을 겨냥한다.
    """
    return "".join(unicodedata.normalize("NFKC", text).split())


@lru_cache(maxsize=256)
def _compile(pattern: str) -> re.Pattern[str]:
    """정규식 컴파일 캐시 — 카탈로그 패턴은 고정·소수라 무한정 증가하지 않는다."""
    return re.compile(pattern)


def _match_one(misconception: Misconception, text: str) -> MisconceptionMatch | None:
    """단일 misconception 매칭 — substring 부분집합(정규형 비교) + 정규식 보조 경로(OR).

    confidence = min(1.0, (substr매치 + regex매치) / len(signals)). 둘 다 0이면 None.
    분모는 substring `signals` 기준 유지(v1.1 의미 보존) — 정규식은 분자에 *가산*·상한 1.0.
    """
    norm_text = _normalize(text)
    matched = tuple(s for s in misconception.signals if _normalize(s) in norm_text)
    matched_regex = tuple(
        rs for rs in misconception.regex_signals if _compile(rs).search(norm_text) is not None
    )
    if not matched and not matched_regex:
        return None
    # 분모는 substring signals 개수(>=1, 카탈로그 불변식). 정규식 가산분은 1.0으로 캡.
    confidence = min(1.0, (len(matched) + len(matched_regex)) / len(misconception.signals))
    return MisconceptionMatch(
        misconception=misconception,
        confidence=confidence,
        matched_signals=matched,
        matched_regex_signals=matched_regex,
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
