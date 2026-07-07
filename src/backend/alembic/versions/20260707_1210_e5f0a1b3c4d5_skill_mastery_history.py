"""skill_mastery_history — 스킬 숙달 시계열 hypertable (Part 2 리치 채택 Phase 2b-2)

`ConceptMasteryHistory`의 *스킬 축* 짝을 신설한다. 채점 attempt가 평가하는 개념을 concept→skill
브리지(`Concept.behavior_skills` ∩ mastery-estimable `skill_node`)로 해소한 각 스킬의 BKT 숙달을
append-only 적재하는 시계열. 개념과의 유일 차이는 PK 두 번째 축이 `concept_id`(UUID)가 아니라
`skill_id`(**TEXT**·`skill.<slug>`)라는 점이다.

`user_id`·`skill_id`는 §느슨참조(REFERENCES 없음·hypertable·concept_mastery_history 선례). 운영
시 timescaledb가 설치된 환경에서만 `measured_at` 7일 청크 hypertable로 변환(if_not_exists 멱등·
미설치 CI/개발은 일반 테이블로 남아 검증 가능·bb30b816083d DO블록 미러). PK에 시간 컬럼이 포함돼
hypertable UNIQUE 제약을 만족한다.

Revision ID: e5f0a1b3c4d5
Revises: d4e5f0a1b3c4
Create Date: 2026-07-07 12:10:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e5f0a1b3c4d5"
down_revision: str | None = "d4e5f0a1b3c4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # concept_mastery_history 미러 — skill_id(TEXT)로 재키잉. 느슨참조(FK 없음).
    op.create_table(
        "skill_mastery_history",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("skill_id", sa.Text(), nullable=False),
        sa.Column("measured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("mastery", sa.Numeric(precision=3, scale=2), nullable=True),
        sa.Column("confidence", sa.Numeric(precision=3, scale=2), nullable=True),
        sa.Column("sample_size", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint(
            "user_id", "skill_id", "measured_at", name=op.f("pk_skill_mastery_history")
        ),
    )
    # TimescaleDB hypertable 변환(설치 환경에서만·if_not_exists 멱등·bb30b816083d 선례).
    # 시간 컬럼(measured_at)이 PK에 포함돼 hypertable UNIQUE 제약 충족(concept 축과 동형).
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'timescaledb') THEN
                PERFORM create_hypertable('skill_mastery_history', 'measured_at',
                    chunk_time_interval => INTERVAL '7 days', if_not_exists => TRUE);
            END IF;
        END
        $$;
        """)


def downgrade() -> None:
    op.drop_table("skill_mastery_history")
