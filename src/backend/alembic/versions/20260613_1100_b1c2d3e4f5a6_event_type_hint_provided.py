"""event_type_enum에 '힌트제공' 값 추가 — WH-1 도움 감소 곡선(지표 ⑤) 적재 좌석

WH-1 튜터링 하네스 0단계 지표 ⑤(도움 감소 곡선)를 NOT_INSTRUMENTED→MEASURED로 끌어올리는
슬라이스의 *적재 좌석*. coach가 매 응답 턴에 결정한 hint_level(1~4·답 미루기 노출량)을
`attempt_event`에 *supply*(AI가 제공한 레벨) 신호로 기록하려면 `event_type_enum`에 새 라벨이
필요하다. 직전 verify 슬라이스(검산결과)와 *동형*이다 — 기존 9종(문제읽기·조건분석·그래프그리기·
계산·지움·막힘·힌트요청·답입력·검산결과)에 더해 '힌트제공' 1종만 추가한다. *테이블 변경 0·기존
데이터 무손상*(ADD VALUE만).

의미 주의: 기존 '힌트요청'은 학생이 *요청*한 demand 신호다. 도움 감소 곡선은 AI가 *제공한*
hint_level(supply·graded 1~4)의 시간 추세이므로 '힌트요청'을 재사용하면 의미가 어긋난다 —
그래서 supply 전용 '힌트제공'을 새로 추가한다. (`attempt_mode_enum`에도 동명 '힌트제공'이 있으나
이는 *다른 PG 타입*·풀이 방식 라벨이라 무관하다.) event_data={hint_level:int}로 적재된다.

upgrade:
  - `ALTER TYPE event_type_enum ADD VALUE IF NOT EXISTS '힌트제공'`. PG 16은 트랜잭션 내
    ADD VALUE를 허용한다(같은 트랜잭션에서 그 값을 *사용*만 하지 않으면 안전 — 이 마이그레이션은
    추가만 하므로 안전). `IF NOT EXISTS`로 재실행 멱등(이미 있으면 무시).

downgrade:
  - PostgreSQL은 enum 값 *제거*를 지원하지 않는다(타입 재생성·컬럼 캐스팅이 필요하고 그 값을
    쓰는 행이 있으면 불가). 관례대로(직전 검산결과 마이그레이션 동형) `pass`로 둔다 — 되돌리기
    불가(no-op·데이터 무손상).

Revision ID: b1c2d3e4f5a6
Revises: a0b1c2d3e4f5
Create Date: 2026-06-13 11:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b1c2d3e4f5a6"
down_revision: str | None = "a0b1c2d3e4f5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # event_type_enum에 '힌트제공' 1종 추가(멱등). 테이블·기존 데이터 무변경.
    op.execute("ALTER TYPE event_type_enum ADD VALUE IF NOT EXISTS '힌트제공'")


def downgrade() -> None:
    # PG는 enum 값 제거 미지원 — no-op(되돌리기 불가·관례). 데이터 무손상.
    pass
