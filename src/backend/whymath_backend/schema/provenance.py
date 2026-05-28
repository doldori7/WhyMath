"""Schema v1.0 도메인8 Provenance 모델 (Pydantic) — 슬라이스 2.

설계 정본: `schemas/v1.0/schema_v1.0.md` §10(`content_provenance`·`generation_log` DDL).

Phase 메모: 코드베이스 전체가 *Pydantic-schema-only*(DB 미배포) — 이 슬라이스도 순수
Pydantic 모델이다. SQLAlchemy/alembic 매핑은 후속 Phase(슬라이스 1 `problem.py` 동일 패턴).

컨벤션(`problem.py`·`l3/models.py` 답습):
  - `ConfigDict(extra="forbid", use_enum_values=True, str_strip_whitespace=True)`.
  - enum은 `enums.py`의 `class X(str, Enum)`.
  - 불변식은 `@model_validator(mode="after")`.
  - 공유 베이스 클래스 없음(각 모델 독립).

타입 매핑 판단(DDL → Pydantic, 슬라이스 1 선례 그대로):
  - `UUID PK` → `uuid.UUID = Field(default_factory=uuid4)`
  - `UUID REFERENCES`(FK) → `uuid.UUID | None`(DDL에 NOT NULL 없음 → 보수적 Optional)
  - `JSONB` 자유형 → `dict[str, Any] | None`
  - `DECIMAL` → `float`(ge=0)
  - `TIMESTAMPTZ` → `datetime`
  - `VARCHAR(n)` → `str | None`(max_length=n)

법적 교정(이번 슬라이스의 핵심, MEMORY 2026-05-28 속편 "스키마 법적 교정"):
  평가원·EBS·교과서는 *본문 미보유*(저작권 가이드 v2.0 §32 단서·§136·§140 영리
  비친고죄). `content_provenance`가 이 본문 규칙을 *license/generation_type 차원*에서
  강제한다. 슬라이스 1 `Problem`은 본문 필드 차원, 이 모델은 출처·라이선스 차원으로
  같은 원칙을 양면 방어한다. 상세는 `ContentProvenance` 불변식 docstring 참조.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from whymath_backend.schema.enums import GenerationType, LicenseType, SourceType

# 단일 출처 유지: 메타데이터 전용 출처 집합은 `problem.py`에서 가져온다(중복 정의 금지).
# (frozenset[SourceType] = {평가원, EBS, 교과서} — 본문 미보유, 저작권 가이드 v2.0 §32 단서)
from whymath_backend.schema.problem import _METADATA_ONLY_SOURCES

# ──────────────────────────────────────────────────────────────────────────
# 변형/생성류 generation_type — 메타 전용 출처가 *반드시* 거쳐야 하는 단계 집합
# (ORIGINAL="원본 그대로"는 제외 — (A) 불변식에서 이미 전면 차단됨)
# ──────────────────────────────────────────────────────────────────────────
_TRANSFORMED_GENERATION_TYPES: frozenset[GenerationType] = frozenset(
    {
        GenerationType.VARIANT_NUMBER,
        GenerationType.VARIANT_STRUCTURE,
        GenerationType.VARIANT_CONTEXT,
        GenerationType.COMPOSED,
        GenerationType.FULLY_GENERATED,
    }
)
"""메타 전용 출처(평가원/EBS/교과서)를 참조하는 레코드가 가질 수 있는 generation_type.

원본을 *그대로* 쓰지 않고 반드시 변형/생성했음을 보장한다. `ORIGINAL`은 (A) 불변식에서
별도로 막히고, `None`도 (C-2)에서 거부된다(변형/생성 단계가 명시돼야 함).
"""

# ──────────────────────────────────────────────────────────────────────────
# original_reference 본문성 키 denylist — 구조 메타만 허용, 본문은 금지
# (키를 소문자화해 부분일치로 검사 — year/exam/number/unit/code/page 등 구조 메타만 통과)
# ──────────────────────────────────────────────────────────────────────────
_BODY_KEY_DENYLIST: tuple[str, ...] = (
    "question",
    "statement",
    "body",
    "content",
    "answer",
    "solution",
    "explanation",
    "choice",
    "passage",
    "본문",
    "문제",
    "풀이",
    "정답",
    "보기",
    "지문",
    "해설",
)
"""`original_reference`에 들어오면 안 되는 *본문성* 키(부분일치·소문자화).

