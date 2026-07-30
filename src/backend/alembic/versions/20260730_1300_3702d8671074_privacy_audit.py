"""privacy audit table (SEC-09)

`docs/architecture/account_security_gap_review.md` D3 — 개인정보 감사 3종(반출·동의변경·
관리자접근)의 append-only 기록. `deletion_audit`(d4e5f6a7b8c9) 패턴을 그대로 답습한다:
`user_id`(행위자)는 **FK 아님**(plain UUID·사용자 삭제돼도 감사 잔존), `event_kind`는
`sa.String(32)`(네이티브 PG enum 미생성 — 코드 안전성은 Pydantic `AuditEventKind`가 확보).
`target_user_id`(행위 대상 — 관리자접근에서만 행위자와 다름)·`consent_scope`(동의변경 구분
메타)·`ip_hash`(sha256(salt+ip)·평문 IP 미저장)는 `deletion_audit`엔 없는 신규 컬럼이다.
삭제 이벤트는 여기 적재하지 않는다(`deletion_audit`가 삭제 감사의 단일 권위 — 이중 진실원천
금지, D3 판단 근거).

Revision ID: 3702d8671074
Revises: c5d6e7f0a2b3
Create Date: 2026-07-30 13:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "3702d8671074"
down_revision: str | None = "c5d6e7f0a2b3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "privacy_audit",
        sa.Column(
            "audit_id",
            sa.Uuid(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("target_user_id", sa.Uuid(), nullable=True),
        sa.Column("event_kind", sa.String(length=32), nullable=False),
        sa.Column("consent_scope", sa.String(length=32), nullable=True),
        sa.Column("ip_hash", sa.String(length=64), nullable=True),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("audit_id", name=op.f("pk_privacy_audit")),
    )
    op.create_index(
        "idx_privacy_audit_user",
        "privacy_audit",
        ["user_id", sa.literal_column("occurred_at DESC")],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_privacy_audit_user", table_name="privacy_audit")
    op.drop_table("privacy_audit")
