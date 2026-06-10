"""problem.visualizations — 선언적 시각화 명세 임베딩 컬럼 (JSONB)

슬라이스 91 — 슬라이스 90 `Visualization` 명세(05 §5.2)를 Problem이 실어 나르도록
`problem.visualizations jsonb` 컬럼을 추가한다. schema는 `list[Visualization]`,
ORM은 `list[dict]`(model_dump→JSONB). `conditions_parsed`/`cross_unit_pairs`와 동형
(NOT NULL·server_default `'[]'::jsonb`). 슬88(ARRAY native enum)과 달리 자유 JSON이라
ENUM 타입 생성·정리 없음. 기존 행은 빈 배열로 시작.

Revision ID: c6d7e8f9a0b1
Revises: b5c6d7e8f9a0
Create Date: 2026-06-10 03:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c6d7e8f9a0b1"
down_revision: str | None = "b5c6d7e8f9a0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "problem",
        sa.Column(
            "visualizations",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("problem", "visualizations")
