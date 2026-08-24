"""LicenseType → PermissionSet 정적 매핑 (LIC-01).

라이선스 enum 값을 EOS 정규화 권한 primitive(`PermissionSet`)로 변환한다.
원본 라이선스 문자열을 코드 곳곳에서 해석하지 않고, 이 모듈을 유일한
정규화 지점으로 삼는다.

설계 원칙:
- `UNKNOWN`은 fail-closed: 모든 권한을 `None`(미확인)으로 반환해
  Policy Engine이 `REVIEW_REQUIRED`/`DENY`로 처리하게 한다.
- `RESTRICTED`는 명시적 금지: 모든 권한 `False`.
- KOGL/CC 계열은 공식 조건에 맞춰 `attribution_required=True`.
- Share-Alike 라이선스(CC_BY_SA, CC_BY_NC_SA)는 `share_alike=True`.
- AI 사용권( rag_index / ai_context / ai_training / ... )은 일반 사용권과
  별도 필드로 관리한다.
"""

from __future__ import annotations

from whymath_backend.schema.enums import LicenseType
from whymath_backend.schema.rights import PermissionSet

__all__ = [
    "UNKNOWN_PERMISSIONS",
    "RESTRICTED_PERMISSIONS",
    "PUBLIC_DOMAIN_PERMISSIONS",
    "license_to_permission_set",
    "license_attributes",
]


# ──────────────────────────────────────────────────────────────────────────
# 극단값
# ──────────────────────────────────────────────────────────────────────────
UNKNOWN_PERMISSIONS: PermissionSet = PermissionSet(
    display=None,
    copy_=None,
    redistribute=None,
    modify=None,
    translate=None,
    commercial_use=None,
    download=None,
    print_=None,
    export=None,
    embed=None,
    api_access=None,
    rag_index=None,
    ai_context=None,
    ai_training=None,
    ai_fine_tuning=None,
    ai_evaluation=None,
    ai_synthetic_derivation=None,
)

RESTRICTED_PERMISSIONS: PermissionSet = PermissionSet(
    display=False,
    copy_=False,
    redistribute=False,
    modify=False,
    translate=False,
    commercial_use=False,
    download=False,
    print_=False,
    export=False,
    embed=False,
    api_access=False,
    rag_index=False,
    ai_context=False,
    ai_training=False,
    ai_fine_tuning=False,
    ai_evaluation=False,
    ai_synthetic_derivation=False,
)

PUBLIC_DOMAIN_PERMISSIONS: PermissionSet = PermissionSet(
    display=True,
    copy_=True,
    redistribute=True,
    modify=True,
    translate=True,
    commercial_use=True,
    download=True,
    print_=True,
    export=True,
    embed=True,
    api_access=True,
    rag_index=True,
    ai_context=True,
    ai_training=True,
    ai_fine_tuning=True,
    ai_evaluation=True,
    ai_synthetic_derivation=True,
)


# ──────────────────────────────────────────────────────────────────────────
# KOGL (공공누리)
# ──────────────────────────────────────────────────────────────────────────
_KOGL_0 = PermissionSet(
    display=True,
    copy_=True,
    redistribute=True,
    modify=True,
    translate=True,
    commercial_use=True,
    download=True,
    print_=True,
    export=True,
    embed=True,
    api_access=True,
    rag_index=True,
    ai_context=True,
    ai_training=True,
    ai_fine_tuning=True,
    ai_evaluation=True,
    ai_synthetic_derivation=True,
)

# KOGL 1~4: 공통적으로 출처표시 + 상업/변경 조건만 다름
_KOGL_1 = PermissionSet(
    display=True,
    copy_=True,
    redistribute=True,
    modify=True,
    translate=True,
    commercial_use=True,
    download=True,
    print_=True,
    export=True,
    embed=True,
    api_access=True,
    rag_index=True,
    ai_context=True,
    ai_training=None,  # KOGL 별도 AI 학습 안내를 따름
    ai_fine_tuning=None,
    ai_evaluation=True,
    ai_synthetic_derivation=None,
)

_KOGL_2 = PermissionSet(
    display=True,
    copy_=True,
    redistribute=True,
    modify=True,
    translate=True,
    commercial_use=False,
    download=True,
    print_=True,
    export=True,
    embed=True,
    api_access=True,
    rag_index=True,
    ai_context=True,
    ai_training=None,
    ai_fine_tuning=None,
    ai_evaluation=True,
    ai_synthetic_derivation=None,
)

_KOGL_3 = PermissionSet(
    display=True,
    copy_=True,
    redistribute=True,
    modify=False,
    translate=False,
    commercial_use=True,
    download=True,
    print_=True,
    export=True,
    embed=True,
    api_access=True,
    rag_index=True,
    ai_context=True,
    ai_training=None,
    ai_fine_tuning=None,
    ai_evaluation=True,
    ai_synthetic_derivation=None,
)

_KOGL_4 = PermissionSet(
    display=True,
    copy_=True,
    redistribute=True,
    modify=False,
    translate=False,
    commercial_use=False,
    download=True,
    print_=True,
    export=True,
    embed=True,
    api_access=True,
    rag_index=True,
    ai_context=True,
    ai_training=None,
    ai_fine_tuning=None,
    ai_evaluation=True,
    ai_synthetic_derivation=None,
)


