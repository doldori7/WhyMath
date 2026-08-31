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

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from whymath_backend.api._auth import CurrentUser
from whymath_backend.db.session import get_session
from whymath_backend.l1.standards.alignment_query import (
    AlignmentAxis,
    get_alignments,
    log_join_stats,
)
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

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/dsl", tags=["dsl"])

# get_session 의존성 — Annotated 메타데이터(B008 회피·concepts.py 선례).
SessionDep = Annotated[AsyncSession, Depends(get_session)]


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
    session: SessionDep,
    pipeline: ValidationPipelineDep,
    repair_engine: RepairEngineDep,
    quality_gate: QualityGateDep,
) -> GenerateResponse:
    """콘텐츠 사양으로 DSL을 생성한다.

    현재 MVP는 LLM 생성 대신 *스캐폴드 DSL*을 만들어 검증 파이프라인을
    검증하는 데 집중한다. 실제 LLM 생성은 `l3/pipeline.py`와 연동한다.

    **CUR-12 통합 경유**: 사양의 `concept`(개념 키)을 `l1/standards/alignment_query.
    get_alignments`(단일 진실 원천)에 대조해 성취기준 코드를 `curriculum.standard_codes`에
    싣는다. 개념 키가 개념 공간에 없으면 빈 채로 남고 — 그것이 정직한 결과다 — 조인이
    성립했는지 아닌지는 `log_join_stats`가 회계로 남긴다(0건이 "매핑 없음"인지 "조인 실패"인지
    묻히지 않게 한다·CLAUDE.md 침묵 실패 금지).
    """
    alignment = await get_alignments(
        session,
        concept_codes=[body.spec.concept],
        axes={AlignmentAxis.ATOM_NODE, AlignmentAxis.CONCEPT_STANDARD_LINK},
    )
    log_join_stats(
        alignment.stats,
        logger=logger,
        context=f"dsl.generate/concept={body.spec.concept}",
    )

    # TODO: l3/pipeline.py 연동 — 현재는 사양 기반 스캐폴드 DSL 생성
    dsl = ProblemDSL(
        content_id=f"{body.spec.subject[:3].upper()}-{body.spec.concept[:8].upper()}-000001",
        dsl_version="1.0",
        curriculum=CurriculumMeta(
            subject=body.spec.subject,
            grade=body.spec.grade,
            domain=body.spec.concept,
            concept=body.spec.concept,
            standard_codes=alignment.standard_refs(),
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
                # CUR-12 — 정렬 결과가 실제로 DSL에 실렸는지 응답에서 관측 가능해야 한다.
                # 아무도 보지 못하는 슬롯은 배선됐는지 확인할 수 없다(검증 장치의 배선 확인).
                "curriculum": dsl.curriculum.model_dump(mode="json"),
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
