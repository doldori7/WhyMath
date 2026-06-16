"""concept.source_id 컬럼(+ 인덱스) + aliases NOT NULL 정규화 (P2b concept_id 재ID 영속)

data-pipeline concept_id 재ID(2026-06-16·`{TRACK}-{AREA}-{NNN}`)를 백엔드 `concept` 테이블로
전파한다. ORM 정본은 `whymath_backend/db/models/concept.py`(Concept), 계약은
`whymath_backend/schema/concept.py`. 재ID로 각 개념이 `source_id`(원천 src_id)와 `aliases`
([레거시 UC, src_id])를 갖게 되어, 이 둘을 백엔드 영속 컬럼으로 받는다.

UUID PK 보존(결정적): `concept.concept_id`(UUID PK)·기존 행은 *건드리지 않는다* — 라이브
`concept_mastery_history`(concept_id 참조)·`concept_edge`(from/to_concept_id FK)가 그 UUID에
의존하므로 PK churn이 없어야 한다. 이 마이그레이션은 컬럼만 더하고/정규화한다(PK·행 보존).

변경:
  ① source_id(VARCHAR(64) NULL) 추가 — 재ID 전 원천 식별자(src_id) 보존. **FK 아님**(원천 키
     공간). 백엔드 적재기는 옛 graph.json(source_id 부재)도 받아야 해 nullable(점진 채움).
  ② idx_concept_source_id 인덱스 — src_id→code 해석(standard_loader load_links)·src_id 역조회.
  ③ aliases NOT NULL 정규화 — 기존 `ARRAY(Text) NULL`을 NOT NULL + server_default '{}'로 바꾼다
     (schema.Concept.aliases가 list[str]·default_factory=list라 NULL 대신 빈 배열이 정합·
     problem.py tags/keywords NOT NULL 배열 선례). 기존 NULL 행은 먼저 '{}'로 backfill해야
     SET NOT NULL이 통과한다(라이브 행 보존·값만 NULL→빈 배열로 정규화).

downgrade(왕복 안전 — CI backend-migrations 잡이 `downgrade base`→`upgrade head` 왕복 검증):
  aliases를 다시 nullable로(server_default 제거) 되돌리고, source_id 인덱스·컬럼을 drop한다.
  enum 신규 없음 → 후처리 불요.

Revision ID: b7c8d9e0f1a2
Revises: a6b7c8d9e0f1
Create Date: 2026-06-16 11:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b7c8d9e0f1a2"
down_revision: str | None = "a6b7c8d9e0f1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ① source_id(NULL) — 원천 src_id 보존(FK 아님·옛 데이터 수용 위해 nullable).
    op.add_column(
        "concept",
        sa.Column("source_id", sa.String(length=64), nullable=True),
    )
    # ② src_id 역조회·src_id→code 해석(load_links) 경로 인덱스.
    op.create_index(
        "idx_concept_source_id",
        "concept",
        ["source_id"],
        unique=False,
    )

    # ③ aliases NOT NULL 정규화 — 기존 NULL 행을 빈 배열로 backfill 후 server_default·NOT NULL.
    #    라이브 행은 PK·다른 컬럼 불변, aliases만 NULL→'{}'로 정규화(값 정규화이지 PK churn 아님).
    op.execute("UPDATE concept SET aliases = '{}'::text[] WHERE aliases IS NULL")
    op.alter_column(
        "concept",
        "aliases",
        existing_type=sa.ARRAY(sa.Text()),
        nullable=False,
        server_default=sa.text("'{}'::text[]"),
    )


def downgrade() -> None:
    # ③ aliases를 다시 nullable로(server_default 제거) — 왕복 안전(값은 빈 배열로 남아도 무해).
    op.alter_column(
        "concept",
        "aliases",
        existing_type=sa.ARRAY(sa.Text()),
        nullable=True,
        server_default=None,
    )
    # ②→① 인덱스 → 컬럼 순으로 drop.
    op.drop_index("idx_concept_source_id", table_name="concept")
    op.drop_column("concept", "source_id")
