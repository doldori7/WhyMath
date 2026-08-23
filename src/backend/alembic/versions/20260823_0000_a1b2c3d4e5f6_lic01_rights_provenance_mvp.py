# ruff: noqa: E501
"""LIC-01 Rights & Provenance Infrastructure MVP — 테이블·enum 생성.

EOS 42번 모듈에 해당하는 Source Registry + Rights Registry의 영속 레이어를 추가한다.
Content-Source/Rights를 N:M으로 분리하고, License를 Permission primitive(JSONB)로
정규화해 기계적 권리 판정을 지원한다.

Revision ID: a1b2c3d4e5f6
Revises: 374fb620de9e
Create Date: 2026-08-23 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: str | None = "374fb620de9e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── 1) 기존 license_enum 확장 ─────────────────────────────────────────
    _add_license_enum_values(
        [
            "KOGL_0",
            "KOGL_1",
            "KOGL_2",
            "KOGL_3",
            "KOGL_4",
            "CC0",
            "CC_BY",
            "CC_BY_SA",
            "CC_BY_NC",
            "CC_BY_ND",
            "CC_BY_NC_SA",
            "CC_BY_NC_ND",
            "INTERNAL_OWNED",
            "CONTRACT_LICENSED",
            "DIRECT_PERMISSION",
            "UNKNOWN",
            "RESTRICTED",
        ]
    )

    # ── 2) 신규 enum type 생성 ─────────────────────────────────────────────
    op.execute(
        "CREATE TYPE source_authority_enum AS ENUM "
        "('OFFICIAL', 'VERIFIED', 'SECONDARY', 'USER_REPORTED', 'UNKNOWN')"
    )
    op.execute(
        "CREATE TYPE rights_review_status_enum AS ENUM "
        "('UNVERIFIED', 'VERIFIED', 'REVIEW_REQUIRED', 'APPROVED', 'RESTRICTED', 'DISPUTED', 'EXPIRED')"
    )
    op.execute(
        "CREATE TYPE derivation_type_enum AS ENUM "
        "('DERIVED_FROM', 'TRANSLATED_FROM', 'ADAPTED_FROM', 'SUMMARIZED_FROM', "
        "'GENERATED_FROM', 'PARAMETERIZED_FROM', 'EXCERPTED_FROM', 'COMBINED_FROM')"
    )

    # ── 3) source_entity 테이블 ──────────────────────────────────────────
    op.create_table(
        "source_entity",
        sa.Column(
            "source_id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column("source_type", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("publisher", sa.String(length=256), nullable=True),
        sa.Column("creator", sa.String(length=256), nullable=True),
        sa.Column("original_url", sa.String(length=2048), nullable=True),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("publication_date", sa.String(length=32), nullable=True),
        sa.Column("jurisdiction", sa.String(length=8), nullable=True),
        sa.Column("source_hash", sa.String(length=128), nullable=True),
        sa.Column("archive_uri", sa.String(length=2048), nullable=True),
        sa.Column(
            "source_authority",
            postgresql.ENUM(
                "OFFICIAL",
                "VERIFIED",
                "SECONDARY",
                "USER_REPORTED",
                "UNKNOWN",
                name="source_authority_enum",
                create_type=False,
            ),
            nullable=True,
        ),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="verified"),
        sa.Column("extra", postgresql.JSONB(none_as_null=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True
        ),
        sa.PrimaryKeyConstraint("source_id"),
    )
    op.create_index("idx_source_type", "source_entity", ["source_type"])
    op.create_index("idx_source_hash", "source_entity", ["source_hash"])

    # ── 4) rights_holder 테이블 ──────────────────────────────────────────
    op.create_table(
        "rights_holder",
        sa.Column(
            "holder_id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column("entity_type", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.Column("country", sa.String(length=8), nullable=True),
        sa.Column(
            "aliases",
            sa.ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::text[]"),
        ),
        sa.Column("contact", sa.String(length=512), nullable=True),
        sa.Column("extra", postgresql.JSONB(none_as_null=True), nullable=True),
        sa.PrimaryKeyConstraint("holder_id"),
    )
    op.create_index("idx_rights_holder_name", "rights_holder", ["name"])

    # ── 5) rights_entity 테이블 ────────────────────────────────────────────
    op.create_table(
        "rights_entity",
        sa.Column(
            "rights_id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column(
            "license_code",
            postgresql.ENUM(
                "PUBLIC_DOMAIN",
                "KOGL_0",
                "KOGL_1",
                "KOGL_2",
                "KOGL_3",
                "KOGL_4",
                "CC0",
                "CC_BY",
                "CC_BY_SA",
                "CC_BY_NC",
                "CC_BY_ND",
                "CC_BY_NC_SA",
                "CC_BY_NC_ND",
                "INTERNAL_OWNED",
                "WHYMATH_GENERATED",
                "USER_GENERATED",
                "AIHUB_OPEN",
                "CONTRACT_LICENSED",
                "DIRECT_PERMISSION",
                "THIRD_PARTY_LICENSED",
                "UNKNOWN",
                "RESTRICTED",
                "EBS_LICENSED",
                name="license_enum",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "copyright_status", sa.String(length=32), nullable=False, server_default="copyrighted"
        ),
        sa.Column("holder_id", sa.Uuid(), sa.ForeignKey("rights_holder.holder_id"), nullable=True),
        sa.Column(
            "permissions",
            postgresql.JSONB(none_as_null=True),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("attribution_required", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("share_alike", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("conditions", postgresql.JSONB(none_as_null=True), nullable=True),
        sa.Column(
            "review_status",
            postgresql.ENUM(
                "UNVERIFIED",
                "VERIFIED",
                "REVIEW_REQUIRED",
                "APPROVED",
                "RESTRICTED",
                "DISPUTED",
                "EXPIRED",
                name="rights_review_status_enum",
                create_type=False,
            ),
            nullable=False,
            server_default="UNVERIFIED",
        ),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True
        ),
        sa.PrimaryKeyConstraint("rights_id"),
    )
    op.create_index("idx_rights_license", "rights_entity", ["license_code"])
    op.create_index("idx_rights_valid_until", "rights_entity", ["valid_until"])
    op.create_index("idx_rights_review_status", "rights_entity", ["review_status"])

    # ── 6) content_source N:M ──────────────────────────────────────────────
    op.create_table(
        "content_source",
        sa.Column("content_type", sa.String(length=64), nullable=False),
        sa.Column("content_id", sa.Uuid(), nullable=False),
        sa.Column("source_id", sa.Uuid(), sa.ForeignKey("source_entity.source_id"), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False, server_default="primary"),
        sa.Column("original_reference", postgresql.JSONB(none_as_null=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True
        ),
        sa.PrimaryKeyConstraint("content_type", "content_id", "source_id"),
    )
    op.create_index("idx_content_source_lookup", "content_source", ["content_type", "content_id"])
    op.create_index("idx_content_source_source", "content_source", ["source_id"])

    # ── 7) content_rights N:M ──────────────────────────────────────────────
    op.create_table(
        "content_rights",
        sa.Column("content_type", sa.String(length=64), nullable=False),
        sa.Column("content_id", sa.Uuid(), nullable=False),
        sa.Column("rights_id", sa.Uuid(), sa.ForeignKey("rights_entity.rights_id"), nullable=False),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("applies_to_fragment", sa.String(length=128), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True
        ),
        sa.PrimaryKeyConstraint("content_type", "content_id", "rights_id"),
    )
    op.create_index("idx_content_rights_lookup", "content_rights", ["content_type", "content_id"])
    op.create_index("idx_content_rights_rights", "content_rights", ["rights_id"])

    # ── 8) derivation_edge ───────────────────────────────────────────────
    op.create_table(
        "derivation_edge",
        sa.Column(
            "edge_id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column("from_content_type", sa.String(length=64), nullable=False),
        sa.Column("from_content_id", sa.Uuid(), nullable=False),
        sa.Column("to_content_type", sa.String(length=64), nullable=False),
        sa.Column("to_content_id", sa.Uuid(), nullable=False),
        sa.Column(
            "derivation_type",
            postgresql.ENUM(
                "DERIVED_FROM",
                "TRANSLATED_FROM",
                "ADAPTED_FROM",
                "SUMMARIZED_FROM",
                "GENERATED_FROM",
                "PARAMETERIZED_FROM",
                "EXCERPTED_FROM",
                "COMBINED_FROM",
                name="derivation_type_enum",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("provenance_id", sa.Uuid(), nullable=True),
        sa.Column("edge_metadata", postgresql.JSONB(none_as_null=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True
        ),
        sa.PrimaryKeyConstraint("edge_id"),
    )
    op.create_index(
        "idx_derivation_from", "derivation_edge", ["from_content_type", "from_content_id"]
    )
    op.create_index("idx_derivation_to", "derivation_edge", ["to_content_type", "to_content_id"])


def downgrade() -> None:
    # 테이블 역순 삭제
    op.drop_index("idx_derivation_to", table_name="derivation_edge")
    op.drop_index("idx_derivation_from", table_name="derivation_edge")
    op.drop_table("derivation_edge")

    op.drop_index("idx_content_rights_rights", table_name="content_rights")
    op.drop_index("idx_content_rights_lookup", table_name="content_rights")
    op.drop_table("content_rights")

    op.drop_index("idx_content_source_source", table_name="content_source")
    op.drop_index("idx_content_source_lookup", table_name="content_source")
    op.drop_table("content_source")

    op.drop_index("idx_rights_review_status", table_name="rights_entity")
    op.drop_index("idx_rights_valid_until", table_name="rights_entity")
    op.drop_index("idx_rights_license", table_name="rights_entity")
    op.drop_table("rights_entity")

    op.drop_index("idx_rights_holder_name", table_name="rights_holder")
    op.drop_table("rights_holder")

    op.drop_index("idx_source_hash", table_name="source_entity")
    op.drop_index("idx_source_type", table_name="source_entity")
    op.drop_table("source_entity")

    # 신규 enum type 삭제
    op.execute("DROP TYPE IF EXISTS derivation_type_enum CASCADE")
    op.execute("DROP TYPE IF EXISTS rights_review_status_enum CASCADE")
    op.execute("DROP TYPE IF EXISTS source_authority_enum CASCADE")
    # license_enum 값 제거는 PostgreSQL에서 직접 지원하지 않으므로 생략.


def _add_license_enum_values(values: list[str]) -> None:
    """license_enum에 값이 없을 때만 추가(재실행/중단 안전)."""
    for value in values:
        op.execute(f"""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_enum e
                    JOIN pg_type t ON e.enumtypid = t.oid
                    WHERE t.typname = 'license_enum' AND e.enumlabel = '{value}'
                ) THEN
                    ALTER TYPE license_enum ADD VALUE '{value}';
                END IF;
            END $$;
            """)
