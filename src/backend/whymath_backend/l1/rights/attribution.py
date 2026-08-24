"""Attribution 자동 생성기 (LIC-01).

라이선스 종류와 출처 메타데이터에 따라 학생 UI/관리자/교사용 출처 문구를
자동 생성한다.
"""

from __future__ import annotations

from whymath_backend.schema.enums import LicenseType
from whymath_backend.schema.rights import (
    AttributionTemplate,
    RightsEntity,
    RightsHolderEntity,
    SourceEntity,
)

__all__ = [
    "build_attribution",
    "build_attribution_from_template",
    "format_license_name",
]


_LICENSE_DISPLAY_NAME: dict[LicenseType, str] = {
    LicenseType.PUBLIC_DOMAIN: "퍼블릭 도메인",
    LicenseType.KOGL_0: "공공누리 제0유형(자유이용)",
    LicenseType.KOGL_1: "공공누리 제1유형(출처표시)",
    LicenseType.KOGL_2: "공공누리 제2유형(출처표시·상업적이용금지)",
    LicenseType.KOGL_3: "공공누리 제3유형(출처표시·변경금지)",
    LicenseType.KOGL_4: "공공누리 제4유형(출처표시·상업적이용금지·변경금지)",
    LicenseType.CC0: "CC0",
    LicenseType.CC_BY: "CC BY",
    LicenseType.CC_BY_SA: "CC BY-SA",
    LicenseType.CC_BY_NC: "CC BY-NC",
    LicenseType.CC_BY_ND: "CC BY-ND",
    LicenseType.CC_BY_NC_SA: "CC BY-NC-SA",
    LicenseType.CC_BY_NC_ND: "CC BY-NC-ND",
    LicenseType.INTERNAL_OWNED: "WhyMath 자체 보유",
    LicenseType.WHYMATH_GENERATED: "WhyMath 자체 생성",
    LicenseType.USER_GENERATED: "사용자 자작",
    LicenseType.AIHUB_OPEN: "AIHub 공개 데이터셋",
    LicenseType.CONTRACT_LICENSED: "계약 라이선스",
    LicenseType.DIRECT_PERMISSION: "개별 이용허락",
    LicenseType.THIRD_PARTY_LICENSED: "제휴 라이선스",
    LicenseType.UNKNOWN: "라이선스 미확인",
    LicenseType.RESTRICTED: "사용 제한",
}


def format_license_name(license_code: LicenseType) -> str:
    """LicenseType을 사람이 읽을 수 있는 한글/영문 이름으로 변환한다."""
    return _LICENSE_DISPLAY_NAME.get(license_code, str(license_code))


def _default_creator(source: SourceEntity, rights: RightsEntity) -> str | None:
    """출처·권리 정보에서 표시용 저작자/기관명을 추출한다."""
    if source.creator:
        return source.creator
    if source.publisher:
        return source.publisher
    if rights.holder_id:
        return "권리자"
    return None


def build_attribution_from_template(template: AttributionTemplate) -> str:
    """AttributionTemplate에서 출처 문구를 생성한다."""
    license_name = format_license_name(template.license_code)
    parts: list[str] = []

    title = template.title.strip()
    creator = (template.creator or "").strip()

    if creator and title:
        parts.append(f"{creator}, 「{title}」")
    elif title:
        parts.append(f"「{title}」")
    elif creator:
        parts.append(creator)

    if template.source_url:
        parts.append(template.source_url)

    license_part = license_name
    if template.year:
        license_part = f"{template.year}, {license_part}"
    parts.append(license_part)

    return " | ".join(parts)


def build_attribution(
    source: SourceEntity | None,
    rights: RightsEntity | None,
    holder: RightsHolderEntity | None = None,
) -> str:
    """Source + Rights + RightsHolder 조합으로 출처 문구를 자동 생성한다.

    - KOGL/CC 계열: 라이선스 표시법에 맞춰 기관명·자료명·URL·라이선스 포함.
    - WhyMath 내부/자체 생성: WhyMath 표기.
    - 사용자 자작/제한/미확인: 최소한의 안내 문구.
    """
    if rights is None:
        return "출처 정보 없음"

    license_code = rights.license_code
    license_name = format_license_name(license_code)

    # 내부/자체 생성
    if license_code in (
        LicenseType.INTERNAL_OWNED,
        LicenseType.WHYMATH_GENERATED,
    ):
        return "출처: WhyMath (자체 생성)"

    # 외부 출처 없음
    if source is None:
        return f"출처: {license_name}"

    title = source.title.strip()
    creator: str | None = None
    if holder is not None:
        creator = holder.name
    if not creator:
        creator = _default_creator(source, rights)

    year_part = ""
    if source.publication_date:
        year = source.publication_date[:4]
        if year.isdigit():
            year_part = f" {year}."

    # KOGL/CC/AIHub 등 외부 라이선스 공통 형식
    source_line = ""
    if creator and title:
        source_line = f"{creator}, 「{title}」"
    elif title:
        source_line = f"「{title}」"
    elif creator:
        source_line = creator

    if source.original_url:
        if source_line:
            source_line = f"{source_line}, {source.original_url}"
        else:
            source_line = source.original_url

    kogl_types = (
        LicenseType.KOGL_1,
        LicenseType.KOGL_2,
        LicenseType.KOGL_3,
        LicenseType.KOGL_4,
    )
    if license_code in kogl_types:
        return f"출처: {source_line}{year_part} {license_name}"

    if license_code in (
        LicenseType.CC0,
        LicenseType.CC_BY,
        LicenseType.CC_BY_SA,
        LicenseType.CC_BY_NC,
        LicenseType.CC_BY_ND,
        LicenseType.CC_BY_NC_SA,
        LicenseType.CC_BY_NC_ND,
    ):
        return f"출처: {source_line}{year_part} {license_name}"

    if license_code == LicenseType.AIHUB_OPEN:
        return (
            f"출처: {source_line}{year_part} AIHub 공개 데이터셋 "
            "(출처표시·국외반출·재판매금지·환수 조건 적용)"
        )

    if license_code == LicenseType.USER_GENERATED:
        creator = creator or "사용자"
        return f"출처: {creator} 제공, {license_name}"

    # 계약/개별 허락/제휴/제한/미확인
    return f"출처: {source_line}{year_part} {license_name}"
