"""CurriculumFramework·CurriculumVersion ORM(영속 레이어) 단위테스트 — DB 연결 *없이*.

test_achievement_standard_orm.py·test_curriculum_entry_orm.py 패턴 답습:
메타데이터 등록 / PG DDL 컴파일(PK·FK·UNIQUE·DATE·TIMESTAMPTZ) / from_schema·to_schema 변환
roundtrip / CUR-10 백필 의도(기존 KR 행 → 'KR_NC_2022' framework).

설계 정본: docs/architecture/eos_curriculum_semantic_backbone_adr.md Phase 1 +
whymath_backend/schema/curriculum_framework.py +
whymath_backend/schema/curriculum_version.py.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import uuid4

from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable

from whymath_backend.db.base import Base
from whymath_backend.db.models.achievement_standard import (
    AchievementStandard as OrmAchievementStandard,
)
from whymath_backend.db.models.curriculum_entry import CurriculumEntry as OrmCurriculumEntry
from whymath_backend.db.models.curriculum_framework import (
    CurriculumFramework as OrmCurriculumFramework,
)
from whymath_backend.db.models.curriculum_version import (
    CurriculumVersion as OrmCurriculumVersion,
)
from whymath_backend.schema.curriculum_entry import CurriculumEntry as SchemaCurriculumEntry
from whymath_backend.schema.curriculum_framework import (
    CurriculumFramework as SchemaCurriculumFramework,
)
from whymath_backend.schema.curriculum_version import (
    CurriculumVersion as SchemaCurriculumVersion,
)
from whymath_backend.schema.enums import CurriculumLicense


def _pg_ddl(table: object) -> str:
    """ORM 테이블을 PostgreSQL dialect로 컴파일한 CREATE TABLE 문자열로 반환."""
    return str(CreateTable(table).compile(dialect=postgresql.dialect()))  # type: ignore[arg-type]


def _valid_framework(**overrides: object) -> SchemaCurriculumFramework:
    """유효한 schema.CurriculumFramework(2022 개정 한국 교육과정)."""
    now = datetime(2026, 8, 25, tzinfo=timezone.utc)
    base: dict[str, object] = {
        "framework_id": "KR_NC_2022",
        "authority": "한국 교육부 / 한국교육과정평가원",
        "country": "KR",
        "title": "2022 개정 교육과정",
        "description": "2015 개정 이후 2022년 고시된 한국 교육과정",
        "effective_from": date(2022, 3, 1),
        "status": "published",
        "created_at": now,
        "updated_at": now,
    }
    base.update(overrides)
    return SchemaCurriculumFramework(**base)  # type: ignore[arg-type]


def _valid_version(**overrides: object) -> SchemaCurriculumVersion:
    """유효한 schema.CurriculumVersion(KR_NC_2022 소속 2022_REV_01)."""
    now = datetime(2026, 8, 25, tzinfo=timezone.utc)
    base: dict[str, object] = {
        "version_id": uuid4(),
        "framework_id": "KR_NC_2022",
        "version_label": "2022_REV_01",
        "effective_from": date(2022, 3, 1),
        "status": "published",
        "created_at": now,
        "updated_at": now,
    }
    base.update(overrides)
    return SchemaCurriculumVersion(**base)  # type: ignore[arg-type]


# ──────────────────────────────────────────────────────────────────────────
# 1) 메타데이터 등록
# ──────────────────────────────────────────────────────────────────────────
def test_curriculum_framework_and_version_registered_in_metadata() -> None:
    """Base.metadata에 두 테이블이 등록돼 있다(alembic 인식 전제)."""
    tables = set(Base.metadata.tables.keys())
    assert {"curriculum_framework", "curriculum_version"} <= tables


def test_curriculum_orm_tablenames() -> None:
    """각 ORM의 __tablename__이 마이그레이션 테이블명과 일치한다."""
    assert OrmCurriculumFramework.__tablename__ == "curriculum_framework"
    assert OrmCurriculumVersion.__tablename__ == "curriculum_version"


# ──────────────────────────────────────────────────────────────────────────
# 2) CurriculumFramework PG DDL — 의미 문자열 PK·status server_default
# ──────────────────────────────────────────────────────────────────────────
def test_curriculum_framework_pk_is_framework_id() -> None:
    """PK는 framework_id(의미 문자열, UUID 아님) 단일이다."""
    ddl = _pg_ddl(OrmCurriculumFramework.__table__)
    assert "PRIMARY KEY (framework_id)" in ddl
    pk_cols = [c.name for c in OrmCurriculumFramework.__table__.primary_key.columns]
    assert pk_cols == ["framework_id"]
    assert "gen_random_uuid()" not in ddl  # framework_id는 로더/마이그레이션이 채움


def test_curriculum_framework_status_server_default() -> None:
    """status는 server_default 'published'를 갖는다."""
    default = OrmCurriculumFramework.__table__.c.status.server_default
    assert default is not None
    assert "published" in str(default.arg)


def test_curriculum_framework_lifecycle_columns() -> None:
    """필수/선택 컬럼이 DDL에 존재하고 DATE/TIMESTAMPTZ가 올바르게 매핑된다."""
    ddl = _pg_ddl(OrmCurriculumFramework.__table__)
    cols = {c.name for c in OrmCurriculumFramework.__table__.columns}
    assert {"framework_id", "authority", "country", "title", "description"} <= cols
    assert {"effective_from", "effective_to", "status", "created_at", "updated_at"} <= cols
    assert "DATE" in ddl  # effective_from/effective_to
    assert "TIMESTAMP" in ddl  # created_at/updated_at(timezone=True)


# ──────────────────────────────────────────────────────────────────────────
# 3) CurriculumVersion PG DDL — UUID PK·framework FK·version_label UNIQUE
# ──────────────────────────────────────────────────────────────────────────
def test_curriculum_version_pk_is_uuid() -> None:
    """PK는 version_id(UUID)이고 server_default gen_random_uuid()를 갖는다."""
    ddl = _pg_ddl(OrmCurriculumVersion.__table__)
    assert "PRIMARY KEY (version_id)" in ddl
    assert "gen_random_uuid()" in ddl
    assert "UUID" in ddl


def test_curriculum_version_framework_fk() -> None:
    """framework_id는 curriculum_framework.framework_id 실 FK이다."""
    ddl = _pg_ddl(OrmCurriculumVersion.__table__)
    assert "REFERENCES curriculum_framework (framework_id)" in ddl
    fks = list(OrmCurriculumVersion.__table__.foreign_keys)
    assert len(fks) == 1
    assert fks[0].column.table.name == "curriculum_framework"
    assert fks[0].parent.name == "framework_id"


def test_curriculum_version_unique_framework_label() -> None:
    """동일 framework 내 version_label은 UNIQUE 제약으로 강제된다."""
    ddl = _pg_ddl(OrmCurriculumVersion.__table__)
    assert "UNIQUE (framework_id, version_label)" in ddl
    assert "uq_curriculum_version_framework_label" in ddl


# ──────────────────────────────────────────────────────────────────────────
# 4) 변환 roundtrip
# ──────────────────────────────────────────────────────────────────────────
def test_curriculum_framework_roundtrip_preserves_fields() -> None:
    """schema.CurriculumFramework → ORM → schema가 핵심 필드를 보존."""
    s = _valid_framework(status="approved")
    orm = OrmCurriculumFramework.from_schema(s)
    assert orm.framework_id == "KR_NC_2022"
    assert orm.authority == "한국 교육부 / 한국교육과정평가원"
    assert orm.country == "KR"
    assert orm.title == "2022 개정 교육과정"
    assert orm.description == "2015 개정 이후 2022년 고시된 한국 교육과정"
    assert orm.effective_from == date(2022, 3, 1)
    assert orm.effective_to is None
    assert orm.status == "approved"

    back = orm.to_schema()
    assert back.framework_id == s.framework_id
    assert back.authority == s.authority
    assert back.country == s.country
    assert back.title == s.title
    assert back.description == s.description
    assert back.effective_from == s.effective_from
    assert back.effective_to == s.effective_to
    assert back.status == s.status


def test_curriculum_version_roundtrip_preserves_fields() -> None:
    """schema.CurriculumVersion → ORM → schema가 핵심 필드를 보존."""
    s = _valid_version(source_id="SRC-KR-NC-2022")
    orm = OrmCurriculumVersion.from_schema(s)
    assert orm.version_id == s.version_id
    assert orm.framework_id == "KR_NC_2022"
    assert orm.version_label == "2022_REV_01"
    assert orm.source_id == "SRC-KR-NC-2022"
    assert orm.status == "published"

    back = orm.to_schema()
    assert back.version_id == s.version_id
    assert back.framework_id == s.framework_id
    assert back.version_label == s.version_label
    assert back.source_id == s.source_id


# ──────────────────────────────────────────────────────────────────────────
# 5) CUR-10 연결 — AchievementStandard/CurriculumEntry의 framework_id FK
# ──────────────────────────────────────────────────────────────────────────
def test_achievement_standard_has_framework_id_fk() -> None:
    """AchievementStandard가 CUR-10에서 추가된 nullable framework_id FK를 갖는다."""
    fks = {
        fk.parent.name: fk.column.table.name for fk in OrmAchievementStandard.__table__.foreign_keys
    }
    assert fks.get("framework_id") == "curriculum_framework"
    col = OrmAchievementStandard.__table__.c.framework_id
    assert col.nullable is True
    assert col.type.length == 64  # type: ignore[attr-defined]


def test_curriculum_entry_has_framework_id_fk() -> None:
    """CurriculumEntry가 CUR-10에서 추가된 nullable framework_id FK를 갖는다."""
    fks = {fk.parent.name: fk.column.table.name for fk in OrmCurriculumEntry.__table__.foreign_keys}
    assert fks.get("framework_id") == "curriculum_framework"
    col = OrmCurriculumEntry.__table__.c.framework_id
    assert col.nullable is True


def test_curriculum_entry_schema_framework_id_roundtrip() -> None:
    """schema.CurriculumEntry가 framework_id=None·'KR_NC_2022' 모두 왕복한다."""
    now = datetime(2026, 8, 25, tzinfo=timezone.utc)
    for fw in (None, "KR_NC_2022"):
        s = SchemaCurriculumEntry(
            concept_id="UC-CAL-LIM-DEF",
            country_code="KR",
            entry_id="KR::UC-CAL-LIM-DEF",
            source_name="2022 개정 교육과정",
            license_id=CurriculumLicense.KR_NCIC,
            is_present=True,
            source_url="https://ncic.example/2022",
            confidence=0.95,
            created_at=now,
            updated_at=now,
            framework_id=fw,
        )
        orm = OrmCurriculumEntry.from_schema(s)
        assert orm.framework_id == fw
        back = orm.to_schema()
        assert back.framework_id == fw
