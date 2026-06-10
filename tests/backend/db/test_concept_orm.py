"""Concept ORM(영속 레이어) 단위테스트 — DB 연결 *없이* 검증 가능한 것만.

problem ORM 테스트(`test_problem_orm.py`) 패턴 답습: 메타데이터 등록 / PG DDL 컴파일
(JSONB·enum 타입명·gen_random_uuid) / enum values_callable / schema↔ORM 변환 roundtrip.
실제 PG 적용은 메인의 실 PG 통합검증에서 확인한다.

설계 정본: schemas/v1.0/schema_v1.0.md §4.2.
"""

from __future__ import annotations

import uuid

from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable

from whymath_backend.db.base import Base
from whymath_backend.db.models.concept import (
    Concept as OrmConcept,
)
from whymath_backend.db.models.concept import (
    ConceptEdge as OrmConceptEdge,
)
from whymath_backend.db.models.concept import (
    ConceptFusion as OrmConceptFusion,
)
from whymath_backend.db.models.concept import (
    ProblemConcept as OrmProblemConcept,
)
from whymath_backend.schema.concept import (
    Concept as SchemaConcept,
)
from whymath_backend.schema.concept import (
    ConceptEdge as SchemaConceptEdge,
)
from whymath_backend.schema.concept import (
    ConceptFusion as SchemaConceptFusion,
)
from whymath_backend.schema.concept import (
    ProblemConcept as SchemaProblemConcept,
)
from whymath_backend.schema.enums import (
    CognitiveType,
    ConceptLevel,
    ConceptRole,
    EdgeType,
    Subject,
)


def _pg_ddl(table: object) -> str:
    """ORM 테이블을 PostgreSQL dialect로 컴파일한 CREATE TABLE 문자열로 반환."""
    return str(CreateTable(table).compile(dialect=postgresql.dialect()))  # type: ignore[arg-type]


# ──────────────────────────────────────────────────────────────────────────
# 1) 메타데이터 등록
# ──────────────────────────────────────────────────────────────────────────
def test_concept_tables_registered_in_metadata() -> None:
    """Base.metadata에 도메인2 네 테이블이 등록돼 있다(alembic 인식 전제)."""
    tables = set(Base.metadata.tables.keys())
    assert {"concept", "concept_edge", "problem_concept", "concept_fusion"} <= tables


def test_concept_orm_tablenames() -> None:
    """각 ORM의 __tablename__이 §4.2 DDL 테이블명과 일치한다."""
    assert OrmConcept.__tablename__ == "concept"
    assert OrmConceptEdge.__tablename__ == "concept_edge"
    assert OrmProblemConcept.__tablename__ == "problem_concept"
    assert OrmConceptFusion.__tablename__ == "concept_fusion"


# ──────────────────────────────────────────────────────────────────────────
# 2) PG DDL 컴파일
# ──────────────────────────────────────────────────────────────────────────
def test_concept_ddl_compiles_to_postgres() -> None:
    """Concept DDL에 JSONB·concept_level_enum·cognitive_type_enum·visualization_style_enum·
    gen_random_uuid()·UUID 포함."""
    ddl = _pg_ddl(OrmConcept.__table__)
    assert "JSONB" in ddl  # common_misconceptions
    assert "concept_level_enum" in ddl  # level
    assert "cognitive_type_enum" in ddl  # cognitive_type[] (enum 배열)
    assert (
        "visualization_style_enum" in ddl
    )  # recommended_visual_styles[] (슬라이스 88)
    assert "gen_random_uuid()" in ddl
    assert "UUID" in ddl


def test_concept_self_fk_and_unique_code() -> None:
    """concept의 self-FK(parent_concept_id→concept)·code UNIQUE가 DDL에 반영된다."""
    ddl = _pg_ddl(OrmConcept.__table__)
    assert "FOREIGN KEY(parent_concept_id) REFERENCES concept" in ddl
    assert "UNIQUE" in ddl  # code UNIQUE


def test_concept_edge_ddl_unique_and_fk() -> None:
    """concept_edge: from/to→concept FK·edge_type_enum·복합 UNIQUE가 DDL에 반영된다."""
    ddl = _pg_ddl(OrmConceptEdge.__table__)
    assert "edge_type_enum" in ddl
    assert "REFERENCES concept" in ddl
    # UNIQUE(from_concept_id, to_concept_id, edge_type)
    assert "UNIQUE" in ddl


def test_problem_concept_composite_pk_cross_table_fk() -> None:
    """problem_concept: 복합 PK(problem_id·concept_id·role) + problem/concept 양쪽 FK."""
    ddl = _pg_ddl(OrmProblemConcept.__table__)
    assert "PRIMARY KEY (problem_id, concept_id, role)" in ddl
    assert "concept_role_enum" in ddl
    assert "REFERENCES problem" in ddl  # problem_id → 메인의 problem 테이블
    assert "REFERENCES concept" in ddl  # concept_id → 이 배치의 concept 테이블


def test_concept_fusion_uuid_arrays_not_fk() -> None:
    """concept_fusion: concept_ids/exemplar_problem_ids는 UUID[](배열)이라 FK가 아니다."""
    ddl = _pg_ddl(OrmConceptFusion.__table__)
    assert "UUID[]" in ddl
    # 배열 컬럼은 FK가 아니므로 concept_fusion에는 REFERENCES가 없어야 한다.
    assert "REFERENCES" not in ddl
    # concept_ids NOT NULL 배열은 server_default로 빈 배열.
    assert len(OrmConceptFusion.__table__.foreign_keys) == 0


