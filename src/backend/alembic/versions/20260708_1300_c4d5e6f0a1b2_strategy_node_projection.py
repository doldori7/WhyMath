"""strategy_node 메타 프로젝션 — Part 2 리치 채택 Phase 6a

리치 Part 2 스펙 Phase 6a. Strategy(문제 공략 heuristic)를 canonical 1급 노드로 승격한다.
data-pipeline `strategy_graph`가 만든 정본 전략 택소노미의 *안전 메타*를 strategy_id 키로 투영하는
`strategy_node` 테이블을 만든다(검색 enrichment·필터·후속 전략 참조 백킹).

**canonical-only·native enum 없음**: `strategy_id`(TEXT PK)는 사람 관리 안정 code
(`strategy.<slug>`). `family`(4종)·`review_status`는 순수 TEXT(화이트리스트·검증은 pipeline·거버넌스
테스트가 동결). 전량 TEXT/TEXT[](enum 미소유). 전략은 Polya 계획 단계의 공략 발상으로 스텝
`ReasoningType`·풀이 `approach_type`과 직교하는 축이다.

additive: 기존 concept_node·atom_node·skill_node·problem_type_node·formula_node와 무충돌(신규
테이블·신규 enum 0·신규 엣지 타입 0). 전략 연결(problem→strategy 등)은 후속(소비처 실재 시).

Revision ID: c4d5e6f0a1b2
Revises: b3c4d5e6f0a1
Create Date: 2026-07-08 13:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c4d5e6f0a1b2"
down_revision: str | None = "b3c4d5e6f0a1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 전략 프로젝션 — strategy_id(TEXT PK·사람 관리 code)·enum 없음·엣지/선수 DAG 컬럼 없음.
    op.create_table(
        "strategy_node",
        sa.Column("strategy_id", sa.Text(), primary_key=True),
        sa.Column("name_ko", sa.Text(), nullable=False),
        sa.Column("family", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
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
    # family(전략 family 그룹) 보조 인덱스(검색·집계).
    op.create_index("ix_strategy_node_family", "strategy_node", ["family"])


def downgrade() -> None:
    op.drop_index("ix_strategy_node_family", table_name="strategy_node")
    op.drop_table("strategy_node")
