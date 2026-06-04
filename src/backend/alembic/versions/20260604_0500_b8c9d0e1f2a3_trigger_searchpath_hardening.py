"""trigger function search_path hardening

슬라이스 62 — slice 59 트리거 함수 `whymath_cleanup_attempt_events`에 `SET search_path =
pg_catalog, public` 추가(보안 하드닝·CLAUDE.md 우선순위 #2). 함수는 SECURITY DEFINER가 아니라
현재 위험은 낮으나(테이블 참조도 `public.`로 한정), 함수가 호출되는 세션의 search_path가
조작돼도 연산자·함수 해석이 pg_catalog에 고정되도록 명시 — 코드베이스 첫 DB 함수의 보안 선례.

`CREATE OR REPLACE FUNCTION`은 기존 트리거 바인딩(`trg_cleanup_attempt_events`)을 유지한다
(트리거는 함수를 이름으로 참조 → 본문 교체만으로 충분·트리거 재생성 불요). 동작 불변
(qualified DELETE 그대로) — proconfig만 추가.

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
Create Date: 2026-06-04 05:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b8c9d0e1f2a3"
down_revision: str | None = "a7b8c9d0e1f2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_FUNCTION = "whymath_cleanup_attempt_events"


def upgrade() -> None:
    # search_path 고정 추가(하드닝). 본문은 slice 59와 동일.
    op.execute(f"""
        CREATE OR REPLACE FUNCTION {_FUNCTION}() RETURNS trigger
        LANGUAGE plpgsql
        SET search_path = pg_catalog, public
        AS $$
        BEGIN
            DELETE FROM public.attempt_event WHERE attempt_id = OLD.attempt_id;
            RETURN OLD;
        END;
        $$;
        """)


def downgrade() -> None:
    # slice 59 원본(search_path 미설정)으로 복원.
    op.execute(f"""
        CREATE OR REPLACE FUNCTION {_FUNCTION}() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            DELETE FROM public.attempt_event WHERE attempt_id = OLD.attempt_id;
            RETURN OLD;
        END;
        $$;
        """)
