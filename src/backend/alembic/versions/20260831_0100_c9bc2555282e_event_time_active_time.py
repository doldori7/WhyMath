"""event_time/ingested_at 분리 + 실측 active/idle 시간 좌석 — 기존 3테이블 ALTER (EOS-48).

`docs/architecture/32_learning_history.md` §7(시간 모델)의 착지. 신규 테이블 없음 — 기존
테이블에 nullable 컬럼만 더한다(**additive·기존 데이터 비파괴**: 기존 행은 전부 NULL 유지,
기존 writer·소비자 무영향).

실측 근거(컬럼 배치가 비대칭인 이유 — 기존 시각 컬럼의 의미가 테이블마다 다르다):
  - `attempt_event.event_at` — 전 writer(api/coach.py·interactions.py)가 서버 `now(UTC)`를
    넣는다 = **수신 시각**. 따라서 *발생* 쪽(`event_time`)만 추가한다.
  - `problem_attempt.started_at/ended_at` — 클라이언트 신고 = **발생 시각**. `created_at`은
    server_default지만 from_schema 경유 덮어쓰기 가능이라 수신을 보장하지 않는다. 따라서
    *수신* 쪽(`ingested_at`)을 추가한다.
  - `learning_session`/`problem_attempt`의 `active_seconds`/`idle_seconds` — 경과(elapsed)와
    별개의 *실측* 활동/공백 좌석("측정된 것만 적재" — §7).

**server_default를 달지 않는 이유(날조 방지)**: `ADD COLUMN ... DEFAULT now()`는 PG가 기존
행에 마이그레이션 시각을 채운다 — 과거 이벤트의 수신·발생 시각을 지금 시각으로 백필하는
날조다. NULL=미기록이 정직한 상태이며 신규 writer가 채운다(백필 금지는 32 §4 EOS-48 항).

**ADR-001 재확인(hypertable 전환 무충돌)**: attempt_event에 nullable 컬럼 추가는 파티션 키
(`event_at`)·복합 PK를 건드리지 않는다 — `create_hypertable` 전환 절차(ADR-001 예약)는 기존
컬럼 목록과 무관하게 동작하고, 본 컬럼은 NULL 지배적이라 압축 부담도 미미하다(ADR-001 추기
2026-08-31 참조).

upgrade: 3테이블에 컬럼 add(전부 nullable·default 없음). downgrade: 같은 컬럼 drop(대칭 —
기존 컬럼·데이터 불변).

Revision ID: c9bc2555282e
Revises: a926d39f126a
Create Date: 2026-08-31 01:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c9bc2555282e"
down_revision: str | None = "a926d39f126a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # attempt_event — 발생 시각 분리(event_at은 실측상 수신 시각 — 재정의 없음·ADR-001 추기).
    op.add_column(
        "attempt_event",
        sa.Column("event_time", sa.DateTime(timezone=True), nullable=True),
    )
    # problem_attempt — 수신 시각 분리(발생은 기존 started_at/ended_at 클라 신고) + 실측 시간.
    op.add_column(
        "problem_attempt",
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column("problem_attempt", sa.Column("active_seconds", sa.Integer(), nullable=True))
    op.add_column("problem_attempt", sa.Column("idle_seconds", sa.Integer(), nullable=True))
    # learning_session — 실측 활동/공백(경과 duration_seconds와 별개 축·측정된 것만).
    op.add_column("learning_session", sa.Column("active_seconds", sa.Integer(), nullable=True))
    op.add_column("learning_session", sa.Column("idle_seconds", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("learning_session", "idle_seconds")
    op.drop_column("learning_session", "active_seconds")
    op.drop_column("problem_attempt", "idle_seconds")
    op.drop_column("problem_attempt", "active_seconds")
    op.drop_column("problem_attempt", "ingested_at")
    op.drop_column("attempt_event", "event_time")
