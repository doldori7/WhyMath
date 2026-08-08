"""dialogue.server_verified_completed_at — S3-32 learning-loop-closure

지금까지 코치 대화 흐름은 학생이 최종 답에 도달해도 서버가 그걸 검증·기록하지 않았다.
`l3/verify_final_answer.py`(서버검증 3상태) + `l4/completion.py`(Polya REVIEW 게이트)
조합이 완료를 확정한 시각을 이 컬럼에 남긴다.

- **additive·nullable**: 기존 행은 전부 NULL(미완료)로 남는다. 기존 데이터 백필 대상 없음.
- **멱등 가드로도 쓰인다**: `PolyaStage.REVIEW`는 self-loop 종착 단계라, 이 컬럼 없이 매 턴
  재판정하면 REVIEW 단계에 머무는 동안 턴마다 `ProblemAttempt`가 중복 적재된다. `api/coach.py`가
  "이미 NULL이 아니면 재판정하지 않는다" 가드로 이 컬럼을 읽는다.
- **클라 자가보고 `resolution`과 별도 신뢰 축**: `resolution`은 PATCH(클라 자가보고, 첫 기록
  우선)이 채운다(`api/me.py`) — 이 컬럼은 서버검증 축이라 `resolution`을 덮어쓰지 않는다.

마이그레이션 ID는 sliding-window hex 스킴을 따른다(임의 id는 alembic CycleDetected 유발 —
MEMORY 2026-07-03 실측). down_revision = 실제 head `090d254a5d43`(2026-08-08 착수 시점
`alembic heads` 실측 확인).

Revision ID: 7ef2b5a8e69e
Revises: 090d254a5d43
Create Date: 2026-08-08 12:00:00
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "7ef2b5a8e69e"
down_revision = "090d254a5d43"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """`dialogue.server_verified_completed_at` 추가(nullable TIMESTAMPTZ·기존 행 무영향)."""
    op.add_column(
        "dialogue",
        sa.Column("server_verified_completed_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    """컬럼 제거 — 서버검증 완료 시각 기록만 소실(원본 대화·턴·ProblemAttempt는 영향 없음)."""
    op.drop_column("dialogue", "server_verified_completed_at")
