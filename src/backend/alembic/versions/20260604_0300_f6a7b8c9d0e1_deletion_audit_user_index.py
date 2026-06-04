"""deletion_audit user index

슬라이스 60 — `list_my_deletions`(slice 58: `WHERE user_id ORDER BY deleted_at DESC`) 접근
패턴 인덱스. `learning_session.idx_session_user`·`dialogue.idx_dialogue_user`와 동형
(`user_id`, time `DESC`). append-only 감사 테이블이 커질수록 user 스코핑+최신순 조회를
seq scan → index scan으로(성능·정합).

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-06-04 03:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f6a7b8c9d0e1"
down_revision: str | None = "e5f6a7b8c9d0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "idx_deletion_audit_user",
        "deletion_audit",
        ["user_id", sa.literal_column("deleted_at DESC")],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_deletion_audit_user", table_name="deletion_audit")
