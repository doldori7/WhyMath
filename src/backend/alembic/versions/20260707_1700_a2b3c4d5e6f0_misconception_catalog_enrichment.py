"""misconception_catalog.severity·behavior_skills — 오개념 enrichment (Part 2 리치 채택 Phase 4a)

리치 Part 2 스펙 Phase 4a. 정본 콘텐츠 카탈로그 `misconception_catalog`(mis_id PK·M-id)에 2필드
additive enrichment:

  - `severity` `String(16)` — 후속 학습 손상도(blocking/local/cosmetic). *문항 난이도
    difficulty와 별개 축*이며 어휘도 disjoint. 어휘 강제는 파이프라인 책임(가짜 CHECK 없음).
    nullable(error_type 신호 없으면 None).
  - `behavior_skills` `ARRAY(Text)` NOT NULL server_default '{}' — 이 오개념이 튀어나오는 skill
    (arises-in·진단 방향) skill_id 참조 배열. concept_node/problem_type_node.behavior_skills 동형.
    junction 아님 — 참조 키 배열이라 **신규 엣지 타입 0**(anti-explosion). 개념 테이블에 FK 결합
    안 됨(Level 2 loose-ref·오개념 독립 DB 유지). 기존 행은 빈 배열 `'{}'`(멱등 재적재가 채움).

additive·비파괴(crosswalk/canonical 무관·frequency/visual_repair 미도입).

Revision ID: a2b3c4d5e6f0
Revises: f0a1b3c4d5e6
Create Date: 2026-07-07 17:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a2b3c4d5e6f0"
down_revision: str | None = "f0a1b3c4d5e6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # severity — 후속 학습 손상도(blocking/local/cosmetic·nullable·difficulty와 별개 축).
    op.add_column(
        "misconception_catalog",
        sa.Column("severity", sa.String(16), nullable=True),
    )
    # behavior_skills — arises-in skill 참조 배열(NOT NULL·빈 배열 server_default·신규 엣지 타입 0).
    op.add_column(
        "misconception_catalog",
        sa.Column(
            "behavior_skills",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::text[]"),
        ),
    )


def downgrade() -> None:
    op.drop_column("misconception_catalog", "behavior_skills")
    op.drop_column("misconception_catalog", "severity")
