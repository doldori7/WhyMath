"""EOS Education Event Taxonomy — EventType 정본 (204 Education Event System).

이 enum은 204 설계 문서(`docs/architecture/204_education_event_system.md`)의
Event Taxonomy을 코드로 구현한 것이다. 모든 값은 `<domain>.<past-tense-action>`
형식을 따르며, Command/Event 구분에서 Event만 포함한다.

확장 규칙:
- 신규 event_type 추가 시 `docs/architecture/204_education_event_system.md` §5 Taxonomy
  와 `data/education_event_registry.json`에 동시 등록한다.
- 네이티브 PG enum 추가(ALTER TYPE)는 불필요 — `EducationEvent` 봉투는 문자열
  event_type을 사용하고, registry가 그 계약을 검증한다.
- deprecated event는 값을 삭제하지 않고 registry `status: deprecated`로 관리한다.
"""

from __future__ import annotations

from enum import Enum


class EducationEventType(str, Enum):
    """EOS Canonical Education Event 타입."""

    # ── interaction ──────────────────────────────────────────────────────────
    PROBLEM_VIEWED = "problem.viewed"
    HINT_REQUESTED = "hint.requested"
    HINT_VIEWED = "hint.viewed"
    SOLUTION_VIEWED = "solution.viewed"
    VIDEO_STARTED = "video.started"
    VISUALIZATION_MANIPULATED = "visualization.manipulated"
    TUTOR_MESSAGE_SENT = "tutor.message.sent"

    # ── learning ───────────────────────────────────────────────────────────
    PROBLEM_ATTEMPTED = "problem.attempted"
    PROBLEM_ANSWERED = "problem.answered"
    PROBLEM_SOLVED = "problem.solved"
    PROBLEM_FAILED = "problem.failed"

    CONCEPT_STUDIED = "concept.studied"
    CONCEPT_PRACTICED = "concept.practiced"
    CONCEPT_REVIEWED = "concept.reviewed"

    SKILL_PRACTICED = "skill.practiced"
    SKILL_DEMONSTRATED = "skill.demonstrated"

    # ── assessment ─────────────────────────────────────────────────────────
    ASSESSMENT_STARTED = "assessment.started"
    ASSESSMENT_COMPLETED = "assessment.completed"

    RESPONSE_SCORED = "response.scored"

    MASTERY_ESTIMATED = "mastery.estimated"
    MASTERY_UPDATED = "mastery.updated"

    ABILITY_ESTIMATED = "ability.estimated"

    OBJECTIVE_ACHIEVED = "objective.achieved"
    OBJECTIVE_FAILED = "objective.failed"

    # ── knowledge ────────────────────────────────────────────────────────────
    CONCEPT_CREATED = "concept.created"
    CONCEPT_UPDATED = "concept.updated"
    CONCEPT_VERSIONED = "concept.versioned"

    DEFINITION_UPDATED = "definition.updated"
    THEOREM_UPDATED = "theorem.updated"
    FORMULA_UPDATED = "formula.updated"

    PREREQUISITE_ADDED = "prerequisite.added"
    PREREQUISITE_REMOVED = "prerequisite.removed"

    MISCONCEPTION_UPDATED = "misconception.updated"

    CURRICULUM_MAPPING_UPDATED = "curriculum.mapping.updated"

    # ── learner_model ──────────────────────────────────────────────────────
    RISK_SCORE_UPDATED = "risk_score.updated"

    # ── misconception ───────────────────────────────────────────────────────
    MISCONCEPTION_DETECTED = "misconception.detected"
    MISCONCEPTION_INFERRED = "misconception.inferred"
    MISCONCEPTION_CORRECTED = "misconception.corrected"

    # ── pedagogy ─────────────────────────────────────────────────────────────
    PEDAGOGY_STRATEGY_SELECTED = "pedagogy.strategy.selected"

    # ── tutoring ─────────────────────────────────────────────────────────────
    TUTOR_QUESTION_SUBMITTED = "tutor.question.submitted"
    TUTOR_RESPONSE_PRESENTED = "tutor.response.presented"
    TUTOR_INTENT_INFERRED = "tutor.intent.inferred"
    LEARNER_CONTEXT_RETRIEVED = "learner.context.retrieved"

    # ── content ────────────────────────────────────────────────────────────────
    CONTENT_PUBLISHED = "content.published"
    CONTENT_UNPUBLISHED = "content.unpublished"
    PROBLEM_APPROVED = "problem.approved"
    PROBLEM_REJECTED = "problem.rejected"

    # ── AI ────────────────────────────────────────────────────────────────────
    AI_TUTOR_INVOKED = "ai.tutor.invoked"
    AI_HINT_GENERATED = "ai.hint.generated"
    AI_SOLUTION_GENERATED = "ai.solution.generated"
    AI_QUESTION_GENERATED = "ai.question.generated"

    AI_RESPONSE_VALIDATED = "ai.response.validated"
    AI_RESPONSE_REJECTED = "ai.response.rejected"

    AI_GRADING_REQUESTED = "ai.grading.requested"
    AI_GRADING_COMPLETED = "ai.grading.completed"

    AI_MISCONCEPTION_INFERRED = "ai.misconception.inferred"

    AI_TOOL_CALLED = "ai.tool.called"
    AI_AGENT_ACTION_EXECUTED = "ai.agent.action.executed"

    AI_REQUESTED = "ai.requested"
    AI_GENERATED = "ai.generated"
    AI_VALIDATED = "ai.validated"
    AI_REJECTED = "ai.rejected"

    # ── learning_path ────────────────────────────────────────────────────────
    LEARNING_PATH_GENERATED = "learning_path.generated"
    LEARNING_PATH_ADJUSTED = "learning_path.adjusted"

    # ── agent ────────────────────────────────────────────────────────────────
    AGENT_ACTION_EXECUTED = "agent.action.executed"

    # ── system ───────────────────────────────────────────────────────────────
    CONTENT_INDEXED = "content.indexed"
    VECTOR_EMBEDDING_CREATED = "vector.embedding.created"

    # ── learning_session ─────────────────────────────────────────────────────
    LEARNING_SESSION_STARTED = "learning.session.started"
    LEARNING_SESSION_ENDED = "learning.session.ended"


