"""437-키 자산의 원자 축 이전 좌석 — atom_node.behavior_skills + concept_content.atom_codes (S0-2)

원자 백본 정합성 회복(로드맵 S0) Phase 4-ⓒ. 구 437 그래프 폐기(S0-4) 전에 437-키 잔존 자산
두 종의 *원자 축 좌석*을 신설한다(채움은 크로스워크 전파 CLI `l1/concept_atom_crosswalk`):

  ① `atom_node.behavior_skills` — #419가 저작한 concept→skill 매핑(`concept_node.behavior_skills`)
     의 원자 미러. skill_id 참조 배열(본문 아님·junction 아님·**신규 엣지 타입 0** —
     anti-explosion). concept_node 선례(`a1b2c3d4e5f0`)와 동형.
  ② `concept_content.atom_codes` — K-12 콘텐츠 행(구 437 개념코드 키)의 원자 연결(Phase 3 Slice 1
     `a8b9c0d1e2f3`가 "원자 연결은 Phase 4"로 예고한 좌석). 대학 행은 '{}' 유지(소단원코드가
     이미 원자 키 공간과 정합·다리 불요). FK 없는 느슨참조(standard_codes 동형).

기존 행은 빈 배열 `'{}'`로 시작(server_default) — 크로스워크 전파가 멱등 UPDATE로 채운다. additive.

Revision ID: b2c3d4e5f0a1
Revises: a1b2c3d4e5f0
Create Date: 2026-07-03 16:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5f0a1"
down_revision: str | None = "a1b2c3d4e5f0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ① 원자→skill 참조 배열(concept_node.behavior_skills 선례 동형·NOT NULL·빈 배열 기본).
    op.add_column(
        "atom_node",
        sa.Column(
            "behavior_skills",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::text[]"),
        ),
    )
    # ② K-12 콘텐츠→원자 code 참조 배열(standard_codes 선례 동형·NOT NULL·빈 배열 기본).
    op.add_column(
        "concept_content",
        sa.Column(
            "atom_codes",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::text[]"),
        ),
    )


def downgrade() -> None:
    # up의 역순 대칭 드롭(additive 컬럼 2개 — 데이터 이전 없음).
    op.drop_column("concept_content", "atom_codes")
    op.drop_column("atom_node", "behavior_skills")
