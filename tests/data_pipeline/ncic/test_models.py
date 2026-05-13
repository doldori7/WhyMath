"""`AchievementStandard` 모델 단위 테스트."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from data_pipeline.ncic.models import (
    LICENSE_NOTICE,
    SOURCE_CITATION,
    STANDARD_CODE_PATTERN,
    AchievementStandard,
    AchievementStandardCollection,
)


# ──────────────────────────────────────────────────────────────────────
# 모델 기본 검증
# ──────────────────────────────────────────────────────────────────────
class TestAchievementStandard:
    def test_minimal_valid_standard(self) -> None:
        """필수 필드만으로 모델 생성."""
        std = AchievementStandard(
            code="[9수01-01]",
            grade_band="중학교 1~3학년군",
            school_type="중학교",
            subject="수학",
            domain="수와 연산",
            statement="소인수분해를 이해한다.",
            source_url="https://www.ncic.go.kr/sample",
        )
        assert std.code == "[9수01-01]"
        assert std.curriculum_revision == "2022 개정"
        assert std.parent_codes == []
        assert std.commentary is None

    def test_high_school_code_with_long_subject(self) -> None:
        """고1 공통수학1 — `[10공수1-01-01]` 형식."""
        std = AchievementStandard(
            code="[10공수1-01-01]",
            grade_band="고등학교",
            school_type="고등학교",
            subject="공통수학1",
            domain="다항식",
            statement="다항식의 덧셈을 이해한다.",
            source_url="https://www.ncic.go.kr/x",
        )
        assert std.subject == "공통수학1"

    def test_high_school_code_with_roman_numeral(self) -> None:
        """`[12미적Ⅰ01-01]` — 로마숫자 포함."""
        std = AchievementStandard(
            code="[12미적Ⅰ01-01]",
            grade_band="고등학교",
            school_type="고등학교",
            subject="미적분Ⅰ",
            domain="함수",
            statement="극한 개념을 이해한다.",
            source_url="https://www.ncic.go.kr/x",
        )
        assert "Ⅰ" in std.subject


class TestCodeValidation:
    @pytest.mark.parametrize(
        "code",
        [
            "[9수01-01]",
            "[9수99-99]",
            "[10공수1-01-01]",
            "[12대수01-01]",
            "[12미적Ⅰ01-01]",
            "[12확통05-12]",
            "[2수01-01]",
            "[6수04-05]",
        ],
    )
    def test_valid_codes_pass_regex(self, code: str) -> None:
        """유효한 코드는 정규식 일치."""
        assert STANDARD_CODE_PATTERN.match(code) is not None

    @pytest.mark.parametrize(
        "bad_code",
        [
            "9수01-01",        # 대괄호 없음
            "[9수0101]",       # 하이픈 없음
            "[9수1-1]",        # 자릿수 부족
            "[수01-01]",       # 학년 없음
            "[9-01-01]",       # 과목 없음
            "[9수01--01]",     # 더블 하이픈
            "",                # 빈 문자열
            "[]",              # 내용 없음
        ],
    )
    def test_invalid_codes_rejected(self, bad_code: str) -> None:
        """모델 생성 시 코드 형식 위반은 ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            AchievementStandard(
                code=bad_code,
                grade_band="중학교 1~3학년군",
                school_type="중학교",
                subject="수학",
                domain="수와 연산",
                statement="x",
                source_url="https://example.com",
            )
        # 에러 메시지에 코드 또는 형식 키워드가 포함
        assert "code" in str(exc_info.value).lower() or "코드" in str(exc_info.value)


class TestSchoolBandConsistency:
    def test_rejects_elementary_with_middle_band(self) -> None:
        """초등학교 + 중학교 학년군 → 검증 실패."""
        with pytest.raises(ValidationError):
            AchievementStandard(
                code="[2수01-01]",
                grade_band="중학교 1~3학년군",  # 불일치
                school_type="초등학교",
                subject="수학",
                domain="수와 연산",
                statement="x",
                source_url="https://example.com",
            )

    def test_rejects_middle_with_high_band(self) -> None:
        """중학교 + 고등학교 학년군 → 검증 실패."""
        with pytest.raises(ValidationError):
            AchievementStandard(
                code="[9수01-01]",
                grade_band="고등학교",
                school_type="중학교",
                subject="수학",
                domain="수와 연산",
                statement="x",
                source_url="https://example.com",
            )

    def test_rejects_high_with_middle_band(self) -> None:
        """고등학교 + 중학교 학년군 → 검증 실패."""
        with pytest.raises(ValidationError):
            AchievementStandard(
                code="[10공수1-01-01]",
                grade_band="중학교 1~3학년군",
                school_type="고등학교",
                subject="공통수학1",
                domain="다항식",
                statement="x",
                source_url="https://example.com",
            )


class TestParentCodes:
    def test_invalid_parent_code_rejected(self) -> None:
        """선수 코드 형식 위반 → 검증 실패."""
        with pytest.raises(ValidationError):
            AchievementStandard(
                code="[9수01-02]",
                grade_band="중학교 1~3학년군",
                school_type="중학교",
                subject="수학",
                domain="수와 연산",
                statement="x",
                source_url="https://example.com",
                parent_codes=["malformed"],
            )

    def test_valid_parent_codes_accepted(self) -> None:
        """유효한 선수 코드 리스트."""
        std = AchievementStandard(
            code="[9수01-02]",
            grade_band="중학교 1~3학년군",
            school_type="중학교",
            subject="수학",
            domain="수와 연산",
            statement="x",
            source_url="https://example.com",
            parent_codes=["[6수01-05]", "[9수01-01]"],
        )
        assert len(std.parent_codes) == 2


class TestExtraFieldsForbidden:
    def test_extra_field_rejected(self) -> None:
        """`extra='forbid'` — 추가 필드는 거부."""
        with pytest.raises(ValidationError):
            AchievementStandard(
                code="[9수01-01]",
                grade_band="중학교 1~3학년군",
                school_type="중학교",
                subject="수학",
                domain="수와 연산",
                statement="x",
                source_url="https://example.com",
                unknown_field="value",  # type: ignore[call-arg]
            )


class TestCollection:
    def test_collection_includes_license_metadata(self) -> None:
        """컬렉션은 항상 출처·라이선스 표지를 가진다."""
        coll = AchievementStandardCollection(collected_at="2026-05-13T00:00:00Z")
        assert coll.source_citation == SOURCE_CITATION
        assert coll.license_notice == LICENSE_NOTICE
        assert coll.count == 0

    def test_collection_count_property(self) -> None:
        """count는 standards 길이."""
        std = AchievementStandard(
            code="[9수01-01]",
            grade_band="중학교 1~3학년군",
            school_type="중학교",
            subject="수학",
            domain="수와 연산",
            statement="x",
            source_url="https://example.com",
        )
        coll = AchievementStandardCollection(
            collected_at="2026-05-13T00:00:00Z",
            standards=[std, std],
        )
        assert coll.count == 2

    def test_source_citation_contains_official_notice_number(self) -> None:
        """SOURCE_CITATION에 고시 번호 포함."""
        assert "2022-33호" in SOURCE_CITATION
        assert "NCIC" in SOURCE_CITATION
        assert "ncic.go.kr" in SOURCE_CITATION
