"""concept_content 교수법-중립성 감사 동결 — 기존 콘텐츠 좌석에 방식 컬럼 부재(03c §1·acceptance 1).

03c §1의 1차 작업은 *새 테이블 신설이 아니라* 기존 `db/models/concept_content.py`가 이미 교수법-
중립인지 감사·정렬하는 것이다. 이 테스트는 그 감사 결과를 코드로 동결한다 — `ConceptContent` ORM의
어떤 컬럼도 교수법 *전략/방식*(socratic·direct 등 "어떻게 가르칠지")을 담지 않음을 전수 확인한다.

⚠️ `metaphor`·`misconception`은 방식이 아니라 *콘텐츠*(지식)다 — 은유·오개념은 "무엇을 아는가"
이지 "어떻게 가르치는가"가 아니므로 방식 토큰에 넣지 않는다(감사 노트
`docs/reviews/rend01_concept_content_neutrality_audit.md` 참조). 값 수준 spot-check는 노트가 다룬다.
"""

from __future__ import annotations

from whymath_backend.db.models.concept_content import ConceptContent

# 교수법 *방식/전략* 토큰 — 컬럼명이 이 중 하나를 부분 문자열로 포함하면 방식이 콘텐츠 좌석에
# 새어든 것(중립성 위반). 콘텐츠 토큰(metaphor·misconception·explanation·flashcard)은 제외한다.
_METHOD_TOKENS: frozenset[str] = frozenset(
    {
        "strategy",
        "pedagogy",
        "socratic",
        "direct_instruction",
        "worked_example",
        "problem_based",
        "teaching",
        "instruction_mode",
        "render_mode",
        "hint_level",
        "game",
    }
)


def test_concept_content_has_no_pedagogy_method_column() -> None:
    """ConceptContent 전 컬럼에 교수법 방식/전략 컬럼이 없다(교수법-중립 좌석 동결)."""
    offenders: dict[str, list[str]] = {}
    for column_name in ConceptContent.__table__.columns.keys():
        lowered = column_name.lower()
        hits = [tok for tok in _METHOD_TOKENS if tok in lowered]
        if hits:
            offenders[column_name] = sorted(hits)
    assert not offenders, (
        f"concept_content에 교수법 방식 컬럼이 있습니다: {offenders} — 콘텐츠 좌석은 "
        "교수법-중립이어야 한다(방식은 l3/render 어댑터가 렌더 시점에·03c §1)."
    )


def test_concept_content_columns_are_knowledge_fields() -> None:
    """감사 스냅샷 — 현재 컬럼 집합을 동결(신규 컬럼이 방식이면 위 테스트와 함께 리뷰 강제)."""
    expected = {
        "code",
        "scope",
        "name",
        "subject",
        "unit",
        "metaphor",
        "misconception",
        "formal_definition_internal",
        "accepted_expressions",
        "explanation",
        "standard_codes",
        "atom_codes",
        "flashcards",
        "review_status",
        "updated_at",
    }
    actual = set(ConceptContent.__table__.columns.keys())
    assert actual == expected, (
        f"concept_content 컬럼 집합이 감사 스냅샷과 다릅니다 — 발견 {sorted(actual)}. "
        "신규 컬럼이 방식이 아니라 지식 필드인지 확인하고 이 스냅샷과 감사 노트를 갱신하라."
    )
