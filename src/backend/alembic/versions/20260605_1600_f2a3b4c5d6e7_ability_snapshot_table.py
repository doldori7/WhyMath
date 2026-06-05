"""ability_snapshot 테이블 (IRT 능력 θ 시계열 적재)

슬라이스 31 — IRT 능력 θ(logit) 성장 곡선을 *적재형*으로 영속한다. `concept_mastery_history`
(BKT 숙달 시계열)와 상보적. surrogate PK `snapshot_id`(gen_random_uuid)·`user_id` 느슨참조
(FK 아님·concept_mastery_history 선례)·`concept_id` null=전 과목 단일 θ·`theta`/`standard_error`
Float·`measured_at` server_default now(). 접근 패턴(본인 시계열·시간순) 인덱스.

Revision ID: f2a3b4c5d6e7
Revises: e1f2a3b4c5d6
Create Date: 2026-06-05 16:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f2a3b4c5d6e7"
down_revision: str | None = "e1f2a3b4c5d6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ability_snapshot",
        sa.Column(
            "snapshot_id",
            sa.Uuid(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("concept_id", sa.Uuid(), nullable=True),
        sa.Column("theta", sa.Float(), nullable=False),
        sa.Column("standard_error", sa.Float(), nullable=True),
        sa.Column("response_count", sa.Integer(), nullable=False),
        sa.Column(
            "measured_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("snapshot_id"),
    )
    op.create_index(
        "idx_ability_snapshot_user",
        "ability_snapshot",
        ["user_id", sa.text("measured_at DESC")],
    )


def downgrade() -> None:
    op.drop_index("idx_ability_snapshot_user", table_name="ability_snapshot")
    op.drop_table("ability_snapshot")
