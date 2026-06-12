"""concept_node 테이블 — 개념 메타 UC 키 PG 프로젝션 (개념그래프 소비 슬라이스 1)

L1 개념그래프 *소비* 트랙의 첫 슬라이스 — 적재 아크(슬1~4)가 개념을 Neo4j(슬2)·pgvector(슬3)에
UC 키로 적재했고, 슬4 의미검색은 UC concept_id+similarity만 돌려준다. 이 마이그레이션은 슬1 산출
`graph.json`의 개념 *안전 메타*를 담을 **UC 키 PG 프로젝션 테이블**을 만든다 — 검색
enrichment(name_ko 등)·검수 게이팅(review_status)을 backend async-PG *조인*으로 하기 위한 백킹
(backend↔Neo4j 런타임 연결 없이 — 확정 설계 결정 "메타 브리지=PG 프로젝션").

PK=concept_id(UC TEXT)로 슬2 Neo4j 노드 키·슬3 `concept_embedding.concept_id`와 *동일 키 공간*
(삼중 store 단일 키). pgvector 확장과 무관하다(이 테이블엔 벡터 컬럼이 없다 — 메타만).

upgrade:
  - `concept_node` 테이블:
    - `concept_id`(TEXT PK) — Universal Concept ID, upsert 충돌 키(슬2/슬3과 동일 공간).
    - `name_ko`(TEXT NOT NULL)·`domain`(TEXT NOT NULL) — 표시·식별 안전 필드.
    - `review_status`(TEXT NOT NULL) — 'reviewed'/'pending' 게이팅 플래그(PG native enum 미생성 —
      concept_embedding 동형·plain text·graph.json use_enum_values로 이미 문자열).
    - `standard_codes`(TEXT[] NOT NULL DEFAULT '{}') — NCIC 성취기준 *코드* 배열(본문 아님).
    - `ccss_code`(TEXT NULL)·`difficulty_tier`(INTEGER NULL) — 매칭 코드·난이도층.
    - `metaphor`(TEXT NULL)·`accepted_expressions`(TEXT NULL) — 자체 작성 교수 주석(표시 가능).
    - `updated_at`(TIMESTAMPTZ NOT NULL DEFAULT now()) — 신선도.
  - **`description`·`formal_definition` 컬럼 없음**(redaction·우선순위 #2 — 성취기준 본문 근접
    필드를 *둘 곳 자체를 두지 않음*. graph.json 부재·적재기 미독·테이블 미수록의 삼중 방어).
  - **인덱스 없음**: 403행 규모·검색 enrichment는 UC IN/조인(PK 인덱스로 충분)·게이팅은 필터.
    스케일 시 review_status·domain 보조 인덱스가 정석이나 현 규모엔 과함(과장 금지).

downgrade (왕복 안전 — CI가 `downgrade base`→`upgrade head` 왕복 검증):
  - `concept_node` 테이블만 drop. pgvector 확장·다른 테이블 무관(이 테이블은 벡터·FK 0).

Revision ID: f9a0b1c2d3e4
Revises: e8f9a0b1c2d3
Create Date: 2026-06-12 12:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f9a0b1c2d3e4"
down_revision: str | None = "e8f9a0b1c2d3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 개념 메타 UC 키 프로젝션 — 안전 표시·게이팅 필드만(description·formal_definition 미수록).
    op.create_table(
        "concept_node",
        sa.Column("concept_id", sa.Text(), nullable=False),
        sa.Column("name_ko", sa.Text(), nullable=False),
        sa.Column("domain", sa.Text(), nullable=False),
        sa.Column("review_status", sa.Text(), nullable=False),
        sa.Column(
            "standard_codes",
            ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::text[]"),
        ),
        sa.Column("ccss_code", sa.Text(), nullable=True),
        sa.Column("difficulty_tier", sa.Integer(), nullable=True),
        sa.Column("metaphor", sa.Text(), nullable=True),
        sa.Column("accepted_expressions", sa.Text(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("concept_id", name=op.f("pk_concept_node")),
    )


def downgrade() -> None:
    # 테이블만 drop. 벡터 확장·FK 0이라 다른 객체 영향 없음(왕복 안전).
    op.drop_table("concept_node")