# ──────────────────────────────────────────────────────────────────────────
# Creative Commons
# ──────────────────────────────────────────────────────────────────────────
_CC_BY = PermissionSet(
    display=True,
    copy_=True,
    redistribute=True,
    modify=True,
    translate=True,
    commercial_use=True,
    download=True,
    print_=True,
    export=True,
    embed=True,
    api_access=True,
    rag_index=True,
    ai_context=True,
    ai_training=None,  # CC는 AI 학습권을 명문하지 않음
    ai_fine_tuning=None,
    ai_evaluation=True,
    ai_synthetic_derivation=None,
)

_CC_BY_SA = PermissionSet(
    display=True,
    copy_=True,
    redistribute=True,
    modify=True,
    translate=True,
    commercial_use=True,
    download=True,
    print_=True,
    export=True,
    embed=True,
    api_access=True,
    rag_index=True,
    ai_context=True,
    ai_training=None,
    ai_fine_tuning=None,
    ai_evaluation=True,
    ai_synthetic_derivation=None,
)

_CC_BY_NC = PermissionSet(
    display=True,
    copy_=True,
    redistribute=True,
    modify=True,
    translate=True,
    commercial_use=False,
    download=True,
    print_=True,
    export=True,
    embed=True,
    api_access=True,
    rag_index=True,
    ai_context=True,
    ai_training=None,
    ai_fine_tuning=None,
    ai_evaluation=True,
    ai_synthetic_derivation=None,
)

_CC_BY_ND = PermissionSet(
    display=True,
    copy_=True,
    redistribute=True,
    modify=False,
    translate=False,
    commercial_use=True,
    download=True,
    print_=True,
    export=True,
    embed=True,
    api_access=True,
    rag_index=True,
    ai_context=True,
    ai_training=None,
    ai_fine_tuning=None,
    ai_evaluation=True,
    ai_synthetic_derivation=None,
)

_CC_BY_NC_SA = PermissionSet(
    display=True,
    copy_=True,
    redistribute=True,
    modify=True,
    translate=True,
    commercial_use=False,
    download=True,
    print_=True,
    export=True,
    embed=True,
    api_access=True,
    rag_index=True,
    ai_context=True,
    ai_training=None,
    ai_fine_tuning=None,
    ai_evaluation=True,
    ai_synthetic_derivation=None,
)

_CC_BY_NC_ND = PermissionSet(
    display=True,
    copy_=True,
    redistribute=True,
    modify=False,
    translate=False,
    commercial_use=False,
    download=True,
    print_=True,
    export=True,
    embed=True,
    api_access=True,
    rag_index=True,
    ai_context=True,
    ai_training=None,
    ai_fine_tuning=None,
    ai_evaluation=True,
    ai_synthetic_derivation=None,
)


# ──────────────────────────────────────────────────────────────────────────
# WhyMath / 내부 / 계약
# ──────────────────────────────────────────────────────────────────────────
_INTERNAL_OWNED = PermissionSet(
    display=True,
    copy_=True,
    redistribute=True,
    modify=True,
    translate=True,
    commercial_use=True,
    download=True,
    print_=True,
    export=True,
    embed=True,
    api_access=True,
    rag_index=True,
    ai_context=True,
    ai_training=True,
    ai_fine_tuning=True,
    ai_evaluation=True,
    ai_synthetic_derivation=True,
)

# 자체 생성: WhyMath가 권리 보유. 학생 노출/내부 학습/파생 모두 허용.
_WHYMATH_GENERATED = PermissionSet(
    display=True,
    copy_=True,
    redistribute=True,
    modify=True,
    translate=True,
    commercial_use=True,
    download=True,
    print_=True,
    export=True,
    embed=True,
    api_access=True,
    rag_index=True,
    ai_context=True,
    ai_training=True,
    ai_fine_tuning=True,
    ai_evaluation=True,
    ai_synthetic_derivation=True,
)

# 사용자 자작: 서비스 내 표시/교사 열람 정도만 기본 허용, 상업·AI 학습은 금지.
_USER_GENERATED = PermissionSet(
    display=True,
    copy_=True,
    redistribute=False,
    modify=True,
    translate=True,
    commercial_use=False,
    download=False,
    print_=False,
    export=False,
    embed=False,
    api_access=False,
    rag_index=False,
    ai_context=False,
    ai_training=False,
    ai_fine_tuning=False,
    ai_evaluation=True,
    ai_synthetic_derivation=False,
)

# AIHub 공개 데이터셋: 영리 명문 허용. 단 국외반출/재판매금지/환수 조건은
# `RightsEntity.conditions`에 별도 기록한다.
_AIHUB_OPEN = PermissionSet(
    display=True,
    copy_=True,
    redistribute=False,  # 재판매 금지
    modify=True,
    translate=True,
    commercial_use=True,
    download=True,
    print_=True,
    export=False,  # 국외반출 금지
    embed=True,
    api_access=True,
    rag_index=True,
    ai_context=True,
    ai_training=True,
    ai_fine_tuning=None,  # 명문 허용 여부는 conditions 참조
    ai_evaluation=True,
    ai_synthetic_derivation=None,
)

