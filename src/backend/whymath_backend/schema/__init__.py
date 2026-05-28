"""WhyMath Schema v1.0 도메인 모델 (Pydantic) — 슬라이스 1·2.

설계 정본: `schemas/v1.0/schema_v1.0.md` §3(Problem)·§10(Provenance)·§14.3(ENUM).

Phase 메모: 코드베이스 전체가 *Pydantic-schema-only*(DB 미배포)이므로 이 슬라이스도
순수 Pydantic 모델이다(SQLAlchemy/alembic은 후속 Phase).

공개 심볼:
  - enums: SourceType·ExamType·Curriculum·Subject·QuestionFormat·AnswerFormat·
    SignaturePattern·Persona·VisualType·LicenseType·GenerationType·ReviewStatus·
    StepType·RelationType
  - problem(슬라이스 1): Condition·Problem·ProblemStep·ProblemRelation
  - provenance(슬라이스 2): ContentProvenance·GenerationLog
"""

from whymath_backend.schema.enums import (
    AnswerFormat,
    Curriculum,
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
    "Curriculum",
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
]
