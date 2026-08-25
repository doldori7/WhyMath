"""xAPI (Experience API / Tin Can API) Adapter.

EOS Canonical Education Event → xAPI Statement 변환.
변환은 lossy일 수 있다. EOS 내부 모델이 정본이고 xAPI는 상호운용성 출력.
"""

from __future__ import annotations

from typing import Any

from whymath_backend.schema.education_event import EducationEvent


def to_xapi(event: EducationEvent) -> dict[str, Any]:
    """EducationEvent를 xAPI Statement로 변환."""
    actor: dict[str, Any] = {
        "objectType": "Agent",
        "account": {
            "homePage": "https://whymath.io",
            "name": event.actor.actor_id,
        },
    }
    if event.actor.actor_type == "learner":
        actor["account"]["homePage"] = "https://whymath.io/learner"

    verb_display: dict[str, str] = {}
    if event.event_type.startswith("problem."):
        verb_display["en-US"] = event.event_type.replace(".", " ")
    else:
        verb_display["en-US"] = event.event_type

    statement = {
        "actor": actor,
        "verb": {
            "id": f"https://whymath.io/xapi/verbs/{event.event_type.replace('.', '_')}",
            "display": verb_display,
        },
        "object": {
            "objectType": "Activity",
            "id": f"https://whymath.io/{event.object.entity_type}/{event.object.entity_id}",
            "definition": {
                "type": f"https://whymath.io/xapi/activity/{event.object.entity_type}",
                "name": {"en-US": event.object.entity_type},
            },
        },
        "result": _build_result(event),
        "context": _build_context(event),
        "timestamp": event.occurred_at.isoformat(),
    }
    return statement


def _build_result(event: EducationEvent) -> dict[str, Any] | None:
    """payload에서 xAPI result로 변환 가능한 필드 추출."""
    payload = event.payload
    result: dict[str, Any] = {}
    if "is_correct" in payload:
        result["success"] = payload["is_correct"]
    if "score" in payload or "mastery" in payload:
        result["score"] = {}
        if "score" in payload:
            result["score"]["raw"] = payload["score"]
        if "mastery" in payload:
            result["score"]["scaled"] = payload["mastery"]
    if "duration_ms" in payload:
        seconds = payload["duration_ms"] / 1000.0
        result["duration"] = f"PT{seconds:.3f}S"
    return result if result else None


def _build_context(event: EducationEvent) -> dict[str, Any] | None:
    """context를 xAPI context로 변환."""
    ctx: dict[str, Any] = {}
    extensions: dict[str, Any] = {}
    if event.context.curriculum_id:
        extensions["https://whymath.io/xapi/context/curriculum_id"] = event.context.curriculum_id
    if event.context.grade:
        extensions["https://whymath.io/xapi/context/grade"] = event.context.grade
    if event.context.concept_ids:
        extensions["https://whymath.io/xapi/context/concept_ids"] = event.context.concept_ids
    if event.context.skill_ids:
        extensions["https://whymath.io/xapi/context/skill_ids"] = event.context.skill_ids
    if event.trace.correlation_id:
        extensions["https://whymath.io/xapi/context/correlation_id"] = event.trace.correlation_id
    if event.trace.causation_id:
        extensions["https://whymath.io/xapi/context/causation_id"] = event.trace.causation_id
    if extensions:
        ctx["extensions"] = extensions
    if event.session.learning_session_id:
        ctx["registration"] = event.session.learning_session_id
    return ctx if ctx else None
