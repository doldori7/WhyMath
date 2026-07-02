"""임베딩 3테이블에 subject 축 추가 — namespace = 테이블(kind) × subject (과목 확장 S1).

`subject_expansion_readiness.md` §8 "임베딩 namespace 과목 축"의 착수(invariant ⑨ 트랙).
`misconception_embedding`·`concept_embedding`·`atom_embedding` 세 임베딩 테이블에 **교과 축**
subject 컬럼('수학'·'물리' — 교과 레벨)을 추가한다. 임베딩 namespace의 논리 경계는
"테이블(kind) × subject"다(`l1/embedding_primitives.py` namespace 불변식) — kind는 테이블명이
이미 함의하므로 별도 컬럼을 두지 않고, subject만 컬럼으로 승격한다.

의미 축 구분(각 ORM docstring 교차 명기):
  - `subject`는 **교과** 레벨('수학'·'물리')이다 — 교육과정 스코핑의 정본은
    `CurriculumEntry.subject`(Overlay)이고, 임베딩 행의 subject는 *콘텐츠 팩 태그*
    (적재기가 `DEFAULT_EMBEDDING_SUBJECT` 상수를 주입하는 스코프 라벨)다.
  - `concept_node.domain`(수학 내부 영역 축 '[고]미적분' 등)과 직교한다.

데이터/런타임 안전 (rev `a4b5c6d7e8f9` curriculum_entry subject 축과 동형 선례):
  - ADD COLUMN NOT NULL + `server_default '수학'` — 기존 행(전량 수학 임베딩)이 무손상
    백필되고(default가 곧 진실), 기존 INSERT 경로도 깨지지 않는다(가산적·BREAKING-free).
    server_default는 ORM(`db/models/*_embedding.py`)·`DEFAULT_EMBEDDING_SUBJECT`와 동일하게
    *영구 유지*한다(드리프트 0 — 거버넌스 테스트가 동결).
  - **재임베딩 0**: subject는 컬럼/스코프에만 들어가고 임베딩 *텍스트*(`join_embedding_text`
    계열·`EMBEDDING_TEXT_FORMAT_VERSION==2`)에는 안 들어간다 — text_hash·벡터 전부 불변이라
    기존 사전 임베딩이 그대로 유효하다.
  - `subject`는 개방 TEXT(enum 아님) — `curriculum_entry.subject` 선례 그대로. 값 범위 가드는
    적재기(상수 주입) 책임.

upgrade: 3테이블 각각 `subject` ADD COLUMN(Text NOT NULL, server_default '수학').
downgrade: 3컬럼 drop(대칭·가역 — 데이터 손실은 subject 라벨뿐·벡터 무손상).

Revision ID: b6c7d8e9f0a1
Revises: a5b6c7d8e9f0
Create Date: 2026-07-02 16:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b6c7d8e9f0a1"
down_revision: str | None = "a5b6c7d8e9f0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# subject 축을 받는 임베딩 3테이블 — kind(자산 종류)는 테이블명이 함의(별도 컬럼 없음).
_EMBEDDING_TABLES: tuple[str, ...] = (
    "misconception_embedding",
    "concept_embedding",
    "atom_embedding",
)


def upgrade() -> None:
    # ── subject 컬럼 추가 — NOT NULL + server_default '수학'(기존 행 무손상 백필). ──
    # ORM(sa.Text)·DEFAULT_EMBEDDING_SUBJECT('수학')와 동일 타입·값(드리프트 0).
    for table in _EMBEDDING_TABLES:
        op.add_column(
            table,
            sa.Column("subject", sa.Text(), server_default="수학", nullable=False),
        )


def downgrade() -> None:
    # ── subject 컬럼 drop(추가 역순·가역) — 벡터·text_hash 무손상(라벨만 제거). ──
    for table in reversed(_EMBEDDING_TABLES):
        op.drop_column(table, "subject")
