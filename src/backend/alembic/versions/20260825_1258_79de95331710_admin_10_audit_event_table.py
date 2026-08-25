"""admin-10 audit_event table

EOS 범용 감사 이벤트 Foundation — `docs/architecture/90_audit_log.md`.
`privacy_audit`/`deletion_audit`과 별도로 두고, 콘텐츠·지식·AI·권한 변경 등의
책임추적을 담당하는 `audit_event` 테이블을 신설한다.

Revision ID: 79de95331710
Revises: fcfdfc277348
Create Date: 2026-08-25 12:58:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "79de95331710"
down_revision: str | None = "fcfdfc277348"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "audit_event",
        sa.Column(
            "audit_event_id",
            sa.Uuid(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("actor_type", sa.String(length=32), nullable=False),
        sa.Column("actor_id", sa.String(length=128), nullable=True),
        sa.Column("actor_role", sa.String(length=64), nullable=True),
        sa.Column("action", sa.String(length=128), nullable=False),
        sa.Column("resource_type", sa.String(length=64), nullable=False),
        sa.Column("resource_id", sa.String(length=128), nullable=False),
        sa.Column("before_version", sa.String(length=64), nullable=True),
        sa.Column("after_version", sa.String(length=64), nullable=True),
        sa.Column("changed_fields", sa.ARRAY(sa.String(length=64)), nullable=True),
        sa.Column("authorization_decision", sa.String(length=32), nullable=True),
        sa.Column("reason_code", sa.String(length=64), nullable=True),
        sa.Column("reason_text", sa.String(length=500), nullable=True),
        sa.Column("request_id", sa.String(length=128), nullable=True),
        sa.Column("trace_id", sa.String(length=128), nullable=True),
        sa.Column("workflow_id", sa.String(length=128), nullable=True),
        sa.Column("source_service", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("metadata", sa.dialects.postgresql.JSONB(none_as_null=True), nullable=True),
        sa.Column("retention_policy_id", sa.String(length=32), nullable=False),
        sa.Column("integrity_hash", sa.String(length=64), nullable=True),
        sa.Column("previous_hash", sa.String(length=64), nullable=True),
        sa.PrimaryKeyConstraint("audit_event_id", name=op.f("pk_audit_event")),
    )
    op.create_index(
        "idx_audit_event_occurred_at",
        "audit_event",
        [sa.literal_column("occurred_at DESC")],
        unique=False,
    )
    op.create_index(
        "idx_audit_event_actor",
        "audit_event",
        ["actor_type", "actor_id", sa.literal_column("occurred_at DESC")],
        unique=False,
    )
    op.create_index(
        "idx_audit_event_action",
        "audit_event",
        ["action", sa.literal_column("occurred_at DESC")],
        unique=False,
    )
    op.create_index(
        "idx_audit_event_resource",
        "audit_event",
        ["resource_type", "resource_id", sa.literal_column("occurred_at DESC")],
        unique=False,
    )
    op.create_index(
        "idx_audit_event_request_id",
        "audit_event",
        ["request_id", sa.literal_column("occurred_at DESC")],
        unique=False,
    )
    op.create_index(
        "idx_audit_event_workflow_id",
        "audit_event",
        ["workflow_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_audit_event_workflow_id", table_name="audit_event")
    op.drop_index("idx_audit_event_request_id", table_name="audit_event")
    op.drop_index("idx_audit_event_resource", table_name="audit_event")
    op.drop_index("idx_audit_event_action", table_name="audit_event")
    op.drop_index("idx_audit_event_actor", table_name="audit_event")
    op.drop_index("idx_audit_event_occurred_at", table_name="audit_event")
    op.drop_table("audit_event")
