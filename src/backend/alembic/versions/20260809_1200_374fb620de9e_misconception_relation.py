"""misconception_relation 테이블 생성 — 오개념 전용 관계셋(caused_by·variant_of·개념그래프 격리).

`MISC-04`(04c §6 Level2 해소). 오개념 A ↔ 오개념 B의 관계만 다루는 물리적으로 격리된 신규
테이블이다(개념 그래프 `concept_edge`와 완전 분리 — 04e_misconception_remediation_design.md
§2-3). 복합 PK `(from_mis_id, relation_type, to_mis_id)` — 서로게이트 PK 없음(`problem_relation`
선례와 동형). 양쪽 FK 모두 `misconception_catalog.mis_id`만 가리키고 개념 테이블 FK는 0개다.
`relation_type`은 닫힌 2종(`caused_by`/`variant_of`)이나 DB CHECK가 아니라 schema Literal이
강제한다(`misconception_crosslink.link_type` 선례 — DB 컬럼은 값만 담는 String).

upgrade: 테이블·PK·FK(CASCADE)·역방향 인덱스 생성(additive — 기존 데이터 무영향).
downgrade: 테이블 drop(인덱스·제약 동반 제거).

Revision ID: 374fb620de9e
Revises: c6d7e8f1a2b4
Create Date: 2026-08-09 12:00:00.000000

**down_revision 재지정(회수 시)**: 원 브랜치(`claude/human-bottleneck-tasks-6dszy0`)에서는
`7ef2b5a8e69e`(S3-32 `dialogue.server_verified_completed_at`) 위에 쌓여 있었으나, 그 리비전은
main에 없다(S3-32는 별도 구현으로 경합 중). 이 마이그레이션은 `misconception_catalog`만
FK로 참조하는 신규 테이블 생성이라 다른 리비전과 순서 의존이 전혀 없으므로, 회수 시점
main의 실제 head(`c6d7e8f1a2b4`)로 재지정해 독립 착륙시킨다.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "374fb620de9e"
down_revision: str | None = "c6d7e8f1a2b4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "misconception_relation",
        sa.Column("from_mis_id", sa.String(length=32), nullable=False),
        sa.Column("relation_type", sa.String(length=16), nullable=False),
        sa.Column("to_mis_id", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(
            ["from_mis_id"],
            ["misconception_catalog.mis_id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["to_mis_id"],
            ["misconception_catalog.mis_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("from_mis_id", "relation_type", "to_mis_id"),
    )
    op.create_index("idx_misconception_relation_to", "misconception_relation", ["to_mis_id"])


def downgrade() -> None:
    op.drop_index("idx_misconception_relation_to", table_name="misconception_relation")
    op.drop_table("misconception_relation")
