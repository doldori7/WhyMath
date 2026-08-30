"""Provenance ORM(영속 레이어) 단위테스트 — DB 연결 *없이* 검증 가능한 것만.

problem ORM 테스트 패턴 답습: 메타데이터 등록 / PG DDL 컴파일(JSONB·enum·gen_random_uuid·
NUMERIC) / enum values_callable / schema↔ORM 변환 roundtrip(법적 불변식 안전망 포함).

설계 정본: schemas/v1.0/schema_v1.0.md §10.1.
"""

from __future__ import annotations

import uuid

from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable

from whymath_backend.db.base import Base
from whymath_backend.db.models.provenance import (
    ContentProvenance as OrmContentProvenance,
)
from whymath_backend.db.models.provenance import (
    GenerationLog as OrmGenerationLog,
)
from whymath_backend.schema.enums import GenerationType, LicenseType, SourceType
from whymath_backend.schema.provenance import (
    ContentProvenance as SchemaContentProvenance,
)
from whymath_backend.schema.provenance import (
    GenerationLog as SchemaGenerationLog,
)


def _pg_ddl(table: object) -> str:
    """ORM 테이블을 PostgreSQL dialect로 컴파일한 CREATE TABLE 문자열로 반환."""
    return str(CreateTable(table).compile(dialect=postgresql.dialect()))  # type: ignore[arg-type]


# ──────────────────────────────────────────────────────────────────────────
# 1) 메타데이터 등록
# ──────────────────────────────────────────────────────────────────────────
def test_provenance_tables_registered_in_metadata() -> None:
    """Base.metadata에 도메인8 두 테이블이 등록돼 있다(alembic 인식 전제)."""
    tables = set(Base.metadata.tables.keys())
    assert {"content_provenance", "generation_log"} <= tables


def test_provenance_orm_tablenames() -> None:
    """각 ORM의 __tablename__이 §10.1 DDL 테이블명과 일치한다."""
    assert OrmContentProvenance.__tablename__ == "content_provenance"
    assert OrmGenerationLog.__tablename__ == "generation_log"


# ──────────────────────────────────────────────────────────────────────────
# 2) PG DDL 컴파일
# ──────────────────────────────────────────────────────────────────────────
def test_content_provenance_ddl_compiles() -> None:
    """ContentProvenance DDL에 JSONB·source_type_enum·license_enum
    ·generation_type_enum·UUID 포함."""
    ddl = _pg_ddl(OrmContentProvenance.__table__)
    assert "JSONB" in ddl  # original_reference·transformation 등
    assert "source_type_enum" in ddl  # original_source (problem과 enum 타입 공유)
    assert "license_enum" in ddl
    assert "generation_type_enum" in ddl
    assert "gen_random_uuid()" in ddl


def test_content_provenance_fk_to_problem() -> None:
    """problem_id·parent_problem_id는 problem FK, approved_by는 FK 아님(plain UUID)."""
    ddl = _pg_ddl(OrmContentProvenance.__table__)
    assert "REFERENCES problem" in ddl
    # approved_by는 DDL에 REFERENCES가 없으므로 FK 개수는 problem_id·parent_problem_id 2개뿐.
    fk_targets = {fk.column.table.name for fk in OrmContentProvenance.__table__.foreign_keys}
    assert fk_targets == {"problem"}
    assert len(OrmContentProvenance.__table__.foreign_keys) == 2


def test_generation_log_ddl_numeric_and_fk() -> None:
    """generation_log: cost_usd NUMERIC(8,4)·problem/provenance FK·gen_random_uuid."""
    ddl = _pg_ddl(OrmGenerationLog.__table__)
    assert "NUMERIC(8, 4)" in ddl  # cost_usd DECIMAL(8,4)
    assert "REFERENCES problem" in ddl
    assert "REFERENCES content_provenance" in ddl
    assert "gen_random_uuid()" in ddl
    # prompt_template_id는 FK 아님 → FK는 problem·content_provenance 2개.
    assert len(OrmGenerationLog.__table__.foreign_keys) == 2


# ──────────────────────────────────────────────────────────────────────────
# 3) enum values_callable
# ──────────────────────────────────────────────────────────────────────────
def test_provenance_enum_values() -> None:
    """license·generation_type·original_source enum이 값을 갖는다(멤버명=값)."""
    lic = OrmContentProvenance.__table__.c.license.type.enums  # type: ignore[attr-defined]
    assert "WHYMATH_GENERATED" in lic
    gen = OrmContentProvenance.__table__.c.generation_type.type.enums  # type: ignore[attr-defined]
    assert "FULLY_GENERATED" in gen
    src = OrmContentProvenance.__table__.c.original_source.type.enums  # type: ignore[attr-defined]
    assert "평가원" in src


# ──────────────────────────────────────────────────────────────────────────
# 4) 변환 roundtrip (법적 불변식 안전망 포함)
# ──────────────────────────────────────────────────────────────────────────
def test_content_provenance_roundtrip_self_generated() -> None:
    """자체생성 경로 ContentProvenance schema↔ORM 변환이 핵심 필드를 보존한다."""
    pid = uuid.uuid4()
    s = SchemaContentProvenance(
        problem_id=pid,
        generation_type=GenerationType.FULLY_GENERATED,
        license=LicenseType.WHYMATH_GENERATED,
        original_reference={"year": 2025, "exam": "수능", "number": 30},
        transformation={"operations": [{"type": "swap_numbers", "from": 3, "to": 5}]},
    )
    orm = OrmContentProvenance.from_schema(s)
    assert orm.problem_id == pid
    assert orm.generation_type == "FULLY_GENERATED"
    assert orm.license == "WHYMATH_GENERATED"
    assert orm.original_reference == {"year": 2025, "exam": "수능", "number": 30}

    back = orm.to_schema()
    assert back.problem_id == pid
    assert back.generation_type == s.generation_type
    assert back.license == s.license
    assert back.transformation == s.transformation


