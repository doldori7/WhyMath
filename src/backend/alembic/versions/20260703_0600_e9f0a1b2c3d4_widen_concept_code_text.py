"""concept.code VARCHAR(64) → TEXT 확폭 — Part 9(#409) 재-ID 오버플로 결함 수정.

Part 9(#409)가 개념을 `math.<area>.<slug>`(교육과정 무관 의미론)로 전면 재-ID하며 concept_id가
최장 **83자**(예 `data/corpus/concept_graph_v1/graph.json`의
'math.measurement.pyeonghaengsabyeonhyeong-samgakhyeong-sadarikkol-mareummoui-neolbi')가 됐다.
backend `concept.code`(=concept_id 적재 컬럼)는 여전히 String(64)라, 통합 로더가 적재 시
`value too long for type character varying(64)`로 실패한다(#409 병합 후 main push-CI의
`backend — 마이그레이션·통합 (실 PG)` 잡이 실제 red). #409 후속 목록엔 이 컬럼 폭이 누락돼 있었다.

`code`를 **TEXT**로 확폭한다 — 같은 UC 키의 다른 투영 `concept_node.concept_id`가 이미 TEXT라
단일 키공간과 정합하고, 향후 slug 성장에도 오버플로가 없다(경계 없는 저장). unique 제약/인덱스는
유지되며(PG는 TEXT 유니크 btree 인덱스를 정상 지원), FK 무영향이다 — 타 테이블
(`concept_edge`·`problem_concept`)은 `concept.concept_id`(UUID)를 참조하지 `code`를 참조하지 않는다.

upgrade(확폭 — 무손실·데이터 무영향):
  - `String(64) → Text`. 기존 행 전건 적합(확폭)이라 안전. 유니크 인덱스(`idx_concept_code`)는
    타입 변경으로 자동 재구축된다.

downgrade(대칭 축소):
  - 전제: 65자+ code 행 미존재. Part 9 이후엔 83자 행이 실재하므로, downgrade는 PG가
    `value too long`으로 **정직하게 실패**한다(조용한 절단 대신 운영자가 장문 행을 먼저 정리해야
    함 — mis_id_widen downgrade의 정직한 실패 선례와 동형). Part 9 재-ID를 되돌리지 않는 한 이
    downgrade는 실행 불가가 정상이다.

Revision ID: e9f0a1b2c3d4
Revises: d8e9f0a1b2c3
Create Date: 2026-07-03 06:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e9f0a1b2c3d4"
down_revision: str | None = "d8e9f0a1b2c3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # code(=concept_id UC) String(64) → Text 확폭(무손실·유니크 유지·FK 무영향).
    op.alter_column(
        "concept",
        "code",
        existing_type=sa.String(length=64),
        type_=sa.Text(),
        existing_nullable=False,
    )


def downgrade() -> None:
    # 65자+ code(Part 9 재-ID 83자 등) 존재 시 PG value too long 정직한 실패(절단 금지).
    op.alter_column(
        "concept",
        "code",
        existing_type=sa.Text(),
        type_=sa.String(length=64),
        existing_nullable=False,
    )
