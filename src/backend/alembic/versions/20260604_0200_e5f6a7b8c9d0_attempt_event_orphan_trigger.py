"""attempt_event orphan cleanup trigger

슬라이스 59 — problem_attempt 삭제(특히 session 삭제 시 slice 56 ON DELETE CASCADE) 시 그
attempt를 참조하던 attempt_event(loose ref·FK 아님·hypertable §6)를 함께 제거한다. FK
CASCADE를 못 쓰는 loose ref를 DB 트리거로 보완 — GDPR 삭제 완전성(자식 시계열 고아 방지·
slice 56 한계 ① 해소).

핵심: **AFTER DELETE 행 트리거는 부모 FK CASCADE로 지워지는 행에도 발화**한다 → session
삭제 → problem_attempt CASCADE 삭제 → 이 트리거가 각 attempt의 attempt_event 제거(연쇄
전파). 직접 attempt 삭제 경로는 현재 없으나(있어도 동일 동작) 미래 대비.

비고: attempt_event는 hypertable이라 attempt_id에 시간 술어 없는 DELETE는 청크 전수 스캔 →
삭제(드문 GDPR 경로)엔 수용. alembic autogenerate는 트리거/함수를 추적 안 함(hypertable
변환과 동일·migration-only) → `alembic check` 무드리프트 유지.

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-06-04 02:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e5f6a7b8c9d0"
down_revision: str | None = "d4e5f6a7b8c9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_FUNCTION = "whymath_cleanup_attempt_events"
_TRIGGER = "trg_cleanup_attempt_events"


def upgrade() -> None:
    # 트리거 함수: 삭제된 attempt(OLD.attempt_id)를 참조하는 attempt_event 제거.
    op.execute(f"""
        CREATE OR REPLACE FUNCTION {_FUNCTION}() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            DELETE FROM public.attempt_event WHERE attempt_id = OLD.attempt_id;
            RETURN OLD;
        END;
        $$;
        """)
    op.execute(f"""
        CREATE TRIGGER {_TRIGGER}
        AFTER DELETE ON problem_attempt
        FOR EACH ROW
        EXECUTE FUNCTION {_FUNCTION}();
        """)


def downgrade() -> None:
    op.execute(f"DROP TRIGGER IF EXISTS {_TRIGGER} ON problem_attempt;")
    op.execute(f"DROP FUNCTION IF EXISTS {_FUNCTION}();")
