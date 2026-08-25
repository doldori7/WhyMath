"""EOS Audit Event SDK — `audit.emit(...)` (ADMIN-10).

`docs/architecture/90_audit_log.md`가 정본. 이 모듈은 Audit 행을 만들어
`session.add()`만 하고 **commit은 호출자**가 담당한다 — 감사 행과 실제 변경이
같은 트랜잭션으로 원자적이어야 하기 때문이다(`privacy/audit.py` 선례).

민감 데이터 보호:
  - `metadata`에는 학생 이름·전화·이메일·답·prompt 원문·세션 토큰 등을 절대 넣지 않는다.
  - `changed_fields`는 필드명 배열만 저장한다.
  - 버전 이력은 `before_version`/`after_version` 식별자만 남기고, 원본은 Version Store에서 조회.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from whymath_backend.db.models.audit import AuditEvent as AuditEventORM
from whymath_backend.schema.audit import AuditEvent as AuditEventSchema
from whymath_backend.schema.enums import (
    AuditEventActorType,
    AuditEventAuthorization,
    AuditEventRetentionPolicy,
    AuditEventSeverity,
    AuditEventStatus,
)

__all__ = [
    "emit",
    "emit_ai_event",
    "emit_content_event",
    "emit_identity_event",
]

_logger = logging.getLogger("whymath.audit.event_bus")


def _validate_metadata(metadata: dict[str, Any] | None) -> None:
    """`metadata`에 금지된 키가 들어가면 즉시 실패한다(fail-closed).

    이 검사는 실수로 PII가 로그에 누설되는 것을 막는 마지막 방어선이다. 키 이름 기반
    차단이므로 완벽하지 않지만, 명백한 실수를 구조적으로 막는다.
    """
    if not metadata:
        return
    forbidden_keys = {
        "name",
        "phone",
        "email",
        "password",
        "token",
        "session_token",
        "refresh_token",
        "answer",
        "student_answer",
        "prompt",
        "prompt_text",
        "raw_prompt",
        "dialogue_content",
        "message",
    }
    lower_keys = {k.lower() for k in metadata.keys()}
    hits = lower_keys & forbidden_keys
    if hits:
        raise ValueError(
            f"audit_event.metadata에 금지 키가 포함되어 있습니다: {sorted(hits)}. "
            "PII·prompt 원문·민감 데이터는 Audit Log에 저장하지 않습니다."
        )


def emit(
    session: AsyncSession,
    *,
    actor_type: AuditEventActorType,
    action: str,
    resource_type: str,
    resource_id: str,
    source_service: str,
    retention_policy_id: AuditEventRetentionPolicy,
    actor_id: str | None = None,
    actor_role: str | None = None,
    before_version: str | None = None,
    after_version: str | None = None,
    changed_fields: list[str] | None = None,
    authorization_decision: AuditEventAuthorization | None = None,
    reason_code: str | None = None,
    reason_text: str | None = None,
    request_id: str | None = None,
    trace_id: str | None = None,
    workflow_id: str | None = None,
    status: AuditEventStatus = AuditEventStatus.success,
    severity: AuditEventSeverity = AuditEventSeverity.notice,
    metadata: dict[str, Any] | None = None,
) -> AuditEventORM:
    """범용 감사 이벤트 1행을 만들어 `session`에 add한다(commit은 호출자).

    Returns:
        추가된 ORM 객체(아직 commit 전).

    Raises:
        ValueError: `metadata`에 금지된 민감 키가 포함된 경우.
    """
    _validate_metadata(metadata)

    schema = AuditEventSchema(
        actor_type=actor_type,
        actor_id=actor_id,
        actor_role=actor_role,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        before_version=before_version,
        after_version=after_version,
        changed_fields=changed_fields,
        authorization_decision=authorization_decision,
        reason_code=reason_code,
        reason_text=reason_text,
        request_id=request_id,
        trace_id=trace_id,
        workflow_id=workflow_id,
        source_service=source_service,
        status=status,
        severity=severity,
        metadata=metadata,
        retention_policy_id=retention_policy_id,
    )
    orm_event = AuditEventORM.from_schema(schema)
    session.add(orm_event)
    _logger.debug(
        "Audit emitted: %s %s %s:%s",
        orm_event.action,
        orm_event.actor_type,
        orm_event.resource_type,
        orm_event.resource_id,
    )
    return orm_event


def emit_identity_event(
    session: AsyncSession,
    *,
    action: str,
    actor_id: uuid.UUID | str | None,
    resource_id: uuid.UUID | str,
    source_service: str,
    actor_role: str | None = None,
    authorization_decision: AuditEventAuthorization | None = None,
    status: AuditEventStatus = AuditEventStatus.success,
    severity: AuditEventSeverity = AuditEventSeverity.notice,
    reason_code: str | None = None,
    reason_text: str | None = None,
    request_id: str | None = None,
    trace_id: str | None = None,
    workflow_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> AuditEventORM:
    """인증·권한 영역 감사 이벤트 헬퍼(USER Actor)."""
    return emit(
        session,
        actor_type=AuditEventActorType.user,
        actor_id=str(actor_id) if actor_id is not None else None,
        actor_role=actor_role,
        action=action,
        resource_type="UserProfile",
        resource_id=str(resource_id),
        source_service=source_service,
        retention_policy_id=AuditEventRetentionPolicy.security,
        authorization_decision=authorization_decision,
        status=status,
        severity=severity,
        reason_code=reason_code,
        reason_text=reason_text,
        request_id=request_id,
        trace_id=trace_id,
        workflow_id=workflow_id,
        metadata=metadata,
    )


def emit_content_event(
    session: AsyncSession,
    *,
    action: str,
    actor_id: uuid.UUID | str | None,
    resource_type: str,
    resource_id: uuid.UUID | str,
    source_service: str,
    actor_role: str | None = None,
    before_version: str | None = None,
    after_version: str | None = None,
    changed_fields: list[str] | None = None,
    authorization_decision: AuditEventAuthorization | None = None,
    reason_code: str | None = None,
    reason_text: str | None = None,
    request_id: str | None = None,
    trace_id: str | None = None,
    workflow_id: str | None = None,
    status: AuditEventStatus = AuditEventStatus.success,
    severity: AuditEventSeverity = AuditEventSeverity.notice,
    metadata: dict[str, Any] | None = None,
) -> AuditEventORM:
    """콘텐츠·지식그래프 변경 감사 헬퍼(USER Actor)."""
    return emit(
        session,
        actor_type=AuditEventActorType.user,
        actor_id=str(actor_id) if actor_id is not None else None,
        actor_role=actor_role,
        action=action,
        resource_type=resource_type,
        resource_id=str(resource_id),
        source_service=source_service,
        retention_policy_id=AuditEventRetentionPolicy.content,
        before_version=before_version,
        after_version=after_version,
        changed_fields=changed_fields,
        authorization_decision=authorization_decision,
        reason_code=reason_code,
        reason_text=reason_text,
        request_id=request_id,
        trace_id=trace_id,
        workflow_id=workflow_id,
        status=status,
        severity=severity,
        metadata=metadata,
    )


def emit_ai_event(
    session: AsyncSession,
    *,
    action: str,
    actor_id: str,
    resource_type: str,
    resource_id: uuid.UUID | str,
    source_service: str,
    provider: str,
    model: str,
    model_version: str | None = None,
    prompt_template_id: str | None = None,
    prompt_version: str | None = None,
    temperature: float | None = None,
    input_hash: str | None = None,
    output_hash: str | None = None,
    validation_result: str | None = None,
    validation_version: str | None = None,
    langfuse_trace_id: str | None = None,
    status: AuditEventStatus = AuditEventStatus.success,
    severity: AuditEventSeverity = AuditEventSeverity.notice,
    request_id: str | None = None,
    trace_id: str | None = None,
    workflow_id: str | None = None,
    reason_code: str | None = None,
    reason_text: str | None = None,
) -> AuditEventORM:
    """AI 생성·승인 감사 헬퍼(AI_AGENT Actor).

    prompt 원문·학생 데이터는 금지. `input_hash`/`output_hash`로 원문의 존재만 증거하고,
    필요 시 Langfuse trace를 참조한다.
    """
    metadata: dict[str, Any] = {
        "provider": provider,
        "model": model,
    }
    if model_version is not None:
        metadata["model_version"] = model_version
    if prompt_template_id is not None:
        metadata["prompt_template_id"] = prompt_template_id
    if prompt_version is not None:
        metadata["prompt_version"] = prompt_version
    if temperature is not None:
        metadata["temperature"] = temperature
    if input_hash is not None:
        metadata["input_hash"] = input_hash
    if output_hash is not None:
        metadata["output_hash"] = output_hash
    if validation_result is not None:
        metadata["validation"] = {
            "result": validation_result,
        }
        if validation_version is not None:
            metadata["validation"]["validator_version"] = validation_version
    if langfuse_trace_id is not None:
        metadata["langfuse_trace_id"] = langfuse_trace_id

    return emit(
        session,
        actor_type=AuditEventActorType.ai_agent,
        actor_id=actor_id,
        action=action,
        resource_type=resource_type,
        resource_id=str(resource_id),
        source_service=source_service,
        retention_policy_id=AuditEventRetentionPolicy.ai,
        status=status,
        severity=severity,
        reason_code=reason_code,
        reason_text=reason_text,
        request_id=request_id,
        trace_id=trace_id,
        workflow_id=workflow_id,
        metadata=metadata,
    )
