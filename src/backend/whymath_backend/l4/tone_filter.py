"""정서 안전 톤필터 — `docs/architecture/04_pedagogy_engine.md` §"정서 안전" L129-138 정본.

금지 6패턴(틀렸·못 하·잘못된·실수·바보·포기)을 권장 표현으로 치환한다. *AI 출력 전용* —
학생 입력은 절대 손대지 않는다(자기표현 검열 금지). 멱등(두 번 적용해도 결과 동일).

v1 선택: 부분 문자열 매칭. "포기하지 않고" 같은 합법 토큰까지 치환될 수 있으나, AI 응답에선
이 6개 단어 자체를 *사용하지 않는 것*이 교수학 원칙(부정적 강화 금지·CLAUDE.md 금기)이라
보수적 치환이 안전한 디폴트. 토큰 경계·문맥 검사는 v2(별도 슬라이스, 실 LLM 응답 코퍼스 분석 후).
"""

from __future__ import annotations

from whymath_backend.l4.models import ToneReport

# 금지 패턴 → 권장 표현 — 스펙 §"금지 패턴"(L132)·§"권장 표현"(L135-137) 정본.
# *순서 의미 있음*: 더 긴 패턴(잘못된)을 짧은 패턴(못 하)보다 *먼저* 치환해
# 부분 매칭 충돌 방지.
_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    ("잘못된", "다시 봐도 좋을"),
    ("틀렸", "다시 봐도 좋아"),
    ("못 하", "아직 더 해볼 수 있"),
    ("실수", "흥미로운 시도"),
    ("바보", "거의 다 왔어"),
    ("포기", "다른 각도로 봐볼까"),
)


def filter_tone(text: str) -> tuple[str, ToneReport]:
    """금지 패턴을 권장 표현으로 치환하고 위반 기록을 반환한다.

    위반 0건이면 원문 그대로(`rewritten=False`)·`violations=[]`. 멱등 — 결과를 다시
    넣어도 같은 결과(권장 표현엔 금지 패턴이 포함되지 않음).
    """
    violations: list[str] = []
    result = text
    for banned, suggestion in _REPLACEMENTS:
        if banned in result:
            count = result.count(banned)
            violations.extend([banned] * count)
            result = result.replace(banned, suggestion)
    return result, ToneReport(violations=violations, rewritten=bool(violations))
