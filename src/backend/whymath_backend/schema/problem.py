"""Schema v1.0 도메인1 Problem 모델 (Pydantic).

설계 정본: `schemas/v1.0/schema_v1.0.md` §3.1(`problem` 테이블 DDL, 50+필드)·
§3.2(`problem_step`·`problem_relation`).

Phase 메모: 코드베이스 전체가 *Pydantic-schema-only*(DB 미배포) — 이 슬라이스도 순수
Pydantic 모델이다. SQLAlchemy/alembic 매핑은 후속 Phase(`ncic/models.py` 동일 패턴).

컨벤션(`l3/models.py` 답습):
  - `ConfigDict(extra="forbid", use_enum_values=True, str_strip_whitespace=True)`.
  - enum은 `enums.py`의 `class X(str, Enum)`.
  - 불변식은 `@model_validator(mode="after")`.
  - 공유 베이스 클래스 없음(각 모델 독립).

타입 매핑 판단(DDL → Pydantic):
  - `UUID PK` → `uuid.UUID = Field(default_factory=uuid4)`
  - `TEXT[]` → `list[str]`
  - `JSONB` → 의미가 있는 곳은 작은 서브모델(`conditions_parsed` → `list[Condition]`),
    자유형(`source_detail`·`answer_constraint`·`ebs_source` 등)은 `dict[str, ...]`
  - `DECIMAL` → `float`
  - `TIMESTAMPTZ` → `datetime`
  - `persona_fit` → `dict[Persona, float]`(페르소나별 적합도 0~1)
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from whymath_backend.schema.enums import (
    AnswerFormat,
    Curriculum,
    ExamType,
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
from whymath_backend.schema.visualization import Visualization

# ──────────────────────────────────────────────────────────────────────────
# 본문 미보유(구조 메타 전용) source_type — 법적 교정의 대상 집합
# (MEMORY 2026-05-28: 평가원·EBS·검정교과서 본문 미보유, 저작권 가이드 v2.0 §32 단서)
# ──────────────────────────────────────────────────────────────────────────
_METADATA_ONLY_SOURCES: frozenset[SourceType] = frozenset(
    {SourceType.평가원, SourceType.EBS, SourceType.교과서}
)
"""이 출처의 레코드는 *구조 메타데이터 참조 전용* — 본문 필드가 비어야 한다.

