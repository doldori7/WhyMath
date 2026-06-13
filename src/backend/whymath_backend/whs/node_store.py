"""WH-S 풀이 경로 트리 노드 비동기 저장소 — `solution_nodes` CRUD (설계 §2.1·§9 S1).

설계 정본: `docs/architecture/03b_wh_s_solver_harness.md` §2.1(풀이 경로 트리 — Solution Tree)·
§9 S1. 본 모듈은 S1 슬라이스의 *풀이 트리 상태 계층 접근*만 제공한다 — 솔버 루프·MCTS·도구 8종이
이 저장소를 통해 노드를 생성·조회·갱신한다(루프 본체는 후속·모듈 끝 "범위 밖").

저장소 패턴(`l2/mastery_tracking.py` 선례 답습):
  - 모든 함수는 `AsyncSession`을 *주입받는다*(엔진·세션 생성은 호출자 책임).
  - **트랜잭션(commit/rollback)은 호출자 관리** — 여기서 자동 commit하지 않는다(`get_session`
    의존성 주석과 정합·읽기 전용 경로까지 강제 commit하지 않기 위함). 단, 새 행/갱신이 PK·
    server_default를 즉시 반영해야 하는 함수는 `flush`만 한다(같은 트랜잭션 내 가시성 확보·
    commit은 호출자).
  - **순수 ORM/쿼리빌더만 사용**(원시 SQL 0 — CLAUDE.md "ORM/쿼리 빌더·원시 SQL 최소화").

WH-S 오프라인(§7.5): `solution_nodes`는 *시스템 솔버 내부 탐색 상태*이며 학생 PII가 아니다
(redaction·암호화 무관). 학생 세션 경로 미개입 — API 엔드포인트 노출 0(이 저장소는 오프라인
솔버 루프 전용 라이브러리).

범위 밖(후속 — §9 S1+): 솔버 루프(LLM 정책 모델·Ollama·Phaiakes9·MCTS-lite 탐색·도구 8종)·
다른 저장소(§2.2 Verified Lemma Store·§2.3 Dead-End Log·§2.4 Verified Solution Bank)·PRM
구축·Tier3(Lean4)·시드 모델 실행. 본 모듈은 *풀이 트리 노드 CRUD*만 둔다.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from whymath_backend.db.models.solution_node import NodeVerifyStatus, SolutionNode

__all__ = [
    "create_node",
    "get_children",
    "get_node",
    "get_roots",
    "increment_visits",
    "update_evaluation",
]


async def create_node(
    session: AsyncSession,
    *,
    problem_id: uuid.UUID,
    parent_id: uuid.UUID | None = None,
    state_repr: dict[str, Any],
    action: str | None = None,
    prm_score: float | None = None,
    verify_status: NodeVerifyStatus = NodeVerifyStatus.PENDING,
) -> SolutionNode:
    """풀이 트리에 노드 1개를 추가한다(§2.1 노드=상태·엣지=행동).

    `parent_id=None`이면 트리 루트(MCTS 탐색 시작점)다. `verify_status`는 확장 직후 기본
    `pending`(verify 도구를 거치기 전). `flush`로 server_default(`id`·`visits`·타임스탬프)를
    즉시 채워 호출자가 새 노드의 `id`를 바로 쓸 수 있게 한다(commit은 호출자).
    """
    node = SolutionNode(
        problem_id=problem_id,
        parent_id=parent_id,
        state_repr=state_repr,
        action=action,
        prm_score=prm_score,
        verify_status=verify_status,
    )
    session.add(node)
    # server_default(id·visits·created_at)를 같은 트랜잭션에서 가시화(commit은 호출자).
    await session.flush()
    await session.refresh(node)
    return node


async def get_node(session: AsyncSession, node_id: uuid.UUID) -> SolutionNode | None:
    """노드 1개를 PK로 조회한다 — 없으면 None."""
    return await session.get(SolutionNode, node_id)


async def get_children(session: AsyncSession, node_id: uuid.UUID) -> list[SolutionNode]:
    """주어진 노드의 직접 자식 노드들(`parent_id == node_id`)을 조회한다.

    트리 한 단계만 내려간다(재귀 아님 — MCTS 확장은 한 레벨씩 진행). 생성순(created_at)으로
    정렬해 결정적 순서를 보장한다.
    """
    stmt = (
        select(SolutionNode)
        .where(SolutionNode.parent_id == node_id)
        .order_by(SolutionNode.created_at, SolutionNode.id)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_roots(session: AsyncSession, problem_id: uuid.UUID) -> list[SolutionNode]:
    """주어진 문제의 트리 루트들(`parent_id IS NULL` AND `problem_id` 일치)을 조회한다.

    한 문제에 대해 여러 탐색 시드(다중 루트)를 둘 수 있다(다중 풀이 경로 — §2.4). 생성순 정렬.
    """
    stmt = (
        select(SolutionNode)
        .where(
            SolutionNode.problem_id == problem_id,
            SolutionNode.parent_id.is_(None),
        )
        .order_by(SolutionNode.created_at, SolutionNode.id)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def increment_visits(session: AsyncSession, node_id: uuid.UUID) -> None:
    """노드의 MCTS 방문 횟수를 *원자적으로* 1 증가시킨다.

    SQL UPDATE(`visits = visits + 1`)로 read-modify-write 경합을 피한다 — Python으로 읽어
    +1해 쓰면 동시 방문에서 갱신 손실이 날 수 있다. `updated_at`은 onupdate로 자동 갱신.
    트랜잭션 commit은 호출자 관리.
    """
    stmt = (
        update(SolutionNode)
        .where(SolutionNode.id == node_id)
        .values(visits=SolutionNode.visits + 1)
    )
    await session.execute(stmt)


async def update_evaluation(
    session: AsyncSession,
    node_id: uuid.UUID,
    *,
    prm_score: float | None = None,
    verify_status: NodeVerifyStatus | None = None,
) -> None:
    """노드의 평가 신호(`prm_score`·`verify_status`)를 갱신한다(verify·PRM 후 호출).

    인자로 *준 값만* 갱신한다 — 둘 다 None이면 무동작(불필요한 UPDATE·updated_at 변동 방지).
    `prm_score=None`을 *명시적으로 비우려는* 의도와 "안 건드림"을 구분하지 않는다(현 범위에서
    PRM 점수를 None으로 되돌릴 일이 없으므로 단순화 — 필요 시 후속에서 sentinel 도입).
    트랜잭션 commit은 호출자 관리.
    """
    values: dict[str, Any] = {}
    if prm_score is not None:
        values["prm_score"] = prm_score
    if verify_status is not None:
        values["verify_status"] = verify_status
    if not values:
        return
    stmt = update(SolutionNode).where(SolutionNode.id == node_id).values(**values)
    await session.execute(stmt)
