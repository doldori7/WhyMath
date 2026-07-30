"""user_profile.role — 인가(authorization) 역할 v0 2값 (SEC-07 D1)

`/v1/concepts`·`/v1/problems`의 CUD(POST/PATCH/DELETE)가 인증 의존성 0건이던 실측 갭
(`docs/architecture/account_security_gap_review.md` D1)을 봉인하는 선결 스키마 변경.
`schema/enums.py` `Role`(STUDENT/CONTENT_ADMIN 2값 — 7단 선형 서열은 의도적 미도입,
`pipa_data_matrix.md:33-47`이 반증하는 부모⊂학생 구조와 모순되기 때문)을 저장하는
`user_profile.role` 컬럼을 추가한다.

NOT NULL + `server_default='student'`로 기존 행을 안전 백필한다(additive·비파괴 — problem
P3a `c8d9e0f1a2b3` 선례처럼 add_column이 새 native ENUM 타입을 자동 생성하지 않으므로
`postgresql.ENUM(...).create(checkfirst=True)`로 명시 생성). `require_role`(`api/_auth.py`)이
이 컬럼으로 콘텐츠 CUD를 게이팅한다.

Revision ID: c5d6e7f0a2b3
Revises: b4c5d6e7f0a2
Create Date: 2026-07-30 12:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c5d6e7f0a2b3"
down_revision: str | None = "b4c5d6e7f0a2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# schema/enums.py Role과 *정확히 일치*해야 한다(마이그레이션은 결정적이어야 하므로 ORM enum을
# import하지 않고 정본 값을 박는다 — initial_problem_domain·P3a 선례).
_ROLES: tuple[str, ...] = ("student", "content_admin")


def upgrade() -> None:
    # ── 신규 native ENUM 타입 생성(add_column이 자동 생성 안 하므로 명시·checkfirst 멱등). ──
    postgresql.ENUM(*_ROLES, name="role_enum").create(op.get_bind(), checkfirst=True)

    # ── ADD COLUMN — NOT NULL + server_default='student'(기존 행 안전 백필). ──
    op.add_column(
        "user_profile",
        sa.Column(
            "role",
            postgresql.ENUM(*_ROLES, name="role_enum", create_type=False),
            nullable=False,
            server_default="student",
        ),
    )


def downgrade() -> None:
    op.drop_column("user_profile", "role")
    postgresql.ENUM(name="role_enum").drop(op.get_bind(), checkfirst=True)
