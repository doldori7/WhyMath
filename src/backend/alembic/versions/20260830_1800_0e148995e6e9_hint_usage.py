"""hint_usage 테이블 생성 — 힌트 횟수·레벨·열람시간 1급 데이터화 (EOS-45).

`docs/architecture/32_learning_history.md` §4가 확정한 신규 엔티티. `problem_attempt.used_hint`
(불리언)의 *병행* 정밀화 — 대체가 아니다(기존 소비자 `daily_hint_reliance_rate` 불변).

**과거분 백필 없음(의도적)**: 과거 힌트 이력은 `attempt_event`의 `힌트제공`(hint_level)·
`힌트요청` 이벤트로 부분 존재하나 hint_id·view_duration_ms가 없고, AI *공급* 이벤트와 학생
*열람* 기록은 의미가 다르다 — 승격 백필은 절반 날조라 하지 않는다. 빈 테이블만 만들고 수집은
배포 시점부터(EOS-32 answer_submission 동형·additive·data migration 0건).

구조(ORM 정본 `db/models/hint_usage.py`와 1:1 — EOS-32 관례 재사용):
  - PK `hint_usage_id` UUID `gen_random_uuid()`.
  - `(attempt_id, user_id)` NOT NULL **복합 FK** → problem_attempt(attempt_id, user_id)
    **ON DELETE CASCADE** — EOS-32 PR #902 P1 소유 정합 원칙을 처음부터 적용. 참조 대상
    UNIQUE `uq_problem_attempt_attempt_user`는 **EOS-32 리비전(8f0b8e906362)이 이미 생성 —
    여기서 재생성하지 않는다**(중복 생성 금지).
  - `user_id` NOT NULL FK → user_profile(복합 FK와 별도 — 계정 실재 강제·NO ACTION).
  - `hint_id` TEXT nullable — 느슨참조(힌트 정본 테이블 부재 실측·FK 날조 금지).
  - `hint_level` INTEGER NOT NULL — 폐쇄 1~4는 schema 강제(DB는 값만).
  - `requested_at` TIMESTAMPTZ NOT NULL DEFAULT now() — 보존 파기 축·자연 순서.
  - `view_duration_ms` INTEGER nullable — 계측 종료 신호 부재 케이스(미확정=NULL·0 날조 금지).
  - 인덱스 `(user_id, requested_at DESC)`·`(attempt_id)`.

upgrade: 테이블·복합 FK·인덱스 생성(additive). downgrade: 테이블 drop(제약·인덱스 동반) —
problem_attempt의 UNIQUE는 EOS-32 소유라 여기서 건드리지 않는다(대칭 유지).

Revision ID: 0e148995e6e9
Revises: 8f0b8e906362
Create Date: 2026-08-30 18:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0e148995e6e9"
down_revision: str | None = "8f0b8e906362"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "hint_usage",
        sa.Column(
            "hint_usage_id",
            sa.Uuid(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("attempt_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("hint_id", sa.Text(), nullable=True),
        sa.Column("hint_level", sa.Integer(), nullable=False),
        sa.Column(
            "requested_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("view_duration_ms", sa.Integer(), nullable=True),
        # EOS-32 소유 정합 관례 — 참조 대상 UNIQUE(uq_problem_attempt_attempt_user)는
        # 8f0b8e906362가 이미 생성(재사용·중복 생성 금지).
        sa.ForeignKeyConstraint(
            ["attempt_id", "user_id"],
            ["problem_attempt.attempt_id", "problem_attempt.user_id"],
            name="fk_hint_usage_attempt_owner",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["user_profile.user_id"],
        ),
        sa.PrimaryKeyConstraint("hint_usage_id"),
    )
    op.create_index(
        "idx_hint_usage_user",
        "hint_usage",
        ["user_id", sa.literal_column("requested_at DESC")],
    )
    op.create_index("idx_hint_usage_attempt", "hint_usage", ["attempt_id"])


def downgrade() -> None:
    op.drop_index("idx_hint_usage_attempt", table_name="hint_usage")
    op.drop_index("idx_hint_usage_user", table_name="hint_usage")
    op.drop_table("hint_usage")
