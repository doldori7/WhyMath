"""DSL 콘텐츠 생성기의 Pydantic IR — 사람용 YAML/JSON과 기계용 정본의 경계.

설계 정본: `docs/architecture/03d_dsl_content_generator.md` §4.3.

- Human-readable YAML/JSON은 저작·검토·버전 관리용이다.
- 본 모듈의 Pydantic 모델이 시스템 내부의 canonical IR이다.
- 수학 동치 검증은 SymPy가 단일 권위다(자체 CAS 금지).
"""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

# =============================================================================
# 콘텐츠 생명주기 상태
# =============================================================================


class ContentLifecycleState(str, Enum):
    """콘텐츠 생명주기 — `docs/architecture/03d_dsl_content_generator.md` §9.2."""

    IDEA = "idea"
    GENERATED = "generated"
    PARSED = "parsed"
    VALIDATED = "validated"
    VERIFIED = "verified"
    REVIEWED = "reviewed"
    PUBLISHED = "published"
    USED = "used"
    ANALYZED = "analyzed"
    IMPROVED = "improved"
    DEPRECATED = "deprecated"


# =============================================================================
# 커리큘럼·난이도 메타
# =============================================================================


class CurriculumMeta(BaseModel):
    """교육과정 메타 — DSL의 curriculum 영역.

    `standard_codes`(CUR-12)는 **정렬 조회 결과를 담는 슬롯**이다. IR은 순수 Pydantic이라
    스스로 DB를 조회하지 않는다 — 채우는 쪽은 세션을 쥔 표면(`api/dsl.py`)이고, 그쪽이
    `l1/standards/alignment_query.get_alignments`를 경유한다(통합 함수 단일 진실 원천).
    비어 있음은 "정렬 없음"이 아니라 "이 DSL에 정렬이 실리지 않음"이다 — 조인이 성립했는지는
    채우는 쪽의 조인 회계 로그가 말한다(`log_join_stats` — 침묵 실패 금지).
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    subject: str = Field(..., min_length=1, description="과목(예: mathematics)")
    grade: str = Field(..., min_length=1, description="학년(예: middle_2)")
    domain: str | None = Field(default=None, description="영역(예: algebra)")
    concept: str = Field(..., min_length=1, description="개념(예: simultaneous_equations)")
    standard_codes: tuple[str, ...] = Field(
        default=(),
        description="정렬된 성취기준 참조(CUR-12 `get_alignments` 산출·정렬·중복 제거). "
        "빈 튜플 = 이 DSL에 정렬이 실리지 않음(조인 성립 여부는 생성 측 회계 로그가 말한다)",
    )


class DifficultyMeta(BaseModel):
    """난이도 메타 — DSL의 difficulty 영역."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    level: int = Field(..., ge=1, le=10, description="난이도 1~10")
    target_time_sec: int | None = Field(default=None, ge=0, description="목표 풀이 시간(초)")


# =============================================================================
# 변수·제약 — Variable DSL
# =============================================================================


class VariableSpec(BaseModel):
    """변수 정의 — 문제 변형의 재료."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    type: Literal["integer", "float", "string"] = Field(..., description="변수 자료형")
    range: tuple[float, float] | None = Field(default=None, description="정수·실수 범위 [min, max]")
    choices: tuple[str, ...] | None = Field(default=None, description="문자열 선택지")
    default: str | None = Field(default=None, description="기본값(선택)")

    @model_validator(mode="after")
    def _check_shape(self) -> "VariableSpec":
        if self.type == "string":
            if self.choices is None or not self.choices:
                raise ValueError("string 타입은 choices가 필요합니다.")
            if self.range is not None:
                raise ValueError("string 타입은 range를 가질 수 없습니다.")
        else:
            if self.range is None:
                raise ValueError("integer/float 타입은 range가 필요합니다.")
            if self.choices is not None:
                raise ValueError("integer/float 타입은 choices를 가질 수 없습니다.")
        return self


class ConstraintSpec(BaseModel):
    """변수 제약 — SymPy로 검증 가능한 조건식."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    expression: str = Field(..., min_length=1, description="SymPy 파싱 가능한 제약식")
    description: str | None = Field(default=None, description="사람용 설명")


