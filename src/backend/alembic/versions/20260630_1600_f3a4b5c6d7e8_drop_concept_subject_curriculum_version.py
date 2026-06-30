"""concept에서 subject·curriculum_version 컬럼 제거 — 교육과정 완전 Overlay 이관.

`grade_introduced`·`semester_introduced` 제거(rev d1e2f3a4b5c6)의 마무리다. 과목(subject)·
교육과정 판(curriculum_version)은 *개념의 의미가 아니라* 시간·국가에 따라 바뀌는 교육과정 조직
라벨이므로 개념 노드에 내장하지 않는다 — `curriculum_entry`(domain_label·curriculum_revision)가
단일 진실 Overlay다(math_dsl_risk_register.md Q5·Q8·Q10-③ "노드는 의미만"·
math_dsl_remediation_design.md §3).

데이터/런타임 안전:
  - 두 컬럼을 *조회·필터·정렬·그룹*하는 런타임 코드가 backend 전수에 없다(정합 게이팅은
    `Problem.curriculum_version`을 쓴다 — Concept과 독립). 적재기 write + API 응답 반환만 있었다.
  - `idx_concept_level (level, subject)`도 활용 쿼리가 없어 `(level)` 단일 컬럼으로 축소한다.
  - `subject`는 원천 코퍼스 `domain`/`subject_area`에서 *파생*된 값이라 비가역 손실이 아니다
    (향후 `curriculum_entry` 적재로 재구성 가능).
  - enum 타입 `subject_enum`·`curriculum_enum`은 `Problem`이 NOT NULL로 계속 쓰므로 *제거하지
    않는다*(컬럼만 drop·타입 보존).

upgrade:
  - `idx_concept_level` 재정의: `(level, subject)` → `(level)`.
  - `concept.subject`·`concept.curriculum_version` drop_column(2개).

downgrade:
  - 두 컬럼을 원래 정의(nullable 공유 enum·create_type=False)로 복원.
  - `idx_concept_level`을 `(level, subject)` 복합으로 복원.

Revision ID: f3a4b5c6d7e8
Revises: e2f3a4b5c6d7
Create Date: 2026-06-30 16:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f3a4b5c6d7e8"
down_revision: str | None = "e2f3a4b5c6d7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 교육과정은 curriculum_entry(Overlay)가 단일 진실 — subject 참조 인덱스 축소 후 컬럼 2개 제거.
    op.drop_index("idx_concept_level", table_name="concept")
    op.create_index("idx_concept_level", "concept", ["level"], unique=False)
    op.drop_column("concept", "subject")
    op.drop_column("concept", "curriculum_version")


def downgrade() -> None:
    # 원래 정의(nullable 공유 enum)로 복원. 데이터는 복원 불가(파생값·원천 코퍼스 잔존).
    op.add_column(
        "concept",
        sa.Column(
            "curriculum_version",
            postgresql.ENUM(
                "2009_REVISION",
                "2015_REVISION",
                "2022_REVISION",
                name="curriculum_enum",
                create_type=False,
            ),
            nullable=True,
        ),
    )
    op.add_column(
        "concept",
        sa.Column(
            "subject",
            postgresql.ENUM(
                "공통",
                "미적분",
                "확통",
                "기하",
                "인공지능수학",
                name="subject_enum",
                create_type=False,
            ),
            nullable=True,
        ),
    )
    op.drop_index("idx_concept_level", table_name="concept")
    op.create_index("idx_concept_level", "concept", ["level", "subject"], unique=False)
