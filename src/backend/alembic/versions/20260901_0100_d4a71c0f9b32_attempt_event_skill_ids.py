"""attempt_event.skill_ids[] 좌석 + event_type_enum '문제시도' 추가 (EOS-57).

`docs/reviews/eos_plan52_crosswalk_2026-09.md` 갭 #4(E3 잔여)·선언 §5 W2 "되돌릴 수 없는 스키마"
①의 착지. 채점 순간 concept→skill로 *해소된* 스킬 배열은 지금까지 런타임(`l2/
skill_mastery_tracking.py`)에만 존재하고 버려졌다 — 문항↔개념↔스킬 매핑이 이후 바뀌면 과거
시도의 스킬 귀속은 **영원히 재구성 불가**라 12월 데이터에 남기려면 지금 좌석이 있어야 한다.

신규 테이블 없음 — 기존 `attempt_event`에 nullable 컬럼 1개 + enum 값 1개(EOS-48과 동형의
**additive·비파괴** 변경: 기존 행은 전부 NULL 유지, 기존 writer·소비자 무영향).

**server_default를 달지 않는 이유(날조 방지 — EOS-48 규약 그대로)**: `ADD COLUMN ... DEFAULT
'{}'::text[]`는 PG가 기존 행 전체를 빈 배열로 채운다 — 그러면 "writer가 안 돌았다"(미기록)와
"돌았는데 해소 0건"(실측)이 같은 값이 되어 기록률 리포트가 구분할 수 없다. NULL=미기록이
정직한 상태이며 신규 writer(`l2/attempt_skill_event.py`)가 채운다.

**FK를 걸지 않는 이유**: `attempt_event`는 §6.1 DDL에서 `attempt_id`·`user_id`·`problem_id`
전부 REFERENCES 없는 느슨참조다(hypertable 전환 대상). `skill_ids`도 같은 규약을 따른다 —
배열 FK는 PG가 지원하지도 않는다.

**enum ADD VALUE 안전성(PG 16)**: 같은 트랜잭션에서 값을 *추가*만 하고 *사용*하지 않으므로
안전하다(직전 선례 `c0d1e2f3a4b5` 시각화조작·`b1c2d3e4f5a6` 힌트제공 docstring 동일 근거).
`IF NOT EXISTS`로 재실행 멱등.

**마이그레이션 체인 조율(EOS-57 acceptance ① 명시 요구)**: 착지 시점 단일 head는
`c9bc2555282e`(EOS-48 event_time/active_time)이고 이 리비전이 그 위에 쌓인다. 같은 활동 도메인
(`activity.py` 3테이블)을 건드리는 **미착수 형제 태스크 EOS-47**(problem_attempt 버전 고정 —
`problem_version_id`·`evaluation_context`)과는 **테이블도 컬럼도 겹치지 않는다**: 본 리비전은
`attempt_event` 1테이블에만 `skill_ids`를 더하고, EOS-47은 `problem_attempt`에 버전 컬럼을
더한다. 따라서 EOS-47은 본 리비전 위에 선형으로 쌓으면 되고(브랜치 head 금지 — 저장소는 단일
head 관례), 두 마이그레이션 사이에 순서 의존이 없다(어느 쪽이 먼저 착지해도 무방하며, 나중
착지분이 그때의 head를 down_revision으로 잡는다).

**ADR-001 재확인(hypertable 전환 무충돌)**: nullable 배열 컬럼 추가는 파티션 키(`event_at`)·
복합 PK를 건드리지 않는다 — `create_hypertable` 전환 절차는 컬럼 목록과 무관하게 동작하고,
본 컬럼은 짧은 텍스트 배열이라 압축 부담도 미미하다(EOS-48 추기 동일 근거).

upgrade: enum 값 1개 add(멱등) + 컬럼 1개 add(nullable·default 없음).
downgrade: 컬럼 drop(대칭). enum 값은 PG가 제거를 지원하지 않아 관례대로 남긴다(no-op·무손상).

Revision ID: d4a71c0f9b32
Revises: c9bc2555282e
Create Date: 2026-09-01 01:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d4a71c0f9b32"
down_revision: str | None = "c9bc2555282e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # event_type_enum에 '문제시도' 1종 추가(멱등·같은 트랜잭션에서 사용하지 않으므로 안전).
    op.execute("ALTER TYPE event_type_enum ADD VALUE IF NOT EXISTS '문제시도'")
    # attempt_event.skill_ids — 해소된 스킬 id 배열. nullable·기본값 없음(백필 날조 방지).
    op.add_column(
        "attempt_event",
        sa.Column("skill_ids", ARRAY(sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("attempt_event", "skill_ids")
    # PG는 enum 값 제거 미지원 — '문제시도'는 남긴다(no-op·관례·데이터 무손상).
