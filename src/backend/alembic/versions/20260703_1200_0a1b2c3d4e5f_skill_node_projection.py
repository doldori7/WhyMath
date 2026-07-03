"""skill_node 메타 프로젝션 + behavior_area_enum — Part 2 리치 채택 Phase 2a

리치 Part 2 스펙 Phase 2a. Skill을 1급 노드로 승격한다. data-pipeline `skill_graph`가 만든
정본 스킬 코퍼스의 *안전 메타*를 skill_id 키로 투영하는 `skill_node` 테이블과, 6종 폐쇄 행동영역
PG native enum `behavior_area_enum`을 만든다(검색 enrichment·필터·Phase 2b skill mastery 조인 백킹).

additive: 기존 concept_node·atom_node·검색·임베딩과 무충돌(신규 테이블·신규 enum). 스킬 연결은
참조 키(prerequisite_skill_ids ARRAY)만 — 별도 엣지 테이블 없음(신규 엣지 타입 0·anti-explosion).

`behavior_area_enum`은 이 마이그레이션이 *소유*(생성·downgrade에서 drop) — visualization_style_enum
(`b5c6d7e8f9a0`) 선례를 따른다(add_column과 달리 create_table도 enum 자동 생성이 되지만, 명시
생성 + create_type=False로 robust하게·downgrade 대칭 drop). 값은 `schema/enums.py::BehaviorArea`·
data-pipeline `skill_graph.models.BehaviorArea`와 *정확히 일치*해야 한다(정합 테스트 동결).

Revision ID: 0a1b2c3d4e5f
Revises: f0a1b2c3d4e5
Create Date: 2026-07-03 12:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0a1b2c3d4e5f"
down_revision: str | None = "f0a1b2c3d4e5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# schema/enums.py BehaviorArea·data-pipeline skill_graph.models.BehaviorArea와 *정확히 일치*(6종).
_BEHAVIOR_AREAS: tuple[str, ...] = (
    "COMPUTE",
    "TRANSFORM",
    "INTERPRET",
    "REPRESENT",
    "REASON",
    "VERIFY",
)


def upgrade() -> None:
    # 6종 폐쇄 행동영역 native enum — 이 마이그레이션이 소유(명시 생성·checkfirst 멱등).
    behavior_area = postgresql.ENUM(*_BEHAVIOR_AREAS, name="behavior_area_enum")
    behavior_area.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "skill_node",
        sa.Column("skill_id", sa.Text(), primary_key=True),
        sa.Column("name_ko", sa.Text(), nullable=False),
        sa.Column(
            "behavior_area",
            postgresql.ENUM(*_BEHAVIOR_AREAS, name="behavior_area_enum", create_type=False),
            nullable=False,
        ),
        sa.Column("family", sa.Text(), nullable=False),
        sa.Column(
            "mastery_estimable",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "prerequisite_skill_ids",
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
    # behavior_area(행동영역 필터)·family(Skill Family 그룹) 보조 인덱스(검색·추천·mastery 집계).
    op.create_index("ix_skill_node_behavior_area", "skill_node", ["behavior_area"])
    op.create_index("ix_skill_node_family", "skill_node", ["family"])


def downgrade() -> None:
    op.drop_index("ix_skill_node_family", table_name="skill_node")
    op.drop_index("ix_skill_node_behavior_area", table_name="skill_node")
    op.drop_table("skill_node")
    # 이 마이그레이션이 만든 native enum 정리(checkfirst로 멱등).
    postgresql.ENUM(name="behavior_area_enum").drop(op.get_bind(), checkfirst=True)
