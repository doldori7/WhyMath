"""AuditEvent ORM(영속 레이어) 단위테스트 — DB 연결 없이 검증 가능한 것들.

ADMIN-10 EOS 범용 감사 이벤트의 schema↔ORM 변환·DDL 컴파일·메타데이터 등록을
동결한다. Pydantic `metadata` 필드는 SQLAlchemy Declarative 예약어 때문에
ORM 속성명 `event_metadata`로 매핑되는 점을 별도로 검증한다.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.schema import CreateTable

from whymath_backend.db.base import Base
from whymath_backend.db.models.audit import AuditEvent as OrmAuditEvent
from whymath_backend.schema.audit import AuditEvent as SchemaAuditEvent
from whymath_backend.schema.enums import (
    AuditEventActorType,
    AuditEventAuthorization,
    AuditEventRetentionPolicy,
    AuditEventSeverity,
    AuditEventStatus,
)


def _pg_ddl(table: object) -> str:
    """ORM 테이블을 PostgreSQL dialect로 컴파일한 CREATE TABLE 문자열로 반환."""
    return str(CreateTable(table).compile(dialect=postgresql.dialect()))  # type: ignore[arg-type]


# ──────────────────────────────────────────────────────────────────────────
# 1) 메타데이터 등록
# ──────────────────────────────────────────────────────────────────────────
def test_audit_event_table_registered_in_metadata() -> None:
    """`Base.metadata`에 `audit_event` 테이블이 등록돼 있다(alembic 인식 전제)."""
    assert "audit_event" in Base.metadata.tables


def test_audit_event_orm_tablename() -> None:
    """ORM의 __tablename__이 ADMIN-10 설계대로 `audit_event`다."""
    assert OrmAuditEvent.__tablename__ == "audit_event"


# ──────────────────────────────────────────────────────────────────────────
# 2) PG DDL 컴파일
# ──────────────────────────────────────────────────────────────────────────
def test_audit_event_ddl_compiles() -> None:
    """audit_event DDL이 PG dialect로 컴파일되며 핵심 컬럼·인덱스를 포함한다."""
    ddl = _pg_ddl(OrmAuditEvent.__table__)
    assert "CREATE TABLE audit_event" in ddl
    assert "audit_event_id" in ddl
    assert "gen_random_uuid()" in ddl
    assert "occurred_at" in ddl
    assert "actor_type" in ddl
    assert "actor_id" in ddl
    assert "action" in ddl
    assert "resource_type" in ddl
    assert "resource_id" in ddl
    assert "before_version" in ddl
    assert "after_version" in ddl
    assert "changed_fields" in ddl
    assert "authorization_decision" in ddl
    assert "reason_code" in ddl
    assert "reason_text" in ddl
    assert "request_id" in ddl
    assert "trace_id" in ddl
    assert "workflow_id" in ddl
    assert "source_service" in ddl
    assert "status" in ddl
    assert "severity" in ddl
    assert "metadata" in ddl  # DB 컬럼명은 `metadata`
    assert "retention_policy_id" in ddl
    assert "integrity_hash" in ddl
    assert "previous_hash" in ddl


def test_audit_event_jsonb_column_uses_none_as_null() -> None:
    """`metadata` JSONB 컬럼이 `none_as_null=True`로 선언돼 있다(SEC-06 동일 기준)."""
    # DB 컬럼명은 `metadata`, ORM 속성명은 `event_metadata`.
    col = OrmAuditEvent.__table__.c.metadata
    assert isinstance(col.type, JSONB)
    assert col.type.none_as_null is True


def test_audit_event_indexes_present() -> None:
    """주요 조회 패턴 인덱스가 ORM 테이블에 등록돼 있다."""
    index_names = {idx.name for idx in OrmAuditEvent.__table__.indexes}
    assert "idx_audit_event_occurred_at" in index_names
    assert "idx_audit_event_actor" in index_names
    assert "idx_audit_event_action" in index_names
    assert "idx_audit_event_resource" in index_names
    assert "idx_audit_event_request_id" in index_names
    assert "idx_audit_event_workflow_id" in index_names


# ──────────────────────────────────────────────────────────────────────────
# 3) schema↔ORM 변환 roundtrip
# ──────────────────────────────────────────────────────────────────────────
def test_audit_event_roundtrip_preserves_core_fields() -> None:
    """schema.AuditEvent → ORM → schema가 핵심 필드를 보존한다."""
    uid = uuid.uuid4()
    occurred = datetime(2026, 8, 25, 12, 0, 0, tzinfo=timezone.utc)
    schema = SchemaAuditEvent(
        audit_event_id=uid,
        occurred_at=occurred,
        actor_type=AuditEventActorType.user,
        actor_id="usr_123",
        actor_role="content_admin",
        action="problem.update",
        resource_type="Problem",
        resource_id="prob_456",
        before_version="v17",
        after_version="v18",
        changed_fields=["difficulty", "solution"],
        authorization_decision=AuditEventAuthorization.allow,
        reason_code="ERROR_FIX",
        reason_text="해설 3단계 계산 오류 수정",
        request_id="req_abc",
        trace_id="trc_def",
        workflow_id="wf_123",
        source_service="problems_api",
        status=AuditEventStatus.success,
        severity=AuditEventSeverity.high,
        metadata={"input_hash": "h1", "output_hash": "h2"},
        retention_policy_id=AuditEventRetentionPolicy.content,
    )

    orm = OrmAuditEvent.from_schema(schema)
    assert orm.audit_event_id == uid
    assert orm.occurred_at == occurred
    assert orm.actor_type == "user"
    assert orm.actor_id == "usr_123"
    assert orm.actor_role == "content_admin"
    assert orm.action == "problem.update"
    assert orm.resource_type == "Problem"
    assert orm.resource_id == "prob_456"
    assert orm.before_version == "v17"
    assert orm.after_version == "v18"
    assert orm.changed_fields == ["difficulty", "solution"]
    assert orm.authorization_decision == "allow"
    assert orm.reason_code == "ERROR_FIX"
    assert orm.reason_text == "해설 3단계 계산 오류 수정"
    assert orm.request_id == "req_abc"
    assert orm.trace_id == "trc_def"
    assert orm.workflow_id == "wf_123"
    assert orm.source_service == "problems_api"
    assert orm.status == "success"
    assert orm.severity == "HIGH"
    # ORM 속성명은 `event_metadata`지만 DB 컬럼명은 `metadata`다.
    assert orm.event_metadata == {"input_hash": "h1", "output_hash": "h2"}
    assert orm.retention_policy_id == "RET_CONTENT"

    back = orm.to_schema()
    assert back.audit_event_id == uid
    assert back.occurred_at == occurred
    assert back.actor_type == AuditEventActorType.user
    assert back.action == "problem.update"
    assert back.metadata == {"input_hash": "h1", "output_hash": "h2"}


def test_audit_event_roundtrip_with_null_metadata() -> None:
    """metadata가 None이어도 schema↔ORM 왕복이 깨지지 않는다."""
    schema = SchemaAuditEvent(
        actor_type=AuditEventActorType.service_account,
        action="system.cron.run",
        resource_type="CronJob",
        resource_id="job_1",
        source_service="scheduler",
        status=AuditEventStatus.success,
        retention_policy_id=AuditEventRetentionPolicy.security,
        metadata=None,
    )
    orm = OrmAuditEvent.from_schema(schema)
    assert orm.event_metadata is None
    back = orm.to_schema()
    assert back.metadata is None
