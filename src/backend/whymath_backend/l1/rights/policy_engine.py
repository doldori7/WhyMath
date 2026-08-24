"""Rights Policy Engine (LIC-01).

콘텐츠에 연결된 권리 정책(`RightsEntity`)과 요청 행위(`PermissionAction`)를 받아
기계적으로 판정(`RightsDecision`)을 내린다.

설계 원칙:
- fail-closed: 권리 미확인(`UNKNOWN`/`None`)은 `REVIEW_REQUIRED` 또는 `DENY`.
- conservative merge: 복수 권리가 충돌하면 가장 제한적인 결정을 따른다.
- 조건부 정책(`conditions`)은 요청 컨텍스트(country/user_type/subscription_tier)와
  매칭되어야 한다.
- 유효기간(`valid_from`/`valid_until`)은 현재 시각 기준으로 검사한다.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from whymath_backend.l1.rights.permission_map import (
    license_attributes,
    license_to_permission_set,
)
from whymath_backend.schema.enums import (
    LicenseType,
    PermissionAction,
    RightsDecision,
    RightsReviewStatus,
)
from whymath_backend.schema.rights import (
    RightsCheckResponse,
    RightsEntity,
    RightsHolderEntity,
    SourceEntity,
)

__all__ = [
    "evaluate_license",
    "check_content_rights",
    "DecisionPriority",
]


class DecisionPriority:
    """보수적 병합을 위한 판정 우선순위(높을수록 제한적)."""

    _PRIORITY: dict[RightsDecision, int] = {
        RightsDecision.DENY: 100,
        RightsDecision.REVIEW_REQUIRED: 80,
        RightsDecision.ALLOW_WITH_RESTRICTIONS: 60,
        RightsDecision.ALLOW_WITH_ATTRIBUTION: 40,
        RightsDecision.ALLOW: 20,
    }

    @classmethod
    def get(cls, decision: RightsDecision) -> int:
        return cls._PRIORITY.get(decision, 0)

    @classmethod
    def worst(cls, decisions: list[RightsDecision]) -> RightsDecision:
        if not decisions:
            return RightsDecision.REVIEW_REQUIRED
        return max(decisions, key=lambda d: cls.get(d))


def _is_expired(
    rights: RightsEntity,
    now: datetime,
) -> bool:
    """유효기간을 초과했거나 아직 시작되지 않은 권리를 식별한다."""
    if rights.valid_from is not None and now < rights.valid_from:
        return True
    if rights.valid_until is not None and now > rights.valid_until:
        return True
    return False


def _conditions_match(
    conditions: dict[str, Any] | None,
    context: dict[str, Any] | None,
) -> bool:
    """조건부 정책이 요청 컨텍스트를 만족하는지 확인한다.

    현재 지원하는 조건:
      - country: list[str] | str
      - user_type: list[str] | str
      - subscription_tier: list[str] | str
    """
    if not conditions:
        return True
    if not context:
        context = {}

    for key in ("country", "user_type", "subscription_tier"):
        allowed = conditions.get(key)
        if allowed is None:
            continue
        requested = context.get(key)
        if requested is None:
            return False
        allowed_values = allowed if isinstance(allowed, list) else [allowed]
        if requested not in allowed_values:
            return False
    return True


def _license_decision(
    rights: RightsEntity,
    action: PermissionAction,
) -> tuple[RightsDecision, str]:
    """개별 RightsEntity에 대해 라이선스 코드와 행위로 판정한다."""
    permission_set = license_to_permission_set(rights.license_code)
    allowed = permission_set.allows(action)

    if rights.license_code in (LicenseType.UNKNOWN, LicenseType.RESTRICTED):
        if rights.license_code == LicenseType.RESTRICTED:
            return RightsDecision.DENY, "LICENSE_RESTRICTED"
        return RightsDecision.REVIEW_REQUIRED, "LICENSE_UNKNOWN"

    if allowed is None:
        return RightsDecision.REVIEW_REQUIRED, "LICENSE_UNCLEAR_ACTION"

    if not allowed:
        return RightsDecision.DENY, "LICENSE_PROHIBITS_ACTION"

    return RightsDecision.ALLOW, "LICENSE_ALLOWS_ACTION"


def evaluate_license(
    rights: RightsEntity,
    action: PermissionAction,
) -> RightsCheckResponse:
    """단일 RightsEntity를 라이선스-행위 단위로 평가한다.

    조건부 정책이나 유효기간은 별도의 컨텍스트 평가 없이 단순 라이선스 의미만 반영.
    """
    decision, reason = _license_decision(rights, action)
    attribution_required, share_alike = license_attributes(rights.license_code)
    if decision is RightsDecision.ALLOW and attribution_required:
        decision = RightsDecision.ALLOW_WITH_ATTRIBUTION

    return RightsCheckResponse(
        content_type="",
        content_id=rights.rights_id,
        action=action,
        decision=decision,
        reason_code=reason,
        rights_id=rights.rights_id,
        attribution=None,
        conditions=rights.conditions,
        share_alike=share_alike,
    )


def check_content_rights(
    content_type: str,
    content_id: Any,  # UUID 또는 uuid.UUID 호환 객체
    rights_list: list[RightsEntity],
    action: PermissionAction,
    sources: list[SourceEntity] | None = None,
    holders: dict[Any, RightsHolderEntity] | None = None,
    request_context: dict[str, Any] | None = None,
    now: datetime | None = None,
) -> RightsCheckResponse:
    """콘텐츠에 연결된 권리 정책들을 종합해 판정한다.

    복수 권리가 연결된 경우 가장 제한적인 결정(보수적 병합)을 따른다.
    """
    if now is None:
        now = datetime.now(timezone.utc)
    if sources is None:
        sources = []
    if holders is None:
        holders = {}

    if not rights_list:
        return RightsCheckResponse(
            content_type=content_type,
            content_id=content_id,
            action=action,
            decision=RightsDecision.REVIEW_REQUIRED,
            reason_code="NO_RIGHTS_LINKED",
            rights_id=None,
            attribution=None,
            conditions=None,
            share_alike=False,
        )

    decisions: list[RightsDecision] = []
    reasons: list[str] = []
    effective_rights: RightsEntity | None = None
    any_attribution_required = False
    any_share_alike = False

    for rights in rights_list:
        # 1) 검수/분쟁 상태
        if rights.review_status is RightsReviewStatus.DISPUTED:
            decisions.append(RightsDecision.DENY)
            reasons.append("RIGHTS_DISPUTED")
            continue
        if rights.review_status is RightsReviewStatus.EXPIRED:
            decisions.append(RightsDecision.DENY)
            reasons.append("RIGHTS_EXPIRED_STATUS")
            continue
        if rights.review_status in (
            RightsReviewStatus.UNVERIFIED,
            RightsReviewStatus.REVIEW_REQUIRED,
        ):
            # 미검증 상태라도 라이선스가 충분히 자유로우면 허용할 수 있지만,
            # MVP에서는 fail-closed로 검수 요구.
            decisions.append(RightsDecision.REVIEW_REQUIRED)
            reasons.append("REVIEW_STATUS_UNVERIFIED")
            continue
        if rights.review_status is RightsReviewStatus.RESTRICTED:
            decisions.append(RightsDecision.DENY)
            reasons.append("REVIEW_STATUS_RESTRICTED")
            continue

        # 2) 유효기간
        if _is_expired(rights, now):
            decisions.append(RightsDecision.DENY)
            reasons.append("RIGHTS_EXPIRED")
            continue

        # 3) 조건부 정책
        if not _conditions_match(rights.conditions, request_context):
            decisions.append(RightsDecision.ALLOW_WITH_RESTRICTIONS)
            reasons.append("CONDITIONS_NOT_MET")
            continue

        # 4) 라이선스-행위 판정
        decision, reason = _license_decision(rights, action)
        attribution_required, share_alike = license_attributes(rights.license_code)

        if decision is RightsDecision.ALLOW and attribution_required:
            decision = RightsDecision.ALLOW_WITH_ATTRIBUTION

        # 5) 보수적 병합에 참여
        decisions.append(decision)
        reasons.append(reason)
        any_attribution_required = any_attribution_required or attribution_required
        any_share_alike = any_share_alike or share_alike
        if effective_rights is None:
            effective_rights = rights

    final_decision = DecisionPriority.worst(decisions)
    final_reason = reasons[decisions.index(final_decision)]

    # 병합 후 출처 표시 의무가 남아 있으면 최종 결정을 상향 보정
    if (
        final_decision in (RightsDecision.ALLOW, RightsDecision.ALLOW_WITH_RESTRICTIONS)
        and any_attribution_required
    ):
        final_decision = RightsDecision.ALLOW_WITH_ATTRIBUTION

    return RightsCheckResponse(
        content_type=content_type,
        content_id=content_id,
        action=action,
        decision=final_decision,
        reason_code=final_reason,
        rights_id=effective_rights.rights_id if effective_rights else None,
        attribution=None,  # Gateway/계층에서 `build_attribution()`으로 채움
        conditions=effective_rights.conditions if effective_rights else None,
        share_alike=any_share_alike,
    )
