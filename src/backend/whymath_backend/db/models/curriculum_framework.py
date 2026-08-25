"""교육과정 프레임워크(CurriculumFramework) ORM 모델 (SQLAlchemy 2.0).

설계 정본: `docs/architecture/eos_curriculum_semantic_backbone_adr.md` Phase 1.
`schema/curriculum_framework.py`와 별도의 영속 매핑이며 `from_schema`/`to_schema`
헬퍼로 둘을 잇는다(standard.py·curriculum_entry.py 동일 패턴).

PK 판단:
  `framework_id`는 의미 문자열 PK. UUID가 아니므로 `gen_random_uuid()` server_default가
  없다 — 로더/마이그레이션이 채운다(AchievementStandard.norm_id, CurriculumEntry.entry_id
  선례).
"""

from __future__ import annotations

from datetime import date, datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from whymath_backend.db.base import Base
from whymath_backend.schema.curriculum_framework import (
    CurriculumFramework as SchemaCurriculumFramework,
)


class CurriculumFramework(Base):
    """교육과정 프레임워크 영속 ORM."""

    __tablename__ = "curriculum_framework"

    framework_id: Mapped[str] = mapped_column(sa.String(64), primary_key=True)
    authority: Mapped[str] = mapped_column(sa.String, nullable=False)
    country: Mapped[str] = mapped_column(sa.String(16), nullable=False)
    title: Mapped[str] = mapped_column(sa.String, nullable=False)
    description: Mapped[str | None] = mapped_column(sa.Text)

    effective_from: Mapped[date | None] = mapped_column(sa.Date)
    effective_to: Mapped[date | None] = mapped_column(sa.Date)
    status: Mapped[str] = mapped_column(
        sa.String(30), nullable=False, server_default=sa.text("'published'")
    )

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)

    # ── 변환 헬퍼 ────────────────────────────────────────────────────────
    @classmethod
    def from_schema(cls, schema: SchemaCurriculumFramework) -> CurriculumFramework:
        """검증된 schema → ORM."""
        data = schema.model_dump()
        mapped_keys = {col.key for col in sa.inspect(cls).mapper.column_attrs}
        kwargs = {k: v for k, v in data.items() if k in mapped_keys}
        return cls(**kwargs)

    def to_schema(self) -> SchemaCurriculumFramework:
        """ORM → schema."""
        mapped_keys = {col.key for col in sa.inspect(type(self)).mapper.column_attrs}
        data = {key: getattr(self, key) for key in mapped_keys}
        return SchemaCurriculumFramework.model_validate(data)


__all__ = ["CurriculumFramework"]
