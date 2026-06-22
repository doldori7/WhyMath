"""concept_content 테이블 — 콘텐츠 4종 code 키 PG 프로젝션 (원자 마이그레이션 Phase 3 Slice 1)

원자 백본 마이그레이션 Phase 3 Slice 1. Phase 3가 이미 캡처·커밋한 콘텐츠 코퍼스
(`concept_content_v1`·K-12 개념 437 + `concept_content_university_v1`·대학 소단원 409)의
**콘텐츠 4종**(은유·오개념·정식정의·허용표현)과 설명·암기카드를 담을 **code 키 PG 프로젝션
테이블**을 만든다 — 학습 장면(L4 코칭·L5 표시·L6 게이팅)이 backend 조인으로 콘텐츠를 끌어쓰기
위한 백킹(`atom_node`/`concept_node` 동일 설계 철학·신규 테이블이라 additive·무영향).

`concept_node`(UC 키·loose metaphor/accepted_expressions만)는 *건드리지 않는다*. PK는 `code`
(K-12=구 437 개념코드 예 'N1'·'A1' / 대학=소단원코드 예 'CALC1-U1-S1'·겹침 0)이고 `scope`
('K-12'|'대학')로 구분한다. FK 0(loose ref·K-12 코드↔원자 연결은 Phase 4 크로스워크).

upgrade:
  - `concept_content` 테이블:
    - `code`(TEXT PK)·`scope`(TEXT NOT NULL·K-12|대학)·`name`(TEXT NOT NULL)·`subject`
      (TEXT NOT NULL) — 식별·구분·표시·필터.
    - `unit`(TEXT NULL) — 단원/영역.
    - `metaphor`·`misconception`·`formal_definition_internal`·`accepted_expressions`(TEXT NULL)
      — 콘텐츠 4종(전량 자체작성·보유 허용). 정식정의는 *학생 비노출*(노출 게이팅은 소비계층).
    - `explanation`(TEXT NULL) — 설명(연결 맥락).
    - `standard_codes`(TEXT[] NOT NULL DEFAULT '{}') — NCIC 성취기준 *코드* 배열(K-12만·본문 아님).
    - `flashcards`(JSONB NOT NULL DEFAULT '[]') — 암기카드 dict 배열(front/back/mnemonic 등).
    - `review_status`(TEXT NOT NULL) — 'ai_estimated' 게이팅 플래그(콘텐츠는 AI 추정·검수필요·정직
      표기·PG native enum 미생성·plain text·atom_node 동형).
    - `updated_at`(TIMESTAMPTZ NOT NULL DEFAULT now()) — 신선도.
  - **인덱스 2종**: `ix_concept_content_scope`(K-12/대학 필터)·`ix_concept_content_subject`
    (과목 필터) — 콘텐츠 서빙·검수 빈번 필터.
  - K-12 성취기준 *본문*은 코퍼스에 없고(standard_codes 코드만 다리) 이 테이블도 본문 컬럼이 없다.

downgrade (왕복 안전 — CI가 `downgrade base`→`upgrade head` 왕복 검증):
  - `concept_content` 테이블만 drop(인덱스 포함). native ENUM 0(전부 TEXT)·FK 0이라 객체 무관.

Revision ID: a8b9c0d1e2f3
Revises: f7a8b9c0d1e2
Create Date: 2026-06-22 12:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY, JSONB

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a8b9c0d1e2f3"
down_revision: str | None = "f7a8b9c0d1e2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 콘텐츠 4종 code 키 프로젝션 — 자체작성 콘텐츠 + 암기카드(native ENUM 0·전부 TEXT/JSONB·FK 0).
    op.create_table(
        "concept_content",
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("scope", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("subject", sa.Text(), nullable=False),
        sa.Column("unit", sa.Text(), nullable=True),
        sa.Column("metaphor", sa.Text(), nullable=True),
        sa.Column("misconception", sa.Text(), nullable=True),
        sa.Column("formal_definition_internal", sa.Text(), nullable=True),
        sa.Column("accepted_expressions", sa.Text(), nullable=True),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column(
            "standard_codes",
            ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::text[]"),
        ),
        sa.Column(
            "flashcards",
            JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("review_status", sa.Text(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("code", name=op.f("pk_concept_content")),
    )
    # 필터 보조 인덱스 — scope(K-12/대학)·subject(과목) (콘텐츠 서빙·검수 빈번 필터).
    op.create_index("ix_concept_content_scope", "concept_content", ["scope"])
    op.create_index("ix_concept_content_subject", "concept_content", ["subject"])


def downgrade() -> None:
    # 인덱스 → 테이블 drop. native ENUM·FK 0이라 다른 객체 영향 없음(왕복 안전).
    op.drop_index("ix_concept_content_subject", table_name="concept_content")
    op.drop_index("ix_concept_content_scope", table_name="concept_content")
    op.drop_table("concept_content")
