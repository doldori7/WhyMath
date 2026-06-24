"""atom_probe 테이블 — ②진단문항·③소크라테스 code 키 PG 프로젝션 (원자 마이그레이션 Phase 3 Slice 3)

원자 백본 마이그레이션 Phase 3 Slice 3. 원자 백본 코퍼스(`data/corpus/atom_graph_v1/graph.json`)의
세부개념 원자가 보유한 **②진단문항**(발문·정답/통과기준·오답신호)과 **③소크라테스 질문**을 담을
**code 키 PG 프로젝션 테이블**을 만든다 — 학습 장면(L2 진단·L4 소크라테스 코칭·L6 모드)이 backend
조인으로 탐침을 끌어쓰기 위한 백킹(`atom_node`/`concept_content` 동일 설계 철학·신규 테이블이라
additive·무영향).

`problem`(UUID PK·provenance·저작권 validator)·`dialogue`(런타임 로그)와 grain이 어긋나 결합하지
않고, Slice 1(`concept_content`) 선례대로 신규 경량 code-PK 테이블을 둔다. PK는 `code`(원자 세부개념
code 예 '2수01-01-2'·'CALC1-C01'). FK 0(loose ref·재적재 독립성).

upgrade:
  - `atom_probe` 테이블:
    - `code`(TEXT PK)·`name`(TEXT NOT NULL) — 식별·표시.
    - `school_level`·`subject_area`·`subunit`(TEXT NULL) — 필터·메타.
    - `diagnostic_item`·`diagnostic_answer`·`diagnostic_signal`(TEXT NULL) — ②진단문항 3필드
      (전량 자체/AI 작성·보유 허용).
    - `socratic_question`(TEXT NULL) — ③소크라테스 질문(자체/AI 작성).
    - `intrinsic_difficulty`(INTEGER NULL) — 난이도 1~5.
    - `standard_codes`(TEXT[] NOT NULL DEFAULT '{}') — NCIC 성취기준 *코드* 배열(본문 아님).
    - `review_status`(TEXT NOT NULL) — 'ai_estimated' 게이팅 플래그(탐침은 AI 추정·검수필요·정직
      표기·PG native enum 미생성·plain text·atom_node/concept_content 동형).
    - `updated_at`(TIMESTAMPTZ NOT NULL DEFAULT now()) — 신선도.
  - **인덱스 2종**: `ix_atom_probe_school_level`(학교급 필터)·`ix_atom_probe_subject_area`
    (과목 필터) — 탐침 서빙·검수 빈번 필터.
  - 성취기준 *본문*은 코퍼스에 없고(standard_codes 코드만 다리) 이 테이블도 본문 컬럼이 없다.

downgrade (왕복 안전 — CI가 `downgrade base`→`upgrade head` 왕복 검증):
  - `atom_probe` 테이블만 drop(인덱스 포함). native ENUM 0(전부 TEXT)·FK 0이라 객체 무관.

Revision ID: b9c0d1e2f3a4
Revises: a8b9c0d1e2f3
Create Date: 2026-06-23 10:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b9c0d1e2f3a4"
down_revision: str | None = "a8b9c0d1e2f3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ②진단문항·③소크라테스 code 키 프로젝션 — 자체/AI 작성(native ENUM 0·전부 TEXT/INTEGER·FK 0).
    op.create_table(
        "atom_probe",
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("school_level", sa.Text(), nullable=True),
        sa.Column("subject_area", sa.Text(), nullable=True),
        sa.Column("subunit", sa.Text(), nullable=True),
        sa.Column("diagnostic_item", sa.Text(), nullable=True),
        sa.Column("diagnostic_answer", sa.Text(), nullable=True),
        sa.Column("diagnostic_signal", sa.Text(), nullable=True),
        sa.Column("socratic_question", sa.Text(), nullable=True),
        sa.Column("intrinsic_difficulty", sa.Integer(), nullable=True),
        sa.Column(
            "standard_codes",
            ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::text[]"),
        ),
        sa.Column("review_status", sa.Text(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("code", name=op.f("pk_atom_probe")),
    )
    # 필터 보조 인덱스 — school_level(학교급)·subject_area(과목) (탐침 서빙·검수 빈번 필터).
    op.create_index("ix_atom_probe_school_level", "atom_probe", ["school_level"])
    op.create_index("ix_atom_probe_subject_area", "atom_probe", ["subject_area"])


def downgrade() -> None:
    # 인덱스 → 테이블 drop. native ENUM·FK 0이라 다른 객체 영향 없음(왕복 안전).
    op.drop_index("ix_atom_probe_subject_area", table_name="atom_probe")
    op.drop_index("ix_atom_probe_school_level", table_name="atom_probe")
    op.drop_table("atom_probe")
