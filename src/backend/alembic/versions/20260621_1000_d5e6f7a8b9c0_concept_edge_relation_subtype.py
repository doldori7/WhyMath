"""concept_edge.relation_subtype — 원자 백본 선수엣지 관계유형 컬럼

원자 백본 마이그레이션 Phase 1(backend 적재). 원자 선수엣지의 `관계유형`(원본/소단원내/소단원간/
학년간/학교급간(추정))을 보존할 nullable TEXT 컬럼을 `concept_edge`에 추가한다. 자유 텍스트
주석이라 native ENUM은 만들지 않는다(원자 백본 전용 메타·후속 Phase 2에서 정식화 가능). 기존
행은 NULL로 시작(구 concept_graph 엣지엔 무관). 인덱스 불필요(엣지 단건·전수 배치).

Revision ID: d5e6f7a8b9c0
Revises: c4d5e6f7a8b9
Create Date: 2026-06-21 10:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d5e6f7a8b9c0"
down_revision: str | None = "c4d5e6f7a8b9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "concept_edge",
        sa.Column("relation_subtype", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("concept_edge", "relation_subtype")
