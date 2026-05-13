"""validate_standards 검증 테스트."""

from __future__ import annotations

import pytest

from data_pipeline.ncic.models import AchievementStandard
from data_pipeline.ncic.validate import validate_standards


def _make_std(code: str = "[9수01-01]", **overrides: object) -> AchievementStandard:
    """테스트용 표준 인스턴스 빌더."""
    defaults: dict[str, object] = {
        "code": code,
        "grade_band": "중학교 1~3학년군",
        "school_type": "중학교",
        "subject": "수학",
        "domain": "수와 연산",
        "statement": "소인수분해를 이해한다.",
        "source_url": "https://www.ncic.go.kr/sample",
    }
    defaults.update(overrides)
    return AchievementStandard(**defaults)  # type: ignore[arg-type]


class TestValidationReportBasics:
    def test_empty_input_not_success(self) -> None:
        """빈 입력은 success=False (total=0)."""
        report = validate_standards([])
        assert report.total == 0
        assert report.passed == 0
        assert report.success is False  # total>0 조건

    def test_single_valid_passes(self) -> None:
        report = validate_standards([_make_std()])
        assert report.total == 1
        assert report.passed == 1
        assert report.failed == 0
        assert report.success is True
        assert report.issues == []

    def test_summary_format(self) -> None:
        report = validate_standards([_make_std()])
        s = report.summary()
        assert "1" in s
        assert "통과" in s


class TestDuplicateDetection:
    def test_detects_duplicate_codes(self) -> None:
        """동일 코드 2회 → 두 번째에서 duplicate 이슈."""
        std = _make_std()
        report = validate_standards([std, std])
        assert report.total == 2
        assert any(i.rule == "duplicate_code" for i in report.issues)


class TestSourceUrlMandatory:
    def test_blank_source_url_fails(self) -> None:
        """공공누리 1유형 — source_url 누락은 위반."""
        # Pydantic은 비공백 강제하지 않으므로 (Field 없이) 공백 가능
        # — validate가 잡아내는지 확인
        std = AchievementStandard(
            code="[9수01-01]",
            grade_band="중학교 1~3학년군",
            school_type="중학교",
            subject="수학",
            domain="수와 연산",
            statement="x",
            source_url="   ",  # 공백만
        )
        report = validate_standards([std])
        assert any(i.rule == "source_url_required" for i in report.issues)
        assert report.success is False


class TestMultipleStandards:
    def test_mixed_pass_and_fail(self) -> None:
        """일부 통과, 일부 실패 — 카운트 정확."""
        good = _make_std("[9수01-01]")
        dup = _make_std("[9수01-02]")
        report = validate_standards([good, dup, dup])
        # 3개 중 첫 2개 통과, 3번째는 중복으로 실패
        assert report.total == 3
        assert report.passed == 2
        assert report.failed == 1


class TestRealWorldShapes:
    """실제 NCIC 데이터에서 발생 가능한 형태들."""

    @pytest.mark.parametrize(
        "code, school, band",
        [
            ("[9수02-03]", "중학교", "중학교 1~3학년군"),
            ("[10공수1-02-05]", "고등학교", "고등학교"),
            ("[12대수01-02]", "고등학교", "고등학교"),
            ("[12미적Ⅰ01-01]", "고등학교", "고등학교"),
        ],
    )
    def test_diverse_curriculum_codes_pass(self, code: str, school: str, band: str) -> None:
        std = _make_std(code=code, school_type=school, grade_band=band, subject="x", domain="x")
        report = validate_standards([std])
        assert report.success is True