`source_detail`/`ebs_source`에 단원·코드·문항번호만 둔다. 학생에게 노출·저장되는
실제 본문은 `SourceType.자체생성`(WHYMATH_GENERATED) 레코드만 가질 수 있다.
"""


# ──────────────────────────────────────────────────────────────────────────
# 서브모델: 발문 조건 (§3.1 conditions_parsed JSONB)
# ──────────────────────────────────────────────────────────────────────────
class Condition(BaseModel):
    """발문의 (가)(나)(다) 조건 1개 — §3.1 `conditions_parsed` JSONB 원소.

    예: {"label":"가", "text":"f(x)는 실수 전체에서 미분가능",
         "formal":"differentiable(f, R)"}
    """

    model_config = ConfigDict(
        extra="forbid",
        use_enum_values=True,
        str_strip_whitespace=True,
    )

    label: str = Field(..., description="조건 라벨 (예: '가', '나', '다')")
    text: str = Field(..., description="조건 자연어 본문")
    formal: str | None = Field(
        default=None,
        description="조건의 형식(수식) 표현 (선택)",
    )


# ──────────────────────────────────────────────────────────────────────────
# 핵심: Problem (§3.1 problem 테이블)
# ──────────────────────────────────────────────────────────────────────────
class Problem(BaseModel):
    """단일 문제 — §3.1 `problem` 테이블(50+ 메타데이터). WhyMath 최중요 단일 모델.

    법적 교정 불변식(MEMORY 2026-05-28, `@model_validator(mode="after")`로 강제):
      평가원·EBS·검정교과서는 *본문·문항 미보유*(상업 영리금지, 저작권 가이드 v2.0
      §32 단서). 따라서 `source_type ∈ {평가원, EBS, 교과서}`이면
      `question_text`·`answer_explanation`·`choices`가 *반드시 비어 있어야* 한다
      (있으면 ValueError → ValidationError). 이 출처 레코드는 구조 메타데이터 참조
      전용이며 `source_detail`/`ebs_source`에 단원·코드·문항번호만 둔다.

      *왜*: 검정 교과서·평가원·EBS 본문의 복제·영리이용은 저작권법 §32 단서·§136·
      §140(영리 비친고죄)로 금지된다. 학생에게 노출·저장되는 실제 문제는
      `source_type=자체생성`(WHYMATH_GENERATED)이며 자체 `question_text`를 가진다.

      (license/generation_type 강제는 ContentProvenance = 슬라이스 2 소관. 이 모델은
      Problem 본문 규칙만 강제한다.)

    DDL의 `question_text`·`answer`는 `NOT NULL`이지만, 본문 미보유 출처의 *메타 전용*
    레코드를 표현하려면 이들이 비어 있을 수 있어야 하므로 Pydantic에서는 Optional로
    완화한다(법적 교정과 정합). 실제 본문 레코드(자체생성)는 `question_text`를 채운다.
    """

    model_config = ConfigDict(
        # 추가 필드 금지 — Pydantic 모델이 스키마의 단일 진실
        extra="forbid",
        # 직렬화 시 enum 값을 그대로(한글 값 보존)
        use_enum_values=True,
        # 문자열 양끝 공백 제거
        str_strip_whitespace=True,
    )

    # ===== 기본 식별 =====
    problem_id: uuid.UUID = Field(
        default_factory=uuid4,
        description="문제 PK (UUID)",
    )
    external_id: str | None = Field(
        default=None,
        description="평가원/EBS 원본 ID(구조 식별자, UNIQUE)",
        max_length=64,
    )
    slug: str | None = Field(
        default=None,
        description="사람이 읽는 식별자(UNIQUE)",
        max_length=128,
    )

    # ===== 출처 =====
    source_type: SourceType = Field(..., description="출처 — 평가원/EBS/AIHub/자체생성 등")
    source_detail: dict[str, Any] | None = Field(
        default=None,
        description="출처 구조 메타 {publisher, year, edition, page} 등(본문 X)",
    )

    # ===== 시험 컨텍스트 =====
    exam_type: ExamType | None = Field(
        default=None,
        description="시험 유형 — 수능/모평/학평/EBS교재/N제/자체생성",
    )
    exam_year: int | None = Field(default=None, description="학년도 (예: 2026)")
    exam_month: int | None = Field(
        default=None,
        description="시행 월 (6/9/11 등)",
        ge=1,
        le=12,
    )
    problem_number: int | None = Field(
        default=None,
        description="문항 번호 (예: 22/30)",
        ge=1,
    )
    exam_authority_weight: float | None = Field(
        default=None,
        description="출처 권위 가중치 — 학평0.5/모평0.8/수능1.0",
        ge=0.0,
        le=1.0,
    )

    # ===== 교육과정 버전 =====
    curriculum_version: Curriculum = Field(..., description="교육과정 버전(2015/2022 개정 등)")
    valid_from_year: int = Field(..., description="적용 시작 학년도(예: 2014)")
    valid_to_year: int | None = Field(
        default=None,
        description="적용 종료 학년도(NULL이면 현재까지)",
    )

    # ===== 과목·단원 =====
    subject: Subject = Field(..., description="과목 — 공통/미적분/확통/기하/인공지능수학")
    unit_codes: list[str] = Field(
        ...,
        description="단원 코드 배열 (예: ['CAL-INT-DEF', 'FUN-COMPOSITE'])",
        min_length=1,
    )

    # ===== 문항 형식 =====
    question_format: QuestionFormat | None = Field(
        default=None,
        description="문항 형식 — 객관식/단답형/합답형/서술형",
    )
    points: int | None = Field(default=None, description="배점 (2/3/4점)", ge=0)
    answer_format: AnswerFormat | None = Field(
        default=None,
        description="정답 형식 — 자연수/분수/실수/식",
    )
    answer_constraint: dict[str, Any] | None = Field(
        default=None,
        description='정답 제약 {"min":1,"max":999,"is_natural":true} 등(자유형 JSONB)',
    )
    answer_transform: dict[str, Any] | None = Field(
        default=None,
        description='자연수 답 변환 패턴 {"type":"p_plus_q","p":3,"q":5} 등(자유형 JSONB)',
    )

    # ===== 본문·풀이·정답 =====
    # 법적 교정: 평가원/EBS/교과서 출처면 question_text/answer_explanation/choices는 비어야 함.
    question_text: str | None = Field(
        default=None,
        description="발문 원문(자체생성만 보유; 평가원/EBS/교과서는 비어야 함)",
    )
    question_text_md: str | None = Field(
        default=None,
        description="마크다운+LaTeX 발문",
    )
    question_image_uri: str | None = Field(
        default=None,
        description="도형/그래프 이미지 URI(MinIO)",
    )
    choices: list[str] | None = Field(
        default=None,
        description="객관식 보기(자체생성만; 평가원/EBS/교과서는 비어야 함)",
    )
    answer: str | None = Field(
        default=None,
        description="정답(자체생성만 본문 보유; 메타 전용 레코드는 비움)",
    )
    answer_explanation: str | None = Field(
        default=None,
        description="공식 해설(자체생성만; 평가원/EBS/교과서는 비어야 함)",
    )
    multiple_answers: dict[str, Any] | None = Field(
        default=None,
        description="복수해 가능성(출제오류 검증, 자유형 JSONB)",
    )

    # ===== 한국 시그니처 패턴 =====
    signature_patterns: list[SignaturePattern] = Field(
        default_factory=list,
        description="한국 수능 시그니처 패턴 배열(10종 중)",
    )

    # ===== 발문 구조 =====
    has_condition_list: bool = Field(
        default=False,
        description="(가)(나)(다) 조건 나열형 여부",
    )
    condition_count: int | None = Field(
        default=None,
        description="조건 개수",
        ge=0,
    )
    conditions_parsed: list[Condition] = Field(
        default_factory=list,
        description="파싱된 조건 목록(label·text·formal)",
    )

    # ===== 시각자료 =====
    has_visual: bool = Field(default=False, description="시각자료 포함 여부")
    visual_type: list[VisualType] = Field(
        default_factory=list,
        description="시각자료 유형 배열 — 그래프/도형/표/좌표평면",
    )
    visual_complexity: int | None = Field(
        default=None,
        description="시각자료 복잡도 1-5",
        ge=1,
        le=5,
    )
    visualizations: list[Visualization] = Field(
        default_factory=list,
        description=(
            "선언적 시각화 명세 배열(05 §5.2 — type·spec·caption·interactive). "
            "has_visual/visual_type(메타 태그)와 다른 축 — L5 ④ 비상구가 렌더(슬라이스 91)"
        ),
    )

    # ===== 다차원 난이도 (5축, 원칙 2) =====
    difficulty_overall: float | None = Field(
        default=None,
        description="종합 난이도 1.0-5.0",
        ge=1.0,
        le=5.0,
    )
    diff_calculation: float | None = Field(
        default=None,
        description="계산 복잡도 1.0-5.0",
        ge=1.0,
        le=5.0,
    )
    diff_interpretation: float | None = Field(
        default=None,
        description="조건 해석 난이도 1.0-5.0",
        ge=1.0,
        le=5.0,
    )
    diff_case_analysis: float | None = Field(
        default=None,
        description="케이스 분류 깊이 1.0-5.0",
        ge=1.0,
        le=5.0,
    )
    diff_visual: float | None = Field(
        default=None,
        description="시각자료 복잡도 1.0-5.0",
        ge=1.0,
        le=5.0,
    )
    diff_integration: float | None = Field(
        default=None,
        description="단원 융합도 1.0-5.0",
        ge=1.0,
        le=5.0,
    )
    irt_difficulty_b: float | None = Field(
        default=None,
        description=(
            "JMLE 보정 문항 난이도 b(logit). 응답 데이터로 적합(l2.fit_jmle), 없으면 전문가 "
            "난이도(difficulty_overall) 휴리스틱 폴백. logit 척도(1~5 아님)·범위 비제한."
        ),
    )

    # ===== 정답률·통계 =====
    historical_correct_rate: float | None = Field(
        default=None,
        description="역대 정답률 0.0-1.0 (예: 0.0822 = 8.22%)",
        ge=0.0,
        le=1.0,
    )
    rate_top_grade: float | None = Field(
        default=None,
        description="1등급 학생 정답률 0.0-1.0",
        ge=0.0,
        le=1.0,
    )
    rate_mid_grade: float | None = Field(
        default=None,
        description="3-4등급 정답률 0.0-1.0",
        ge=0.0,
        le=1.0,
    )
    rate_low_grade: float | None = Field(
        default=None,
        description="6등급 이하 정답률 0.0-1.0",
        ge=0.0,
        le=1.0,
    )

    # ===== 시간 예상치 =====
    expected_solve_seconds: int | None = Field(
        default=None,
        description="평균 풀이 시간(초)",
        ge=0,
    )
    expected_solve_seconds_p90: int | None = Field(
        default=None,
        description="상위 10% 기준 풀이 시간(초)",
        ge=0,
    )

    # ===== 페르소나 적합도 (원칙 5) =====
    persona_fit: dict[Persona, float] = Field(
        default_factory=dict,
        description="페르소나별 적합도 0.0-1.0 {Persona: score}",
    )

    # ===== EBS 연계 =====
    ebs_linked: bool = Field(default=False, description="EBS 연계 여부")
    ebs_source: dict[str, Any] | None = Field(
        default=None,
        description='EBS 구조 메타 {"book":"수능특강","chapter":3,"page":47}(본문 X)',
    )

    # ===== 단원 융합 =====
    is_cross_unit: bool = Field(default=False, description="단원 융합 여부")
    cross_unit_pairs: list[list[str]] = Field(
        default_factory=list,
        description='융합 단원 쌍 [["수열","극한"],["미분","함수"]]',
    )

    # ===== 그래프 개형 추론 =====
    requires_graph_sketch: bool = Field(
        default=False,
        description="그래프를 그려야 풀리는가",
    )
    sketch_step_count: int | None = Field(
        default=None,
        description="개형 추론 단계 수(보통 5-6)",
        ge=0,
    )

    # ===== 라벨링 =====
    tags: list[str] = Field(
        default_factory=list,
        description="검색·필터 태그 (예: ['킬러','22번고정'])",
    )
    keywords: list[str] = Field(
        default_factory=list,
        description="키워드 (예: ['합성함수','미분가능성'])",
    )

    # ===== 사용자 노출 정책 =====
    is_premium: bool = Field(default=False, description="프리미엄 콘텐츠 여부")
    is_published: bool = Field(default=False, description="게시 여부")
    publish_at: datetime | None = Field(default=None, description="게시 예정 시각")

    # ===== 운영 메타 =====
    created_at: datetime | None = Field(default=None, description="생성 시각")
    updated_at: datetime | None = Field(default=None, description="수정 시각")
    created_by: uuid.UUID | None = Field(
        default=None,
        description="생성 주체(인간 검수자 또는 AI 에이전트)",
    )
    review_status: ReviewStatus | None = Field(
        default=None,
        description="검수 상태 — pending/approved/rejected",
    )
    review_score: float | None = Field(
        default=None,
        description="검수 점수 0-5",
        ge=0.0,
        le=5.0,
    )

    # ── 불변식 ────────────────────────────────────────────────────
    @model_validator(mode="after")
    def _enforce_copyright_no_body_for_metadata_sources(self) -> Problem:
        """법적 교정 — 평가원/EBS/교과서는 본문 필드를 가질 수 없다.

        MEMORY 2026-05-28 결정: 평가원·EBS·검정교과서는 *본문·문항 미보유*(상업
        영리금지, 저작권법 §32 단서·§136·§140 영리 비친고죄). 이 출처의 레코드는
        구조 메타데이터 참조 전용이므로 본문 필드가 비어 있어야 한다. 본문이 있으면
        ValueError를 던져 ValidationError로 전파한다.

        대상 본문 필드(태스크 명세): `question_text`·`answer_explanation`·`choices`.
        (license/generation_type 강제는 슬라이스 2 ContentProvenance 소관.)

        use_enum_values=True 환경: `source_type`이 문자열 값일 수 있으므로
        enum/문자열 양쪽을 정규화해 비교한다(`l3/models.py` 패턴 답습).
        """
        source_value = (
            self.source_type.value if isinstance(self.source_type, SourceType) else self.source_type
        )
        metadata_only_values = {s.value for s in _METADATA_ONLY_SOURCES}

        if source_value not in metadata_only_values:
            # 자체생성·AIHub·사용자자작 등은 본문 보유 허용 → 규칙 비적용
            return self

        # 비어 있어야 하는 본문 필드를 점검(None/빈 문자열/빈 리스트만 허용)
        offending: list[str] = []
        if self.question_text:
            offending.append("question_text")
        if self.answer_explanation:
            offending.append("answer_explanation")
        if self.choices:
            offending.append("choices")

        if offending:
            raise ValueError(
                f"저작권 교정 위반: source_type={source_value!r}(평가원/EBS/교과서)는 "
                f"본문·문항 미보유여야 한다(저작권 가이드 v2.0 §32 단서·영리 금지). "
                f"비어 있어야 할 본문 필드에 값이 있음: {offending}. "
                f"이 출처는 구조 메타데이터 참조 전용이며 본문은 "
                f"source_type='자체생성'(WHYMATH_GENERATED) 레코드만 가질 수 있다 "
                f"(MEMORY 2026-05-28)."
            )
        return self


# ──────────────────────────────────────────────────────────────────────────
# 보조: ProblemStep (§3.2 problem_step)
# ──────────────────────────────────────────────────────────────────────────
class ProblemStep(BaseModel):
    """문항 풀이 단계 — §3.2 `problem_step`(Socratic 코칭 시 사용).

    `UNIQUE(problem_id, step_order)` — 한 문제 안에서 step_order는 유일(런타임/DB
    제약; 단일 모델 레벨에서는 표현하지 않음).
    """

    model_config = ConfigDict(
        extra="forbid",
        use_enum_values=True,
        str_strip_whitespace=True,
    )

    step_id: uuid.UUID = Field(default_factory=uuid4, description="단계 PK (UUID)")
    problem_id: uuid.UUID = Field(..., description="소속 문제 FK")
    step_order: int = Field(..., description="단계 순서(1부터)", ge=1)
    step_type: StepType | None = Field(
        default=None,
        description="단계 유형 — 조건해석/케이스분류/그래프스케치/계산/검산",
    )
    step_title: str | None = Field(
        default=None,
        description="단계 제목",
        max_length=200,
    )
    socratic_prompt: str | None = Field(
        default=None,
        description="소크라테스 발문 (예: '조건 (가)를 수식으로 표현해보세요')",
    )
    expected_answer: str | None = Field(
        default=None,
        description="이 단계의 기대 답",
    )
    common_mistakes: list[dict[str, Any]] = Field(
        default_factory=list,
        description='흔한 실수 목록 [{"error":"...","hint":"..."}](자유형 JSONB)',
    )


# ──────────────────────────────────────────────────────────────────────────
# 보조: ProblemRelation (§3.2 problem_relation)
# ──────────────────────────────────────────────────────────────────────────
class ProblemRelation(BaseModel):
    """문항 간 관계 — §3.2 `problem_relation`(전형성·유사도).

    복합 PK `(parent_problem_id, related_problem_id, relation_type)` — DB 제약.
    불변식: 자기 자신과의 관계 금지(parent ≠ related).
    """

    model_config = ConfigDict(
        extra="forbid",
        use_enum_values=True,
        str_strip_whitespace=True,
    )

    parent_problem_id: uuid.UUID = Field(..., description="기준 문제 FK")
    related_problem_id: uuid.UUID = Field(..., description="관계 대상 문제 FK")
    relation_type: RelationType = Field(
        ...,
        description="관계 유형 — 변형/유사/선수/심화/대조",
    )
    similarity_score: float | None = Field(
        default=None,
        description="유사도 0.0-1.0",
        ge=0.0,
        le=1.0,
    )

    @model_validator(mode="after")
    def _no_self_relation(self) -> ProblemRelation:
        """자기 자신과의 관계 금지 — parent_problem_id ≠ related_problem_id."""
        if self.parent_problem_id == self.related_problem_id:
            raise ValueError(
                "문항 관계 위반: parent_problem_id와 related_problem_id가 같을 수 없다 "
                "(자기 자신과의 관계 금지)"
            )
        return self
