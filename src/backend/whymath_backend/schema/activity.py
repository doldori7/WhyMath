"""Schema v1.0 도메인4 학습 활동(Activity) 모델 (Pydantic) — 슬라이스 5.

설계 정본: `schemas/v1.0/schema_v1.0.md` §6.1(`learning_session`·`problem_attempt`·
`attempt_event` DDL 3테이블). 학생이 앱을 한 번 열고 닫는 *세션*, 그 안의 한 문제
*풀이 시도*, 시도 중 발생한 단계별 *실시간 이벤트*를 담는 도메인(특성 #2/#39/#42/
#91/#95/#96 — 콴다 대비 차별 측정 used_socratic vs used_solution_view).

Phase 메모: 코드베이스 전체가 *Pydantic-schema-only*(DB 미배포) — 이 슬라이스도 순수
Pydantic 모델이다. SQLAlchemy/alembic 매핑은 후속 Phase(슬라이스 1~4 동일 패턴).

컨벤션(`problem.py`·`concept.py`·`user.py` 답습):
  - `ConfigDict(extra="forbid", use_enum_values=True, str_strip_whitespace=True)`.
  - enum은 `enums.py`의 `class X(str, Enum)`(SessionType·AttemptMode·EventType 신규 +
    기존 Device 재사용 — learning_session.device_used).
  - 공유 베이스 클래스 없음(각 모델 독립).

타입 매핑 판단(DDL → Pydantic, 슬라이스 1~4 선례 그대로):
  - `UUID PK` → `uuid.UUID = Field(default_factory=uuid4)`
  - `UUID`(복합 PK 구성요소) → required `uuid.UUID`(slice1 `ProblemRelation`·slice4
    `UserPersonaHistory` PK 선례)
  - nullable `UUID`(FK) → `uuid.UUID | None`(예: user_id, session_id, problem_id)
  - `BIGSERIAL`(시계열 PK) → `int | None = Field(default=None, ge=1)` — DB가 할당하는
    값이라 클라이언트 기본값이 없다(UUID PK의 default_factory와 달리 default_factory
    불가). `attempt_event.event_id`에서만 사용.
  - `VARCHAR(n)` → `str | None`(max_length=n; enum 아닌 자유 문자열, 예: network_type)
  - `INTEGER` → `int | None`(ge/le)
  - `DECIMAL(p,s)` → `float | None`(ge/le); 범위는 DDL 인라인 주석을 따르고, 미명시는
    의미에 맞는 보수값을 골라 각 필드 description에 1줄로 명시(슬라이스 1~4 방식)
  - `TIMESTAMPTZ` → `datetime | None`; `TIMESTAMPTZ NOT NULL` → required `datetime`
    (예: attempt_event.event_at)
  - `BOOLEAN`(기본값 없음) → `bool | None`(미응답=None 구분 — `user.py` 선례)
  - `JSONB`(자유형) → `dict[str, Any] | None`(예: ocr_result, event_data)
  - `JSONB` 배열 → `list[dict[str, Any]]`(default_factory=list)(예: step_times)

개인정보 메모(CLAUDE.md 절대 금기·개인정보보호법, `user.py`·`concept.py` 방침과 동일):
  `problem_attempt`의 `student_answer`(학생 제출 답)·`handwriting_uri`(손글씨 풀이
  이미지 URI)·`ocr_result`(OCR 인식 결과)는 *미성년 학생 풀이 데이터*다. CLAUDE.md
  절대 금기("학생 풀이 데이터를 명시적 동의 없이 학습에 사용 금지"·"미성년자 채팅·풀이
  데이터 평문 저장 금지")는 *저장·동의 계층* 책임이다 — 암호화 저장·동의 게이팅은
  인프라/미들웨어(`ParentalConsentMiddleware`)·검수 플로우가 시행한다. 모델 필드는
  그 사실을 *상기*시키되 cross-field 강제(가짜 validator)를 두지 않는다(슬라이스 1~2가
  `source_type`/`license`라는 *구조 신호*로 강제 가능했던 것과 달리, 여기엔 강제할 구조
  신호가 없다 — `user.py`/`concept.py` 법적 메모와 같은 방침: 문서화만).

  또한 이 도메인에는 자기관계(self-relation) 같은 구조 cross-field 불변식이 없다.
  카운트 정합(예: problems_attempted ≥ problems_completed, total turns 등)은
  중간 집계·동시성으로 항상 성립하지 않을 수 있어 모델 불변식으로 강제하지 않는다
  (`concept.py` 방침 — 없는 게 맞다).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from whymath_backend.schema.enums import (
    AttemptMode,
    Device,
    EventType,
    SessionType,
)


# ──────────────────────────────────────────────────────────────────────────
# 핵심: LearningSession (§6.1 learning_session — 한 번 앱 열고 닫을 때까지)
# ──────────────────────────────────────────────────────────────────────────
class LearningSession(BaseModel):
    """학습 세션 — §6.1 `learning_session`(앱 진입~종료 한 단위).

    PK `session_id`만 있고 나머지는 모두 nullable/기본값(DDL 그대로 — `started_at`도
    DDL은 `DEFAULT NOW()`지만 클라이언트가 시작 시각을 채우는 운영 메타라 Optional로
    둔다, 슬라이스 1~4 `created_at` 선례).

    `device_used`는 기존 `Device` enum(아이패드/iPhone/안드로이드폰/PC) 재사용,
    `network_type`은 §6.1 DDL이 `VARCHAR(20)`이라 enum이 아니라 `str`로 둔다(값 미명시).
    """

    model_config = ConfigDict(
        # 추가 필드 금지 — Pydantic 모델이 스키마의 단일 진실
        extra="forbid",
        # 직렬화 시 enum 값을 그대로(한글 값 보존: session_type="자유학습" 등)
        use_enum_values=True,
        # 문자열 양끝 공백 제거
        str_strip_whitespace=True,
    )

    # ===== 기본 식별 =====
    session_id: uuid.UUID = Field(
        default_factory=uuid4,
        description="세션 PK (UUID)",
    )
    user_id: uuid.UUID | None = Field(
        default=None,
        description="학생 FK (user_profile 참조)",
    )

    # ===== 시간 =====
    started_at: datetime | None = Field(
        default=None,
        description="세션 시작 시각 (DDL DEFAULT NOW() — 운영 메타라 Optional)",
    )
    ended_at: datetime | None = Field(default=None, description="세션 종료 시각")
    duration_seconds: int | None = Field(
        default=None,
        description="세션 지속 시간(초). DDL에 범위 미명시 → 시간 길이라 음수 불가 ge=0만 설정.",
        ge=0,
    )

    # ===== 세션 유형·목표 =====
    session_type: SessionType | None = Field(
        default=None,
        description="세션 유형 — 자유학습/실전모의고사/단원집중/약점보완/AI추천",
    )
    target_concept_id: uuid.UUID | None = Field(
        default=None,
        description="이번 세션의 학습 목표 개념 FK",
    )

    # ===== 진행 카운트 =====
    problems_attempted: int | None = Field(
        default=None,
        description="시도한 문제 수. DDL에 범위 미명시 → 개수라 음수 불가 ge=0만 설정.",
        ge=0,
    )
    problems_completed: int | None = Field(
        default=None,
        description="완료한 문제 수. DDL에 범위 미명시 → 개수라 음수 불가 ge=0만 설정.",
        ge=0,
    )
    problems_correct: int | None = Field(
        default=None,
        description="정답 문제 수. DDL에 범위 미명시 → 개수라 음수 불가 ge=0만 설정.",
        ge=0,
    )

    # ===== 세션 품질 신호 =====
    focus_score: float | None = Field(
        default=None,
        description="집중도(앱 전환·지연 분석). DDL 'DECIMAL(3,2)' → 정규화 점수로 보아 "
        "ge=0 le=1 설정(`user.py` time_management_score 선례).",
        ge=0.0,
        le=1.0,
    )
    engagement_score: float | None = Field(
        default=None,
        description="Socratic 응답 적극성. DDL 'DECIMAL(3,2)' → 정규화 점수로 보아 "
        "ge=0 le=1 설정.",
        ge=0.0,
        le=1.0,
    )

    # ===== 환경 =====
    device_used: Device | None = Field(
        default=None,
        description="사용 기기 — 아이패드/iPhone/안드로이드폰/PC(기존 Device enum 재사용)",
    )
    network_type: str | None = Field(
        default=None,
        description="네트워크 유형 — §6.1 DDL이 VARCHAR(20)이라 enum 아닌 str(값 미명시, "
        "예: 'wifi'/'5g'). 추후 값 확정 시 enum 승격.",
        max_length=20,
    )


# ──────────────────────────────────────────────────────────────────────────
# 핵심: ProblemAttempt (§6.1 problem_attempt — 한 문제 풀이 시작~종료)
# ──────────────────────────────────────────────────────────────────────────
class ProblemAttempt(BaseModel):
    """문항 풀이 시도 — §6.1 `problem_attempt`(한 문제 풀이 1단위, 특성 #2/#39/#42/#95/#96).

    PK `attempt_id`만 있고 나머지는 모두 nullable/기본값(DDL 그대로). `used_socratic` vs
    `used_solution_view`로 콴다 대비 차별(스스로 사고 vs 답 보기)을 측정한다(특성 #96).

    개인정보 메모(모듈 docstring 참조): `student_answer`·`handwriting_uri`·`ocr_result`는
    *미성년 학생 풀이 데이터*다. CLAUDE.md 절대 금기(학생 풀이 동의 없는 학습 사용 금지·
    미성년 데이터 평문 저장 금지)는 *저장·동의 계층*(암호화·미들웨어·검수) 책임이며,
    이 모델 필드는 그 사실을 *상기*시키되 가짜 validator를 두지 않는다(문서화만 —
    `user.py`/`concept.py` 방침과 동일). 여기엔 강제할 구조 신호가 없다.
    """

    model_config = ConfigDict(
        extra="forbid",
        use_enum_values=True,
        str_strip_whitespace=True,
    )

    # ===== 기본 식별 =====
    attempt_id: uuid.UUID = Field(
        default_factory=uuid4,
        description="시도 PK (UUID)",
    )
    user_id: uuid.UUID | None = Field(
        default=None,
        description="학생 FK (user_profile 참조)",
    )
    session_id: uuid.UUID | None = Field(
        default=None,
        description="소속 세션 FK (learning_session 참조)",
    )
    problem_id: uuid.UUID | None = Field(
        default=None,
        description="문제 FK (problem 참조)",
    )

    # ===== 시간 =====
    started_at: datetime | None = Field(default=None, description="풀이 시작 시각")
    ended_at: datetime | None = Field(default=None, description="풀이 종료 시각")
    duration_seconds: int | None = Field(
        default=None,
        description="실제 풀이 시간(초). DDL에 범위 미명시 → 시간 길이라 음수 불가 ge=0만 설정.",
        ge=0,
    )

    # ===== 결과 =====
    is_correct: bool | None = Field(
        default=None,
        description="정답 여부(기본값 없는 BOOLEAN → 미채점=None 구분)",
    )
    student_answer: str | None = Field(
        default=None,
        description="학생이 제출한 답 — *미성년 풀이 데이터*(평문 저장 금지는 저장계층 책임, "
        "모듈 docstring 참조)",
    )
    # ASM-06 신규: "몇 번 보기를 골랐는가" — student_answer(자유텍스트)엔 이 개념이 없어
    # distractor_map 역추적(l4.misconception.distractor_link)이 불가능했다. *미성년 풀이
    # 데이터*(student_answer와 동일 민감도, 모듈 docstring 참조).
    selected_choice_index: int | None = Field(
        default=None,
        description="학생이 실제로 고른 객관식 보기의 0-기반 인덱스(`Problem.choices` 위치). "
        "자유응답형 등 객관식이 아니면 None. distractor_map 대조로 오개념 역추적에 쓰인다(ASM-06).",
        ge=0,
    )
    confidence_self_reported: float | None = Field(
        default=None,
        description="학생 자기 평가 확신도. DDL 'DECIMAL(3,2)' → 정규화 신호로 보아 "
        "ge=0 le=1 설정.",
        ge=0.0,
        le=1.0,
    )

    # ===== 풀이 방식 (특성 #96) =====
    attempt_mode: AttemptMode | None = Field(
        default=None,
        description="풀이 방식 — 자유풀이/Socratic대화/힌트제공/풀이공개",
    )
    used_socratic: bool | None = Field(
        default=None,
        description="Socratic 대화 사용 여부(기본값 없는 BOOLEAN → 미응답=None, 특성 #96)",
    )
    used_hint: bool | None = Field(
        default=None,
        description="힌트 사용 여부(기본값 없는 BOOLEAN → 미응답=None)",
    )
    used_solution_view: bool | None = Field(
        default=None,
        description="풀이 보기 사용 여부(기본값 없는 BOOLEAN → 미응답=None, 특성 #96 콴다 대비)",
    )

    # ===== 풀이 이미지/PDF (특성 #95) =====
    handwriting_uri: str | None = Field(
        default=None,
        description="손글씨 풀이 이미지 URI(MinIO) — *미성년 풀이 데이터*(저장계층 보호 책임, "
        "모듈 docstring 참조)",
    )
    ocr_result: dict[str, Any] | None = Field(
        default=None,
        description="OCR 인식 결과(자유형 JSONB) — *미성년 풀이 데이터*(저장계층 보호 책임, "
        "모듈 docstring 참조)",
    )

    # ===== 막힌 지점 분석 =====
    stuck_at_step: int | None = Field(
        default=None,
        description="어느 단계에서 막혔는지(단계 번호). DDL에 범위 미명시 → 단계는 1부터라 "
        "ge=1 설정(`problem.py` step_order 선례).",
        ge=1,
    )
    stuck_at_concept_id: uuid.UUID | None = Field(
        default=None,
        description="막힌 개념 FK (concept 참조)",
    )

    # ===== 시간 관리 =====
    time_vs_expected: float | None = Field(
        default=None,
        description="예상 시간 대비 비율(1.0=평균, 2.0=평균의 2배 느림, 0.5=빠름). DDL "
        "'DECIMAL(4,2)' → 비율이라 음수 불가 ge=0만 설정(상한은 자유).",
        ge=0.0,
    )

    # ===== 풀이 단계별 시간 (특성 #42) =====
    step_times: list[dict[str, Any]] = Field(
        default_factory=list,
        description='풀이 단계별 시간 [{"step":1,"seconds":30},{"step":2,"seconds":120}]'
        "(JSONB 배열)",
    )

    # ===== 운영 메타 =====
    created_at: datetime | None = Field(
        default=None,
        description="생성 시각 (DDL DEFAULT NOW() — 운영 메타라 Optional)",
    )


# ──────────────────────────────────────────────────────────────────────────
# 핵심: AttemptEvent (§6.1 attempt_event — 실시간 단계 이벤트, TimescaleDB hypertable)
# ──────────────────────────────────────────────────────────────────────────
class AttemptEvent(BaseModel):
    """학생 풀이 단계 이벤트 — §6.1 `attempt_event`(실시간 분석용 시계열).

    복합 PK `(event_id, event_at)` — DB 제약. 운영 시 `attempt_event`는 TimescaleDB
    hypertable로 변환되어 `event_at` 기준 1일 청크로 분할된다(런타임/DB 레벨; 단일 모델
    레벨에서는 표현하지 않음).

    `event_id`는 `BIGSERIAL`이라 DB가 INSERT 시 할당한다 — 클라이언트 기본값이 없으므로
    UUID PK처럼 default_factory를 쓰지 않고 `int | None = Field(default=None)`으로 둔다
    (DB-assigned). `event_at`은 `TIMESTAMPTZ NOT NULL`이라 required다(복합 PK 구성요소).
    """

    model_config = ConfigDict(
        extra="forbid",
        use_enum_values=True,
        str_strip_whitespace=True,
    )

    # ===== 복합 PK (event_id, event_at) =====
    event_id: int | None = Field(
        default=None,
        description="이벤트 PK 일부 — DDL BIGSERIAL(DB-assigned, 클라이언트 기본값 없음). "
        "복합 PK (event_id, event_at) 구성요소. DB가 1부터 할당하므로 ge=1.",
        ge=1,
    )
    event_at: datetime = Field(
        ...,
        description="이벤트 발생 시각 — DDL TIMESTAMPTZ NOT NULL → required(복합 PK 구성요소·"
        "hypertable 분할 키)",
    )

    # ===== FK =====
    attempt_id: uuid.UUID | None = Field(
        default=None,
        description="소속 시도 FK (problem_attempt 참조)",
    )
    user_id: uuid.UUID | None = Field(
        default=None,
        description="학생 FK (user_profile 참조)",
    )
    problem_id: uuid.UUID | None = Field(
        default=None,
        description="문제 FK (problem 참조)",
    )

    # ===== 이벤트 내용 =====
    event_type: EventType | None = Field(
        default=None,
        description="이벤트 유형 — 문제읽기/조건분석/그래프그리기/계산/지움/막힘/힌트요청/답입력/"
        "검산결과",
    )
    event_data: dict[str, Any] | None = Field(
        default=None,
        description="이벤트 부가 데이터(JSONB). 생산 3종(검산결과·힌트제공·시각화조작)은 "
        "event_data_contract 계약으로 모양 고정(invariant ⑫)·휴면 8종은 자유형.",
    )