def test_content_provenance_roundtrip_metadata_only_source() -> None:
    """메타 전용 출처(평가원) + WHYMATH_GENERATED + 변형 경로가 법적 불변식을 통과해 복원된다.

    to_schema가 schema.ContentProvenance 법적 validator((C-1)·(C-2)·(C-3))를 재차 통과하는지
    확인 — 메타 전용 출처는 WHYMATH_GENERATED·변형류·구조 메타 only여야 정상 복원된다.
    """
    s = SchemaContentProvenance(
        original_source=SourceType.평가원,
        license=LicenseType.WHYMATH_GENERATED,
        generation_type=GenerationType.VARIANT_NUMBER,
        original_reference={"year": 2025, "number": 30},  # 구조 메타만(본문성 키 없음)
    )
    orm = OrmContentProvenance.from_schema(s)
    assert orm.original_source == "평가원"

    back = orm.to_schema()  # 법적 불변식 재통과(예외 없이 복원)
    assert back.original_source == s.original_source
    assert back.license == s.license
    assert back.generation_type == s.generation_type


def test_generation_log_roundtrip() -> None:
    """GenerationLog schema↔ORM 변환이 비용·토큰·모델명을 보존한다."""
    pid = uuid.uuid4()
    s = SchemaGenerationLog(
        problem_id=pid,
        model_name="qwen3-32b",
        input_tokens=1200,
        output_tokens=800,
        cost_usd=0.0123,
        latency_ms=4500,
        success=True,
    )
    orm = OrmGenerationLog.from_schema(s)
    assert orm.problem_id == pid
    assert orm.model_name == "qwen3-32b"
    assert float(orm.cost_usd) == 0.0123

    back = orm.to_schema()
    assert back.problem_id == pid
    assert back.model_name == s.model_name
    assert back.input_tokens == s.input_tokens
    assert back.success is True


# ──────────────────────────────────────────────────────────────────────────
# 5) EOS-55 재현 좌석 — DDL·roundtrip·복원 계약 (acceptance ①·②의 영속측)
# ──────────────────────────────────────────────────────────────────────────
def test_generation_log_ddl_reproducibility_seats() -> None:
    """재현 좌석 4컬럼(prompt_version·seed·input_sha256·input_snapshot) DDL 계약.

    전부 nullable(구 행 NULL=미기록)·server_default 없음(날조 금지) — alembic
    f4b2d8c1a3e5와 1:1.
    """
    table = OrmGenerationLog.__table__
    ddl = _pg_ddl(table)
    assert "prompt_version VARCHAR(128)" in ddl
    assert "seed BIGINT" in ddl
    assert "input_sha256 VARCHAR(64)" in ddl
    assert "input_snapshot JSONB" in ddl
    for name in ("prompt_version", "seed", "input_sha256", "input_snapshot"):
        column = table.c[name]
        assert column.nullable, f"{name}은 nullable이어야 한다(구 행 NULL=미기록)"
        assert column.server_default is None, f"{name}에 server_default 금지(날조 금지)"


def test_generation_log_reproducibility_roundtrip_and_restore() -> None:
    """재현 필드 schema↔ORM 왕복 보존 + **왕복한 레코드만으로 입력 복원**(재현 계약 영속측).

    to_schema는 model_validate를 다시 지나므로 스냅샷↔해시 봉인도 재통과한다 — DB에서
    읽은 레코드가 복원 가능함을 동결한다(EOS-55 acceptance ②).
    """
    from whymath_backend.schema.provenance import (
        input_snapshot_sha256,
        restore_input_snapshot,
    )

    snapshot = {
        "kind": "l3.pregenerate.prewarm",
        "prompt_sha256": "a" * 64,
        "system_sha256": "b" * 64,
        "request": {"task_type": "explain", "difficulty": "easy", "sync": True},
    }
    s = SchemaGenerationLog(
        model_name="qwen2-math:1.5b",
        prompt_version="l3.equivalent@sha256:abc123def456",
        seed=None,  # 현행 경로 seed 미사용(실측) — NULL=미기록
        input_snapshot=snapshot,
    )
    assert s.input_sha256 == input_snapshot_sha256(snapshot)  # 쓰기측 자동 봉인

    orm = OrmGenerationLog.from_schema(s)
    assert orm.prompt_version == "l3.equivalent@sha256:abc123def456"
    assert orm.seed is None
    assert orm.input_sha256 == s.input_sha256
    assert orm.input_snapshot == snapshot

    back = orm.to_schema()  # 무결성 validator 재통과(예외 없이 복원)
    assert back.prompt_version == s.prompt_version
    assert back.seed is None
    assert back.input_sha256 == s.input_sha256
    # 재현 계약 본체: 왕복한 레코드만 보고 동일 입력 복원 + 해시 재계산 일치.
    restored = restore_input_snapshot(back)
    assert restored == snapshot
    assert input_snapshot_sha256(restored) == back.input_sha256


def test_generation_log_seed_roundtrip_when_used() -> None:
    """seed가 *실제로 쓰인* 미래 경로의 값 왕복 — 좌석 실재 계약(int64 폭)."""
    s = SchemaGenerationLog(model_name="qwen2.5:7b", seed=2**53 + 7)
    orm = OrmGenerationLog.from_schema(s)
    assert orm.seed == 2**53 + 7
    assert orm.to_schema().seed == 2**53 + 7
