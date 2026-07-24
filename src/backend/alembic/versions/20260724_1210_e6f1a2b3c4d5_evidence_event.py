"""evidence event (L2) — 학습목표별 유형 달성 증거 하이퍼테이블

교수법 DSL 검토서(`docs/reviews/260724_v2_migration_pedagogy_dsl_review.md`)의 수정 목표 스키마
(`260724_v2_migration_pedagogy_dsl.alembic_draft.py`) L2 부분을 정합 구현한다.

이 리비전(L2)은 L3(pedagogy_pack_dsl·앞 리비전)과 **계층 경계가 달라 분리**한 학습자 데이터
하이퍼테이블 `evidence_event`를 만든다(검토서 H3 — 역방향 의존 금지). `knowledge_type` enum은
앞 리비전(L3)이 이미 소유·생성하므로 여기서는 재사용만 한다(create_type=False·downgrade에서
drop하지 않음).

반영 지적:
  B1  payload(원문 발화·미성년 데이터)는 평문 금지 → payload_encrypted/payload_nonce +
      retention_until(dialogue_turn 봉투 암호화 선례). 비민감 메타만 meta(JSONB) 평문.
  H3  attempt_event 선례 미러 — surrogate BigInteger + 파티션 키 time을 복합 PK로.
      objective_id/session_id는 FK 아님(하이퍼테이블 느슨참조).

Revision ID: e6f1a2b3c4d5
Revises: d5e6f0a1b2c3
Create Date: 2026-07-24 12:10:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e6f1a2b3c4d5"
down_revision: str | None = "d5e6f0a1b2c3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# knowledge_type enum — 앞 리비전(L3·d5e6f0a1b2c3)이 소유·생성. 여기서는 재사용만
# (create_type=False → 재생성 안 함·downgrade에서 drop 안 함).
knowledge_type_enum = postgresql.ENUM(
    "CONCEPT",
    "PROCEDURE",
    "REPRESENT",
    "PROOF",
    "MODELING",
    "SPATIAL",
    "STOCHASTIC",
    name="knowledge_type",
    create_type=False,
)


def upgrade() -> None:
    # ── L2: 학습 증거 하이퍼테이블 (학습자 데이터) ─────────────────────────────
    #   B1: payload(원문 발화·미성년 데이터)는 평문 금지 → 봉투 암호화 + retention_until.
    op.create_table(
        "evidence_event",
        # attempt_event 선례: 이벤트 하이퍼테이블은 surrogate BigInteger + 시간 컬럼을 PK로.
        # (같은 session·같은 time 동시 이벤트 충돌 회피 + 파티션 키(time)를 PK에 포함하는 규칙).
        sa.Column("event_id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("objective_id", sa.Text(), nullable=False),  # 느슨참조(하이퍼테이블 FK 회피)
        sa.Column("k_type", knowledge_type_enum, nullable=False),
        sa.Column("pack_version", sa.Integer(), nullable=True),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("correct", sa.Boolean(), nullable=True),
        sa.Column("rt_ms", sa.Integer(), nullable=True),
        sa.Column("judge_score", sa.SmallInteger(), nullable=True),
        sa.Column("fidelity_score", sa.SmallInteger(), nullable=True),
        # B1: 비민감 메타(문항 ID 등)만 평문. 원문 발화는 암호화 컬럼으로.
        sa.Column("meta", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("payload_encrypted", sa.LargeBinary(), nullable=True),  # AES-256-GCM 본문
        sa.Column("payload_nonce", sa.LargeBinary(), nullable=True),  # 96-bit nonce
        sa.Column("retention_until", sa.DateTime(timezone=True), nullable=True),  # 파기 스케줄
        sa.PrimaryKeyConstraint("event_id", "time", name=op.f("pk_evidence_event")),
        sa.CheckConstraint(
            "judge_score IS NULL OR judge_score BETWEEN 0 AND 3",
            name=op.f("ck_evidence_event_judge"),
        ),
        sa.CheckConstraint(
            "fidelity_score IS NULL OR fidelity_score BETWEEN 0 AND 3",
            name=op.f("ck_evidence_event_fidelity"),
        ),
    )
    # 목표별 최근 증거 조회(objective_id, time DESC) — idx_session_user 선례(DESC 정렬 인덱스).
    op.create_index(
        "idx_ev_obj_time",
        "evidence_event",
        ["objective_id", sa.literal_column("time DESC")],
        unique=False,
    )
    # TimescaleDB 하이퍼테이블 변환 — timescaledb 확장이 설치된 환경에서만 적용(미설치 PG·CI는
    # 일반 테이블로 남아 검증 가능). time이 PK에 포함돼 hypertable UNIQUE 제약 만족.
    # if_not_exists 멱등.
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'timescaledb') THEN
                PERFORM create_hypertable('evidence_event', 'time',
                    chunk_time_interval => INTERVAL '7 days', if_not_exists => TRUE);
            END IF;
        END
        $$;
        """)


def downgrade() -> None:
    op.drop_index("idx_ev_obj_time", table_name="evidence_event")
    op.drop_table("evidence_event")  # 하이퍼테이블 chunk 자동 정리
    # knowledge_type enum은 앞 리비전(L3)이 소유하므로 여기서 drop하지 않는다(L3 다운시 정리).
