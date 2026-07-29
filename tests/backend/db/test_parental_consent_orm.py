"""ParentalConsent ORM(영속 레이어) + 신원 확인 SEAM 단위테스트 — DB 연결 없이 검증.

PIPA 만14세 미만 법정대리인 동의 GRANT(docs/legal/pipa_data_matrix.md §3). curriculum_entry/
audit ORM 테스트 패턴 답습: 메타데이터 등록 / PG DDL 컴파일(UUID PK·FK·VARCHAR) / schema↔ORM
변환 roundtrip / PK 단일성. 추가로 `consent_grant.py` SEAM(Protocol·stub) 동작을 단위 검증한다.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable
from whymath_backend.consent_grant import (
    GuardianVerificationRequest,
    GuardianVerifier,
    StubGuardianVerifier,
    VerificationResult,
    _default_guardian_verifier,
)
from whymath_backend.db.base import Base
from whymath_backend.db.models.parental_consent import ParentalConsent as OrmParentalConsent
from whymath_backend.schema.enums import ConsentScope
from whymath_backend.schema.parental_consent import ParentalConsent as SchemaParentalConsent


def _pg_ddl(table: object) -> str:
    """ORM 테이블을 PostgreSQL dialect로 컴파일한 CREATE TABLE 문자열로 반환."""
    return str(CreateTable(table).compile(dialect=postgresql.dialect()))  # type: ignore[arg-type]


# ──────────────────────────────────────────────────────────────────────────
# 1) 메타데이터 등록 (alembic autogenerate 인식 전제)
# ──────────────────────────────────────────────────────────────────────────
def test_parental_consent_registered_in_metadata() -> None:
    """Base.metadata에 parental_consent 테이블이 등록돼 있다(alembic 인식 전제)."""
    assert "parental_consent" in Base.metadata.tables
    assert OrmParentalConsent.__tablename__ == "parental_consent"


# ──────────────────────────────────────────────────────────────────────────
# 2) PG DDL 컴파일 + PK 단일성 + FK
# ──────────────────────────────────────────────────────────────────────────
def test_parental_consent_pk_is_consent_id_single() -> None:
    """PK는 consent_id 단일 surrogate PK다."""
    pk_cols = [c.name for c in OrmParentalConsent.__table__.primary_key.columns]
    assert pk_cols == ["consent_id"]


def test_parental_consent_ddl_columns_and_fk() -> None:
    """DDL에 UUID PK(server_default)·user_profile FK·해시/방식 VARCHAR·시각 TIMESTAMPTZ 포함."""
    ddl = _pg_ddl(OrmParentalConsent.__table__)
    assert "consent_id UUID DEFAULT gen_random_uuid() NOT NULL" in ddl
    assert "FOREIGN KEY(user_id) REFERENCES user_profile (user_id)" in ddl
    assert "guardian_email_hash VARCHAR(64)" in ddl
    assert "verification_method VARCHAR(32)" in ddl
    assert "verification_ref VARCHAR(255)" in ddl
    assert "consent_scope VARCHAR(32)" in ddl
    assert "consent_signed_at TIMESTAMP WITH TIME ZONE" in ddl
    assert "created_at TIMESTAMP WITH TIME ZONE DEFAULT now()" in ddl


# ──────────────────────────────────────────────────────────────────────────
# 3) schema↔ORM 변환 roundtrip
# ──────────────────────────────────────────────────────────────────────────
def test_schema_orm_roundtrip_preserves_fields() -> None:
    """schema → ORM → schema 왕복이 모든 필드를 보존한다(from_schema/to_schema seam)."""
    now = datetime(2026, 6, 16, 12, 0, tzinfo=timezone.utc)
    schema = SchemaParentalConsent(
        consent_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        guardian_email_hash="a" * 64,
        verification_method="stub",
        verification_ref=None,
        consent_scope=ConsentScope.service_core,
        consent_signed_at=now,
        expires_at=None,
        revoked_at=None,
        created_at=now,
    )
    orm = OrmParentalConsent.from_schema(schema)
    back = orm.to_schema()
    assert back.consent_id == schema.consent_id
    assert back.user_id == schema.user_id
    assert back.guardian_email_hash == "a" * 64
    assert back.verification_method == "stub"
    # use_enum_values=True라 schema의 consent_scope는 문자열 값으로 직렬화된다.
    assert back.consent_scope == ConsentScope.service_core.value
    assert back.consent_signed_at == now


# ──────────────────────────────────────────────────────────────────────────
# 4) 신원 확인 SEAM (Protocol + StubGuardianVerifier) — 법적 경계
# ──────────────────────────────────────────────────────────────────────────
def test_stub_verifier_records_method_stub_not_fake_real_verification() -> None:
    """stub은 통과를 주되 method='stub'을 *명시*한다(법적 검증으로 위장하지 않음·reference None)."""
    verifier = StubGuardianVerifier()
    result = verifier.verify(GuardianVerificationRequest(guardian_email="guardian@example.com"))
    assert isinstance(result, VerificationResult)
    assert result.verified is True
    # 핵심(법적 경계): 방식이 'stub'으로 남아 감사 시 실 본인확인이 아니었음을 식별 가능.
    assert result.method == "stub"
    assert result.method == StubGuardianVerifier.METHOD
    # 외부 거래 참조 없음(PII 아님·stub).
    assert result.reference is None


def test_stub_verifier_rejects_empty_email_input_hygiene() -> None:
    """빈 이메일은 통지 대상조차 없어 미통과(입력 위생 — 신원 검증 아님)."""
    verifier = StubGuardianVerifier()
    result = verifier.verify(GuardianVerificationRequest(guardian_email="   "))
    assert result.verified is False
    assert result.method == "stub"


def test_stub_satisfies_guardian_verifier_protocol() -> None:
    """StubGuardianVerifier는 GuardianVerifier Protocol을 만족한다(runtime_checkable)."""
    assert isinstance(StubGuardianVerifier(), GuardianVerifier)


def test_default_verifier_is_stub_pending_legal_review() -> None:
    """기본 verifier는 stub이다 — 실 본인확인은 변호사 자문 후속(consent_grant.py 경계)."""
    assert isinstance(_default_guardian_verifier(), StubGuardianVerifier)