class EducationEventDomain(str, Enum):
    """Education Event 최상위 도메인."""

    INTERACTION = "interaction"
    LEARNING = "learning"
    ASSESSMENT = "assessment"
    KNOWLEDGE = "knowledge"
    CURRICULUM = "curriculum"
    LEARNER_MODEL = "learner_model"
    MISCONCEPTION = "misconception"
    PEDAGOGY = "pedagogy"
    TUTORING = "tutoring"
    CONTENT = "content"
    AI = "ai"
    COLLABORATION = "collaboration"
    PARENT = "parent"
    TEACHER = "teacher"
    AGENT = "agent"
    SYSTEM = "system"


class EventActorType(str, Enum):
    """Event 행위자 유형."""

    LEARNER = "learner"
    TEACHER = "teacher"
    PARENT = "parent"
    AI = "ai"
    SYSTEM = "system"
    ADMIN = "admin"
    CONTENT_SYSTEM = "content_system"


class EventPrivacyClassification(str, Enum):
    """이벤트 PII 등급."""

    ANONYMOUS = "anonymous"
    PSEUDONYMOUS = "pseudonymous"
    PII = "pii"
    SENSITIVE = "sensitive"


class EventStatus(str, Enum):
    """Event Registry 항목 상태."""

    DRAFT = "draft"
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    RETIRED = "retired"


class EventNamespace(str, Enum):
    """Event 최상위 namespace. Education 외 감사/운영/보안은 별도."""

    EDUCATION = "EDUCATION_EVENT"
    SECURITY = "SECURITY_EVENT"
    AUDIT = "AUDIT_EVENT"
    OPERATIONAL = "OPERATIONAL_EVENT"


