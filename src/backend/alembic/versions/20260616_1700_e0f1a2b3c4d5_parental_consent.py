"""parental_consent 테이블 — 14세 미만 법정대리인 동의 GRANT 감사 (PIPA §22-2)

동의 *게이트*(`api/_auth.py.get_consented_user` 403)는 있었으나 동의를 *받는(GRANT)* 경로가
없었다(pipa_data_matrix.md §3.4 "미구현"). 이 리비전은 그 GRANT를 영속화하는 `parental_consent`
테이블을 *가산적*으로 만든다 — 법정대리인 동의 1건당 1행(append-only). 동의-기록 엔드포인트
(`POST /v1/users/me/parental-consent`)가 이 행을 적재하며 동시에 `user_profile.parent_consent_at`
을 채워 게이트를 통과시킨다. ORM 정본은 `whymath_backend/db/models/parental_consent.py`
(ParentalConsent). enum 타입 생성 없음 — consent_scope·verification_method는 String 컬럼
(AuditResourceType 선례·자유 문자열 태그)이라 PG enum DDL을 만들지 않는다.

스키마(refresh_token_session·deletion_audit 동형 — 보조/감사 테이블):
  - consent_id(UUID PK·server_default gen_random_uuid() — 앱이 명시 생성도 함·deletion_audit 선례).
  - user_id(UUID nullable·FK user_profile.user_id) — 동의 대상 학생. CASCADE 미적용(device.py 방침).
  - guardian_email_hash(VARCHAR(64) nullable) — 법정대리인 이메일 sha256 해시(평문 PII 금지).
  - verification_method(VARCHAR(32) nullable) — 검증 방식 이름(예: 'stub'·실 본인확인은 후속).
  - verification_ref(VARCHAR(255) nullable) — 외부 검증 거래의 불투명 참조(PII 아님).
  - consent_scope(VARCHAR(32) nullable) — 동의 범위(ConsentScope.value·현재 service_core만).
  - consent_signed_at·expires_at·revoked_at(TIMESTAMPTZ nullable) — 동의 완료·만료·철회 시각.
  - created_at(TIMESTAMPTZ nullable·server_default now()).

인덱스:
  - idx_parental_consent_user(user_id, consent_signed_at DESC) — 학생별 최신 동의 조회(감사).

downgrade(왕복 안전 — CI backend-migrations 잡이 `downgrade base`→`upgrade head` 왕복 검증):
  - 인덱스 → 테이블 순 drop. enum 타입 추가/정리 없음(String이라 무관).

Revision ID: e0f1a2b3c4d5
Revises: d9e0f1a2b3c4
Create Date: 2026-06-16 17:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e0f1a2b3c4d5"
down_revision: str | None = "d9e0f1a2b3c4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "parental_consent",
        # surrogate UUID PK — server_default gen_random_uuid()(앱이 명시 생성도 함·audit 선례).
        sa.Column(
            "consent_id",
            sa.Uuid(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        # 동의 대상 학생 — user_profile FK(nullable·CASCADE 미적용).
        sa.Column("user_id", sa.Uuid(), nullable=True),
        # 법정대리인 이메일 sha256 해시(64 hex) — 평문 PII 금지(parent_email_hash 동일 접근).
        sa.Column("guardian_email_hash", sa.String(length=64), nullable=True),
        # 검증 방식 이름(예: 'stub') — 실 본인확인은 변호사 자문 후속(consent_grant.py seam).
        sa.Column("verification_method", sa.String(length=32), nullable=True),
        # 외부 검증 거래의 불투명 참조(PII 아님). stub은 NULL.
        sa.Column("verification_ref", sa.String(length=255), nullable=True),
        # 동의 범위(ConsentScope.value 저장 — 현재 service_core만). enum 미생성(String·자유 태그).
        sa.Column("consent_scope", sa.String(length=32), nullable=True),
        # 동의 완료·만료·철회 시각(security_privacy.md parental_consents 필드 + 철회).
        sa.Column("consent_signed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("consent_id", name=op.f("pk_parental_consent")),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["user_profile.user_id"],
            name=op.f("fk_parental_consent_user_id_user_profile"),
        ),
    )
    # 학생별 최신 동의 조회(만료 재확인·감사) — deletion_audit·refresh_token_session DESC 패턴 동형.
    op.create_index(
        "idx_parental_consent_user",
        "parental_consent",
        ["user_id", sa.literal_column("consent_signed_at DESC")],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "idx_parental_consent_user",
        table_name="parental_consent",
    )
    op.drop_table("parental_consent")
