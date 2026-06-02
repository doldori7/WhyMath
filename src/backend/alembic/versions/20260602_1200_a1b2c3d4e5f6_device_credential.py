"""device_credential

슬라이스 23 — PgDeviceStore 백킹 테이블. device_id PK + user_id FK + secret_plain
+ revoked + created_at/revoked_at.

Revision ID: a1b2c3d4e5f6
Revises: bb30b816083d
Create Date: 2026-06-02 12:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: str | None = "bb30b816083d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "device_credential",
        sa.Column("device_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("secret_plain", sa.String(length=128), nullable=False),
        sa.Column(
            "revoked",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["user_profile.user_id"],
        ),
        sa.PrimaryKeyConstraint("device_id"),
    )
    op.create_index(
        op.f("ix_device_credential_user_id"),
        "device_credential",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_device_credential_user_id"), table_name="device_credential"
    )
    op.drop_table("device_credential")
