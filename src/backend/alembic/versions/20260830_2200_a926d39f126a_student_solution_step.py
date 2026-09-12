"""student_solution_step 테이블 생성 — 학생 풀이 step 정규 기록 (EOS-46).

판정 정본: `docs/architecture/adr/ADR-002-student-solution-step-entity.md` — attempt_event
event_type 확장(enum ALTER·경량 payload 계약 위반·FK 부재) 대신 별도 정규 엔티티. **WH-S
`solution_nodes`(MCTS 탐색 노드·시스템 데이터)와 무관하다**(ADR-002 명칭·책임 구분).

**과거분 백필 없음(의도적)**: 과거 step *내용*의 원천이 없다 — `problem_attempt.step_times`
는 시간만, telemetry 이벤트는 본문 없음. 빈 테이블만 만들고 수집은 배포·writer 배선
시점부터(EOS-32/45 동형·additive·data migration 0건).

구조(ORM 정본 `db/models/student_solution_step.py`와 1:1 — EOS-32/45 관례 재사용):
  - PK `student_step_id` UUID `gen_random_uuid()`.
  - `(attempt_id, user_id)` NOT NULL **복합 FK** → problem_attempt(attempt_id, user_id)
    **ON DELETE CASCADE** — 소유 정합(EOS-32 PR #902 P1). 참조 대상 UNIQUE
    `uq_problem_attempt_attempt_user`는 **EOS-32 리비전(8f0b8e906362)이 이미 생성 —
    재생성하지 않는다**(중복 생성 금지·EOS-45 동형).
  - `user_id` NOT NULL FK → user_profile(복합 FK와 별도·NO ACTION).
  - `UNIQUE(attempt_id, sequence_no)` — attempt 내 step 순번 유일(answer_submission 동형).
  - `expression` TEXT NOT NULL — 렌더러-중립 LaTeX 본문.
  - JSONB 3종(canonical_ast·validation nullable / concept_ids NOT NULL DEFAULT '[]') —
    ORM은 `none_as_null=True`(SEC-06).
  - `submitted_at` TIMESTAMPTZ NOT NULL DEFAULT now() — 보존 파기 축.
  - 인덱스 `(user_id, submitted_at DESC)` — privacy 경로.

upgrade: 테이블·복합 FK·UNIQUE·인덱스 생성(additive). downgrade: 테이블 drop(제약·인덱스
동반) — problem_attempt UNIQUE는 EOS-32 소유라 건드리지 않는다.

Revision ID: a926d39f126a
Revises: 0e148995e6e9
Create Date: 2026-08-30 22:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a926d39f126a"
down_revision: str | None = "0e148995e6e9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "student_solution_step",
        sa.Column(
            "student_step_id",
            sa.Uuid(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("attempt_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("sequence_no", sa.Integer(), nullable=False),
        sa.Column("expression", sa.Text(), nullable=False),
        sa.Column("canonical_ast", JSONB(none_as_null=True), nullable=True),
        sa.Column("validation", JSONB(none_as_null=True), nullable=True),
        sa.Column(
            "concept_ids",
            JSONB(none_as_null=True),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "submitted_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        # EOS-32 소유 정합 관례 — 참조 대상 UNIQUE(uq_problem_attempt_attempt_user)는
        # 8f0b8e906362가 이미 생성(재사용·중복 생성 금지).
        sa.ForeignKeyConstraint(
            ["attempt_id", "user_id"],
            ["problem_attempt.attempt_id", "problem_attempt.user_id"],
            name="fk_student_solution_step_attempt_owner",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["user_profile.user_id"],
        ),
        sa.PrimaryKeyConstraint("student_step_id"),
        sa.UniqueConstraint(
            "attempt_id", "sequence_no", name="uq_student_solution_step_attempt_seq"
        ),
    )
    op.create_index(
        "idx_student_solution_step_user",
        "student_solution_step",
        ["user_id", sa.literal_column("submitted_at DESC")],
    )


def downgrade() -> None:
    op.drop_index("idx_student_solution_step_user", table_name="student_solution_step")
    op.drop_table("student_solution_step")
