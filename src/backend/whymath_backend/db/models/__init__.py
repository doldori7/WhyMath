"""ORM 모델 패키지 — 모든 테이블을 import해 `Base.metadata`에 등록한다.

alembic autogenerate(env.py의 `target_metadata = Base.metadata`)가 테이블을 인식하려면
모델 클래스가 *import되어 메타데이터에 등록*되어 있어야 한다. env.py가
`import whymath_backend.db.models`만 하면 이 `__init__`이 아래 모델들을 끌어와 등록한다.

수록 도메인:
  - 도메인1 Problem (§3.1·§3.2): Problem·ProblemStep·ProblemRelation.
  - 도메인2 Concept (§4.2): Concept·ConceptEdge·ProblemConcept·ConceptFusion.
  - 도메인8 Provenance (§10.1): ContentProvenance·GenerationLog.
  - 도메인3 User (§5.1·§5.2): UserProfile·UserTrackHistory·UserPersonaHistory·UserStateSnapshot.
  - 도메인4 Activity (§6.1): LearningSession·ProblemAttempt·AttemptEvent.
  - 도메인5 Dialogue (§7.1): Dialogue·DialogueTurn.
  - 도메인6 Assessment (§8.1): Assessment·ConceptMasteryHistory.
  - 도메인7 TimeSeries (§9.1): DailyLearningMetrics·ProblemSolveTimeDistribution·
    UserBehaviorMetrics.
  - v1.1 CurriculumEntry (다국 커리큘럼 매트릭스 셀).
  - v1.1 TextbookMapping·TextbookUnit (교과서 매핑 — 중첩 → 관계형 2테이블).
  - 슬105 MisconceptionEmbedding (L4 오개념 의미 매칭 pgvector 영속 — `vector` 컬럼 소유).
  - 슬3(개념그래프 아크) ConceptEmbedding (L1 개념 의미검색 pgvector 영속 — UC 키·`vector` 컬럼).
  - 개념그래프 소비 슬1 ConceptNode (L1 개념 메타 PG 프로젝션 — UC 키·검색 enrichment 백킹).
  - P1-2 AchievementStandard·ConceptStandardLink (NCIC 성취기준 영속 + 개념↔성취기준 N:M 링크).
  - PIPA §22-2 ParentalConsent (14세 미만 법정대리인 동의 GRANT 감사 — user_profile FK).
모든 테이블이 한 `Base.metadata`에 모여 문자열 FK 타깃(`problem.problem_id`·
`concept.concept_id`·`user_profile.user_id`·`learning_session.session_id`·
`problem_attempt.attempt_id`·`dialogue.dialogue_id`·`textbook_mapping.isbn` 등)이 해소된다.

도메인4~7의 hypertable 5종(attempt_event·concept_mastery_history·daily_learning_metrics·
problem_solve_time_distribution·user_behavior_metrics)은 ORM에선 *일반 테이블*이다
(create_hypertable 변환은 마이그레이션 레벨 — 메인 처리). §6~§9 DDL이 REFERENCES를 명시하지
않은 컬럼(target_concept_id·stuck_at_concept_id·attempt_event/시계열 FK들)은 FK가 아니다.
"""

from __future__ import annotations

