"""achievement_standard.evaluation_criteria_codes + achievement_level_unit (CUR-07)

`docs/architecture/curriculum_module_gap_review_r2.md` §3 D5 — CUR-05가 회수한
`achievement_criteria_v1` 코퍼스(13 school_level×subject 세트: `standard_criteria_coverage`
459건·`achievement_levels_by_unit` 54건)를 실측 근거로 `AchievementStandard` 정본 스키마를
확장한다. 설계 트레이드오프는 `whymath_backend/schema/standard.py` 모듈 docstring "CUR-07 확장"이
기록한다 — 요약:

  ① `standard_criteria_coverage`(official_code 단위 1:N) — 실측 459/459가 `standards_v1`의
     '2015 개정' official_code 집합과 정확히 일치(교차검증 완료)하므로 `achievement_standard`에
     **컬럼 추가**: `evaluation_criteria_codes ARRAY(TEXT) NOT NULL DEFAULT '{}'`(parent_codes와
     동일 배열 패턴). 매칭·채움은 로더(`l1/standards/criteria_loader.py`) 몫 — 이 마이그레이션은
     스키마만 연다.
  ② `achievement_levels_by_unit`(unit 문자열 단위) — unit 어휘가 domain/sub_domain·
     unit_hierarchy 어느 쪽과도 실측상 정합하지 않아(교집합 0 실측) 개별 성취기준에 안전하게
     귀속시킬 근거가 없다. **별도 테이블** `achievement_level_unit`(자연키
     (school_level,subject,unit)·FK 없음)을 신설한다 — 개별 성취기준과의 연결은 범위 밖(설계
     결정, 우연한 누락 아님).

둘 다 additive(기존 achievement_standard 행 0 충돌 — 컬럼은 server_default가 채우고, 신규
테이블은 그 자체로 무충돌).

downgrade(왕복 안전 — CI backend-migrations 잡이 `downgrade base`→`upgrade head` 왕복 검증):
  신규 테이블 drop → 신규 컬럼 drop(생성 역순). FK·enum 없음이라 후처리 불요.

Revision ID: fcfdfc277348
Revises: b8e76fe238d0
Create Date: 2026-08-11 14:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "fcfdfc277348"
down_revision: str | None = "b8e76fe238d0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── ① achievement_standard.evaluation_criteria_codes (additive 컬럼) ──
    # parent_codes와 동일 패턴 — NOT NULL + server_default 빈 배열이라 기존 행 무충돌.
    op.add_column(
        "achievement_standard",
        sa.Column(
            "evaluation_criteria_codes",
            ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::text[]"),
        ),
    )

    # ── ② achievement_level_unit (신규 독립 테이블 — FK 없음) ──
    op.create_table(
        "achievement_level_unit",
        sa.Column(
            "unit_id",
            sa.Uuid(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        # 코퍼스 출처 KICE 보고서 구분('고등학교'|'초중학교') — achievement_standard.school_type과
        # 다른 어휘(모듈 docstring)라 FK·공유 enum 없이 자유 문자열.
        sa.Column("school_level", sa.String(), nullable=False),
        sa.Column("subject", sa.String(), nullable=False),
        sa.Column("unit", sa.String(), nullable=False),
        sa.Column(
            "levels",
            ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::text[]"),
        ),
        sa.Column("source_document", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("unit_id", name=op.f("pk_achievement_level_unit")),
        # 자연 유일키 — 같은 (보고서구분, 과목, 단원) 재적재 시 멱등 upsert 대상.
        sa.UniqueConstraint(
            "school_level",
            "subject",
            "unit",
            name="uq_achievement_level_unit_school_subject_unit",
        ),
    )
    # 과목 단위 조회 경로(예: '고등학교'의 '심화수학Ⅰ' 단원별 등급 목록).
    op.create_index(
        "idx_achievement_level_unit_subject",
        "achievement_level_unit",
        ["school_level", "subject"],
        unique=False,
    )


def downgrade() -> None:
    # 생성 역순 — 신규 테이블 → 신규 컬럼.
    op.drop_index(
        "idx_achievement_level_unit_subject",
        table_name="achievement_level_unit",
    )
    op.drop_table("achievement_level_unit")
    op.drop_column("achievement_standard", "evaluation_criteria_codes")
