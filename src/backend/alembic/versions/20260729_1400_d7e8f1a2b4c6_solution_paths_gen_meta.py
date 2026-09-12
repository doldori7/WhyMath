"""solution_paths.gen_meta 추가 — 다중 풀이 생성 주관 메타 단일 JSONB 좌석 (S4-10·D2)

`docs/architecture/solution_module_gap_review.md` §3 D2. 다중 풀이 생성 파이프라인
(`l3/multi_solution.py`)이 산출하는 주관 메타(elegance·educational_value·difficulty·
key_insight·comparison)를 **JSONB 1컬럼**으로 영속한다(컬럼 폭발 방지 — acceptance
"저장 좌석은 최소로"). 내부에 `review_status="ai_estimated"`를 항상 동반해 게이팅한다 —
학생 대면 서빙 결선 0(§4-⑥ 유보·검수 전 노출 금지). nullable — 기존 행(승격 어댑터 경유
레거시 경로)은 NULL 그대로(비파괴 additive).

JSONB Python None → SQL NULL 방침(SEC-06 `none_as_null` 전수 거버넌스)은 ORM 선언이
강제한다(`db/models/solution_path.py`).

Revision ID: d7e8f1a2b4c6
Revises: fad7f750090d
Create Date: 2026-07-29 14:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d7e8f1a2b4c6"
down_revision: str | None = "fad7f750090d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 생성 주관 메타 단일 JSONB 좌석 — nullable additive(기존 행·응답 비파괴).
    op.add_column(
        "solution_paths",
        sa.Column("gen_meta", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    # up의 정확한 역(대칭) — 컬럼 제거.
    op.drop_column("solution_paths", "gen_meta")