# ──────────────────────────────────────────────────────────────────────────
# 3) enum values_callable
# ──────────────────────────────────────────────────────────────────────────
def test_concept_level_enum_values() -> None:
    """level 컬럼의 PG enum이 한글 값('단원' 등)을 갖는다(멤버명=값 케이스)."""
    enums = OrmConcept.__table__.c.level.type.enums  # type: ignore[attr-defined]
    assert "단원" in enums
    assert "세부개념" in enums


def test_cognitive_type_array_enum_values() -> None:
    """cognitive_type[] 원소 enum이 값('THEOREM' 등)을 갖는다."""
    item_type = OrmConcept.__table__.c.cognitive_type.type.item_type  # type: ignore[attr-defined]
    assert "THEOREM" in item_type.enums
    assert "VISUAL_REASONING" in item_type.enums


def test_recommended_visual_styles_array_enum_values() -> None:
    """recommended_visual_styles[] 원소 enum이 값('단위원'·'수형도' 등)을 갖는다(슬라이스 88)."""
    col = OrmConcept.__table__.c.recommended_visual_styles
    item_type = col.type.item_type  # type: ignore[attr-defined]
    assert item_type.name == "visualization_style_enum"
    assert "단위원" in item_type.enums
    assert "수형도" in item_type.enums


# ──────────────────────────────────────────────────────────────────────────
# 4) 변환 roundtrip
# ──────────────────────────────────────────────────────────────────────────
def test_concept_roundtrip_preserves_core_fields() -> None:
    """schema.Concept → ORM → schema가 핵심 필드(id·code·계층·인지유형·오개념)를 보존."""
    cid = uuid.uuid4()
    s = SchemaConcept(
        concept_id=cid,
        code="CAL-INT-DEF-FUNDAMENTAL",
        name_ko="미적분학의 기본정리",
        name_en="Fundamental Theorem of Calculus",
        level=ConceptLevel.세부개념,
        subject=Subject.미적분,
        cognitive_type=[CognitiveType.THEOREM, CognitiveType.TECHNIQUE],
        common_misconceptions=[
            {"misconception": "정적분=넓이", "correction": "부호 있는 넓이"}
        ],
        aliases=["FTC"],
    )
    orm = OrmConcept.from_schema(s)
    # ORM 단계 보존(use_enum_values=True → enum은 문자열 값).
    assert orm.concept_id == cid
    assert orm.code == "CAL-INT-DEF-FUNDAMENTAL"
    assert orm.level == "세부개념"
    assert orm.cognitive_type == ["THEOREM", "TECHNIQUE"]
    assert orm.common_misconceptions == [
        {"misconception": "정적분=넓이", "correction": "부호 있는 넓이"}
    ]

    back = orm.to_schema()
    assert back.concept_id == cid
    assert back.code == s.code
    assert back.level == s.level
    assert back.cognitive_type == s.cognitive_type
    assert back.common_misconceptions == s.common_misconceptions
    assert back.aliases == s.aliases


def test_concept_edge_roundtrip() -> None:
    """ConceptEdge schema↔ORM 변환이 FK·관계유형을 보존한다."""
    a, b = uuid.uuid4(), uuid.uuid4()
    s = SchemaConceptEdge(
        from_concept_id=a,
        to_concept_id=b,
        edge_type=EdgeType.PREREQUISITE,
        edge_strength=0.9,
        typical_gap_signal="A를 모르면 B가 막힌다",
    )
    orm = OrmConceptEdge.from_schema(s)
    assert orm.from_concept_id == a
    assert orm.to_concept_id == b
    assert orm.edge_type == "PREREQUISITE"

    back = orm.to_schema()
    assert back.from_concept_id == a
    assert back.to_concept_id == b
    assert back.edge_type == s.edge_type
    assert back.edge_strength == s.edge_strength


def test_problem_concept_roundtrip() -> None:
    """ProblemConcept schema↔ORM 변환이 복합키·역할을 보존한다."""
    pid, cid = uuid.uuid4(), uuid.uuid4()
    s = SchemaProblemConcept(
        problem_id=pid,
        concept_id=cid,
        relevance=0.8,
        role=ConceptRole.PRIMARY,
    )
    orm = OrmProblemConcept.from_schema(s)
    assert orm.problem_id == pid
    assert orm.concept_id == cid
    assert orm.role == "PRIMARY"

    back = orm.to_schema()
    assert back.problem_id == pid
    assert back.concept_id == cid
    assert back.role == s.role


def test_concept_fusion_roundtrip_uuid_arrays() -> None:
    """ConceptFusion schema↔ORM 변환이 UUID[] 배열(FK 아님)을 보존한다."""
    fid = uuid.uuid4()
    c1, c2 = uuid.uuid4(), uuid.uuid4()
    ex1 = uuid.uuid4()
    s = SchemaConceptFusion(
        fusion_id=fid,
        name="수열의 극한 + 부등식",
        concept_ids=[c1, c2],
        fusion_difficulty=4.5,
        exemplar_problem_ids=[ex1],
    )
    orm = OrmConceptFusion.from_schema(s)
    assert orm.fusion_id == fid
    assert orm.concept_ids == [c1, c2]
    assert orm.exemplar_problem_ids == [ex1]

    back = orm.to_schema()
    assert back.fusion_id == fid
    assert back.concept_ids == [c1, c2]
    assert back.exemplar_problem_ids == [ex1]
    assert back.name == s.name
