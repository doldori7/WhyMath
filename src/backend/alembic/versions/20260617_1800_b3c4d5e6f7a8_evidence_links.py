"""evidence_links (WH-1 §2.3 학습 증거 그래프 — 증거→가설 엣지·삭제권 연쇄)

WH-1 튜터링 하네스 2단계(설계 `04a_wh1_tutoring_harness.md` §2.3 학습 증거 그래프·§3 도구7
`log_evidence`)의 영속 좌석. 개별 학습 이벤트가 어떤 오개념 가설을 지지/반박하는지 기록하는 엣지
테이블. ORM 정본은 `whymath_backend/db/models/evidence_link.py`(EvidenceLink).

★개인정보(04a §2.3 v0.2·R11): 증거 그래프는 미성년자 인지·행동 정밀 프로파일 → **삭제권 연쇄를
1차 마이그레이션에 포함**(설계 요구·"나중에 붙이기 어려움"). `student_id`는 `user_profile.user_id`
FK **ON DELETE CASCADE** — 학생 삭제 시 증거 자동 연쇄 삭제. `retention_until` 경과 레코드는 야간
배치(`evidence_store.purge_expired`)로 파기.

`evidence_links`(§2.3):
  - `link_id`(BIGSERIAL PK·이벤트 볼륨·DB-assigned) · `session_id`(UUID NOT NULL·**FK 아님**) ·
    `student_id`(UUID NOT NULL·**FK user_profile ON DELETE CASCADE**·삭제권 핵심).
  - `event_id`(BIGINT nullable·**FK 아님**·attempt_event 복합 PK라 단일 FK 불가·느슨참조) ·
    `misconception_id`(TEXT NOT NULL·**FK 아님**·인코드 카탈로그·`evidence_store`가 CATALOG_BY_ID
    대조) · `node_id`(TEXT nullable·**FK 아님**·concept_id 느슨참조).
  - `polarity`(SMALLINT NOT NULL·CHECK ∈ {−1,+1}·+1 지지/−1 반박) · `weight`(REAL nullable) ·
    `retention_until`(DATE nullable) · `created_at`(TIMESTAMPTZ NOT NULL·now()).
  - 인덱스 `idx_evidence_student_mid`(student_id, misconception_id — 삭제권 조회 + 가설-증거 진단
    조인) · `idx_evidence_retention`(retention_until — 야간 배치 파기). CHECK `polarity IN (-1,1)`.

upgrade: `create_table` + FK(CASCADE) + CHECK + 인덱스 2. enum 0.
downgrade (왕복 안전 — CI가 `downgrade -1`/`downgrade base`→`upgrade head` 검증): 인덱스 2 →
테이블 drop(CHECK·FK 동반 제거·enum 없음).

CLAUDE.md 개인정보: `evidence_links`는 민감 학생 데이터(미성년 인지·행동)이나 *식별자·극성·가중치·
날짜*만 담아 자유텍스트 PII 부재(평문 적정·`misconception_hypothesis` 동일 방침). 삭제권 CASCADE +
retention 배치로 권리 보장.

Revision ID: b3c4d5e6f7a8
Revises: a2b3c4d5e6f7
Create Date: 2026-06-17 18:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b3c4d5e6f7a8"
down_revision: str | None = "a2b3c4d5e6f7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "evidence_links",
        # BIGSERIAL PK — 이벤트 볼륨·DB-assigned(gen_random_uuid 없음·attempt_event 선례).
        sa.Column("link_id", sa.BigInteger(), autoincrement=True, nullable=False),
        # 세션 맥락 — FK 아님(느슨참조).
        sa.Column("session_id", sa.Uuid(), nullable=False),
        # ★삭제권 핵심 — user_profile FK ON DELETE CASCADE.
        sa.Column("student_id", sa.Uuid(), nullable=False),
        # 느슨참조 — attempt_event 복합 PK라 단일 FK 불가.
        sa.Column("event_id", sa.BigInteger(), nullable=True),
        # 오개념 카탈로그 id — FK 아님(인코드 카탈로그·스토어가 CATALOG_BY_ID 대조).
        sa.Column("misconception_id", sa.Text(), nullable=False),
        # 커리큘럼 노드(concept_id) — FK 아님(느슨 TEXT 참조).
        sa.Column("node_id", sa.Text(), nullable=True),
        sa.Column("polarity", sa.SmallInteger(), nullable=False),
        sa.Column("weight", sa.Float(), nullable=True),
        sa.Column("retention_until", sa.Date(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("link_id", name=op.f("pk_evidence_links")),
        # ★삭제권 연쇄 — 학생 삭제 시 증거 자동 제거.
        sa.ForeignKeyConstraint(
            ["student_id"],
            ["user_profile.user_id"],
            name=op.f("fk_evidence_links_student_id_user_profile"),
            ondelete="CASCADE",
        ),
        # 극성 이중 가드(+1/−1만).
        sa.CheckConstraint("polarity IN (-1, 1)", name="ck_evidence_links_polarity"),
    )
    # 삭제권 조회(student_id 선행) + 가설-증거 진단 조인.
    op.create_index(
        "idx_evidence_student_mid", "evidence_links", ["student_id", "misconception_id"]
    )
    # 보존 기한 야간 배치 파기 스캔.
    op.create_index("idx_evidence_retention", "evidence_links", ["retention_until"])


def downgrade() -> None:
    op.drop_index("idx_evidence_retention", table_name="evidence_links")
    op.drop_index("idx_evidence_student_mid", table_name="evidence_links")
    # 테이블 drop이 CHECK·FK도 함께 제거(enum 없음).
    op.drop_table("evidence_links")
