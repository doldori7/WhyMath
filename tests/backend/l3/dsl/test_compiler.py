"""콘텐츠 컴파일러 테스트."""

from whymath_backend.l3.dsl.compiler import ContentCompiler
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


def test_compiler_fixed_problem() -> None:
    dsl = ProblemDSL(
        content_id="COMP-001",
        curriculum=CurriculumMeta(
            subject="mathematics", grade="middle_2", concept="linear_equation"
        ),
        difficulty=DifficultyMeta(level=3),
        problem=ProblemTemplate(statement="x + 2 = 5 일 때 x를 구하여라."),
        answer=AnswerSpec(type="integer", value="3"),
        solution=(
            SolutionStepSpec(order=1, content="양변에서 2를 뺀다."),
            SolutionStepSpec(order=2, content="x = 3"),
        ),
        hints=(HintSpec(level=1, text="양변에서 같은 수를 빼 보세요."),),
    )
    compiler = ContentCompiler()
    content = compiler.compile(dsl)

    assert content.content_id == "COMP-001"
    assert content.problem_text == "x + 2 = 5 일 때 x를 구하여라."
    assert content.answer == "3"
    assert content.solution_texts == ("양변에서 2를 뺀다.", "x = 3")
    assert content.hint_texts == ("양변에서 같은 수를 빼 보세요.",)
    assert content.grading["type"] == "numeric"


def test_compiler_variable_problem() -> None:
    dsl = ProblemDSL(
        content_id="COMP-002",
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
    compiler = ContentCompiler()
    content = compiler.compile(dsl)

    assert content.problem_text == "2x + 4 = 12"
    assert content.answer == "4"


def test_compiler_includes_concept_dsl() -> None:
    dsl = ProblemDSL(
        content_id="COMP-003",
        curriculum=CurriculumMeta(
            subject="mathematics", grade="middle_2", concept="linear_equation"
        ),
        difficulty=DifficultyMeta(level=3),
        problem=ProblemTemplate(statement="x + 2 = 5"),
        answer=AnswerSpec(type="integer", value="3"),
    )
    compiler = ContentCompiler()
    content = compiler.compile(dsl)
    assert content.concept_dsl is not None
    assert content.concept_dsl["code"] == "COMP-003"
    assert content.concept_dsl["name"] == "linear_equation"