class ProblemTemplate(BaseModel):
    """문제 본문 템플릿 — {a}·{b} 같은 변수 치환 자리."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    statement: str | None = Field(default=None, description="고정 본문(변수 없음)")
    template: str | None = Field(
        default=None, description="변수 치환 템플릿(예: '{a}x + {b} = {c}')"
    )
    variables: dict[str, VariableSpec] = Field(
        default_factory=dict, description="템플릿에서 참조하는 변수 정의"
    )
    constraints: tuple[ConstraintSpec, ...] = Field(
        default=(), description="변수 값이 만족해야 할 제약"
    )

    @model_validator(mode="after")
    def _require_statement_or_template(self) -> "ProblemTemplate":
        if not self.statement and not self.template:
            raise ValueError("statement 또는 template 중 하나는 필수입니다.")
        if self.template and not self.variables:
            raise ValueError("template을 쓰려면 variables 정의가 필요합니다.")
        return self


# =============================================================================
# 정답·풀이·힌트
# =============================================================================


class AnswerSpec(BaseModel):
    """정답 정의 — SymPy로 검증 가능한 형태."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    type: Literal["integer", "float", "expression", "set", "choice"] = Field(
        ..., description="정답 유형"
    )
    value: str | None = Field(default=None, description="고정 정답 값")
    expression: str | None = Field(default=None, description="변수 기반 정답 식(예: '(a + b) / 2')")
    choices: tuple[str, ...] | None = Field(default=None, description="객관식 선택지")

    @model_validator(mode="after")
    def _check_answer_source(self) -> "AnswerSpec":
        sources = sum(1 for v in (self.value, self.expression, self.choices) if v is not None)
        if sources == 0:
            raise ValueError("value·expression·choices 중 하나는 필수입니다.")
        if sources > 1:
            raise ValueError("value·expression·choices는 동시에 하나만 지정해야 합니다.")
        return self


class SolutionStepSpec(BaseModel):
    """풀이 한 단계 — 자연어 + 수식 + 개념 참조."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    order: int = Field(..., ge=1, description="단계 순서(1부터)")
    content: str = Field(..., min_length=1, description="단계 내용(자연어+LaTeX)")
    formula: str | None = Field(default=None, description="SymPy 파싱 가능한 수식")
    concept_node_id: str | None = Field(default=None, description="L1 개념 그래프 노드")
    hint: str | None = Field(default=None, description="막힌 학생용 힌트")
    common_errors: tuple[str, ...] = Field(default=(), description="흔한 오류")


class HintSpec(BaseModel):
    """단계별 힌트 — L4 graded Hint로 전달될 원천."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    level: int = Field(..., ge=1, description="힌트 단계")
    text: str = Field(..., min_length=1, description="힌트 본문")


# =============================================================================
# 오개념·적응 메타
# =============================================================================


class MisconceptionTrigger(BaseModel):
    """오개념 진단 트리거 — 특정 오답 패턴이 특정 오개념을 시사."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    answer_pattern: dict[str, float] = Field(
        ..., description="오답 값 → 확률 매핑(예: {'x = 8': 0.9})"
    )
    interpretation: tuple[str, ...] = Field(default=(), description="오개념 해석 문구")


class MisconceptionSpec(BaseModel):
    """오개념 연결 — L1 misconceptions 카탈로그와의 다리."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    target: tuple[str, ...] = Field(default=(), description="오개념 코드")
    diagnostic: MisconceptionTrigger | None = Field(default=None, description="진단 트리거")


class AdaptationRule(BaseModel):
    """적응 규칙 — L4가 소비하는 메타데이터."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    condition: str = Field(..., min_length=1, description="조건(예: 'accuracy < 0.5')")
    then: dict[str, str] = Field(default_factory=dict, description="조건 충족 시 변경할 파라미터")


class AdaptationSpec(BaseModel):
    """적응 메타 — 실제 실행은 L4에서 한다."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    difficulty: dict[str, tuple[str, ...]] = Field(
        default_factory=dict, description="난이도 적응 기준(예: 'based_on': ['accuracy'])"
    )
    rules: tuple[AdaptationRule, ...] = Field(default=(), description="적응 규칙")


