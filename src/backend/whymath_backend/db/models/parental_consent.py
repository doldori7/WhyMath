"""parental_consent 테이블 — 14세 미만 법정대리인 동의 GRANT 감사 행 (PIPA §22-2).

동의 *게이트*(`api/_auth.py.get_consented_user` 403)는 이미 있었으나 동의를 *받는(GRANT)*
경로가 없었다(pipa_data_matrix.md §3.4 "미구현"). 이 테이블은 그 빈자리를 메운다 — 법정대리인이
동의를 완료할 때마다 1행을 append-only로 적재하고(누가·무엇을·언제·어떻게 동의했는가), 동의-기록
엔드포인트가 동시에 `user_profile.parent_consent_at`을 채워 게이트를 통과시킨다(`api/users.py`의
parental-consent 엔드포인트). ORM 정본은 이 클래스, 검증·API 표현은 `schema/parental_consent.py`
(ParentalConsent)이며 `from_schema`/`to_schema`가 잇는다(audit.py·user.py 동일 패턴).

설계(audit.py DeletionAudit·refresh_token_session.py 동형 — 보조/감사 테이블):
  - **PK = consent_id(UUID·surrogate)**: server_default `gen_random_uuid()`(audit.py 선례).
    한 학생이 여러 번 동의(만료 후 재확인·범위 추가)하면 여러 행 → surrogate PK가 자연스럽다.
  - **user_id FK → user_profile.user_id**: *동의 대상 학생*(법정대리인이 대신 동의한 미성년
    본인). nullable(audit.py user_id는 FK 아님이었지만, 여기선 동의 대상이 명확한 실 사용자라
    FK를 건다 — refresh_token_session 선례). CASCADE 미적용(상위 lifecycle 몫·device.py 방침).
  - **guardian_email_hash(String(64))**: 법정대리인 이메일 sha256 해시. **평문 PII 금지**
    (CLAUDE.md 미성년 개인정보·security_privacy.md "PII 평문 저장 금지") — 기존
    parent_email_hash·email_hash와 동일 접근(api/auth.py.email_hash 재사용).
  - **verification_method(String(32))**: 검증 *방식* 이름(예: "stub"). AuditResourceType처럼
    네이티브 PG enum을 만들지 않고 String — 방식은 *seam*으로 확장되며(consent_grant.py) 실
    본인확인 방식은 변호사 자문 후 추가되므로 enum 마이그레이션을 강제하지 않는다.
  - **verification_ref(String(255)·nullable)**: 외부 검증 거래의 *불투명 참조*(PII 아님). stub은
    None(외부 거래 없음).
  - **consent_scope(String(32))**: 동의 범위(ConsentScope.value 저장 — 현재 service_core만).
    AuditResourceType과 동일하게 String + Pydantic enum으로 코드 안전성 확보(DB는 문자열 태그).
  - **consent_signed_at·expires_at·revoked_at(TIMESTAMPTZ)**: security_privacy.md
    parental_consents 필드(consent_signed_at·expires_at) + 철회 시각. expires_at·revoked_at은
    nullable(만료 미설정·미철회=NULL). created_at은 server_default now()(audit.py 선례).

인덱스:
  - idx_parental_consent_user(user_id, consent_signed_at DESC) — 학생별 최신 동의 조회(만료 재
    확인·감사). deletion_audit.idx_deletion_audit_user·refresh_token_session 동형.

개인정보 메모(CLAUDE.md): 법정대리인의 이름·연락처 등 다른 PII는 *수집하지 않는다*(데이터
최소화) — 이메일조차 해시로만 둔다. "is_minor면 동의 필수" 같은 cross-field 강제는 user.py
방침대로 ORM/schema 모두 하지 않는다(동의 대기 상태가 정당 — 미들웨어/게이트 책임).
"""

from __future__ import annotations

import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from whymath_backend.db.base import Base
from whymath_backend.schema.parental_consent import ParentalConsent as SchemaParentalConsent


class ParentalConsent(Base):
    """14세 미만 법정대리인 동의 1행(GRANT 감사) — append-only 기록."""

    __tablename__ = "parental_consent"

    consent_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid,
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    # 동의 대상 학생(법정대리인이 대신 동의한 미성년 본인) — user_profile FK(CASCADE 미적용).
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.Uuid, sa.ForeignKey("user_profile.user_id")
    )
    # 법정대리인 이메일 sha256 해시(64 hex) — 평문 PII 금지(parent_email_hash 동일 접근).
    guardian_email_hash: Mapped[str | None] = mapped_column(sa.String(64))
    # 검증 *방식* 이름(예: "stub"). 실 본인확인 방식은 변호사 자문 후속(consent_grant.py seam).
    verification_method: Mapped[str | None] = mapped_column(sa.String(32))
    # 외부 검증 거래의 불투명 참조(PII 아님). stub은 None.
    verification_ref: Mapped[str | None] = mapped_column(sa.String(255))
    # 동의 범위(ConsentScope.value 저장 — 현재 service_core만). enum 미생성(String·Audit 선례).
    consent_scope: Mapped[str | None] = mapped_column(sa.String(32))
    # 동의 완료·만료·철회 시각(security_privacy.md parental_consents 필드 + 철회).
    consent_signed_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    # 레코드 생성 시각 — server_default now()(audit.py 선례).
    created_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now()
    )

    # 학생별 최신 동의 조회(만료 재확인·감사) 접근 경로(deletion_audit·refresh_token_session 동형).
    __table_args__ = (
        sa.Index(
            "idx_parental_consent_user",
            "user_id",
            sa.desc("consent_signed_at"),
        ),
    )

    # ── 변환 헬퍼 (schema↔db seam, audit.py 패턴) ──────────────────────────
    @classmethod
    def from_schema(cls, schema: SchemaParentalConsent) -> ParentalConsent:
        """검증된 `schema.ParentalConsent` → 영속 ORM(mapper 컬럼키 필터)."""
        data = schema.model_dump()
        mapped_keys = {col.key for col in sa.inspect(cls).mapper.column_attrs}
        kwargs = {k: v for k, v in data.items() if k in mapped_keys}
        return cls(**kwargs)

    def to_schema(self) -> SchemaParentalConsent:
        """영속 ORM → `schema.ParentalConsent`(Pydantic 검증 복원)."""
        mapped_keys = {col.key for col in sa.inspect(type(self)).mapper.column_attrs}
        data = {key: getattr(self, key) for key in mapped_keys}
        return SchemaParentalConsent.model_validate(data)


__all__ = ["ParentalConsent"]
