"""concept_edge prerequisite 메타 확장 (CUR-16)

EOS 6_개념 DB 검토 §13에 따른 prerequisite 엣지 메타를 추가한다.
- required_strength_enum, dependency_level_enum 생성
- concept_edge 테이블에 required_strength, dependency_level, minimum_mastery,
  curriculum_context, evidence_source_id 컬럼 추가

Revision ID: fad7f750090d
Revises: d5e6f7a8b9c0
Create Date: 2026-08-25 17:16:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "fad7f750090d"
down_revision: str | None = "fcfdfc277348"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    required_strength_enum = postgresql.ENUM(
        "WEAK",
        "MODERATE",
        "STRONG",
        "CRITICAL",
        name="required_strength_enum",
        create_type=True,
    )
    required_strength_enum.create(op.get_bind(), checkfirst=True)

    dependency_level_enum = postgresql.ENUM(
        "RECOMMENDED",
        "EXPECTED",
        "REQUIRED",
        name="dependency_level_enum",
        create_type=True,
    )
    dependency_level_enum.create(op.get_bind(), checkfirst=True)

    op.add_column(
        "concept_edge",
        sa.Column(
            "required_strength",
            sa.Enum(
                "WEAK",
                "MODERATE",
                "STRONG",
                "CRITICAL",
                name="required_strength_enum",
            ),
            nullable=True,
        ),
    )
    op.add_column(
        "concept_edge",
        sa.Column(
            "dependency_level",
            sa.Enum(
                "RECOMMENDED",
                "EXPECTED",
                "REQUIRED",
                name="dependency_level_enum",
            ),
            nullable=True,
        ),
    )
    op.add_column(
        "concept_edge",
        sa.Column("minimum_mastery", sa.Numeric(3, 2), nullable=True),
    )
    op.add_column(
        "concept_edge",
        sa.Column(
            "curriculum_context",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::text[]"),
        ),
    )
    op.add_column(
        "concept_edge",
        sa.Column("evidence_source_id", sa.String(length=64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("concept_edge", "evidence_source_id")
    op.drop_column("concept_edge", "curriculum_context")
    op.drop_column("concept_edge", "minimum_mastery")
    op.drop_column("concept_edge", "dependency_level")
    op.drop_column("concept_edge", "required_strength")

    op.execute("DROP TYPE IF EXISTS dependency_level_enum")
    op.execute("DROP TYPE IF EXISTS required_strength_enum")
