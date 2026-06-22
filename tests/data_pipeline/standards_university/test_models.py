"""대학 성취기준 모델 단위테스트 — Pydantic 검증(코드·norm_id·소단원 형식·본문 비공란·자체작성)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from data_pipeline.standards_university.models import (
    LICENSE_NOTICE,
    SOURCE_CITATION,
    UniversityConceptStandardLink,
    UniversityStandard,
)


class TestUniversityStandard:
    def test_minimal_valid(self) -> None:
        s = UniversityStandard(
            norm_id="대학_CALC1_01_01",
            code="[CALC1-01-01]",
            subject="미적분학 I",
            domain="극한",
            statement="극한의 ε-δ 정의를 안다.",
        )
        # 대학 상수 기본값.
        assert s.curriculum_revision == "대학"
        assert s.grade_band == "대학교"
        assert s.school_type == "대학교"
        assert s.parent_codes == []
        assert "자체작성" in s.source_document

    @pytest.mark.parametrize(
        "bad", ["CALC1-01-01", "[CALC1-1-1]", "[calc1-01-01]", "[CALC1-01]"]
    )
    def test_rejects_bad_code(self, bad: str) -> None:
        with pytest.raises(ValidationError, match="코드 형식"):
            UniversityStandard(
                norm_id="대학_CALC1_01_01",
                code=bad,
                subject="x",
                domain="y",
                statement="z",
            )

    @pytest.mark.parametrize(
        "bad", ["CALC1_01_01", "대학-CALC1-01-01", "고등_CALC1_01_01x"]
    )
    def test_rejects_bad_norm_id(self, bad: str) -> None:
        with pytest.raises(ValidationError, match="norm_id 형식"):
            UniversityStandard(
                norm_id=bad,
                code="[CALC1-01-01]",
                subject="x",
                domain="y",
                statement="z",
            )

    def test_rejects_empty_statement(self) -> None:
        with pytest.raises(ValidationError, match="statement"):
            UniversityStandard(
                norm_id="대학_CALC1_01_01",
                code="[CALC1-01-01]",
                subject="x",
                domain="y",
                statement="   ",
            )

    def test_forbids_extra_keys(self) -> None:
        # extra=forbid — backend 로더가 코퍼스 `code`만 보기에 잉여 키 차단.
        with pytest.raises(ValidationError):
            UniversityStandard(
                norm_id="대학_CALC1_01_01",
                code="[CALC1-01-01]",
                subject="x",
                domain="y",
                statement="z",
                unexpected="bad",  # type: ignore[call-arg]
            )

    def test_dump_has_loader_keys(self) -> None:
        # backend 로더가 읽는 키(code 보존·official_code 아님)가 산출에 있다.
        d = UniversityStandard(
            norm_id="대학_CALC1_01_01",
            code="[CALC1-01-01]",
            subject="x",
            domain="y",
            statement="z",
        ).model_dump(mode="json")
        assert d["code"] == "[CALC1-01-01]"
        assert "official_code" not in d  # rename은 backend 로더 몫.
        assert set(d) >= {
            "norm_id",
            "code",
            "school_type",
            "subject",
            "domain",
            "statement",
        }


class TestUniversityLink:
    def test_minimal_valid(self) -> None:
        link = UniversityConceptStandardLink(
            concept_src_id="CALC1-U1-S1", norm_id="대학_CALC1_01_01"
        )
        assert link.link_type == "직접"

    @pytest.mark.parametrize(
        "bad", ["CALC1-S1", "CALC1_U1_S1", "calc1-u1-s1", "[CALC1-01-01]"]
    )
    def test_rejects_bad_subunit(self, bad: str) -> None:
        with pytest.raises(ValidationError, match="소단원 코드 형식"):
            UniversityConceptStandardLink(
                concept_src_id=bad, norm_id="대학_CALC1_01_01"
            )


def test_license_is_self_authored() -> None:
    # 자체작성 표기 — NCIC 공공누리가 아니다(라이선스 분리·redaction 불요).
    assert "자체" in SOURCE_CITATION
    assert "공공누리" in LICENSE_NOTICE and "아니" in LICENSE_NOTICE
    assert "redaction" in LICENSE_NOTICE.lower()
