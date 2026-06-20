"""misconception_catalog 테이블 (Phase B.2 M-id 오개념 콘텐츠 카탈로그 영속)

#290 코퍼스(`data/corpus/misconceptions_v1/misconceptions.json`·839 레코드·Collection JSON)를
적재할 영속 카탈로그를 만든다. ORM 정본은 `whymath_backend/db/models/misconception_catalog.py`,
계약은 `whymath_backend/schema/misconception_catalog.py`. 이 슬라이스는 ORM·계약·마이그레이션만
세우고 코퍼스 로더는 후속 슬라이스 몫이다.

별개 체계(FK 미생성): 이 테이블은 **M-id(예 'M0425') 콘텐츠 카탈로그**다. 기존 L4 탐지 엔진
(kebab-id 30종)·런타임 테이블(`misconception_hypothesis`·`evidence_links`·
`misconception_embedding`)과는 *별개 체계*이며 그들과 FK를 걸지 않는다(두 체계 공존).
`concept_src_id`·`standard_code`도 느슨참조라 FK가 아니다(해소는 로더 후속). 따라서 이
마이그레이션엔 ForeignKeyConstraint·CREATE TYPE이 전혀 없다(achievement_standard와 동형).

스키마(`misconception_catalog`):
  - mis_id(VARCHAR(16) PK = 의미 문자열·예 'M0425'·server_default 없음·로더가 채움).
  - canonical_statement/student_wrong_thinking/distractor_rule/correction_point(TEXT NULL·
    와이매스 자체 저작 본문 보유 허용).
  - error_type(VARCHAR(32) NULL·8종이나 닫힌 enum 강제는 파이프라인 책임).
  - difficulty(VARCHAR(8) NULL).
  - ccss_code/standard_code(VARCHAR(32) NULL)·concept_src_id(VARCHAR(64) NULL·느슨참조)·
    school_level(VARCHAR(32) NULL)·domain(VARCHAR(64) NULL)·subunit(VARCHAR(128) NULL)·
    mapping_confidence(VARCHAR(16) NULL)·provenance_note(VARCHAR(32) NULL).
  - mapping_score(NUMERIC(5,3) NULL·예 0.454~1.236).
  - UNIQUE는 mis_id PK뿐.
  - 인덱스: concept_src_id / standard_code / error_type.

downgrade(왕복 안전 — CI backend-migrations 잡이 `downgrade base`→`upgrade head` 왕복 검증):
  - 인덱스 → 테이블 순으로 drop. enum·FK 미생성이라 후처리 불요.

Revision ID: c4d5e6f7a8b9
Revises: b3c4d5e6f7a8
Create Date: 2026-06-20 10:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c4d5e6f7a8b9"
down_revision: str | None = "b3c4d5e6f7a8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── misconception_catalog (mis_id PK·M-id 콘텐츠 카탈로그·FK 없음) ──
    op.create_table(
        "misconception_catalog",
        # mis_id는 의미 문자열(UUID 아님) — server_default 없음(로더/스키마가 채움).
        sa.Column("mis_id", sa.String(length=16), nullable=False),
        # 본문 — 와이매스 자체 저작이라 보유 허용(redaction 불요).
        sa.Column("canonical_statement", sa.Text(), nullable=True),
        sa.Column("student_wrong_thinking", sa.Text(), nullable=True),
        sa.Column("distractor_rule", sa.Text(), nullable=True),
        sa.Column("error_type", sa.String(length=32), nullable=True),
        sa.Column("difficulty", sa.String(length=8), nullable=True),
        sa.Column("correction_point", sa.Text(), nullable=True),
        sa.Column("ccss_code", sa.String(length=32), nullable=True),
        # 느슨참조 — FK 아님(개념 코드 어휘 길이 64).
        sa.Column("concept_src_id", sa.String(length=64), nullable=True),
        # 느슨참조 — FK 아님.
        sa.Column("standard_code", sa.String(length=32), nullable=True),
        sa.Column("school_level", sa.String(length=32), nullable=True),
        sa.Column("domain", sa.String(length=64), nullable=True),
        sa.Column("subunit", sa.String(length=128), nullable=True),
        sa.Column("mapping_confidence", sa.String(length=16), nullable=True),
        # NUMERIC(5,3) — mapping_score float(예 0.454~1.236).
        sa.Column("mapping_score", sa.Numeric(precision=5, scale=3), nullable=True),
        sa.Column("provenance_note", sa.String(length=32), nullable=True),
        sa.PrimaryKeyConstraint("mis_id", name=op.f("pk_misconception_catalog")),
    )
    # 개념 코드로 카탈로그를 찾는 경로(느슨참조).
    op.create_index(
        "idx_misconception_catalog_concept",
        "misconception_catalog",
        ["concept_src_id"],
        unique=False,
    )
    # 성취기준 코드로 찾는 경로(느슨참조).
    op.create_index(
        "idx_misconception_catalog_standard",
        "misconception_catalog",
        ["standard_code"],
        unique=False,
    )
    # 오류 유형으로 필터.
    op.create_index(
        "idx_misconception_catalog_error_type",
        "misconception_catalog",
        ["error_type"],
        unique=False,
    )


def downgrade() -> None:
    # 인덱스 → 테이블 순으로 drop(왕복 안전). enum·FK 미생성이라 후처리 불요.
    op.drop_index(
        "idx_misconception_catalog_error_type",
        table_name="misconception_catalog",
    )
    op.drop_index(
        "idx_misconception_catalog_standard",
        table_name="misconception_catalog",
    )
    op.drop_index(
        "idx_misconception_catalog_concept",
        table_name="misconception_catalog",
    )
    op.drop_table("misconception_catalog")
