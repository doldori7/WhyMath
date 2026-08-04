"""defect_report table (RPT-01)

`docs/architecture/service_operations_gap_review.md` §3 D1 — 학생이 문항·AI응답·수식 오류를
신고할 경로가 스키마·API·UI 전부 0건이던 갭을 메운다. `deletion_audit`/`privacy_audit`
append-only 패턴을 답습하되 **`user_id` 컬럼을 만들지 않는다** — 결함 대장은 "누가"가 아니라
"무엇을" 신고했는지만 기록한다(미성년 PII 미저촉·보존파기 대상 아님·반출/삭제권 대상 아님이
구조적으로 성립). `category`는 `sa.String(32)`(네이티브 PG enum 미생성 — 코드 안전성은 Pydantic
`DefectCategory`가 확보, `AuditResourceType` 선례). `problem_id`는 FK 아님(plain UUID) —
문항이 나중에 삭제·재편돼도 신고 기록은 잔존해야 한다. 자유서술 필드 없음(v0는 카테고리 +
problem_id만). append-only — 이 마이그레이션은 UPDATE/DELETE 라우터를 전제하지 않는다.

`attempt_event`/`EventType`은 의도적으로 재사용하지 않는다(`EventType`은 네이티브 PG enum이라
값 추가에 별도 alembic이 필요해지고, `attempt_event`는 `privacy/retention.py`가 이미 3년
보존파기 대상으로 지정해 학생 데이터 파기와 함께 사라지는데 결함 대장은 콘텐츠 기록이라 그와
함께 사라지면 안 된다).

Revision ID: db8ae6d2d91c
Revises: d6e7f0a2b3c4
Create Date: 2026-08-03 13:59:00.636030
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "db8ae6d2d91c"
down_revision: str | None = "d6e7f0a2b3c4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "defect_report",
        sa.Column(
            "report_id",
            sa.Uuid(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("category", sa.String(length=32), nullable=False),
        # FK 아님(plain UUID) — 문항이 삭제·재편돼도 신고 기록 잔존(deletion_audit 설계 메모).
        sa.Column("problem_id", sa.Uuid(), nullable=True),
        sa.Column(
            "reported_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("report_id", name=op.f("pk_defect_report")),
    )
    op.create_index(
        "idx_defect_report_category",
        "defect_report",
        ["category", sa.literal_column("reported_at DESC")],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_defect_report_category", table_name="defect_report")
    op.drop_table("defect_report")
