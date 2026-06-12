"""concept_embedding 테이블 + pgvector 확장 (L1 개념 의미검색 영속·슬라이스 3)

L1 개념그래프 적재 아크 슬3 — 슬2가 개념을 Neo4j에 적재한 뒤, 개념의 *의미 임베딩*을 pgvector에
영속하는 백킹 테이블을 만든다. PK=concept_id(UC TEXT)로 슬2 Neo4j 노드 키와 *동일 키 공간*이라
그래프↔벡터가 한 키로 join된다(이중 store 단일 키). L4 `misconception_embedding`(슬105)
마이그레이션을 개념용으로 미러링한다.

upgrade:
  - `CREATE EXTENSION IF NOT EXISTS vector` — pgvector 확장 활성(`vector` 타입 사용 전제).
    슬105 마이그레이션이 이미 생성하므로 정상 체인에선 무동작(IF NOT EXISTS). *그러나 여기서도
    명시 실행*하는 이유: 이 마이그레이션이 단독 적용되거나(다른 DB에 cherry-pick) 슬105가 어떤
    경로로 빠져도 `concept_embedding`의 `vector` 컬럼 생성이 안전하도록 자기완결적으로 보장한다.
  - `concept_embedding` 테이블:
    - `concept_id`(TEXT PK) — Universal Concept ID, upsert 충돌 키(슬2 Neo4j 노드 키와 동일).
    - `embedding`(pgvector `vector(1024)`) — 임베딩(기본 bge-m3 1024차원).
    - `provider`·`model`·`dim`·`text_hash`·`updated_at` — 임베딩 공간 메타·표현 변경 감지·신선도.
      **원문(source_text)은 컬럼으로 두지 않는다**(redaction·중복 — ORM docstring 참조).
  - **HNSW/IVFFlat 인덱스 없음**: `misconception_embedding`과 동일 — 현 규모는 seq-scan이 최적
    (스케일 코퍼스는 fixed-dim + HNSW cosine 인덱스가 정석 — 후속·이 테이블은 영속화 groundwork).

downgrade (왕복 안전 — CI가 `downgrade base`→`upgrade head` 왕복 검증):
  - `concept_embedding` 테이블만 drop. **`vector` 확장은 drop하지 않는다** — 슬105
    `misconception_embedding`이 *여전히 `vector` 타입 컬럼을 소유*하므로 확장을 떨어뜨리면
    그 테이블이 깨진다(슬105 마이그레이션이 down_revision 체인상 이 마이그레이션보다 *아래*에
    있어, 이 downgrade 시점엔 misconception_embedding이 살아 있다). 확장 생애주기는 *맨 처음
    확장을 도입한* 슬105 마이그레이션의 downgrade가 책임진다(확장 소유권은 한 곳).

차원 메모: `embedding`은 `vector(1024)`로 고정한다(`config.embedding_dim` 기본값과 정합·ORM
`ConceptEmbedding.embedding`·`misconception_embedding`과 동일). 임베딩 *모델* 교체로 차원이
달라지면(Fake 64·te-3-large 3072) config·ORM과 함께 *새 마이그레이션*으로 컬럼 차원을 바꾼다
(마이그레이션은 결정적이어야 하므로 여기선 정본 기본값을 박는다).

Revision ID: e8f9a0b1c2d3
Revises: d7e8f9a0b1c2
Create Date: 2026-06-12 10:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e8f9a0b1c2d3"
down_revision: str | None = "d7e8f9a0b1c2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# 정본 임베딩 차원(config.embedding_dim 기본 1024·bge-m3). 마이그레이션은 결정적이어야 하므로
# 런타임 설정이 아닌 고정 리터럴을 박는다(모델 교체 시 새 마이그레이션으로 변경·슬105 동일).
_EMBEDDING_DIM = 1024


def upgrade() -> None:
    # pgvector 확장 — vector 타입 사용 전제. 슬105가 이미 만들었으면 무동작(IF NOT EXISTS).
    # 자기완결적 보장(단독 적용·cherry-pick 안전).
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "concept_embedding",
        sa.Column("concept_id", sa.Text(), nullable=False),
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
        sa.PrimaryKeyConstraint("concept_id", name=op.f("pk_concept_embedding")),
    )


def downgrade() -> None:
    # 테이블만 drop. `vector` 확장은 슬105 misconception_embedding이 여전히 소유하므로
    # *떨어뜨리지 않는다*(확장 소유권은 도입 마이그레이션[슬105]에 있음 — docstring 참조).
    op.drop_table("concept_embedding")
