"""`AchievementStandard`·`ConceptStandardLink` 모델 단위 테스트."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from data_pipeline.ncic.models import (
    LICENSE_NOTICE,
    NORM_ID_PATTERN,
    SOURCE_CITATION,
    STANDARD_CODE_PATTERN,
    AchievementStandard,
    AchievementStandardCollection,
    ConceptStandardLink,
    ConceptStandardLinkCollection,
)


def _std_kwargs(**overrides: object) -> dict[str, object]:
    """필수 필드를 채운 표준 생성 인자 (norm_id 포함)."""
    base: dict[str, object] = {
        "norm_id": "2022_9수_01_01",
        "code": "[9수01-01]",
        "grade_band": "중학교 1~3학년군",
        "school_type": "중학교",
        "subject": "수학",
        "domain": "수와 연산",
        "statement": "소인수분해를 이해한다.",
        "source_url": "https://www.ncic.go.kr/sample",
    }
    base.update(overrides)
    return base


# ──────────────────────────────────────────────────────────────────────
# 모델 기본 검증
# ──────────────────────────────────────────────────────────────────────
class TestAchievementStandard:
    def test_minimal_valid_standard(self) -> None:
        """필수 필드만으로 모델 생성."""
        std = AchievementStandard(**_std_kwargs())  # type: ignore[arg-type]
        assert std.norm_id == "2022_9수_01_01"
        assert std.code == "[9수01-01]"
        assert std.curriculum_revision == "2022 개정"
        assert std.parent_codes == []
        assert std.commentary is None

    def test_high_school_code_with_long_subject(self) -> None:
        """고1 공통수학1 — `[10공수1-01-01]` 형식."""
        std = AchievementStandard(
            **_std_kwargs(
                norm_id="2022_10공수1_01_01",
                code="[10공수1-01-01]",
                grade_band="고등학교",
                school_type="고등학교",
                subject="공통수학1",
                domain="다항식",
                statement="다항식의 덧셈을 이해한다.",
            )  # type: ignore[arg-type]
        )
        assert std.subject == "공통수학1"

    def test_high_school_code_with_roman_numeral(self) -> None:
        """`[12미적Ⅰ01-01]` — 로마숫자 포함(코드)·norm_id는 ASCII 정규화."""
        std = AchievementStandard(
            **_std_kwargs(
                norm_id="2022_12미적I_01_01",
                code="[12미적Ⅰ01-01]",
                grade_band="고등학교",
                school_type="고등학교",
                subject="미적분Ⅰ",
                domain="함수",
                statement="극한 개념을 이해한다.",
            )  # type: ignore[arg-type]
        )
        assert "Ⅰ" in std.subject


# ──────────────────────────────────────────────────────────────────────
# norm_id (PK) 검증 — P1-1 신규
# ──────────────────────────────────────────────────────────────────────
class TestNormIdValidation:
    @pytest.mark.parametrize(
        "norm_id",
        [
            "2022_2수_01_01",
            "2022_10공수1_01_01",
            "2015_12미적I_01_03",
            "2015_9수_04_05",
        ],
    )
    def test_valid_norm_ids_pass_regex(self, norm_id: str) -> None:
        assert NORM_ID_PATTERN.match(norm_id) is not None

    @pytest.mark.parametrize(
        "bad",
        [
            "2020_2수_01_01",  # 미지원 개정연도
            "2022_2수_1_01",  # 영역 1자리
            "2022_2수_01",  # 순번 누락
            "수_01_01",  # 연도 prefix 없음
            "2022__01_01",  # 빈 토큰
            "2022_2수_01_01_99",  # 꼬리 잉여
            "2022_123456789_01_01",  # 토큰 9자(>8)
        ],
    )
    def test_invalid_norm_ids_rejected(self, bad: str) -> None:
        with pytest.raises(ValidationError) as exc:
            AchievementStandard(**_std_kwargs(norm_id=bad))  # type: ignore[arg-type]
        assert "norm_id" in str(exc.value)


class TestOfficialCodeNonUnique:
    def test_same_code_different_curricula_allowed_at_model_level(self) -> None:
        """같은 official_code가 2022·2015에 공존 가능 — 모델은 norm_id로만 식별."""
        s2022 = AchievementStandard(
            **_std_kwargs(  # type: ignore[arg-type]
                norm_id="2022_9수_01_01",
                code="[9수01-01]",
                curriculum_revision="2022 개정",
            )
        )
        s2015 = AchievementStandard(
            **_std_kwargs(  # type: ignore[arg-type]
                norm_id="2015_9수_01_01",
                code="[9수01-01]",
                curriculum_revision="2015 개정",
            )
        )
        assert s2022.code == s2015.code  # official_code 충돌 허용
        assert s2022.norm_id != s2015.norm_id  # 정규화키로 구분


class TestCurriculumRevision:
    def test_2015_revision_accepted(self) -> None:
        std = AchievementStandard(
            **_std_kwargs(norm_id="2015_9수_01_01", curriculum_revision="2015 개정")  # type: ignore[arg-type]
        )
        assert std.curriculum_revision == "2015 개정"

    def test_unknown_revision_rejected(self) -> None:
        with pytest.raises(ValidationError):
            AchievementStandard(**_std_kwargs(curriculum_revision="2009 개정"))  # type: ignore[arg-type]


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
            "9수01-01",  # 대괄호 없음
            "[9수0101]",  # 하이픈 없음
            "[9수1-1]",  # 자릿수 부족
            "[수01-01]",  # 학년 없음
            "[9-01-01]",  # 과목 없음
            "[9수01--01]",  # 더블 하이픈
            "",  # 빈 문자열
            "[]",  # 내용 없음
        ],
    )
    def test_invalid_codes_rejected(self, bad_code: str) -> None:
        """모델 생성 시 코드 형식 위반은 ValidationError (norm_id는 유효값 고정)."""
        with pytest.raises(ValidationError) as exc_info:
            AchievementStandard(**_std_kwargs(code=bad_code))  # type: ignore[arg-type]
        assert "code" in str(exc_info.value).lower() or "코드" in str(exc_info.value)


class TestSchoolBandConsistency:
    def test_rejects_elementary_with_middle_band(self) -> None:
        """초등학교 + 중학교 학년군 → 검증 실패."""
        with pytest.raises(ValidationError):
            AchievementStandard(
                **_std_kwargs(
                    norm_id="2022_2수_01_01",
                    code="[2수01-01]",
                    grade_band="중학교 1~3학년군",
                    school_type="초등학교",
                )  # type: ignore[arg-type]
            )

    def test_rejects_middle_with_high_band(self) -> None:
        """중학교 + 고등학교 학년군 → 검증 실패."""
        with pytest.raises(ValidationError):
            AchievementStandard(
                **_std_kwargs(grade_band="고등학교", school_type="중학교")  # type: ignore[arg-type]
            )

    def test_rejects_high_with_middle_band(self) -> None:
        """고등학교 + 중학교 학년군 → 검증 실패."""
        with pytest.raises(ValidationError):
            AchievementStandard(
                **_std_kwargs(
                    norm_id="2022_10공수1_01_01",
                    code="[10공수1-01-01]",
                    grade_band="중학교 1~3학년군",
                    school_type="고등학교",
                    subject="공통수학1",
                    domain="다항식",
                )  # type: ignore[arg-type]
            )


class TestParentCodes:
    def test_invalid_parent_code_rejected(self) -> None:
        """선수 코드 형식 위반 → 검증 실패."""
        with pytest.raises(ValidationError):
            AchievementStandard(
                **_std_kwargs(code="[9수01-02]", parent_codes=["malformed"])  # type: ignore[arg-type]
            )

    def test_valid_parent_codes_accepted(self) -> None:
        """유효한 선수 코드 리스트."""
        std = AchievementStandard(
            **_std_kwargs(
                norm_id="2022_9수_01_02",
                code="[9수01-02]",
                parent_codes=["[6수01-05]", "[9수01-01]"],
            )  # type: ignore[arg-type]
        )
        assert len(std.parent_codes) == 2


class TestExtraFieldsForbidden:
    def test_extra_field_rejected(self) -> None:
        """`extra='forbid'` — 추가 필드는 거부."""
        with pytest.raises(ValidationError):
            AchievementStandard(**_std_kwargs(unknown_field="value"))  # type: ignore[arg-type]


# ──────────────────────────────────────────────────────────────────────
# 개념↔성취기준 연결 모델 — P1-1 신규
# ──────────────────────────────────────────────────────────────────────
class TestConceptStandardLink:
    def test_valid_link(self) -> None:
        link = ConceptStandardLink(concept_src_id="N1", norm_id="2022_9수_01_01", link_type="직접")
        assert link.concept_src_id == "N1"
        assert link.link_type == "직접"
        assert link.note is None

    @pytest.mark.parametrize("link_type", ["직접", "재매핑", "준용"])
    def test_all_link_types_accepted(self, link_type: str) -> None:
        link = ConceptStandardLink(
            concept_src_id="N1",
            norm_id="2022_9수_01_01",
            link_type=link_type,  # type: ignore[arg-type]
        )
        assert link.link_type == link_type

    def test_invalid_link_type_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ConceptStandardLink(
                concept_src_id="N1",
                norm_id="2022_9수_01_01",
                link_type="유사",  # type: ignore[arg-type]
            )

    def test_invalid_norm_id_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ConceptStandardLink(concept_src_id="N1", norm_id="bad-id", link_type="직접")

    def test_blank_concept_src_id_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ConceptStandardLink(concept_src_id="", norm_id="2022_9수_01_01", link_type="직접")

    def test_extra_field_forbidden(self) -> None:
        with pytest.raises(ValidationError):
            ConceptStandardLink(
                concept_src_id="N1",
                norm_id="2022_9수_01_01",
                link_type="직접",
                unknown="x",  # type: ignore[call-arg]
            )


class TestCollections:
    def test_standard_collection_license_metadata(self) -> None:
        """성취기준 컬렉션은 항상 출처·라이선스 표지를 가진다."""
        coll = AchievementStandardCollection(collected_at="2026-06-16T00:00:00Z")
        assert coll.source_citation == SOURCE_CITATION
        assert coll.license_notice == LICENSE_NOTICE
        assert coll.count == 0

    def test_standard_collection_count(self) -> None:
        std = AchievementStandard(**_std_kwargs())  # type: ignore[arg-type]
        coll = AchievementStandardCollection(
            collected_at="2026-06-16T00:00:00Z", standards=[std, std]
        )
        assert coll.count == 2

    def test_link_collection_count_and_metadata(self) -> None:
        link = ConceptStandardLink(concept_src_id="N1", norm_id="2022_9수_01_01", link_type="직접")
        coll = ConceptStandardLinkCollection(collected_at="2026-06-16T00:00:00Z", links=[link])
        assert coll.count == 1
        assert coll.source_citation == SOURCE_CITATION
        assert coll.license_notice == LICENSE_NOTICE

    def test_source_citation_contains_official_notice_number(self) -> None:
        """SOURCE_CITATION에 고시 번호 포함."""
        assert "2022-33호" in SOURCE_CITATION
        assert "NCIC" in SOURCE_CITATION
        assert "ncic.go.kr" in SOURCE_CITATION


# ──────────────────────────────────────────────────────────────────────
# 과학과 코드 수용성 동결 — S2 회귀 (subject_expansion_readiness.md §4.2)
# ──────────────────────────────────────────────────────────────────────
class TestScienceCodeAcceptance:
    """과학과 성취기준 코드가 기존 정규식·모델을 *그대로* 통과함을 동결.

    정규식·모델 개편 불필요가 실측 확인됨(2026-07-02) — 과목 한글 토큰
    `[ㄱ-ㆎ가-힣Ⅰ-ⅿ]{1,6}`이 과목명을 가리지 않는다. 이 테스트는 수용성이
    이후 변경으로 *후퇴*하지 않도록 회귀만 잠근다(정규식 변경 자체는 금지).
    """

    @pytest.mark.parametrize(
        "code",
        [
            "[12물리01-01]",  # 고교 물리학 (A형식)
            "[10통과1-01-01]",  # 고1 통합과학1 (B형식 — 과목 숫자 접미)
            "[12화학02-03]",  # 고교 화학
            "[9과01-05]",  # 중학교 과학
            "[12물리Ⅱ03-02]",  # 로마숫자 과목 접미
        ],
    )
    def test_science_codes_pass_regex(self, code: str) -> None:
        """과학과 5종 코드가 STANDARD_CODE_PATTERN에 매치."""
        assert STANDARD_CODE_PATTERN.match(code) is not None

    def test_science_norm_id_passes_pattern(self) -> None:
        """과학과 norm_id(`2022_12물리_01_01`)가 NORM_ID_PATTERN 통과 — 수학과 비충돌 축."""
        assert NORM_ID_PATTERN.match("2022_12물리_01_01") is not None

    def test_physics_standard_instance_created(self) -> None:
        """물리학 성취기준으로 `AchievementStandard` 생성 성공 — 모델 개편 불필요 증명."""
        std = AchievementStandard(
            **_std_kwargs(
                norm_id="2022_12물리_01_01",
                code="[12물리01-01]",
                grade_band="고등학교",
                school_type="고등학교",
                subject="물리학Ⅰ",
                domain="역학과 에너지",
                statement="물체의 운동을 시간·변위·속도·가속도로 기술한다.",
            )  # type: ignore[arg-type]
        )
        assert std.subject == "물리학Ⅰ"
        assert std.norm_id == "2022_12물리_01_01"
        assert std.code == "[12물리01-01]"
