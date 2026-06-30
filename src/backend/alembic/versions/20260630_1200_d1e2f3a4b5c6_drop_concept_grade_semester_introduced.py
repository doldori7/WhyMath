"""concept에서 grade_introduced·semester_introduced 컬럼 제거 — 교육과정 Overlay 분리.

교육과정 도입정보(학년·학기)는 *개념 노드에 내장하지 않는다* — 교육과정은 시간·국가에 따라
바뀌는 Overlay이므로 `curriculum_entry`(국가별 introduced_grade·required_depth)가 단일 진실
원천이다(math_dsl_risk_register.md Q5·Q8·Q10-③ "노드는 의미만"). `concept.grade_introduced`·
`concept.semester_introduced`는 적재된 적이 없고(전량 NULL·backend_concept.py 미매핑 주석)
`curriculum_entry`와 중복이라 제거한다(Overlay 분리·math_dsl_remediation_design.md).

데이터 안전: 두 컬럼은 전량 NULL이라 drop이 데이터 손실 0이다. `curriculum_version`·`subject`는
별도 소비처가 있어 이번 범위 밖(잔존 — 완전 Overlay 이관은 설계 항목).

upgrade:
  - `concept.grade_introduced`·`concept.semester_introduced` drop_column(2개).

downgrade:
  - 두 컬럼을 nullable Integer로 복원(원래 정의 그대로·데이터는 복원 불가하나 전량 NULL이라 무의미).

Revision ID: d1e2f3a4b5c6
Revises: c0d1e2f3a4b5
Create Date: 2026-06-30 12:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d1e2f3a4b5c6"
down_revision: str | None = "c0d1e2f3a4b5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 교육과정 도입정보는 curriculum_entry(Overlay)가 단일 진실 — 노드 컬럼 2개 제거(전량 NULL).
    op.drop_column("concept", "grade_introduced")
    op.drop_column("concept", "semester_introduced")


def downgrade() -> None:
    # 원래 정의(nullable Integer)로 복원. 데이터는 전량 NULL이었으므로 복원 불가가 무의미.
    op.add_column("concept", sa.Column("semester_introduced", sa.Integer(), nullable=True))
    op.add_column("concept", sa.Column("grade_introduced", sa.Integer(), nullable=True))
