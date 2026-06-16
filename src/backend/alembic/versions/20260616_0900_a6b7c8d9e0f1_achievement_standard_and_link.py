"""achievement_standard + concept_standard_link 테이블 (P1-2 성취기준 영속·개념↔성취기준 링크)

NCIC 성취기준(`achievement_standard`)과 개념↔성취기준 N:M 링크(`concept_standard_link`)의 영속
백킹을 만든다. ORM 정본은 `whymath_backend/db/models/achievement_standard.py`(AchievementStandard)·
`whymath_backend/db/models/concept_standard_link.py`(ConceptStandardLink), 계약은
`whymath_backend/schema/standard.py`. 이 슬라이스는 ORM·계약·마이그레이션만 세우고 jsonl 코퍼스
로더는 후속 슬라이스 몫이다(코퍼스 포맷 확정 전까지 보류).

PG native enum 미생성: `link_type`('직접'/'재매핑'/'준용')은 `VARCHAR(8)`로 담는다(닫힌 어휘 강제는
Pydantic Literal·to_schema 재검증 몫 — concept_node.review_status가 plain text였던 선례). 따라서
이 마이그레이션엔 `CREATE TYPE`/`DROP TYPE`이 없다(refresh_token_session·concept_node와 동형).

스키마(`achievement_standard`):
  - norm_id(VARCHAR(32) PK = 교육과정 간 유일 식별자·의미 문자열·server_default 없음·로더가 채움).
  - official_code(VARCHAR(32) NOT NULL·**비유일** — 교육과정 간 동일 code 가능).
  - curriculum_revision(VARCHAR(16) NOT NULL)·grade_band/school_type/subject/domain(VARCHAR NN).
  - sub_domain(VARCHAR NULL)·statement(TEXT NOT NULL·공공누리 1유형 본문 보유 허용).
  - commentary/big_idea(TEXT NULL)·effective_from(DATE NULL).
  - parent_codes(TEXT[] NOT NULL DEFAULT '{}')·source_url(TEXT NOT NULL)·source_document(TEXT NULL).
  - UNIQUE(curriculum_revision, official_code) — official_code 단독 비유일을 개정과 함께 유일화.
  - 인덱스: official_code 단일 / (curriculum_revision, domain).

스키마(`concept_standard_link`):
  - link_id(UUID PK·server_default gen_random_uuid()).
  - concept_code(VARCHAR(64) NOT NULL·느슨참조·**FK 아님** — 개념 식별자 공간 진화 중).
  - norm_id(VARCHAR(32) NOT NULL·**REAL FK** achievement_standard.norm_id·ON DELETE CASCADE).
  - link_type(VARCHAR(8) NOT NULL)·note(TEXT NULL).
  - UNIQUE(concept_code, norm_id, link_type) — (개념, 성취기준, 의미) 중복 링크 금지.
  - 인덱스: norm_id / concept_code.

downgrade(왕복 안전 — CI backend-migrations 잡이 `downgrade base`→`upgrade head` 왕복 검증):
  - 자식(concept_standard_link·FK 보유) → 부모(achievement_standard) 순으로 인덱스·테이블 drop.
    enum 미생성이라 후처리 불요.

Revision ID: a6b7c8d9e0f1
Revises: f5a6b7c8d9e0
Create Date: 2026-06-16 09:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a6b7c8d9e0f1"
down_revision: str | None = "f5a6b7c8d9e0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── 부모: achievement_standard (norm_id PK·official_code 비유일) ──
    op.create_table(
        "achievement_standard",
        # norm_id는 의미 문자열(UUID 아님) — server_default 없음(로더/스키마가 채움).
        sa.Column("norm_id", sa.String(length=32), nullable=False),
        # official_code는 교육과정 간 비유일 — UNIQUE 아님(아래 복합 UNIQUE로 유일화).
        sa.Column("official_code", sa.String(length=32), nullable=False),
        sa.Column("curriculum_revision", sa.String(length=16), nullable=False),
        sa.Column("grade_band", sa.String(), nullable=False),
        sa.Column("school_type", sa.String(), nullable=False),
        sa.Column("subject", sa.String(), nullable=False),
        sa.Column("domain", sa.String(), nullable=False),
        sa.Column("sub_domain", sa.String(), nullable=True),
        # 공공누리 1유형 — 성취기준 본문 보유 허용(검정교과서·EBS 본문 금지와 대비).
        sa.Column("statement", sa.Text(), nullable=False),
        sa.Column("commentary", sa.Text(), nullable=True),
        sa.Column("big_idea", sa.Text(), nullable=True),
        # DATE — 날짜만(TIMESTAMPTZ 아님).
        sa.Column("effective_from", sa.Date(), nullable=True),
        sa.Column(
            "parent_codes",
            ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::text[]"),
        ),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("source_document", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("norm_id", name=op.f("pk_achievement_standard")),
        # official_code 단독 비유일 → 개정과 함께 유일.
        sa.UniqueConstraint(
            "curriculum_revision",
            "official_code",
            name="uq_achievement_standard_revision_official_code",
        ),
    )
    # official_code로 성취기준을 찾는 경로(개정 미지정 광역 조회).
    op.create_index(
        "idx_achievement_standard_official_code",
        "achievement_standard",
        ["official_code"],
        unique=False,
    )
    # 개정 × 영역 필터(예: '2022 개정'의 '도형과 측정' 성취기준 목록).
    op.create_index(
        "idx_achievement_standard_revision_domain",
        "achievement_standard",
        ["curriculum_revision", "domain"],
        unique=False,
    )

    # ── 자식: concept_standard_link (norm_id 실 FK·CASCADE) ──
    op.create_table(
        "concept_standard_link",
        sa.Column(
            "link_id",
            sa.Uuid(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        # 개념 식별자 느슨참조 — FK 아님(Concept.code와 동일 String(64)).
        sa.Column("concept_code", sa.String(length=64), nullable=False),
        # 성취기준 실 FK — CASCADE(성취기준 삭제 시 링크도 삭제).
        sa.Column("norm_id", sa.String(length=32), nullable=False),
        sa.Column("link_type", sa.String(length=8), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("link_id", name=op.f("pk_concept_standard_link")),
        # (개념, 성취기준, 의미) 중복 링크 금지.
        sa.UniqueConstraint(
            "concept_code",
            "norm_id",
            "link_type",
            name="uq_concept_standard_link_concept_norm_type",
        ),
        sa.ForeignKeyConstraint(
            ["norm_id"],
            ["achievement_standard.norm_id"],
            name=op.f("fk_concept_standard_link_norm_id_achievement_standard"),
            ondelete="CASCADE",
        ),
    )
    # 성취기준 → 연결 개념 조회(FK 역방향).
    op.create_index(
        "idx_concept_standard_link_norm",
        "concept_standard_link",
        ["norm_id"],
        unique=False,
    )
    # 개념 → 연결 성취기준 조회.
    op.create_index(
        "idx_concept_standard_link_concept",
        "concept_standard_link",
        ["concept_code"],
        unique=False,
    )


def downgrade() -> None:
    # 자식(FK 보유) → 부모 순으로 drop(왕복 안전). enum 미생성이라 후처리 불요.
    op.drop_index(
        "idx_concept_standard_link_concept",
        table_name="concept_standard_link",
    )
    op.drop_index(
        "idx_concept_standard_link_norm",
        table_name="concept_standard_link",
    )
    op.drop_table("concept_standard_link")
    op.drop_index(
        "idx_achievement_standard_revision_domain",
        table_name="achievement_standard",
    )
    op.drop_index(
        "idx_achievement_standard_official_code",
        table_name="achievement_standard",
    )
    op.drop_table("achievement_standard")