from whymath_backend.db.models.achievement_standard import AchievementStandard
from whymath_backend.db.models.activity import (
    AttemptEvent,
    LearningSession,
    ProblemAttempt,
)
from whymath_backend.db.models.assessment import (
    Assessment,
    ConceptMasteryHistory,
)
from whymath_backend.db.models.audit import DeletionAudit
from whymath_backend.db.models.concept import (
    Concept,
    ConceptEdge,
    ConceptFusion,
    ProblemConcept,
)
from whymath_backend.db.models.concept_embedding import ConceptEmbedding
from whymath_backend.db.models.concept_node import ConceptNode
from whymath_backend.db.models.concept_standard_link import ConceptStandardLink
from whymath_backend.db.models.curriculum_entry import CurriculumEntry
from whymath_backend.db.models.dead_end_log import DeadEndLog
from whymath_backend.db.models.device import DeviceCredential
from whymath_backend.db.models.dialogue import (
    Dialogue,
    DialogueTurn,
)
from whymath_backend.db.models.misconception_embedding import MisconceptionEmbedding
from whymath_backend.db.models.misconception_hypothesis import (
    MisconceptionHypothesisRecord,
)
from whymath_backend.db.models.parental_consent import ParentalConsent
from whymath_backend.db.models.problem import (
    Problem,
    ProblemRelation,
    ProblemStep,
)
from whymath_backend.db.models.provenance import (
    ContentProvenance,
    GenerationLog,
)
from whymath_backend.db.models.refresh_token_session import RefreshTokenSession
from whymath_backend.db.models.solution_node import (
    NodeVerifyStatus,
    SolutionNode,
)
from whymath_backend.db.models.textbook_mapping import (
    TextbookMapping,
    TextbookUnit,
)
from whymath_backend.db.models.timeseries import (
    DailyLearningMetrics,
    ProblemSolveTimeDistribution,
    UserBehaviorMetrics,
)
from whymath_backend.db.models.user import (
    UserPersonaHistory,
    UserProfile,
    UserStateSnapshot,
    UserTrackHistory,
)
from whymath_backend.db.models.verified_solution import (
    VerifiedSolution,
    WhsSolutionGrade,
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
    # 도메인4 Activity
    "LearningSession",
    "ProblemAttempt",
    "AttemptEvent",
    # 도메인5 Dialogue
    "Dialogue",
    "DialogueTurn",
    # 도메인6 Assessment
    "Assessment",
    "ConceptMasteryHistory",
    # 도메인7 TimeSeries
    "DailyLearningMetrics",
    "ProblemSolveTimeDistribution",
    "UserBehaviorMetrics",
    # v1.1 CurriculumEntry
    "CurriculumEntry",
    # v1.1 TextbookMapping
    "TextbookMapping",
    "TextbookUnit",
    # 슬라이스 23: DeviceCredential
    "DeviceCredential",
    # 슬라이스 57: DeletionAudit
    "DeletionAudit",
    # 슬라이스 105: MisconceptionEmbedding (pgvector 영속)
    "MisconceptionEmbedding",
    # WH-1 2단계: MisconceptionHypothesisRecord (활성 오개념 가설 per-student 영속·§8.4)
    "MisconceptionHypothesisRecord",
    # 슬라이스 3(개념그래프 아크): ConceptEmbedding (L1 개념 의미검색 pgvector 영속·UC 키)
    "ConceptEmbedding",
    # 개념그래프 소비 슬1: ConceptNode (L1 개념 메타 PG 프로젝션·UC 키·검색 enrichment 백킹)
    "ConceptNode",
    # WH-S S1: SolutionNode (풀이 경로 트리 노드·§2.1·오프라인 솔버 상태) + 검증 상태 enum
    "SolutionNode",
    "NodeVerifyStatus",
    # WH-S S1 §2.3: DeadEndLog (실패 접근 로그·멱등 (problem,state,action) UNIQUE)
    "DeadEndLog",
    # WH-S S1 §2.4: VerifiedSolution (검증 풀이 저장소·다중 풀이) + 등급 enum(verified/unverified)
    "VerifiedSolution",
    "WhsSolutionGrade",
    # OAuth-a3b: RefreshTokenSession (리프레시 토큰 서버측 취소 allowlist·PK=jti)
    "RefreshTokenSession",
    # PIPA §22-2: ParentalConsent (14세 미만 법정대리인 동의 GRANT 감사·surrogate UUID PK)
    "ParentalConsent",
    # P1-2: AchievementStandard (NCIC 성취기준 영속·norm_id PK·official_code 비유일)
    "AchievementStandard",
    # P1-2: ConceptStandardLink (개념↔성취기준 N:M 연결·norm_id 실 FK·link_id UUID PK)
    "ConceptStandardLink",
]
