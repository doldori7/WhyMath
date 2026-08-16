"""수학 검증기 테스트."""

from whymath_backend.l3.dsl.math_verifier import (
    MathValidator,
    verify_problem_answer,
    verify_solution_consistency,
)
from whymath_backend.l3.dsl.models import (
    AnswerSpec,
    CurriculumMeta,
    DifficultyMeta,
    ProblemDSL,
    ProblemTemplate,
    SolutionStepSpec,
    VariableSpec,
)
from whymath_backend.l3.dsl.variable_engine import VariableBinding


def _make_dsl_with_answer(answer: AnswerSpec) -> ProblemDSL:
    return ProblemDSL(
        content_id="MATH-001",
        curriculum=CurriculumMeta(
            subject="mathematics", grade="middle_2", concept="linear_equation"
        ),
        difficulty=DifficultyMeta(level=3),
        problem=ProblemTemplate(statement="x + 2 = 5"),
        answer=answer,
    )


def test_verify_problem_answer_valid_integer() -> None:
    dsl = _make_dsl_with_answer(AnswerSpec(type="integer", value="3"))
    assert verify_problem_answer(dsl) is None


def test_verify_problem_answer_invalid_parse() -> None:
    dsl = _make_dsl_with_answer(AnswerSpec(type="integer", value="not_a_number"))
    signal = verify_problem_answer(dsl)
    assert signal is not None
    assert "정답이 숫자가 아닙니다" in signal.reason


def test_verify_problem_answer_expression_with_binding() -> None:
    dsl = ProblemDSL(
        content_id="MATH-002",
        curriculum=CurriculumMeta(
            subject="mathematics", grade="middle_2", concept="linear_equation"
        ),
        difficulty=DifficultyMeta(level=3),
        problem=ProblemTemplate(
            template="{a}x + {b} = {c}",
            variables={
                "a": VariableSpec(type="integer", range=(2, 2)),
                "b": VariableSpec(type="integer", range=(4, 4)),
                "c": VariableSpec(type="integer", range=(12, 12)),
            },
        ),
        answer=AnswerSpec(type="integer", expression="(c - b) / a"),
    )
    binding = VariableBinding(values={"a": "2", "b": "4", "c": "12"})
    assert verify_problem_answer(dsl, binding) is None


def test_verify_solution_consistency_valid() -> None:
    dsl = ProblemDSL(
        content_id="MATH-003",
        curriculum=CurriculumMeta(
            subject="mathematics", grade="middle_2", concept="linear_equation"
        ),
        difficulty=DifficultyMeta(level=3),
        problem=ProblemTemplate(statement="x + 2 = 5"),
        answer=AnswerSpec(type="integer", value="3"),
        solution=(
            SolutionStepSpec(order=1, content="양변에서 2를 뺀다.", formula="x = 5 - 2"),
            SolutionStepSpec(order=2, content="계산한다.", formula="x = 3"),
        ),
    )
    assert verify_solution_consistency(dsl) is None


def test_verify_solution_consistency_invalid_formula() -> None:
    dsl = ProblemDSL(
        content_id="MATH-004",
        curriculum=CurriculumMeta(
            subject="mathematics", grade="middle_2", concept="linear_equation"
        ),
        difficulty=DifficultyMeta(level=3),
        problem=ProblemTemplate(statement="x + 2 = 5"),
        answer=AnswerSpec(type="integer", value="3"),
        solution=(SolutionStepSpec(order=1, content="틀린 수식", formula="x === 3"),),
    )
    signal = verify_solution_consistency(dsl)
    assert signal is not None
    assert signal.kind == "solution"


def test_math_validator_integration() -> None:
    dsl = ProblemDSL(
        content_id="MATH-005",
        curriculum=CurriculumMeta(
            subject="mathematics", grade="middle_2", concept="linear_equation"
        ),
        difficulty=DifficultyMeta(level=3),
        problem=ProblemTemplate(statement="x + 2 = 5"),
        answer=AnswerSpec(type="integer", value="3"),
    )
    validator = MathValidator()
    result = validator.validate(dsl)
    assert result.passed is True
