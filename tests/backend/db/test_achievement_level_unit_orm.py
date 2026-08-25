"""AchievementLevelUnit ORM(영속 레이어) 단위테스트 — DB 연결 *없이* (CUR-07 신규 테이블).

`test_achievement_standard_orm.py` 패턴 답습: 메타데이터 등록 / PG DDL 컴파일(UUID PK·자연
UNIQUE·FK 부재) / from_schema·to_schema 변환 roundtrip. 실제 PG 적용·왕복은 CI
`backend-migrations` 잡(alembic upgrade head ↔ downgrade base)이 확인한다.

설계 정본: whymath_backend/schema/standard.py(AchievementLevelUnit) +
db/models/achievement_level_unit.py.
"""

from __future__ import annotations

from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable

from whymath_backend.db.base import Base
from whymath_backend.db.models.achievement_level_unit import (
    AchievementLevelUnit as OrmAchievementLevelUnit,
)
from whymath_backend.schema.standard import (
    AchievementLevelUnit as SchemaAchievementLevelUnit,
)


def _pg_ddl(table: object) -> str:
    """ORM 테이블을 PostgreSQL dialect로 컴파일한 CREATE TABLE 문자열로 반환."""
    return str(CreateTable(table).compile(dialect=postgresql.dialect()))  # type: ignore[arg-type]


def _valid_unit(**overrides: object) -> SchemaAchievementLevelUnit:
    """유효한 schema.AchievementLevelUnit(고등학교 공통수학 '다항식' 단원 등급)."""
    base: dict[str, object] = {
        "school_level": "고등학교",
        "subject": "공통수학",
        "unit": "(1) 다항식",
        "levels": ["A", "B", "C", "D", "E"],
    }
    base.update(overrides)
    return SchemaAchievementLevelUnit(**base)  # type: ignore[arg-type]


# ──────────────────────────────────────────────────────────────────────────
# 1) 메타데이터 등록
# ──────────────────────────────────────────────────────────────────────────
def test_achievement_level_unit_registered_in_metadata() -> None:
    """Base.metadata에 테이블이 등록돼 있다(alembic 인식 전제)."""
    assert "achievement_level_unit" in Base.metadata.tables


def test_achievement_level_unit_tablename() -> None:
    assert OrmAchievementLevelUnit.__tablename__ == "achievement_level_unit"


# ──────────────────────────────────────────────────────────────────────────
# 2) PG DDL — UUID PK·자연 UNIQUE·FK 없음(독립 테이블 — 설계 결정)
# ──────────────────────────────────────────────────────────────────────────
def test_achievement_level_unit_uuid_pk() -> None:
    """unit_id는 UUID PK이고 server_default gen_random_uuid()를 갖는다."""
    ddl = _pg_ddl(OrmAchievementLevelUnit.__table__)
    assert "PRIMARY KEY (unit_id)" in ddl
    assert "gen_random_uuid()" in ddl
    pk_cols = [c.name for c in OrmAchievementLevelUnit.__table__.primary_key.columns]
    assert pk_cols == ["unit_id"]


def test_achievement_level_unit_no_fk() -> None:
    """어떤 테이블과도 FK를 걸지 않는다 — 개별 성취기준 연결은 설계상 범위 밖(모듈 docstring)."""
    ddl = _pg_ddl(OrmAchievementLevelUnit.__table__)
    assert len(OrmAchievementLevelUnit.__table__.foreign_keys) == 0
    assert "REFERENCES" not in ddl


def test_achievement_level_unit_natural_unique_key() -> None:
    """자연 유일키 UNIQUE(school_level, subject, unit) — 멱등 upsert 대상."""
    ddl = _pg_ddl(OrmAchievementLevelUnit.__table__)
    assert "UNIQUE (school_level, subject, unit)" in ddl
    assert "uq_achievement_level_unit_school_subject_unit" in ddl


def test_achievement_level_unit_levels_text_array_not_null() -> None:
    """levels는 TEXT[] NOT NULL(빈 배열 기본) — parent_codes와 동일 배열 패턴."""
    col = OrmAchievementLevelUnit.__table__.c.levels
    assert col.nullable is False
    ddl = _pg_ddl(OrmAchievementLevelUnit.__table__)
    assert "TEXT[]" in ddl
    assert "'{}'::text[]" in ddl


def test_achievement_level_unit_index() -> None:
    """과목 단위 조회 경로 인덱스(school_level, subject)가 정의된다."""
    by_name = {
        ix.name: [c.name for c in ix.columns] for ix in OrmAchievementLevelUnit.__table__.indexes
    }
    assert by_name["idx_achievement_level_unit_subject"] == ["school_level", "subject"]


# ──────────────────────────────────────────────────────────────────────────
# 3) 변환 roundtrip (unit_id는 ORM 전용 — schema에 없음)
# ──────────────────────────────────────────────────────────────────────────
def test_achievement_level_unit_roundtrip_preserves_fields() -> None:
    """schema.AchievementLevelUnit → ORM → schema가 핵심 필드를 보존."""
    s = _valid_unit(source_document="achievement_criteria_v1")
    orm = OrmAchievementLevelUnit.from_schema(s)
    assert orm.school_level == "고등학교"
    assert orm.subject == "공통수학"
    assert orm.unit == "(1) 다항식"
    assert orm.levels == ["A", "B", "C", "D", "E"]
    assert orm.source_document == "achievement_criteria_v1"

    back = orm.to_schema()
    assert back.school_level == s.school_level
    assert back.subject == s.subject
    assert back.unit == s.unit
    assert back.levels == s.levels
    assert back.source_document == s.source_document


def test_achievement_level_unit_from_schema_leaves_unit_id_for_server_default() -> None:
    """schema엔 unit_id가 없으므로 from_schema는 unit_id를 비운다(DB server_default가 채움)."""
    orm = OrmAchievementLevelUnit.from_schema(_valid_unit())
    assert orm.unit_id is None


def test_achievement_level_unit_roundtrip_minimal_defaults() -> None:
    """levels 미지정(빈 배열)·source_document 미지정(None)도 변환된다."""
    s = _valid_unit(levels=[])
    orm = OrmAchievementLevelUnit.from_schema(s)
    assert orm.levels == []
    assert orm.source_document is None

    back = orm.to_schema()
    assert back.levels == []
    assert back.source_document is None


def test_achievement_level_unit_roundtrip_partial_levels() -> None:
    """A~C만 정의된 단원(고급수학 등 일부 과목 실측 패턴)도 그대로 보존한다."""
    s = _valid_unit(unit="(2) 예시 평가 문항", levels=["C"])
    orm = OrmAchievementLevelUnit.from_schema(s)
    assert orm.levels == ["C"]
    assert orm.to_schema().levels == ["C"]
