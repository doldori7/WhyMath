"""atom_node 테이블 — 원자 메타 code 키 PG 프로젝션 (원자 마이그레이션 Phase 2a)

원자 백본 마이그레이션 Phase 2a. Phase 1이 원자 코퍼스(`graph.json`·2,697 노드)를 backend
`concept`/`concept_edge`에 *런타임 최소 식별*만 적재했고, 풍부 원자 메타(인지축·노드유형·학교급·
전이·원자성·연결성취기준)는 코퍼스에 보존돼 있었다. 이 마이그레이션은 그 *안전 메타*를 담을
**code 키 PG 프로젝션 테이블**을 만든다 — 검색 enrichment·필터·검수 게이팅을 backend async-PG
조인으로 하기 위한 백킹(`concept_node` 동일 설계 철학·신규 테이블이라 additive·무영향).

`concept_node`(UC 키·difficulty_tier 0~24·domain NOT NULL)는 *건드리지 않는다* — 원자는 의미가
다르다(code 키·난이도 1~5·subject_area). 그래서 재키잉이 아닌 *신규 테이블*이다.

upgrade:
  - `atom_node` 테이블:
    - `code`(TEXT PK) — 원자ID/소단원코드/단원코드(backend `concept.code` 공간·upsert 충돌 키).
    - `name_ko`(TEXT NOT NULL)·`level`(TEXT NOT NULL) — 표시·계층 식별(단원/소단원/세부개념).
    - `parent_code`(TEXT NULL)·`school_level`(TEXT NULL)·`subject_area`(TEXT NULL)·
      `subunit_code`(TEXT NULL) — 계층·학교급·영역·소단원 코드(필터·식별·코드는 사실정보).
    - `cognitive_type`(TEXT NULL·인지축)·`node_type`(TEXT NULL·노드유형)·`misconception_type`
      (TEXT NULL·오개념유형) — 자체 택소노미 라벨. **PG native enum 미생성**(plain TEXT·
      concept_node.review_status 동형·억지 enum 결합 회피).
    - `intrinsic_difficulty`(INTEGER NULL) — 1~5 난이도(세부개념만·단원/소단원 NULL).
    - `standard_codes`(TEXT[] NOT NULL DEFAULT '{}') — NCIC 성취기준 *코드* 배열(본문 아님).
    - `transfer`(TEXT NULL)·`transfer_example`(TEXT NULL) — 전이(④요소·자체 작성 교수 주석).
    - `atomicity`(JSONB NULL) — 원자성 a/b/c/d 판정 dict(구조 메타·본문 아님).
    - `review_status`(TEXT NOT NULL) — 'ai_estimated' 게이팅 플래그(원자 메타는 AI 추정·정직 표기·
      PG native enum 미생성·plain text·concept_node 동형).
    - `updated_at`(TIMESTAMPTZ NOT NULL DEFAULT now()) — 신선도.
  - **core_proposition·description·formal_definition·4요소(misconception/diagnostic/socratic)
    컬럼 없음**(redaction·우선순위 #2 — 성취기준 본문·검수 책임 4요소를 *둘 곳 자체를 두지 않음*.
    적재기 미독·테이블 미수록의 이중 방어. 4요소는 Phase 3에서 misconception_catalog/problem 승격).
  - **인덱스 2종**: `ix_atom_node_level`(단원/소단원/세부개념 필터)·`ix_atom_node_school_level`
    (초/중/고/대 필터) — 검색·추천 빈번 필터(2,697행 규모에 정석·PK는 code IN/조인으로 충분).

downgrade (왕복 안전 — CI가 `downgrade base`→`upgrade head` 왕복 검증):
  - `atom_node` 테이블만 drop(인덱스도 함께). native ENUM 0(전부 TEXT)·FK 0이라 다른 객체 무관.

Revision ID: e6f7a8b9c0d1
Revises: d5e6f7a8b9c0
Create Date: 2026-06-21 11:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY, JSONB

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e6f7a8b9c0d1"
down_revision: str | None = "d5e6f7a8b9c0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 원자 메타 code 키 프로젝션 — 안전 표시·필터 메타만(본문·4요소 미수록·native ENUM 0·전부 TEXT).
    op.create_table(
        "atom_node",
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("name_ko", sa.Text(), nullable=False),
        sa.Column("level", sa.Text(), nullable=False),
        sa.Column("parent_code", sa.Text(), nullable=True),
        sa.Column("school_level", sa.Text(), nullable=True),
        sa.Column("subject_area", sa.Text(), nullable=True),
        sa.Column("subunit_code", sa.Text(), nullable=True),
        sa.Column("cognitive_type", sa.Text(), nullable=True),
        sa.Column("node_type", sa.Text(), nullable=True),
        sa.Column("misconception_type", sa.Text(), nullable=True),
        sa.Column("intrinsic_difficulty", sa.Integer(), nullable=True),
        sa.Column(
            "standard_codes",
            ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::text[]"),
        ),
        sa.Column("transfer", sa.Text(), nullable=True),
        sa.Column("transfer_example", sa.Text(), nullable=True),
        sa.Column("atomicity", JSONB(), nullable=True),
        sa.Column("review_status", sa.Text(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("code", name=op.f("pk_atom_node")),
    )
    # 필터 보조 인덱스 — level(계층)·school_level(학교급) (검색·추천 빈번 필터).
    op.create_index("ix_atom_node_level", "atom_node", ["level"])
    op.create_index("ix_atom_node_school_level", "atom_node", ["school_level"])


def downgrade() -> None:
    # 인덱스 → 테이블 drop. native ENUM·FK 0이라 다른 객체 영향 없음(왕복 안전).
    op.drop_index("ix_atom_node_school_level", table_name="atom_node")
    op.drop_index("ix_atom_node_level", table_name="atom_node")
    op.drop_table("atom_node")
