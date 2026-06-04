"""deletion audit table

슬라이스 57 — GDPR 삭제 감사 로그. 본인 리소스 삭제(slice 51~53)의 *부모 삭제 이벤트*를
append-only로 기록(언제·누가·무엇 — 콘텐츠는 저장 안 함, 메타만). user_id는 **FK 아님**
(사용자 삭제돼도 감사 잔존). resource_type은 String(32)(네이티브 PG enum 미생성).

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-06-04 01:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d4e5f6a7b8c9"
down_revision: str | None = "c3d4e5f6a7b8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "deletion_audit",
        sa.Column(
            "audit_id",
            sa.Uuid(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("resource_type", sa.String(length=32), nullable=False),
        sa.Column("resource_id", sa.Uuid(), nullable=False),
        sa.Column(
            "deleted_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("audit_id", name=op.f("pk_deletion_audit")),
    )


def downgrade() -> None:
    op.drop_table("deletion_audit")
