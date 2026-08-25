"""CUR-10 curriculum framework version tables

Revision ID: 899ae0efbb8b
Revises: fcfdfc277348
Create Date: 2026-08-25 16:34:35.375852
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "899ae0efbb8b"
down_revision: str | None = "fad7f750090d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# CUR-10 Phase 1: EOS Curriculum Semantic Backbone의 Framework/Version 분리.
# - CurriculumFramework / CurriculumVersion 테이블 신설.
# - AchievementStandard / CurriculumEntry에 nullable framework_id(FK) 추가.
# - 기존 한국(KR) 행은 'KR_NC_2022' 프레임워크로 백필.
def upgrade() -> None:
    op.create_table(
        "curriculum_framework",
        sa.Column("framework_id", sa.String(length=64), nullable=False),
        sa.Column("authority", sa.String(), nullable=False),
        sa.Column("country", sa.String(length=16), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("effective_from", sa.Date(), nullable=True),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column(
            "status",
            sa.String(length=30),
            server_default=sa.text("'published'"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("framework_id", name=op.f("pk_curriculum_framework")),
    )
    op.create_table(
        "curriculum_version",
        sa.Column(
            "version_id",
            sa.Uuid(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("framework_id", sa.String(length=64), nullable=False),
        sa.Column("version_label", sa.String(), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=True),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column(
            "status",
            sa.String(length=30),
            server_default=sa.text("'published'"),
            nullable=False,
        ),
        sa.Column("source_id", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["framework_id"],
            ["curriculum_framework.framework_id"],
            name=op.f("fk_curriculum_version_framework_id_curriculum_framework"),
        ),
        sa.PrimaryKeyConstraint("version_id", name=op.f("pk_curriculum_version")),
        sa.UniqueConstraint(
            "framework_id",
            "version_label",
            name="uq_curriculum_version_framework_label",
        ),
    )

    op.add_column(
        "achievement_standard",
        sa.Column("framework_id", sa.String(length=64), nullable=True),
    )
    op.create_foreign_key(
        op.f("fk_achievement_standard_framework_id_curriculum_framework"),
        "achievement_standard",
        "curriculum_framework",
        ["framework_id"],
        ["framework_id"],
    )

    op.add_column(
        "curriculum_entry",
        sa.Column("framework_id", sa.String(length=64), nullable=True),
    )
    op.create_foreign_key(
        op.f("fk_curriculum_entry_framework_id_curriculum_framework"),
        "curriculum_entry",
        "curriculum_framework",
        ["framework_id"],
        ["framework_id"],
    )

    # --- 백필: 기존 한국 교육과정 행을 KR_NC_2022 프레임워크로 연결 ---
    # Framework은 항상 한 개만 보장 (이미 있으면 noop).
    op.execute("""
        INSERT INTO curriculum_framework (
            framework_id, authority, country, title, description,
            status, created_at, updated_at
        )
        VALUES (
            'KR_NC_2022', '한국 교육부 / 한국교육과정평가원', 'KR',
            '2022 개정 교육과정',
            '2015 개정 이후 2022년 고시된 한국 교육과정',
            'published', NOW(), NOW()
        )
        ON CONFLICT (framework_id) DO NOTHING
        """)

    # AchievementStandard.version_id별로 CurriculumVersion 행을 생성해 기존 스냅숏을 보존.
    # 먼저 같은 curriculum_revision을 가진 KR 행의 version_id를 단일 UUID로 통일해야
    # curriculum_version의 (framework_id, version_label) UNIQUE 제약이 위반되지 않는다.
    op.execute("""
        UPDATE achievement_standard s
        SET version_id = rev.version_id
        FROM (
            SELECT DISTINCT ON (COALESCE(NULLIF(curriculum_revision, ''), 'initial'))
                gen_random_uuid() AS version_id,
                COALESCE(NULLIF(curriculum_revision, ''), 'initial') AS version_label
            FROM achievement_standard
            WHERE jurisdiction = 'KR'
        ) rev
        WHERE s.jurisdiction = 'KR'
          AND rev.version_label = COALESCE(NULLIF(s.curriculum_revision, ''), 'initial')
        """)
    op.execute("""
        INSERT INTO curriculum_version (
            version_id, framework_id, version_label,
            effective_from, status, created_at, updated_at
        )
        SELECT DISTINCT ON (COALESCE(NULLIF(s.curriculum_revision, ''), 'initial'))
            s.version_id,
            'KR_NC_2022',
            COALESCE(NULLIF(s.curriculum_revision, ''), 'initial'),
            s.effective_from,
            s.status,
            NOW(),
            NOW()
        FROM achievement_standard s
        WHERE s.jurisdiction = 'KR'
        ON CONFLICT (version_id) DO NOTHING
        """)
    op.execute("""
        UPDATE achievement_standard
        SET framework_id = 'KR_NC_2022'
        WHERE jurisdiction = 'KR' AND framework_id IS NULL
        """)

    # CurriculumEntry는 version이 없으므로 framework만 연결.
    op.execute("""
        UPDATE curriculum_entry
        SET framework_id = 'KR_NC_2022'
        WHERE country_code = 'KR' AND framework_id IS NULL
        """)


def downgrade() -> None:
    op.drop_constraint(
        op.f("fk_curriculum_entry_framework_id_curriculum_framework"),
        "curriculum_entry",
        type_="foreignkey",
    )
    op.drop_column("curriculum_entry", "framework_id")

    op.drop_constraint(
        op.f("fk_achievement_standard_framework_id_curriculum_framework"),
        "achievement_standard",
        type_="foreignkey",
    )
    op.drop_column("achievement_standard", "framework_id")

    op.drop_table("curriculum_version")
    op.drop_table("curriculum_framework")
