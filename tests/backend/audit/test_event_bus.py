"""Audit Event SDK (`audit.emit` 및 헬퍼) 단위테스트 — DB 연결 없음.

ADMIN-10 P0 계약:
  - `emit()`이 AuditEvent ORM을 만들어 `session.add()`만 한다(commit은 호출자).
  - `emit_identity_event`/`emit_content_event`/`emit_ai_event` 헬퍼가 올바른
    `actor_type`·`retention_policy_id`·메타데이터 구조를 만든다.
  - `metadata`에 PII·prompt 원문·민감 키가 들어가면 즉시 실패한다(fail-closed).
"""

from __future__ import annotations

import hashlib
import uuid
from collections.abc import AsyncIterator
from typing import Any

import pytest

from whymath_backend.audit import event_bus
from whymath_backend.audit.llm import _hash_text, emit_generate_audit
from whymath_backend.db.models.audit import AuditEvent as AuditEventORM
from whymath_backend.schema.enums import (
    AuditEventActorType,
    AuditEventAuthorization,
    AuditEventRetentionPolicy,
    AuditEventSeverity,
    AuditEventStatus,
)


class _FakeSession:
    """`emit()`이 호출하는 최소 AsyncSession 표면 — add/commit/rollback만 추적."""

    def __init__(self) -> None:
        self.added: list[Any] = []
        self.committed = False
        self.rolled_back = False

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True

    async def __aenter__(self) -> "_FakeSession":
        return self

    async def __aexit__(self, *args: object) -> None:
        pass


async def _fake_session() -> AsyncIterator[_FakeSession]:
    yield _FakeSession()


# ──────────────────────────────────────────────────────────────────────────
# 범용 emit
# ──────────────────────────────────────────────────────────────────────────
def test_emit_creates_audit_event_and_adds_to_session() -> None:
    """`emit()`은 AuditEvent ORM을 만들어 세션에 add하고, commit은 호출자가 담당한다."""
    session = _FakeSession()
    event = event_bus.emit(
        session,
        actor_type=AuditEventActorType.user,
        action="problem.update",
        resource_type="Problem",
        resource_id="prob_456",
        source_service="problems_api",
        retention_policy_id=AuditEventRetentionPolicy.content,
        actor_id="usr_123",
        actor_role="content_admin",
        before_version="v17",
        after_version="v18",
        changed_fields=["difficulty"],
        authorization_decision=AuditEventAuthorization.allow,
        reason_code="ERROR_FIX",
        reason_text="해설 오류 수정",
        request_id="req_abc",
        trace_id="trc_def",
        workflow_id="wf_1",
        status=AuditEventStatus.success,
        severity=AuditEventSeverity.high,
        metadata={"client": "admin-cms"},
    )
    assert isinstance(event, AuditEventORM)
    assert session.added == [event]
    assert session.committed is False
    assert event.action == "problem.update"
    assert event.actor_type == "user"
    assert event.actor_id == "usr_123"
    assert event.resource_type == "Problem"
    assert event.resource_id == "prob_456"
    assert event.severity == "HIGH"
    assert event.retention_policy_id == "RET_CONTENT"


def test_emit_uses_default_severity_and_status() -> None:
    """severity/status를 생략하면 기본값 NOTICE/success가 적용된다."""
    session = _FakeSession()
    event = event_bus.emit(
        session,
        actor_type=AuditEventActorType.user,
        action="concept.read",
        resource_type="Concept",
        resource_id="c_1",
        source_service="concept_api",
        retention_policy_id=AuditEventRetentionPolicy.content,
    )
    assert event.severity == "NOTICE"
    assert event.status == "success"


# ──────────────────────────────────────────────────────────────────────────
# 헬퍼별 actor_type·retention_policy·필드
# ──────────────────────────────────────────────────────────────────────────
def test_emit_identity_event_uses_user_actor_and_security_retention() -> None:
    """인증·권한 이벤트는 `user` Actor + `RET_SECURITY` 정책을 사용한다."""
    session = _FakeSession()
    uid = uuid.uuid4()
    event = event_bus.emit_identity_event(
        session,
        action="iam.role.assign",
        actor_id=uid,
        resource_id=uid,
        source_service="role_grant_cli",
        authorization_decision=AuditEventAuthorization.allow,
        severity=AuditEventSeverity.high,
        metadata={"old_role": "student", "new_role": "content_admin"},
    )
    assert event.actor_type == "user"
    assert event.action == "iam.role.assign"
    assert event.resource_type == "UserProfile"
    assert event.resource_id == str(uid)
    assert event.retention_policy_id == "RET_SECURITY"
    assert event.severity == "HIGH"
    assert event.authorization_decision == "allow"


def test_emit_content_event_uses_user_actor_and_content_retention() -> None:
    """콘텐츠·지식 변경은 `user` Actor + `RET_CONTENT` 정책을 사용한다."""
    session = _FakeSession()
    uid = uuid.uuid4()
    event = event_bus.emit_content_event(
        session,
        action="problem.update",
        actor_id=uid,
        resource_type="Problem",
        resource_id=uid,
        source_service="problems_api",
        changed_fields=["answer", "solution"],
        severity=AuditEventSeverity.high,
        reason_code="CONTENT_IMPROVEMENT",
    )
    assert event.actor_type == "user"
    assert event.action == "problem.update"
    assert event.resource_type == "Problem"
    assert event.resource_id == str(uid)
    assert event.changed_fields == ["answer", "solution"]
    assert event.retention_policy_id == "RET_CONTENT"
    assert event.reason_code == "CONTENT_IMPROVEMENT"


