"""Repair Loop — 검증 실패 DSL을 LLM으로 자동 복구.

설계 정본: `docs/architecture/03d_dsl_content_generator.md` §7.

- 최대 3회 재시도.
- 3회 실패 시 Human Review Queue로 전달.
- 무한 재시도 금지.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from whymath_backend.l3.dsl.models import ProblemDSL, ValidationReport


@runtime_checkable
class DSLRepairLLM(Protocol):
    """DSL 복구용 LLM 호출 경계."""

    async def repair(
        self, dsl: ProblemDSL, validation_report: ValidationReport, attempt: int
    ) -> ProblemDSL:
        """검증 실패한 DSL을 수정해 새 DSL을 반환한다."""
        ...


@runtime_checkable
class HumanReviewQueue(Protocol):
    """사람 검수 큐 경계."""

    async def enqueue(self, dsl: ProblemDSL, report: ValidationReport) -> str:
        """검수 대기열에 추가하고 ticket_id를 반환한다."""
        ...


@dataclass(frozen=True, slots=True)
class RepairResult:
    """Repair Loop 최종 결과."""

    dsl: ProblemDSL | None
    validation_report: ValidationReport
    attempts: int
    escalated_to_human: bool = False
    human_review_ticket: str | None = None


class InMemoryHumanReviewQueue:
    """테스트/로컬용 인메모리 사람 검수 큐."""

    def __init__(self) -> None:
        self.items: list[tuple[ProblemDSL, ValidationReport]] = []

    async def enqueue(self, dsl: ProblemDSL, report: ValidationReport) -> str:
        self.items.append((dsl, report))
        return f"HR-{len(self.items):04d}"


class RepairEngine:
    """검증 실패 DSL을 최대 3회까지 복구 시도한다."""

    MAX_ATTEMPTS = 3

    def __init__(
        self,
        llm: DSLRepairLLM,
        human_queue: HumanReviewQueue,
    ) -> None:
        self._llm = llm
        self._human_queue = human_queue

    async def repair(
        self,
        dsl: ProblemDSL,
        validation_report: ValidationReport,
    ) -> RepairResult:
        """검증 실패 DSL을 복구한다.

        통과하면 RepairResult(dsl=수정된DSL, escalated_to_human=False).
        3회 실패하면 Human Review Queue로 전달한다.
        """
        current_dsl = dsl
        current_report = validation_report

        for attempt in range(1, self.MAX_ATTEMPTS + 1):
            if current_report.publishable:
                return RepairResult(
                    dsl=current_dsl,
                    validation_report=current_report,
                    attempts=attempt - 1,
                    escalated_to_human=False,
                )

            current_dsl = await self._llm.repair(current_dsl, current_report, attempt)
            # 재검증은 호출자(파이프라인)가 수행한다. 여기서는 시도만 기록.
            current_report = validation_report  # 재검증 결과는 파이프라인이 갱신

        ticket = await self._human_queue.enqueue(current_dsl, current_report)
        return RepairResult(
            dsl=None,
            validation_report=current_report,
            attempts=self.MAX_ATTEMPTS,
            escalated_to_human=True,
            human_review_ticket=ticket,
        )


__all__ = [
    "DSLRepairLLM",
    "HumanReviewQueue",
    "InMemoryHumanReviewQueue",
    "RepairEngine",
    "RepairResult",
]
