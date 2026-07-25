"""교수법-중립 ConceptDSL 계약 테스트 — 불변식 + concept_content 투영의 중립성 감사."""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest
from pydantic import ValidationError

from whymath_backend.l3.render.dsl import ConceptAssessment, ConceptDSL, from_concept_content


@dataclass
class _FakeRow:
    """`ConceptContent` ORM 행의 최소 대역 — 렌더 투영은 ORM 세션에 묶이지 않는다."""

    code: str = "N1"
    name: str = "수 개념과 세기"
    subject: str = "초등수학"
    unit: str | None = "수와 연산"
    metaphor: str | None = "사물 하나에 바둑돌 하나씩 짝지어 센다."
    misconception: str | None = "서수와 기수를 혼동한다."
    formal_definition_internal: str | None = "수는 개수(기수)와 순서(서수)를 나타낸다."
    accepted_expressions: str | None = "빠뜨리지 않고 세고 마지막 수가 개수라고 말함"
    explanation: str | None = "수의 필요성을 알고 센다."
    standard_codes: list[str] = field(default_factory=lambda: ["[2수01-01]"])
    atom_codes: list[str] = field(default_factory=lambda: ["atom.count.basic"])
    flashcards: list[dict[str, object]] = field(default_factory=list)


class TestNeutralityInvariant:
    """중립성 불변식 — 본문에 교수 *방식* 지시어가 들어오면 거부한다."""

    def test_method_directive_in_definition_is_rejected(self) -> None:
        with pytest.raises(ValidationError, match="교수법-중립 위반"):
            ConceptDSL(
                code="C1",
                name="개념",
                subject="수학",
                definition="이 개념은 소크라테스식으로 질문하며 가르친다.",
            )

    def test_method_directive_in_example_is_rejected(self) -> None:
        with pytest.raises(ValidationError, match="교수법-중립 위반"):
            ConceptDSL(
                code="C1",
                name="개념",
                subject="수학",
                examples=("발견학습 활동으로 유도한다",),
            )

    def test_neutral_content_is_accepted(self) -> None:
        dsl = ConceptDSL(
            code="C1",
            name="개념",
            subject="수학",
            definition="두 수의 비가 일정한 관계.",
            intuition="저울이 균형을 이루는 상황과 같다.",
            examples=("2:4 = 3:6",),
        )
        assert dsl.code == "C1"
        assert dsl.examples == ("2:4 = 3:6",)

    def test_unknown_field_is_forbidden(self) -> None:
        # extra="forbid" — 계약 밖 필드(특히 방식 축)가 몰래 들어오지 못한다.
        with pytest.raises(ValidationError):
            ConceptDSL(
                code="C1",
                name="개념",
                subject="수학",
                pedagogy="SOCRATIC",  # type: ignore[call-arg]
            )


class TestConceptAssessment:
    """평가 재료 — verify_answer 입력 형식과 정합해야 한다."""

    def test_empty_answer_map_is_rejected(self) -> None:
        with pytest.raises(ValidationError, match="answer_map이 비었습니다"):
            ConceptAssessment(conditions=("x - 1 = 0",), answer_map={})

    def test_valid_assessment(self) -> None:
        assessment = ConceptAssessment(conditions=("x - 1 = 0",), answer_map={"x": "1"})
        assert assessment.conditions == ("x - 1 = 0",)
        assert assessment.prompt is None


class TestFromConceptContent:
    """투영 = 중립성 감사 — 모든 매핑이 '무엇을 가르치나' 축이어야 한다."""

    def test_maps_content_fields_to_neutral_axes(self) -> None:
        dsl = from_concept_content(_FakeRow())
        assert dsl.code == "N1"
        assert dsl.definition is not None and "기수" in dsl.definition
        assert dsl.intuition is not None and "바둑돌" in dsl.intuition
        assert dsl.examples and "마지막 수가 개수" in dsl.examples[0]
        assert dsl.misconceptions and "혼동" in dsl.misconceptions[0]

    def test_relations_merge_standard_and_atom_codes(self) -> None:
        dsl = from_concept_content(_FakeRow())
        assert dsl.relations == ("[2수01-01]", "atom.count.basic")

    def test_explanation_and_flashcards_are_not_projected(self) -> None:
        # explanation(전달 서술 누적 위험)·flashcards(노출 시점 힌트)는 렌더 입력에서 제외한다.
        row = _FakeRow(
            explanation="강의식으로 설명한다",
            flashcards=[{"front": "a", "exposure_condition": "이해 후 노출"}],
        )
        dsl = from_concept_content(row)  # explanation이 실렸다면 중립성 검증에서 터졌을 것이다.
        rendered_text = " ".join(
            [dsl.definition or "", dsl.intuition or "", *dsl.examples, *dsl.misconceptions]
        )
        assert "강의식" not in rendered_text
        assert "노출" not in rendered_text

    def test_blank_fields_become_none_not_empty_string(self) -> None:
        dsl = from_concept_content(_FakeRow(metaphor="   ", accepted_expressions=None))
        assert dsl.intuition is None
        assert dsl.examples == ()
