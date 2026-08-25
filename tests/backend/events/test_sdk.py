"""EOS 204 Education Event SDK + Adapter 테스트."""

from __future__ import annotations

import pytest

from whymath_backend.events import emit_education_event
from whymath_backend.events.adapters import to_caliper, to_cloudevents, to_xapi
from whymath_backend.schema.education_event import EducationEvent
from whymath_backend.schema.event_taxonomy import (
    EducationEventType,
    EventActorType,
    EventPrivacyClassification,
)


@pytest.fixture
def sample_event() -> EducationEvent:
    """테스트용 EducationEvent 샘플."""
    return emit_education_event(
        event_type=EducationEventType.PROBLEM_ANSWERED,
        actor_type=EventActorType.LEARNER,
        actor_id="usr_001",
        object_type="problem",
        object_id="prob_001",
        object_version="7",
        payload={"attempt_no": 2, "response_type": "expression", "duration_ms": 42115},
        context={
            "subject_id": "math",
            "curriculum_id": "kr_2022",
            "grade": "middle_2",
            "concept_ids": ["concept_quadratic_function"],
            "skill_ids": ["skill_axis_of_symmetry"],
        },
        trace={"trace_id": "trc_001", "correlation_id": "cor_001"},
        privacy={"consent_scope": "learning_analytics"},
        source_service="problem-service",
        source_client="student-web",
    )


def test_emit_creates_education_event(sample_event: EducationEvent) -> None:
    """SDK emit이 EducationEvent를 생성한다."""
    assert sample_event.event_type == EducationEventType.PROBLEM_ANSWERED
    assert sample_event.actor.actor_id == "usr_001"
    assert sample_event.object.entity_id == "prob_001"
    assert sample_event.object.entity_version == "7"
    assert sample_event.payload["attempt_no"] == 2
    assert sample_event.context.subject_id == "math"
    assert sample_event.trace.correlation_id == "cor_001"
    assert sample_event.privacy.classification == EventPrivacyClassification.PSEUDONYMOUS
    assert sample_event.privacy.retention_policy_id == "RET-LEARN-03"


def test_emit_rejects_unregistered_event() -> None:
    """미등록 event_type은 ValueError."""
    with pytest.raises(ValueError, match="미등록 event_type"):
        emit_education_event(
            event_type=EducationEventType.CONTENT_INDEXED,
            actor_type=EventActorType.SYSTEM,
            actor_id=None,
            object_type="content",
            object_id="content_001",
        )


def test_emit_sets_timestamps(sample_event: EducationEvent) -> None:
    """emit이 occurred_at/recorded_at을 설정한다."""
    assert sample_event.occurred_at.tzinfo is not None
    assert sample_event.recorded_at.tzinfo is not None
    assert sample_event.recorded_at >= sample_event.occurred_at


def test_xapi_adapter(sample_event: EducationEvent) -> None:
    """xAPI adapter가 Statement를 생성."""
    statement = to_xapi(sample_event)
    assert statement["actor"]["objectType"] == "Agent"
    assert "problem_answered" in statement["verb"]["id"]
    assert statement["object"]["objectType"] == "Activity"
    assert "result" in statement
    assert statement["result"]["duration"] == "PT42.115S"


def test_caliper_adapter(sample_event: EducationEvent) -> None:
    """Caliper adapter가 Event를 생성."""
    caliper = to_caliper(sample_event)
    assert caliper["@context"] == "http://purl.imsglobal.org/ctx/caliper/v1p2"
    assert caliper["type"] == "AssessmentEvent"
    assert "problem-answered" in caliper["action"]
    assert caliper["actor"]["type"] == "Person"
    assert caliper["object"]["type"] == "AssessmentItem"


def test_cloudevents_adapter(sample_event: EducationEvent) -> None:
    """CloudEvents adapter가 envelope을 생성."""
    ce = to_cloudevents(sample_event)
    assert ce["specversion"] == "1.0"
    assert ce["type"] == "whymath.eos.problem.answered"
    assert ce["source"] == "whymath.io/problem-service"
    assert ce["id"] == sample_event.event_id
    assert "data" in ce
