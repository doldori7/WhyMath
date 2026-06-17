"""verified_lemmas (WH-S S1 §2.2 검증된 중간 결과 저장소 — Verified Lemma Store)

WH-S 솔버 하네스 S1 잔여(설계 `03b_wh_s_solver_harness.md` §2.2 검증된 중간 결과 저장소)의 마지막
*상태 저장소* 영속 좌석. 솔버 루프·도구 7(`log_lemma`)이 verify 통과한 부분 결과를 적재하고, 다른
가지가 `find_lemma`로 재사용해 중복 탐색을 제거한다. ORM 정본은
`whymath_backend/db/models/verified_lemma.py`(VerifiedLemma).

`verified_lemmas`(§2.2):
  - `id`(UUID PK·gen_random_uuid()) · `problem_id`(UUID NOT NULL·**FK 아님**·느슨참조).
  - `lemma_key`(Text NOT NULL — 재사용 매칭 키) · `lemma_repr`(JSONB NOT NULL — 검증된 부분
    결과) · `statement`(Text nullable — 사람 가독 진술) · `source_node_id`(UUID nullable·**FK
    아님**·재사용 자산이라 트리 GC 비강결합) · `created_at`(TIMESTAMPTZ NOT NULL·now()).
  - **UNIQUE(problem_id, lemma_key)** — 멱등 적재(두 가지 독립 발견해도 1행). 이 복합 UNIQUE
    인덱스가 find_lemma(정확 매칭 재사용)·get_lemmas(problem_id prefix)를 겸한다(별도 인덱스 불요).

★등급 컬럼 없음(§2.2 구조 전제): 저장소는 *검증된* 보조정리만 담는다(`log_lemma`는 verify 통과 후
호출). `verified_solutions`(verified/unverified 격리)와 달리 lemma는 재사용 대상이라 검증된 것만
둔다. enum 없으므로 downgrade는 테이블 drop만(enum 정리 불요 — solution_nodes/verified_solutions
대비 단순).

upgrade: `create_table("verified_lemmas", ...)` + 복합 UNIQUE.
downgrade (왕복 안전 — CI가 `downgrade -1`/`downgrade base`→`upgrade head` 검증): 테이블 drop
(복합 UNIQUE 동반 제거·enum 없음).

CLAUDE.md 개인정보: `verified_lemmas`는 *시스템 솔버 내부 중간 산출*이며 학생 PII가 아니다(동의·
암호화 대상 아님 — 평문 적정). WH-S 학생 경로 미개입(§7.5·API 노출 0).

Revision ID: a2b3c4d5e6f7
Revises: f1a2b3c4d5e6
Create Date: 2026-06-17 16:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a2b3c4d5e6f7"
down_revision: str | None = "f1a2b3c4d5e6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "verified_lemmas",
        sa.Column(
            "id",
            sa.Uuid(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        # 느슨참조 — problem 테이블 FK 아님(WH-S 오프라인 독립성).
        sa.Column("problem_id", sa.Uuid(), nullable=False),
        sa.Column("lemma_key", sa.Text(), nullable=False),
        sa.Column("lemma_repr", JSONB(), nullable=False),
        sa.Column("statement", sa.Text(), nullable=True),
        # 보조정리 출처 노드 약참조 — FK 아님(재사용 자산이라 트리 GC에 비강결합).
        sa.Column("source_node_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_verified_lemmas")),
        # 멱등 적재 — 같은 (문제·키) 보조정리는 1행(§2.2 중복 제거). 복합 UNIQUE 인덱스가
        # find_lemma·get_lemmas를 겸한다.
        sa.UniqueConstraint(
            "problem_id",
            "lemma_key",
            name="uq_verified_lemmas_problem_key",
        ),
    )


def downgrade() -> None:
    # enum 없음 — 테이블 drop이 복합 UNIQUE도 함께 제거(verified_solutions 대비 단순).
    op.drop_table("verified_lemmas")
