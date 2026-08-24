"""Attribution 자동 생성 단위 테스트."""

from __future__ import annotations

from whymath_backend.l1.rights.attribution import (
    build_attribution,
    build_attribution_from_template,
    format_license_name,
)
from whymath_backend.schema.enums import LicenseType
from whymath_backend.schema.rights import (
    AttributionTemplate,
    RightsEntity,
    RightsHolderEntity,
    SourceEntity,
)


class TestFormatLicenseName:
    def test_kogl_1_name(self) -> None:
        assert "공공누리" in format_license_name(LicenseType.KOGL_1)

    def test_cc_by_name(self) -> None:
        assert format_license_name(LicenseType.CC_BY) == "CC BY"


class TestBuildAttributionFromTemplate:
    def test_kogl_template(self) -> None:
        template = AttributionTemplate(
            title="2022 개정 수학과 교육과정",
            creator="교육부",
            source_url="https://example.gov",
            license_code=LicenseType.KOGL_1,
            year=2022,
        )
        result = build_attribution_from_template(template)
        assert "교육부" in result
        assert "2022 개정 수학과 교육과정" in result
        assert "공공누리" in result
        assert "2022" in result


class TestBuildAttribution:
    def test_internal_owned(self) -> None:
        rights = RightsEntity(license_code=LicenseType.INTERNAL_OWNED)
        result = build_attribution(None, rights)
        assert result == "출처: WhyMath (자체 생성)"

    def test_kogl_with_source_and_holder(self) -> None:
        source = SourceEntity(
            source_type="public_institution",
            title="2022 개정 수학과 교육과정",
            publisher="교육부",
            original_url="https://example.gov",
            publication_date="2022-12-22",
        )
        rights = RightsEntity(license_code=LicenseType.KOGL_1)
        holder = RightsHolderEntity(entity_type="organization", name="교육부")
        result = build_attribution(source, rights, holder)
        assert result.startswith("출처:")
        assert "교육부" in result
        assert "공공누리" in result
        assert "example.gov" in result

    def test_cc_by_nc_nd(self) -> None:
        source = SourceEntity(
            source_type="website",
            title="수학 예제",
            creator="홍길동",
        )
        rights = RightsEntity(license_code=LicenseType.CC_BY_NC_ND)
        result = build_attribution(source, rights)
        assert "홍길동" in result
        assert "CC BY-NC-ND" in result

    def test_aihub_open_includes_conditions(self) -> None:
        source = SourceEntity(
            source_type="dataset",
            title="AIHub 수학 데이터",
            publisher="AIHub",
        )
        rights = RightsEntity(license_code=LicenseType.AIHUB_OPEN)
        result = build_attribution(source, rights)
        assert "AIHub" in result
        assert "국외반출" in result
        assert "재판매금지" in result

    def test_no_source(self) -> None:
        rights = RightsEntity(license_code=LicenseType.KOGL_1)
        result = build_attribution(None, rights)
        assert result == "출처: 공공누리 제1유형(출처표시)"

    def test_no_rights(self) -> None:
        result = build_attribution(None, None)
        assert result == "출처 정보 없음"
