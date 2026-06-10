"""misconception_embedding 테이블 + pgvector 확장 (L4 의미 매칭 영속)

슬라이스 105 — 슬104 `VectorIndex` 좌석의 *영속(pgvector) 백엔드*(`PgVectorIndex`) 백킹
테이블을 만든다. 슬98 결정(벡터 DB=pgvector·Postgres 16 통합)의 첫 실 결선.

upgrade:
  - `CREATE EXTENSION IF NOT EXISTS vector` — pgvector 확장 활성(`vector` 타입 사용 전제).
  - `misconception_embedding` 테이블:
    - `misconception_id`(TEXT PK) — 카탈로그 항목 식별자, upsert 충돌 키.
    - `embedding`(pgvector `vector(1024)`) — 임베딩(기본 bge-m3 1024차원).
    - `provider`·`model`·`dim`·`text_hash`·`updated_at` — 임베딩 공간 메타·표현 변경 감지·신선도.
  - **HNSW/IVFFlat 인덱스 없음**: 30종 코퍼스는 seq-scan이 최적이라 ANN 인덱스를 두지 않는다
    (스케일 코퍼스는 fixed-dim + HNSW cosine 인덱스가 정석 — 후속·이 테이블은 영속화 groundwork).

downgrade (왕복 안전 — CI가 `downgrade base`→`upgrade head` 왕복 검증):
  - 테이블 drop + `DROP EXTENSION IF EXISTS vector`. 현재 `vector` 타입을 쓰는 객체는 이
    테이블뿐이라 extension drop이 다른 객체와 충돌하지 않는다(CASCADE 불요·IF EXISTS로 안전).

차원 메모: `embedding`은 `vector(1024)`로 고정한다(`config.embedding_dim` 기본값과 정합·ORM
`MisconceptionEmbedding.embedding`과 동일). 임베딩 *모델* 교체로 차원이 달라지면(Fake 64·
te-3-large 3072) config·ORM과 함께 *새 마이그레이션*으로 컬럼 차원을 바꾼다(마이그레이션은
결정적이어야 하므로 여기선 정본 기본값을 박는다).

Revision ID: d7e8f9a0b1c2
Revises: c6d7e8f9a0b1
Create Date: 2026-06-10 05:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d7e8f9a0b1c2"
down_revision: str | None = "c6d7e8f9a0b1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# 정본 임베딩 차원(config.embedding_dim 기본 1024·bge-m3). 마이그레이션은 결정적이어야 하므로
# 런타임 설정이 아닌 고정 리터럴을 박는다(모델 교체 시 새 마이그레이션으로 변경).
_EMBEDDING_DIM = 1024


def upgrade() -> None:
    # pgvector 확장 — vector 타입 사용 전제. 이미 있으면 무동작(IF NOT EXISTS).
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "misconception_embedding",
        sa.Column("misconception_id", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(_EMBEDDING_DIM), nullable=False),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("model", sa.Text(), nullable=False),
        sa.Column("dim", sa.Integer(), nullable=False),
        sa.Column("text_hash", sa.Text(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("misconception_id", name=op.f("pk_misconception_embedding")),
    )


def downgrade() -> None:
    op.drop_table("misconception_embedding")
    # vector 타입을 쓰는 객체는 이 테이블뿐이라 안전하게 drop(IF EXISTS·왕복 정합).
    op.execute("DROP EXTENSION IF EXISTS vector")
