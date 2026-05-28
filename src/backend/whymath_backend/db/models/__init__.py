"""ORM 모델 패키지 — 모든 테이블을 import해 `Base.metadata`에 등록한다.

alembic autogenerate(env.py의 `target_metadata = Base.metadata`)가 테이블을 인식하려면
모델 클래스가 *import되어 메타데이터에 등록*되어 있어야 한다. env.py가
`import whymath_backend.db.models`만 하면 이 `__init__`이 아래 모델들을 끌어와 등록한다.

수록 도메인:
  - 도메인1 Problem (§3.1·§3.2): Problem·ProblemStep·ProblemRelation.
  - 도메인2 Concept (§4.2): Concept·ConceptEdge·ProblemConcept·ConceptFusion.
  - 도메인8 Provenance (§10.1): ContentProvenance·GenerationLog.
  - 도메인3 User (§5.1·§5.2): UserProfile·UserTrackHistory·UserPersonaHistory·UserStateSnapshot.
  - v1.1 CurriculumEntry (다국 커리큘럼 매트릭스 셀).
  - v1.1 TextbookMapping·TextbookUnit (교과서 매핑 — 중첩 → 관계형 2테이블).
모든 테이블이 한 `Base.metadata`에 모여 문자열 FK 타깃(`problem.problem_id`·
`concept.concept_id`·`user_profile.user_id`·`textbook_mapping.isbn` 등)이 해소된다.
"""

from __future__ import annotations

from whymath_backend.db.models.concept import (
    Concept,
    ConceptEdge,
    ConceptFusion,
    ProblemConcept,
)
from whymath_backend.db.models.curriculum_entry import CurriculumEntry
from whymath_backend.db.models.problem import (
    Problem,
    ProblemRelation,
    ProblemStep,
)
from whymath_backend.db.models.provenance import (
    ContentProvenance,
    GenerationLog,
)
from whymath_backend.db.models.textbook_mapping import (
    TextbookMapping,
    TextbookUnit,
)
from whymath_backend.db.models.user import (
    UserPersonaHistory,
    UserProfile,
    UserStateSnapshot,
    UserTrackHistory,
)

__all__ = [
    # 도메인1 Problem
    "Problem",
    "ProblemStep",
    "ProblemRelation",
    # 도메인2 Concept
    "Concept",
    "ConceptEdge",
    "ProblemConcept",
    "ConceptFusion",
    # 도메인8 Provenance
    "ContentProvenance",
    "GenerationLog",
    # 도메인3 User
    "UserProfile",
    "UserTrackHistory",
    "UserPersonaHistory",
    "UserStateSnapshot",
    # v1.1 CurriculumEntry
    "CurriculumEntry",
    # v1.1 TextbookMapping
    "TextbookMapping",
    "TextbookUnit",
]
