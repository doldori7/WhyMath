"""교수법 DSL(L3) ORM 단위테스트 — DB 연결 *없이* 검증(hermetic·PG 0).

검토서(`docs/reviews/260724_v2_migration_pedagogy_dsl_review.md`)·수정 목표 스키마
(`260724_v2_migration_pedagogy_dsl.alembic_draft.py`)의 정합 구현을 잠근다. dialogue/parental_consent
ORM 테스트 패턴 답습: 메타데이터 등록 / PG DDL 컴파일(enum·FK·CHECK·인덱스) / 기본값·제약.

검증 대상 지적: B2/H1(provenance FK 위임·license_tier 부재) · H2(concept_nodes atom_node·legacy FK
부재) · M1(status DRAFT fail-closed) · M4(knowledge_type native enum) · slot_type TEXT 유지.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateIndex, CreateTable

from whymath_backend.db.base import Base
from whymath_backend.db.models.pedagogy_dsl import (
    LearningObjective,
    PedagogyContentSlot,
    PedagogyPack,
    UnitSpec,
)
from whymath_backend.schema.enums import KnowledgeType


def _pg_ddl(table: object) -> str:
    """ORM 테이블을 PostgreSQL dialect로 컴파일한 CREATE TABLE 문자열로 반환."""
    return str(CreateTable(table).compile(dialect=postgresql.dialect()))  # type: ignore[arg-type]


def _index_ddl(index: object) -> str:
    return str(CreateIndex(index).compile(dialect=postgresql.dialect()))  # type: ignore[arg-type]


# ──────────────────────────────────────────────────────────────────────────
# 0) 지식 유형 enum (M4 native enum·7유형)
# ──────────────────────────────────────────────────────────────────────────
def test_knowledge_type_enum_values() -> None:
    """KnowledgeType은 7유형 폐쇄 택소노미다(값·순서 고정)."""
    assert [m.value for m in KnowledgeType] == [
        "CONCEPT",
        "PROCEDURE",
        "REPRESENT",
        "PROOF",
        "MODELING",
        "SPATIAL",
        "STOCHASTIC",
    ]


# ──────────────────────────────────────────────────────────────────────────
# 1) 메타데이터 등록 + 테이블명 (content_material 아님·pedagogy_content_slot)
# ──────────────────────────────────────────────────────────────────────────
def test_pedagogy_dsl_tables_registered_in_metadata() -> None:
    """Base.metadata에 L3 4테이블이 등록돼 있다(alembic autogenerate 인식 전제)."""
    tables = set(Base.metadata.tables.keys())
    assert {"unit_spec", "pedagogy_pack", "learning_objective", "pedagogy_content_slot"} <= tables


def test_tablenames_slot_not_content_material() -> None:
    """슬롯 테이블은 pedagogy_content_slot(concept_content 중복 방지 — content_material 아님)."""
    assert UnitSpec.__tablename__ == "unit_spec"
    assert PedagogyPack.__tablename__ == "pedagogy_pack"
    assert LearningObjective.__tablename__ == "learning_objective"
    assert PedagogyContentSlot.__tablename__ == "pedagogy_content_slot"
    assert "content_material" not in Base.metadata.tables


def test_models_import_cleanly() -> None:
    """4개 모델 클래스가 __table__을 갖는다(import·매핑 정상)."""
    for cls in (UnitSpec, PedagogyPack, LearningObjective, PedagogyContentSlot):
        assert hasattr(cls, "__table__")


# ──────────────────────────────────────────────────────────────────────────
# 2) unit_spec — 복합 PK·M1 status DRAFT·H2 concept_nodes FK 없음
# ──────────────────────────────────────────────────────────────────────────
def test_unit_spec_composite_pk() -> None:
    """PK는 (unit_id, unit_version) 복합 PK다(버전 보존)."""
    pk = [c.name for c in UnitSpec.__table__.primary_key.columns]
    assert pk == ["unit_id", "unit_version"]


def test_unit_spec_status_default_draft_m1() -> None:
    """M1: status는 NOT NULL·기본 'DRAFT'(fail-closed)·CHECK 4상태."""
    col = UnitSpec.__table__.c.status
    assert col.nullable is False
    assert col.server_default is not None
    ddl = _pg_ddl(UnitSpec.__table__)
    assert "status TEXT DEFAULT 'DRAFT' NOT NULL" in ddl
    assert "status IN ('DRAFT','ACTIVE','SUPERSEDED','BLOCKED')" in ddl


def test_unit_spec_concept_nodes_array_no_fk_h2() -> None:
    """H2: concept_nodes는 TEXT[](atom_node code)이며 어떤 FK도 없다(legacy 437/545 못박지 않음)."""
    ddl = _pg_ddl(UnitSpec.__table__)
    assert "concept_nodes TEXT[] NOT NULL" in ddl
    # unit_spec 자체에 FK 없음(concept_nodes는 느슨참조).
    assert len(UnitSpec.__table__.foreign_keys) == 0
    assert "REFERENCES" not in ddl


# ──────────────────────────────────────────────────────────────────────────
# 3) pedagogy_pack — PK k_type native enum(M4)·기본값
# ──────────────────────────────────────────────────────────────────────────
def test_pedagogy_pack_pk_ktype_native_enum_m4() -> None:
    """M4: PK는 k_type이고 native enum 타입명은 'knowledge_type'(7유형)."""
    pk = [c.name for c in PedagogyPack.__table__.primary_key.columns]
    assert pk == ["k_type"]
    ktype = PedagogyPack.__table__.c.k_type.type
    assert ktype.name == "knowledge_type"  # type: ignore[attr-defined]
    assert "STOCHASTIC" in ktype.enums  # type: ignore[attr-defined]
    assert len(ktype.enums) == 7  # type: ignore[attr-defined]


def test_pedagogy_pack_defaults() -> None:
    """is_stub 기본 false·forbidden_modes 기본 빈 배열·required_slots/default_evidence NOT NULL."""
    ddl = _pg_ddl(PedagogyPack.__table__)
    assert "is_stub BOOLEAN DEFAULT false NOT NULL" in ddl
    assert "forbidden_modes TEXT[] DEFAULT '{}'::text[] NOT NULL" in ddl
    assert "required_slots JSONB NOT NULL" in ddl
    assert "default_evidence JSONB NOT NULL" in ddl


# ──────────────────────────────────────────────────────────────────────────
# 4) learning_objective — 복합 FK unit_spec·secondary CHECK·H2 concept_nodes
# ──────────────────────────────────────────────────────────────────────────
def test_learning_objective_composite_fk_unit_spec_cascade() -> None:
    """복합 FK (unit_id, unit_version)→unit_spec·ON DELETE CASCADE."""
    ddl = _pg_ddl(LearningObjective.__table__)
    assert "FOREIGN KEY(unit_id, unit_version) REFERENCES unit_spec (unit_id, unit_version)" in ddl
    assert "ON DELETE CASCADE" in ddl


def test_learning_objective_secondary_distinct_check() -> None:
    """부 유형은 주 유형과 달라야 한다(CHECK)."""
    ddl = _pg_ddl(LearningObjective.__table__)
    assert "k_type_secondary IS NULL OR k_type_secondary <> k_type" in ddl


def test_learning_objective_concept_nodes_no_legacy_fk_h2() -> None:
    """H2: concept_nodes는 TEXT[](atom_node code). FK는 unit_spec 하나뿐(개념/원자 그래프 FK 없음)."""
    ddl = _pg_ddl(LearningObjective.__table__)
    assert "concept_nodes TEXT[] NOT NULL" in ddl
    # FK 타깃은 unit_spec 뿐 — concept/atom/legacy 그래프로의 FK 없음.
    fk_targets = {fk.column.table.name for fk in LearningObjective.__table__.foreign_keys}
    assert fk_targets == {"unit_spec"}
    assert "REFERENCES concept" not in ddl
    assert "REFERENCES atom_node" not in ddl


def test_learning_objective_idx_lo_unit() -> None:
    """소단원별 목표 조회 인덱스 idx_lo_unit(unit_id, unit_version)."""
    names = {ix.name for ix in LearningObjective.__table__.indexes}
    assert "idx_lo_unit" in names


# ──────────────────────────────────────────────────────────────────────────
# 5) pedagogy_content_slot — B2/H1 provenance FK 위임·M1 status·slot_type TEXT
# ──────────────────────────────────────────────────────────────────────────
def test_content_slot_provenance_fk_delegation_b2_h1() -> None:
    """B2/H1: provenance_id FK → content_provenance(생성/라이선스 위임). objective FK CASCADE."""
    ddl = _pg_ddl(PedagogyContentSlot.__table__)
    assert (
        "FOREIGN KEY(provenance_id) REFERENCES content_provenance (provenance_id)" in ddl
    )
    assert "FOREIGN KEY(objective_id) REFERENCES learning_objective (id)" in ddl
    fk_targets = {fk.column.table.name for fk in PedagogyContentSlot.__table__.foreign_keys}
    assert fk_targets == {"content_provenance", "learning_objective"}


def test_content_slot_no_provenance_columns_b2_h1() -> None:
    """B2/H1: license_tier·generated_by·prompt_version·source_refs 컬럼을 소유하지 않는다."""
    cols = set(PedagogyContentSlot.__table__.c.keys())
    for forbidden in ("license_tier", "generated_by", "prompt_version", "source_refs"):
        assert forbidden not in cols


def test_content_slot_slot_type_is_text_not_enum() -> None:
    """slot_type은 팩이 정의하므로 enum 아닌 TEXT다."""
    col = PedagogyContentSlot.__table__.c.slot_type
    assert isinstance(col.type, sa.Text)
    ddl = _pg_ddl(PedagogyContentSlot.__table__)
    assert "slot_type TEXT NOT NULL" in ddl


def test_content_slot_status_default_draft_and_checks_m1() -> None:
    """M1: status NOT NULL·기본 'DRAFT'·CHECK 4상태·prescreen 0~3 CHECK."""
    col = PedagogyContentSlot.__table__.c.status
    assert col.nullable is False
    assert col.server_default is not None
    ddl = _pg_ddl(PedagogyContentSlot.__table__)
    assert "status TEXT DEFAULT 'DRAFT' NOT NULL" in ddl
    assert "status IN ('DRAFT','PRESCREENED','APPROVED','REJECTED')" in ddl
    assert "prescreen_score IS NULL OR prescreen_score BETWEEN 0 AND 3" in ddl


def test_content_slot_indexes() -> None:
    """idx_cm_obj_status(objective_id, status)·idx_cm_queue(부분 인덱스·검수 대기)."""
    names = {ix.name for ix in PedagogyContentSlot.__table__.indexes}
    assert {"idx_cm_obj_status", "idx_cm_queue"} <= names
    queue_ix = next(ix for ix in PedagogyContentSlot.__table__.indexes if ix.name == "idx_cm_queue")
    ddl = _index_ddl(queue_ix)
    assert "WHERE status IN ('DRAFT','PRESCREENED')" in ddl
