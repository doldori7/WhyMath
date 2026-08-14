"""분석 이벤트 envelope 계약 — 멱등성·시간 의미·PII allowlist 경계."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from whymath_backend.schema.analytics_event import (
    AnalyticsEventEnvelope,
    AnalyticsEventSource,
    build_analytics_event_envelope,
)
from whymath_backend.schema.enums import EventType


def _valid_kwargs() -> dict[str, object]:
    return {
        "event_uuid": uuid4(),
        "occurred_at": datetime(2026, 8, 2, 10, 0, tzinfo=timezone.utc),
        "received_at": datetime(2026, 8, 2, 10, 0, 1, tzinfo=timezone.utc),
        "source": AnalyticsEventSource.BACKEND,
        "event_type": EventType.힌트제공,
        "payload": {"hint_level": 2},
    }


def test_envelope_preserves_idempotency_and_timestamp_meaning() -> None:
    envelope = AnalyticsEventEnvelope(**_valid_kwargs())

    assert envelope.schema_version == 1
    assert envelope.event_uuid is not None
    assert envelope.occurred_at < envelope.received_at
    # 기존 event_data 계약은 선택 필드를 None으로 명시해 정규화한다.
    assert envelope.payload["hint_level"] == 2
    assert envelope.payload["mode"] is None
    assert envelope.payload["persona"] is None


def test_envelope_rejects_unknown_top_level_fields() -> None:
    with pytest.raises(ValidationError):
        AnalyticsEventEnvelope(**_valid_kwargs(), device_id="permanent-device")  # type: ignore[call-arg]


@pytest.mark.parametrize(
    "forbidden_key",
    [
        "chat_text",
        "student_answer",
        "solution_latex",
        "image",
        "url_query",
        "x_coordinate",
        "device_id",
    ],
)
def test_envelope_rejects_forbidden_pii_payload_keys(forbidden_key: str) -> None:
    kwargs = _valid_kwargs()
    kwargs["payload"] = {"hint_level": 2, forbidden_key: "sensitive"}

    with pytest.raises(ValidationError, match="금지"):
        AnalyticsEventEnvelope(**kwargs)


def test_envelope_rejects_payload_key_not_allowlisted_for_event_type() -> None:
    kwargs = _valid_kwargs()
    kwargs["payload"] = {"hint_level": 2, "unexpected": True}

    with pytest.raises(ValidationError, match="allowlist"):
        AnalyticsEventEnvelope(**kwargs)


def test_builder_normalizes_allowed_payload() -> None:
    envelope = build_analytics_event_envelope(
        event_uuid=uuid4(),
        occurred_at=datetime(2026, 8, 2, 10, 0, tzinfo=timezone.utc),
        received_at=datetime(2026, 8, 2, 10, 0, 1, tzinfo=timezone.utc),
        source=AnalyticsEventSource.BACKEND,
        event_type=EventType.검산결과,
        payload={"passed": True},
    )

    assert envelope.payload["passed"] is True
    assert envelope.payload["error_kind"] is None
    assert envelope.event_type == EventType.검산결과


def test_mobile_event_requires_session_id() -> None:
    kwargs = _valid_kwargs()
    kwargs["source"] = AnalyticsEventSource.MOBILE

    with pytest.raises(ValidationError, match="session_id"):
        AnalyticsEventEnvelope(**kwargs)


def test_received_at_before_occurred_at_rejected() -> None:
    kwargs = _valid_kwargs()
    kwargs["received_at"] = datetime(2026, 8, 2, 9, 59, tzinfo=timezone.utc)

    with pytest.raises(ValidationError, match="received_at"):
        AnalyticsEventEnvelope(**kwargs)