# 계약 라이선스: 조건이 계약에 따르므로 기본값은 모두 None(검수 필요).
_CONTRACT_LICENSED = UNKNOWN_PERMISSIONS

# 직접 허락: 권리자와의 개별 계약. 일반 사용은 허용하되 AI 학습은 검수 필요.
_DIRECT_PERMISSION = PermissionSet(
    display=True,
    copy_=True,
    redistribute=None,  # 허락 범위에 따름
    modify=None,
    translate=None,
    commercial_use=None,
    download=None,
    print_=None,
    export=None,
    embed=None,
    api_access=None,
    rag_index=None,
    ai_context=None,
    ai_training=None,
    ai_fine_tuning=None,
    ai_evaluation=True,
    ai_synthetic_derivation=None,
)

# 사설 제휴: 계약 조건을 따르므로 기본 unknown.
_THIRD_PARTY_LICENSED = UNKNOWN_PERMISSIONS


_LICENSE_PERMISSION_MAP: dict[LicenseType, PermissionSet] = {
    LicenseType.PUBLIC_DOMAIN: PUBLIC_DOMAIN_PERMISSIONS,
    LicenseType.KOGL_0: _KOGL_0,
    LicenseType.KOGL_1: _KOGL_1,
    LicenseType.KOGL_2: _KOGL_2,
    LicenseType.KOGL_3: _KOGL_3,
    LicenseType.KOGL_4: _KOGL_4,
    LicenseType.CC0: PUBLIC_DOMAIN_PERMISSIONS,
    LicenseType.CC_BY: _CC_BY,
    LicenseType.CC_BY_SA: _CC_BY_SA,
    LicenseType.CC_BY_NC: _CC_BY_NC,
    LicenseType.CC_BY_ND: _CC_BY_ND,
    LicenseType.CC_BY_NC_SA: _CC_BY_NC_SA,
    LicenseType.CC_BY_NC_ND: _CC_BY_NC_ND,
    LicenseType.INTERNAL_OWNED: _INTERNAL_OWNED,
    LicenseType.WHYMATH_GENERATED: _WHYMATH_GENERATED,
    LicenseType.USER_GENERATED: _USER_GENERATED,
    LicenseType.AIHUB_OPEN: _AIHUB_OPEN,
    LicenseType.CONTRACT_LICENSED: _CONTRACT_LICENSED,
    LicenseType.DIRECT_PERMISSION: _DIRECT_PERMISSION,
    LicenseType.THIRD_PARTY_LICENSED: _THIRD_PARTY_LICENSED,
    LicenseType.UNKNOWN: UNKNOWN_PERMISSIONS,
    LicenseType.RESTRICTED: RESTRICTED_PERMISSIONS,
}

# KOGL/CC/AIHub 등 외부 자료는 출처 표시가 필요하다.
_LICENSE_ATTRIBUTION_MAP: dict[LicenseType, bool] = {
    LicenseType.PUBLIC_DOMAIN: False,
    LicenseType.KOGL_0: False,
    LicenseType.KOGL_1: True,
    LicenseType.KOGL_2: True,
    LicenseType.KOGL_3: True,
    LicenseType.KOGL_4: True,
    LicenseType.CC0: False,
    LicenseType.CC_BY: True,
    LicenseType.CC_BY_SA: True,
    LicenseType.CC_BY_NC: True,
    LicenseType.CC_BY_ND: True,
    LicenseType.CC_BY_NC_SA: True,
    LicenseType.CC_BY_NC_ND: True,
    LicenseType.INTERNAL_OWNED: False,
    LicenseType.WHYMATH_GENERATED: False,
    LicenseType.USER_GENERATED: True,
    LicenseType.AIHUB_OPEN: True,
    LicenseType.CONTRACT_LICENSED: True,
    LicenseType.DIRECT_PERMISSION: True,
    LicenseType.THIRD_PARTY_LICENSED: True,
    LicenseType.UNKNOWN: True,
    LicenseType.RESTRICTED: False,
}

# Share-Alike 의무
_LICENSE_SHARE_ALIKE_MAP: dict[LicenseType, bool] = {
    LicenseType.CC_BY_SA: True,
    LicenseType.CC_BY_NC_SA: True,
}


def license_to_permission_set(license_type: LicenseType) -> PermissionSet:
    """LicenseType을 EOS PermissionSet으로 변환한다.

    매핑에 없는 경우(이론상 발생 불가) fail-closed로 UNKNOWN을 반환한다.
    """
    return _LICENSE_PERMISSION_MAP.get(license_type, UNKNOWN_PERMISSIONS)


def license_attributes(license_type: LicenseType) -> tuple[bool, bool]:
    """(attribution_required, share_alike)를 반환한다."""
    return (
        _LICENSE_ATTRIBUTION_MAP.get(license_type, True),
        _LICENSE_SHARE_ALIKE_MAP.get(license_type, False),
    )
