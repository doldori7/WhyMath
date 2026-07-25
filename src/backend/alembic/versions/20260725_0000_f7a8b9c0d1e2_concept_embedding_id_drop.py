"""concept.embedding_id drop — ARCH-14 순수성 부채 청산

죽은 컬럼 `concept.embedding_id`(구 ChromaDB→pgvector 이관 잔재·슬98) 제거.
소비처 0·전량 NULL·로더 미설정·코퍼스 부재(2026-07-03 Phase 1b 4컬럼 청산 선례 동형).
실 벡터는 code 키 별 테이블(`concept_embedding` 등)이 소유하므로 이 참조 컬럼은 불필요.
Concept Purity(구축 플레이북 8대 원칙 — 노드에 embedding 혼입 금지) 부채 -1.

Revision ID: f7a8b9c0d1e2
Revises: e6f1a2b3c4d5
Create Date: 2026-07-25 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f7a8b9c0d1e2"
down_revision: str | None = "e6f1a2b3c4d5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 죽은 참조 컬럼 제거 — PG는 컬럼 전용 인덱스가 있으면 함께 자동 정리한다.
    op.drop_column("concept", "embedding_id")


def downgrade() -> None:
    # 왕복 안전 — nullable UUID 참조로 복원(값은 전량 NULL이었으므로 데이터 손실 0).
    op.add_column("concept", sa.Column("embedding_id", sa.Uuid(), nullable=True))
