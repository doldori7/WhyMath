"""AchievementStandard lifecycle expansion — official_statement, version, status, etc.

성취기준(AchievementStandard)에 공식 원문 분리(official_statement), EOS 정규화/학생용 표현,
라이프사이클 상태(status), 버전 식별자(version_id), 시행 종료일(effective_to), 管轄/언어
(jurisdiction/language) 컬럼을 추가한다. 기존 `statement`는 하위호환용 deprecated로 유지하고
데이터는 `official_statement`로 복사한다.

Revision ID: b8e76fe238d0
Revises: e07b1324d1d4
Create Date: 2026-08-24 02:08:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b8e76fe238d0"
down_revision: str | None = "e07b1324d1d4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add lifecycle columns + populate official_statement from statement."""
    op.add_column(
        "achievement_standard",
        sa.Column("official_statement", sa.Text(), nullable=False, server_default=""),
    )
    op.add_column(
        "achievement_standard",
        sa.Column("normalized_statement", sa.Text(), nullable=True),
    )
    op.add_column(
        "achievement_standard",
        sa.Column("learner_friendly_statement", sa.Text(), nullable=True),
    )
    op.add_column(
        "achievement_standard",
        sa.Column(
            "status",
            sa.String(length=30),
            nullable=False,
            server_default=sa.text("'published'"),
        ),
    )
    op.add_column(
        "achievement_standard",
        sa.Column(
            "version_id",
            sa.Uuid(),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
    )
    op.add_column(
        "achievement_standard",
        sa.Column("effective_to", sa.Date(), nullable=True),
    )
    op.add_column(
        "achievement_standard",
        sa.Column(
            "jurisdiction",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'KR'"),
        ),
    )
    op.add_column(
        "achievement_standard",
        sa.Column(
            "language",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'ko-KR'"),
        ),
    )

    # 기존 데이터: statement → official_statement 복사
    op.execute("UPDATE achievement_standard SET official_statement = statement")

    # 기존 데이터에 안정적인 version_id 부여(이미 server_default로 채워졌지만 명시적 마이그레이션).
    op.execute(
        "UPDATE achievement_standard SET version_id = gen_random_uuid() " "WHERE version_id IS NULL"
    )

    # 인덱스 추가
    op.create_index(
        "idx_achievement_standard_status",
        "achievement_standard",
        ["status"],
    )
    op.create_index(
        "idx_achievement_standard_version_id",
        "achievement_standard",
        ["version_id"],
    )


def downgrade() -> None:
    """Drop lifecycle columns and their indexes."""
    op.drop_index("idx_achievement_standard_version_id", table_name="achievement_standard")
    op.drop_index("idx_achievement_standard_status", table_name="achievement_standard")
    op.drop_column("achievement_standard", "language")
    op.drop_column("achievement_standard", "jurisdiction")
    op.drop_column("achievement_standard", "effective_to")
    op.drop_column("achievement_standard", "version_id")
    op.drop_column("achievement_standard", "status")
    op.drop_column("achievement_standard", "learner_friendly_statement")
    op.drop_column("achievement_standard", "normalized_statement")
    op.drop_column("achievement_standard", "official_statement")
