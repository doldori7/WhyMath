"""교육과정 프레임워크 버전(CurriculumVersion) ORM 모델 (SQLAlchemy 2.0).

설계 정본: `docs/architecture/eos_curriculum_semantic_backbone_adr.md` Phase 1.
`schema/curriculum_version.py`와 별도의 영속 매핑이며 `from_schema`/`to_schema`
헬퍼로 둘을 잇는다(standard.py·curriculum_entry.py 동일 패턴).

PK 판단:
  `version_id`는 UUID PK — server_default `gen_random_uuid()`.
  `framework_id`는 FK로 `curriculum_framework.framework_id`를 참조한다.
"""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from whymath_backend.db.base import Base
from whymath_backend.schema.curriculum_version import (
    CurriculumVersion as SchemaCurriculumVersion,
)


class CurriculumVersion(Base):
    """교육과정 프레임워크 버전 영속 ORM."""

    __tablename__ = "curriculum_version"

    version_id: Mapped[UUID] = mapped_column(
        sa.Uuid, primary_key=True, server_default=sa.text("gen_random_uuid()")
    )
    framework_id: Mapped[str] = mapped_column(
        sa.String(64),
        sa.ForeignKey("curriculum_framework.framework_id"),
        nullable=False,
    )
    version_label: Mapped[str] = mapped_column(sa.String, nullable=False)

    effective_from: Mapped[date | None] = mapped_column(sa.Date)
    effective_to: Mapped[date | None] = mapped_column(sa.Date)
    status: Mapped[str] = mapped_column(
        sa.String(30), nullable=False, server_default=sa.text("'published'")
    )

    source_id: Mapped[str | None] = mapped_column(sa.String)

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)

    # ── 제약 (동일 framework 내 version_label 유일성) ─────────────────────
    __table_args__ = (
        sa.UniqueConstraint(
            "framework_id", "version_label", name="uq_curriculum_version_framework_label"
        ),
    )

    # ── 변환 헬퍼 ────────────────────────────────────────────────────────
    @classmethod
    def from_schema(cls, schema: SchemaCurriculumVersion) -> CurriculumVersion:
        """검증된 schema → ORM."""
        data = schema.model_dump()
        mapped_keys = {col.key for col in sa.inspect(cls).mapper.column_attrs}
        kwargs = {k: v for k, v in data.items() if k in mapped_keys}
        return cls(**kwargs)

    def to_schema(self) -> SchemaCurriculumVersion:
        """ORM → schema."""
        mapped_keys = {col.key for col in sa.inspect(type(self)).mapper.column_attrs}
        data = {key: getattr(self, key) for key in mapped_keys}
        return SchemaCurriculumVersion.model_validate(data)


__all__ = ["CurriculumVersion"]
