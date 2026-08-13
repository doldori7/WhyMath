"""MisconceptionRelation ORM(영속 레이어) 단위테스트 — DB 연결 *없이*(MISC-04).

`test_misconception_catalog_model.py` 패턴 답습: 메타데이터 등록 / PG DDL 컴파일(복합 PK·FK
CASCADE·인덱스) / from_schema·to_schema 변환 roundtrip / schema Literal이 닫힌 2종
(`caused_by`/`variant_of`) 밖 값을 거부함(오타 테스트). 실제 PG 적용·왕복(CASCADE delete 동작
포함)은 CI `backend — 마이그레이션·통합 (실 PG)` 잡이 확인한다 — 이 파일은 hermetic만 다룬다
(`test_misconception_seven_stage_manifest.py`의 "hermetic: 외부 의존·DB 불요" 설계 목표와 동형).

설계 정본: `docs/architecture/04e_misconception_remediation_design.md` §2-3.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable

from whymath_backend.db.base import Base
from whymath_backend.db.models.misconception_relation import (
    MisconceptionRelation as OrmMisconceptionRelation,
)
from whymath_backend.schema.misconception_relation import (
    MisconceptionRelation as SchemaMisconceptionRelation,
)


def _pg_ddl(table: object) -> str:
    """ORM 테이블을 PostgreSQL dialect로 컴파일한 CREATE TABLE 문자열로 반환."""
    return str(CreateTable(table).compile(dialect=postgresql.dialect()))  # type: ignore[arg-type]


def _valid_relation(**overrides: object) -> SchemaMisconceptionRelation:
    """유효한 schema.MisconceptionRelation(3필드 전부 필수)."""
    base: dict[str, object] = {
        "from_mis_id": "M0425",
        "relation_type": "caused_by",
        "to_mis_id": "M0431",
    }
    base.update(overrides)
    return SchemaMisconceptionRelation(**base)  # type: ignore[arg-type]


# ──────────────────────────────────────────────────────────────────────────
# 1) 메타데이터 등록
# ──────────────────────────────────────────────────────────────────────────
def test_relation_table_registered_in_metadata() -> None:
    """Base.metadata에 misconception_relation 테이블이 등록돼 있다(alembic 인식 전제)."""
    assert "misconception_relation" in Base.metadata.tables


def test_relation_orm_tablename() -> None:
    """ORM의 __tablename__이 마이그레이션 테이블명과 일치한다."""
    assert OrmMisconceptionRelation.__tablename__ == "misconception_relation"


# ──────────────────────────────────────────────────────────────────────────
# 2) 복합 PK — 서로게이트 PK 없음, (from_mis_id, relation_type, to_mis_id) 정확히 3컬럼
# ──────────────────────────────────────────────────────────────────────────
def test_relation_composite_pk_columns() -> None:
    """PK는 정확히 (from_mis_id, relation_type, to_mis_id) 3컬럼 — link_id류 서로게이트 없음."""
    pk_cols = [c.name for c in OrmMisconceptionRelation.__table__.primary_key.columns]
    assert pk_cols == ["from_mis_id", "relation_type", "to_mis_id"]


def test_relation_pk_ddl() -> None:
    """DDL의 PRIMARY KEY 절이 acceptance①의 정확한 순서·컬럼셋과 일치한다."""
    ddl = _pg_ddl(OrmMisconceptionRelation.__table__)
    assert "PRIMARY KEY (from_mis_id, relation_type, to_mis_id)" in ddl
    # 서로게이트 PK가 없으므로 gen_random_uuid() server_default가 어디에도 없다.
    assert "gen_random_uuid()" not in ddl


# ──────────────────────────────────────────────────────────────────────────
# 3) FK — 양쪽 모두 misconception_catalog.mis_id만, 개념 테이블 FK 0개, CASCADE
# ──────────────────────────────────────────────────────────────────────────
def test_relation_fk_count_and_targets() -> None:
    """FK는 정확히 2개, 양쪽 다 misconception_catalog.mis_id를 가리킨다(개념 FK 0)."""
    fks = OrmMisconceptionRelation.__table__.foreign_keys
    assert len(fks) == 2
    targets = {(fk.column.table.name, fk.column.name) for fk in fks}
    assert targets == {("misconception_catalog", "mis_id")}


def test_relation_fk_source_columns() -> None:
    """FK 출발 컬럼이 정확히 from_mis_id·to_mis_id다(다른 컬럼에 FK가 걸리지 않았다)."""
    fk_source_columns = {fk.parent.name for fk in OrmMisconceptionRelation.__table__.foreign_keys}
    assert fk_source_columns == {"from_mis_id", "to_mis_id"}


def test_relation_fk_no_concept_table() -> None:
    """개념 측 테이블(concept*)을 가리키는 FK가 전혀 없다(04e §2-3 Storage 레벨 불변식)."""
    referenced_tables = {
        fk.column.table.name for fk in OrmMisconceptionRelation.__table__.foreign_keys
    }
    assert all(not name.startswith("concept") for name in referenced_tables)


def test_relation_fk_cascade_ddl() -> None:
    """양쪽 FK 모두 ON DELETE CASCADE다 — M-id 삭제 시 관계도 함께 삭제(crosslink 선례 동형)."""
    ddl = _pg_ddl(OrmMisconceptionRelation.__table__)
    assert ddl.count("ON DELETE CASCADE") == 2
    assert "REFERENCES misconception_catalog (mis_id)" in ddl


# ──────────────────────────────────────────────────────────────────────────
# 4) 컬럼 폭 — misconception_catalog.mis_id(String(32))와 정합
# ──────────────────────────────────────────────────────────────────────────
def test_relation_mis_id_columns_string_32() -> None:
    """from_mis_id·to_mis_id는 String(32) — misconception_catalog.mis_id와 동일 폭."""
    from_col = OrmMisconceptionRelation.__table__.c.from_mis_id
    to_col = OrmMisconceptionRelation.__table__.c.to_mis_id
    assert from_col.type.length == 32  # type: ignore[attr-defined]
    assert to_col.type.length == 32  # type: ignore[attr-defined]
    assert from_col.nullable is False
    assert to_col.nullable is False


def test_relation_type_column_is_plain_string() -> None:
    """relation_type DB 컬럼은 닫힌 어휘 CHECK가 아니라 plain String(16)이다(schema Literal 몫)."""
    col = OrmMisconceptionRelation.__table__.c.relation_type
    assert col.type.length == 16  # type: ignore[attr-defined]
    assert col.nullable is False
    ddl = _pg_ddl(OrmMisconceptionRelation.__table__)
    assert "CHECK" not in ddl


# ──────────────────────────────────────────────────────────────────────────
# 5) 인덱스 — 역방향(to_mis_id) 조회 경로
# ──────────────────────────────────────────────────────────────────────────
def test_relation_reverse_index() -> None:
    """to_mis_id 역방향 조회 인덱스가 정의된다(PK 선두는 from_mis_id라 정방향은 이미 인덱싱됨)."""
    by_name = {
        ix.name: [c.name for c in ix.columns] for ix in OrmMisconceptionRelation.__table__.indexes
    }
    assert by_name["idx_misconception_relation_to"] == ["to_mis_id"]


# ──────────────────────────────────────────────────────────────────────────
# 6) schema Literal — 닫힌 2종(caused_by/variant_of) 밖 값 거부(오타 테스트)
# ──────────────────────────────────────────────────────────────────────────
class TestSchemaClosedVocabulary:
    def test_caused_by_accepted(self) -> None:
        rel = _valid_relation(relation_type="caused_by")
        assert rel.relation_type == "caused_by"

    def test_variant_of_accepted(self) -> None:
        rel = _valid_relation(relation_type="variant_of")
        assert rel.relation_type == "variant_of"

    def test_repaired_by_rejected(self) -> None:
        """`repaired_by`는 04e §2-2가 명시적으로 제외한 값 — intervene.py 결정트리와 중복."""
        with pytest.raises(ValidationError):
            _valid_relation(relation_type="repaired_by")

    def test_misconception_of_rejected(self) -> None:
        """`misconception_of`는 개념 방향 축(이미 concept_src_id로 해결) — 이 모델 범위 밖."""
        with pytest.raises(ValidationError):
            _valid_relation(relation_type="misconception_of")

    def test_typo_rejected(self) -> None:
        with pytest.raises(ValidationError):
            _valid_relation(relation_type="cause_by")

    def test_extra_field_forbidden(self) -> None:
        with pytest.raises(ValidationError):
            SchemaMisconceptionRelation(  # type: ignore[call-arg]
                from_mis_id="M0425",
                relation_type="caused_by",
                to_mis_id="M0431",
                bogus="x",
            )

    def test_mis_id_max_length_matches_db_width(self) -> None:
        """from_mis_id/to_mis_id max_length=32가 DB String(32)와 정합(33자는 거부)."""
        with pytest.raises(ValidationError):
            _valid_relation(from_mis_id="M" * 33)


# ──────────────────────────────────────────────────────────────────────────
# 7) 변환 roundtrip — 서로게이트 PK 없이 3필드가 그대로 왕복
# ──────────────────────────────────────────────────────────────────────────
def test_relation_roundtrip_preserves_fields() -> None:
    """schema → ORM → schema가 3필드(from_mis_id·relation_type·to_mis_id)를 보존한다."""
    s = _valid_relation(from_mis_id="M0425", relation_type="variant_of", to_mis_id="M0431")
    orm = OrmMisconceptionRelation.from_schema(s)
    assert orm.from_mis_id == "M0425"
    assert orm.relation_type == "variant_of"
    assert orm.to_mis_id == "M0431"

    back = orm.to_schema()
    assert back.from_mis_id == s.from_mis_id
    assert back.relation_type == s.relation_type
    assert back.to_mis_id == s.to_mis_id


def test_relation_to_schema_rejects_unknown_relation_type() -> None:
    """to_schema()가 DB에 (가상으로) 들어간 닫힌 어휘 밖 값을 재검증에서 거부한다.

    DB 컬럼 자체는 plain String이라 CHECK 없이도 값이 들어갈 수 있지만(예: 수기 INSERT·구
    데이터), `to_schema()`가 Pydantic Literal 재검증으로 이를 잡아낸다 — "닫힌 어휘는 schema
    재검증이 강제한다"는 모듈 설계를 실측으로 증명한다.
    """
    orm = OrmMisconceptionRelation(
        from_mis_id="M0425", relation_type="repaired_by", to_mis_id="M0431"
    )
    with pytest.raises(ValidationError):
        orm.to_schema()
