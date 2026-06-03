"""device_credential last_used_at

슬라이스 32 — verify 성공 시각 추적 컬럼 추가. "30일 미사용 자동 폐기" 정책·보안 이상
탐지 기반. CachedDeviceStore 사용 시 cache miss에서만 갱신(정밀도 ≈ TTL).

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-06-03 12:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5f6a7"
down_revision: str | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "device_credential",
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("device_credential", "last_used_at")
