"""DSL 콘텐츠 생성기 — L3 콘텐츠 생성·검증의 내부 컴파일러.

설계 정본: `docs/architecture/03d_dsl_content_generator.md`.

LLM이 만든 자연어 콘텐츠를 교육 DSL로 정의하고, 다중 검증·수학 검증·교육 검증을
통과한 것만 컴파일해 Runtime으로 넘긴다. LLM은 생성하고, 결정론적 엔진은 판정한다.
"""

from whymath_backend.l3.dsl.models import (
    AdaptationSpec,
    AnswerSpec,
    CompiledContent,
    ConstraintSpec,
    ContentLifecycleState,
    ContentSpecification,
    CurriculumMeta,
    DifficultyMeta,
    HintSpec,
    MisconceptionSpec,
    ProblemDSL,
    ProblemTemplate,
    SolutionStepSpec,
    ValidationReport,
    VariableSpec,
)
from whymath_backend.l3.dsl.variable_engine import VariableBinding, VariableEngine

__all__ = [
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
    "ProblemDSL",
    "ProblemTemplate",
    "SolutionStepSpec",
    "ValidationReport",
    "VariableBinding",
    "VariableEngine",
    "VariableSpec",
]
