"""GDPR 삭제 감사(DeletionAudit) ORM 모델 — slice 57.

본인 데이터 삭제(`DELETE /v1/me/{sessions,dialogues,assessments}/{id}`, slice 51~53) 시 *부모
리소스 삭제 이벤트*를 append-only로 기록한다 — GDPR 삭제권 이행의 *증빙*(언제·누가·무엇을
지웠는가). 삭제된 **콘텐츠 자체는 저장하지 않는다**(메타데이터만: 도메인·id·시각·소유자
UUID) — 미성년 PII 비저촉(CLAUDE.md). 자식(cascade·slice 56)은 DB 레벨이라 비가시 → 부모만
기록(개별 자식 감사는 앱레벨 명시 삭제 필요·후속).

설계 결정:
  - `user_id`는 **FK 아님**(plain UUID) — 사용자 프로필이 삭제돼도 감사 로그는 *잔존*해야
    하므로(FK CASCADE/RESTRICT 어느 쪽도 부적합). compliance 로그의 독립성.
  - `resource_type`은 `sa.String(32)`(네이티브 PG enum 미생성) — 코드 안전성은 Pydantic
    `AuditResourceType`(.value 저장)으로 확보, DB는 단순 문자열(감사 메타 태그).
  - append-only — UPDATE/DELETE 라우터 없음. 읽기는 slice 58 `GET /v1/me/deletions`(본인 스코핑).
"""

from __future__ import annotations

import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from whymath_backend.db.base import Base
from whymath_backend.schema.audit import DeletionAudit as SchemaDeletionAudit


class DeletionAudit(Base):
    """GDPR 삭제 감사 1행 — 한 번의 본인 리소스 삭제 이벤트."""

    __tablename__ = "deletion_audit"

    audit_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid,
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    # FK 아님(plain UUID) — 사용자 삭제돼도 감사 잔존(설계 메모 참조).
    user_id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, nullable=False)
    resource_type: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    resource_id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, nullable=False)
    deleted_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
    )

    # ── 변환 헬퍼 (schema↔db seam, activity.py 패턴) — slice 58 조회 API용 ──
    @classmethod
    def from_schema(cls, schema: SchemaDeletionAudit) -> DeletionAudit:
        """검증된 `schema.DeletionAudit` → 영속 ORM(mapper 컬럼키 필터)."""
        data = schema.model_dump()
        mapped_keys = {col.key for col in sa.inspect(cls).mapper.column_attrs}
        kwargs = {k: v for k, v in data.items() if k in mapped_keys}
        return cls(**kwargs)

    def to_schema(self) -> SchemaDeletionAudit:
        """영속 ORM → `schema.DeletionAudit`(Pydantic 검증 복원)."""
        mapped_keys = {col.key for col in sa.inspect(type(self)).mapper.column_attrs}
        data = {key: getattr(self, key) for key in mapped_keys}
        return SchemaDeletionAudit.model_validate(data)
