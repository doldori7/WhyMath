"""TextbookMapping ORM(영속 레이어) 단위테스트 — DB 연결 *없이* 검증 가능한 것만.

⚠️ 이 도메인은 *유일하게 비-1:1*이다 — schema 중첩(unit_tree·tone_profile)을 관계형 2테이블
(textbook_mapping + textbook_unit)로 편다. 따라서 다른 테스트보다 *중첩 roundtrip*에 무게를 둔다.

problem ORM 테스트 패턴 답습 + 관계형 평탄화 검증: 메타데이터 등록(2테이블) / PG DDL 컴파일
(JSONB tone_profile·ON DELETE CASCADE·self-FK) / enum values_callable / **중첩 unit_tree
roundtrip**(from_schema→to_schema 보존).

설계 정본: schemas/v1.1/textbook_mapping.schema.yaml.
"""

from __future__ import annotations

from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable
from whymath_backend.db.base import Base
from whymath_backend.db.models.textbook_mapping import (
    TextbookMapping as OrmTextbookMapping,
)
from whymath_backend.db.models.textbook_mapping import (
    TextbookUnit as OrmTextbookUnit,
)
from whymath_backend.schema.enums import LegalReviewStatus
from whymath_backend.schema.textbook_mapping import (
    TextbookMapping as SchemaTextbookMapping,
)
from whymath_backend.schema.textbook_mapping import (
    TextbookToneProfile as SchemaTextbookToneProfile,
)
from whymath_backend.schema.textbook_mapping import (
    TextbookUnit as SchemaTextbookUnit,
)


def _pg_ddl(table: object) -> str:
    """ORM 테이블을 PostgreSQL dialect로 컴파일한 CREATE TABLE 문자열로 반환."""
    return str(CreateTable(table).compile(dialect=postgresql.dialect()))  # type: ignore[arg-type]


def _valid_mapping(**overrides: object) -> SchemaTextbookMapping:
    """유효한 schema.TextbookMapping(대→중 2단계 단원 트리·톤 프로필 보유)."""
    units = [
        SchemaTextbookUnit(
            unit_id="U1",
            unit_number="1",
            unit_title="이차함수",
            page_range="12-35",
            standard_codes=["[10공수1-02-01]"],
            concept_ids=["UC-QUAD"],
        ),
        SchemaTextbookUnit(
            unit_id="U1-1",
            parent_unit_id="U1",
            unit_number="1-1",
            unit_title="이차함수의 그래프",
        ),
    ]
    tone = SchemaTextbookToneProfile(
        formality_level="높음",
        sequencing_style="개념선행형",
        notation_preferences=["f(x)", "y="],
    )
    base: dict[str, object] = {
        "isbn": "9791234567890",
        "publisher": "미래엔",
        "book_title": "고등학교 공통수학1",
        "authors": ["저자A", "저자B"],
        "subject": "공통수학1",
        "grade": 10,
        "revision_year": 2025,
        "unit_tree": units,
        "tone_profile": tone,
        "source_urls": ["https://publisher.example/toc"],
        "isolation_tag": "미래엔-9791234567890",
    }
    base.update(overrides)
    return SchemaTextbookMapping(**base)  # type: ignore[arg-type]


# ──────────────────────────────────────────────────────────────────────────
# 1) 메타데이터 등록 — 중첩이 2테이블로 펴졌는지
# ──────────────────────────────────────────────────────────────────────────
def test_textbook_tables_registered_in_metadata() -> None:
    """Base.metadata에 textbook_mapping·textbook_unit 두 테이블이 등록돼 있다."""
    tables = set(Base.metadata.tables.keys())
    assert {"textbook_mapping", "textbook_unit"} <= tables


def test_textbook_orm_tablenames() -> None:
    """각 ORM의 __tablename__이 YAML storage(textbook_mappings + textbook_units)와 정합."""
    assert OrmTextbookMapping.__tablename__ == "textbook_mapping"
    assert OrmTextbookUnit.__tablename__ == "textbook_unit"


# ──────────────────────────────────────────────────────────────────────────
# 2) PG DDL 컴파일 — tone_profile JSONB·ON DELETE CASCADE·self-FK
# ──────────────────────────────────────────────────────────────────────────
def test_textbook_mapping_tone_profile_is_jsonb() -> None:
    """TextbookMapping: tone_profile은 별도 테이블이 아니라 JSONB 컬럼·isbn PK."""
    ddl = _pg_ddl(OrmTextbookMapping.__table__)
    assert "JSONB" in ddl  # tone_profile
    assert "PRIMARY KEY (isbn)" in ddl
    assert "legal_review_status_enum" in ddl
    # isbn은 UUID가 아니므로 gen_random_uuid()가 없어야 한다.
    assert "gen_random_uuid()" not in ddl


def test_textbook_unit_cascade_and_self_fk() -> None:
    """TextbookUnit: textbook_isbn FK는 ON DELETE CASCADE, parent_unit_id는 self-FK."""
    ddl = _pg_ddl(OrmTextbookUnit.__table__)
    assert "ON DELETE CASCADE" in ddl  # 교과서 격리 시 단원 동반 삭제(YAML §4.5)
    assert "REFERENCES textbook_mapping (isbn)" in ddl
    assert "REFERENCES textbook_unit (unit_id)" in ddl  # parent_unit_id self-FK


