"""misconception_crosslink 테이블 생성 — 오개념 kebab-id ↔ M-id N:M 매핑(정체성 통합 골격).

L4 런타임 탐지 정본 kebab-id 30종과 콘텐츠 카탈로그 M-id 839종(misconception_catalog)을 *FK로 묶지
않던* 두 체계 사이를 N:M 매핑으로 잇는다(math_dsl_remediation_design.md §1·risk_register Q10-⑥).
학생 데이터는 kebab-id를 보존하고(rekey 불필요) 조회 시점에 이 테이블로 M-id를 해석한다(read-time).
`concept_standard_link` 선례 그대로 — `link_id` UUID PK·`kebab_id` 느슨참조·`mis_id` 실 FK(CASCADE)·
의미 유일키 `(kebab_id, mis_id, link_type)`·양방향 인덱스 2.

upgrade: 테이블·UNIQUE·인덱스·FK 생성(additive — 기존 데이터 무영향).
downgrade: 테이블 drop(인덱스·제약 동반 제거).

Revision ID: e2f3a4b5c6d7
Revises: d1e2f3a4b5c6
Create Date: 2026-06-30 14:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e2f3a4b5c6d7"
down_revision: str | None = "d1e2f3a4b5c6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "misconception_crosslink",
        sa.Column(
            "link_id",
            sa.Uuid(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("kebab_id", sa.String(length=64), nullable=False),
        sa.Column("mis_id", sa.String(length=16), nullable=False),
        sa.Column("link_type", sa.String(length=8), nullable=False),
        sa.Column("confidence", sa.Numeric(precision=3, scale=2), nullable=True),
        sa.Column("method", sa.String(length=16), server_default="manual", nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["mis_id"],
            ["misconception_catalog.mis_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("link_id"),
        sa.UniqueConstraint(
            "kebab_id",
            "mis_id",
            "link_type",
            name="uq_misconception_crosslink_kebab_mis_type",
        ),
    )
    op.create_index("idx_misconception_crosslink_kebab", "misconception_crosslink", ["kebab_id"])
    op.create_index("idx_misconception_crosslink_mis", "misconception_crosslink", ["mis_id"])


def downgrade() -> None:
    op.drop_index("idx_misconception_crosslink_mis", table_name="misconception_crosslink")
    op.drop_index("idx_misconception_crosslink_kebab", table_name="misconception_crosslink")
    op.drop_table("misconception_crosslink")