# domain → event_type 매핑 (거버넌스 테스트용).
# registry가 단일 진실원이지만, 코드 내 빠른 lookup을 위해 별도 상수로 둔다.
DOMAIN_EVENT_MAP: dict[EducationEventDomain, frozenset[EducationEventType]] = {
    EducationEventDomain.INTERACTION: frozenset(
        {
            EducationEventType.PROBLEM_VIEWED,
            EducationEventType.HINT_REQUESTED,
            EducationEventType.HINT_VIEWED,
            EducationEventType.SOLUTION_VIEWED,
            EducationEventType.VIDEO_STARTED,
            EducationEventType.VISUALIZATION_MANIPULATED,
            EducationEventType.TUTOR_MESSAGE_SENT,
        }
    ),
    EducationEventDomain.LEARNING: frozenset(
        {
            EducationEventType.PROBLEM_ATTEMPTED,
            EducationEventType.PROBLEM_ANSWERED,
            EducationEventType.PROBLEM_SOLVED,
            EducationEventType.PROBLEM_FAILED,
            EducationEventType.CONCEPT_STUDIED,
            EducationEventType.CONCEPT_PRACTICED,
            EducationEventType.CONCEPT_REVIEWED,
            EducationEventType.SKILL_PRACTICED,
            EducationEventType.SKILL_DEMONSTRATED,
        }
    ),
    EducationEventDomain.ASSESSMENT: frozenset(
        {
            EducationEventType.ASSESSMENT_STARTED,
            EducationEventType.ASSESSMENT_COMPLETED,
            EducationEventType.RESPONSE_SCORED,
            EducationEventType.MASTERY_ESTIMATED,
            EducationEventType.MASTERY_UPDATED,
            EducationEventType.ABILITY_ESTIMATED,
            EducationEventType.OBJECTIVE_ACHIEVED,
            EducationEventType.OBJECTIVE_FAILED,
        }
    ),
    EducationEventDomain.KNOWLEDGE: frozenset(
        {
            EducationEventType.CONCEPT_CREATED,
            EducationEventType.CONCEPT_UPDATED,
            EducationEventType.CONCEPT_VERSIONED,
            EducationEventType.DEFINITION_UPDATED,
            EducationEventType.THEOREM_UPDATED,
            EducationEventType.FORMULA_UPDATED,
            EducationEventType.PREREQUISITE_ADDED,
            EducationEventType.PREREQUISITE_REMOVED,
            EducationEventType.MISCONCEPTION_UPDATED,
            EducationEventType.CURRICULUM_MAPPING_UPDATED,
        }
    ),
    EducationEventDomain.CURRICULUM: frozenset({EducationEventType.CURRICULUM_MAPPING_UPDATED}),
    EducationEventDomain.LEARNER_MODEL: frozenset(
        {EducationEventType.RISK_SCORE_UPDATED, EducationEventType.MASTERY_UPDATED}
    ),
    EducationEventDomain.SYSTEM: frozenset(
        {
            EducationEventType.LEARNING_SESSION_STARTED,
            EducationEventType.LEARNING_SESSION_ENDED,
            EducationEventType.LEARNING_PATH_GENERATED,
            EducationEventType.LEARNING_PATH_ADJUSTED,
            EducationEventType.CONTENT_INDEXED,
            EducationEventType.VECTOR_EMBEDDING_CREATED,
        }
    ),
    EducationEventDomain.MISCONCEPTION: frozenset(
        {
            EducationEventType.MISCONCEPTION_DETECTED,
            EducationEventType.MISCONCEPTION_INFERRED,
            EducationEventType.MISCONCEPTION_CORRECTED,
        }
    ),
    EducationEventDomain.PEDAGOGY: frozenset({EducationEventType.PEDAGOGY_STRATEGY_SELECTED}),
    EducationEventDomain.TUTORING: frozenset(
        {
            EducationEventType.TUTOR_QUESTION_SUBMITTED,
            EducationEventType.TUTOR_RESPONSE_PRESENTED,
            EducationEventType.TUTOR_INTENT_INFERRED,
            EducationEventType.LEARNER_CONTEXT_RETRIEVED,
        }
    ),
    EducationEventDomain.CONTENT: frozenset(
        {
            EducationEventType.CONTENT_PUBLISHED,
            EducationEventType.CONTENT_UNPUBLISHED,
            EducationEventType.PROBLEM_APPROVED,
            EducationEventType.PROBLEM_REJECTED,
        }
    ),
    EducationEventDomain.AI: frozenset(
        {
            EducationEventType.AI_TUTOR_INVOKED,
            EducationEventType.AI_HINT_GENERATED,
            EducationEventType.AI_SOLUTION_GENERATED,
            EducationEventType.AI_QUESTION_GENERATED,
            EducationEventType.AI_RESPONSE_VALIDATED,
            EducationEventType.AI_RESPONSE_REJECTED,
            EducationEventType.AI_GRADING_REQUESTED,
            EducationEventType.AI_GRADING_COMPLETED,
            EducationEventType.AI_MISCONCEPTION_INFERRED,
            EducationEventType.AI_TOOL_CALLED,
            EducationEventType.AI_AGENT_ACTION_EXECUTED,
            EducationEventType.AI_REQUESTED,
            EducationEventType.AI_GENERATED,
            EducationEventType.AI_VALIDATED,
            EducationEventType.AI_REJECTED,
        }
    ),
    EducationEventDomain.AGENT: frozenset({EducationEventType.AGENT_ACTION_EXECUTED}),
}


def event_domain(event_type: EducationEventType) -> EducationEventDomain:
    """event_type이 속한 domain을 반환한다. 매핑 누락 시 KeyError."""
    for domain, types in DOMAIN_EVENT_MAP.items():
        if event_type in types:
            return domain
    raise KeyError(f"EducationEventType {event_type.value}에 대한 domain 매핑 없음")