@pytest.mark.asyncio
async def test_emit_ai_event_uses_ai_agent_and_ai_retention() -> None:
    """AI 생성·승인은 `ai_agent` Actor + `RET_AI` 정책, model/prompt/hash 메타데이터를 남긴다."""
    session = _FakeSession()
    rid = uuid.uuid4()
    event = event_bus.emit_ai_event(
        session,
        action="ai.problem.generate",
        actor_id="problem-generator",
        resource_type="Problem",
        resource_id=rid,
        source_service="app.generate",
        provider="ollama",
        model="qwen3:30b-a3b",
        model_version="latest",
        prompt_template_id="problem-gen",
        prompt_version="v21",
        temperature=0.2,
        input_hash="sha256_input",
        output_hash="sha256_output",
        validation_result="pass",
        validation_version="math-validator-v8",
        langfuse_trace_id="trace_1",
        status=AuditEventStatus.success,
        severity=AuditEventSeverity.notice,
    )
    assert event.actor_type == "ai_agent"
    assert event.action == "ai.problem.generate"
    assert event.retention_policy_id == "RET_AI"
    assert event.resource_id == str(rid)
    assert event.event_metadata == {
        "provider": "ollama",
        "model": "qwen3:30b-a3b",
        "model_version": "latest",
        "prompt_template_id": "problem-gen",
        "prompt_version": "v21",
        "temperature": 0.2,
        "input_hash": "sha256_input",
        "output_hash": "sha256_output",
        "validation": {"result": "pass", "validator_version": "math-validator-v8"},
        "langfuse_trace_id": "trace_1",
    }


# ──────────────────────────────────────────────────────────────────────────
# metadata 민감 키 차단 (fail-closed)
# ──────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize(
    "forbidden_key",
    [
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
    ],
)
def test_emit_rejects_forbidden_metadata_keys(forbidden_key: str) -> None:
    """금지 키가 metadata에 들어가면 ValueError로 즉시 거부한다."""
    session = _FakeSession()
    with pytest.raises(ValueError, match="금지 키"):
        event_bus.emit(
            session,
            actor_type=AuditEventActorType.user,
            action="problem.update",
            resource_type="Problem",
            resource_id="p1",
            source_service="test",
            retention_policy_id=AuditEventRetentionPolicy.content,
            metadata={forbidden_key: "value"},
        )
    assert session.added == []


def test_emit_allows_safe_metadata_keys() -> None:
    """안전한 메타데이터 키는 통과한다."""
    session = _FakeSession()
    event = event_bus.emit(
        session,
        actor_type=AuditEventActorType.ai_agent,
        action="ai.problem.generate",
        resource_type="Problem",
        resource_id="p1",
        source_service="test",
        retention_policy_id=AuditEventRetentionPolicy.ai,
        metadata={
            "provider": "ollama",
            "model": "qwen3:30b-a3b",
            "model_version": "latest",
            "prompt_template_id": "problem-gen",
            "input_hash": "h1",
            "output_hash": "h2",
            "validation": {"result": "pass"},
            "langfuse_trace_id": "trace_1",
        },
    )
    assert event.event_metadata["provider"] == "ollama"


# ──────────────────────────────────────────────────────────────────────────
# AI 감사 헬퍼 (audit/llm.py)
# ──────────────────────────────────────────────────────────────────────────


def test_hash_text_returns_sha256_hex() -> None:
    """`_hash_text`는 SHA256 hex digest를 반환한다."""
    text = "원문 데이터"
    expected = hashlib.sha256(text.encode("utf-8")).hexdigest()
    assert _hash_text(text) == expected


@pytest.mark.asyncio
async def test_emit_generate_audit_records_ai_event() -> None:
    """`/v1/generate`용 AI 감사 헬퍼가 input/output hash + model 메타데이터를 남긴다."""
    from whymath_backend.l3.models import CostTier, LocalModelTier, RoutingDecision
    from whymath_backend.l3.pipeline import GenerationResult

    session = _FakeSession()
    decision = RoutingDecision(
        cost_tier=CostTier.LOCAL,
        mode="async",
        local_model=LocalModelTier.QUALITY,
        est_latency_ms=0,
    )
    result = GenerationResult(
        decision=decision, text="생성결과", cache_hit=False, status="completed"
    )
    await emit_generate_audit(
        session,
        decision=decision,
        prompt="prompt 원문",
        system="system 원문",
        result=result,
        request_id="req_1",
        validation_result="pass",
    )
    assert len(session.added) == 1
    event = session.added[0]
    assert isinstance(event, AuditEventORM)
    assert event.actor_type == "ai_agent"
    assert event.action == "ai.generate"
    assert event.resource_type == "LLMCall"
    assert event.resource_id == "req_1"
    assert event.retention_policy_id == "RET_AI"
    assert event.source_service == "app.generate"
    assert event.event_metadata["provider"] == "ollama"
    assert event.event_metadata["model"] == "qwen3:30b-a3b"
    assert event.event_metadata["input_hash"] == _hash_text("system 원문\nprompt 원문")
    assert event.event_metadata["output_hash"] == _hash_text("생성결과")
    assert event.event_metadata["validation"] == {"result": "pass"}
