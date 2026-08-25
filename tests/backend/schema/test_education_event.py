"""EOS 204 Education Event System — 봉투·Taxonomy·Registry 거버넌스 테스트."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

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
from whymath_backend.schema.event_registry import DEFAULT_REGISTRY, EventRegistryLoader
from whymath_backend.schema.event_taxonomy import (
    DOMAIN_EVENT_MAP,
    EducationEventDomain,
    EducationEventType,
    EventActorType,
    EventPrivacyClassification,
    EventStatus,
    event_domain,
)


def test_all_event_types_have_domain_mapping() -> None:
    """모든 EducationEventType은 DOMAIN_EVENT_MAP에 속해야 한다."""
    all_mapped: set[EducationEventType] = set()
    for types in DOMAIN_EVENT_MAP.values():
        all_mapped.update(types)
    missing = set(EducationEventType) - all_mapped
    assert not missing, f"domain 매핑 누락: {[e.value for e in missing]}"


def test_event_domain_lookup() -> None:
    """event_domain()이 정확한 domain을 반환."""
    assert event_domain(EducationEventType.PROBLEM_ANSWERED) == EducationEventDomain.LEARNING
    assert event_domain(EducationEventType.MASTERY_UPDATED) == EducationEventDomain.ASSESSMENT
    assert (
        event_domain(EducationEventType.MISCONCEPTION_INFERRED)
        == EducationEventDomain.MISCONCEPTION
    )
    assert event_domain(EducationEventType.AI_GENERATED) == EducationEventDomain.AI


def test_education_event_envelope_builds() -> None:
    """Canonical Education Event 봉투가 생성된다."""
    now = datetime.now(timezone.utc)
    event = EducationEvent(
        event_id=str(uuid4()),
        event_type=EducationEventType.PROBLEM_ANSWERED,
        event_version="1.0",
        occurred_at=now,
        recorded_at=now,
        actor=Actor(actor_type=EventActorType.LEARNER, actor_id="usr_001"),
        session=Session(session_id="ses_001", learning_session_id="ls_001"),
        object=Object(entity_type="problem", entity_id="prob_001", entity_version="7"),
        context=EducationContext(
            subject_id="math",
            curriculum_id="kr_2022",
            grade="middle_2",
            concept_ids=["concept_quadratic_function"],
            skill_ids=["skill_axis_of_symmetry"],
        ),
        payload={"attempt_no": 2, "response_type": "expression", "duration_ms": 42115},
        source=Source(service="problem-service", client="student-web"),
        trace=Trace(
            trace_id="trc_001",
            correlation_id="cor_001",
            causation_id="evt_parent",
            parent_event_id="evt_parent",
        ),
        privacy=Privacy(
            classification=EventPrivacyClassification.PSEUDONYMOUS,
            contains_pii=False,
            consent_scope="learning_analytics",
            retention_policy_id="RET-LEARN-03",
            ai_training_allowed=False,
        ),
        schema_version="education-event@1.0",
    )
    assert event.event_type == EducationEventType.PROBLEM_ANSWERED
    assert event.actor.actor_id == "usr_001"
    assert event.object.entity_id == "prob_001"
    assert event.context.concept_ids == ["concept_quadratic_function"]
    assert event.trace.causation_id == "evt_parent"


def test_recorded_at_must_not_precede_occurred_at() -> None:
    """recorded_at은 occurred_at보다 빠를 수 없다."""
    now = datetime.now(timezone.utc)
    with pytest.raises(ValueError, match="recorded_at은 occurred_at보다 빠를 수 없습니다"):
        EducationEvent(
            event_id=str(uuid4()),
            event_type=EducationEventType.PROBLEM_ANSWERED,
            occurred_at=now,
            recorded_at=now.replace(second=now.second - 1),
            actor=Actor(actor_type=EventActorType.LEARNER),
            object=Object(entity_type="problem", entity_id="prob_001"),
            source=Source(service="problem-service"),
            privacy=Privacy(classification=EventPrivacyClassification.PSEUDONYMOUS),
        )


def test_naive_datetime_rejected() -> None:
    """occurred_at/recorded_at은 timezone-aware여야 한다."""
    naive = datetime.now()
    with pytest.raises(ValueError, match="occurred_at과 recorded_at은 timezone-aware"):
        EducationEvent(
            event_id=str(uuid4()),
            event_type=EducationEventType.PROBLEM_ANSWERED,
            occurred_at=naive,
            recorded_at=naive,
            actor=Actor(actor_type=EventActorType.LEARNER),
            object=Object(entity_type="problem", entity_id="prob_001"),
            source=Source(service="problem-service"),
            privacy=Privacy(classification=EventPrivacyClassification.PSEUDONYMOUS),
        )


def test_default_registry_has_mvp_events() -> None:
    """기본 registry에 MVP 핵심 이벤트가 등록돼 있다."""
    required = {
        EducationEventType.PROBLEM_ANSWERED,
        EducationEventType.HINT_REQUESTED,
        EducationEventType.HINT_VIEWED,
        EducationEventType.MASTERY_UPDATED,
        EducationEventType.MISCONCEPTION_INFERRED,
        EducationEventType.PEDAGOGY_STRATEGY_SELECTED,
        EducationEventType.TUTOR_RESPONSE_PRESENTED,
        EducationEventType.AI_GENERATED,
        EducationEventType.LEARNING_PATH_GENERATED,
    }
    for event_type in required:
        entry = DEFAULT_REGISTRY.get(event_type)
        assert entry is not None, f"registry 누락: {event_type.value}"
        assert entry.status == EventStatus.ACTIVE


def test_registry_json_loads() -> None:
    """data/education_event_registry.json이 로드된다."""
    registry = EventRegistryLoader.load()
    assert registry.get(EducationEventType.PROBLEM_ANSWERED) is not None


def test_registry_required_fields() -> None:
    """registry required_fields가 payload에 존재하면 통과."""
    entry = DEFAULT_REGISTRY.get(EducationEventType.PROBLEM_ANSWERED)
    assert entry is not None
    assert "attempt_no" in entry.required_fields


def test_event_type_values_are_lowercase_past_tense() -> None:
    """event_type 값은 소문자이고 점으로 구분된 과거형 형식을 따른다."""
    for event_type in EducationEventType:
        assert event_type.value.islower()
        assert "." in event_type.value
