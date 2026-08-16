"""DSL 콘텐츠 생성기 모델 테스트."""

import pytest
from pydantic import ValidationError

from whymath_backend.l3.dsl.models import (
    AnswerSpec,
    CurriculumMeta,
    DifficultyMeta,
    HintSpec,
    ProblemDSL,
    ProblemTemplate,
    SolutionStepSpec,
    VariableSpec,
)


def _make_minimal_dsl() -> ProblemDSL:
    return ProblemDSL(
        content_id="TEST-001",
        curriculum=CurriculumMeta(
            subject="mathematics", grade="middle_2", concept="linear_equation"
        ),
        difficulty=DifficultyMeta(level=3),
        problem=ProblemTemplate(statement="x + 2 = 5 일 때 x를 구하여라."),
        answer=AnswerSpec(type="integer", value="3"),
    )


def test_problem_dsl_minimal_valid() -> None:
    dsl = _make_minimal_dsl()
    assert dsl.content_id == "TEST-001"
    assert dsl.curriculum.subject == "mathematics"


def test_problem_template_requires_statement_or_template() -> None:
    with pytest.raises(ValidationError, match="statement 또는 template"):
        ProblemTemplate()


def test_variable_spec_string_requires_choices() -> None:
    with pytest.raises(ValidationError, match="choices가 필요합니다"):
        VariableSpec(type="string")


def test_variable_spec_integer_requires_range() -> None:
    with pytest.raises(ValidationError, match="range가 필요합니다"):
        VariableSpec(type="integer")


def test_answer_spec_requires_single_source() -> None:
    with pytest.raises(ValidationError, match="하나는 필수입니다"):
        AnswerSpec(type="integer")

    with pytest.raises(ValidationError, match="동시에 하나만"):
        AnswerSpec(type="integer", value="1", expression="x")


def test_problem_dsl_solution_order_must_be_sorted() -> None:
    with pytest.raises(ValidationError, match="order 오름차순"):
        ProblemDSL(
            content_id="TEST-002",
            curriculum=CurriculumMeta(
                subject="mathematics", grade="middle_2", concept="linear_equation"
            ),
            difficulty=DifficultyMeta(level=3),
            problem=ProblemTemplate(statement="x + 2 = 5"),
            answer=AnswerSpec(type="integer", value="3"),
            solution=(
                SolutionStepSpec(order=2, content="둘째 단계"),
                SolutionStepSpec(order=1, content="첫째 단계"),
            ),
        )


def test_hint_spec_level_must_be_positive() -> None:
    with pytest.raises(ValidationError):
        HintSpec(level=0, text="힌트")
