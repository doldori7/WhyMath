"""mis_id VARCHAR(16) → VARCHAR(32) 확폭 — atom 투영 mis_id 오버플로 결함 수정(M0).

atom 백본 승격 mis_id(`"ATOM:" + code`, `l1/misconception/atom_catalog.py`)는 실측 최장 **18자**
(1,837건 중 348건이 16자 초과 — 예 'ATOM:10공수1-01-01-1' = 18자)라 구 VARCHAR(16)에 적재 시
`value too long for type character varying(16)`로 실패한다. 이 결함은 atom 통합테스트의 코퍼스
경로가 CWD 상대(`Path("data/...")`)여서 CI(cwd=src/backend)에서 항상 skip돼 한 번도 실행 검증되지
않았다(같은 슬라이스에서 경로 앵커도 함께 수정). 두 테이블 —
`misconception_catalog.mis_id`(PK)·`misconception_crosslink.mis_id`(실 FK·CASCADE) — 를 같은 폭
**VARCHAR(32)** 로 확폭한다(Phase 5 kebab→ATOM 이전 대비 헤드룸 포함·ORM String(32)과 드리프트 0).

upgrade(확폭 — 무손실·데이터 무영향):
  - FK 부모(`misconception_catalog.mis_id` PK) 먼저 → 자식(`misconception_crosslink.mis_id`) 순.
    PG는 참조 중 컬럼의 TYPE 변경을 허용하며 확폭은 기존 행 전건 적합이라 안전하다.

downgrade(대칭 축소 — 자식 먼저·역순):
  - 전제: 17자+ mis_id 행 미존재. 17자 이상 행(atom 'ATOM:' 접두 등)이 있으면 PG가
    `value too long`으로 **정직하게 실패**한다 — 조용한 절단 대신 운영자가 장문 행
    (`DELETE ... WHERE length(mis_id) > 16`)을 먼저 정리해야 한다(curriculum_entry
    subject downgrade의 정직한 실패 선례와 동형).

Revision ID: a5b6c7d8e9f0
Revises: a4b5c6d7e8f9
Create Date: 2026-07-02 14:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a5b6c7d8e9f0"
down_revision: str | None = "a4b5c6d7e8f9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── ① FK 부모 먼저 — misconception_catalog.mis_id(PK) 16 → 32 확폭(무손실). ──
    op.alter_column(
        "misconception_catalog",
        "mis_id",
        existing_type=sa.String(length=16),
        type_=sa.String(length=32),
        existing_nullable=False,
    )
    # ── ② FK 자식 — misconception_crosslink.mis_id(실 FK·CASCADE) 동일 폭 32. ──
    op.alter_column(
        "misconception_crosslink",
        "mis_id",
        existing_type=sa.String(length=16),
        type_=sa.String(length=32),
        existing_nullable=False,
    )


def downgrade() -> None:
    # ── ② FK 자식 먼저(역순) — 17자+ 행 존재 시 PG value too long 정직한 실패. ──
    op.alter_column(
        "misconception_crosslink",
        "mis_id",
        existing_type=sa.String(length=32),
        type_=sa.String(length=16),
        existing_nullable=False,
    )
    # ── ① FK 부모 — misconception_catalog.mis_id 16 복원(장문 행은 먼저 정리 전제). ──
    op.alter_column(
        "misconception_catalog",
        "mis_id",
        existing_type=sa.String(length=32),
        type_=sa.String(length=16),
        existing_nullable=False,
    )
