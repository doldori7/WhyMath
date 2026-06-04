"""cascade ondelete on lifecycle FKs

슬라이스 56 — 본인 데이터 GDPR 삭제 cascade 정책. learning_session·dialogue 삭제 시 자식이
FK 위반(기본 NO ACTION)으로 막히던 한계(slice 51/52) 해소:
  - problem_attempt.session_id → ON DELETE CASCADE (세션 삭제 시 attempt 제거)
  - dialogue_turn.dialogue_id → ON DELETE CASCADE (대화 삭제 시 turn 제거)
  - dialogue.attempt_id → ON DELETE SET NULL (attempt cascade 삭제 시 대화 보존·링크만 끊음)

attempt_event.attempt_id는 FK가 아닌 loose ref(hypertable §6)라 cascade 대상 아님 — 세션
삭제 시 attempt_event는 고아로 잔존(설계상 한계·문서화). 제약 이름은 naming_convention
산출과 동일(op.f로 재적용 방지).

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-06-04 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c3d4e5f6a7b8"
down_revision: str | None = "b2c3d4e5f6a7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # problem_attempt.session_id → CASCADE
    op.drop_constraint(
        "fk_problem_attempt_session_id_learning_session",
        "problem_attempt",
        type_="foreignkey",
    )
    op.create_foreign_key(
        op.f("fk_problem_attempt_session_id_learning_session"),
        "problem_attempt",
        "learning_session",
        ["session_id"],
        ["session_id"],
        ondelete="CASCADE",
    )
    # dialogue_turn.dialogue_id → CASCADE
    op.drop_constraint(
        "fk_dialogue_turn_dialogue_id_dialogue",
        "dialogue_turn",
        type_="foreignkey",
    )
    op.create_foreign_key(
        op.f("fk_dialogue_turn_dialogue_id_dialogue"),
        "dialogue_turn",
        "dialogue",
        ["dialogue_id"],
        ["dialogue_id"],
        ondelete="CASCADE",
    )
    # dialogue.attempt_id → SET NULL
    op.drop_constraint(
        "fk_dialogue_attempt_id_problem_attempt",
        "dialogue",
        type_="foreignkey",
    )
    op.create_foreign_key(
        op.f("fk_dialogue_attempt_id_problem_attempt"),
        "dialogue",
        "problem_attempt",
        ["attempt_id"],
        ["attempt_id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    # 원복 — ondelete 제거(기본 NO ACTION).
    op.drop_constraint(
        "fk_dialogue_attempt_id_problem_attempt",
        "dialogue",
        type_="foreignkey",
    )
    op.create_foreign_key(
        op.f("fk_dialogue_attempt_id_problem_attempt"),
        "dialogue",
        "problem_attempt",
        ["attempt_id"],
        ["attempt_id"],
    )
    op.drop_constraint(
        "fk_dialogue_turn_dialogue_id_dialogue",
        "dialogue_turn",
        type_="foreignkey",
    )
    op.create_foreign_key(
        op.f("fk_dialogue_turn_dialogue_id_dialogue"),
        "dialogue_turn",
        "dialogue",
        ["dialogue_id"],
        ["dialogue_id"],
    )
    op.drop_constraint(
        "fk_problem_attempt_session_id_learning_session",
        "problem_attempt",
        type_="foreignkey",
    )
    op.create_foreign_key(
        op.f("fk_problem_attempt_session_id_learning_session"),
        "problem_attempt",
        "learning_session",
        ["session_id"],
        ["session_id"],
    )
