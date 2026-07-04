"""concept 런타임 본문·오개념 컬럼 제거 — Part 2 리치 채택 Phase 1b(redaction 청산)

리치 Part 2 전면 채택 Phase 1b. 런타임 `concept` 테이블의 legacy 본문 3컬럼과 자유텍스트 오개념
컬럼을 제거한다:
  - `description`·`formal_definition`·`intuitive_explanation`(TEXT×3) — 성취기준·교과서 *본문*
    근접 자유 서술(redaction·CLAUDE.md 우선순위 #2). 정본은 정본 identity 노드 semantic 계층
    (intuition·representations)·ConceptContent다.
  - `common_misconceptions`(JSONB) — 자유텍스트 오개념 리스트(낙인·즉답·날조 위험). 정본은 독립
    오개념 카탈로그(kebab-id·CLAUDE.md #6)다.
네 컬럼 모두 런타임 소비처 0·전량 NULL/`[]`이었다(죽은 컬럼 청산). 인덱스 무관. downgrade는 대칭
복원(TEXT nullable×3 + JSONB NOT NULL `'[]'::jsonb` — 원 DDL 등가).

Revision ID: f0a1b2c3d4e5
Revises: e9f0a1b2c3d4
Create Date: 2026-07-03 10:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f0a1b2c3d4e5"
down_revision: str | None = "e9f0a1b2c3d4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# 본문 3컬럼(TEXT nullable) — downgrade 복원 시 원 DDL과 등가.
_BODY_TEXT_COLUMNS: tuple[str, ...] = (
    "description",
    "formal_definition",
    "intuitive_explanation",
)


def upgrade() -> None:
    # 본문 3컬럼(TEXT) + 오개념 컬럼(JSONB) 제거 — 전량 NULL/`[]`·소비처 0(redaction 청산).
    for column in _BODY_TEXT_COLUMNS:
        op.drop_column("concept", column)
    op.drop_column("concept", "common_misconceptions")


def downgrade() -> None:
    # 대칭 복원 — 원 DDL 등가(TEXT nullable×3 + JSONB NOT NULL server_default '[]'::jsonb).
    op.add_column(
        "concept",
        sa.Column(
            "common_misconceptions",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    for column in _BODY_TEXT_COLUMNS:
        op.add_column("concept", sa.Column(column, sa.Text(), nullable=True))
