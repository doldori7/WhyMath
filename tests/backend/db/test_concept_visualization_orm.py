"""ConceptVisualization Overlay ORM 단위테스트 — DB 없이 검증 가능한 것만.

시각화 가능성 4분류를 노드 비내장 Overlay로 외부화(ADR concept_node_layering §1·플레이북 Part 5).
메타데이터 등록 / PG DDL 컴파일(visualizability_enum·PK code·NOT NULL) / enum values.
"""

from __future__ import annotations

from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable
from whymath_backend.db.base import Base
from whymath_backend.db.models.concept_visualization import ConceptVisualization


def _pg_ddl(table: object) -> str:
    return str(CreateTable(table).compile(dialect=postgresql.dialect()))  # type: ignore[arg-type]


def test_registered_and_tablename() -> None:
    """Base.metadata에 concept_visualization 테이블이 등록돼 있다(alembic 인식 전제)."""
    assert ConceptVisualization.__tablename__ == "concept_visualization"
    assert "concept_visualization" in set(Base.metadata.tables.keys())


def test_ddl_pk_code_and_visualizability_enum() -> None:
    """DDL: PK code(TEXT)·visualizability_enum·NOT NULL·FK 없음(loose ref·노드 비내장)."""
    ddl = _pg_ddl(ConceptVisualization.__table__)
    assert "visualizability_enum" in ddl
    assert "PRIMARY KEY (code)" in ddl
    assert "REFERENCES" not in ddl  # loose ref — FK 없음(concept_content·curriculum_entry 선례)
    # visualizability는 NOT NULL(행 존재=분류됨).
    assert ConceptVisualization.__table__.c.visualizability.nullable is False


def test_visualizability_enum_values() -> None:
    """visualizability 컬럼 enum이 4분류 값(직접/동적/추상/불가)을 갖는다(Part 5)."""
    col = ConceptVisualization.__table__.c.visualizability
    assert col.type.name == "visualizability_enum"  # type: ignore[attr-defined]
    assert set(col.type.enums) == {"직접", "동적", "부분", "추상"}  # type: ignore[attr-defined]
