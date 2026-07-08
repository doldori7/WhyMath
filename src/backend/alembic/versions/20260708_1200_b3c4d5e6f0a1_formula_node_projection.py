"""formula_node 메타 프로젝션 — Part 2 리치 채택 Phase 5a

리치 Part 2 스펙 Phase 5a. Formula를 canonical-only 1급 노드로 승격한다. data-pipeline
`formula_graph`가 만든 정본 canonical 수식 코퍼스의 *안전 메타*를 formula_id 키로 투영하는
`formula_node` 테이블을 만든다(검색 enrichment·필터·후속 5b 수식 참조 백킹).

**canonical-only·ID≠Signature·native enum 없음**: `formula_id`(TEXT PK)는 사람 관리 안정 code
(`formula.<slug>`·SymPy 계산값 아님). `canonical_signature`는 nullable 보조 메타(정체성 아님).
변형/동치 컬럼 없음 — 변형↔canonical 동치는 런타임 SymPy(l3)가 판정(SymPy 재구현 금지). 전량
TEXT/TEXT[](enum 미소유).

additive: 기존 concept_node·atom_node·skill_node·problem_type_node와 무충돌(신규 테이블·신규 enum 0·
신규 엣지 타입 0). 수식 연결(concept→formula·`formula_refs`)은 Phase 5b(소비처 실재 시).

Revision ID: b3c4d5e6f0a1
Revises: a2b3c4d5e6f0
Create Date: 2026-07-08 12:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b3c4d5e6f0a1"
down_revision: str | None = "a2b3c4d5e6f0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 수식 프로젝션 — formula_id(TEXT PK·사람 관리 code)·enum 없음·변형/동치 컬럼 없음(SymPy 위임).
    op.create_table(
        "formula_node",
        sa.Column("formula_id", sa.Text(), primary_key=True),
        sa.Column("name_ko", sa.Text(), nullable=False),
        sa.Column("family", sa.Text(), nullable=False),
        sa.Column("latex", sa.Text(), nullable=False),
        sa.Column("dsl", sa.Text(), nullable=False),
        sa.Column("canonical_signature", sa.Text(), nullable=True),
        sa.Column(
            "aliases",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::text[]"),
        ),
        sa.Column(
            "standard_codes",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::text[]"),
        ),
        sa.Column("review_status", sa.Text(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    # family(수식 family 그룹) 보조 인덱스(검색·집계).
    op.create_index("ix_formula_node_family", "formula_node", ["family"])


def downgrade() -> None:
    op.drop_index("ix_formula_node_family", table_name="formula_node")
    op.drop_table("formula_node")
