"""problem.irt_difficulty_b — JMLE 보정 문항 난이도 b(logit) 컬럼

슬라이스 79 — 응답 데이터로 적합한 문항 난이도 b(`l2.fit_jmle`)를 영속할 컬럼을 `problem`에
추가한다. NULL=미보정 → θ 추정은 `difficulty_overall` 휴리스틱(`difficulty_to_logit`)으로
폴백. Float·nullable·a(변별도)는 1PL 고정이라 미저장. 기존 행은 NULL로 시작(점진 보정).
인덱스 불필요(PK 단건 update·전수 배치 SELECT).

Revision ID: a3b4c5d6e7f8
Revises: f2a3b4c5d6e7
Create Date: 2026-06-09 12:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a3b4c5d6e7f8"
down_revision: str | None = "f2a3b4c5d6e7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "problem",
        sa.Column("irt_difficulty_b", sa.Float(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("problem", "irt_difficulty_b")
