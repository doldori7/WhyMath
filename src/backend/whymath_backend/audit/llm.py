"""LLM 호출 감사 헬퍼 — `app.py` /v1/generate 등 L3 표면에서 사용 (ADMIN-10).

`docs/architecture/90_audit_log.md`가 정본. prompt 원문·학생 데이터는 저장하지 않고
input/output 해시 + 라우팅 메타데이터만 `audit_event`에 남긴다.
"""

from __future__ import annotations

import hashlib
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from whymath_backend.audit.event_bus import emit_ai_event
from whymath_backend.l3.models import CostTier, RoutingDecision
from whymath_backend.l3.pipeline import GenerationResult
from whymath_backend.schema.enums import AuditEventSeverity, AuditEventStatus


def _model_id_from_decision(decision: RoutingDecision) -> tuple[str, str | None]:
    """라우팅 결정에서 provider·모델 식별자를 추정한다(P0).

    - LOCAL → provider "ollama", model은 `resolve_model()`로 해석.
    - CLOUD_MID/HIGH → provider "anthropic", model은 decision에 없으므로 None(후속 매핑).
    """
    cost = decision.cost_tier
    if cost == CostTier.LOCAL:
        from whymath_backend.l3.router import resolve_model

        try:
            model = resolve_model(decision.local_family, decision.local_model)
        except ValueError:
            model = None
        return "ollama", model
    # CLOUD_MID/HIGH는 모델 매핑이 별도 contract라 여기선 tier만 남긴다.
    if cost == CostTier.CLOUD_MID:
        return "anthropic", "claude-sonnet-4-6"
    if cost == CostTier.CLOUD_HIGH:
        return "anthropic", "claude-opus-4-7"
    return str(cost.value), None


def _hash_text(text: str) -> str:
    """SHA256 hex digest — 원문 해시만 남기고 평문은 폐기."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


async def emit_generate_audit(
    session: AsyncSession,
    *,
    decision: RoutingDecision,
    prompt: str,
    system: str,
    result: GenerationResult,
    request_id: str | None = None,
    validation_result: str | None = None,
) -> None:
    """`/v1/generate` 동기/비동기 호출에 대한 AI 감사 이벤트 1행을 기록한다.

    이 함수는 `audit.emit(...)`의 래퍼로, session.add()만 하고 commit은 호출자가 담당한다.
    """
    provider, model = _model_id_from_decision(decision)
    input_hash = _hash_text(f"{system}\n{prompt}")
    output_hash = _hash_text(result.text) if result.text else None
    status = (
        AuditEventStatus.success
        if result.status in {"completed", "queued"}
        else AuditEventStatus.failure
    )
    severity = (
        AuditEventSeverity.notice if result.status == "completed" else AuditEventSeverity.info
    )

    emit_ai_event(
        session,
        action="ai.generate",
        actor_id="l3-pipeline",
        resource_type="LLMCall",
        resource_id=request_id or str(uuid.uuid4()),
        source_service="app.generate",
        provider=provider,
        model=model or "unknown",
        prompt_template_id=None,
        prompt_version=None,
        temperature=None,
        input_hash=input_hash,
        output_hash=output_hash,
        validation_result=validation_result,
        validation_version=None,
        status=status,
        severity=severity,
        request_id=request_id,
        trace_id=None,
        workflow_id=None,
    )
