"""dead_end_log + verified_solutions + whs_solution_grade_enum (WH-S S1 §2.3·§2.4)

WH-S 솔버 하네스 S1 잔여(설계 `03b_wh_s_solver_harness.md` §2.3 실패 접근 로그 — Dead-End Log·
§2.4 검증 풀이 저장소 — Verified Solution Bank)의 *상태 저장소* 영속 좌석. 솔버 루프·도구 8종
(`log_deadend`·`finalize`)이 쓸 두 테이블을 생성한다. ORM 정본은
`whymath_backend/db/models/dead_end_log.py`(DeadEndLog)·`verified_solution.py`
(VerifiedSolution·WhsSolutionGrade).

`dead_end_log`(§2.3 — 같은 막다른 길 재진입 차단):
  - `id`(UUID PK·gen_random_uuid()) · `problem_id`(UUID NOT NULL·**FK 아님**·느슨참조).
  - `state_hash`(Text NOT NULL) · `action`(Text NOT NULL) · `reason`(Text nullable).
  - `created_at`(TIMESTAMPTZ NOT NULL·now()).
  - **UNIQUE(problem_id, state_hash, action)** — 멱등 기록(중복 막다른 길 1행). 이 복합 UNIQUE
    인덱스가 is_dead_end(정확 매칭)·get_dead_ends(problem_id prefix)를 겸한다(별도 인덱스 불요).

`verified_solutions`(§2.4 — 최종 통과 풀이 경로·다중 풀이):
  - `id`(UUID PK) · `problem_id`(UUID NOT NULL·**FK 아님**·느슨참조).
  - `grade`(whs_solution_grade_enum NOT NULL — **verified/unverified만**·failed는 enum에서 구조
    배제·§2.4·R-S2) · `solution_path`(JSONB NOT NULL) · `strategy_tag`(Text nullable) ·
    `answer`(Text nullable) · `source_root_id`(UUID nullable·**FK 아님**·내구 자산이라 트리 GC
    비강결합) · `created_at`(TIMESTAMPTZ NOT NULL·now()).
  - 인덱스 `idx_verified_solutions_problem_grade`(problem_id, grade) — get_solutions·get_verified
    겸용. problem_id에 UNIQUE 없음(다중 풀이 — 한 문제 여러 풀이 행).

upgrade:
  - `create_table("dead_end_log", ...)` + 복합 UNIQUE.
  - `create_table("verified_solutions", ...)` — `grade`의 `sa.Enum(...,
    name="whs_solution_grade_enum")`가 PG native enum을 *자동 생성*(소문자 라벨). 그 뒤 인덱스 1종.

downgrade (왕복 안전 — CI가 `downgrade -1`/`downgrade base`→`upgrade head` 검증):
  - verified_solutions: 인덱스 → 테이블 → `whs_solution_grade_enum` PG 타입 *명시 drop*
    (create_table 자동 생성 enum은 drop_table로 안 사라짐 — 안 떨구면 재-upgrade "type already
    exists"·solution_nodes 선례·checkfirst 멱등). dead_end_log: 테이블 drop(복합 UNIQUE 동반 제거).

CLAUDE.md 개인정보: 두 테이블 모두 *시스템 솔버의 내부 상태/산출*이며 학생 PII가 아니다(동의·
암호화 대상 아님 — 평문 적정). WH-S 학생 경로 미개입(§7.5·API 노출 0).

Revision ID: f1a2b3c4d5e6
Revises: e0f1a2b3c4d5
Create Date: 2026-06-17 14:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f1a2b3c4d5e6"
down_revision: str | None = "e0f1a2b3c4d5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# whs_solution_grade_enum 라벨(WhsSolutionGrade 값과 일치·소문자). 마이그레이션은 결정적이어야
# 하므로 ORM enum을 import하지 않고 정본 값을 박는다(solution_nodes의 인라인 라벨 선례). failed는
# *없다* — 저장소는 verified/unverified만 적재(§2.4·R-S2 구조 차단).
_SOLUTION_GRADE_LABELS = ("verified", "unverified")


def upgrade() -> None:
    # ── §2.3 dead_end_log ──
    op.create_table(
        "dead_end_log",
        sa.Column(
            "id",
            sa.Uuid(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        # 느슨참조 — problem 테이블 FK 아님(WH-S 오프라인 독립성).
        sa.Column("problem_id", sa.Uuid(), nullable=False),
        sa.Column("state_hash", sa.Text(), nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_dead_end_log")),
        # 멱등 기록 — 같은 (문제·상태·행동) 막다른 길은 1행(§2.3 중복 차단). 복합 UNIQUE 인덱스가
        # is_dead_end·get_dead_ends를 겸한다.
        sa.UniqueConstraint(
            "problem_id",
            "state_hash",
            "action",
            name="uq_dead_end_log_problem_state_action",
        ),
    )

    # ── §2.4 verified_solutions ──
    op.create_table(
        "verified_solutions",
        sa.Column(
            "id",
            sa.Uuid(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        # 느슨참조 — problem 테이블 FK 아님(WH-S 오프라인 독립성).
        sa.Column("problem_id", sa.Uuid(), nullable=False),
        sa.Column(
            "grade",
            sa.Enum(
                *_SOLUTION_GRADE_LABELS,
                name="whs_solution_grade_enum",
            ),
            nullable=False,
        ),
        sa.Column("solution_path", JSONB(), nullable=False),
        sa.Column("strategy_tag", sa.Text(), nullable=True),
        sa.Column("answer", sa.Text(), nullable=True),
        # 풀이 트리 루트 약참조 — FK 아님(내구 자산이라 트리 GC에 비강결합).
        sa.Column("source_root_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_verified_solutions")),
    )
    # (problem_id, grade) — get_solutions·get_verified 겸용. problem_id UNIQUE 없음(다중 풀이).
    op.create_index(
        "idx_verified_solutions_problem_grade",
        "verified_solutions",
        ["problem_id", "grade"],
    )


def downgrade() -> None:
    op.drop_index("idx_verified_solutions_problem_grade", table_name="verified_solutions")
    op.drop_table("verified_solutions")
    # 네이티브 ENUM 타입 정리 — create_table 자동 생성 enum은 drop_table로 안 사라짐(안 떨구면
    # 재-upgrade "type already exists"·solution_nodes 선례·checkfirst 멱등).
    postgresql.ENUM(name="whs_solution_grade_enum").drop(op.get_bind(), checkfirst=True)
    # dead_end_log는 enum 없음 — 테이블 drop이 복합 UNIQUE도 함께 제거.
    op.drop_table("dead_end_log")
