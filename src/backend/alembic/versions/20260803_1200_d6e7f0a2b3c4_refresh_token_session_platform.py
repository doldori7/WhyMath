"""refresh_token_session.platform — 세션 가시성 플랫폼 요약 컬럼 (SEC-10 D4)

`GET /v1/auth/sessions`(세션 목록)의 목적은 "낯선 기기 인지"이지 신원 추적이 아니다
(`docs/architecture/account_security_gap_review.md` D4 — 최소 수집 원칙). 그래서 IP·User-Agent
원문은 저장하지 않고, 로그인·리프레시 시점에 `api/auth.py`의 `_summarize_platform`이 요청의
`User-Agent` 헤더에서 도출한 좁은 범주(`"iOS"`/`"Android"`/`"Web"`)만 이 컬럼에 남긴다. 판별
불가면 `NULL`(오분류로 거짓 정보를 만들지 않음).

nullable — 기존 세션 행(이 마이그레이션 이전 발급분)은 플랫폼 정보가 없다(소급 채움 불가·
회고적 UA 추정 금지). 새 세션부터 점진 채움.

Revision ID: d6e7f0a2b3c4
Revises: 3702d8671074
Create Date: 2026-08-03 12:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d6e7f0a2b3c4"
down_revision: str | None = "3702d8671074"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "refresh_token_session",
        sa.Column("platform", sa.String(length=32), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("refresh_token_session", "platform")
