"""텍스트 정제 함수 단위 테스트."""

from __future__ import annotations

import pytest

from data_pipeline.ncic.clean import clean_text, normalize_code


class TestCleanText:
    def test_empty_string(self) -> None:
        assert clean_text("") == ""

    def test_whitespace_only(self) -> None:
        assert clean_text("   \t  \n  ") == ""

    def test_collapses_multiple_spaces(self) -> None:
        assert clean_text("소인수분해의   뜻을   알고") == "소인수분해의 뜻을 알고"

    def test_removes_zero_width_chars(self) -> None:
        # ZWSP (U+200B) · ZWNJ (U+200C) · BOM (U+FEFF)
        text = "소인​수‌분﻿해"
        assert clean_text(text) == "소인수분해"

    def test_html_entities_decoded(self) -> None:
        assert clean_text("자연수를&nbsp;소인수분해") == "자연수를 소인수분해"
        assert clean_text("&amp;&lt;&gt;") == "&<>"

    def test_collapses_unicode_spaces(self) -> None:
        # NBSP·전각 공백·narrow NBSP 등
        text = "자연수를 소인수분해　합니다 ."
        cleaned = clean_text(text)
        assert " " not in cleaned
        assert "　" not in cleaned
        assert " " not in cleaned

    def test_removes_control_chars_keeps_newlines(self) -> None:
        text = "본문\x00안에\x07제어문자\n다음 줄"
        cleaned = clean_text(text)
        assert "\x00" not in cleaned
        assert "\x07" not in cleaned
        assert "\n" in cleaned

    def test_collapses_multiple_newlines(self) -> None:
        text = "첫 단락\n\n\n\n둘째 단락"
        cleaned = clean_text(text)
        # 3+ 개행은 2개로 축약
        assert "\n\n\n" not in cleaned
        assert "\n\n" in cleaned

    def test_preserves_korean_punctuation_and_hanja(self) -> None:
        text = "수학(數學)의 정의: ‘수’와 관련된 학문."
        cleaned = clean_text(text)
        assert "數學" in cleaned
        assert "‘" in cleaned

    def test_pdf_line_break_hyphen_joined(self) -> None:
        """PDF 줄바꿈 하이픈 결합 (영문 혼용 시)."""
        text = "다항식(poly-\nnomial)의 곱셈"
        cleaned = clean_text(text)
        assert "polynomial" in cleaned


class TestNormalizeCode:
    def test_removes_spaces_inside_brackets(self) -> None:
        assert normalize_code("[ 9수 01-01 ]") == "[9수01-01]"

    @pytest.mark.parametrize(
        "input_code, expected",
        [
            ("[9수01–01]", "[9수01-01]"),  # en-dash
            ("[9수01—01]", "[9수01-01]"),  # em-dash
            ("[9수01−01]", "[9수01-01]"),  # minus sign
            ("[9수01‐01]", "[9수01-01]"),  # hyphen U+2010
            ("[9수01‑01]", "[9수01-01]"),  # non-breaking hyphen
            ("[9수01―01]", "[9수01-01]"),  # horizontal bar
        ],
    )
    def test_dash_variants_normalized(self, input_code: str, expected: str) -> None:
        """다양한 dash 변형 → ASCII '-'."""
        assert normalize_code(input_code) == expected

    def test_preserves_korean_chars(self) -> None:
        assert normalize_code("[12미적Ⅰ01-01]") == "[12미적Ⅰ01-01]"
