"""assessment user index

슬라이스 61 — `list_my_assessments`(`WHERE user_id ORDER BY started_at DESC`) 접근 패턴 인덱스.
`learning_session.idx_session_user`·`dialogue.idx_dialogue_user`와 동형 — slice 60에서 발견한
parity 갭(세 /me 도메인 중 assessment만 user 인덱스 부재) 해소.

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-06-04 04:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a7b8c9d0e1f2"
down_revision: str | None = "f6a7b8c9d0e1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "idx_assessment_user",
        "assessment",
        ["user_id", sa.literal_column("started_at DESC")],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_assessment_user", table_name="assessment")
