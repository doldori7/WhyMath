"""misconception_hypothesis 테이블 (WH-1 2단계 활성 오개념 가설 per-student 영속·§8.4)

WH-1(소크라테스 튜터링 하네스) 2단계(설계 `04a_wh1_tutoring_harness.md` §8.4)의 *활성 가설
세트 영속* 좌석. 직전 슬라이스(#191) 순수 결정 로직(`l4/misconception/hypothesis.py`)이 만든
가설을 per-student로 적재하는 `misconception_hypothesis` 테이블을 *최초 생성*한다. ORM 정본은
`whymath_backend/db/models/misconception_hypothesis.py`(MisconceptionHypothesisRecord).
enum 없음(전부 기본 타입 — UUID·Text·Numeric·Integer·Boolean·TIMESTAMPTZ).

스키마:
  - `id`(UUID PK·`gen_random_uuid()` server_default — 모든 UUID PK 선례).
  - `user_id`(UUID nullable·**FK `user_profile.user_id`**) — 학생 결부 *민감* 데이터
    (activity.py problem_attempt.user_id 동형·인덱스). 사용자 삭제 시 정리는 상위 lifecycle 몫.
  - `misconception_id`(Text NOT NULL) — 카탈로그 오개념 id(kebab-case). **FK 아님**(카탈로그는
    코드 상수·느슨참조).
  - `confidence`(Numeric(3,2) NOT NULL) — 가설 현재 신뢰[0,1]. 클램프는 순수 로직 책임(가짜
    CHECK 두지 않음 — activity.py 방침).
  - `turns_since_evidence`(Integer NOT NULL·server_default 0)·`evidence_count`(Integer NOT
    NULL·server_default 1) — 순수 모델 동명 필드 영속 사본.
  - `is_active`(Boolean NOT NULL·server_default true) — 가지치기된 stale 가설을 *삭제 대신*
    false로 비활성화(증거 이력 보존·낙인 방지).
  - `created_at`/`updated_at`(TIMESTAMPTZ NOT NULL·server_default now()) — 운영 메타.

제약·인덱스(저장소 upsert·활성 세트 조회 접근 패턴):
  - `uq_misconception_hypothesis_user_mid`(user_id, misconception_id) — per-student per-오개념
    1행. 저장소가 이 키로 upsert(있으면 갱신·없으면 insert).
  - `idx_misconception_hypothesis_user_active`(user_id, is_active) — `get_active_hypotheses`
    학생별 활성 세트 로드.

upgrade:
  - `create_table("misconception_hypothesis", ...)` — FK to user_profile·유니크 제약·기본 타입만.
  - `idx_misconception_hypothesis_user_active` 생성(유니크 제약은 자체 인덱스 보유).

downgrade (왕복 안전 — CI `downgrade -1`→`upgrade head` 검증):
  - 인덱스 → 테이블 순 drop. enum 없으므로 PG 타입 명시 drop 불요(solution_nodes의
    node_verify_status_enum 정리 단계 같은 후처리 없음).

CLAUDE.md 개인정보: 본 테이블은 *미성년 학생 오개념 가설*(민감)이다. 평문 저장·동의 없는 학습
사용 금지는 저장·동의 계층(암호화·미들웨어·PIPA 권한 매트릭스) 책임이라 마이그레이션·ORM엔
가짜 CHECK를 두지 않는다(activity.py 패턴 동형 — 문서화만).

Revision ID: d3e4f5a6b7c8
Revises: c2d3e4f5a6b7
Create Date: 2026-06-13 13:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d3e4f5a6b7c8"
down_revision: str | None = "c2d3e4f5a6b7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "misconception_hypothesis",
        sa.Column(
            "id",
            sa.Uuid(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        # 민감 학생 데이터 — user_profile FK(activity.py 학생 데이터 FK 동형·nullable).
        sa.Column("user_id", sa.Uuid(), nullable=True),
        # 카탈로그 오개념 id(kebab-case) — FK 아님(코드 정본·느슨참조).
        sa.Column("misconception_id", sa.Text(), nullable=False),
        # 가설 현재 신뢰[0,1] — 클램프는 순수 로직 책임(가짜 CHECK 없음).
        sa.Column("confidence", sa.Numeric(precision=3, scale=2), nullable=False),
        sa.Column(
            "turns_since_evidence",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "evidence_count",
            sa.Integer(),
            server_default=sa.text("1"),
            nullable=False,
        ),
        # 가지치기된 stale 가설은 삭제 대신 false로 비활성화(이력 보존·낙인 방지).
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.true(),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_misconception_hypothesis")),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["user_profile.user_id"],
            name=op.f("fk_misconception_hypothesis_user_id_user_profile"),
        ),
        # per-student per-오개념 1행 — 저장소 upsert 충돌 키.
        sa.UniqueConstraint(
            "user_id",
            "misconception_id",
            name="uq_misconception_hypothesis_user_mid",
        ),
    )
    # 학생별 활성 가설 로드(get_active_hypotheses) 접근 경로.
    op.create_index(
        "idx_misconception_hypothesis_user_active",
        "misconception_hypothesis",
        ["user_id", "is_active"],
    )


def downgrade() -> None:
    op.drop_index(
        "idx_misconception_hypothesis_user_active",
        table_name="misconception_hypothesis",
    )
    op.drop_table("misconception_hypothesis")
