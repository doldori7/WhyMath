"""[리뷰어 초안 · 미적용] 교수법 팩 + 소단원 DSL 스키마 (7유형→팩→증거)

╔══════════════════════════════════════════════════════════════════════════╗
║  이 파일은 검토서 산출물이다 — alembic/versions/ 밖에 있어 자동 적용되지 않는다.  ║
║  검토서: docs/reviews/260724_v2_migration_pedagogy_dsl_review.md            ║
║                                                                            ║
║  ▸ 적용 금지(PED-01 승인 전). 원본 원시 SQL의 Blocking/High 지적을 반영한       ║
║    "정합 버전" 참고 초안이다. 승인되면:                                        ║
║      1) `cd src/backend && alembic revision -m "pedagogy pack dsl"`로        ║
║         빈 리비전을 만들고 이 upgrade/downgrade 본문을 옮긴다(revision 해시는    ║
║         alembic가 새로 발급 — 아래 하드코딩 값 사용 금지).                       ║
║      2) L2(evidence_event)와 L3(content/pack)를 **별도 리비전 2건**으로 분리.  ║
║      3) 로컬 pg(5433)에서 `alembic upgrade head` → `alembic downgrade -1`     ║
║         드라이런. prod 미적용.                                                ║
║                                                                            ║
║  down_revision 대상(현재 head): c4d5e6f0a1b2 (strategy_node_projection)      ║
╚══════════════════════════════════════════════════════════════════════════╝

원본 대비 반영한 검토 지적(review §2):
  B1  evidence_event.payload 평문 → payload_encrypted/payload_nonce + retention_until
      (dialogue_turn 봉투 암호화 선례 · CLAUDE.md '미성년 채팅 평문 저장 금지')
  B2  license_tier TEXT 폐기 → provenance는 content_provenance(FK) 위임(LicenseType enum)
  H1  content_material → pedagogy_content_slot: provenance 컬럼 제거, provenance_id FK
  H2  concept_nodes 주석을 atom_node(런타임 진실 2,697) 기준으로 — ARCH-13 결론 대기
  H3  원시 SQL → Alembic op API. L2/L3 분리 주석(실적용 시 리비전 2건)
  M1  unit_spec.status 기본 'DRAFT'(fail-closed) — 게이트 통과 시에만 ACTIVE
  M2  v_manifest_fill 나눗셈에 nullif(required_cnt,0)
  M4  knowledge_type ENUM은 '커널 소유·과목 불변' 예외로 채택 — MEMORY 결정 필요
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers — 초안 placeholder. 실적용 시 alembic이 새 해시를 발급한다.
revision: str = "PED01_DRAFT_DO_NOT_APPLY"
down_revision: str | None = "c4d5e6f0a1b2"  # 현재 head(strategy_node_projection)
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# 지식 유형(커널 소유·과목 불변) — 교수법 팩과 1:1. create_type=False로 명시 생성/삭제 제어.
# M4: house style은 plain Text지만 이 축은 안정·커널 소유라 ENUM 예외(MEMORY 결정 전제).
knowledge_type_enum = postgresql.ENUM(
    "CONCEPT",     # 개념·정의형
    "PROCEDURE",   # 절차·알고리즘형
    "REPRESENT",   # 표상연결형
    "PROOF",       # 증명·논증형
    "MODELING",    # 문제해결·모델링형
    "SPATIAL",     # 공간·시각형
    "STOCHASTIC",  # 데이터·불확실성형
    name="knowledge_type",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    knowledge_type_enum.create(bind, checkfirst=True)

    # ── L3: 소단원 DSL 컴파일 이력 (YAML=소스, DB=산출물, 단방향) ──────────────
    op.create_table(
        "unit_spec",
        sa.Column("unit_id", sa.Text(), nullable=False),
        sa.Column("unit_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("api_version", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("curriculum_rev", sa.Text(), nullable=False),
        sa.Column("standard_codes", postgresql.ARRAY(sa.Text()), nullable=False),
        # H2: 원자 백본(atom_node·런타임 진실) 노드 code 배열. legacy 437/545 아님.
        #     존재 검증은 컴파일러(데이터 파이프라인) 책임 — FK/CHECK 없음(house style).
        #     ARCH-13(개념↔원자 입도 통합) 결론 시 참조 축 확정.
        sa.Column("concept_nodes", postgresql.ARRAY(sa.Text()), nullable=False),
        sa.Column("yaml_sha256", sa.Text(), nullable=False),
        sa.Column("compiler_ver", sa.Text(), nullable=False),
        sa.Column(
            "compiled_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        # M1: fail-closed 기본 'DRAFT'. v_unit_release_gate 통과 시에만 컴파일러가 'ACTIVE'로.
        sa.Column("status", sa.Text(), nullable=False, server_default="DRAFT"),
        sa.PrimaryKeyConstraint("unit_id", "unit_version", name=op.f("pk_unit_spec")),
        sa.CheckConstraint(
            "status IN ('DRAFT','ACTIVE','SUPERSEDED','BLOCKED')",
            name=op.f("ck_unit_spec_status"),
        ),
    )

    # ── L3: 교수법 팩 (팩=데이터. 시더가 subject-math packs YAML에서 적재) ────────
    op.create_table(
        "pedagogy_pack",
        sa.Column("k_type", knowledge_type_enum, nullable=False),
        sa.Column("pack_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("api_version", sa.Text(), nullable=False),
        sa.Column("is_stub", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("socratic_prompt", sa.Text(), nullable=False),  # 과목 명사 금지(lint)
        sa.Column("fading_schedule", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "forbidden_modes",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::text[]"),
        ),
        sa.Column("required_slots", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("default_evidence", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.PrimaryKeyConstraint("k_type", name=op.f("pk_pedagogy_pack")),
    )

    # ── L3: 학습목표 (소단원→목표→유형→팩 사슬의 가운데 고리) ──────────────────
    op.create_table(
        "learning_objective",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("unit_id", sa.Text(), nullable=False),
        sa.Column("unit_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("statement", sa.Text(), nullable=False),
        # L2(검토): 성취기준(NCIC 공공누리) 유래 자체 분해임을 전제 — 교과서 학습목표
        #           본문이면 저작권 게이트 대상(learning_objective_text 선례).
        sa.Column("achievement_std", sa.Text(), nullable=False),
        sa.Column("source_verb", sa.Text(), nullable=True),
        sa.Column("k_type", knowledge_type_enum, nullable=False),  # 주 유형 → 팩 바인딩
        sa.Column("k_type_secondary", knowledge_type_enum, nullable=True),  # 부 유형(기록만)
        sa.Column(
            "k_type_verified", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column("concept_nodes", postgresql.ARRAY(sa.Text()), nullable=False),  # atom_node code
        sa.Column("misconception_ids", postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column("slot_manifest", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("exit_evidence", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("phase_overrides", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_learning_objective")),
        sa.ForeignKeyConstraint(
            ["unit_id", "unit_version"],
            ["unit_spec.unit_id", "unit_spec.unit_version"],
            ondelete="CASCADE",
            name=op.f("fk_learning_objective_unit_spec"),
        ),
        sa.CheckConstraint(
            "k_type_secondary IS NULL OR k_type_secondary <> k_type",
            name=op.f("ck_learning_objective_secondary_distinct"),
        ),
    )
    op.create_index("idx_lo_unit", "learning_objective", ["unit_id", "unit_version"])

    # ── L3: 콘텐츠 슬롯 (H1: provenance는 소유 않고 content_provenance FK 위임) ────
    #   B2/H1: generated_by·prompt_version·source_refs·license_tier 제거.
    #   생성 이력·라이선스·저작권 불변식은 기존 content_provenance/generation_log가 소유.
    op.create_table(
        "pedagogy_content_slot",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("objective_id", sa.Text(), nullable=False),
        sa.Column("slot_type", sa.Text(), nullable=False),  # 팩이 정의(diag_item 등) — TEXT 유지
        # 본문: 렌더러-중립 LaTeX + 구조 태그(CLAUDE.md L55 — 완전 AST 아님·화면 문자열 금지).
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("tts_safe", sa.Boolean(), nullable=True),
        sa.Column("sympy_verified", sa.Boolean(), nullable=True),
        # provenance 위임 — 생성/라이선스 이력은 여기 FK로만. (nullable=사람 직접 저작 시 NULL)
        sa.Column("provenance_id", sa.Uuid(), nullable=True),
        # 상태 흐름: DRAFT → PRESCREENED → APPROVED | REJECTED
        sa.Column("status", sa.Text(), nullable=False, server_default="DRAFT"),
        sa.Column("prescreen_score", sa.SmallInteger(), nullable=True),
        sa.Column("reviewed_by", sa.Text(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reject_reason", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_pedagogy_content_slot")),
        sa.ForeignKeyConstraint(
            ["objective_id"],
            ["learning_objective.id"],
            ondelete="CASCADE",
            name=op.f("fk_pedagogy_content_slot_objective"),
        ),
        sa.ForeignKeyConstraint(
            ["provenance_id"],
            ["content_provenance.provenance_id"],
            name=op.f("fk_pedagogy_content_slot_provenance"),
        ),
        sa.CheckConstraint(
            "status IN ('DRAFT','PRESCREENED','APPROVED','REJECTED')",
            name=op.f("ck_pedagogy_content_slot_status"),
        ),
        sa.CheckConstraint(
            "prescreen_score IS NULL OR prescreen_score BETWEEN 0 AND 3",
            name=op.f("ck_pedagogy_content_slot_prescreen"),
        ),
    )
    op.create_index(
        "idx_cm_obj_status", "pedagogy_content_slot", ["objective_id", "status"]
    )
    op.create_index(
        "idx_cm_queue",
        "pedagogy_content_slot",
        ["status"],
        postgresql_where=sa.text("status IN ('DRAFT','PRESCREENED')"),
    )

    # ── L2: 학습 증거 하이퍼테이블 (학습자 데이터 · 별도 리비전 권고) ──────────────
    #   H3: 실적용 시 이 블록은 별도 L2 리비전으로 분리(계층 경계).
    #   B1: payload(원문 발화·미성년 데이터)는 평문 금지 → 봉투 암호화 + retention_until.
    #   대안(중복 회피): 기존 attempt_event 하이퍼테이블 확장 재사용 — 택1은 PED-01/설계 결정.
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
        sa.Column("payload_nonce", sa.LargeBinary(), nullable=True),      # 96-bit nonce
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
    # DESC 정렬 인덱스는 raw로 생성(op.create_index 표현식 이식성 회피). 이름으로 drop 가능.
    op.execute(
        "CREATE INDEX idx_ev_obj_time ON evidence_event (objective_id, time DESC)"
    )
    # 하이퍼테이블 변환 — timescaledb 설치 환경에서만(미설치 PG/CI는 일반 테이블). 멱등.
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'timescaledb') THEN
                PERFORM create_hypertable('evidence_event', 'time',
                    chunk_time_interval => INTERVAL '7 days', if_not_exists => TRUE);
            END IF;
        END
        $$;
        """
    )

    # ── 운영 뷰 4종 ──────────────────────────────────────────────────────────
    op.execute(
        """
        CREATE VIEW v_unit_pedagogy_profile AS
        SELECT unit_id, unit_version, k_type, count(*) AS objective_cnt
        FROM   learning_objective
        GROUP  BY unit_id, unit_version, k_type;
        """
    )
    # M2: nullif(required_cnt,0)로 division-by-zero 방어. 슬롯 테이블명 반영.
    op.execute(
        """
        CREATE VIEW v_manifest_fill AS
        SELECT lo.id AS objective_id, lo.unit_id, lo.k_type,
               need.slot_type, need.required_cnt,
               count(cm.id) FILTER (WHERE cm.status = 'APPROVED') AS approved_cnt,
               round(count(cm.id) FILTER (WHERE cm.status = 'APPROVED')::numeric
                     / nullif(need.required_cnt, 0) * 100, 1)       AS fill_pct
        FROM   learning_objective lo
        CROSS  JOIN LATERAL (
                 SELECT s ->> 'type'         AS slot_type,
                        (s ->> 'count')::int AS required_cnt
                 FROM   jsonb_array_elements(lo.slot_manifest) s
               ) need
        LEFT   JOIN pedagogy_content_slot cm
               ON cm.objective_id = lo.id AND cm.slot_type = need.slot_type
        GROUP  BY lo.id, lo.unit_id, lo.k_type, need.slot_type, need.required_cnt;
        """
    )
    op.execute(
        """
        CREATE VIEW v_unit_release_gate AS
        SELECT unit_id,
               min(fill_pct)             AS worst_fill_pct,
               bool_and(fill_pct >= 100) AS releasable
        FROM   v_manifest_fill
        GROUP  BY unit_id;
        """
    )
    op.execute(
        """
        CREATE VIEW v_prescreen_calibration AS
        SELECT date_trunc('week', reviewed_at)::date AS review_week,
               count(*) FILTER (WHERE prescreen_score >= 2)                         AS prescreen_passed,
               count(*) FILTER (WHERE prescreen_score >= 2 AND status = 'REJECTED') AS false_accept,
               round(count(*) FILTER (WHERE prescreen_score >= 2 AND status = 'REJECTED')::numeric
                     / nullif(count(*) FILTER (WHERE prescreen_score >= 2), 0) * 100, 1)
                                                                                    AS false_accept_pct
        FROM   pedagogy_content_slot
        WHERE  reviewed_at IS NOT NULL
        GROUP  BY 1
        ORDER  BY 1;
        """
    )


def downgrade() -> None:
    for _view in (
        "v_prescreen_calibration",
        "v_unit_release_gate",
        "v_manifest_fill",
        "v_unit_pedagogy_profile",
    ):
        op.execute(f"DROP VIEW IF EXISTS {_view}")

    op.drop_index("idx_ev_obj_time", table_name="evidence_event")
    op.drop_table("evidence_event")  # 하이퍼테이블 chunk 자동 정리

    op.drop_index("idx_cm_queue", table_name="pedagogy_content_slot")
    op.drop_index("idx_cm_obj_status", table_name="pedagogy_content_slot")
    op.drop_table("pedagogy_content_slot")

    op.drop_index("idx_lo_unit", table_name="learning_objective")
    op.drop_table("learning_objective")
    op.drop_table("pedagogy_pack")
    op.drop_table("unit_spec")

    knowledge_type_enum.drop(op.get_bind(), checkfirst=True)
