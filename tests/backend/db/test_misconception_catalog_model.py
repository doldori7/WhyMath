"""MisconceptionCatalog ORM(영속 레이어) 단위테스트 — DB 연결 *없이*.

`test_achievement_standard_orm.py` 패턴 답습: 메타데이터 등록 / PG DDL 컴파일(PK·인덱스·NUMERIC·
FK 부재) / from_schema·to_schema 변환 roundtrip / 제약 의도(mis_id PK·UNIQUE는 PK뿐·기존 kebab
체계와 별개라 FK 0). 실제 PG 적용·왕복은 CI `backend — 마이그레이션·통합 (실 PG)` 잡(alembic
upgrade head ↔ downgrade base)이 확인한다.

설계 정본: whymath_backend/schema/misconception_catalog.py + db/models/misconception_catalog.py.
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable

from whymath_backend.db.base import Base
from whymath_backend.db.models.misconception_catalog import (
    MisconceptionCatalog as OrmMisconceptionCatalog,
)
from whymath_backend.schema.misconception_catalog import (
    MisconceptionCatalog as SchemaMisconceptionCatalog,
)


def _pg_ddl(table: object) -> str:
    """ORM 테이블을 PostgreSQL dialect로 컴파일한 CREATE TABLE 문자열로 반환."""
    return str(CreateTable(table).compile(dialect=postgresql.dialect()))  # type: ignore[arg-type]


def _valid_catalog(**overrides: object) -> SchemaMisconceptionCatalog:
    """유효한 schema.MisconceptionCatalog(mis_id만 필수 — 나머지 선택)."""
    base: dict[str, object] = {"mis_id": "M0425"}
    base.update(overrides)
    return SchemaMisconceptionCatalog(**base)  # type: ignore[arg-type]


# ──────────────────────────────────────────────────────────────────────────
# 1) 메타데이터 등록
# ──────────────────────────────────────────────────────────────────────────
def test_catalog_table_registered_in_metadata() -> None:
    """Base.metadata에 misconception_catalog 테이블이 등록돼 있다(alembic 인식 전제)."""
    assert "misconception_catalog" in Base.metadata.tables


def test_catalog_orm_tablename() -> None:
    """ORM의 __tablename__이 마이그레이션 테이블명과 일치한다."""
    assert OrmMisconceptionCatalog.__tablename__ == "misconception_catalog"


# ──────────────────────────────────────────────────────────────────────────
# 2) PG DDL — PK·NUMERIC·인덱스·FK 부재(별개 체계)
# ──────────────────────────────────────────────────────────────────────────
def test_catalog_pk_is_mis_id() -> None:
    """PK는 mis_id 단일이고 의미 문자열이라 gen_random_uuid() server_default가 없다."""
    ddl = _pg_ddl(OrmMisconceptionCatalog.__table__)
    assert "PRIMARY KEY (mis_id)" in ddl
    assert "gen_random_uuid()" not in ddl
    pk_cols = [c.name for c in OrmMisconceptionCatalog.__table__.primary_key.columns]
    assert pk_cols == ["mis_id"]


def test_catalog_mis_id_string_length() -> None:
    """mis_id는 String(16) NOT NULL(PK)다."""
    col = OrmMisconceptionCatalog.__table__.c.mis_id
    assert col.type.length == 16  # type: ignore[attr-defined]
    assert col.nullable is False
    assert col.primary_key is True


def test_catalog_mapping_score_is_numeric() -> None:
    """mapping_score는 NUMERIC(5, 3)이다(float 0.454~1.236 담음)."""
    ddl = _pg_ddl(OrmMisconceptionCatalog.__table__)
    assert "NUMERIC(5, 3)" in ddl
    col_type = OrmMisconceptionCatalog.__table__.c.mapping_score.type
    assert isinstance(col_type, postgresql.NUMERIC) or col_type.__class__.__name__ == "Numeric"


def test_catalog_no_foreign_keys() -> None:
    """기존 kebab-id 오개념 체계와 별개라 FK가 전혀 없다(코드들은 느슨참조)."""
    ddl = _pg_ddl(OrmMisconceptionCatalog.__table__)
    assert len(OrmMisconceptionCatalog.__table__.foreign_keys) == 0
    assert "REFERENCES" not in ddl


def test_catalog_unique_is_pk_only() -> None:
    """UNIQUE는 mis_id PK뿐이다(별도 UniqueConstraint 없음)."""
    ddl = _pg_ddl(OrmMisconceptionCatalog.__table__)
    # PK 외 UNIQUE 절이 없어야 한다.
    assert "UNIQUE" not in ddl


def test_catalog_indexes() -> None:
    """concept_src_id · standard_code · error_type 인덱스가 정의된다."""
    by_name = {
        ix.name: [c.name for c in ix.columns] for ix in OrmMisconceptionCatalog.__table__.indexes
    }
    assert by_name["idx_misconception_catalog_concept"] == ["concept_src_id"]
    assert by_name["idx_misconception_catalog_standard"] == ["standard_code"]
    assert by_name["idx_misconception_catalog_error_type"] == ["error_type"]


def test_catalog_loose_ref_columns_lengths() -> None:
    """concept_src_id(64)·standard_code(32)는 느슨참조 String 컬럼이고 FK가 아니다."""
    concept_col = OrmMisconceptionCatalog.__table__.c.concept_src_id
    standard_col = OrmMisconceptionCatalog.__table__.c.standard_code
    assert concept_col.type.length == 64  # type: ignore[attr-defined]
    assert standard_col.type.length == 32  # type: ignore[attr-defined]
    assert len(concept_col.foreign_keys) == 0
    assert len(standard_col.foreign_keys) == 0


# ──────────────────────────────────────────────────────────────────────────
# 3) 변환 roundtrip
# ──────────────────────────────────────────────────────────────────────────
def test_catalog_roundtrip_preserves_fields() -> None:
    """schema → ORM → schema가 16필드(본문·코드·매핑)를 보존한다."""
    s = _valid_catalog(
        canonical_statement="분수의 분모끼리 더한다.",
        student_wrong_thinking="1/2 + 1/3 = 2/5 라고 생각함",
        distractor_rule="분자·분모를 각각 더한 보기 생성",
        error_type="절차오류",
        difficulty="중",
        correction_point="통분의 필요성을 시각으로 보인다",
        ccss_code="5.NF.A.1",
        concept_src_id="UC-NUM-FRAC-ADD",
        standard_code="2022_5수01_03",
        school_level="초등학교",
        domain="수와 연산",
        subunit="분수의 덧셈",
        mapping_confidence="높음",
        mapping_score=0.873,
        provenance_note="gen:gpt5 / 검수:Kiki",
    )
    orm = OrmMisconceptionCatalog.from_schema(s)
    assert orm.mis_id == "M0425"
    assert orm.canonical_statement == "분수의 분모끼리 더한다."
    assert orm.error_type == "절차오류"
    assert orm.difficulty == "중"
    assert orm.concept_src_id == "UC-NUM-FRAC-ADD"
    assert orm.standard_code == "2022_5수01_03"

    back = orm.to_schema()
    assert back.mis_id == s.mis_id
    assert back.canonical_statement == s.canonical_statement
    assert back.student_wrong_thinking == s.student_wrong_thinking
    assert back.distractor_rule == s.distractor_rule
    assert back.error_type == s.error_type
    assert back.difficulty == s.difficulty
    assert back.correction_point == s.correction_point
    assert back.ccss_code == s.ccss_code
    assert back.concept_src_id == s.concept_src_id
    assert back.standard_code == s.standard_code
    assert back.school_level == s.school_level
    assert back.domain == s.domain
    assert back.subunit == s.subunit
    assert back.mapping_confidence == s.mapping_confidence
    assert back.provenance_note == s.provenance_note
    # mapping_score는 float로 복원된다(ORM은 Decimal로 담지만 schema는 float).
    assert back.mapping_score == 0.873


def test_catalog_roundtrip_minimal_defaults() -> None:
    """필수 mis_id만 채운 레코드도 변환된다(나머지 선택 필드는 None)."""
    s = _valid_catalog()
    orm = OrmMisconceptionCatalog.from_schema(s)
    assert orm.mis_id == "M0425"
    assert orm.canonical_statement is None
    assert orm.error_type is None
    assert orm.mapping_score is None

    back = orm.to_schema()
    assert back.mis_id == "M0425"
    assert back.canonical_statement is None
    assert back.difficulty is None
    assert back.concept_src_id is None
    assert back.mapping_score is None


def test_catalog_mapping_score_high_value() -> None:
    """mapping_score 1.236(>1) 같은 값도 NUMERIC(5,3) 범위라 보존된다."""
    s = _valid_catalog(mapping_score=1.236)
    orm = OrmMisconceptionCatalog.from_schema(s)
    # from_schema는 float을 그대로 넘긴다(INSERT 시 Numeric으로 저장).
    assert orm.mapping_score == 1.236

    # ORM이 Decimal을 들고 있을 때도 schema 복원이 float으로 된다.
    orm.mapping_score = Decimal("1.236")
    assert orm.to_schema().mapping_score == 1.236
