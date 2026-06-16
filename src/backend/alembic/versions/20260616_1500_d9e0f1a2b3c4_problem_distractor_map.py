"""problem.distractor_map — 객관식 오답 선지→오개념 매핑 컬럼 (JSONB, nullable)

P3b — `Problem`에 `distractor_map jsonb`(nullable)를 *가산적(additive)*으로 더한다. 객관식
오답 선지(distractor)를 정본 오개념 카탈로그 id로 매핑하는 rich list(원소:
choice_index·misconception_id·op_code?)를 싣는다. schema는 `list[DistractorEntry] | None`,
ORM은 `list[dict] | None`(model_dump→JSONB). 기존 50+필드 Problem·난이도 5축·signature_patterns·
저작권 source_type 게이트·P3a 8필드는 *불변*이고, 신규 컬럼은 nullable이라 기존 행·구성 무손상
(BREAKING-free).

`visualizations`(슬91)는 NOT NULL·server_default `'[]'::jsonb`였지만, `distractor_map`은
*없음*을 NULL로 표현(`source_detail`·`multiple_answers` 동형) — schema의
`distractor_map: ... | None = None`과 정합하고, "이 문항은 오답 매핑이 아직 없다"를 빈 배열이
아니라 NULL로 둔다(점진 채움). enum 타입 생성·정리 없음(자유 JSON).

**레이어 노트(CLAUDE.md 역방향 의존 금지)**: 이 컬럼은 L1(DB) 영속만 담당한다 — 저장된
misconception_id가 정본 카탈로그에 실재하는지의 *참조 무결성*은 L4 검증자
(`l4/misconception/validate.py`)가 콘텐츠 검증 시점(L3/L4)에 본다. DB CHECK를 만들지 않는다.

downgrade(왕복 안전 — CI backend-migrations 잡이 `downgrade base`→`upgrade head` 왕복 검증):
  - distractor_map 컬럼 drop. enum 타입 추가/정리 없음(자유 JSON이라 무관).

Revision ID: d9e0f1a2b3c4
Revises: c8d9e0f1a2b3
Create Date: 2026-06-16 15:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d9e0f1a2b3c4"
down_revision: str | None = "c8d9e0f1a2b3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ADD COLUMN distractor_map JSONB nullable(기존 행 무손상 — NULL=미매핑·점진 채움).
    # visualizations와 달리 server_default 없음(없음을 빈 배열 아닌 NULL로 표현 — schema 정합).
    op.add_column(
        "problem",
        sa.Column(
            "distractor_map",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("problem", "distractor_map")
