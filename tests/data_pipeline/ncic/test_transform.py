"""raw 레코드 → AchievementStandard 변환 테스트."""

from __future__ import annotations

import pytest

from data_pipeline.ncic.transform import (
    TransformError,
    build_norm_id,
    infer_school_and_band,
    normalize_norm_id,
    parse_standard_code,
    resolve_subject,
    transform_raw_to_link,
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
            transform_raw_to_standard({"statement": "x", "source_url": "https://x.com"})

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

    def test_norm_id_derived_when_absent(self) -> None:
        """raw에 norm_id 없으면 (개정, code)로 결정적 파생."""
        std = transform_raw_to_standard(
            {
                "code": "[9수01-01]",
                "statement": "소인수분해를 이해한다.",
                "source_url": "https://x.com",
            }
        )
        assert std.norm_id == "2022_9수_01_01"

    def test_norm_id_used_when_present(self) -> None:
        """raw에 norm_id 있으면 그대로(공백만 정규화)."""
        std = transform_raw_to_standard(
            {
                "code": "[9수01-01]",
                "norm_id": " 2022_9수_01_01 ",
                "statement": "x",
                "source_url": "https://x.com",
            }
        )
        assert std.norm_id == "2022_9수_01_01"

    def test_revision_2015_drives_norm_id_prefix(self) -> None:
        """2015 개정 명시 → norm_id가 2015 prefix로 파생."""
        std = transform_raw_to_standard(
            {
                "code": "[9수01-01]",
                "curriculum_revision": "2015 개정",
                "statement": "x",
                "source_url": "https://x.com",
            }
        )
        assert std.norm_id == "2015_9수_01_01"
        assert std.curriculum_revision == "2015 개정"


# ──────────────────────────────────────────────────────────────────────
# norm_id 파생·정규화 — P1-1 신규
# ──────────────────────────────────────────────────────────────────────
class TestBuildNormId:
    @pytest.mark.parametrize(
        "revision, code, expected",
        [
            ("2022 개정", "[2수01-01]", "2022_2수_01_01"),
            ("2022 개정", "[9수01-01]", "2022_9수_01_01"),
            ("2022 개정", "[10공수1-01-01]", "2022_10공수1_01_01"),
            ("2015 개정", "[12미적Ⅰ01-03]", "2015_12미적I_01_03"),  # 로마숫자→ASCII
            ("2015 개정", "[6수04-05]", "2015_6수_04_05"),
        ],
    )
    def test_deterministic_norm_id(
        self, revision: str, code: str, expected: str
    ) -> None:
        assert build_norm_id(revision, code) == expected

    def test_idempotent(self) -> None:
        """같은 입력 → 항상 같은 출력."""
        assert build_norm_id("2022 개정", "[9수01-01]") == build_norm_id(
            "2022 개정", "[9수01-01]"
        )

    def test_unsupported_revision_raises(self) -> None:
        with pytest.raises(TransformError):
            build_norm_id("2009 개정", "[9수01-01]")

    def test_malformed_code_raises(self) -> None:
        with pytest.raises(TransformError):
            build_norm_id("2022 개정", "not-a-code")


class TestNormalizeNormId:
    def test_strips_internal_and_edge_whitespace(self) -> None:
        assert normalize_norm_id("  2022_9수 _01_01 ") == "2022_9수_01_01"


class Test2015SubjectTokens:
    @pytest.mark.parametrize(
        "token, expected",
        [
            ("수학Ⅰ", "수학Ⅰ"),
            ("수학I", "수학Ⅰ"),  # ASCII 변형
            ("수학II", "수학Ⅱ"),
            ("미적", "미적분"),
        ],
    )
    def test_2015_subject_resolution(self, token: str, expected: str) -> None:
        assert resolve_subject(token) == expected


# ──────────────────────────────────────────────────────────────────────
# 개념↔성취기준 연결 변환 — P1-1 신규
# ──────────────────────────────────────────────────────────────────────
class TestTransformRawToLink:
    def test_minimal_valid_link(self) -> None:
        link = transform_raw_to_link(
            {"concept_src_id": "N1", "norm_id": "2022_9수_01_01", "link_type": "직접"}
        )
        assert link.concept_src_id == "N1"
        assert link.norm_id == "2022_9수_01_01"
        assert link.link_type == "직접"
        assert link.note is None

    def test_link_with_note(self) -> None:
        link = transform_raw_to_link(
            {
                "concept_src_id": "HK42",
                "norm_id": "2015_9수_01_01",
                "link_type": "재매핑",
                "note": "2015→2022 대응",
            }
        )
        assert link.note == "2015→2022 대응"

    def test_norm_id_whitespace_normalized(self) -> None:
        link = transform_raw_to_link(
            {"concept_src_id": "N1", "norm_id": " 2022_9수_01_01 ", "link_type": "준용"}
        )
        assert link.norm_id == "2022_9수_01_01"

    @pytest.mark.parametrize("missing", ["concept_src_id", "norm_id", "link_type"])
    def test_missing_required_field_raises(self, missing: str) -> None:
        raw = {
            "concept_src_id": "N1",
            "norm_id": "2022_9수_01_01",
            "link_type": "직접",
        }
        del raw[missing]
        with pytest.raises(TransformError):
            transform_raw_to_link(raw)  # type: ignore[arg-type]

    def test_invalid_link_type_raises(self) -> None:
        with pytest.raises(TransformError):
            transform_raw_to_link(
                {
                    "concept_src_id": "N1",
                    "norm_id": "2022_9수_01_01",
                    "link_type": "유사",
                }
            )
