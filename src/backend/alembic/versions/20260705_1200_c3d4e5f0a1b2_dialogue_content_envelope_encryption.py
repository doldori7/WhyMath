"""dialogue_turn 대화 본문 봉투 암호화 컬럼 (content_encrypted·content_nonce)

감사상환 #2 — 미성년 대화 본문(`dialogue_turn.content`) at-rest 봉투 암호화(AES-256-GCM,
`_crypto`)를 결선. 본문을 마스터 키(DB 밖·env)로 암호화해 `content_encrypted`(ciphertext)+
`content_nonce`(96-bit)에 저장 → DB dump 단독 복호 불가(CLAUDE.md 절대 금기 '미성년 채팅 평문
저장 금지'의 저장계층 시행). device_credential.secret_encrypted/secret_nonce 선례 미러.

`content`는 이미 nullable(생성 마이그레이션 bb30b816083d `nullable=True`)이라 별도 완화 불요 —
암호화 행은 content=NULL, 기존/암호화 비활성 행은 평문 유지(dual-read 폴백). 기본은 키 미설정
평문 폴백이라 기존 배포·CI 무영향(점진 도입). 후속 백필(dialogue_content_backfill) 재암호화 가능.

Revision ID: c3d4e5f0a1b2
Revises: b2c3d4e5f0a1
Create Date: 2026-07-05 12:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c3d4e5f0a1b2"
down_revision: str | None = "b2c3d4e5f0a1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "dialogue_turn",
        sa.Column("content_encrypted", sa.LargeBinary(), nullable=True),
    )
    op.add_column(
        "dialogue_turn",
        sa.Column("content_nonce", sa.LargeBinary(), nullable=True),
    )
    # content는 이미 nullable(생성 마이그레이션)이라 alter_column 불요 — 암호화 행 content=NULL.


def downgrade() -> None:
    op.drop_column("dialogue_turn", "content_nonce")
    op.drop_column("dialogue_turn", "content_encrypted")
