"""SolutionPath 조회 store — 승격된 풀이 경로의 *읽기* 표면 (S4-09·D1 reader ②의 하부).

`solution_paths`(헤더·`db/models/solution_path.py`)에서 문제 단위로 경로를 조회한다. 쓰기는
승격 어댑터(`whs/path_promotion.py`)만 한다 — 본 모듈은 읽기 전용(commit 없음·저장소 패턴).

소비처(계층 방향): L4 `scene_generation.find_step_panel_solution_path_id`가 본 모듈을
*다운콜*해 `StepPanelElement.solution_path_id` 댕글링을 해소한다(L4→L3 — import-linter 계약
방향). SolutionPath는 L3 소유 엔티티(yaml `layer: L3`)라 조회 좌석도 L3에 둔다.

저장소 패턴(`whs/solution_bank.py` 선례): AsyncSession 주입·순수 ORM/쿼리빌더·결정적 정렬.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from whymath_backend.db.models.solution_path import SolutionPath

__all__ = ["find_solution_path_id", "get_solution_paths"]


async def get_solution_paths(session: AsyncSession, problem_id: uuid.UUID) -> list[SolutionPath]:
    """문제의 승격된 풀이 경로 *전부*를 결정적 순서로 조회한다(검사·열람용).

    `(created_at, solution_path_id)` 정렬로 재실행에도 순서가 안정적이다.
    `idx_solution_paths_problem` 인덱스를 탄다.
    """
    stmt = (
        select(SolutionPath)
        .where(SolutionPath.problem_id == problem_id)
        .order_by(SolutionPath.created_at, SolutionPath.solution_path_id)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def find_solution_path_id(session: AsyncSession, problem_id: uuid.UUID) -> str | None:
    """문제에 승격된 SolutionPath가 있으면 *첫* 경로의 id, 없으면 None.

    `StepPanelElement.solution_path_id` 결선용 최소 조회 — "첫 경로"는 결정적 순서
    (`created_at, solution_path_id`)의 첫 행이다. 다중 경로 간 *선택 정책*(선호 유형·검수
    우선 등)은 L2 `preferred_solution_style` 추적이 서는 후속 몫이라 여기서 만들지 않는다
    (`solution_module_gap_review.md` §4-⑤).
    """
    stmt = (
        select(SolutionPath.solution_path_id)
        .where(SolutionPath.problem_id == problem_id)
        .order_by(SolutionPath.created_at, SolutionPath.solution_path_id)
        .limit(1)
    )
    result = await session.execute(stmt)
    row = result.scalars().first()
    return row
