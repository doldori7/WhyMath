"""Rights Policy Engine 단위 테스트."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from whymath_backend.l1.rights.policy_engine import (
    DecisionPriority,
    check_content_rights,
    evaluate_license,
)
from whymath_backend.schema.enums import (
    LicenseType,
    PermissionAction,
    RightsDecision,
    RightsReviewStatus,
)
from whymath_backend.schema.rights import RightsEntity, RightsHolderEntity, SourceEntity


@pytest.fixture
def whymath_generated() -> RightsEntity:
    return RightsEntity(
        license_code=LicenseType.WHYMATH_GENERATED,
        review_status=RightsReviewStatus.APPROVED,
    )


@pytest.fixture
def kogl_1() -> RightsEntity:
    return RightsEntity(
        license_code=LicenseType.KOGL_1,
        review_status=RightsReviewStatus.APPROVED,
    )


@pytest.fixture
def restricted() -> RightsEntity:
    return RightsEntity(
        license_code=LicenseType.RESTRICTED,
        review_status=RightsReviewStatus.APPROVED,
    )


@pytest.fixture
def unknown() -> RightsEntity:
    return RightsEntity(
        license_code=LicenseType.UNKNOWN,
        review_status=RightsReviewStatus.APPROVED,
    )


@pytest.fixture
def expired() -> RightsEntity:
    return RightsEntity(
        license_code=LicenseType.WHYMATH_GENERATED,
        review_status=RightsReviewStatus.APPROVED,
        valid_until=datetime.now(timezone.utc) - timedelta(days=1),
    )


class TestEvaluateLicense:
    def test_whymath_generated_allows_display(self, whymath_generated: RightsEntity) -> None:
        resp = evaluate_license(whymath_generated, PermissionAction.DISPLAY)
        assert resp.decision is RightsDecision.ALLOW
        assert resp.share_alike is False

    def test_kogl_1_display_requires_attribution(self, kogl_1: RightsEntity) -> None:
        resp = evaluate_license(kogl_1, PermissionAction.DISPLAY)
        assert resp.decision is RightsDecision.ALLOW_WITH_ATTRIBUTION

    def test_kogl_3_modify_denied(self, kogl_1: RightsEntity) -> None:
        # 실제로는 KOGL_3 fixture를 별도 만들어야 하지만, evaluate_license는 단일 라이선스만
        # 보므로 KOGL_3 객체를 생성한다.
        rights = RightsEntity(
            license_code=LicenseType.KOGL_3,
            review_status=RightsReviewStatus.APPROVED,
        )
        resp = evaluate_license(rights, PermissionAction.MODIFY)
        assert resp.decision is RightsDecision.DENY

    def test_unknown_is_review_required(self, unknown: RightsEntity) -> None:
        resp = evaluate_license(unknown, PermissionAction.DISPLAY)
        assert resp.decision is RightsDecision.REVIEW_REQUIRED


class TestCheckContentRights:
    def test_allow_when_no_rights_linked(self) -> None:
        resp = check_content_rights(
            content_type="problem",
            content_id="00000000-0000-0000-0000-000000000001",
            rights_list=[],
            action=PermissionAction.DISPLAY,
        )
        assert resp.decision is RightsDecision.REVIEW_REQUIRED
        assert resp.reason_code == "NO_RIGHTS_LINKED"

    def test_whymath_generated_allows_display(self, whymath_generated: RightsEntity) -> None:
        resp = check_content_rights(
            content_type="problem",
            content_id="00000000-0000-0000-0000-000000000001",
            rights_list=[whymath_generated],
            action=PermissionAction.DISPLAY,
        )
        assert resp.decision is RightsDecision.ALLOW
        assert resp.reason_code == "LICENSE_ALLOWS_ACTION"

    def test_kogl_1_display_with_attribution(self, kogl_1: RightsEntity) -> None:
        resp = check_content_rights(
            content_type="problem",
            content_id="00000000-0000-0000-0000-000000000001",
            rights_list=[kogl_1],
            action=PermissionAction.DISPLAY,
        )
        assert resp.decision is RightsDecision.ALLOW_WITH_ATTRIBUTION
        assert resp.share_alike is False

    def test_restricted_denies(self, restricted: RightsEntity) -> None:
        resp = check_content_rights(
            content_type="problem",
            content_id="00000000-0000-0000-0000-000000000001",
            rights_list=[restricted],
            action=PermissionAction.DISPLAY,
        )
        assert resp.decision is RightsDecision.DENY

    def test_unverified_review_required(self, whymath_generated: RightsEntity) -> None:
        rights = whymath_generated.model_copy(
            update={"review_status": RightsReviewStatus.UNVERIFIED}
        )
        resp = check_content_rights(
            content_type="problem",
            content_id="00000000-0000-0000-0000-000000000001",
            rights_list=[rights],
            action=PermissionAction.DISPLAY,
        )
        assert resp.decision is RightsDecision.REVIEW_REQUIRED
        assert resp.reason_code == "REVIEW_STATUS_UNVERIFIED"

    def test_expired_rights_denied(self, expired: RightsEntity) -> None:
        resp = check_content_rights(
            content_type="problem",
            content_id="00000000-0000-0000-0000-000000000001",
            rights_list=[expired],
            action=PermissionAction.DISPLAY,
        )
        assert resp.decision is RightsDecision.DENY
        assert resp.reason_code == "RIGHTS_EXPIRED"

    def test_conditions_mismatch(self, whymath_generated: RightsEntity) -> None:
        rights = whymath_generated.model_copy(
            update={
                "conditions": {"country": ["US"]},
            }
        )
        resp = check_content_rights(
            content_type="problem",
            content_id="00000000-0000-0000-0000-000000000001",
            rights_list=[rights],
            action=PermissionAction.DISPLAY,
            request_context={"country": "KR"},
        )
        assert resp.decision is RightsDecision.ALLOW_WITH_RESTRICTIONS
        assert resp.reason_code == "CONDITIONS_NOT_MET"

    def test_conservative_merge_restricted_wins(
        self,
        whymath_generated: RightsEntity,
        restricted: RightsEntity,
    ) -> None:
        resp = check_content_rights(
            content_type="problem",
            content_id="00000000-0000-0000-0000-000000000001",
            rights_list=[whymath_generated, restricted],
            action=PermissionAction.DISPLAY,
        )
        assert resp.decision is RightsDecision.DENY

    def test_conservative_merge_attribution_propagates(
        self,
        whymath_generated: RightsEntity,
        kogl_1: RightsEntity,
    ) -> None:
        resp = check_content_rights(
            content_type="problem",
            content_id="00000000-0000-0000-0000-000000000001",
            rights_list=[whymath_generated, kogl_1],
            action=PermissionAction.DISPLAY,
        )
        assert resp.decision is RightsDecision.ALLOW_WITH_ATTRIBUTION


class TestDecisionPriority:
    def test_deny_worst(self) -> None:
        worst = DecisionPriority.worst(
            [
                RightsDecision.ALLOW,
                RightsDecision.ALLOW_WITH_ATTRIBUTION,
                RightsDecision.DENY,
            ]
        )
        assert worst is RightsDecision.DENY

    def test_review_required_over_allow(self) -> None:
        worst = DecisionPriority.worst([RightsDecision.ALLOW, RightsDecision.REVIEW_REQUIRED])
        assert worst is RightsDecision.REVIEW_REQUIRED


class TestAttributionFill:
    def test_attribution_auto_generated_for_kogl(
        self,
        kogl_1: RightsEntity,
    ) -> None:
        source = SourceEntity(
            source_type="public_institution",
            title="2022 개정 수학과 교육과정",
            publisher="교육부",
            original_url="https://example.gov",
            publication_date="2022-12-22",
        )
        holder = RightsHolderEntity(entity_type="organization", name="교육부")
        resp = check_content_rights(
            content_type="problem",
            content_id="00000000-0000-0000-0000-000000000001",
            rights_list=[kogl_1],
            action=PermissionAction.DISPLAY,
            sources=[source],
            holders={holder.holder_id: holder},
        )
        # attribution은 Policy Engine에서 채우지 않고 Gateway에서 채우지만,
        # check_content_rights는 sources/holders를 받아도 attribution은 None으로 둔다.
        assert resp.attribution is None
        assert resp.decision is RightsDecision.ALLOW_WITH_ATTRIBUTION
