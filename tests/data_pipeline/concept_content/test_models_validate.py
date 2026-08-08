"""K-12 콘텐츠 모델·검증 단위테스트 — 코드 완화·자체작성 표기·집합 invariant."""

from __future__ import annotations

import pytest
from data_pipeline.concept_content.models import (
    LICENSE_NOTICE,
    SOURCE_CITATION,
    ConceptContent,
    Flashcard,
)
from data_pipeline.concept_content.validate import validate_content
from pydantic import ValidationError


def _content(code: str = "N1", **over: object) -> ConceptContent:
    base: dict[str, object] = {
        "code": code,
        "name": "수 감각",
        "subject": "수학(초1~2)",
        "metaphor": "은유",
        "misconception": "오개념",
        "formal_definition_internal": "정식정의",
        "accepted_expressions": "허용표현",
    }
    base.update(over)
    return ConceptContent(**base)  # type: ignore[arg-type]


class TestModels:
    def test_valid_content(self) -> None:
        c = _content()
        assert c.code == "N1"
        assert c.flashcards == []
        assert c.standard_codes == []

    @pytest.mark.parametrize("code", ["N1", "A1", "HK01", "F2", "10기수1-01-01", "Q2"])
    def test_accepts_varied_k12_codes(self, code: str) -> None:
        # K-12 개념ID는 형식이 다양 → 비어있지 않으면 통과(U4 SUBUNIT_PATTERN 미적용).
        assert _content(code=code).code == code

    @pytest.mark.parametrize("bad", ["", "   "])
    def test_rejects_blank_code(self, bad: str) -> None:
        with pytest.raises(ValidationError, match="공란"):
            _content(code=bad)

    def test_standard_codes_preserved(self) -> None:
        c = _content(standard_codes=["[2수01-01]", "[2수01-02]"])
        assert c.standard_codes == ["[2수01-01]", "[2수01-02]"]

    def test_flashcard_fields(self) -> None:
        card = Flashcard(front="앞", back="뒤", mnemonic="암기")
        assert card.front == "앞" and card.exposure_condition is None

    def test_forbids_extra(self) -> None:
        with pytest.raises(ValidationError):
            _content(unexpected="x")

    def test_no_ncic_body_field(self) -> None:
        # NCIC 본문(성취기준 문장/요약)은 모델 필드로 존재하지 않는다(redaction).
        fields = set(ConceptContent.model_fields)
        assert "standard_statement" not in fields
        assert "standard_summary" not in fields
        assert "standard_codes" in fields


class TestValidate:
    def test_valid_set(self) -> None:
        report = validate_content([_content()])
        assert report.is_valid
        assert report.content_count == 1

    def test_duplicate_code_error(self) -> None:
        report = validate_content([_content(), _content()])
        assert not report.is_valid
        assert any(r[1] == "code_unique" for r in report.errors)

    def test_missing_content_is_warning(self) -> None:
        # 콘텐츠 누락은 warning(검수 큐)·적재 차단 아님.
        report = validate_content([_content(metaphor=None, misconception=None)])
        assert report.is_valid
        assert any(r[1] == "content_present" for r in report.issues)

    def test_flashcard_count(self) -> None:
        c = _content(flashcards=[Flashcard(front="a", back="b")])
        report = validate_content([c])
        assert report.flashcard_count == 1


def test_self_authored_license() -> None:
    assert "자체" in SOURCE_CITATION
    assert "학생 비노출" in LICENSE_NOTICE and "검수필요" in LICENSE_NOTICE
    # NCIC 본문 미수록·코드만 보존 표기.
    assert "미수록" in LICENSE_NOTICE
