"""pedagogy pack dsl (L3) — 교수법 팩 + 소단원 DSL (7유형→팩→증거)

교수법 DSL 검토서(`docs/reviews/260724_v2_migration_pedagogy_dsl_review.md`)의 수정 목표 스키마
(`260724_v2_migration_pedagogy_dsl.alembic_draft.py`)를 정합 구현한다. 원본 원시 SQL의
Blocking/High 지적을 반영한 버전이다(원본 복제 아님).

이 리비전(L3)은 콘텐츠/팩 계층을 만든다:
  - `knowledge_type` PG native ENUM(7유형·M4 예외·이 리비전이 소유)
  - `pedagogy_pack`·`unit_spec`·`learning_objective`·`pedagogy_content_slot`
  - 운영 뷰 4종(v_unit_pedagogy_profile·v_manifest_fill·v_unit_release_gate·v_prescreen_calibration)

L2 학습자 데이터(`evidence_event`)는 계층 경계가 달라 **별 리비전**(다음 head)으로 분리한다
(검토서 H3 — 역방향 의존 금지).

반영 지적:
  B2/H1  pedagogy_content_slot은 provenance/라이선스를 소유하지 않고 content_provenance FK 위임.
  H2     concept_nodes는 원자 백본(atom_node·런타임 진실) code 배열·FK 없음(ARCH-13 대기).
  M1     unit_spec.status·pedagogy_content_slot.status 기본 'DRAFT'(fail-closed).
  M2     v_manifest_fill 나눗셈에 nullif(required_cnt,0).
  M4     knowledge_type는 native ENUM(커널 소유·과목 불변·plain Text house style의 의도적 예외).

Revision ID: d5e6f0a1b2c3
Revises: c4d5e6f0a1b2
Create Date: 2026-07-24 12:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d5e6f0a1b2c3"
down_revision: str | None = "c4d5e6f0a1b2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# 지식 유형(커널 소유·과목 불변) — 교수법 팩과 1:1. 이 리비전이 *소유*(생성·downgrade drop).
# M4: house style은 plain Text지만 이 축은 안정·커널 소유라 ENUM 예외. create_type=False로
# 명시 생성/삭제를 제어한다(behavior_area_enum·skill_node 선례 동형). 값은 schema/enums.py
# KnowledgeType과 *정확히 일치*해야 한다.
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
    bind = op.get_bind()
    # 7유형 native enum — 이 리비전이 소유(명시 생성·checkfirst 멱등).
    knowledge_type_enum.create(bind, checkfirst=True)

    # ── L3: 소단원 DSL 컴파일 이력 (YAML=소스, DB=산출물·단방향) ──────────────
    op.create_table(
        "unit_spec",
        sa.Column("unit_id", sa.Text(), nullable=False),
        sa.Column("unit_version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("api_version", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("curriculum_rev", sa.Text(), nullable=False),
        sa.Column("standard_codes", postgresql.ARRAY(sa.Text()), nullable=False),
        # H2: 원자 백본(atom_node·런타임 진실) 노드 code 배열. legacy 437/545 아님·FK/CHECK 없음.
        sa.Column("concept_nodes", postgresql.ARRAY(sa.Text()), nullable=False),
        sa.Column("yaml_sha256", sa.Text(), nullable=False),
        sa.Column("compiler_ver", sa.Text(), nullable=False),
        sa.Column(
            "compiled_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        # M1: fail-closed 기본 'DRAFT'. v_unit_release_gate 통과 시에만 컴파일러가 'ACTIVE'로.
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'DRAFT'")),
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
        sa.Column("pack_version", sa.Integer(), nullable=False, server_default=sa.text("1")),
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
        sa.Column("unit_version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("statement", sa.Text(), nullable=False),
        # 검토서 L2: 성취기준(NCIC 공공누리) 유래 자체 분해 전제 — 교과서 학습목표 본문이면
        #           저작권 게이트 대상(learning_objective_text 선례).
        sa.Column("achievement_std", sa.Text(), nullable=False),
        sa.Column("source_verb", sa.Text(), nullable=True),
        sa.Column("k_type", knowledge_type_enum, nullable=False),  # 주 유형 → 팩 바인딩
        sa.Column("k_type_secondary", knowledge_type_enum, nullable=True),  # 부 유형(기록만)
        sa.Column("k_type_verified", sa.Boolean(), nullable=False, server_default=sa.false()),
        # H2: atom_node code 배열(런타임 진실). FK 없음.
        sa.Column("concept_nodes", postgresql.ARRAY(sa.Text()), nullable=False),
        sa.Column("misconception_ids", postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column("slot_manifest", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("exit_evidence", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("phase_overrides", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_learning_objective")),
        sa.ForeignKeyConstraint(
            ["unit_id", "unit_version"],
            ["unit_spec.unit_id", "unit_spec.unit_version"],
            ondelete="CASCADE",
            name=op.f("fk_learning_objective_unit_id_unit_spec"),
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
        # 상태 흐름: DRAFT → PRESCREENED → APPROVED | REJECTED (M1: 기본 DRAFT)
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'DRAFT'")),
        sa.Column("prescreen_score", sa.SmallInteger(), nullable=True),
        sa.Column("reviewed_by", sa.Text(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reject_reason", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_pedagogy_content_slot")),
        sa.ForeignKeyConstraint(
            ["objective_id"],
            ["learning_objective.id"],
            ondelete="CASCADE",
            name=op.f("fk_pedagogy_content_slot_objective_id_learning_objective"),
        ),
        sa.ForeignKeyConstraint(
            ["provenance_id"],
            ["content_provenance.provenance_id"],
            name=op.f("fk_pedagogy_content_slot_provenance_id_content_provenance"),
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
    op.create_index("idx_cm_obj_status", "pedagogy_content_slot", ["objective_id", "status"])
    op.create_index(
        "idx_cm_queue",
        "pedagogy_content_slot",
        ["status"],
        postgresql_where=sa.text("status IN ('DRAFT','PRESCREENED')"),
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
    # M2: nullif(required_cnt,0)로 division-by-zero 방어.
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

    op.drop_index("idx_cm_queue", table_name="pedagogy_content_slot")
    op.drop_index("idx_cm_obj_status", table_name="pedagogy_content_slot")
    op.drop_table("pedagogy_content_slot")

    op.drop_index("idx_lo_unit", table_name="learning_objective")
    op.drop_table("learning_objective")
    op.drop_table("pedagogy_pack")
    op.drop_table("unit_spec")

    # 이 리비전이 만든 native enum 정리(checkfirst로 멱등). evidence_event(L2·다음 리비전)도
    # knowledge_type을 쓰나, 그 리비전이 먼저 downgrade되므로 여기서 안전하게 drop한다.
    postgresql.ENUM(name="knowledge_type").drop(op.get_bind(), checkfirst=True)
