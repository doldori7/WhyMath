"""Education Event SDK — EOS 204.

`emit_education_event`는 producer가 Canonical Education Event를 만들 때 사용하는
단일 강제 지점이다. SDK는 자동으로 event_id, timestamp, source, trace, privacy
metadata, schema validation을 처리한다.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from whymath_backend.schema.education_event import (
    Actor,
    EducationContext,
    EducationEvent,
    Object,
    Privacy,
    Session,
    Source,
    Trace,
)
from whymath_backend.schema.event_registry import DEFAULT_REGISTRY, EventRegistry
from whymath_backend.schema.event_taxonomy import (
    EducationEventType,
    EventActorType,
    EventPrivacyClassification,
)


class EducationEventSDK:
    """Education Event 생산 SDK."""

    def __init__(
        self,
        registry: EventRegistry | None = None,
        service: str = "whymath-backend",
        client: str | None = None,
    ) -> None:
        self.registry = registry or DEFAULT_REGISTRY
        self.service = service
        self.client = client

    def emit(
        self,
        event_type: EducationEventType,
        actor_type: EventActorType | str,
        actor_id: str | None,
        object_type: str,
        object_id: str,
        object_version: str | None = None,
        payload: dict[str, Any] | None = None,
        context: dict[str, Any] | None = None,
        trace: dict[str, Any] | None = None,
        privacy: dict[str, Any] | None = None,
        session: dict[str, Any] | None = None,
        occurred_at: datetime | None = None,
        source_service: str | None = None,
        source_client: str | None = None,
    ) -> EducationEvent:
        """Canonical Education Event를 생성한다.

        자동 처리:
        - event_id: UUIDv7
        - occurred_at / recorded_at
        - source: service/client
        - privacy: registry 조회로 기본값 채움
        - schema validation (extra="forbid")
        """
        now = datetime.now(timezone.utc)
        occurred = occurred_at or now
        if occurred.tzinfo is None:
            occurred = occurred.replace(tzinfo=timezone.utc)

        # registry 조회로 privacy 기본값 채움
        entry = self.registry.get(event_type)
        if entry is None:
            raise ValueError(
                f"미등록 event_type: {event_type.value} — " "registry에 등록 또는 exemption 필요"
            )

        privacy_obj = Privacy(
            classification=entry.pii_classification,
            contains_pii=entry.pii_classification
            in (
                EventPrivacyClassification.PII,
                EventPrivacyClassification.SENSITIVE,
            ),
            retention_policy_id=entry.retention_policy_id,
            ai_training_allowed=entry.ai_training_allowed,
        )
        if privacy:
            privacy_obj = privacy_obj.model_copy(update=privacy)

        actor_kwargs: dict[str, Any] = {"actor_type": actor_type}
        if actor_id is not None:
            actor_kwargs["actor_id"] = actor_id

        object_kwargs: dict[str, Any] = {"entity_type": object_type, "entity_id": object_id}
        if object_version is not None:
            object_kwargs["entity_version"] = object_version

        return EducationEvent(
            event_id=str(uuid4()),  # TODO: UUIDv7로 교체(Python 3.13+ 또는 라이브러리 도입)
            event_type=event_type,
            event_version=entry.schema_version,
            occurred_at=occurred,
            recorded_at=now,
            actor=Actor(**actor_kwargs),
            session=Session(**(session or {})),
            object=Object(**object_kwargs),
            context=EducationContext(**(context or {})),
            payload=payload or {},
            source=Source(
                service=source_service or self.service,
                client=source_client or self.client,
            ),
            trace=Trace(**(trace or {})),
            privacy=privacy_obj,
            schema_version="education-event@1.0",
        )


# 모듈 레벨 기본 SDK 인스턴스.
_sdk = EducationEventSDK()


def emit_education_event(
    event_type: EducationEventType,
    actor_type: EventActorType | str,
    actor_id: str | None,
    object_type: str,
    object_id: str,
    **kwargs: Any,
) -> EducationEvent:
    """기본 SDK 인스턴스로 EducationEvent를 생성한다."""
    return _sdk.emit(
        event_type=event_type,
        actor_type=actor_type,
        actor_id=actor_id,
        object_type=object_type,
        object_id=object_id,
        **kwargs,
    )
