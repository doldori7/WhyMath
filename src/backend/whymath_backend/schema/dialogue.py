"""Schema v1.0 도메인5 Socratic 대화(Dialogue) 모델 (Pydantic) — 슬라이스 5.

설계 정본: `schemas/v1.0/schema_v1.0.md` §7.1(`dialogue`·`dialogue_turn` DDL 2테이블).
한 문제 풀이 중에 오간 학생↔AI 대화(`dialogue`)와 그 안의 개별 교환 턴
(`dialogue_turn`)을 담는 도메인. WhyMath의 핵심 차별점인 *답이 아닌 이유를 묻는*
Socratic 코칭의 로그(특성 #8/#18 조건확인·#21 단계분해·#23 귀납적 수열 다회 턴).

Phase 메모: 코드베이스 전체가 *Pydantic-schema-only*(DB 미배포) — 이 슬라이스도 순수
Pydantic 모델이다. SQLAlchemy/alembic 매핑은 후속 Phase(슬라이스 1~4 동일 패턴).

컨벤션(`problem.py`·`concept.py`·`user.py`·`activity.py` 답습):
  - `ConfigDict(extra="forbid", use_enum_values=True, str_strip_whitespace=True)`.
  - enum은 `enums.py`의 `class X(str, Enum)`(Resolution·TurnRole·ContentType·
    SocraticStrategy·StudentIntent 신규).
  - 공유 베이스 클래스 없음(각 모델 독립).

타입 매핑 판단(DDL → Pydantic, 슬라이스 1~4 선례 그대로):
  - `UUID PK` → `uuid.UUID = Field(default_factory=uuid4)`
  - nullable `UUID`(FK) → `uuid.UUID | None`(예: user_id, attempt_id, dialogue_id)
  - `INTEGER` → `int | None`(ge/le); `INTEGER NOT NULL` → required `int`
    (예: dialogue_turn.turn_order)
  - `VARCHAR(n)` → `str | None`(max_length=n; 자유 문자열, 예: model_used)
  - `DECIMAL(p,s)` → `float | None`(ge/le); 범위는 DDL 인라인 주석을 따르고, 미명시는
    의미에 맞는 보수값을 골라 각 필드 description에 1줄로 명시(슬라이스 1~4 방식)
  - `TIMESTAMPTZ` → `datetime | None`
  - `BOOLEAN DEFAULT FALSE` → `bool = False`(예: flagged_for_review)
  - `TEXT` → `str | None`
  - `JSONB`(자유형) → `dict[str, Any] | None`(예: image_analysis)

개인정보 메모(CLAUDE.md 절대 금기·개인정보보호법, `user.py`·`activity.py` 방침과 동일):
  `dialogue_turn`의 `content`(대화 본문)·`image_uri`(손글씨 이미지 URI)·`image_analysis`
  (Qwen3-VL 분석 결과)는 *미성년 채팅·손글씨 데이터*다. CLAUDE.md 절대 금기("미성년자
  채팅 데이터를 평문으로 저장 금지"·"학생 풀이 데이터 명시적 동의 없이 학습 사용 금지")는
  *저장·동의 계층* 책임이다 — 암호화 저장·동의 게이팅은 인프라/미들웨어
  (`ParentalConsentMiddleware`)·검수 플로우가 시행한다. 모델 필드는 그 사실을 *상기*
  시키되 cross-field 강제(가짜 validator)를 두지 않는다(문서화만 — `user.py`/`concept.py`
  법적 메모와 같은 방침). 여기엔 강제할 구조 신호가 없다.

  또한 이 도메인에는 자기관계(self-relation) 같은 구조 cross-field 불변식이 없다.
  카운트 정합(total_turns = student_turns + assistant_turns)도 system 턴이 끼면 항상
  성립하지 않으므로 모델 불변식으로 강제하지 않는다(`concept.py` 방침 — 없는 게 맞다).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from whymath_backend.schema.enums import (
    ContentType,
    Resolution,
    SocraticStrategy,
    StudentIntent,
    TurnRole,
)


# ──────────────────────────────────────────────────────────────────────────
# 핵심: Dialogue (§7.1 dialogue — 한 문제 풀이 중의 대화 세션)
# ──────────────────────────────────────────────────────────────────────────
class Dialogue(BaseModel):
    """Socratic 대화 세션 — §7.1 `dialogue`(한 문제 풀이 중 오간 학생↔AI 대화 1단위).

    PK `dialogue_id`만 있고 나머지는 모두 nullable/기본값(DDL 그대로). `resolution`으로
    학생이 스스로 풀었는지·유도로 풀었는지·결국 풀이를 봤는지·포기했는지를 가른다.

    카운트 정합 메모(모듈 docstring 참조): `total_turns = student_turns + assistant_turns`는
    `system` 턴이 끼면 항상 성립하지 않으므로 cross-field validator로 강제하지 않는다
    (`concept.py`/`activity.py` 방침 — 없는 게 맞다).
    """

    model_config = ConfigDict(
        # 추가 필드 금지 — Pydantic 모델이 스키마의 단일 진실
        extra="forbid",
        # 직렬화 시 enum 값을 그대로(한글 값 보존: resolution="학생자력해결" 등)
        use_enum_values=True,
        # 문자열 양끝 공백 제거
        str_strip_whitespace=True,
    )

    # ===== 기본 식별 =====
    dialogue_id: uuid.UUID = Field(
        default_factory=uuid4,
        description="대화 PK (UUID)",
    )
    user_id: uuid.UUID | None = Field(
        default=None,
        description="학생 FK (user_profile 참조)",
    )
    attempt_id: uuid.UUID | None = Field(
        default=None,
        description="소속 풀이 시도 FK (problem_attempt 참조)",
    )
    problem_id: uuid.UUID | None = Field(
        default=None,
        description="문제 FK (problem 참조)",
    )

    # ===== 시간 =====
    started_at: datetime | None = Field(default=None, description="대화 시작 시각")
    ended_at: datetime | None = Field(default=None, description="대화 종료 시각")

    # ===== 대화 결과 =====
    resolution: Resolution | None = Field(
        default=None,
        description="대화 종결 결과 — 학생자력해결/Socratic유도성공/힌트필요/풀이공개로종결/포기",
    )

    # ===== 턴 카운트 =====
    total_turns: int | None = Field(
        default=None,
        description="전체 턴 수. DDL에 범위 미명시 → 개수라 음수 불가 ge=0만 설정.",
        ge=0,
    )
    student_turns: int | None = Field(
        default=None,
        description="학생 턴 수. DDL에 범위 미명시 → 개수라 음수 불가 ge=0만 설정.",
        ge=0,
    )
    assistant_turns: int | None = Field(
        default=None,
        description="AI 턴 수. DDL에 범위 미명시 → 개수라 음수 불가 ge=0만 설정.",
        ge=0,
    )

    # ===== LLM 사용량 =====
    model_used: str | None = Field(
        default=None,
        description="사용 모델명 (예: 'claude-opus-4-7'/'qwen3-32b-local') — VARCHAR(50)",
        max_length=50,
    )
    total_tokens: int | None = Field(
        default=None,
        description="총 토큰 수. DDL에 범위 미명시 → 개수라 음수 불가 ge=0만 설정.",
        ge=0,
    )
    estimated_cost_usd: float | None = Field(
        default=None,
        description="추정 비용(USD). DDL 'DECIMAL(8,4)' → 비용이라 음수 불가 ge=0만 설정.",
        ge=0.0,
    )

    # ===== 품질 평가 =====
    student_rating: int | None = Field(
        default=None,
        description="학생 평가 1-5 (DDL 주석 '1-5')",
        ge=1,
        le=5,
    )
    auto_quality_score: float | None = Field(
        default=None,
        description="자동 평가 점수. DDL 'DECIMAL(3,2)' → 정규화 점수로 보아 ge=0 le=1 설정 "
        "(`activity.py` focus_score 선례).",
        ge=0.0,
        le=1.0,
    )
    flagged_for_review: bool = Field(
        default=False,
        description="검수 필요 플래그 (BOOLEAN DEFAULT FALSE)",
    )


# ──────────────────────────────────────────────────────────────────────────
# 핵심: DialogueTurn (§7.1 dialogue_turn — 한 번의 학생↔AI 교환)
# ──────────────────────────────────────────────────────────────────────────
class DialogueTurn(BaseModel):
    """대화 턴 — §7.1 `dialogue_turn`(학생↔AI 한 번의 교환, 특성 #8/#18/#21).

    `UNIQUE(dialogue_id, turn_order)` — 한 대화 안에서 turn_order는 유일(런타임/DB
    제약; 단일 모델 레벨에서는 표현하지 않음). `turn_order`는 `INTEGER NOT NULL`이라
    required다(슬라이스 1 `ProblemStep.step_order`가 NOT NULL을 required로 둔 선례 답습).

    개인정보 메모(모듈 docstring 참조): `content`(대화 본문)·`image_uri`(손글씨 이미지
    URI)·`image_analysis`(Qwen3-VL 분석)는 *미성년 채팅·손글씨 데이터*다. CLAUDE.md 절대
    금기(미성년 채팅 평문 저장 금지·학생 풀이 동의 없는 학습 사용 금지)는 *저장·동의 계층*
    (암호화·미들웨어·검수) 책임이며, 이 모델 필드는 그 사실을 *상기*시키되 가짜 validator를
    두지 않는다(문서화만 — `user.py`/`concept.py` 방침과 동일).
    """

    model_config = ConfigDict(
        extra="forbid",
        use_enum_values=True,
        str_strip_whitespace=True,
    )

    # ===== 기본 식별 =====
    turn_id: uuid.UUID = Field(
        default_factory=uuid4,
        description="턴 PK (UUID)",
    )
    dialogue_id: uuid.UUID | None = Field(
        default=None,
        description="소속 대화 FK (dialogue 참조)",
    )
    turn_order: int = Field(
        ...,
        description="턴 순서 — DDL INTEGER NOT NULL → required(1부터). UNIQUE(dialogue_id, "
        "turn_order)의 구성요소라 ge=1 설정(`problem.py` step_order 선례).",
        ge=1,
    )
    spoken_at: datetime | None = Field(
        default=None,
        description="발화 시각 (DDL DEFAULT NOW() — 운영 메타라 Optional)",
    )

    # ===== 내용 =====
    role: TurnRole | None = Field(
        default=None,
        description="화자 — student/assistant/system",
    )
    content: str | None = Field(
        default=None,
        description="턴 본문 — *미성년 채팅 데이터*(평문 저장 금지는 저장계층 책임, "
        "모듈 docstring 참조)",
    )
    content_type: ContentType | None = Field(
        default=None,
        description="콘텐츠 형식 — 텍스트/수식/이미지/혼합",
    )

    # ===== AI 응답 메타데이터 (특성 #8/#18/#21) =====
    socratic_strategy: SocraticStrategy | None = Field(
        default=None,
        description="Socratic 발문 전략 — 조건확인/예시제시/반례제시/단계분해/유사문제/"
        "그래프그리기제안",
    )
    targeted_step: int | None = Field(
        default=None,
        description="어느 풀이 단계를 향한 응답인지(단계 번호). DDL에 범위 미명시 → 단계는 "
        "1부터라 ge=1 설정(`problem.py` step_order 선례).",
        ge=1,
    )
    targeted_concept_id: uuid.UUID | None = Field(
        default=None,
        description="다루는 개념 FK (concept 참조)",
    )

    # ===== 학생 응답 분석 =====
    student_intent: StudentIntent | None = Field(
        default=None,
        description="학생 발화 의도 — 답시도/질문/막힘표현/포기/이해확인",
    )
    student_understanding_signal: float | None = Field(
        default=None,
        description="이해 수준 신호. DDL 'DECIMAL(3,2)' → 정규화 신호로 보아 ge=0 le=1 설정 "
        "(`activity.py` confidence_self_reported 선례).",
        ge=0.0,
        le=1.0,
    )

    # ===== 멀티모달 =====
    image_uri: str | None = Field(
        default=None,
        description="손글씨 풀이 이미지 URI — *미성년 풀이 데이터*(저장계층 보호 책임, "
        "모듈 docstring 참조)",
    )
    image_analysis: dict[str, Any] | None = Field(
        default=None,
        description="Qwen3-VL 분석 결과(자유형 JSONB) — *미성년 풀이 데이터*(저장계층 보호 "
        "책임, 모듈 docstring 참조)",
    )
