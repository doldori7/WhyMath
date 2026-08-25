"""Caliper Analytics 1.2 Adapter.

EOS Canonical Education Event → Caliper Event 변환.
"""

from __future__ import annotations

from typing import Any

from whymath_backend.schema.education_event import EducationEvent


def to_caliper(event: EducationEvent) -> dict[str, Any]:
    """EducationEvent를 Caliper Event로 변환."""
    caliper_event: dict[str, Any] = {
        "@context": "http://purl.imsglobal.org/ctx/caliper/v1p2",
        "id": f"https://whymath.io/event/{event.event_id}",
        "type": _caliper_type(event),
        "actor": {
            "id": f"https://whymath.io/actor/{event.actor.actor_id}",
            "type": _caliper_actor_type(event.actor.actor_type),
        },
        "action": _caliper_action(event),
        "object": {
            "id": f"https://whymath.io/{event.object.entity_type}/{event.object.entity_id}",
            "type": _caliper_object_type(event.object.entity_type),
        },
        "eventTime": event.occurred_at.isoformat(),
    }

    if event.context.curriculum_id or event.context.concept_ids:
        caliper_event["extensions"] = {}
        if event.context.curriculum_id:
            caliper_event["extensions"]["curriculum_id"] = event.context.curriculum_id
        if event.context.concept_ids:
            caliper_event["extensions"]["concept_ids"] = event.context.concept_ids
        if event.context.skill_ids:
            caliper_event["extensions"]["skill_ids"] = event.context.skill_ids

    if event.trace.correlation_id:
        caliper_event["extensions"] = caliper_event.get("extensions", {})
        caliper_event["extensions"]["correlation_id"] = event.trace.correlation_id

    return caliper_event


def _caliper_type(event: EducationEvent) -> str:
    """Caliper Event type 매핑."""
    domain = event.event_type.split(".", 1)[0]
    if domain in {"problem", "assessment"}:
        return "AssessmentEvent"
    if domain in {"hint", "solution", "video", "visualization"}:
        return "ToolUseEvent"
    return "Event"


def _caliper_actor_type(actor_type: str) -> str:
    mapping = {
        "learner": "Person",
        "teacher": "Person",
        "parent": "Person",
        "ai": "SoftwareApplication",
        "system": "SoftwareApplication",
        "admin": "Person",
    }
    return mapping.get(actor_type, "Agent")


def _caliper_action(event: EducationEvent) -> str:
    """event_type → Caliper action URI."""
    action = event.event_type.replace(".", "-")
    return f"http://purl.imsglobal.org/vocab/caliper/v1p2/action/{action}"


def _caliper_object_type(entity_type: str) -> str:
    mapping = {
        "problem": "AssessmentItem",
        "concept": "DigitalResource",
        "hint": "Message",
        "solution": "Message",
        "video": "VideoObject",
        "assessment": "Assessment",
    }
    return mapping.get(entity_type, "DigitalResource")
