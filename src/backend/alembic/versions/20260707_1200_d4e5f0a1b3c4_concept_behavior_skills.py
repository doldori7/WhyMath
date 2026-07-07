"""concept.behavior_skills — 런타임 concept→skill 참조 배열 (Part 2 리치 채택 Phase 2b-2)

리치 Part 2 스펙 Phase 2b-2. skill mastery의 런타임 concept→skill 해소를 위해 정본 노드
`behavior_skills`(2b-1 저작)를 *런타임 `concept` 테이블*에 투영한다. skill_id(`skill.<slug>`) 목록·
`aliases` 동형 안전 배열(본문 아님·자체작성 skill_id 공간).

구 437 `concept_node.behavior_skills`(2b-1·a1b2c3d4e5f0)가 아니라 런타임 `concept`에 싣는 이유:
S0-4b 거버넌스(`test_legacy_snapshot_governance.py`)가 `concept_node`의 런타임 read(ConceptNode
ORM 참조)를 api/l2/l3/l4에서 금지한다. 문제가 태깅되는 축은 `problem_concept`→`concept`(UUID)이고
concept mastery도 그 축을 쓰므로 skill mastery도 같은 sanctioned 축(concept UUID)에 브리지를 둔다.

junction 테이블 아님 — 참조 키 배열이라 **신규 엣지 타입 0**(anti-explosion). 기존 행은 빈 배열
`'{}'`로 시작(멱등 재적재가 매핑 채움). additive·비파괴.

Revision ID: d4e5f0a1b3c4
Revises: c3d4e5f0a1b3
Create Date: 2026-07-07 12:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d4e5f0a1b3c4"
down_revision: str | None = "c3d4e5f0a1b3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 런타임 concept→skill 참조 배열(aliases 선례 동형·NOT NULL·빈 배열 server_default).
    op.add_column(
        "concept",
        sa.Column(
            "behavior_skills",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::text[]"),
        ),
    )


def downgrade() -> None:
    op.drop_column("concept", "behavior_skills")