# =============================================================================
# 콘텐츠 생성 요청·문제 DSL
# =============================================================================


class ContentSpecification(BaseModel):
    """생성 요청 — 무엇을 만들 것인가."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    subject: str = Field(..., min_length=1)
    grade: str = Field(..., min_length=1)
    concept: str = Field(..., min_length=1)
    difficulty: int = Field(..., ge=1, le=10)
    count: int = Field(default=1, ge=1, le=100)
    purpose: Literal["practice", "assessment", "review"] = Field(default="practice")
    seed: int | None = Field(default=None, description="결정론적 생성용 난수 시드")


class ProblemDSL(BaseModel):
    """문제 DSL — 문제·변수·정답·풀이·힌트·오개념을 하나로 묶는 IR."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    content_id: str = Field(..., min_length=1, description="콘텐츠 식별자")
    dsl_version: str = Field(default="1.0", description="DSL 버전")
    curriculum: CurriculumMeta
    difficulty: DifficultyMeta
    learning: dict[str, tuple[str, ...]] = Field(
        default_factory=dict, description="학습 메타(스킬 등)"
    )
    problem: ProblemTemplate
    answer: AnswerSpec
    solution: tuple[SolutionStepSpec, ...] = Field(default=(), description="풀이 단계")
    hints: tuple[HintSpec, ...] = Field(default=(), description="힌트")
    misconception: MisconceptionSpec | None = Field(default=None)
    adaptation: AdaptationSpec | None = Field(default=None)

    @model_validator(mode="after")
    def _check_solution_order(self) -> "ProblemDSL":
        orders = [step.order for step in self.solution]
        if orders and orders != sorted(orders):
            raise ValueError("solution 단계는 order 오름차순이어야 합니다.")
        return self


# =============================================================================
# 검증 결과·컴파일 산출물
# =============================================================================


class ValidationReport(BaseModel):
    """검증 결과 — 6단계 검증기의 통합 보고서.

    필드명 `schema`는 Pydantic BaseModel.schema()와 충돌하므로 `schema_validation`을 사용한다.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    syntax: Literal["PASS", "FAIL"] = "PASS"
    schema_validation: Literal["PASS", "FAIL"] = "PASS"
    semantic: Literal["PASS", "FAIL"] = "PASS"
    math: Literal["PASS", "FAIL", "UNVERIFIABLE"] = "PASS"
    education: Literal["PASS", "FAIL"] = "PASS"
    duplicate: Literal["PASS", "FAIL"] = "PASS"
    quality_score: float = Field(default=0.0, ge=0.0, le=1.0)
    publishable: bool = False
    signals: tuple[dict[str, str], ...] = Field(default=(), description="검증 실패 신호 목록")

    @property
    def math_passed(self) -> bool:
        """수학 검증이 PASS인가 — UNVERIFIABLE은 통과 아님."""
        return self.math == "PASS"


class CompiledContent(BaseModel):
    """컴파일 산출물 — Runtime이 소비하는 형태."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    content_id: str
    runtime_type: Literal["math_problem", "concept", "assessment"] = "math_problem"
    render: dict[str, str] = Field(default_factory=dict, description="렌더 힌트")
    grading: dict[str, str] = Field(default_factory=dict, description="채점 힌트")
    problem_text: str = Field(..., description="최종 문제 본문(변수 치환 완료)")
    answer: str = Field(..., description="최종 정답(변수 치환 완료)")
    solution_texts: tuple[str, ...] = Field(default=(), description="치환된 풀이")
    hint_texts: tuple[str, ...] = Field(default=(), description="치환된 힌트")
    concept_dsl: dict[str, object] | None = Field(
        default=None, description="L4/L5가 소비하는 ConceptDSL 투영"
    )


__all__ = [
    "AdaptationRule",
    "AdaptationSpec",
    "AnswerSpec",
    "CompiledContent",
    "ConstraintSpec",
    "ContentLifecycleState",
    "ContentSpecification",
    "CurriculumMeta",
    "DifficultyMeta",
    "HintSpec",
    "MisconceptionSpec",
    "MisconceptionTrigger",
    "ProblemDSL",
    "ProblemTemplate",
    "SolutionStepSpec",
    "ValidationReport",
    "VariableSpec",
]
