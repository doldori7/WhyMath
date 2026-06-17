"""AchievementStandard·ConceptStandardLink ORM(영속 레이어) 단위테스트 — DB 연결 *없이*.

`test_concept_orm.py`·`test_curriculum_entry_orm.py` 패턴 답습: 메타데이터 등록 / PG DDL 컴파일
(PK·UNIQUE·FK·DATE·TEXT[]) / from_schema·to_schema 변환 roundtrip / 제약 의도(official_code
비유일 · norm_id PK · UNIQUE(curriculum_revision, official_code) · norm_id 실 FK CASCADE).
실제 PG 적용·왕복은 CI `backend-migrations` 잡(alembic upgrade head ↔ downgrade base)이 확인한다.

설계 정본: whymath_backend/schema/standard.py + db/models/achievement_standard.py +
db/models/concept_standard_link.py.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable

from whymath_backend.db.base import Base
from whymath_backend.db.models.achievement_standard import (
    AchievementStandard as OrmAchievementStandard,
)
from whymath_backend.db.models.concept_standard_link import (
    ConceptStandardLink as OrmConceptStandardLink,
)
from whymath_backend.schema.standard import (
    AchievementStandard as SchemaAchievementStandard,
)
from whymath_backend.schema.standard import (
    ConceptStandardLink as SchemaConceptStandardLink,
)


def _pg_ddl(table: object) -> str:
    """ORM 테이블을 PostgreSQL dialect로 컴파일한 CREATE TABLE 문자열로 반환."""
    return str(CreateTable(table).compile(dialect=postgresql.dialect()))  # type: ignore[arg-type]


def _valid_standard(**overrides: object) -> SchemaAchievementStandard:
    """유효한 schema.AchievementStandard(고등학교 미적분 성취기준 — 본문·출처 보유)."""
    base: dict[str, object] = {
        "norm_id": "2022_12미적1_01_01",
        "official_code": "[12미적1-01-01]",
        "curriculum_revision": "2022 개정",
        "grade_band": "고등학교",
        "school_type": "고등학교",
        "subject": "미적분Ⅰ",
        "domain": "변화와 관계",
        "statement": "함수의 극한의 뜻을 알고 그 성질을 이해한다.",
        "source_url": "https://ncic.example/2022/12미적1",
    }
    base.update(overrides)
    return SchemaAchievementStandard(**base)  # type: ignore[arg-type]


def _valid_link(**overrides: object) -> SchemaConceptStandardLink:
    """유효한 schema.ConceptStandardLink(개념↔성취기준 '직접' 연결)."""
    base: dict[str, object] = {
        "concept_code": "UC-CAL-LIM-DEF",
        "norm_id": "2022_12미적1_01_01",
        "link_type": "직접",
    }
    base.update(overrides)
    return SchemaConceptStandardLink(**base)  # type: ignore[arg-type]


# ──────────────────────────────────────────────────────────────────────────
# 1) 메타데이터 등록
# ──────────────────────────────────────────────────────────────────────────
def test_standard_tables_registered_in_metadata() -> None:
    """Base.metadata에 두 테이블이 등록돼 있다(alembic 인식 전제)."""
    tables = set(Base.metadata.tables.keys())
    assert {"achievement_standard", "concept_standard_link"} <= tables


def test_standard_orm_tablenames() -> None:
    """각 ORM의 __tablename__이 마이그레이션 테이블명과 일치한다."""
    assert OrmAchievementStandard.__tablename__ == "achievement_standard"
    assert OrmConceptStandardLink.__tablename__ == "concept_standard_link"


# ──────────────────────────────────────────────────────────────────────────
# 2) achievement_standard PG DDL — PK·UNIQUE·official_code 비유일·DATE·TEXT[]
# ──────────────────────────────────────────────────────────────────────────
def test_achievement_standard_pk_is_norm_id() -> None:
    """PK는 norm_id 단일이다(official_code 아님)."""
    ddl = _pg_ddl(OrmAchievementStandard.__table__)
    assert "PRIMARY KEY (norm_id)" in ddl
    pk_cols = [c.name for c in OrmAchievementStandard.__table__.primary_key.columns]
    assert pk_cols == ["norm_id"]


def test_achievement_standard_official_code_non_unique() -> None:
    """official_code는 NON-unique 컬럼이다 — 단독 UNIQUE/PK가 아니다(교육과정 간 비유일)."""
    col = OrmAchievementStandard.__table__.c.official_code
    assert col.unique is not True  # 단독 UNIQUE 아님(None/False)
    assert col.primary_key is False
    assert col.nullable is False  # 단, NOT NULL은 맞다


def test_achievement_standard_unique_revision_official_code() -> None:
    """교육과정 간 유일성은 UNIQUE(curriculum_revision, official_code)로 강제된다."""
    ddl = _pg_ddl(OrmAchievementStandard.__table__)
    assert "UNIQUE (curriculum_revision, official_code)" in ddl
    assert "uq_achievement_standard_revision_official_code" in ddl


def test_achievement_standard_date_and_text_array_and_no_fk() -> None:
    """effective_from은 DATE, parent_codes는 TEXT[](빈 배열 기본), FK·UUID PK 없음."""
    ddl = _pg_ddl(OrmAchievementStandard.__table__)
    assert "DATE" in ddl  # effective_from (TIMESTAMPTZ 아님)
    assert "TEXT[]" in ddl  # parent_codes
    assert "'{}'::text[]" in ddl  # NOT NULL 배열 빈 기본값
    # norm_id는 의미 문자열(UUID 아님) → gen_random_uuid() 없음.
    assert "gen_random_uuid()" not in ddl
    # 성취기준 자체는 다른 테이블을 참조하지 않는다(느슨참조 코드들도 FK 아님).
    assert len(OrmAchievementStandard.__table__.foreign_keys) == 0
    assert "REFERENCES" not in ddl


def test_achievement_standard_indexes() -> None:
    """official_code 단일 · (curriculum_revision, domain) 인덱스가 정의된다."""
    by_name = {
        ix.name: [c.name for c in ix.columns] for ix in OrmAchievementStandard.__table__.indexes
    }
    assert by_name["idx_achievement_standard_official_code"] == ["official_code"]
    assert by_name["idx_achievement_standard_revision_domain"] == [
        "curriculum_revision",
        "domain",
    ]


# ──────────────────────────────────────────────────────────────────────────
# 3) concept_standard_link PG DDL — UUID PK·실 FK CASCADE·느슨 concept_code·UNIQUE
# ──────────────────────────────────────────────────────────────────────────
def test_concept_standard_link_uuid_pk() -> None:
    """link_id는 UUID PK이고 server_default gen_random_uuid()를 갖는다."""
    ddl = _pg_ddl(OrmConceptStandardLink.__table__)
    assert "PRIMARY KEY (link_id)" in ddl
    assert "gen_random_uuid()" in ddl
    assert "UUID" in ddl
    pk_cols = [c.name for c in OrmConceptStandardLink.__table__.primary_key.columns]
    assert pk_cols == ["link_id"]


def test_concept_standard_link_real_fk_cascade_to_standard() -> None:
    """norm_id는 achievement_standard.norm_id 실 FK이고 ON DELETE CASCADE다."""
    ddl = _pg_ddl(OrmConceptStandardLink.__table__)
    assert "REFERENCES achievement_standard (norm_id)" in ddl
    assert "ON DELETE CASCADE" in ddl
    fks = list(OrmConceptStandardLink.__table__.foreign_keys)
    assert len(fks) == 1  # norm_id 단 하나의 FK(concept_code는 느슨참조라 FK 아님)
    fk = fks[0]
    assert fk.column.table.name == "achievement_standard"
    assert fk.parent.name == "norm_id"
    assert fk.ondelete == "CASCADE"


def test_concept_standard_link_concept_code_is_loose_ref_not_fk() -> None:
    """concept_code는 느슨참조(String(64))라 FK가 아니다(Concept.code와 동일 어휘·길이)."""
    col = OrmConceptStandardLink.__table__.c.concept_code
    assert len(col.foreign_keys) == 0
    assert col.type.length == 64  # type: ignore[attr-defined]


def test_concept_standard_link_unique_and_indexes() -> None:
    """UNIQUE(concept_code, norm_id, link_type) + norm_id·concept_code 인덱스."""
    ddl = _pg_ddl(OrmConceptStandardLink.__table__)
    assert "UNIQUE (concept_code, norm_id, link_type)" in ddl
    assert "uq_concept_standard_link_concept_norm_type" in ddl
    by_name = {
        ix.name: [c.name for c in ix.columns] for ix in OrmConceptStandardLink.__table__.indexes
    }
    assert by_name["idx_concept_standard_link_norm"] == ["norm_id"]
    assert by_name["idx_concept_standard_link_concept"] == ["concept_code"]


def test_concept_standard_link_link_type_is_string_not_enum() -> None:
    """link_type은 VARCHAR(8)로 담는다(PG native enum 아님 — concept_node.review_status 선례)."""
    col_type = OrmConceptStandardLink.__table__.c.link_type.type
    assert isinstance(col_type, postgresql.VARCHAR) or col_type.__class__.__name__ == "String"
    assert col_type.length == 8  # type: ignore[attr-defined]
    # enum이 아니므로 enums 속성이 없다.
    assert not hasattr(col_type, "enums")


# ──────────────────────────────────────────────────────────────────────────
# 4) 변환 roundtrip — AchievementStandard
# ──────────────────────────────────────────────────────────────────────────
def test_achievement_standard_roundtrip_preserves_fields() -> None:
    """schema.AchievementStandard → ORM → schema가 핵심 필드(식별·본문·날짜·배열·출처)를 보존."""
    s = _valid_standard(
        sub_domain="극한",
        commentary="좌극한·우극한을 함께 다룬다.",
        big_idea="변화의 누적과 순간",
        effective_from=date(2025, 3, 1),
        parent_codes=["[9수01-01]"],
        source_document="2022-33호.pdf",
    )
    orm = OrmAchievementStandard.from_schema(s)
    assert orm.norm_id == "2022_12미적1_01_01"
    assert orm.official_code == "[12미적1-01-01]"
    assert orm.curriculum_revision == "2022 개정"
    assert orm.statement == "함수의 극한의 뜻을 알고 그 성질을 이해한다."
    assert orm.effective_from == date(2025, 3, 1)
    assert orm.parent_codes == ["[9수01-01]"]
    assert orm.source_url == "https://ncic.example/2022/12미적1"

    back = orm.to_schema()
    assert back.norm_id == s.norm_id
    assert back.official_code == s.official_code
    assert back.sub_domain == s.sub_domain
    assert back.commentary == s.commentary
    assert back.big_idea == s.big_idea
    assert back.effective_from == date(2025, 3, 1)
    assert back.parent_codes == s.parent_codes
    assert back.source_document == s.source_document


def test_achievement_standard_roundtrip_minimal_defaults() -> None:
    """필수 필드만 채운 성취기준도 변환된다(parent_codes 기본 빈 리스트·선택 필드 None)."""
    s = _valid_standard()
    orm = OrmAchievementStandard.from_schema(s)
    assert orm.parent_codes == []  # schema default_factory=list
    assert orm.sub_domain is None
    assert orm.effective_from is None

    back = orm.to_schema()
    assert back.parent_codes == []
    assert back.commentary is None
    assert back.big_idea is None
    assert back.source_document is None


# ──────────────────────────────────────────────────────────────────────────
# 5) 변환 roundtrip — ConceptStandardLink (link_id는 ORM 전용 — schema에 없음)
# ──────────────────────────────────────────────────────────────────────────
def test_concept_standard_link_roundtrip_preserves_fields() -> None:
    """schema.ConceptStandardLink → ORM → schema가 concept_code·norm_id·link_type·note를 보존."""
    s = _valid_link(note="2022 개정 신설 성취기준에 직접 대응")
    orm = OrmConceptStandardLink.from_schema(s)
    assert orm.concept_code == "UC-CAL-LIM-DEF"
    assert orm.norm_id == "2022_12미적1_01_01"
    assert orm.link_type == "직접"
    assert orm.note == "2022 개정 신설 성취기준에 직접 대응"

    back = orm.to_schema()
    assert back.concept_code == s.concept_code
    assert back.norm_id == s.norm_id
    assert back.link_type == s.link_type
    assert back.note == s.note


def test_concept_standard_link_from_schema_leaves_link_id_for_server_default() -> None:
    """schema엔 link_id가 없으므로 from_schema는 link_id를 비운다(DB server_default가 채움)."""
    s = _valid_link()
    orm = OrmConceptStandardLink.from_schema(s)
    # 앱에서 명시하지 않았으니 None(INSERT 시 gen_random_uuid() server_default가 채운다).
    assert orm.link_id is None


def test_concept_standard_link_roundtrip_all_link_types() -> None:
    """세 link_type 값('직접'/'재매핑'/'준용') 모두 ORM↔schema를 왕복한다(한글 정본 보존)."""
    for lt in ("직접", "재매핑", "준용"):
        s = _valid_link(link_type=lt)
        orm = OrmConceptStandardLink.from_schema(s)
        assert orm.link_type == lt
        assert orm.to_schema().link_type == lt
