"""solution_nodes 테이블 + node_verify_status_enum (WH-S S1 풀이 경로 트리·§2.1)

WH-S 솔버 하네스 S1(설계 `03b_wh_s_solver_harness.md` §2.1 풀이 경로 트리·§9 S1)의 *풀이 트리
상태 계층* 영속 좌석. 솔버 루프·MCTS·도구 8종이 쓸 노드 상태(`solution_nodes`)와 그 검증 상태
PG enum(`node_verify_status_enum`)을 *최초 생성*한다. ORM 정본은
`whymath_backend/db/models/solution_node.py`(SolutionNode·NodeVerifyStatus).

스키마(§2.1 `solution_nodes(problem_id, parent_id, state_repr, action, prm_score,
verify_status, visits)`):
  - `id`(UUID PK·`gen_random_uuid()` server_default — 모든 UUID PK 선례[ability_snapshot 등]).
  - `problem_id`(UUID NOT NULL·**FK 아님**) — WH-S는 독립 오프라인 서브시스템이라 운영
    `problem` 테이블에 강결합하지 않는다(느슨참조·인덱스만·ability_snapshot.user_id 동형).
  - `parent_id`(UUID nullable·**self-FK** `solution_nodes.id` `ondelete="CASCADE"`) — 트리
    부모. 루트는 NULL. 부모 삭제 시 자식 가지 전체 제거(고아 노드 방지).
  - `state_repr`(JSONB NOT NULL) — 풀이 상태 구조화 표현(자유형·솔버 루프가 내용 계약 정의).
  - `action`(Text nullable) — 부모에서 적용한 전략 1스텝(루트는 NULL).
  - `prm_score`(Float nullable) — 과정 보상 추정치(미평가 시 NULL).
  - `verify_status`(node_verify_status_enum NOT NULL·server_default 'pending') — 노드 검증
    상태(pending→verified/unverified/failed). `WhsGrade`(verdict.py)와 의미 정합 + 미검증
    초기상태 pending 추가.
  - `visits`(Integer NOT NULL·server_default 0) — MCTS 방문 횟수(미방문 0).
  - `created_at`/`updated_at`(TIMESTAMPTZ NOT NULL·server_default now()) — 운영 메타.

인덱스(§2.1 접근 패턴 — problem별 루트 조회·parent별 자식 조회):
  - `idx_solution_nodes_problem`(problem_id) — `get_roots`/문제별 트리 스캔.
  - `idx_solution_nodes_parent`(parent_id) — `get_children` 자식 조회.

upgrade:
  - `create_table("solution_nodes", ...)` — `verify_status` 컬럼의 `sa.Enum(...,
    name="node_verify_status_enum")`가 PG native enum 타입을 *자동 생성*한다(initial_problem_domain
    선례). values_callable로 enum 값(소문자 라벨)을 박는다(멤버명≠값 대비·_orm_enum 규칙 동형).
  - 인덱스 2종 생성.

downgrade (왕복 안전 — CI가 `downgrade -1`/`downgrade base`→`upgrade head` 검증):
  - 인덱스 2종 → 테이블 순 drop. 그 다음 `node_verify_status_enum` PG 타입을 *명시 drop*한다
    (create_table이 자동 생성한 PG enum은 drop_table로 사라지지 않아, 안 떨구면 재-upgrade가
    "type already exists"로 깨짐 — initial_problem_domain 선례·checkfirst 멱등).

CLAUDE.md 개인정보: `solution_nodes`는 *시스템 솔버 내부 탐색 상태*이며 학생 PII가 아니다
(동의·암호화 대상 아님 — 평문 JSONB 적정). WH-S 학생 경로 미개입(§7.5).

Revision ID: c2d3e4f5a6b7
Revises: b1c2d3e4f5a6
Create Date: 2026-06-13 12:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c2d3e4f5a6b7"
down_revision: str | None = "b1c2d3e4f5a6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# node_verify_status_enum 라벨(NodeVerifyStatus 값과 일치·소문자). 마이그레이션은 결정적이어야
# 하므로 ORM enum을 import하지 않고 정본 값을 박는다(initial_problem_domain의 인라인 라벨 선례).
_VERIFY_STATUS_LABELS = ("pending", "verified", "unverified", "failed")


def upgrade() -> None:
    op.create_table(
        "solution_nodes",
        sa.Column(
            "id",
            sa.Uuid(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        # 느슨참조 — problem 테이블 FK 아님(WH-S 오프라인 독립성). 인덱스만.
        sa.Column("problem_id", sa.Uuid(), nullable=False),
        # self-FK — 트리 부모(루트 NULL). 부모 삭제 시 자식 가지 CASCADE 제거.
        sa.Column("parent_id", sa.Uuid(), nullable=True),
        sa.Column("state_repr", JSONB(), nullable=False),
        sa.Column("action", sa.Text(), nullable=True),
        sa.Column("prm_score", sa.Float(), nullable=True),
        sa.Column(
            "verify_status",
            sa.Enum(
                *_VERIFY_STATUS_LABELS,
                name="node_verify_status_enum",
            ),
            server_default="pending",
            nullable=False,
        ),
        sa.Column(
            "visits",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_solution_nodes")),
        # self-FK — 부모 노드 삭제 시 자식 가지 CASCADE(고아 노드 방지).
        sa.ForeignKeyConstraint(
            ["parent_id"],
            ["solution_nodes.id"],
            name=op.f("fk_solution_nodes_parent_id_solution_nodes"),
            ondelete="CASCADE",
        ),
    )
    op.create_index("idx_solution_nodes_problem", "solution_nodes", ["problem_id"])
    op.create_index("idx_solution_nodes_parent", "solution_nodes", ["parent_id"])


def downgrade() -> None:
    op.drop_index("idx_solution_nodes_parent", table_name="solution_nodes")
    op.drop_index("idx_solution_nodes_problem", table_name="solution_nodes")
    op.drop_table("solution_nodes")
    # 네이티브 ENUM 타입 정리 — create_table이 자동 생성한 PG enum은 drop_table로 사라지지
    # 않으므로 명시 drop(안 떨구면 재-upgrade가 "type already exists"로 깨짐·checkfirst 멱등).
    postgresql.ENUM(name="node_verify_status_enum").drop(op.get_bind(), checkfirst=True)
