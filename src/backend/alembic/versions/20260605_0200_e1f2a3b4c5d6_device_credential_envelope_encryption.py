"""device_credential 봉투 암호화 컬럼 (secret_encrypted·secret_nonce)

슬라이스 73 — AES-256-GCM 봉투 암호화(slice 72 `_crypto`)를 PgDeviceStore에 결선. secret을
마스터 키(DB 밖·env)로 암호화해 `secret_encrypted`(ciphertext)+`secret_nonce`(96-bit)에 저장
→ DB dump 단독 복호 불가. `secret_plain`을 nullable로 완화(암호화 행은 NULL·기존/비활성 행은
평문 유지·dual-read 폴백). 기존 평문 행은 그대로 verify(하위 호환)·후속 백필 슬라이스에서
재암호화 가능.

Revision ID: e1f2a3b4c5d6
Revises: d0e1f2a3b4c5
Create Date: 2026-06-05 02:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e1f2a3b4c5d6"
down_revision: str | None = "d0e1f2a3b4c5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "device_credential",
        sa.Column("secret_encrypted", sa.LargeBinary(), nullable=True),
    )
    op.add_column(
        "device_credential",
        sa.Column("secret_nonce", sa.LargeBinary(), nullable=True),
    )
    # 암호화 행은 secret_plain=NULL이므로 NOT NULL 제약 완화.
    op.alter_column(
        "device_credential", "secret_plain", existing_type=sa.String(length=128), nullable=True
    )


def downgrade() -> None:
    # 복원 전 암호화 행(secret_plain NULL)이 있으면 NOT NULL 복원이 실패하므로 주의 — 본
    # 마이그레이션 다운그레이드는 암호화 미사용(평문만) 상태에서만 안전.
    op.alter_column(
        "device_credential", "secret_plain", existing_type=sa.String(length=128), nullable=False
    )
    op.drop_column("device_credential", "secret_nonce")
    op.drop_column("device_credential", "secret_encrypted")