def test_textbook_unit_loose_refs_are_not_fk() -> None:
    """standard_codes·concept_ids는 cross-dataset 느슨참조라 FK가 아니다(배열 TEXT[])."""
    ddl = _pg_ddl(OrmTextbookUnit.__table__)
    assert "TEXT[]" in ddl  # standard_codes·concept_ids
    # FK는 textbook_isbn·parent_unit_id 둘뿐(standard_codes/concept_ids는 FK 아님).
    fk_cols = {fk.parent.name for fk in OrmTextbookUnit.__table__.foreign_keys}
    assert fk_cols == {"textbook_isbn", "parent_unit_id"}


# ──────────────────────────────────────────────────────────────────────────
# 3) enum values_callable + 관계 설정
# ──────────────────────────────────────────────────────────────────────────
def test_legal_review_status_enum_values() -> None:
    """legal_review_status 컬럼 enum이 값('not_required'·'cleared' 등)을 갖는다."""
    enums = OrmTextbookMapping.__table__.c.legal_review_status.type.enums  # type: ignore[attr-defined]
    assert "not_required" in enums
    assert "pending" in enums
    assert "cleared" in enums


def test_textbook_mapping_units_relationship_exists() -> None:
    """TextbookMapping.units ↔ TextbookUnit.mapping back_populates 관계가 매핑돼 있다."""
    rels = OrmTextbookMapping.__mapper__.relationships
    assert "units" in rels
    assert rels["units"].mapper.class_ is OrmTextbookUnit
    back_rels = OrmTextbookUnit.__mapper__.relationships
    assert "mapping" in back_rels


# ──────────────────────────────────────────────────────────────────────────
# 4) 중첩 unit_tree roundtrip — 이 도메인의 핵심
# ──────────────────────────────────────────────────────────────────────────
def test_textbook_nested_roundtrip_preserves_unit_tree_and_tone() -> None:
    """schema.TextbookMapping(중첩) → ORM(2테이블) → schema가 unit_tree·tone_profile을 보존."""
    s = _valid_mapping()
    orm = OrmTextbookMapping.from_schema(s)

    # from_schema: 중첩 평탄화 — units 행 2개·tone_profile은 JSONB dict.
    assert len(orm.units) == 2
    assert isinstance(orm.tone_profile, dict)
    assert orm.tone_profile["formality_level"] == "높음"
    assert orm.isbn == "9791234567890"
    assert orm.subject == "공통수학1"  # str(enum 아님)

    # to_schema: 중첩 복원.
    back = orm.to_schema()
    assert back.isbn == "9791234567890"
    assert back.publisher == "미래엔"
    assert back.authors == ["저자A", "저자B"]
    assert len(back.unit_tree) == 2
    # 단원 트리 내용 보존(대단원·중단원 + self-parent + 느슨참조 코드).
    assert back.unit_tree[0].unit_id == "U1"
    assert back.unit_tree[0].standard_codes == ["[10공수1-02-01]"]
    assert back.unit_tree[0].concept_ids == ["UC-QUAD"]
    assert back.unit_tree[1].unit_id == "U1-1"
    assert back.unit_tree[1].parent_unit_id == "U1"
    # 톤 프로필(JSONB → 서브모델) 보존.
    assert back.tone_profile.formality_level == "높음"
    assert back.tone_profile.sequencing_style == "개념선행형"
    assert back.tone_profile.notation_preferences == ["f(x)", "y="]


def test_textbook_unit_from_schema_skips_isbn_fk() -> None:
    """TextbookUnit.from_schema는 schema에 없는 textbook_isbn FK를 세우지 않는다(관계가 설정).

    개별 단원 변환 시 textbook_isbn은 None이고(관계 append/flush 시 채워짐), unit_id·
    parent_unit_id 같은 schema 필드만 매핑된다.
    """
    su = SchemaTextbookUnit(unit_id="U9", unit_number="9", unit_title="삼각함수")
    ou = OrmTextbookUnit.from_schema(su)
    assert ou.unit_id == "U9"
    assert ou.unit_title == "삼각함수"
    assert ou.textbook_isbn is None  # 관계로 채워지기 전(단위테스트는 flush 없음)

    back = ou.to_schema()
    assert back.unit_id == "U9"
    assert back.unit_title == "삼각함수"


def test_textbook_legal_gating_default_keeps_objective_none() -> None:
    """기본(not_required)에서 learning_objective_text는 None — schema 게이팅이 강제(ORM 보존)."""
    s = _valid_mapping()
    assert s.legal_review_status == LegalReviewStatus.not_required.value
    orm = OrmTextbookMapping.from_schema(s)
    back = orm.to_schema()
    assert back.legal_review_status == LegalReviewStatus.not_required.value
    for unit in back.unit_tree:
        assert unit.learning_objective_text is None
