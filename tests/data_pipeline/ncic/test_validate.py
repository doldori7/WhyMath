"""validate_standards·validate_links 검증 테스트."""

from __future__ import annotations

import pytest

from data_pipeline.ncic.models import AchievementStandard, ConceptStandardLink
from data_pipeline.ncic.transform import build_norm_id
from data_pipeline.ncic.validate import validate_links, validate_standards


def _make_std(code: str = "[9수01-01]", **overrides: object) -> AchievementStandard:
    """테스트용 표준 인스턴스 빌더. norm_id는 (개정, code)로 파생(override 가능)."""
    revision = str(overrides.get("curriculum_revision", "2022 개정"))
    defaults: dict[str, object] = {
        "norm_id": build_norm_id(revision, code),
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
        # curriculum_split INFO는 issues에 누적되나 오류(errors)는 없음
        assert report.errors == []

    def test_summary_format(self) -> None:
        report = validate_standards([_make_std()])
        s = report.summary()
        assert "1" in s
        assert "통과" in s


class TestNormIdUniqueness:
    def test_detects_duplicate_norm_id(self) -> None:
        """동일 std 2회 → 두 번째에서 norm_id_unique 위반."""
        std = _make_std()
        report = validate_standards([std, std])
        assert report.total == 2
        assert any(i.rule == "norm_id_unique" for i in report.errors)

    def test_forced_norm_id_collision_flagged(self) -> None:
        """code는 달라도 norm_id가 겹치면 위반."""
        a = _make_std("[9수01-01]")
        b = _make_std("[9수01-02]", norm_id="2022_9수_01_01")  # 강제 충돌
        report = validate_standards([a, b])
        assert any(i.rule == "norm_id_unique" for i in report.errors)
        assert report.success is False


class TestOfficialCodeNonUnique:
    def test_same_code_across_curricula_passes(self) -> None:
        """같은 official_code가 2022·2015에 공존 → 위반 아님(norm_id·(rev,code) 모두 유일)."""
        s2022 = _make_std("[9수01-01]", curriculum_revision="2022 개정")
        s2015 = _make_std("[9수01-01]", curriculum_revision="2015 개정")
        report = validate_standards([s2022, s2015])
        assert report.errors == []
        assert report.success is True

    def test_same_code_same_curriculum_flagged(self) -> None:
        """같은 교육과정 안에서 code 중복(강제) → official_code_curriculum_unique 위반."""
        a = _make_std("[9수01-01]")
        b = _make_std("[9수01-01]", norm_id="2022_9수_99_99")  # norm_id는 다르게
        report = validate_standards([a, b])
        assert any(i.rule == "official_code_curriculum_unique" for i in report.errors)


class TestCurriculumSplit:
    def test_curriculum_split_info_reported(self) -> None:
        """개정별 건수는 INFO로 집계되며 통과 판정에 영향 없음."""
        s2022 = _make_std("[9수01-01]", curriculum_revision="2022 개정")
        s2015 = _make_std("[9수01-01]", curriculum_revision="2015 개정")
        report = validate_standards([s2022, s2015])
        splits = [i for i in report.infos if i.rule == "curriculum_split"]
        assert len(splits) == 2
        assert report.success is True


class TestSourceUrlMandatory:
    def test_blank_source_url_fails(self) -> None:
        """공공누리 1유형 — source_url 누락은 위반."""
        std = AchievementStandard(
            norm_id="2022_9수_01_01",
            code="[9수01-01]",
            grade_band="중학교 1~3학년군",
            school_type="중학교",
            subject="수학",
            domain="수와 연산",
            statement="x",
            source_url="   ",  # 공백만
        )
        report = validate_standards([std])
        assert any(i.rule == "source_url_required" for i in report.errors)
        assert report.success is False


class TestMultipleStandards:
    def test_mixed_pass_and_fail(self) -> None:
        """일부 통과, 일부 실패 — 카운트 정확."""
        good = _make_std("[9수01-01]")
        dup = _make_std("[9수01-02]")
        report = validate_standards([good, dup, dup])
        # 3개 중 첫 2개 통과, 3번째는 norm_id 중복으로 실패
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
    def test_diverse_curriculum_codes_pass(
        self, code: str, school: str, band: str
    ) -> None:
        std = _make_std(
            code=code, school_type=school, grade_band=band, subject="x", domain="x"
        )
        report = validate_standards([std])
        assert report.success is True


# ──────────────────────────────────────────────────────────────────────
# 개념↔성취기준 연결 검증 — P1-1 신규
# ──────────────────────────────────────────────────────────────────────
class TestValidateLinks:
    def test_all_resolve_passes(self) -> None:
        std = _make_std("[9수01-01]")
        link = ConceptStandardLink(
            concept_src_id="N1", norm_id=std.norm_id, link_type="직접"
        )
        report = validate_links([link], [std], {"N1"})
        assert report.success is True
        assert report.errors == []

    def test_unresolved_norm_id_flagged(self) -> None:
        std = _make_std("[9수01-01]")
        link = ConceptStandardLink(
            concept_src_id="N1", norm_id="2015_9수_99_99", link_type="직접"
        )
        report = validate_links([link], [std], {"N1"})
        assert any(i.rule == "link_norm_id_resolves" for i in report.errors)
        assert report.success is False

    def test_unresolved_concept_flagged(self) -> None:
        std = _make_std("[9수01-01]")
        link = ConceptStandardLink(
            concept_src_id="GHOST", norm_id=std.norm_id, link_type="직접"
        )
        report = validate_links([link], [std], {"N1"})
        assert any(i.rule == "link_concept_resolves" for i in report.errors)
        assert report.success is False

    def test_invalid_link_type_flagged(self) -> None:
        """모델을 우회(model_construct)해 비허용 link_type을 넣어도 검증기가 잡는다."""
        std = _make_std("[9수01-01]")
        bad = ConceptStandardLink.model_construct(
            concept_src_id="N1", norm_id=std.norm_id, link_type="유사"
        )
        report = validate_links([bad], [std], {"N1"})
        assert any(i.rule == "link_type_enum" for i in report.errors)