`original_reference`는 *구조 메타 전용*(year/exam/number/unit/code/page/문항번호 등)이다.
본문(발문·풀이·정답·보기)을 이 JSONB에 끼워 넣어 우회 저장하는 것을 차단한다.
"""


# ──────────────────────────────────────────────────────────────────────────
# 핵심: ContentProvenance (§10.1 content_provenance 테이블)
# ──────────────────────────────────────────────────────────────────────────
class ContentProvenance(BaseModel):
    """콘텐츠 변형·생성 이력 — §10.1 `content_provenance`(감사 추적).

    한 `problem`이 어떤 원본 출처에서 어떤 변형/생성 단계를 거쳐 만들어졌는지, 검증·승인·
    저작권 메타데이터까지 추적한다. 특성 #11·#33·#36·#37의 영속 모델.

    FK Optional 판단(docstring 1줄): DDL의 `problem_id`·`parent_problem_id`·`approved_by`는
    모두 `UUID REFERENCES`이지만 *NOT NULL이 없으므로* 보수적으로 Optional로 둔다(슬라이스
    1 `Problem.created_by`와 동일 정책 — NOT NULL 명시 FK만 required, 예: `ProblemStep.
    problem_id`).

    법적 불변식(`@model_validator(mode="after")`로 강제 — 이번 슬라이스의 핵심,
    근거: MEMORY 2026-05-28 속편 "스키마 법적 교정", 저작권 가이드 v2.0 §32 단서·§136·§140):

      (A) `generation_type == ORIGINAL` → ValueError.
          ORIGINAL="원본 그대로"=본문 복제 전제 → 공식 제휴(Phase 3+) 전까지 전면 미사용.

      (B) `license == EBS_LICENSED` → ValueError.
          공식 제휴(Phase 3+) 전까지 전면 미사용.

      (C) `original_source ∈ {평가원, EBS, 교과서}`(= `problem._METADATA_ONLY_SOURCES`)이면:
        (C-1) `license != WHYMATH_GENERATED` → ValueError.
              이 레코드가 가리키는 본문 문제는 우리가 만든 *동등문제*이므로 지배
              license는 WHYMATH_GENERATED. 원본의 license는 통과하지 못한다.
        (C-2) `generation_type`이 None이거나 변형류(VARIANT_NUMBER·VARIANT_STRUCTURE·
              VARIANT_CONTEXT·COMPOSED·FULLY_GENERATED)가 아니면 → ValueError.
              원본을 그대로 쓰지 않고 *반드시 변형/생성*했음을 보장(ORIGINAL은 (A)에서 차단).
        (C-3) `original_reference`의 키에 본문성 키(question/statement/body/answer/풀이/
              정답/… denylist)가 있으면 → ValueError. 구조 메타(year/exam/number/unit/
              code/page/문항번호)만 허용. DDL 예시 `{"year":2025,"exam":"수능","number":30}`
              은 통과한다.

      use_enum_values=True 환경: `original_source`·`license`·`generation_type`가 *문자열
      값일 수 있으므로* enum/문자열 양쪽을 정규화해 비교한다(`problem.py` L430-435 패턴 답습).
    """

    model_config = ConfigDict(
        # 추가 필드 금지 — Pydantic 모델이 스키마의 단일 진실
        extra="forbid",
        # 직렬화 시 enum 값을 그대로(영어 값 보존)
        use_enum_values=True,
        # 문자열 양끝 공백 제거
        str_strip_whitespace=True,
    )

    # ===== 기본 식별 =====
    provenance_id: uuid.UUID = Field(
        default_factory=uuid4,
        description="이력 PK (UUID)",
    )
    problem_id: uuid.UUID | None = Field(
        default=None,
        description="대상 문제 FK (DDL NOT NULL 없음 → Optional)",
    )

    # ===== 원본 출처 =====
    original_source: SourceType | None = Field(
        default=None,
        description="원본 출처 — 평가원/EBS/AIHub 등(메타 전용 출처는 본문 미보유)",
    )
    original_reference: dict[str, Any] | None = Field(
        default=None,
        description=(
            '원본 참조 *구조 메타 전용* {"year":2025,"exam":"수능","number":30} 등 '
            "(본문성 키 금지 — (C-3) 불변식으로 차단)"
        ),
    )

    # ===== 변형·생성 단계 =====
    generation_type: GenerationType | None = Field(
        default=None,
        description="변형/생성 단계 — VARIANT_*/COMPOSED/FULLY_GENERATED (ORIGINAL 미사용)",
    )
    transformation: dict[str, Any] | None = Field(
        default=None,
        description='변형 메타 {"operations":[{"type":"swap_numbers","from":3,"to":5}]} 등',
    )
    parent_problem_id: uuid.UUID | None = Field(
        default=None,
        description="원본 문제 FK(변형의 경우; DDL NOT NULL 없음 → Optional)",
    )
    transformation_pipeline: dict[str, Any] | None = Field(
        default=None,
        description='변형 파이프라인 {"steps":["Qwen3-32B 초안","Claude 검증","사람 검수"]}',
    )

    # ===== 검증·승인 =====
    auto_validation: dict[str, Any] | None = Field(
        default=None,
        description="자동 검증 결과(자유형 JSONB)",
    )
    human_review: dict[str, Any] | None = Field(
        default=None,
        description='사람 검수 결과 {"reviewer_id":"...","score":4.5,"comments":"..."}',
    )
    approved_at: datetime | None = Field(default=None, description="승인 시각")
    approved_by: uuid.UUID | None = Field(
        default=None,
        description="승인 주체 FK(DDL NOT NULL 없음 → Optional)",
    )

    # ===== 저작권·법적 메타데이터 =====
    license: LicenseType | None = Field(
        default=None,
        description="라이선스 — 본문 보유 문제의 지배 license는 WHYMATH_GENERATED",
    )
    copyright_notice: str | None = Field(
        default=None,
        description="저작권 고지 문구",
    )
    usage_restrictions: dict[str, Any] | None = Field(
        default=None,
        description="사용 제약(자유형 JSONB)",
    )

    # ===== 운영 메타 =====
    created_at: datetime | None = Field(default=None, description="생성 시각")

    # ── 불변식 ────────────────────────────────────────────────────
    @model_validator(mode="after")
    def _enforce_license_and_generation_legal_corrections(self) -> ContentProvenance:
        """법적 교정 — license/generation_type 차원의 저작권 불변식 강제.

        근거: MEMORY 2026-05-28 속편 "스키마 법적 교정"(저작권 가이드 v2.0 §32 단서·
        §136·§140 영리 비친고죄). 슬라이스 1 `Problem`이 *본문 필드* 차원을 막았고, 이
        validator는 *출처·라이선스* 차원을 막아 같은 원칙을 양면 방어한다.

        분기 (A)·(B)·(C-1·2·3)는 클래스 docstring 참조. use_enum_values=True 환경이라
        enum/문자열 양쪽이 들어올 수 있으므로 모두 *문자열 값*으로 정규화해 비교한다
        (`problem.py` L430-435 패턴).
        """
        # ── enum/문자열 정규화 (use_enum_values=True 대응) ──
        gen_value = (
            self.generation_type.value
            if isinstance(self.generation_type, GenerationType)
            else self.generation_type
        )
        license_value = (
            self.license.value if isinstance(self.license, LicenseType) else self.license
        )
        source_value = (
            self.original_source.value
            if isinstance(self.original_source, SourceType)
            else self.original_source
        )

        # ── (A) ORIGINAL 전면 차단 ──
        if gen_value == GenerationType.ORIGINAL.value:
            raise ValueError(
                "저작권 교정 위반(A): generation_type=ORIGINAL은 *원본 그대로*(본문 복제) "
                "전제이므로 공식 제휴(Phase 3+) 전까지 전면 미사용이다(저작권 가이드 v2.0 "
                "§32 단서·영리 금지). 변형/생성(VARIANT_*/COMPOSED/FULLY_GENERATED)을 "
                "사용하라 (MEMORY 2026-05-28 속편)."
            )

        # ── (B) EBS_LICENSED 전면 차단 ──
        if license_value == LicenseType.EBS_LICENSED.value:
            raise ValueError(
                "저작권 교정 위반(B): license=EBS_LICENSED는 공식 제휴(Phase 3+) 전까지 "
                "전면 미사용이다(MEMORY 2026-05-28 속편). 본문 보유 문제의 지배 license는 "
                "WHYMATH_GENERATED이다."
            )

        # ── (C) 메타 전용 출처(평가원/EBS/교과서) 추가 규칙 ──
        metadata_only_values = {s.value for s in _METADATA_ONLY_SOURCES}
        if source_value in metadata_only_values:
            # (C-1) 지배 license는 WHYMATH_GENERATED만 허용
            if license_value != LicenseType.WHYMATH_GENERATED.value:
                raise ValueError(
                    f"저작권 교정 위반(C-1): original_source={source_value!r}"
                    "(평가원/EBS/교과서)가 가리키는 본문 문제는 우리가 만든 *동등문제*이므로 "
                    f"지배 license는 WHYMATH_GENERATED여야 한다. 현재 license={license_value!r} "
                    "(MEMORY 2026-05-28 속편·저작권 가이드 v2.0)."
                )

            # (C-2) 반드시 변형/생성류여야 함(None·비변형 거부; ORIGINAL은 (A)에서 차단)
            transformed_values = {g.value for g in _TRANSFORMED_GENERATION_TYPES}
            if gen_value not in transformed_values:
                raise ValueError(
                    f"저작권 교정 위반(C-2): original_source={source_value!r}"
                    "(평가원/EBS/교과서)는 원본을 그대로 쓰지 않고 *반드시 변형/생성*해야 한다. "
                    "generation_type은 VARIANT_NUMBER/VARIANT_STRUCTURE/VARIANT_CONTEXT/"
                    f"COMPOSED/FULLY_GENERATED 중 하나여야 한다. 현재 generation_type="
                    f"{gen_value!r} (MEMORY 2026-05-28 속편)."
                )

            # (C-3) original_reference에 본문성 키 금지(구조 메타만)
            if self.original_reference is not None:
                offending_keys = [
                    key
                    for key in self.original_reference
                    if any(banned in str(key).lower() for banned in _BODY_KEY_DENYLIST)
                ]
                if offending_keys:
                    raise ValueError(
                        f"저작권 교정 위반(C-3): original_source={source_value!r}의 "
                        "original_reference는 *구조 메타 전용*(year/exam/number/unit/code/"
                        f"page/문항번호 등)이다. 본문성 키 발견: {offending_keys}. 발문·풀이·"
                        "정답·보기 등 본문을 이 JSONB에 끼워 넣을 수 없다 "
                        "(MEMORY 2026-05-28 속편·저작권 가이드 v2.0)."
                    )

        return self


# ──────────────────────────────────────────────────────────────────────────
# 보조: GenerationLog (§10.1 generation_log 테이블)
# ──────────────────────────────────────────────────────────────────────────
class GenerationLog(BaseModel):
    """LLM 생성 호출 이력 — §10.1 `generation_log`(비용·품질 분석).

    문제 1개를 생성/변형하며 호출한 LLM의 모델·토큰·비용·지연·성공 여부를 기록한다.
    `l3/pregenerate` 동등문제 엔진의 호출 결과를 이 모델로 적재한다(연결 코드는 계층
    규칙상 L3쪽 `l3/pregenerate/provenance_bridge.py`에 둔다 — schema는 l3를 import하지
    않는다).

    이 모델은 *순수 데이터 모델*로 유지한다 — l3를 import하지 않는다(역방향 의존 금지,
    7계층 절대원칙). 검증 불변식 없음(로그 레코드는 가능한 한 관대하게 받아 적재).

    FK Optional 판단: `problem_id`·`provenance_id`·`prompt_template_id`는 모두 `UUID
    REFERENCES`이나 DDL에 NOT NULL이 없으므로 Optional로 둔다(`ContentProvenance` 동일 정책).
    """

    model_config = ConfigDict(
        extra="forbid",
        use_enum_values=True,
        str_strip_whitespace=True,
    )

    log_id: uuid.UUID = Field(default_factory=uuid4, description="로그 PK (UUID)")
    problem_id: uuid.UUID | None = Field(
        default=None,
        description="대상 문제 FK(DDL NOT NULL 없음 → Optional)",
    )
    provenance_id: uuid.UUID | None = Field(
        default=None,
        description="대상 이력 FK(DDL NOT NULL 없음 → Optional)",
    )
    model_name: str | None = Field(
        default=None,
        description="모델명 — 'qwen3-32b'/'claude-opus-4-7' 등",
        max_length=64,
    )
    prompt_template_id: uuid.UUID | None = Field(
        default=None,
        description="프롬프트 템플릿 FK(DDL NOT NULL 없음 → Optional)",
    )
    input_tokens: int | None = Field(
        default=None,
        description="입력 토큰 수",
        ge=0,
    )
    output_tokens: int | None = Field(
        default=None,
        description="출력 토큰 수",
        ge=0,
    )
    cost_usd: float | None = Field(
        default=None,
        description="호출 비용(USD) — DECIMAL(8,4)",
        ge=0,
    )
    latency_ms: int | None = Field(
        default=None,
        description="지연 시간(ms)",
        ge=0,
    )
    success: bool | None = Field(default=None, description="성공 여부")
    error_detail: str | None = Field(default=None, description="실패 사유(있으면)")
    generated_at: datetime | None = Field(default=None, description="생성 시각")
