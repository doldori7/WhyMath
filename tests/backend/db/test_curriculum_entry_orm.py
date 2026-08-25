"""CurriculumEntry ORM(영속 레이어) 단위테스트 — DB 연결 *없이* 검증 가능한 것만.

problem ORM 테스트 패턴 답습: 메타데이터 등록 / PG DDL 컴파일(enum·DATE·UNIQUE) / enum
values_callable(⚠️ CurriculumLicense는 멤버명≠값 하이픈 케이스 — KR-NCIC) / schema↔ORM 변환
roundtrip / PK 판단(entry_id 단일 PK + UNIQUE(concept_id, country_code, subject) — S1 3-튜플).

설계 정본: schemas/v1.1/curriculum_entry.schema.yaml.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable

from whymath_backend.db.base import Base
from whymath_backend.db.models.curriculum_entry import CurriculumEntry as OrmCurriculumEntry
from whymath_backend.schema.curriculum_entry import CurriculumEntry as SchemaCurriculumEntry
from whymath_backend.schema.enums import CurriculumLicense, RequiredDepth


def _pg_ddl(table: object) -> str:
    """ORM 테이블을 PostgreSQL dialect로 컴파일한 CREATE TABLE 문자열로 반환."""
    return str(CreateTable(table).compile(dialect=postgresql.dialect()))  # type: ignore[arg-type]


def _valid_entry(**overrides: object) -> SchemaCurriculumEntry:
    """유효한 schema.CurriculumEntry(KR 셀 — is_present=true·source_url 보유)."""
    now = datetime(2026, 5, 1, tzinfo=timezone.utc)
    base: dict[str, object] = {
        "concept_id": "UC-CAL-INT-DEF",
        "country_code": "KR",
        "entry_id": "KR::UC-CAL-INT-DEF",
        "source_name": "2022 개정 교육과정 — 수학과 교육과정",
        "license_id": CurriculumLicense.KR_NCIC,
        "is_present": True,
        "source_url": "https://ncic.example/2022",
        "confidence": 0.95,
        "created_at": now,
        "updated_at": now,
    }
    base.update(overrides)
    return SchemaCurriculumEntry(**base)  # type: ignore[arg-type]


# ──────────────────────────────────────────────────────────────────────────
# 1) 메타데이터 등록
# ──────────────────────────────────────────────────────────────────────────
def test_curriculum_entry_registered_in_metadata() -> None:
    """Base.metadata에 curriculum_entry 테이블이 등록돼 있다(alembic 인식 전제)."""
    assert "curriculum_entry" in Base.metadata.tables
    assert OrmCurriculumEntry.__tablename__ == "curriculum_entry"


# ──────────────────────────────────────────────────────────────────────────
# 2) PG DDL 컴파일 + PK 판단
# ──────────────────────────────────────────────────────────────────────────
def test_curriculum_entry_pk_is_entry_id_single() -> None:
    """PK는 entry_id 단일 PK다(복합키 (concept_id, country_code, subject)는 UNIQUE로 강제)."""
    ddl = _pg_ddl(OrmCurriculumEntry.__table__)
    assert "PRIMARY KEY (entry_id)" in ddl
    # 복합 의미키는 3-튜플 UNIQUE 제약으로(S1 subject 축 — 2-튜플 회귀 방지).
    assert "UNIQUE (concept_id, country_code, subject)" in ddl
    assert "UNIQUE (concept_id, country_code)\n" not in ddl  # 구 2-튜플 잔존 금지
    pk_cols = [c.name for c in OrmCurriculumEntry.__table__.primary_key.columns]
    assert pk_cols == ["entry_id"]


def test_curriculum_entry_subject_column_not_null_default_math() -> None:
    """subject 컬럼(S1) — NOT NULL + server_default '수학'(기존 행·INSERT 무손상 백필).

    교과 레벨 축('수학'·'물리') — NCIC AchievementStandard.subject(과목 레벨)와 granularity
    다름(모듈 docstring 교차 명기). 마이그레이션 rev a4b5c6d7e8f9와 정의 일치(드리프트 0).
    """
    col = OrmCurriculumEntry.__table__.c.subject
    assert col.nullable is False
    assert col.server_default is not None
    assert col.server_default.arg == "수학"  # type: ignore[union-attr]
    ddl = _pg_ddl(OrmCurriculumEntry.__table__)
    assert "subject VARCHAR DEFAULT '수학' NOT NULL" in ddl


def test_curriculum_entry_ddl_enum_and_date() -> None:
    """DDL에 required_depth_enum·curriculum_license_enum·DATE(effective_from) 포함."""
    ddl = _pg_ddl(OrmCurriculumEntry.__table__)
    assert "required_depth_enum" in ddl
    assert "curriculum_license_enum" in ddl
    assert "DATE" in ddl  # effective_from (TIMESTAMPTZ 아님)
    # entry_id는 UUID가 아니므로 gen_random_uuid()가 없어야 한다(표면키 str).
    assert "gen_random_uuid()" not in ddl


def test_curriculum_entry_loose_refs_and_framework_fk() -> None:
    """concept_id·country_code·national_standard_codes 등은 느슨참조라 FK가 없고,
    CUR-10에서 추가된 framework_id만 curriculum_framework를 참조한다."""
    fks = {fk.parent.name: fk.column.table.name for fk in OrmCurriculumEntry.__table__.foreign_keys}
    assert fks == {"framework_id": "curriculum_framework"}
    ddl = _pg_ddl(OrmCurriculumEntry.__table__)
    assert "REFERENCES curriculum_framework (framework_id)" in ddl
    # 느슨참조 컬럼들은 여전히 FK가 아니다.
    assert "REFERENCES concept" not in ddl
    assert "REFERENCES country" not in ddl


# ──────────────────────────────────────────────────────────────────────────
# 3) enum values_callable — ⚠️ CurriculumLicense 멤버명≠값(하이픈) 회귀 가드
# ──────────────────────────────────────────────────────────────────────────
def test_curriculum_license_enum_uses_hyphen_values_not_member_names() -> None:
    """license_id 컬럼 enum이 하이픈 값('KR-NCIC')을 갖는다(멤버명 'KR_NCIC' 아님).

    CurriculumLicense.KR_NCIC = "KR-NCIC"처럼 멤버명≠값이라 values_callable이 빠지면
    SQLAlchemy가 멤버명('KR_NCIC')으로 PG enum을 만들어 YAML 값('KR-NCIC')과 어긋난다 —
    이 테스트가 그 회귀를 막는다(problem의 '2015_REVISION' 가드와 동형).
    """
    enums = OrmCurriculumEntry.__table__.c.license_id.type.enums  # type: ignore[attr-defined]
    assert "KR-NCIC" in enums  # 값(정본)
    assert "KR_NCIC" not in enums  # 멤버명이 라벨로 새지 않았는지
    assert "US-CCSS" in enums
    assert "INT-IMO" in enums


def test_required_depth_enum_values() -> None:
    """required_depth 컬럼 enum이 값('conceptual' 등)을 갖는다."""
    enums = OrmCurriculumEntry.__table__.c.required_depth.type.enums  # type: ignore[attr-defined]
    assert "awareness" in enums
    assert "conceptual" in enums
    assert "mastery" in enums


# ──────────────────────────────────────────────────────────────────────────
# 4) 변환 roundtrip
# ──────────────────────────────────────────────────────────────────────────
def test_curriculum_entry_roundtrip_preserves_core_fields() -> None:
    """schema.CurriculumEntry → ORM → schema가 핵심 필드(복합키·라이선스·깊이·날짜·배열)를 보존."""
    s = _valid_entry(
        required_depth=RequiredDepth.conceptual,
        effective_from=date(2025, 3, 1),
        notation_variants=["∫", "antiderivative"],
        national_standard_codes=["[10공수1-02-01]"],
        introduced_grade=11,
    )
    orm = OrmCurriculumEntry.from_schema(s)
    assert orm.entry_id == "KR::UC-CAL-INT-DEF"
    assert orm.concept_id == "UC-CAL-INT-DEF"
    assert orm.country_code == "KR"
    assert orm.subject == "수학"  # S1 — schema default가 mapper 컬럼키 필터로 자동 포함
    assert orm.license_id == "KR-NCIC"  # use_enum_values=True → 하이픈 값 문자열
    assert orm.required_depth == "conceptual"
    assert orm.effective_from == date(2025, 3, 1)
    assert orm.notation_variants == ["∫", "antiderivative"]
    assert orm.is_present is True
    assert float(orm.confidence) == 0.95

    back = orm.to_schema()
    assert back.entry_id == s.entry_id
    assert back.concept_id == s.concept_id
    assert back.country_code == s.country_code
    assert back.subject == "수학"  # S1 — 왕복 보존
    assert back.license_id == s.license_id  # 'KR-NCIC' 값 보존
    assert back.required_depth == s.required_depth
    assert back.effective_from == date(2025, 3, 1)
    assert back.notation_variants == s.notation_variants
    assert back.national_standard_codes == s.national_standard_codes
    assert back.confidence == 0.95


def test_curriculum_entry_roundtrip_absent_cell() -> None:
    """is_present=false인 빈 셀(시점·깊이 필드 없음)도 변환된다(source_url 불요)."""
    now = datetime(2026, 5, 1, tzinfo=timezone.utc)
    s = SchemaCurriculumEntry(
        concept_id="UC-X",
        country_code="JP",
        entry_id="JP::UC-X",
        source_name="学習指導要領",
        license_id=CurriculumLicense.JP_MEXT,
        is_present=False,  # 그 나라에 개념 없음 → source_url 비어도 OK
        confidence=0.6,
        created_at=now,
        updated_at=now,
    )
    orm = OrmCurriculumEntry.from_schema(s)
    assert orm.is_present is False
    assert orm.license_id == "JP-MEXT"

    back = orm.to_schema()  # schema 불변식(is_present=false면 source_url 불요) 재통과
    assert back.is_present is False
    assert back.source_url is None
    assert back.license_id == s.license_id


def test_curriculum_entry_roundtrip_preserves_non_math_subject() -> None:
    """subject='물리' 셀도 왕복 보존(S1 — 개방 str·같은 개념의 물리 교육과정 셀 표현).

    3-튜플 유일성(수학·물리 두 행 공존 + 동일 3-튜플 거부)은 DB 제약이라 실 PG 통합테스트
    (`test_curriculum_entry_subject_migration_integration.py`) 소관 — 여기서는 변환만.
    """
    s = _valid_entry(
        entry_id="KR:물리:UC-VEC",
        concept_id="UC-VEC",
        subject="물리",
    )
    orm = OrmCurriculumEntry.from_schema(s)
    assert orm.subject == "물리"
    back = orm.to_schema()
    assert back.subject == "물리"
