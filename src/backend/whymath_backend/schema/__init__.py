"""WhyMath Schema v1.0 도메인 모델 (Pydantic) — 슬라이스 1·2·3.

설계 정본: `schemas/v1.0/schema_v1.0.md` §3(Problem)·§4(Concept Graph)·§10(Provenance)·
§14.3(ENUM).

Phase 메모: 코드베이스 전체가 *Pydantic-schema-only*(DB 미배포)이므로 이 슬라이스도
순수 Pydantic 모델이다(SQLAlchemy/alembic은 후속 Phase).

공개 심볼:
  - enums: CognitiveType·ConceptLevel·ConceptRole·EdgeType·SourceType·ExamType·
    Curriculum·Subject·QuestionFormat·AnswerFormat·SignaturePattern·Persona·
    VisualType·LicenseType·GenerationType·ReviewStatus·StepType·RelationType
  - problem(슬라이스 1): Condition·Problem·ProblemStep·ProblemRelation
  - provenance(슬라이스 2): ContentProvenance·GenerationLog
  - concept(슬라이스 3): Concept·ConceptEdge·ProblemConcept·ConceptFusion
"""

from whymath_backend.schema.concept import (
    Concept,
    ConceptEdge,
    ConceptFusion,
    ProblemConcept,
)
from whymath_backend.schema.enums import (
    AnswerFormat,
    CognitiveType,
    ConceptLevel,
    ConceptRole,
    Curriculum,
    EdgeType,
    ExamType,
    GenerationType,
    LicenseType,
    Persona,
    QuestionFormat,
    RelationType,
    ReviewStatus,
    SignaturePattern,
    SourceType,
    StepType,
    Subject,
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

__all__ = [
    # enums
    "AnswerFormat",
    "CognitiveType",
    "ConceptLevel",
    "ConceptRole",
    "Curriculum",
    "EdgeType",
    "ExamType",
    "GenerationType",
    "LicenseType",
    "Persona",
    "QuestionFormat",
    "RelationType",
    "ReviewStatus",
    "SignaturePattern",
    "SourceType",
    "StepType",
    "Subject",
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
]
