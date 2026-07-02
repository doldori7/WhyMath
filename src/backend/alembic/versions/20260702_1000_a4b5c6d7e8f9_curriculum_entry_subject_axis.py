"""curriculum_entry에 subject 축 추가 — 복합 의미키 (concept_id, country_code) → 3-튜플.

과목 확장 준비 S1(`subject_expansion_readiness.md` §9 — 유일한 마이그레이션 슬라이스).
`subject`는 **교과** 레벨 과목 축('수학'·'물리')이다 — 같은 개념('벡터')이 같은 나라의 수학·
물리 양쪽 교육과정에 등장할 수 있어 셀 의미키가 (concept_id, country_code, subject) 3-튜플로
확장된다. 과목 스코핑의 정본은 개념 노드가 아니라 이 Overlay다(rev `f3a4b5c6d7e8`이 Concept에서
subject를 *제거* — "노드는 의미만"·그 축을 노드로 되돌리지 않는다). ⚠️ NCIC
`AchievementStandard.subject`(**과목** 레벨 — '공통수학1')와 이름만 같고 granularity가 다르다.

데이터/런타임 안전:
  - ADD COLUMN NOT NULL + `server_default '수학'` — 기존 KR 수학 행이 무손상 백필되고(전량
    수학이므로 default가 곧 진실), 기존 INSERT 경로도 깨지지 않는다(가산적·BREAKING-free).
    server_default는 ORM(`db/models/curriculum_entry.py`)과 동일하게 *영구 유지*한다(드리프트 0).
  - UNIQUE 교체는 drop → create 순서라 같은 컨벤션 이름(`uq_curriculum_entry_concept_id` —
    `uq_%(table_name)s_%(column_0_name)s`, 선두 컬럼 불변)을 재사용한다(ORM 무명 제약과 정합).
  - `subject`는 개방 str(enum 아님) — `country_code` 선례 그대로. Phase 1 산출물 '수학' 외
    금지 범위 가드는 파이프라인 책임(스키마 validation_invariants).

upgrade:
  - `curriculum_entry.subject` ADD COLUMN(String NOT NULL, server_default '수학').
  - UNIQUE(concept_id, country_code) drop → UNIQUE(concept_id, country_code, subject) 생성.

downgrade(대칭·역순):
  - 3-튜플 UNIQUE drop → 2-튜플 UNIQUE 복원 → subject 컬럼 drop.
  - 전제: 비수학 셀 미존재(Phase 1 산출물은 '수학'뿐) — 같은 (concept_id, country_code)에
    교과만 다른 두 행이 있으면 2-튜플 UNIQUE 복원이 실패한다(정직한 실패 — 조용한 데이터
    손실 대신 운영자가 비수학 셀을 먼저 정리해야 한다).

Revision ID: a4b5c6d7e8f9
Revises: f3a4b5c6d7e8
Create Date: 2026-07-02 10:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a4b5c6d7e8f9"
down_revision: str | None = "f3a4b5c6d7e8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# 기존/신규 UNIQUE 제약 이름 — 명명 규약 `uq_%(table_name)s_%(column_0_name)s`(db/base.py).
# 선두 컬럼(concept_id)이 불변이라 2-튜플·3-튜플 모두 같은 이름이다(드리프트 0·재사용).
_UQ_NAME = "uq_curriculum_entry_concept_id"


def upgrade() -> None:
    # ── ① subject 컬럼 추가 — NOT NULL + server_default '수학'(기존 행 무손상 백필). ──
    op.add_column(
        "curriculum_entry",
        sa.Column("subject", sa.String(), server_default="수학", nullable=False),
    )
    # ── ② 기존 2-튜플 UNIQUE drop → ③ 3-튜플 UNIQUE 생성(같은 컨벤션 이름 재사용). ──
    op.drop_constraint(_UQ_NAME, "curriculum_entry", type_="unique")
    op.create_unique_constraint(
        op.f(_UQ_NAME),
        "curriculum_entry",
        ["concept_id", "country_code", "subject"],
    )


def downgrade() -> None:
    # ── ③ 3-튜플 UNIQUE drop → ② 2-튜플 UNIQUE 복원(비수학 셀 존재 시 정직한 실패). ──
    op.drop_constraint(_UQ_NAME, "curriculum_entry", type_="unique")
    op.create_unique_constraint(
        op.f(_UQ_NAME),
        "curriculum_entry",
        ["concept_id", "country_code"],
    )
    # ── ① subject 컬럼 drop(추가 역순). ──
    op.drop_column("curriculum_entry", "subject")
