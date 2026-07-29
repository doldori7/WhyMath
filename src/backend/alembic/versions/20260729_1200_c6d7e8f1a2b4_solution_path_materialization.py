"""solution_paths 신설 + problem_step additive 6컬럼 — SolutionPath 실체화 (S4-09·D1)

`docs/architecture/solution_module_gap_review.md` §3 D1. WH-S 620문 실가동 출력
(`verified_solutions.solution_path` 평문 JSONB)의 구조 승격 좌석:

  ① **`solution_paths` 신설**(풀이 경로 헤더) — TEXT PK(`sp-{verified_solutions.id}` 결정론
     ID·멱등 승격)·`problem_id` UUID FK(참조 실재의 DB 강제 — 서빙 표면 원천이라
     `verified_solutions` 느슨참조와 달리 코퍼스 정합 FK)·`approach_type` TEXT NOT NULL
     (폐쇄 6종 강제는 l3 Pydantic Literal — PG enum 신설 안 함·단일 enum 좌석 승격은 S4-10)·
     `concept_sequence` JSONB(매칭 확정분만·날조 금지)·`verified_by_human` 기본 false(AI
     자기승인 금지)·`equivalence_cluster_id` nullable(동치 *후보* 군집 좌석 — 부여는 S4-12).
  ② **`problem_step` additive 6컬럼**(전부 nullable — 기존 행·기존 API 응답 비파괴):
     `solution_path_id` FK·`concept_node_id`(NULL=매칭 검수 대기)·`reasoning_type` TEXT
     (폐쇄 7종 강제는 schema/enums.py ReasoningType — PG enum 추가 없음)·`justification`
     JSONB·`common_errors` JSONB·`sympy_verified` BOOL(NULL=미판정). 단계 전용 테이블을
     신설하지 않는다(테이블 증식 최소화 — D1 좌석 설계).

`embedding` 컬럼은 **넣지 않는다** — 소비처(군집·D4)가 서는 S4-12에서 판정(acceptance 명시).
JSONB Python None → SQL NULL 방침(SEC-06 `none_as_null` 전수 거버넌스)은 ORM 선언이 강제한다
(`db/models/solution_path.py`·`db/models/problem.py`).

Revision ID: c6d7e8f1a2b4
Revises: b4c5d6e7f0a2
Create Date: 2026-07-29 12:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c6d7e8f1a2b4"
down_revision: str | None = "b4c5d6e7f0a2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── ① 풀이 경로 헤더 테이블 신설 (단계는 problem_step additive 컬럼에 영속) ──
    op.create_table(
        "solution_paths",
        sa.Column("solution_path_id", sa.Text(), nullable=False),
        sa.Column("problem_id", sa.Uuid(), nullable=False),
        # 폐쇄 6종(algebraic/geometric/combinatorial/inductive/visual/backward) 강제는 l3
        # Pydantic — DB는 TEXT 좌석만(PG enum 신설 안 함·S4-10에서 단일 enum 좌석 재론).
        sa.Column("approach_type", sa.Text(), nullable=False),
        # 개념 노드 ID 순서열(풀이 골격) — 매칭 확정분만. 기존 행 백필은 빈 배열.
        sa.Column(
            "concept_sequence",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        # 승격 직후 항상 false(AI 자기승인 금지) — 사람 검수 통과 시에만 true.
        sa.Column("verified_by_human", sa.Boolean(), nullable=False, server_default=sa.false()),
        # 동치 *후보* 군집 좌석(확정 동치 아님 — 정직 경계). 부여는 S4-12(D4).
        sa.Column("equivalence_cluster_id", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("solution_path_id", name=op.f("pk_solution_paths")),
        # 서빙 표면 원천의 코퍼스 정합 강제 — problem_step.problem_id 기존 FK 관례 동형.
        sa.ForeignKeyConstraint(
            ["problem_id"],
            ["problem.problem_id"],
            name=op.f("fk_solution_paths_problem_id_problem"),
        ),
    )
    # 문제 단위 조회(steps API·learning_scene 결선·승격 멱등 확인) 인덱스.
    op.create_index("idx_solution_paths_problem", "solution_paths", ["problem_id"])

    # ── ② problem_step additive 6컬럼 (전부 nullable — 기존 행·응답 비파괴) ──
    op.add_column("problem_step", sa.Column("solution_path_id", sa.Text(), nullable=True))
    op.create_foreign_key(
        op.f("fk_problem_step_solution_path_id_solution_paths"),
        "problem_step",
        "solution_paths",
        ["solution_path_id"],
        ["solution_path_id"],
    )
    op.add_column("problem_step", sa.Column("concept_node_id", sa.Text(), nullable=True))
    op.add_column("problem_step", sa.Column("reasoning_type", sa.Text(), nullable=True))
    op.add_column(
        "problem_step",
        sa.Column("justification", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "problem_step",
        sa.Column("common_errors", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column("problem_step", sa.Column("sympy_verified", sa.Boolean(), nullable=True))


def downgrade() -> None:
    # up의 정확한 역순(대칭) — additive 컬럼 제거 후 테이블 드랍.
    op.drop_column("problem_step", "sympy_verified")
    op.drop_column("problem_step", "common_errors")
    op.drop_column("problem_step", "justification")
    op.drop_column("problem_step", "reasoning_type")
    op.drop_column("problem_step", "concept_node_id")
    op.drop_constraint(
        op.f("fk_problem_step_solution_path_id_solution_paths"),
        "problem_step",
        type_="foreignkey",
    )
    op.drop_column("problem_step", "solution_path_id")
    op.drop_index("idx_solution_paths_problem", table_name="solution_paths")
    op.drop_table("solution_paths")
