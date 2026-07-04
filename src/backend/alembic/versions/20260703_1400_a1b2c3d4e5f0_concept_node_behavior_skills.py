"""concept_node.behavior_skills — concept→skill 참조 배열 (Part 2 리치 채택 Phase 2b-1)

리치 Part 2 스펙 Phase 2b-1. concept→skill 매핑(`behavior_skills`)을 런타임에서 조회 가능하게
`concept_node` 프로젝션에 참조 배열 컬럼을 추가한다. skill_id(`skill.<slug>`) 목록이며 본문 아님
(`standard_codes` 동형 안전 배열). (Phase 2b-2) skill mastery 런타임 해소(concept UUID→code→
concept_node.behavior_skills→skill)의 조인 백킹이다.

junction 테이블 아님 — 참조 키 배열(개념측 behavior_skills)이라 **신규 엣지 타입 0** 준수
(anti-explosion). 기존 행은 빈 배열 `'{}'`로 시작(멱등 재적재가 매핑 채움). additive.

Revision ID: a1b2c3d4e5f0
Revises: 0a1b2c3d4e5f
Create Date: 2026-07-03 14:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f0"
down_revision: str | None = "0a1b2c3d4e5f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # concept→skill 참조 배열(standard_codes 선례 동형·NOT NULL·빈 배열 server_default).
    op.add_column(
        "concept_node",
        sa.Column(
            "behavior_skills",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::text[]"),
        ),
    )


def downgrade() -> None:
    op.drop_column("concept_node", "behavior_skills")
