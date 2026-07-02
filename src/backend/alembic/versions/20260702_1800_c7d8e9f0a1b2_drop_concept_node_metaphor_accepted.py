"""concept_node에서 metaphor·accepted_expressions 컬럼 제거 — pedagogy 계층 이관(Part 2 §3 Stage B).

`concept`에서 subject·curriculum_version을 제거(rev f3a4b5c6d7e8)한 것과 같은 계층 분리 조치다.
은유(metaphor)·허용표현(accepted_expressions)은 *개념의 식별/게이팅 메타가 아니라* pedagogy
정보이므로 메타 프로젝션(`concept_node`)에 두지 않는다 — pedagogy 계층 `concept_content`(code 키)가
단일 진실이다(플레이북 Part 2 §3·CLAUDE.md Concept Purity·Layer Separation).

데이터/런타임 안전:
  - 두 컬럼을 *조회·조인*하는 런타임 코드가 없다 — `fetch_node_meta`는 name_ko·domain·
    review_status만 SELECT하고, 검색 enrichment(`ConceptNodeMeta`)에도 두 필드가 없다. 즉
    write-only였다(적재기 write만·reader 0). 제거는 read 경로에 무영향.
  - 의미검색 임베딩은 이제 metaphor/accepted를 `concept_content`(source_id↔code 조인)에서
    소싱한다(`l1/concept_graph/embedding.py` Stage B). 값 동일 → 재임베딩 0.
  - 원천 값은 `concept_content` 코퍼스(content.json)에 잔존 — 비가역 손실 아님.

upgrade:
  - `concept_node.metaphor`·`concept_node.accepted_expressions` drop_column(2개).

downgrade:
  - 두 컬럼을 원래 정의(nullable sa.Text)로 복원. 데이터는 재적재(populate)로 복원 가능.

Revision ID: c7d8e9f0a1b2
Revises: b6c7d8e9f0a1
Create Date: 2026-07-02 18:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c7d8e9f0a1b2"
down_revision: str | None = "b6c7d8e9f0a1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # pedagogy는 concept_content(code 키)가 단일 진실 — 메타 프로젝션에서 두 컬럼 제거(write-only).
    op.drop_column("concept_node", "metaphor")
    op.drop_column("concept_node", "accepted_expressions")


def downgrade() -> None:
    # 원래 정의(nullable Text)로 복원. 데이터는 populate 재적재로 복원(원천은 content.json).
    op.add_column("concept_node", sa.Column("accepted_expressions", sa.Text(), nullable=True))
    op.add_column("concept_node", sa.Column("metaphor", sa.Text(), nullable=True))
