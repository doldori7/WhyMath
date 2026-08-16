"""Repair Loop 테스트."""

import pytest

from whymath_backend.l3.dsl.models import (
    AnswerSpec,
    CurriculumMeta,
    DifficultyMeta,
    ProblemDSL,
    ProblemTemplate,
    ValidationReport,
)
from whymath_backend.l3.dsl.repair import InMemoryHumanReviewQueue, RepairEngine


class _AlwaysFailLLM:
    """항상 같은 DSL을 돌려주는 실패 LLM."""

    async def repair(self, dsl, report, attempt):  # noqa: ANN001
        return dsl


class _SuccessOnSecondLLM:
    """두 번째 시도에서 publishable=True로 만드는 LLM."""

    async def repair(self, dsl, report, attempt):  # noqa: ANN001
        if attempt == 2:
            return dsl
        return dsl


@pytest.mark.asyncio
async def test_repair_engine_escalates_after_max_attempts() -> None:
    dsl = ProblemDSL(
        content_id="REPAIR-001",
        curriculum=CurriculumMeta(
            subject="mathematics", grade="middle_2", concept="linear_equation"
        ),
        difficulty=DifficultyMeta(level=3),
        problem=ProblemTemplate(statement="x + 2 = 5"),
        answer=AnswerSpec(type="integer", value="3"),
    )
    report = ValidationReport(math="FAIL", publishable=False)

    queue = InMemoryHumanReviewQueue()
    engine = RepairEngine(llm=_AlwaysFailLLM(), human_queue=queue)
    result = await engine.repair(dsl, report)

    assert result.attempts == 3
    assert result.escalated_to_human is True
    assert result.human_review_ticket is not None
    assert len(queue.items) == 1


@pytest.mark.asyncio
async def test_repair_engine_returns_early_when_already_publishable() -> None:
    dsl = ProblemDSL(
        content_id="REPAIR-002",
        curriculum=CurriculumMeta(
            subject="mathematics", grade="middle_2", concept="linear_equation"
        ),
        difficulty=DifficultyMeta(level=3),
        problem=ProblemTemplate(statement="x + 2 = 5"),
        answer=AnswerSpec(type="integer", value="3"),
    )
    report = ValidationReport(math="PASS", publishable=True)

    queue = InMemoryHumanReviewQueue()
    engine = RepairEngine(llm=_AlwaysFailLLM(), human_queue=queue)
    result = await engine.repair(dsl, report)

    assert result.attempts == 0
    assert result.escalated_to_human is False
    assert result.dsl is dsl
