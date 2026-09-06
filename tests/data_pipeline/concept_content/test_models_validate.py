"""K-12 콘텐츠 모델·검증 단위테스트 — 코드 완화·자체작성 표기·집합 invariant."""

from __future__ import annotations

import json
from pathlib import Path

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
    # 2026-09-06 정정: 옛 선언은 "NCIC 본문 미수록"이었으나 실제로는 explanation 133건이
    # 성취기준 본문과 사실상 동일했다(전수 실측). 데이터를 지우는 대신 선언을 데이터에
    # 맞췄으므로(교육부 고시 = 저작권법 §7 비보호 + 공공누리 제1유형), 이제 상수가 지켜야 할
    # 것은 "미수록" 주장이 아니라 **출처 표시**다 — 공공누리 제1유형의 유일한 조건이다.
    # 코퍼스 파일과의 바이트 동일성은 tests/backend/l1/test_concept_content_license_declaration.py.
    assert "미수록" not in LICENSE_NOTICE
    for marker in ("NCIC", "교육부 고시 제2022-33호", "공공누리"):
        assert marker in LICENSE_NOTICE, f"출처 표시에 '{marker}' 누락"


# 이 상수들은 코퍼스를 *생성*한다. 커밋된 코퍼스만 고치고 여기를 놔두면 다음 재생성에서 옛
# 선언이 소리 없이 돌아온다 — 2026-09-06 정정에서 실제로 드러난 드리프트 경로다. 그래서
# "선언이 옳다"가 아니라 "**생성원과 산출물이 같다**"를 동결한다(집행 지점 분리).
_CORPUS = (
    Path(__file__).resolve().parents[3] / "data" / "corpus" / "concept_content_v1" / "content.json"
)


def test_constants_match_committed_corpus() -> None:
    committed = json.loads(_CORPUS.read_text(encoding="utf-8"))
    assert committed["source_citation"] == SOURCE_CITATION, (
        "커밋된 코퍼스의 source_citation이 파이프라인 상수와 다르다 — 재생성하면 코퍼스 선언이 "
        "조용히 뒤집힌다. 둘을 함께 갱신하라."
    )
    assert (
        committed["license_notice"] == LICENSE_NOTICE
    ), "커밋된 코퍼스의 license_notice가 파이프라인 상수와 다르다 — 위와 같은 이유로 red."
