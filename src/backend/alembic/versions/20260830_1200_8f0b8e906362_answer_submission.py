"""answer_submission 테이블 생성 — attempt 내 다회 제출 시퀀스 정규화 (EOS-32).

`docs/architecture/32_learning_history.md` §4가 확정한 신규 엔티티. `problem_attempt.
student_answer`는 최종값 1개만 담아 중간 제출(오답 → 오답 → 정답)의 오개념 신호가 손실된다 —
이 테이블이 제출 시퀀스를 1급 데이터로 영속한다(오개념 시스템 `evidence_links`의 핵심 입력).

**과거분 백필 없음(의도적)**: `attempt_event`의 `답입력` payload(`ResponseLatencyEventData`)는
응답 본문·채점 결과를 담지 않는 지연 신호라 과거 시퀀스를 이벤트에서 재구성하면 날조다. 이
마이그레이션은 빈 테이블만 만들고 수집은 배포 시점부터 시작한다(additive — 기존 데이터 무영향·
data migration 0건. 이관·병행 전략 = 32_learning_history §4).

구조(ORM 정본 `db/models/answer_submission.py`와 1:1):
  - PK `submission_id` UUID `gen_random_uuid()`.
  - `attempt_id` NOT NULL FK → problem_attempt **ON DELETE CASCADE**(attempt 삭제 시 자식 제출
    동반 제거 — slice 56 dialogue_turn 선례).
  - `user_id` NOT NULL FK → user_profile(NO ACTION — 삭제권은 앱레벨 `_ERASURE_PLAN`이 자식
    우선 명시 삭제·`problem_attempt.user_id` 동형).
  - `UNIQUE(attempt_id, sequence_no)` — attempt 내 제출 순번 유일(dialogue_turn 선례).
  - JSONB 3종(canonical_ast·grading_result·error_analysis) — ORM은 `none_as_null=True`(SEC-06).
  - `submitted_at` TIMESTAMPTZ NOT NULL DEFAULT now() — 보존 파기(`_RETENTION_PLAN`) 축.
  - 인덱스 `(user_id, submitted_at DESC)` — 학생 단위 최근순 조회·privacy 경로.

upgrade: 테이블·PK·FK·UNIQUE·인덱스 생성(additive). downgrade: 테이블 drop(제약·인덱스 동반).

Revision ID: 8f0b8e906362
Revises: d7e8f1a2b4c6
Create Date: 2026-08-30 12:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8f0b8e906362"
down_revision: str | None = "d7e8f1a2b4c6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "answer_submission",
        sa.Column(
            "submission_id",
            sa.Uuid(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("attempt_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("sequence_no", sa.Integer(), nullable=False),
        sa.Column("response_type", sa.String(length=32), nullable=False),
        sa.Column("raw_response", sa.Text(), nullable=True),
        sa.Column("latex", sa.Text(), nullable=True),
        sa.Column("canonical_ast", JSONB(none_as_null=True), nullable=True),
        sa.Column("grading_result", JSONB(none_as_null=True), nullable=True),
        sa.Column("error_analysis", JSONB(none_as_null=True), nullable=True),
        sa.Column(
            "submitted_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["attempt_id"],
            ["problem_attempt.attempt_id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["user_profile.user_id"],
        ),
        sa.PrimaryKeyConstraint("submission_id"),
        sa.UniqueConstraint("attempt_id", "sequence_no", name="uq_answer_submission_attempt_seq"),
    )
    op.create_index(
        "idx_answer_submission_user",
        "answer_submission",
        ["user_id", sa.literal_column("submitted_at DESC")],
    )


def downgrade() -> None:
    op.drop_index("idx_answer_submission_user", table_name="answer_submission")
    op.drop_table("answer_submission")
