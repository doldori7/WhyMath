"""review_timer_event 테이블 생성 — HIT 검수 타이머 이벤트 계측기 (EOS-54).

`docs/standards/eos_verification_design_v1.md` §6이 동결한 주 기준 KPI **HIT(CU당 인간 개입
시간·중앙값 ≤4분)**의 측정 방법 "검수 타이머 이벤트(시작·종료·중단) 전수 자동 수집"의 영속
좌석. ★이 계측기가 없으면 12월 검증에서 잴 것이 없다(G1 차단 조건 — crosswalk §2 후보 #1).

**과거분 백필 없음(정직)**: 과거 검수(코퍼스 `review_status` 백필·#841 라벨)는 타이머 계측
없이 이뤄졌다 — 시간을 소급 날조하지 않는다. 빈 테이블만 만들고 수집은 배선 시점부터
(EOS-45 hint_usage 동형·additive·data migration 0건). 무계측 과거 판정은 집계
(`ops/hit_cu_metrics`)가 "미계측"으로 분리 보고한다(0분 위장 금지 — acceptance ④).

구조(ORM 정본 `db/models/review_timer_event.py`와 1:1):
  - PK `event_id` UUID `gen_random_uuid()`.
  - `review_session_id` UUID NOT NULL — 세션(sitting) 페어링 축(FK 아님 — 세션 정본 테이블
    부재·writer 발급 상관 id·FK 날조 금지).
  - `cu_slug` TEXT NOT NULL — CU 식별 축(폭 128은 schema 강제·DB는 TEXT 좌석).
  - `problem_id` UUID nullable FK → problem — 적재된 CU만 채움(needs_review 후보는 problem
    행이 없어 NULL — NOT NULL FK면 적재 전 검수가 기록 불가). GenerationLog.problem_id 동형.
  - `reviewer_id` TEXT NOT NULL — 검수 행위자 핸들. **학생 소유 축 아님**(user_id/student_id
    없음 — privacy 스윕 비대상 실측·erasure/retention/export 배선 불요 판정은 ORM docstring).
  - `event_type`/`verdict`/`failure_code`/`failure_note` TEXT — 폐쇄(3종/2종/F1~F8)는 schema
    강제·DB는 값만.
  - `elapsed_ms` INTEGER nullable — **미측정=NULL·server_default 0 날조 금지**(acceptance ④).
  - `occurred_at` TIMESTAMPTZ nullable(발생·미신고=NULL) / `recorded_at` TIMESTAMPTZ NOT NULL
    DEFAULT now()(수신) — EOS-48 발생/수신 분리 계약.
  - 인덱스 `(review_session_id)`·`(cu_slug, recorded_at DESC)`.

upgrade: 테이블·FK·인덱스 생성(additive). downgrade: 테이블 drop(제약·인덱스 동반) —
problem 테이블은 참조만 하므로 건드리지 않는다(대칭 유지).

Revision ID: 84c782415837
Revises: c9bc2555282e
Create Date: 2026-08-31 02:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "84c782415837"
down_revision: str | None = "c9bc2555282e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "review_timer_event",
        sa.Column(
            "event_id",
            sa.Uuid(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("review_session_id", sa.Uuid(), nullable=False),
        sa.Column("cu_slug", sa.Text(), nullable=False),
        sa.Column("problem_id", sa.Uuid(), nullable=True),
        sa.Column("reviewer_id", sa.Text(), nullable=False),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("verdict", sa.Text(), nullable=True),
        sa.Column("failure_code", sa.Text(), nullable=True),
        sa.Column("failure_note", sa.Text(), nullable=True),
        # 미측정=NULL — server_default 0 날조 금지(acceptance ④).
        sa.Column("elapsed_ms", sa.Integer(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["problem_id"],
            ["problem.problem_id"],
        ),
        sa.PrimaryKeyConstraint("event_id"),
    )
    op.create_index("idx_review_timer_session", "review_timer_event", ["review_session_id"])
    op.create_index(
        "idx_review_timer_cu",
        "review_timer_event",
        ["cu_slug", sa.literal_column("recorded_at DESC")],
    )


def downgrade() -> None:
    op.drop_index("idx_review_timer_cu", table_name="review_timer_event")
    op.drop_index("idx_review_timer_session", table_name="review_timer_event")
    op.drop_table("review_timer_event")
