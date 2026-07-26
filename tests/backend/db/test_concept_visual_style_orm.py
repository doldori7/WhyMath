"""ConceptVisualStyle Overlay ORM 단위테스트 — DB 없이 검증 가능한 것만 (슬88·ARCH-14 ③).

권장 시각화 양식을 노드 비내장 Overlay로 외부화(Concept Purity 마지막 부채 청산·ADR
concept_node_layering §1·`concept_visualization` Overlay 선례). 메타데이터 등록 / PG DDL 컴파일
(visualization_style_enum[]·PK code·NOT NULL·FK 없음) / 원소 enum 값.
"""

from __future__ import annotations

from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable

from whymath_backend.db.base import Base
from whymath_backend.db.models.concept_visual_style import ConceptVisualStyle


def _pg_ddl(table: object) -> str:
    return str(CreateTable(table).compile(dialect=postgresql.dialect()))  # type: ignore[arg-type]


def test_registered_and_tablename() -> None:
    """Base.metadata에 concept_visual_style 테이블이 등록돼 있다(alembic 인식 전제)."""
    assert ConceptVisualStyle.__tablename__ == "concept_visual_style"
    assert "concept_visual_style" in set(Base.metadata.tables.keys())


def test_ddl_pk_code_and_visualization_style_enum() -> None:
    """DDL: PK code(TEXT)·visualization_style_enum[]·NOT NULL·FK 없음(loose ref·노드 비내장)."""
    ddl = _pg_ddl(ConceptVisualStyle.__table__)
    assert "visualization_style_enum" in ddl
    assert "PRIMARY KEY (code)" in ddl
    assert "REFERENCES" not in ddl  # loose ref — FK 없음(concept_visualization 선례)
    # recommended_styles는 NOT NULL(행 존재=양식 태깅됨).
    assert ConceptVisualStyle.__table__.c.recommended_styles.nullable is False


def test_recommended_styles_array_enum_values() -> None:
    """recommended_styles[] 원소 enum이 값('단위원'·'수형도' 등)을 갖는다(슬88 통제 어휘)."""
    col = ConceptVisualStyle.__table__.c.recommended_styles
    item_type = col.type.item_type  # type: ignore[attr-defined]
    assert item_type.name == "visualization_style_enum"
    assert "단위원" in item_type.enums
    assert "수형도" in item_type.enums
