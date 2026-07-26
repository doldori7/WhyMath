"""concept_visual_style Overlay — 권장 시각화 양식 이관 (ARCH-14 ③·Concept Purity 마지막 부채 청산)

슬라이스 88은 개념↔권장 시각화 양식 매핑을 `concept.recommended_visual_styles
visualization_style_enum[]` 컬럼으로 노드에 내장했다. 권장 양식(단위원·수형도·수직선 등)은 개념
정체성이 아니라 *시각화 계층*의 투영 정보이므로(ADR concept_node_layering §1 "visualization
계층=노드 비내장"·`CurriculumEntry`·`concept_visualization` Overlay 선례) Concept 노드에서 떼어
전용 Overlay 테이블 `concept_visual_style`(PK `code`·loose ref·FK 없음)로 외부화한다. 한 행
존재=양식 태깅됨, 행 부재=미태깅(리졸버 `[]`·하위호환).

시각화 *가능성* Overlay `concept_visualization`(그려야 하는가·4분류)과는 **다른 축**(양식='무엇을')
이라 그 테이블에 얹지 않고 전용 테이블을 신설한다.

native ENUM `visualization_style_enum`은 슬88 마이그레이션 `b5c6d7e8f9a0`이 *이미 소유*하므로 본
마이그레이션은 그 타입을 **재사용**한다(create_type=False·중복 CREATE TYPE 금지). 컬럼 drop 규약
(f3a4b5c6d7e8·f1a2b3c4d5e7 선례)에 따라 enum 타입은 drop하지 않는다(컬럼/테이블만 조작). 데이터
이관 스텝 없음 — `concept.recommended_visual_styles`는 전량 NULL(로더 미설정·코퍼스 부재)이었다.

설계 정본: `docs/architecture/05b_visualization_classification.md`·ARCH-14 잔여 하드닝.

Revision ID: a9b8c7d6e5f4
Revises: f1a2b3c4d5e7
Create Date: 2026-07-26 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a9b8c7d6e5f4"
down_revision: str | None = "f1a2b3c4d5e7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# schema/enums.py VisualizationStyle(슬라이스 87)와 *정확히 일치*해야 한다(16종·한글 값).
# 타입은 이미 `b5c6d7e8f9a0`이 생성·소유 — 여기선 create_type=False로 *참조*만 한다.
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
    # (a) 전용 Overlay 테이블 신설 — enum은 기존 `visualization_style_enum` 재사용(create_type=
    #     False·중복 CREATE TYPE 금지·`b5c6d7e8f9a0` 소유). code PK·loose ref(FK 없음)·
    #     recommended_styles NOT NULL(행 존재=태깅됨).
    op.create_table(
        "concept_visual_style",
        sa.Column("code", sa.Text(), primary_key=True),
        sa.Column(
            "recommended_styles",
            postgresql.ARRAY(
                postgresql.ENUM(
                    *_VISUALIZATION_STYLES,
                    name="visualization_style_enum",
                    create_type=False,
                )
            ),
            nullable=False,
        ),
    )
    # (b) 노드 컬럼 제거 — 권장 양식은 이제 Overlay가 단일 진실(Concept Purity). 데이터 이관 없음
    #     (전량 NULL). enum 타입은 drop하지 않는다(컬럼만 drop 규약·f3a4b5c6d7e8 선례).
    op.drop_column("concept", "recommended_visual_styles")


def downgrade() -> None:
    # 왕복 안전 — 원래 정의(nullable enum[]·create_type=False)로 노드 컬럼 복원 후 Overlay 제거.
    # 데이터는 전량 NULL이었으므로 손실 0. enum 타입은 그대로 둔다(`b5c6d7e8f9a0` 소유).
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
    op.drop_table("concept_visual_style")
