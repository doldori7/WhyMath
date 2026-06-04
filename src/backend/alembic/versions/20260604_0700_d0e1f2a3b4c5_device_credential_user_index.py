"""device_credential composite user index (list_for_user sort optimization)

슬라이스 64 — `list_for_user`의 기본 접근 패턴(`WHERE user_id ORDER BY created_at DESC,
seq DESC` — slice 63 tie-break 포함) 복합 인덱스. slice 23의 단일 `ix_device_credential_
user_id`를 *대체*: 복합의 선두 컬럼 user_id가 단일 인덱스를 포섭(count_for_user·revoke의
user_id 필터도 prefix로 충족)하므로 중복 제거 → register INSERT 시 유지할 인덱스 1개 절감.
slice 60/61(deletion_audit·assessment user 인덱스)와 동형이나, device_credential은 기존
단일 user 인덱스가 있어 *추가가 아닌 대체*다.

slice 63 한계 ②("(user_id, created_at, seq) 복합 인덱스 미추가") 해소. last_used_at/
revoked_at 정렬은 이 인덱스 미적용(기본 정렬만 최적화·후속).

Revision ID: d0e1f2a3b4c5
Revises: c9d0e1f2a3b4
Create Date: 2026-06-04 07:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d0e1f2a3b4c5"
down_revision: str | None = "c9d0e1f2a3b4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 단일 user_id 인덱스 제거 — 복합이 포섭(선두 컬럼 user_id)
    op.drop_index(op.f("ix_device_credential_user_id"), table_name="device_credential")
    # 복합 인덱스 — list_for_user 기본 정렬(created_at DESC, seq DESC) 충족
    op.create_index(
        "idx_device_credential_user",
        "device_credential",
        [
            "user_id",
            sa.literal_column("created_at DESC"),
            sa.literal_column("seq DESC"),
        ],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_device_credential_user", table_name="device_credential")
    op.create_index(
        op.f("ix_device_credential_user_id"),
        "device_credential",
        ["user_id"],
        unique=False,
    )
