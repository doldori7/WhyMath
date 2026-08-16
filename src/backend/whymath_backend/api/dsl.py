"""DSL 콘텐츠 생성기 HTTP API — generate/validate/compile 3종.

설계 정본: `docs/architecture/03d_dsl_content_generator.md` §8.

엔드포인트(prefix `/v1/dsl`):
  - POST /v1/dsl/generate  — 콘텐츠 사양 → 검증된 DSL 생성
  - POST /v1/dsl/validate  — DSL 검증
  - POST /v1/dsl/compile   — DSL → Runtime 객체 컴파일

인가(SEC-07 D1): `CurrentUser`(인증만)로 게이팅한다. 관리자 발행은 후속
`RequireContentAdmin`으로 분리한다.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from whymath_backend.api._auth import CurrentUser
from whymath_backend.l3.dsl.compiler import ContentCompiler
from whymath_backend.l3.dsl.math_verifier import MathValidator
from whymath_backend.l3.dsl.models import (
    AnswerSpec,
    CompiledContent,
    ContentSpecification,
    CurriculumMeta,
    DifficultyMeta,
    ProblemDSL,
    ProblemTemplate,
    ValidationReport,
)
from whymath_backend.l3.dsl.quality_gate import QualityGate
from whymath_backend.l3.dsl.repair import (
    DSLRepairLLM,
    InMemoryHumanReviewQueue,
    RepairEngine,
)
from whymath_backend.l3.dsl.validators import (
    DSLValidationPipeline,
    DuplicateValidator,
    EducationValidator,
    SchemaValidator,
    SemanticValidator,
    SyntaxValidator,
)
from whymath_backend.l3.dsl.variable_engine import VariableBinding

router = APIRouter(prefix="/v1/dsl", tags=["dsl"])


# =============================================================================
# 요청/응답 모델
# =============================================================================


class GenerateRequest(BaseModel):
    """DSL 생성 요청."""

    spec: ContentSpecification


class GenerateResponse(BaseModel):
    """DSL 생성 응답."""

    generation_id: str
    status: str
    contents: list[dict[str, object]] = Field(default_factory=list)


class ValidateRequest(BaseModel):
    """DSL 검증 요청."""

    dsl: ProblemDSL


class ValidateResponse(BaseModel):
    """DSL 검증 응답."""

    report: ValidationReport


class CompileRequest(BaseModel):
    """DSL 컴파일 요청."""

    dsl: ProblemDSL
    binding: dict[str, str] | None = Field(
        default=None, description="변수 바인딩(없으면 seed=0으로 생성)"
    )


class CompileResponse(BaseModel):
    """DSL 컴파일 응답."""

    content: CompiledContent


# =============================================================================
# 의존성
# =============================================================================


def get_validation_pipeline() -> DSLValidationPipeline:
    """기본 검증 파이프라인을 조립한다."""
    return DSLValidationPipeline(
        syntax=SyntaxValidator(),
        schema=SchemaValidator(),
        semantic=SemanticValidator(),
        math=MathValidator(),
        education=EducationValidator(),
        duplicate=DuplicateValidator(),
    )


def get_repair_engine() -> RepairEngine:
    """Repair Engine을 조립한다.

    현재는 LLM 복구 호출이 구현되지 않아 placeholder로 둔다.
    """

    class _NoopRepairLLM(DSLRepairLLM):
        async def repair(
            self, dsl: ProblemDSL, report: ValidationReport, attempt: int
        ) -> ProblemDSL:
            # TODO: LLM 라우터 경유 복구 호출 구현
            return dsl

    return RepairEngine(llm=_NoopRepairLLM(), human_queue=InMemoryHumanReviewQueue())


def get_quality_gate() -> QualityGate:
    return QualityGate()


def get_compiler() -> ContentCompiler:
    return ContentCompiler()


ValidationPipelineDep = Annotated[DSLValidationPipeline, Depends(get_validation_pipeline)]
RepairEngineDep = Annotated[RepairEngine, Depends(get_repair_engine)]
QualityGateDep = Annotated[QualityGate, Depends(get_quality_gate)]
CompilerDep = Annotated[ContentCompiler, Depends(get_compiler)]


# =============================================================================
# 엔드포인트
# =============================================================================


@router.post("/generate", response_model=GenerateResponse, summary="DSL 콘텐츠 생성")
async def generate_dsl(
    body: GenerateRequest,
    user: CurrentUser,
    pipeline: ValidationPipelineDep,
    repair_engine: RepairEngineDep,
    quality_gate: QualityGateDep,
) -> GenerateResponse:
    """콘텐츠 사양으로 DSL을 생성한다.

    현재 MVP는 LLM 생성 대신 *스캐폴드 DSL*을 만들어 검증 파이프라인을
    검증하는 데 집중한다. 실제 LLM 생성은 `l3/pipeline.py`와 연동한다.
    """
    # TODO: l3/pipeline.py 연동 — 현재는 사양 기반 스캐폴드 DSL 생성
    dsl = ProblemDSL(
        content_id=f"{body.spec.subject[:3].upper()}-{body.spec.concept[:8].upper()}-000001",
        dsl_version="1.0",
        curriculum=CurriculumMeta(
            subject=body.spec.subject,
            grade=body.spec.grade,
            domain=body.spec.concept,
            concept=body.spec.concept,
        ),
        difficulty=DifficultyMeta(level=body.spec.difficulty, target_time_sec=120),
        learning={"skill": ("equation_transformation",)},
        problem=ProblemTemplate(
            statement="스캐폴드 문제 본문 — 실제 LLM 생성 연동 필요",
            template=None,
            variables={},
            constraints=(),
        ),
        answer=AnswerSpec(type="integer", value="0", expression=None, choices=None),
        solution=(),
        hints=(),
    )

    report = pipeline.validate(dsl)
    report = quality_gate.evaluate(report)

    if not report.publishable:
        # Repair Loop는 후속 LLM 연동 후 활성화한다.
        pass

    return GenerateResponse(
        generation_id=f"GEN-{body.spec.subject[:3].upper()}-001",
        status="validated" if report.publishable else "failed_validation",
        contents=[
            {
                "content_id": dsl.content_id,
                "dsl_version": dsl.dsl_version,
                "quality_score": report.quality_score,
                "publishable": report.publishable,
            }
        ],
    )


@router.post("/validate", response_model=ValidateResponse, summary="DSL 검증")
async def validate_dsl(
    body: ValidateRequest,
    user: CurrentUser,
    pipeline: ValidationPipelineDep,
    quality_gate: QualityGateDep,
) -> ValidateResponse:
    """DSL을 6단계 검증 파이프라인으로 검증한다."""
    report = pipeline.validate(body.dsl)
    report = quality_gate.evaluate(report)
    return ValidateResponse(report=report)


@router.post("/compile", response_model=CompileResponse, summary="DSL 컴파일")
async def compile_dsl(
    body: CompileRequest,
    user: CurrentUser,
    pipeline: ValidationPipelineDep,
    quality_gate: QualityGateDep,
    compiler: CompilerDep,
) -> CompileResponse:
    """검증된 DSL을 Runtime 객체로 컴파일한다."""
    report = pipeline.validate(body.dsl)
    report = quality_gate.evaluate(report)

    if not report.publishable:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "message": "검증을 통과하지 못해 컴파일할 수 없습니다.",
                "signals": report.signals,
            },
        )

    binding = None
    if body.binding is not None:
        binding = VariableBinding(values=body.binding)

    content = compiler.compile(body.dsl, binding=binding)
    return CompileResponse(content=content)


__all__ = ["router"]
