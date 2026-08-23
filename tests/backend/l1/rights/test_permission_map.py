"""LicenseType → PermissionSet 정적 매핑 단위 테스트."""

from __future__ import annotations

import pytest

from whymath_backend.schema.enums import LicenseType, PermissionAction
from whymath_backend.schema.rights import PermissionSet


@pytest.mark.parametrize(
    "license_type",
    [
        LicenseType.PUBLIC_DOMAIN,
        LicenseType.KOGL_0,
        LicenseType.KOGL_1,
        LicenseType.KOGL_2,
        LicenseType.KOGL_3,
        LicenseType.KOGL_4,
        LicenseType.CC0,
        LicenseType.CC_BY,
        LicenseType.CC_BY_SA,
        LicenseType.CC_BY_NC,
        LicenseType.CC_BY_ND,
        LicenseType.CC_BY_NC_SA,
        LicenseType.CC_BY_NC_ND,
        LicenseType.INTERNAL_OWNED,
        LicenseType.WHYMATH_GENERATED,
        LicenseType.USER_GENERATED,
        LicenseType.AIHUB_OPEN,
        LicenseType.CONTRACT_LICENSED,
        LicenseType.DIRECT_PERMISSION,
        LicenseType.THIRD_PARTY_LICENSED,
        LicenseType.UNKNOWN,
        LicenseType.RESTRICTED,
    ],
)
def test_every_license_type_has_mapping(license_type: LicenseType) -> None:
    """모든 LicenseType이 PermissionSet 매핑을 가진다."""
    from whymath_backend.l1.rights.permission_map import license_to_permission_set

    ps = license_to_permission_set(license_type)
    assert isinstance(ps, PermissionSet)


def test_unknown_is_fail_closed() -> None:
    """UNKNOWN은 모든 권한이 None(미확인)이어야 한다."""
    from whymath_backend.l1.rights.permission_map import (
        UNKNOWN_PERMISSIONS,
        license_to_permission_set,
    )

    ps = license_to_permission_set(LicenseType.UNKNOWN)
    assert ps == UNKNOWN_PERMISSIONS
    for action in PermissionAction:
        assert ps.allows(action) is None


def test_restricted_is_all_false() -> None:
    """RESTRICTED은 모든 권한이 False여야 한다."""
    from whymath_backend.l1.rights.permission_map import (
        RESTRICTED_PERMISSIONS,
        license_to_permission_set,
    )

    ps = license_to_permission_set(LicenseType.RESTRICTED)
    assert ps == RESTRICTED_PERMISSIONS
    for action in PermissionAction:
        assert ps.allows(action) is False


def test_kogl_1_allows_display_and_modification() -> None:
    """KOGL_1은 표시/수정/상업 이용을 허용한다."""
    from whymath_backend.l1.rights.permission_map import license_to_permission_set

    ps = license_to_permission_set(LicenseType.KOGL_1)
    assert ps.display is True
    assert ps.modify is True
    assert ps.commercial_use is True


def test_kogl_2_prohibits_commercial_use() -> None:
    """KOGL_2는 상업적 이용을 금지한다."""
    from whymath_backend.l1.rights.permission_map import license_to_permission_set

    ps = license_to_permission_set(LicenseType.KOGL_2)
    assert ps.display is True
    assert ps.commercial_use is False


def test_kogl_3_prohibits_modification() -> None:
    """KOGL_3은 변경(수정·번역)을 금지한다."""
    from whymath_backend.l1.rights.permission_map import license_to_permission_set

    ps = license_to_permission_set(LicenseType.KOGL_3)
    assert ps.display is True
    assert ps.modify is False
    assert ps.translate is False


def test_cc_by_nc_nd_is_most_restrictive_cc() -> None:
    """CC BY-NC-ND는 상업/변경/파생을 모두 금지한다."""
    from whymath_backend.l1.rights.permission_map import license_to_permission_set

    ps = license_to_permission_set(LicenseType.CC_BY_NC_ND)
    assert ps.display is True
    assert ps.commercial_use is False
    assert ps.modify is False
    assert ps.redistribute is True  # CC는 재배포는 허용


def test_internal_owned_is_fully_allowed() -> None:
    """WhyMath 내부 보유 콘텐츠는 AI 학습까지 허용한다."""
    from whymath_backend.l1.rights.permission_map import license_to_permission_set

    ps = license_to_permission_set(LicenseType.INTERNAL_OWNED)
    assert ps.ai_training is True
    assert ps.rag_index is True
    assert ps.ai_context is True


def test_user_generated_prohibits_commercial_and_ai_training() -> None:
    """사용자 자작은 상업/AI 학습/재배포를 금지한다."""
    from whymath_backend.l1.rights.permission_map import license_to_permission_set

    ps = license_to_permission_set(LicenseType.USER_GENERATED)
    assert ps.display is True
    assert ps.commercial_use is False
    assert ps.ai_training is False
    assert ps.redistribute is False


def test_aihub_open_allows_commercial_but_not_resale_export() -> None:
    """AIHub 공개 데이터셋은 상업·AI 학습은 허용하되 재판매/국외반출은 금지한다."""
    from whymath_backend.l1.rights.permission_map import license_to_permission_set

    ps = license_to_permission_set(LicenseType.AIHUB_OPEN)
    assert ps.commercial_use is True
    assert ps.ai_training is True
    assert ps.redistribute is False
    assert ps.export is False


def test_license_attributes_for_attribution() -> None:
    """KOGL/CC/AIHub 등 외부 라이선스는 출처 표시가 필요하고,
    CC Share-Alike 라이선스는 share_alike=True다."""
    from whymath_backend.l1.rights.permission_map import license_attributes

    assert license_attributes(LicenseType.KOGL_1) == (True, False)
    assert license_attributes(LicenseType.CC0) == (False, False)
    assert license_attributes(LicenseType.CC_BY_SA) == (True, True)
    assert license_attributes(LicenseType.CC_BY_NC_SA) == (True, True)
