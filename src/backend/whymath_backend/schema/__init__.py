"""WhyMath Schema v1.0 도메인 모델 (Pydantic) — 슬라이스 1·2·3·4·5·6·7(도메인 완결).

설계 정본: `schemas/v1.0/schema_v1.0.md` §3(Problem)·§4(Concept Graph)·§5(User)·
§6(Activity)·§7(Dialogue)·§8(Assessment)·§9(Time Series)·§10(Provenance)·§14.3(ENUM).

Phase 메모: 코드베이스 전체가 *Pydantic-schema-only*(DB 미배포)이므로 이 슬라이스도
순수 Pydantic 모델이다(SQLAlchemy/alembic은 후속 Phase).

공개 심볼:
  - enums: Accessibility·AnswerFormat·AssessmentType·AttemptMode·CognitiveType·
    ConceptLevel·ConceptRole·ContentType·Curriculum·Device·EdgeType·EventType·
    ExamType·GenerationType·LicenseType·MajorCategory·MentalPhase·NoteApp·Persona·
    QuestionFormat·RelationType·Resolution·ReviewStatus·SchoolType·SessionType·
    SignaturePattern·SocraticStrategy·SourceType·StepType·StudentIntent·Subject·
    SubscriptionTier·TrackType·TurnRole·VisualType
  - problem(슬라이스 1): Condition·Problem·ProblemStep·ProblemRelation
  - provenance(슬라이스 2): ContentProvenance·GenerationLog
  - concept(슬라이스 3): Concept·ConceptEdge·ProblemConcept·ConceptFusion
  - user(슬라이스 4): UserProfile·UserTrackHistory·UserPersonaHistory·UserStateSnapshot
  - activity(슬라이스 5): LearningSession·ProblemAttempt·AttemptEvent
  - dialogue(슬라이스 5): Dialogue·DialogueTurn
  - assessment(슬라이스 6): Assessment·ConceptMasteryHistory
  - timeseries(슬라이스 7): DailyLearningMetrics·ProblemSolveTimeDistribution·
    UserBehaviorMetrics
"""

from whymath_backend.schema.activity import (
    AttemptEvent,
    LearningSession,
    ProblemAttempt,
)
from whymath_backend.schema.assessment import (
    Assessment,
    ConceptMasteryHistory,
)
from whymath_backend.schema.concept import (
    Concept,
    ConceptEdge,
    ConceptFusion,
    ProblemConcept,
)
from whymath_backend.schema.dialogue import (
    Dialogue,
    DialogueTurn,
)
from whymath_backend.schema.enums import (
    Accessibility,
    AnswerFormat,
    AssessmentType,
    AttemptMode,
    CognitiveType,
    ConceptLevel,
    ConceptRole,
    ContentType,
    Curriculum,
    Device,
    EdgeType,
    EventType,
    ExamType,
    GenerationType,
    LicenseType,
    MajorCategory,
    MentalPhase,
    NoteApp,
    Persona,
    QuestionFormat,
    RelationType,
    Resolution,
    ReviewStatus,
    SchoolType,
    SessionType,
    SignaturePattern,
    SocraticStrategy,
    SourceType,
    StepType,
    StudentIntent,
    Subject,
    SubscriptionTier,
    TrackType,
    TurnRole,
    VisualType,
)
from whymath_backend.schema.problem import (
    Condition,
    Problem,
    ProblemRelation,
    ProblemStep,
)
from whymath_backend.schema.provenance import (
    ContentProvenance,
    GenerationLog,
)
from whymath_backend.schema.timeseries import (
    DailyLearningMetrics,
    ProblemSolveTimeDistribution,
    UserBehaviorMetrics,
)
from whymath_backend.schema.user import (
    UserPersonaHistory,
    UserProfile,
    UserStateSnapshot,
    UserTrackHistory,
)

__all__ = [
    # enums
    "Accessibility",
    "AnswerFormat",
    "AssessmentType",
    "AttemptMode",
    "CognitiveType",
    "ConceptLevel",
    "ConceptRole",
    "ContentType",
    "Curriculum",
    "Device",
    "EdgeType",
    "EventType",
    "ExamType",
    "GenerationType",
    "LicenseType",
    "MajorCategory",
    "MentalPhase",
    "NoteApp",
    "Persona",
    "QuestionFormat",
    "RelationType",
    "Resolution",
    "ReviewStatus",
    "SchoolType",
    "SessionType",
    "SignaturePattern",
    "SocraticStrategy",
    "SourceType",
    "StepType",
    "StudentIntent",
    "Subject",
    "SubscriptionTier",
    "TrackType",
    "TurnRole",
    "VisualType",
    # problem
    "Condition",
    "Problem",
    "ProblemRelation",
    "ProblemStep",
    # provenance
    "ContentProvenance",
    "GenerationLog",
    # concept
    "Concept",
    "ConceptEdge",
    "ConceptFusion",
    "ProblemConcept",
    # user
    "UserPersonaHistory",
    "UserProfile",
    "UserStateSnapshot",
    "UserTrackHistory",
    # activity
    "AttemptEvent",
    "LearningSession",
    "ProblemAttempt",
    # dialogue
    "Dialogue",
    "DialogueTurn",
    # assessment
    "Assessment",
    "ConceptMasteryHistory",
    # timeseries
    "DailyLearningMetrics",
    "ProblemSolveTimeDistribution",
    "UserBehaviorMetrics",
]
