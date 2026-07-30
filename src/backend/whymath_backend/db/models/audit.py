"""감사(audit) ORM 모델 — `DeletionAudit`(slice 57) + `PrivacyAudit`(SEC-09).

본인 데이터 삭제(`DELETE /v1/me/{sessions,dialogues,assessments}/{id}`, slice 51~53) 시 *부모
리소스 삭제 이벤트*를 append-only로 기록한다 — GDPR 삭제권 이행의 *증빙*(언제·누가·무엇을
지웠는가). 삭제된 **콘텐츠 자체는 저장하지 않는다**(메타데이터만: 도메인·id·시각·소유자
UUID) — 미성년 PII 비저촉(CLAUDE.md). 자식(cascade·slice 56)은 DB 레벨이라 비가시 → 부모만
기록(개별 자식 감사는 앱레벨 명시 삭제 필요·후속).

설계 결정(`DeletionAudit`):
  - `user_id`는 **FK 아님**(plain UUID) — 사용자 프로필이 삭제돼도 감사 로그는 *잔존*해야
    하므로(FK CASCADE/RESTRICT 어느 쪽도 부적합). compliance 로그의 독립성.
  - `resource_type`은 `sa.String(32)`(네이티브 PG enum 미생성) — 코드 안전성은 Pydantic
    `AuditResourceType`(.value 저장)으로 확보, DB는 단순 문자열(감사 메타 태그).
  - append-only — UPDATE/DELETE 라우터 없음. 읽기는 slice 58 `GET /v1/me/deletions`(본인 스코핑).

`PrivacyAudit`(SEC-09)은 개인정보 감사 3종(반출·동의변경·관리자접근)의 append-only 기록이다 —
`docs/architecture/account_security_gap_review.md` D3의 경계 확정(본인 조회 29개 엔드포인트
전수 감사는 *하지 않는다*)에 따라 "시스템 밖으로 나가는 사건"·"본인 아닌 주체의 접근"만
기록한다. `DeletionAudit`의 append-only·plain-UUID·String(32) 패턴을 그대로 답습하되
**삭제 이벤트는 중복 기록하지 않는다**(`deletion_audit`가 삭제 감사의 단일 권위 — 이중
진실원천 금지).
"""

from __future__ import annotations

import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from whymath_backend.db.base import Base
from whymath_backend.schema.audit import DeletionAudit as SchemaDeletionAudit
from whymath_backend.schema.audit import PrivacyAudit as SchemaPrivacyAudit


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

    # slice 60: list_my_deletions(user_id 필터·deleted_at desc 정렬) 접근 패턴 인덱스 —
    # learning_session.idx_session_user·dialogue.idx_dialogue_user와 동형(parity).
    __table_args__ = (sa.Index("idx_deletion_audit_user", "user_id", sa.desc("deleted_at")),)

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


class PrivacyAudit(Base):
    """SEC-09 개인정보 감사 1행 — 반출·동의변경·관리자접근 3종 중 1건의 append-only 기록.

    `user_id`는 **행위자**(action을 수행한 주체)다 — 본인 반출·동의변경이면 본인, 관리자접근
    이면 그 관리자. `target_user_id`는 *행위자와 다른 사용자의 데이터가 대상일 때만* 채운다
    (관리자접근이 자기 아닌 학생의 데이터를 봤을 때 그 학생 id) — 본인 행위(반출·동의변경)는
    행위자==대상이라 중복 저장하지 않고 NULL로 둔다(현재 admin_access 호출부 0곳이라 실제로는
    항상 NULL — `AuditEventKind.admin_access` docstring 참조).

    `consent_scope`는 `event_kind=consent_change`일 때만 채우는 *유일한* 구분 메타데이터
    (어떤 동의 범위가 바뀌었는지) — 그 외 이벤트는 NULL. 자유텍스트 필드는 두지 않는다(감사
    행이 PII를 우연히 담는 사고 방지 — CLAUDE.md 미성년 PII 보호).

    설계 결정(DeletionAudit 패턴 답습 — `docs/architecture/account_security_gap_review.md` D3):
      - `user_id`/`target_user_id` 둘 다 **FK 아님**(plain UUID) — 계정 삭제 후에도 감사 잔존.
      - `event_kind`는 `sa.String(32)`(네이티브 PG enum 미생성) — Pydantic `AuditEventKind`
        (.value 저장)로 코드 안전성 확보, DB는 단순 문자열(AuditResourceType 선례).
      - `ip_hash`는 `sa.String(64)`(sha256 hex) **nullable** — salt 미설정(개발·CI)이면
        `privacy.audit.hash_client_ip`가 None을 반환해도 감사 행 자체는 적재된다(주행위를
        막지 않기 위해 — config.py `pii_audit_ip_salt` 설명 참조). 평문 IP는 어떤 컬럼에도
        저장하지 않는다.
      - append-only — UPDATE/DELETE 라우터 없음. 읽기는 `GET /v1/me/privacy-audit`(본인 스코핑
        — `user_id`로 필터, `DeletionAudit`/`GET /v1/me/deletions` 패턴 답습).
      - **삭제 이벤트는 여기 적재하지 않는다** — `deletion_audit`가 단일 권위(이중 진실원천
        금지). `api/me.py:291`의 `_delete_owned_resource`도 `erase_my_account`도 이 테이블에
        쓰지 않는다(회귀 테스트로 동결 — `tests/backend/api/test_privacy_audit.py`).
    """

    __tablename__ = "privacy_audit"

    audit_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid,
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    # FK 아님(plain UUID) — 사용자 삭제돼도 감사 잔존(DeletionAudit 설계 메모 참조).
    user_id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, nullable=False)
    target_user_id: Mapped[uuid.UUID | None] = mapped_column(sa.Uuid, nullable=True)
    event_kind: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    consent_scope: Mapped[str | None] = mapped_column(sa.String(32), nullable=True)
    ip_hash: Mapped[str | None] = mapped_column(sa.String(64), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
    )

    # `GET /v1/me/privacy-audit`(user_id 필터·occurred_at desc 정렬) 접근 패턴 인덱스 —
    # idx_deletion_audit_user와 동형(parity). target_user_id는 admin_access 호출부가 생길 때
    # 실 쿼리 부하로 다시 판단(현재 0행이라 인덱스를 먼저 만들지 않는다 — YAGNI).
    __table_args__ = (sa.Index("idx_privacy_audit_user", "user_id", sa.desc("occurred_at")),)

    # ── 변환 헬퍼 (schema↔db seam, DeletionAudit 패턴) ──
    @classmethod
    def from_schema(cls, schema: SchemaPrivacyAudit) -> PrivacyAudit:
        """검증된 `schema.PrivacyAudit` → 영속 ORM(mapper 컬럼키 필터)."""
        data = schema.model_dump()
        mapped_keys = {col.key for col in sa.inspect(cls).mapper.column_attrs}
        kwargs = {k: v for k, v in data.items() if k in mapped_keys}
        return cls(**kwargs)

    def to_schema(self) -> SchemaPrivacyAudit:
        """영속 ORM → `schema.PrivacyAudit`(Pydantic 검증 복원)."""
        mapped_keys = {col.key for col in sa.inspect(type(self)).mapper.column_attrs}
        data = {key: getattr(self, key) for key in mapped_keys}
        return SchemaPrivacyAudit.model_validate(data)
