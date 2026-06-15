"""edge_type_enum에 'TRIGGERS_DISTRACTOR' 값 추가 — 슬108 distractor→오개념 관계 어휘

객관식 *오답 선지*(distractor)가 유발하는 *오개념*(misconception)을 잇는 관계 타입을
`edge_type_enum`에 추가한다. 기존 5종(선수·구성·유사·확장·대조)에 더해 1종만 추가하며,
*테이블 변경 0·기존 데이터 무손상*(ADD VALUE만)이다. 직전 `event_type_enum` 확장
마이그레이션(힌트제공·검산결과)과 *동형*이다.

**범위 주의(어휘만)**: 이 슬라이스는 enum *어휘*만 추가하고 `concept_edge`에 실제 간선을
적재하지 않는다 — `concept_edge`는 concept→concept(UUID FK) 테이블인데 misconception은 아직
그래프 노드가 아니라 L4 카탈로그(kebab id)다. 노드화 전까지 distractor→misconception 매핑은
op-code 카탈로그(`l4/misconception/distractor.py`)가 보유한다. 따라서 백엔드 엣지 로더
(`l1/concept_graph/backend_edge.py`)는 종전대로 PREREQUISITE만 적재한다(무변경).

upgrade:
  - `ALTER TYPE edge_type_enum ADD VALUE IF NOT EXISTS 'TRIGGERS_DISTRACTOR'`. PG 16은 트랜잭션
    내 ADD VALUE를 허용한다(같은 트랜잭션에서 그 값을 *사용*만 하지 않으면 안전 — 이 마이그레이션은
    추가만 하므로 안전). `IF NOT EXISTS`로 재실행 멱등.

downgrade:
  - PostgreSQL은 enum 값 *제거*를 지원하지 않는다(타입 재생성·컬럼 캐스팅 필요). 관례대로
    (event_type 확장 마이그레이션 동형) `pass`로 둔다 — 되돌리기 불가(no-op·데이터 무손상).

Revision ID: f5a6b7c8d9e0
Revises: e4f5a6b7c8d9
Create Date: 2026-06-15 10:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f5a6b7c8d9e0"
down_revision: str | None = "e4f5a6b7c8d9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # edge_type_enum에 'TRIGGERS_DISTRACTOR' 1종 추가(멱등). 테이블·기존 데이터 무변경.
    op.execute("ALTER TYPE edge_type_enum ADD VALUE IF NOT EXISTS 'TRIGGERS_DISTRACTOR'")


def downgrade() -> None:
    # PG는 enum 값 제거 미지원 — no-op(되돌리기 불가·관례). 데이터 무손상.
    pass
