"""concept_visualization Overlay — 시각화 가능성 4분류 테이블 + visualizability_enum

구축 플레이북 Part 5(시각화 시스템) 검토 결과 도입. 개념의 *시각화 가능성*(직접/동적/추상/불가)은
개념 정체성이 아니라 시각화 계층의 판별 정보이므로(ADR concept_node_layering §1 "visualization
계층=노드 비내장"·CurriculumEntry Overlay 선례), Concept 노드에 컬럼을 넣지 않고 별도 Overlay
테이블 `concept_visualization`(PK `code`·loose ref·FK 없음)로 외부화한다. 한 행 존재=분류됨,
행 부재=미태깅(하위호환). 신규 native ENUM `visualizability_enum`은 본 마이그레이션이 소유한다.

설계 정본: `docs/architecture/05b_visualization_classification.md`.

Revision ID: d8e9f0a1b2c3
Revises: c7d8e9f0a1b2
Create Date: 2026-07-02 20:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d8e9f0a1b2c3"
down_revision: str | None = "c7d8e9f0a1b2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# schema/enums.py Visualizability와 *정확히 일치*해야 한다(4종·한글 값·멤버명==값).
_VISUALIZABILITY: tuple[str, ...] = (
    "직접",
    "동적",
    "부분",
    "추상",
)


def upgrade() -> None:
    # create_table은 컬럼 enum 타입을 자동 생성하나, checkfirst 멱등을 위해 명시 생성한다.
    viz_enum = postgresql.ENUM(*_VISUALIZABILITY, name="visualizability_enum")
    viz_enum.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "concept_visualization",
        sa.Column("code", sa.Text(), primary_key=True),
        sa.Column(
            "visualizability",
            postgresql.ENUM(*_VISUALIZABILITY, name="visualizability_enum", create_type=False),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("concept_visualization")
    # 본 마이그레이션이 만든 native ENUM 정리(checkfirst로 멱등).
    postgresql.ENUM(name="visualizability_enum").drop(op.get_bind(), checkfirst=True)
