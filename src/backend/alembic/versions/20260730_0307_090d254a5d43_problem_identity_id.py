"""problem.identity_id — 변형 계보 Identity/Canonical 분리 (S4-18·additive·비파괴)

`docs/architecture/problem_bank_gap_review.md` §3 D8 — problem_relation을 채우려면
rephrase 변형이 원본과 별개 행(별개 problem_id/slug)이어야 하는데, 지금은 slug가 같아
upsert 시 원본과 같은 행에 병합돼 관계 자체가 불가하다(schema._no_self_relation 위반).

Kiki 결정(2026-07-29, Identity/Canonical 분리): `problem_id`는 개체마다 절대 불변,
`identity_id`(신규 nullable UUID·색인)로만 "같은 문제의 다른 표현" 계열(원본+rephrase 등
변형들)을 묶는다. 계열 조회는 이 컬럼의 등가 비교만으로 O(1) — 관계 그래프 순회 불요.

additive·비파괴(기존 행은 전부 NULL=계열 없음 유지·자기관계 금지 등 기존 불변식 무영향).

Revision ID: 090d254a5d43
Revises: b4c5d6e7f0a2
Create Date: 2026-07-30 03:07:55.372102
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "090d254a5d43"
down_revision: str | None = "b4c5d6e7f0a2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "problem",
        sa.Column("identity_id", sa.Uuid(), nullable=True),
    )
    op.create_index("ix_problem_identity_id", "problem", ["identity_id"])


def downgrade() -> None:
    op.drop_index("ix_problem_identity_id", table_name="problem")
    op.drop_column("problem", "identity_id")
