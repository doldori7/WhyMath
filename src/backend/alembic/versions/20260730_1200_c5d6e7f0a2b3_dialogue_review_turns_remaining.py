"""dialogue.review_turns_remaining — 완료 상태머신(S3-27·원 S3-10 완료를 풀이 제출에 통합)

정답 도달 후 완료 전 남은 *돌아보기(메타인지) 턴 수*를 세션(dialogue)에 둔다. >0이면 돌아보기
대기(review_pending)·0이면 아님. 완료 여부 자체는 기존 `attempt_id` 존재로 판정(완료 시 링크·
재완료 가드). 상태머신은 `l4/completion.py`, 결선은 `api/coach.py`(create_session·append_turns).

`server_default 0`이라 기존 행은 자동으로 "돌아보기 아님"이 되고(백필 불요), 기능 플래그
(`l4_solution_completion_enabled`) off면 아예 읽지도 않아 완전 되돌리기 가능(점진 도입·회귀 0).

**재채번 메모**: 원본 리비전 `d5e6f0a1b2c3`(원 S3-10, down `c4d5e6f0a1b2`)는 main이 이미
`pedagogy_pack_dsl`(무관한 다른 작업)에 같은 ID를 써버려 그대로 재사용하면 충돌한다. 이 리비전은
회수 시점(2026-07-30) main의 실제 alembic head `b4c5d6e7f0a2`(formula_node_constraints_meta) 위에
sliding-window hex 스킴으로 새로 채번했다(`versions/` 전수 grep 무충돌 확인).

Revision ID: c5d6e7f0a2b3
Revises: b4c5d6e7f0a2
Create Date: 2026-07-30 12:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c5d6e7f0a2b3"
down_revision: str | None = "b4c5d6e7f0a2"
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
