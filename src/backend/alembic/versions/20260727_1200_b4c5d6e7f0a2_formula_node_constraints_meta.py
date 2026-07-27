"""formula_node.constraints·mnemonic — 수식 메타 보강 (S4-06·additive·비파괴)

`docs/architecture/knowledge_module_gap_review.md` §3 D3. canonical-only 수식 노드
(`formula_node`·P5a)에 2필드 additive enrichment(P4a `misconception_catalog_enrichment` 동형):

  - `constraints` `ARRAY(Text)` NOT NULL server_default '{}' — 성립 조건·사용범위(자체작성
    텍스트·예 'a ≠ 0'·'진수 > 0'). 무조건 항등식은 빈 배열. **유도/증명 슬롯이 아니다** —
    유도는 Theorem/Proof 축(P6·D2) 위임(증명 축 이중화 금지·canonical-only 불변).
  - `mnemonic` `Text` nullable — 암기팁(자체작성·표준 정착 구절만·대부분 NULL — 날조 저작 금지).

additive·비파괴(변형/동치 슬롯 미도입·SymPy 재구현 금지 경계 불변·기존 행은 server_default가 백필).

Revision ID: b4c5d6e7f0a2
Revises: a9b8c7d6e5f4
Create Date: 2026-07-27 12:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b4c5d6e7f0a2"
down_revision: str | None = "a9b8c7d6e5f4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # constraints — 성립 조건·사용범위(NOT NULL·빈 배열 server_default·기존 25행 백필).
    op.add_column(
        "formula_node",
        sa.Column(
            "constraints",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::text[]"),
        ),
    )
    # mnemonic — 암기팁(nullable·표준 정착 구절만·대부분 NULL).
    op.add_column(
        "formula_node",
        sa.Column("mnemonic", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("formula_node", "mnemonic")
    op.drop_column("formula_node", "constraints")
