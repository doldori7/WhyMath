"""problem_type_node 메타 프로젝션 — Part 2 리치 채택 Phase 3

리치 Part 2 스펙 Phase 3. ProblemType을 1급 노드로 승격한다. data-pipeline `problem_type_graph`가
만든 정본 문제유형 코퍼스의 *안전 메타*를 problem_type_id 키로 투영하는 `problem_type_node` 테이블을
만든다(검색 enrichment·필터·후속 문제 분류·추천 백킹).

**native enum 없음(D1)**: skill_node의 `behavior_area_enum`과 달리, cognitive-action 축은 이미
`BehaviorArea`(Phase 2a)라 중복 enum을 두지 않고 유형이 exercise하는 스킬(`behavior_skills` TEXT[]·
skill_graph_v1 참조)로 표현한다. 따라서 이 마이그레이션은 enum을 소유·생성하지 않는다(전량
TEXT/TEXT[]/BOOL). 표면(SignaturePattern) 컬럼도 없다(≠surface 불변식).

additive: 기존 concept_node·atom_node·skill_node·검색과 무충돌(신규 테이블·신규 enum 0). 유형 연결은
참조 키(behavior_skills TEXT[])만 — 별도 엣지 테이블·prerequisite DAG 없음(신규 엣지 타입 0).

Revision ID: f0a1b3c4d5e6
Revises: e5f0a1b3c4d5
Create Date: 2026-07-07 15:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f0a1b3c4d5e6"
down_revision: str | None = "e5f0a1b3c4d5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 문제유형 프로젝션 — problem_type_id(TEXT PK)·enum 없음(behavior_skills로 축 표현).
    op.create_table(
        "problem_type_node",
        sa.Column("problem_type_id", sa.Text(), primary_key=True),
        sa.Column("name_ko", sa.Text(), nullable=False),
        sa.Column("family", sa.Text(), nullable=False),
        sa.Column(
            "behavior_skills",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::text[]"),
        ),
        sa.Column(
            "mastery_estimable",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column("description", sa.Text(), nullable=True),
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
    # family(문제유형 family 그룹) 보조 인덱스(검색·추천·집계).
    op.create_index("ix_problem_type_node_family", "problem_type_node", ["family"])


def downgrade() -> None:
    op.drop_index("ix_problem_type_node_family", table_name="problem_type_node")
    op.drop_table("problem_type_node")
