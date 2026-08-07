"""대학 콘텐츠 모델·검증 단위테스트 — 코드 형식·자체작성 표기·집합 invariant."""

from __future__ import annotations

import pytest
from data_pipeline.concept_content_university.models import (
    LICENSE_NOTICE,
    SOURCE_CITATION,
    Flashcard,
    UniversityConceptContent,
)
from data_pipeline.concept_content_university.validate import validate_content
from pydantic import ValidationError


def _content(code: str = "CALC1-U1-S1", **over: object) -> UniversityConceptContent:
    base: dict[str, object] = {
        "code": code,
        "name": "함수",
        "subject": "미적분학 I",
        "metaphor": "은유",
        "misconception": "오개념",
        "formal_definition_internal": "정식정의",
        "accepted_expressions": "허용표현",
    }
    base.update(over)
    return UniversityConceptContent(**base)  # type: ignore[arg-type]


class TestModels:
    def test_valid_content(self) -> None:
        c = _content()
        assert c.code == "CALC1-U1-S1"
        assert c.flashcards == []

    @pytest.mark.parametrize("bad", ["CALC1-S1", "calc1-u1-s1", "[CALC1-01-01]", "N4"])
    def test_rejects_bad_code(self, bad: str) -> None:
        with pytest.raises(ValidationError, match="소단원 코드 형식"):
            _content(code=bad)

    def test_flashcard_fields(self) -> None:
        card = Flashcard(front="앞", back="뒤", mnemonic="암기")
        assert card.front == "앞" and card.exposure_condition is None

    def test_forbids_extra(self) -> None:
        with pytest.raises(ValidationError):
            _content(unexpected="x")


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
