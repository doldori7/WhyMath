"""Rights & Provenance 스키마 계약 단위 테스트."""

from __future__ import annotations

import uuid

import pytest
from pydantic import ValidationError

from whymath_backend.schema.enums import (
    LicenseType,
    PermissionAction,
    RightsDecision,
)
from whymath_backend.schema.rights import (
    AttributionTemplate,
    ContentRightsLink,
    ContentSourceLink,
    DerivationEdge,
    PermissionSet,
    RightsCheckResponse,
    RightsEntity,
)


class TestPermissionSet:
    def test_allows_maps_actions(self) -> None:
        ps = PermissionSet(
            display=True,
            copy_=False,
            modify=None,
        )
        assert ps.allows(PermissionAction.DISPLAY) is True
        assert ps.allows(PermissionAction.COPY) is False
        assert ps.allows(PermissionAction.MODIFY) is None

    def test_alias_populate_by_name(self) -> None:
        """Pydantic alias(copy/print)와 필드명(copy_/print_) 모두 생성 가능해야 한다."""
        by_alias = PermissionSet(copy=True, print=True)
        by_field = PermissionSet(copy_=True, print_=True)
        assert by_alias.copy_ is True
        assert by_field.copy_ is True
        assert by_alias.print_ is True
        assert by_field.print_ is True

    def test_model_dump_uses_field_name(self) -> None:
        ps = PermissionSet(copy_=True, print_=False)
        data = ps.model_dump(by_alias=False)
        assert "copy_" in data
        assert "print_" in data


class TestRightsEntity:
    def test_default_review_status(self) -> None:
        rights = RightsEntity(license_code=LicenseType.UNKNOWN)
        # use_enum_values=True이므로 문자열 값으로 직렬화
        assert rights.review_status == "UNVERIFIED"


class TestRightsCheckResponse:
    def test_share_alike_field(self) -> None:
        resp = RightsCheckResponse(
            content_type="problem",
            content_id=uuid.uuid4(),
            action=PermissionAction.DISPLAY,
            decision=RightsDecision.ALLOW,
            reason_code="TEST",
            share_alike=True,
        )
        assert resp.share_alike is True


class TestContentLinks:
    def test_content_source_link(self) -> None:
        link = ContentSourceLink(
            content_type="problem",
            content_id=uuid.uuid4(),
            source_id=uuid.uuid4(),
            role="primary",
        )
        assert link.role == "primary"

    def test_content_rights_link_fragment(self) -> None:
        link = ContentRightsLink(
            content_type="problem",
            content_id=uuid.uuid4(),
            rights_id=uuid.uuid4(),
            applies_to_fragment="diagram",
        )
        assert link.applies_to_fragment == "diagram"


class TestAttributionTemplate:
    def test_extra_forbidden(self) -> None:
        with pytest.raises(ValidationError):
            AttributionTemplate(
                title="x",
                license_code=LicenseType.CC_BY,
                unknown_field=True,  # type: ignore[arg-type]
            )


class TestDerivationEdge:
    def test_edge_metadata_not_reserved(self) -> None:
        edge = DerivationEdge(
            from_content_type="problem",
            from_content_id=uuid.uuid4(),
            to_content_type="problem",
            to_content_id=uuid.uuid4(),
            derivation_type="GENERATED_FROM",
            edge_metadata={"template": "v1"},
        )
        assert edge.edge_metadata == {"template": "v1"}
