"""`ReasoningType` 폐쇄 enum 동결 테스트 — MATH DSL 교육 추론 엔진 §2.2 얇은 도입.

`SolutionStep.reasoning_type`의 구현 정본 어휘(`schema/enums.py` `ReasoningType`)가 *폐쇄 7종*임을
동결한다. 무한 추론 온톨로지 금지(§2.2 금기)를 회귀로 강제 — 멤버 추가·제거가 이 테스트를 깨서
"의도적 결정"을 통과시키게 한다(EdgeType 거버넌스 동결 선례·`test_concept.py`).
"""

from __future__ import annotations

from whymath_backend.schema.enums import ReasoningType

# math_dsl_evolution.md §2.2·03_content_generation.md ReasoningStep 절이 명시한 폐쇄 7종.
_EXPECTED = {
    "DEDUCTION",
    "SUBSTITUTION",
    "CASE_SPLIT",
    "INDUCTION",
    "TRANSFORMATION",
    "HEURISTIC",
    "BACKWARD",
}


def test_reasoning_type_is_closed_seven() -> None:
    """정확히 7종(6~8 폐쇄 상한 안) — 증식하면 실패해 '의도적 결정'을 강제한다."""
    assert {m.value for m in ReasoningType} == _EXPECTED
    assert len(ReasoningType) == 7


def test_reasoning_type_str_enum_roundtrip() -> None:
    """str-Enum — 값 문자열과 동등 비교·`(value)` 왕복(BloomLevel·CognitiveType 선례)."""
    assert ReasoningType.DEDUCTION == "DEDUCTION"
    assert ReasoningType("CASE_SPLIT") is ReasoningType.CASE_SPLIT
    # 멤버명 = 값(국제 인지 어휘 컨벤션) — 대문자 영어 일치.
    for member in ReasoningType:
        assert member.name == member.value
