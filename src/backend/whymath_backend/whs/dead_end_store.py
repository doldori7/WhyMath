"""WH-S 실패 접근 로그 저장소 — `dead_end_log` 멱등 기록·회피 조회(설계 §2.3·§3 도구 7).

설계 정본: `docs/architecture/03b_wh_s_solver_harness.md` §2.3(실패 접근 로그)·§3 도구 7
(`log_deadend`). 솔버 탐색 정책이 막다른 길을 *기록*(`log_dead_end`)하고, 행동 적용 전 *회피
조회*(`is_dead_end`)로 같은 막다른 길 재진입을 차단한다(LLM의 같은 실수 반복을 구조 차단).

저장소 패턴(`whs/node_store.py` 선례 답습):
  - 모든 함수는 `AsyncSession`을 *주입받는다*(엔진·세션 생성은 호출자 책임).
  - **트랜잭션(commit/rollback)은 호출자 관리** — 여기서 자동 commit하지 않는다.
  - **순수 ORM/쿼리빌더만**(원시 SQL 0). 멱등 INSERT는 PG `ON CONFLICT DO NOTHING`을 쿼리빌더
    (`postgresql.insert`)로 표현한다.

WH-S 오프라인(§7.5): `dead_end_log`는 *시스템 솔버 내부 탐색 실패 상태*이며 학생 PII가 아니다
(redaction·암호화 무관·API 노출 0).

범위 밖(후속): 솔버 루프(탐색 정책이 `is_dead_end`로 회피)·해시 스킴 표준화. 본 모듈은 *실패
접근 로그 CRUD*만 둔다.
"""

from __future__ import annotations

import uuid

from sqlalchemy import exists, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from whymath_backend.db.models.dead_end_log import DeadEndLog

__all__ = [
    "get_dead_ends",
    "is_dead_end",
    "log_dead_end",
]


async def log_dead_end(
    session: AsyncSession,
    *,
    problem_id: uuid.UUID,
    state_hash: str,
    action: str,
    reason: str | None = None,
) -> None:
    """막다른 길 `(problem_id, state_hash, action)`을 *멱등* 기록한다(§2.3 중복 차단).

    같은 막다른 길을 두 번 기록해도 한 행이다 — `ON CONFLICT (problem_id, state_hash, action) DO
    NOTHING`(복합 UNIQUE). 즉 재진입을 기록해도 안전(중복 행·예외 없음). 이미 있던 행의 `reason`은
    덮어쓰지 않는다(최초 기록 보존 — DO NOTHING). 트랜잭션 commit은 호출자 관리.
    """
    stmt = (
        pg_insert(DeadEndLog)
        .values(
            problem_id=problem_id,
            state_hash=state_hash,
            action=action,
            reason=reason,
        )
        .on_conflict_do_nothing(
            constraint="uq_dead_end_log_problem_state_action",
        )
    )
    await session.execute(stmt)


async def is_dead_end(
    session: AsyncSession,
    *,
    problem_id: uuid.UUID,
    state_hash: str,
    action: str,
) -> bool:
    """이 `(problem_id, state_hash, action)`이 이미 막다른 길로 기록됐는지 — 탐색 정책 회피 조회.

    복합 UNIQUE 인덱스를 정확 매칭으로 탄다. `EXISTS`로 행 적재 없이 boolean만 받는다(가벼움).
    """
    stmt = select(
        exists().where(
            DeadEndLog.problem_id == problem_id,
            DeadEndLog.state_hash == state_hash,
            DeadEndLog.action == action,
        )
    )
    result = await session.execute(stmt)
    return bool(result.scalar())


async def get_dead_ends(session: AsyncSession, problem_id: uuid.UUID) -> list[DeadEndLog]:
    """주어진 문제의 막다른 길 전체를 기록순으로 조회(검사·디버그·탐색 정책 일괄 로드).

    복합 UNIQUE 인덱스의 선행 컬럼(`problem_id`)을 prefix로 탄다. `created_at`·`id` 정렬로 결정적
    순서를 보장한다.
    """
    stmt = (
        select(DeadEndLog)
        .where(DeadEndLog.problem_id == problem_id)
        .order_by(DeadEndLog.created_at, DeadEndLog.id)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())
