"""Schema v1.0 도메인3 학생(User) 모델 (Pydantic) — 슬라이스 4.

설계 정본: `schemas/v1.0/schema_v1.0.md` §5.1(`user_profile`·`user_track_history`·
`user_persona_history` DDL)·§5.2(`user_state_snapshot` DDL). 학생의 학적·입시 트랙·
페르소나·학습 환경·진단 상태·구독·보호자 정보를 담는 도메인(PRD 페르소나 5종, 특성
#27/#47/#48/#71~77/#87/#94).

Phase 메모: 코드베이스 전체가 *Pydantic-schema-only*(DB 미배포) — 이 슬라이스도 순수
Pydantic 모델이다. SQLAlchemy/alembic 매핑은 후속 Phase(슬라이스 1~3 동일 패턴).

컨벤션(`problem.py`·`concept.py`·`provenance.py` 답습):
  - `ConfigDict(extra="forbid", use_enum_values=True, str_strip_whitespace=True)`.
  - enum은 `enums.py`의 `class X(str, Enum)`(이번에 추가된 SchoolType·TrackType·
    MajorCategory·Device·NoteApp·SubscriptionTier·Accessibility + 기존 Persona 재사용).
  - 공유 베이스 클래스 없음(각 모델 독립).

타입 매핑 판단(DDL → Pydantic, 슬라이스 1~3 선례 그대로):
  - `UUID PK` → `uuid.UUID = Field(default_factory=uuid4)`
  - `UUID`(복합 PK 구성요소) → required `uuid.UUID`(slice1 `ProblemRelation` PK 선례)
  - nullable `UUID`(FK) → `uuid.UUID | None`(예: user_id, school_id, embedding_id)
  - `VARCHAR(n)` → `str | None`(max_length=n; NOT NULL이면 required)
  - `INTEGER` → `int | None`(ge/le)
  - `DECIMAL(p,s)` → `float | None`(ge/le); 범위는 DDL 인라인 주석을 따르고, 미명시는
    의미에 맞는 보수값을 골라 각 필드 description에 1줄로 명시(슬라이스 1~3 방식)
  - `DATE` → `datetime.date | None`(TIMESTAMPTZ가 아님에 주의 — target_exam_date)
  - `TIMESTAMPTZ` → `datetime | None`
  - `BOOLEAN DEFAULT FALSE/TRUE` → `bool = False/True`; 기본값 없는 `BOOLEAN` → `bool | None`
  - `enum[]` → `list[Enum]`(default_factory=list)
  - `TEXT[]` → `list[str]`(default_factory=list)
  - `JSONB`(자유형) → `dict[str, Any] | None`; `JSONB` 배열 → `list[dict[str, Any]]`
  - `JSONB`(키→스칼라 맵) → `dict[str, float] | None`(예: concept_mastery {개념코드:숙련도})

개인정보 메모(CLAUDE.md 절대 금기·개인정보보호법, `concept.py` 법적 메모 방침과 동일):
  `user_profile`은 *미성년 민감정보*를 담는다 — 이메일은 `email_hash`(평문 미저장)·
  생일은 `birth_year`(연 단위, 월일 미수집)·보호자 동의는 `parent_consent_at`로 관리한다.
  CLAUDE.md 절대 금기("미성년자 개인정보 분석·마케팅 외부 공유 금지"·"미성년자 채팅
  데이터 평문 저장 금지"·"학부모/14세 미만 동의 절차 준수")를 모델 수준에서 *상기*시키되,
  "is_minor면 parent_consent_at 필수" 같은 cross-field 강제는 *하지 않는다*: 가입 직후
  *동의 대기* 상태(is_minor=True·parent_consent_at=None)가 정당하게 존재하므로 모델
  불변식으로 막으면 그 합법 상태를 표현할 수 없다. 동의 게이팅은 미들웨어
  (`ParentalConsentMiddleware`)·검수/플로우 책임이다. 이는 자유 서술 텍스트라 강제 신호가
  없던 `concept.py` 법적 메모(가짜 validator 금지·문서화만)와 같은 방침이며, 슬라이스 1~2가
  `source_type`/`license`라는 *구조 신호*가 있어 강제 가능했던 것과 대비된다. 또한 이
  도메인에는 자기관계(self-relation) 같은 구조 cross-field 불변식이 없어 validator를 두지
  않는다(없는 게 맞다 — `concept.py` 방침).
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from whymath_backend.schema.enums import (
    Accessibility,
    Device,
    MajorCategory,
    NoteApp,
    Persona,
    Role,
    SchoolType,
    TrackType,
)


# ──────────────────────────────────────────────────────────────────────────
# 핵심: UserProfile (§5.1 user_profile 테이블 — 학생 프로필, ~40필드)
# ──────────────────────────────────────────────────────────────────────────
class UserProfile(BaseModel):
    """학생 프로필 — §5.1 `user_profile`. 학적·입시 트랙·페르소나·학습 환경·진단·구독·
    보호자 정보를 담는 도메인3 핵심 모델(특성 #27/#47/#48/#71~77/#87/#94).

    required는 `persona_primary`(DDL `persona_enum NOT NULL`) 하나뿐이다 — 나머지 필드는
    모두 nullable/기본값. 가입 직후 페르소나만 분류된 *최소 레코드*도 표현할 수 있어야
    하기 때문이다.

    개인정보 메모(모듈 docstring 참조): 이 모델은 *미성년 민감정보*를 담는다(이메일은
    `email_hash`로 해시·생일은 `birth_year` 연 단위만·보호자 동의는 `parent_consent_at`).
    CLAUDE.md 절대 금기(미성년 개인정보 외부 공유·평문 저장 금지·14세 미만/보호자 동의)를
    모델 수준에서 상기시키되, "is_minor면 parent_consent_at 필수" 같은 cross-field 불변식은
    *강제하지 않는다*(동의 대기 상태가 정당히 존재 → 미들웨어·검수/플로우 책임). 가짜
    validator를 만들지 않고 문서화만 하는 방침은 `concept.py` 법적 메모와 동일하다.

    gender·school_region 메모: 둘 다 `str | None`이다(enum 아님). §14.3에 정의가 없고
    §5.1 DDL 주석도 불완전하기 때문이다(각 필드 description 참조). 추후 Kiki가 값을
    확정하면 enum으로 승격한다(`enums.py` 섹션 주석의 결정과 동일).
    """

    model_config = ConfigDict(
        # 추가 필드 금지 — Pydantic 모델이 스키마의 단일 진실
        extra="forbid",
        # 직렬화 시 enum 값을 그대로(한글 값 보존: school_type="일반고" 등)
        use_enum_values=True,
        # 문자열 양끝 공백 제거
        str_strip_whitespace=True,
    )

    # ===== 기본 식별 =====
    user_id: uuid.UUID = Field(
        default_factory=uuid4,
        description="학생 PK (UUID)",
    )

    # ===== 기본 정보 (개인정보 보호) =====
    email_hash: str | None = Field(
        default=None,
        description="이메일 해시(UNIQUE, 평문 미저장 — 미성년 개인정보 보호)",
        max_length=64,
    )
    nickname: str | None = Field(
        default=None,
        description="닉네임(실명 아님)",
        max_length=50,
    )
    birth_year: int | None = Field(
        default=None,
        description="출생 연도 — 연 단위만 수집(월일 미수집, 미성년 개인정보 최소화). DDL에 "
        "범위 미명시 → 중·고생 대상이라 1900~2100의 보수적 4자리 연도 범위로 설정.",
        ge=1900,
        le=2100,
    )
    gender: str | None = Field(
        default=None,
        description="성별 — enum 값 미확정(§14.3 정의 없음·DDL 주석 '선택 입력'으로 값 "
        "미기재) → str, 추후 Kiki 결정 시 enum 승격. 미성년 민감정보라 닫힌 카테고리 "
        "강제 부적절.",
        max_length=32,
    )

    # ===== 학적 정보 (특성 #71~77) =====
    school_type: SchoolType | None = Field(
        default=None,
        description="학교 유형 — 일반고/자사고_전국/.../검정고시(§14.3 school_type_enum 12종)",
    )
    school_region: str | None = Field(
        default=None,
        description="학교 지역 — enum 값 미확정(§14.3 정의 없음·DDL 주석 '강남/대치/지방/...'로 "
        "명시적 미완결, v1.1은 시도교육청 코드로 모델링) → str, 추후 Kiki 결정 시 enum 승격.",
        max_length=64,
    )
    # school_id(FK 없는 고아 컬럼)는 ADMIN-02(2026-08-08)에서 드롭 — 소비처 0(실측).
    grade: int | None = Field(
        default=None,
        description="학년 — 10/11/12(고1~고3)/13(N수1)/14(N수2). DDL 주석 범위(10~14)를 "
        "그대로 ge=10 le=14로 설정.",
        ge=10,
        le=14,
    )

    # ===== 입시 트랙 (특성 #51~70) =====
    track_type: list[TrackType] = Field(
        default_factory=list,
        description="입시 트랙 배열 — 정시/수시학종/수시교과/수시논술/MMI/특기자/농어촌/특례",
    )
    target_universities: list[dict[str, Any]] = Field(
        default_factory=list,
        description='목표 대학 목록 [{"univ":"서울대","major":"의예","priority":1}, ...]'
        "(자유형 JSONB)",
    )
    target_major_category: MajorCategory | None = Field(
        default=None,
        description="목표 전공 계열 — 의대/약대/치대/한의대/이공계/인문계/경상계/예체능",
    )

    # ===== 학습 목표 (특성 #28, #48) =====
    target_grade: int | None = Field(
        default=None,
        description="목표 등급 1~9 (DDL 주석 '1~9')",
        ge=1,
        le=9,
    )
    target_score: int | None = Field(
        default=None,
        description="목표 표준점수. DDL에 범위 미명시 → 점수는 음수가 될 수 없어 ge=0만 설정.",
        ge=0,
    )
    target_exam_date: date | None = Field(
        default=None,
        description="목표 수능일 — DATE 타입(TIMESTAMPTZ 아님, 날짜만)",
    )

    # ===== 페르소나 분류 (PRD 페르소나 5종) =====
    persona_primary: Persona = Field(
        ...,
        description="주 페르소나 — A_일반고고3/B_자사고N수/C_검정고시N수/D_학종고2/"
        "E_홈스쿨링영재 (NOT NULL → 유일한 required)",
    )
    persona_secondary: Persona | None = Field(
        default=None,
        description="보조 페르소나(혼합 페르소나일 때)",
    )
    persona_confidence: float | None = Field(
        default=None,
        description="페르소나 분류 신뢰도 0-1 (DDL 'DECIMAL(3,2)')",
        ge=0.0,
        le=1.0,
    )

    # ===== 학습 환경 =====
    primary_device: Device | None = Field(
        default=None,
        description="주 사용 기기 — 아이패드/iPhone/안드로이드폰/PC",
    )
    has_apple_pencil: bool | None = Field(
        default=None,
        description="애플펜슬 보유 여부(기본값 없는 BOOLEAN → 미응답=None 구분)",
    )
    note_app: NoteApp | None = Field(
        default=None,
        description="필기 앱 — 굿노트/노타빌리티/플렉슬/없음",
    )

    # ===== 현재 학력 진단 (초기 + 갱신) =====
    current_grade_estimate: float | None = Field(
        default=None,
        description="현재 등급 추정 1.0-9.0 (DDL 주석 '1.0-9.0')",
        ge=1.0,
        le=9.0,
    )
    current_grade_updated_at: datetime | None = Field(
        default=None,
        description="현재 등급 추정 갱신 시각",
    )
    diagnostic_completed: bool = Field(
        default=False,
        description="진단 완료 여부 (BOOLEAN DEFAULT FALSE)",
    )
    diagnostic_completed_at: datetime | None = Field(
        default=None,
        description="진단 완료 시각",
    )

    # ===== 사교육 사용 현황 =====
    uses_inkang: bool | None = Field(
        default=None,
        description="인강 사용 여부(기본값 없는 BOOLEAN → 미응답=None)",
    )
    inkang_provider: list[str] = Field(
        default_factory=list,
        description="인강 제공자 배열 (예: ['메가스터디','이투스'])",
    )
    uses_offline_academy: bool | None = Field(
        default=None,
        description="오프라인 학원 사용 여부(기본값 없는 BOOLEAN → 미응답=None)",
    )
    monthly_education_spend: int | None = Field(
        default=None,
        description="월 사교육비(원). DDL에 범위 미명시 → 금액이라 음수 불가 ge=0만 설정.",
        ge=0,
    )

    # ===== 결제·구독 =====
    # subscription_tier·subscription_started_at·subscription_renewed_at은 ADMIN-02
    # (2026-08-08)에서 드롭 — 결제 시스템 부재로 소비처 0(실측).

    # ===== 보호자 정보 (특성 #94, 미성년자 보호) =====
    is_minor: bool | None = Field(
        default=None,
        description="미성년자 여부(기본값 없는 BOOLEAN → 미판정=None)",
    )
    parent_consent_at: datetime | None = Field(
        default=None,
        description="보호자 동의 시각(미성년 동의 절차 — None이면 동의 대기/미해당)",
    )
    parent_email_hash: str | None = Field(
        default=None,
        description="보호자 이메일 해시(평문 미저장)",
        max_length=64,
    )

    # ===== 접근성 (특성 #47) =====
    accessibility_needs: list[Accessibility] = Field(
        default_factory=list,
        description="접근성 필요 배열 — 시각약자/색약/큰글씨/음성안내/시간연장",
    )

    # ===== 인가(authorization) 역할 (SEC-07 D1 — 콘텐츠 CUD 게이팅) =====
    role: Role = Field(
        default=Role.STUDENT,
        validate_default=True,
        description=(
            "인가 역할 v0 2값(student/content_admin) — server_default='student'가 기존 행도 "
            "백필. `validate_default=True`: Role이 str mixin이 아니라(enums.py 참조) 기본값도 "
            "검증 경로를 태워야 use_enum_values 직렬화가 일관된다."
        ),
    )

    # ===== 운영 메타 =====
    created_at: datetime | None = Field(default=None, description="생성 시각")
    last_active_at: datetime | None = Field(default=None, description="마지막 활동 시각")
    is_active: bool = Field(default=True, description="활성 여부 (BOOLEAN DEFAULT TRUE)")
    is_deleted: bool = Field(
        default=False,
        description="삭제 표시 (BOOLEAN DEFAULT FALSE, 개인정보 삭제 요청 대응)",
    )
    deleted_at: datetime | None = Field(default=None, description="삭제 시각")


# ──────────────────────────────────────────────────────────────────────────
# 보조: UserTrackHistory (§5.1 user_track_history — 진로 변경 이력)
# ──────────────────────────────────────────────────────────────────────────
class UserTrackHistory(BaseModel):
    """학생 진로 변경 이력 — §5.1 `user_track_history`(입시 1년 사이클에서 자주 바뀜).

    `track_before`/`track_after`는 변경 전후 트랙 스냅샷(자유형 JSONB)이다. PK
    `history_id`만 있고 나머지는 모두 nullable(DDL 그대로).
    """

    model_config = ConfigDict(
        extra="forbid",
        use_enum_values=True,
        str_strip_whitespace=True,
    )

    history_id: uuid.UUID = Field(default_factory=uuid4, description="이력 PK (UUID)")
    user_id: uuid.UUID | None = Field(
        default=None,
        description="학생 FK (user_profile 참조)",
    )
    changed_at: datetime | None = Field(default=None, description="변경 시각")
    track_before: dict[str, Any] | None = Field(
        default=None,
        description="변경 전 트랙 스냅샷(자유형 JSONB)",
    )
    track_after: dict[str, Any] | None = Field(
        default=None,
        description="변경 후 트랙 스냅샷(자유형 JSONB)",
    )
    reason: str | None = Field(default=None, description="변경 사유(자유 서술)")


# ──────────────────────────────────────────────────────────────────────────
# 보조: UserPersonaHistory (§5.1 user_persona_history — 페르소나 분류 이력)
# ──────────────────────────────────────────────────────────────────────────
class UserPersonaHistory(BaseModel):
    """페르소나 분류 이력 — §5.1 `user_persona_history`(페르소나는 시간에 따라 변함).

    복합 PK `(user_id, detected_at)` — DB 제약. PK 구성요소는 NOT NULL이므로 `user_id`·
    `detected_at` 둘 다 required로 둔다(슬라이스 1 `ProblemRelation`·슬라이스 3
    `ProblemConcept`가 PK 구성요소를 모두 required로 둔 선례 답습).

    `signals`는 어떤 행동 신호로 페르소나를 판정했는지 담는 자유형 JSONB다.
    """

    model_config = ConfigDict(
        extra="forbid",
        use_enum_values=True,
        str_strip_whitespace=True,
    )

    user_id: uuid.UUID = Field(..., description="학생 FK (복합 PK 구성요소)")
    detected_at: datetime = Field(..., description="페르소나 판정 시각 (복합 PK 구성요소)")
    persona: Persona | None = Field(
        default=None,
        description="판정된 페르소나 — A_일반고고3/B_자사고N수/.../E_홈스쿨링영재",
    )
    confidence: float | None = Field(
        default=None,
        description="판정 신뢰도 0-1 (DDL 'DECIMAL(3,2)')",
        ge=0.0,
        le=1.0,
    )
    signals: dict[str, Any] | None = Field(
        default=None,
        description="판정 근거 행동 신호(자유형 JSONB)",
    )


# ──────────────────────────────────────────────────────────────────────────
# 핵심: UserStateSnapshot (§5.2 user_state_snapshot — 시점별 학습 상태)
# ──────────────────────────────────────────────────────────────────────────
class UserStateSnapshot(BaseModel):
    """학생 시점별 학습 상태 스냅샷 — §5.2 `user_state_snapshot`(페르소나 임베딩 + 진단
    결과, 특성 #16/#44).

    종합 학력(등급·표준점수·백분위)·단원별/패턴별 숙련도·시간 관리·멘탈 신호를 한 시점에
    묶은 스냅샷이다. PK `snapshot_id`만 있고 나머지는 모두 nullable(DDL 그대로).

    `concept_mastery`·`pattern_mastery`는 {코드: 숙련도0-1} 형태의 키→스칼라 맵이라
    `dict[str, float]`로 둔다. `avg_solve_time_by_difficulty`는 {easy:60, medium:180,
    hard:600}처럼 값이 초(int) 단위지만 난이도 키 집합이 자유형이라 `dict[str, Any]`로 둔다.

    `embedding_id`는 벡터 저장소(pgvector·Postgres 동거·슬98) 참조일 뿐 *임베딩 벡터 저장이
    아니다* (`concept.py` `Concept.embedding_id`와 동일).
    """

    model_config = ConfigDict(
        extra="forbid",
        use_enum_values=True,
        str_strip_whitespace=True,
    )

    snapshot_id: uuid.UUID = Field(default_factory=uuid4, description="스냅샷 PK (UUID)")
    user_id: uuid.UUID | None = Field(
        default=None,
        description="학생 FK (user_profile 참조)",
    )
    snapshot_at: datetime | None = Field(default=None, description="스냅샷 시각")

    # ===== 종합 학력 =====
    estimated_grade: float | None = Field(
        default=None,
        description="추정 등급. DDL에 범위 미명시 → 등급 척도이므로 current_grade_estimate "
        "선례를 따라 ge=1 le=9 설정.",
        ge=1.0,
        le=9.0,
    )
    estimated_score: int | None = Field(
        default=None,
        description="추정 표준점수. DDL에 범위 미명시 → 점수라 음수 불가 ge=0만 설정.",
        ge=0,
    )
    estimated_percentile: float | None = Field(
        default=None,
        description="추정 백분위 0-100 (DDL 'DECIMAL(5,2)' → 백분위 척도이므로 ge=0 le=100)",
        ge=0.0,
        le=100.0,
    )

    # ===== 단원별/패턴별 숙련도 (특성 #16, #44) =====
    concept_mastery: dict[str, float] | None = Field(
        default=None,
        description='단원(개념)별 숙련도 {"CAL-INT-DEF":0.8, ...}(개념코드→숙련도 0-1)',
    )
    pattern_mastery: dict[str, float] | None = Field(
        default=None,
        description='시그니처 패턴별 숙련도 {"COMPOSITE_DIFFERENTIABILITY":0.6, ...}(0-1)',
    )

    # ===== 시간 관리 능력 =====
    avg_solve_time_by_difficulty: dict[str, Any] | None = Field(
        default=None,
        description='난이도별 평균 풀이 시간(초) {"easy":60,"medium":180,"hard":600}'
        "(난이도 키 자유형 JSONB)",
    )
    time_management_score: float | None = Field(
        default=None,
        description="시간 관리 점수 0-1 (DDL 주석 '0-1')",
        ge=0.0,
        le=1.0,
    )

    # ===== 멘탈·컨디션 신호 =====
    consecutive_active_days: int | None = Field(
        default=None,
        description="연속 학습일. DDL에 범위 미명시 → 일수라 음수 불가 ge=0만 설정.",
        ge=0,
    )
    avg_session_quality: float | None = Field(
        default=None,
        description="집중도 평균. DDL에 범위 미명시('DECIMAL(3,2)') → 정규화 품질 점수로 보아 "
        "time_management_score 선례를 따라 ge=0 le=1 설정.",
        ge=0.0,
        le=1.0,
    )

    # ===== 임베딩 (pgvector·Postgres 동거 참조·슬98) =====
    embedding_id: uuid.UUID | None = Field(
        default=None,
        description="벡터 저장소(pgvector·Postgres) 참조 ID(임베딩 벡터 저장 아님)",
    )
