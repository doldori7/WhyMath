"""raw 레코드 → AchievementStandard 변환 테스트."""

from __future__ import annotations

import pytest

from data_pipeline.ncic.transform import (
    TransformError,
    infer_school_and_band,
    parse_standard_code,
    resolve_subject,
    transform_raw_to_standard,
)


class TestParseStandardCode:
    def test_middle_school_code(self) -> None:
        grade, subject, domain, seq = parse_standard_code("[9수01-01]")
        assert grade == "9"
        assert subject == "수"
        assert domain == "01"
        assert seq == "01"

    def test_high_school_common_code(self) -> None:
        grade, subject, domain, seq = parse_standard_code("[10공수1-01-01]")
        # 패턴은 그리디 매치 — `공수1` 까지 과목으로 잡힘
        assert grade == "10"
        assert subject == "공수1"
        assert domain == "01"
        assert seq == "01"

    def test_high_school_selective_code_with_roman(self) -> None:
        grade, subject, domain, seq = parse_standard_code("[12미적Ⅰ01-01]")
        assert grade == "12"
        assert "미적" in subject  # 'Ⅰ' 포함 여부는 정규식 클래스 따라
        assert domain == "01"
        assert seq == "01"

    def test_invalid_code_raises(self) -> None:
        with pytest.raises(TransformError):
            parse_standard_code("not-a-code")


class TestInferSchoolAndBand:
    @pytest.mark.parametrize(
        "grade_num, expected_school, expected_band",
        [
            ("2", "초등학교", "초등학교 1~2학년군"),
            ("4", "초등학교", "초등학교 3~4학년군"),
            ("6", "초등학교", "초등학교 5~6학년군"),
            ("9", "중학교", "중학교 1~3학년군"),
            ("10", "고등학교", "고등학교"),
            ("12", "고등학교", "고등학교"),
        ],
    )
    def test_known_grade_numbers(
        self, grade_num: str, expected_school: str, expected_band: str
    ) -> None:
        school, band = infer_school_and_band(grade_num)
        assert school == expected_school
        assert band == expected_band

    def test_unknown_grade_number_raises(self) -> None:
        with pytest.raises(TransformError) as exc_info:
            infer_school_and_band("99")
        assert "99" in str(exc_info.value)


class TestResolveSubject:
    def test_explicit_subject_takes_priority(self) -> None:
        """수집기가 명시한 subject가 우선."""
        assert resolve_subject("수", explicit_subject="중학교 수학") == "중학교 수학"

    def test_token_mapped_to_full_name(self) -> None:
        assert resolve_subject("수") == "수학"
        assert resolve_subject("공수1") == "공통수학1"
        assert resolve_subject("미적Ⅰ") == "미적분Ⅰ"
        assert resolve_subject("확통") == "확률과 통계"

    def test_unknown_token_returned_as_is(self) -> None:
        """매핑 미정 토큰은 보수적으로 그대로."""
        assert resolve_subject("새과목") == "새과목"


class TestTransformRawToStandard:
    def test_minimal_valid_record(self) -> None:
        std = transform_raw_to_standard(
            {
                "code": "[9수01-01]",
                "statement": "소인수분해의 뜻을 알고 자연수를 소인수분해할 수 있다.",
                "source_url": "https://www.ncic.go.kr/sample",
            }
        )
        assert std.code == "[9수01-01]"
        assert std.school_type == "중학교"
        assert std.grade_band == "중학교 1~3학년군"
        assert std.subject == "수학"  # 약칭 '수' → '수학'
        assert std.domain == "미지정"  # raw에 없을 때 fallback

    def test_record_with_all_fields(self) -> None:
        std = transform_raw_to_standard(
            {
                "code": "[10공수1-01-01]",
                "subject": "공통수학1",
                "domain": "다항식",
                "sub_domain": "다항식의 사칙연산",
                "statement": "다항식의 덧셈을 이해한다.",
                "commentary": "동류항 결합 등 기본 연산 규칙을 활용한다.",
                "big_idea": "다항식의 구조와 연산",
                "source_url": "https://www.ncic.go.kr/x",
                "source_document": "교육부고시_2022-33호_별책8",
            }
        )
        assert std.subject == "공통수학1"
        assert std.commentary is not None
        assert "동류항" in std.commentary

    def test_normalizes_dash_variants_in_code(self) -> None:
        std = transform_raw_to_standard(
            {
                "code": "[9수01—01]",  # em-dash
                "statement": "x",
                "source_url": "https://x.com",
            }
        )
        assert std.code == "[9수01-01]"

    def test_missing_code_raises(self) -> None:
        with pytest.raises(TransformError):
            transform_raw_to_standard(
                {"statement": "x", "source_url": "https://x.com"}
            )

    def test_missing_statement_raises(self) -> None:
        with pytest.raises(TransformError):
            transform_raw_to_standard(
                {"code": "[9수01-01]", "source_url": "https://x.com"}
            )

    def test_missing_source_url_raises(self) -> None:
        """공공누리 1유형 의무 — source_url 누락 시 변환 거부."""
        with pytest.raises(TransformError) as exc_info:
            transform_raw_to_standard({"code": "[9수01-01]", "statement": "x"})
        assert "source_url" in str(exc_info.value) or "공공누리" in str(exc_info.value)

    def test_empty_statement_after_cleaning_raises(self) -> None:
        """정제 후 statement가 빈 문자열 → 거부."""
        with pytest.raises(TransformError):
            transform_raw_to_standard(
                {
                    "code": "[9수01-01]",
                    "statement": "   \n\t  ",
                    "source_url": "https://x.com",
                }
            )
