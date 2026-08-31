"""WhyMath Schema 도메인 모델 (Pydantic) — 슬라이스 1~7(v1.0 도메인 완결) + 8a(v1.1 이식).

설계 정본: `schemas/v1.0/schema_v1.0.md` §3(Problem)·§4(Concept Graph)·§5(User)·
§6(Activity)·§7(Dialogue)·§8(Assessment)·§9(Time Series)·§10(Provenance)·§14.3(ENUM);
슬라이스 8a는 `schemas/v1.1/curriculum_entry.schema.yaml`(v1.0 도메인 밖 다국 커리큘럼 셀).

Phase 메모: 코드베이스 전체가 *Pydantic-schema-only*(DB 미배포)이므로 이 슬라이스도
순수 Pydantic 모델이다(SQLAlchemy/alembic은 후속 Phase).

공개 심볼:
  - enums: Accessibility·AnswerFormat·AssessmentType·AttemptMode·CognitiveType·
    ConceptLevel·ConceptRole·ContentType·Curriculum·CurriculumLicense·Device·EdgeType·
    EventType·ExamType·GenerationType·LegalReviewStatus·LicenseType·MajorCategory·MentalPhase·
    NoteApp·Persona·QuestionFormat·RelationType·RequiredDepth·Resolution·ReviewStatus·
    SchoolType·SessionType·SignaturePattern·SocraticStrategy·SourceType·StepType·StudentIntent·
    Subject·SubscriptionTier·TrackType·TurnRole·VisualType·VisualizationStyle·VisualizationType
  - problem(슬라이스 1): Condition·Problem·ProblemStep·ProblemRelation
  - provenance(슬라이스 2): ContentProvenance·GenerationLog
  - concept(슬라이스 3): Concept·ConceptEdge·ProblemConcept·ConceptFusion
  - user(슬라이스 4): UserProfile·UserTrackHistory·UserPersonaHistory·UserStateSnapshot
  - activity(슬라이스 5): LearningSession·ProblemAttempt·AttemptEvent
  - dialogue(슬라이스 5): Dialogue·DialogueTurn
  - assessment(슬라이스 6): Assessment·ConceptMasteryHistory
  - timeseries(슬라이스 7): DailyLearningMetrics·ProblemSolveTimeDistribution·
    UserBehaviorMetrics
  - curriculum(슬라이스 8a, v1.1 이식): CurriculumEntry
  - textbook(슬라이스 8b, v1.1 이식): TextbookMapping·TextbookToneProfile·TextbookUnit
  - visualization(슬라이스 90): Visualization
  - standard(P1-2): AchievementStandard·ConceptStandardLink
  - ocr(L5 OCR): BBox·OcrRegion·OcrResult
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
from whymath_backend.schema.curriculum_entry import (
    CurriculumEntry,
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
    CurriculumLicense,
    Device,
    EdgeType,
    EventType,
    ExamType,
    GenerationType,
    LegalReviewStatus,
    LicenseType,
    MajorCategory,
    MentalPhase,
    NoteApp,
    Persona,
    QuestionFormat,
    RelationType,
    RequiredDepth,
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
    VisualizationStyle,
    VisualizationType,
    VisualType,
)
from whymath_backend.schema.ocr import (
    BBox,
    OcrRegion,
    OcrResult,
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
    canonical_input_json,
    input_snapshot_sha256,
    restore_input_snapshot,
    text_sha256,
)
from whymath_backend.schema.standard import (
    AchievementStandard,
    ConceptStandardLink,
)
from whymath_backend.schema.textbook_mapping import (
    TextbookMapping,
    TextbookToneProfile,
    TextbookUnit,
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
from whymath_backend.schema.visualization import (
    Visualization,
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
    "CurriculumLicense",
    "Device",
    "EdgeType",
    "EventType",
    "ExamType",
    "GenerationType",
    "LegalReviewStatus",
    "LicenseType",
    "MajorCategory",
    "MentalPhase",
    "NoteApp",
    "Persona",
    "QuestionFormat",
    "RelationType",
    "RequiredDepth",
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
    "VisualizationStyle",
    "VisualizationType",
    # problem
    "Condition",
    "Problem",
    "ProblemRelation",
    "ProblemStep",
    # provenance
    "ContentProvenance",
    "GenerationLog",
    "canonical_input_json",
    "input_snapshot_sha256",
    "restore_input_snapshot",
    "text_sha256",
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
    # curriculum
    "CurriculumEntry",
    # textbook
    "TextbookMapping",
    "TextbookToneProfile",
    "TextbookUnit",
    # visualization (슬라이스 90)
    "Visualization",
    # standard (P1-2)
    "AchievementStandard",
    "ConceptStandardLink",
    # ocr (L5 OCR)
    "BBox",
    "OcrRegion",
    "OcrResult",
]
