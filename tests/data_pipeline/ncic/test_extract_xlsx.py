"""extract_xlsx — 순수 행 파서 + openpyxl 라운드트립 테스트."""

from __future__ import annotations

from pathlib import Path

import pytest

from data_pipeline.ncic.extract_xlsx import (
    ExtractError,
    extract_file_a,
    parse_link_row,
    parse_standard_row,
)
from data_pipeline.ncic.transform import TransformError
from data_pipeline.ncic.validate import validate_links, validate_standards


# ──────────────────────────────────────────────────────────────────────
# 순수 행 파서 (openpyxl 불요 — transform 레이어 재사용)
# ──────────────────────────────────────────────────────────────────────
class TestParseStandardRow:
    def test_minimal_row_derives_norm_id(self) -> None:
        std = parse_standard_row(
            {
                "코드": "[9수01-01]",
                "교육과정": "2022개정",  # 공백 없는 변형
                "과목": "수학",
                "영역": "수와 연산",
                "성취기준": "소인수분해를 이해한다.",
            }
        )
        assert std.code == "[9수01-01]"
        assert std.norm_id == "2022_9수_01_01"
        assert std.curriculum_revision == "2022 개정"  # 표기 정규화
        assert std.school_type == "중학교"  # code에서 추론

    def test_missing_source_url_uses_ncic_default(self) -> None:
        std = parse_standard_row({"코드": "[9수01-01]", "성취기준": "x"})
        assert std.source_url == "https://www.ncic.go.kr"

    def test_2015_revision_row(self) -> None:
        std = parse_standard_row(
            {"코드": "[9수01-01]", "교육과정": "2015 개정", "성취기준": "x"}
        )
        assert std.norm_id == "2015_9수_01_01"

    def test_optional_fields_mapped(self) -> None:
        std = parse_standard_row(
            {
                "코드": "[10공수1-01-01]",
                "교육과정": "2022개정",
                "과목": "공통수학1",
                "영역": "다항식",
                "세부영역": "다항식의 연산",
                "성취기준": "다항식의 덧셈을 이해한다.",
                "해설": "동류항 결합.",
                "핵심아이디어": "다항식의 구조와 연산",
                "출처문서": "교육부고시_2022-33호",
            }
        )
        assert std.sub_domain == "다항식의 연산"
        assert std.commentary == "동류항 결합."
        assert std.big_idea == "다항식의 구조와 연산"
        assert std.source_document == "교육부고시_2022-33호"

    def test_missing_statement_raises(self) -> None:
        with pytest.raises(TransformError):
            parse_standard_row({"코드": "[9수01-01]"})


class TestParseLinkRow:
    def test_direct_norm_id(self) -> None:
        link = parse_link_row(
            {"개념ID": "N1", "norm_id": "2022_9수_01_01", "연결구분": "직접"}
        )
        assert link.concept_src_id == "N1"
        assert link.norm_id == "2022_9수_01_01"
        assert link.link_type == "직접"

    def test_norm_id_derived_from_code_and_revision(self) -> None:
        link = parse_link_row(
            {
                "개념ID": "HK42",
                "코드": "[9수01-01]",
                "교육과정": "2015개정",
                "연결구분": "재매핑",
                "비고": "대응",
            }
        )
        assert link.norm_id == "2015_9수_01_01"
        assert link.note == "대응"

    @pytest.mark.parametrize("link_type", ["직접", "재매핑", "준용"])
    def test_all_link_types(self, link_type: str) -> None:
        link = parse_link_row(
            {"개념ID": "N1", "norm_id": "2022_9수_01_01", "연결구분": link_type}
        )
        assert link.link_type == link_type

    def test_missing_norm_id_and_code_raises(self) -> None:
        with pytest.raises(ExtractError):
            parse_link_row({"개념ID": "N1", "연결구분": "직접"})

    def test_invalid_link_type_raises(self) -> None:
        with pytest.raises(TransformError):
            parse_link_row(
                {"개념ID": "N1", "norm_id": "2022_9수_01_01", "연결구분": "유사"}
            )


# ──────────────────────────────────────────────────────────────────────
# openpyxl 라운드트립 (openpyxl 필요 — 없으면 skip)
# ──────────────────────────────────────────────────────────────────────
def _write_file_a(path: Path) -> None:
    """3시트 합성 File A xlsx 작성 — official_code 충돌쌍 포함."""
    openpyxl = pytest.importorskip("openpyxl")
    workbook = openpyxl.Workbook()
    default_sheet = workbook.active
    sheets: dict[str, list[list[str]]] = {
        "성취기준_목록": [
            ["코드", "교육과정", "과목", "영역", "성취기준"],
            ["[9수01-01]", "2022개정", "수학", "수와 연산", "소인수분해를 이해한다."],
            # official_code 충돌 — 같은 code가 2015에도 존재
            [
                "[9수01-01]",
                "2015개정",
                "수학",
                "수와 연산",
                "소인수분해를 이해한다.(2015)",
            ],
            [
                "[10공수1-01-01]",
                "2022개정",
                "공통수학1",
                "다항식",
                "다항식의 덧셈을 이해한다.",
            ],
        ],
        "연결_개념-성취기준": [
            ["개념ID", "norm_id", "코드", "교육과정", "연결구분", "비고"],
            ["N1", "2022_9수_01_01", "", "", "직접", ""],
            ["HK42", "", "[9수01-01]", "2015개정", "재매핑", "2015→2022 대응"],
            ["N2", "2022_10공수1_01_01", "", "", "준용", ""],
        ],
    }
    for name, rows in sheets.items():
        worksheet = workbook.create_sheet(title=name)
        for row in rows:
            worksheet.append(row)
    workbook.remove(default_sheet)
    workbook.save(str(path))


class TestExtractFileA:
    def test_roundtrip_standards_and_links(self, tmp_path: Path) -> None:
        path = tmp_path / "file_a.xlsx"
        _write_file_a(path)
        standards, links = extract_file_a(path)

        assert len(standards) == 3
        norm_ids = {s.norm_id for s in standards}
        # official_code 충돌쌍이 서로 다른 norm_id로 해소됨
        assert "2022_9수_01_01" in norm_ids
        assert "2015_9수_01_01" in norm_ids
        codes = [s.code for s in standards]
        assert codes.count("[9수01-01]") == 2  # 같은 official_code 2건 공존

        assert len(links) == 3
        assert {link.link_type for link in links} == {"직접", "재매핑", "준용"}
        # 코드+교육과정으로 파생된 연결
        hk = next(link for link in links if link.concept_src_id == "HK42")
        assert hk.norm_id == "2015_9수_01_01"

    def test_extracted_set_passes_validation(self, tmp_path: Path) -> None:
        """추출 결과가 불변식을 통과 — 충돌 허용·연결 전부 해소."""
        path = tmp_path / "file_a.xlsx"
        _write_file_a(path)
        standards, links = extract_file_a(path)

        std_report = validate_standards(standards)
        assert std_report.errors == []  # norm_id 유일·(rev,code) 유일

        link_report = validate_links(links, standards, {"N1", "HK42", "N2"})
        assert link_report.errors == []  # 모든 norm_id·concept 해소

    def test_missing_sheet_raises(self, tmp_path: Path) -> None:
        openpyxl = pytest.importorskip("openpyxl")
        path = tmp_path / "empty.xlsx"
        openpyxl.Workbook().save(str(path))
        with pytest.raises(ExtractError):
            extract_file_a(path)
