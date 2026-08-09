"""dialogue.review_turns_remaining — 완료 상태머신 돌아보기 턴 카운터 (S3-32·additive·비파괴)

`l4/completion.py`(완료를 풀이 제출에 통합 — 정답 도달 시 Polya 돌아보기 1턴 경유 후 완료)의
세션 영속 상태. 정답 도달 후 완료 전 *남은 돌아보기(메타인지) 턴 수*를 담는다 — >0이면 돌아보기
대기(review_pending)·0/NULL이면 아님. 완료 여부 자체는 기존 `dialogue.attempt_id`(slice 56 이미
존재) 존재로 판정하므로 별도 완료 플래그 컬럼은 두지 않는다.

additive·비파괴: nullable Integer·server_default 0 — 기존 행은 전부 0(돌아보기 아님)으로 채워져
기존 동작에 영향이 없다(다운그레이드도 컬럼 제거만·데이터 손실 없음).

Revision ID: d1e2f3c4b5a6
Revises: 374fb620de9e
Create Date: 2026-08-07 13:05:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d1e2f3c4b5a6"
down_revision: str | None = "374fb620de9e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "dialogue",
        sa.Column(
            "review_turns_remaining",
            sa.Integer(),
            nullable=True,
            server_default=sa.text("0"),
        ),
    )


def downgrade() -> None:
    op.drop_column("dialogue", "review_turns_remaining")
