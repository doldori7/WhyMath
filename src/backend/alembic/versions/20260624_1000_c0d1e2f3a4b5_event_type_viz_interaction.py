"""event_type_enum에 '시각화조작' 값 추가 — L5 시각화 탐구적 조작 신호 적재 좌석. 슬라이스 96-J.

F(슬라이스 96-F)는 학생의 시각화 조작(슬라이더·3D 식·확률 시뮬)을 `attempt_event`에 적재했지만
`EventType.그래프그리기`(그래프를 그려 *답함*)로 분류해, *답안 작도*와 *탐구적 조작*이 한 지표로
뭉개졌다. L2 행동 분석이 그래프그리기 빈도를 신호로 쓸 때 오염된다. J는 *능동 탐구·메타인지* 신호를
분리하려 전용 라벨 '시각화조작'을 추가한다. 직전 '힌트제공'/'검산결과' 슬라이스와 *동형* —
기존 10종에 1종만 더한다. *테이블 변경 0·기존 데이터 무손상*(ADD VALUE만).

의미 주의: '그래프그리기'는 학생이 그래프를 *그려 답하는* 활동(작도)이다. '시각화조작'은 약점개념
scene의 임베드 계산기에서 학생이 파라미터·식을 바꿔 *본질을 탐색*하는 행동으로, 답안이 아니라
탐구·메타인지 신호다. 약점개념 흐름엔 problem/attempt가 없어 컨텍스트는 concept_id/scene_id를
event_data에 싣고 attempt_id/problem_id는 NULL로 둔다(거짓 연결 금지).

upgrade:
  - `ALTER TYPE event_type_enum ADD VALUE IF NOT EXISTS '시각화조작'`. PG 16은 트랜잭션 내
    ADD VALUE를 허용한다(같은 트랜잭션에서 그 값을 *사용*만 하지 않으면 안전 — 이 마이그레이션은
    추가만 하므로 안전). `IF NOT EXISTS`로 재실행 멱등(이미 있으면 무시).

downgrade:
  - PostgreSQL은 enum 값 *제거*를 지원하지 않는다. 관례대로(직전 힌트제공 마이그레이션 동형)
    `pass`로 둔다 — 되돌리기 불가(no-op·데이터 무손상).

Revision ID: c0d1e2f3a4b5
Revises: b9c0d1e2f3a4
Create Date: 2026-06-24 10:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c0d1e2f3a4b5"
down_revision: str | None = "b9c0d1e2f3a4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # event_type_enum에 '시각화조작' 1종 추가(멱등). 테이블·기존 데이터 무변경.
    op.execute("ALTER TYPE event_type_enum ADD VALUE IF NOT EXISTS '시각화조작'")


def downgrade() -> None:
    # PG는 enum 값 제거 미지원 — no-op(되돌리기 불가·관례). 데이터 무손상.
    pass
