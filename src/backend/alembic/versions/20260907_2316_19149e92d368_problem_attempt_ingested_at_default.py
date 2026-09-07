"""problem_attempt.ingested_at server_default 부여 (SEC-33 ⑥ — 좌석 보장 선행).

배경: `SEC-33`(클라 신고 `started_at`이 PII 보존기한 파기를 무기한 회피)의 해법 ②는
`privacy/retention._RETENTION_PLAN`이 `ProblemAttempt`를 `COALESCE(started_at, ingested_at)`
기준으로 파기하게 바꾸는 것이다. 그런데 `ingested_at`은 지금 **애플리케이션 코드의 관례**로만
채워진다 — 현재 두 writer(`api/me.py::submit_attempt`·`api/coach.py::_complete_problem`)가
`ingested_at=received_at`을 명시하지만, 스키마 자체는 이를 보장하지 않는다(nullable·기본값
없음). 세 번째 writer가 그 관례를 빠뜨리면 `ingested_at`도 NULL이 되어 COALESCE 폴백 자체가
무력해진다 — 폴백 컬럼을 고르기 전에 그 컬럼에 *스키마 수준* 보장을 부여하는 것이 선행이다.

**왜 EOS-48이 `ingested_at`에 server_default를 안 달았는지, 그리고 지금은 왜 달아도 안전한지**:
`db/models/activity.py:184-185` 주석이 그 이유를 "ALTER 시 기존 행에 마이그레이션 시각이
백필되는 날조를 막는다"고 적었다 — 이는 `ADD COLUMN ... DEFAULT`(PG가 기존 행 전체를 그 기본값
으로 **채운다**) 축의 위험이다. 이 마이그레이션은 **이미 존재하는** nullable 컬럼에
`ALTER COLUMN ... SET DEFAULT`만 건다 — PG의 `SET DEFAULT`는 *향후 INSERT가 그 컬럼을 생략할
때만* 기본값을 채우며, 기존 행은 전혀 건드리지 않는다(UPDATE가 아니다). 그래서 EOS-48이 막으려던
"기존 NULL 행이 조용히 채워지는" 날조 축은 발생하지 않는다 — 기존 NULL 행은 그대로 NULL로
남고(정직), 이 마이그레이션 이후의 신규 INSERT만 애플리케이션이 값을 생략해도 서버 시각으로
채워진다. `existing_nullable=True`를 유지해 컬럼 자체의 NULL 허용은 바꾸지 않는다(과거 데이터
직접 대조는 여전히 가능).

upgrade: `problem_attempt.ingested_at`에 `server_default=now()` 부여(컬럼 정의·nullable 불변).
downgrade: server_default 제거(대칭 — 기존 행 데이터는 영향 없음).

Revision ID: 19149e92d368
Revises: c1a5e07b4d38
Create Date: 2026-09-07 23:16:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "19149e92d368"
down_revision: str | None = "c1a5e07b4d38"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "problem_attempt",
        "ingested_at",
        existing_type=sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "problem_attempt",
        "ingested_at",
        existing_type=sa.DateTime(timezone=True),
        server_default=None,
        existing_nullable=True,
    )
