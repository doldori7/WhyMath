"""concept.recommended_visual_styles — 개념↔시각화 양식 매핑 컬럼 + visualization_style_enum

슬라이스 88 — 개념이 가장 잘 드러나는 교수학적 표현 양식(슬라이스 87 `VisualizationStyle` 16종)을
개념에 매핑하는 `concept.recommended_visual_styles visualization_style_enum[]` 컬럼을 추가한다.
`cognitive_type_enum[]` 동형(nullable·schema `default_factory=list`). 신규 native ENUM 타입
`visualization_style_enum`을 *본 마이그레이션이 소유*(생성·downgrade에서 drop). 기존 행은 NULL로
시작(점진 태깅). 인덱스 불필요(개념 단건 조회·전수 배치).

Revision ID: b5c6d7e8f9a0
Revises: a3b4c5d6e7f8
Create Date: 2026-06-10 01:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b5c6d7e8f9a0"
down_revision: str | None = "a3b4c5d6e7f8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# schema/enums.py VisualizationStyle(슬라이스 87)와 *정확히 일치*해야 한다(16종·한글 값).
_VISUALIZATION_STYLES: tuple[str, ...] = (
    "수직선",
    "함수그래프",
    "단위원",
    "평면도형",
    "입체도형",
    "넓이모델",
    "수형도",
    "부등식영역",
    "벡터도",
    "점화도",
    "통계차트",
    "산점도",
    "상자그림",
    "분포곡선",
    "접선도함수",
    "확률시뮬레이션",
)


def upgrade() -> None:
    # add_column은 create_table과 달리 enum 타입을 자동 생성하지 않으므로 명시 생성한다.
    postgresql.ENUM(*_VISUALIZATION_STYLES, name="visualization_style_enum").create(
        op.get_bind(), checkfirst=True
    )
    op.add_column(
        "concept",
        sa.Column(
            "recommended_visual_styles",
            postgresql.ARRAY(
                postgresql.ENUM(
                    *_VISUALIZATION_STYLES,
                    name="visualization_style_enum",
                    create_type=False,
                )
            ),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("concept", "recommended_visual_styles")
    # 본 마이그레이션이 만든 native ENUM 정리(checkfirst로 멱등).
    postgresql.ENUM(name="visualization_style_enum").drop(op.get_bind(), checkfirst=True)
