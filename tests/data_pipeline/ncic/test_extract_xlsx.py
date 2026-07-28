"""extract_xlsx — 순수 행 파서 + openpyxl 라운드트립 테스트(실 File A 컬럼 정합).

컬럼 리터럴은 실 File A(2026-06-20·sha256 `4e21d6d4…`) 시트 헤더를 그대로 쓴다 — 매핑 로직이
실 데이터에 정합함을 hermetic하게 검증. 실데이터 특성 3종(연결 시트): 교육과정 열 부재→2022 기본,
link_type 괄호 접미사→베어 토큰·note 보존, code 셀 `;` 다중코드→코드별 링크 분할.
"""

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
                "성취기준 코드": "[9수01-01]",
                "교육과정": "2022개정",  # 공백 없는 변형
                "과목약칭": "수학",
                "영역(단원)": "수와 연산",
                "성취기준 내용": "소인수분해를 이해한다.",
            }
        )
        assert std.code == "[9수01-01]"
        assert std.norm_id == "2022_9수_01_01"
        assert std.curriculum_revision == "2022 개정"  # 표기 정규화
        assert std.school_type == "중학교"  # code에서 추론

    def test_roman_numeral_code_derives_ascii_norm_id(self) -> None:
        """File A norm_id 열(로마숫자 Ⅰ)을 쓰지 않고 code에서 Ⅰ→I 정규화 파생함을 보장."""
        std = parse_standard_row(
            {
                "성취기준 코드": "[12미적Ⅰ-01-01]",
                "교육과정": "2022개정",
                "성취기준 내용": "극한을 이해한다.",
            }
        )
        assert std.norm_id == "2022_12미적I_01_01"  # ASCII I (Ⅰ 아님)

    def test_missing_source_url_uses_ncic_default(self) -> None:
        std = parse_standard_row({"성취기준 코드": "[9수01-01]", "성취기준 내용": "x"})
        assert std.source_url == "https://www.ncic.go.kr"

    def test_2015_revision_row(self) -> None:
        std = parse_standard_row(
            {"성취기준 코드": "[9수01-01]", "교육과정": "2015 개정", "성취기준 내용": "x"}
        )
        assert std.norm_id == "2015_9수_01_01"

    def test_optional_fields_mapped(self) -> None:
        std = parse_standard_row(
            {
                "성취기준 코드": "[10공수1-01-01]",
                "교육과정": "2022개정",
                "과목약칭": "공통수학1",
                "영역(단원)": "다항식",
                "소단원(개념)": "다항식의 연산",
                "성취기준 내용": "다항식의 덧셈을 이해한다.",
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
            parse_standard_row({"성취기준 코드": "[9수01-01]"})


class TestParseLinkRow:
    def test_code_derives_norm_id_default_2022(self) -> None:
        """교육과정 열이 없으면 revision 2022 기본으로 norm_id 파생(단일 코드)."""
        links = parse_link_row(
            {"개념ID": "N1", "한국 성취기준(2022)": "[9수01-01]", "연결구분": "직접"}
        )
        assert len(links) == 1
        assert links[0].concept_src_id == "N1"
        assert links[0].norm_id == "2022_9수_01_01"
        assert links[0].link_type == "직접"

    def test_link_type_paren_stripped_to_note(self) -> None:
        """`직접(기본수학)`→link_type 직접·note 기본수학(괄호 정보 보존)."""
        links = parse_link_row(
            {"개념ID": "N1", "한국 성취기준(2022)": "[9수01-01]", "연결구분": "직접(기본수학)"}
        )
        assert len(links) == 1
        assert links[0].link_type == "직접"
        assert links[0].note == "기본수학"

    def test_remap_paren_stripped(self) -> None:
        links = parse_link_row(
            {
                "개념ID": "HK42",
                "한국 성취기준(2022)": "[9수01-01]",
                "연결구분": "재매핑(2015→2022)",
            }
        )
        assert len(links) == 1
        assert links[0].link_type == "재매핑"
        assert links[0].note == "2015→2022"

    def test_multi_code_cell_splits(self) -> None:
        """code 셀 `;` 다중코드 → 코드별 1 링크로 분할."""
        links = parse_link_row(
            {
                "개념ID": "N5",
                "한국 성취기준(2022)": "[2수03-08];[2수03-09];[4수03-13]",
                "연결구분": "직접",
            }
        )
        assert len(links) == 3
        assert {link.norm_id for link in links} == {
            "2022_2수_03_08",
            "2022_2수_03_09",
            "2022_4수_03_13",
        }
        assert all(link.concept_src_id == "N5" for link in links)

    def test_direct_norm_id_single(self) -> None:
        """norm_id 직접값(하위호환)이 있으면 단일 링크로 우선."""
        links = parse_link_row({"개념ID": "N1", "norm_id": "2022_9수_01_01", "연결구분": "직접"})
        assert len(links) == 1
        assert links[0].norm_id == "2022_9수_01_01"

    @pytest.mark.parametrize("link_type", ["직접", "재매핑", "준용"])
    def test_all_link_types(self, link_type: str) -> None:
        links = parse_link_row(
            {"개념ID": "N1", "한국 성취기준(2022)": "[9수01-01]", "연결구분": link_type}
        )
        assert links[0].link_type == link_type

    def test_missing_norm_id_and_code_raises(self) -> None:
        with pytest.raises(ExtractError):
            parse_link_row({"개념ID": "N1", "연결구분": "직접"})

    def test_invalid_link_type_raises(self) -> None:
        with pytest.raises(TransformError):
            parse_link_row(
                {"개념ID": "N1", "한국 성취기준(2022)": "[9수01-01]", "연결구분": "유사"}
            )


# ──────────────────────────────────────────────────────────────────────
# openpyxl 라운드트립 (openpyxl 필요 — 없으면 skip)
# ──────────────────────────────────────────────────────────────────────
def _write_file_a(path: Path) -> None:
    """합성 File A xlsx 작성 — 실 컬럼명·official_code 충돌쌍·다중코드·괄호 link_type 포함."""
    openpyxl = pytest.importorskip("openpyxl")
    workbook = openpyxl.Workbook()
    default_sheet = workbook.active
    sheets: dict[str, list[list[str]]] = {
        "성취기준_목록": [
            ["성취기준 코드", "교육과정", "과목약칭", "영역(단원)", "성취기준 내용"],
            ["[9수01-01]", "2022개정", "수학", "수와 연산", "소인수분해를 이해한다."],
            # official_code 충돌 — 같은 code가 2015에도 존재
            ["[9수01-01]", "2015개정", "수학", "수와 연산", "소인수분해를 이해한다.(2015)"],
            ["[10공수1-01-01]", "2022개정", "공통수학1", "다항식", "다항식의 덧셈을 이해한다."],
            # 분할 링크의 대상 코드(고아 방지)
            ["[2수03-08]", "2022개정", "수학", "도형과 측정", "도형 A."],
            ["[2수03-09]", "2022개정", "수학", "도형과 측정", "도형 B."],
        ],
        "개념-성취기준-CCSS": [
            ["개념ID", "한국 성취기준(2022)", "연결구분"],
            ["N1", "[9수01-01]", "직접(기본수학)"],  # 괄호 link_type→note
            ["N2", "[10공수1-01-01]", "준용"],
            ["N5", "[2수03-08];[2수03-09]", "직접"],  # 다중코드→2 링크
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

        assert len(standards) == 5
        norm_ids = {s.norm_id for s in standards}
        # official_code 충돌쌍이 서로 다른 norm_id로 해소됨
        assert "2022_9수_01_01" in norm_ids
        assert "2015_9수_01_01" in norm_ids
        codes = [s.code for s in standards]
        assert codes.count("[9수01-01]") == 2  # 같은 official_code 2건 공존

        # 3 연결 행 → 4 링크(N5 다중코드 분할)
        assert len(links) == 4
        n1 = next(link for link in links if link.concept_src_id == "N1")
        assert n1.link_type == "직접" and n1.note == "기본수학"  # 괄호 정규화
        n5 = [link for link in links if link.concept_src_id == "N5"]
        assert {link.norm_id for link in n5} == {"2022_2수_03_08", "2022_2수_03_09"}

    def test_extracted_set_passes_validation(self, tmp_path: Path) -> None:
        """추출 결과가 불변식을 통과 — 충돌 허용·연결 전부 해소."""
        path = tmp_path / "file_a.xlsx"
        _write_file_a(path)
        standards, links = extract_file_a(path)

        std_report = validate_standards(standards)
        assert std_report.errors == []  # norm_id 유일·(rev,code) 유일

        link_report = validate_links(links, standards, {"N1", "N2", "N5"})
        assert link_report.errors == []  # 모든 norm_id·concept 해소

    def test_missing_sheet_raises(self, tmp_path: Path) -> None:
        openpyxl = pytest.importorskip("openpyxl")
        path = tmp_path / "empty.xlsx"
        openpyxl.Workbook().save(str(path))
        with pytest.raises(ExtractError):
            extract_file_a(path)
