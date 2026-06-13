"""event_type_enum에 '검산결과' 값 추가 — WH-1 검산(verify) 결과 이벤트 적재 좌석

WH-1 튜터링 하네스 0단계 지표 ①(verify 통과율)을 NOT_INSTRUMENTED→MEASURED로 끌어올리는
슬라이스의 *적재 좌석*. coach가 학생 풀이의 *거짓 수치 관계*를 결정론 검증(`arithmetic_validator`)
으로 검출한 결과(통과/적발)를 `attempt_event`에 기록하려면 `event_type_enum`에 새 라벨이
필요하다. 기존 8종(문제읽기·조건분석·그래프그리기·계산·지움·막힘·힌트요청·답입력)에 더해
'검산결과' 1종만 추가한다 — *테이블 변경 0·기존 데이터 무손상*(ADD VALUE만).

이는 binary 검산(통과=거짓관계 미적발 / 적발=거짓관계 발견)이지 3-state(정답/오답/검증불가)
verify가 아니다 — `event_data={passed: bool, error_kind: str|None}`로 적재된다.

upgrade:
  - `ALTER TYPE event_type_enum ADD VALUE IF NOT EXISTS '검산결과'`. PG 16은 트랜잭션 내
    ADD VALUE를 허용한다(같은 트랜잭션에서 그 값을 *사용*만 하지 않으면 안전 — 이 마이그레이션은
    추가만 하므로 안전). `IF NOT EXISTS`로 재실행 멱등(이미 있으면 무시).

downgrade:
  - PostgreSQL은 enum 값 *제거*를 지원하지 않는다(타입 재생성·컬럼 캐스팅이 필요하고 그 값을
    쓰는 행이 있으면 불가). 관례대로 `pass`로 둔다 — 되돌리기 불가(no-op·데이터 무손상).

Revision ID: a0b1c2d3e4f5
Revises: f9a0b1c2d3e4
Create Date: 2026-06-13 10:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a0b1c2d3e4f5"
down_revision: str | None = "f9a0b1c2d3e4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # event_type_enum에 '검산결과' 1종 추가(멱등). 테이블·기존 데이터 무변경.
    op.execute("ALTER TYPE event_type_enum ADD VALUE IF NOT EXISTS '검산결과'")


def downgrade() -> None:
    # PG는 enum 값 제거 미지원 — no-op(되돌리기 불가·관례). 데이터 무손상.
    pass
