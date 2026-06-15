"""refresh_token_session 테이블 (리프레시 토큰 서버측 취소 allowlist·OAuth-a3b)

a3 stateless 리프레시 토큰의 빈자리(만료 전 개별 취소 불가)를 메우는 백킹 테이블. 발급된 리프레시
토큰마다 1행(PK=토큰 jti)을 두어 `/v1/auth/refresh`가 존재·미취소를 확인(allowlist)하고
`/v1/auth/logout`이 revoked=true로 즉시 무효화(denylist)한다. ORM 정본은
`whymath_backend/db/models/refresh_token_session.py`(RefreshTokenSession). enum 없음(UUID·
TIMESTAMPTZ·Boolean 기본 타입).

스키마:
  - token_session_id(UUID PK = 리프레시 토큰 jti·앱 생성). server_default 없음 — 발급 코드가 명시.
  - user_id(UUID NOT NULL·FK user_profile.user_id) — 사용자별 일괄취소(a3c)·소유 검증.
  - issued_at(TIMESTAMPTZ NOT NULL·server_default now())·expires_at(TIMESTAMPTZ NOT NULL·앱 설정).
  - revoked(Boolean NOT NULL·server_default false)·revoked_at(TIMESTAMPTZ nullable).

인덱스:
  - idx_refresh_token_session_user(user_id, issued_at DESC) — 사용자별 세션 조회/일괄취소(a3c).

downgrade(왕복 안전 — CI 왕복 검증): 인덱스 → 테이블 순 drop. enum 없어 후처리 불요.

Revision ID: e4f5a6b7c8d9
Revises: d3e4f5a6b7c8
Create Date: 2026-06-15 02:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e4f5a6b7c8d9"
down_revision: str | None = "d3e4f5a6b7c8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "refresh_token_session",
        # PK = 리프레시 토큰 jti(앱 생성·server_default 없음 — 발급 코드가 토큰 클레임과 동시 설정).
        sa.Column("token_session_id", sa.Uuid(), nullable=False),
        # 사용자 결부 — user_profile FK(NOT NULL·일괄취소/소유검증).
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "issued_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        # 리프레시 토큰 만료(앱 설정) — 프루닝·감사용(실제 만료 게이트는 JWT exp).
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "revoked",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("token_session_id", name=op.f("pk_refresh_token_session")),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["user_profile.user_id"],
            name=op.f("fk_refresh_token_session_user_id_user_profile"),
        ),
    )
    # 사용자별 세션 조회/일괄취소(a3c) 접근 경로(device.idx_device_credential_user DESC 패턴 동형).
    op.create_index(
        "idx_refresh_token_session_user",
        "refresh_token_session",
        ["user_id", sa.literal_column("issued_at DESC")],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "idx_refresh_token_session_user",
        table_name="refresh_token_session",
    )
    op.drop_table("refresh_token_session")
