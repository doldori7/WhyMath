"""WH-S 검증 풀이 저장소 — `verified_solutions` 적재·조회(설계 §2.4·§3 도구 8·§5·§7).

설계 정본: `docs/architecture/03b_wh_s_solver_harness.md` §2.4(검증 풀이 저장소)·§3 도구 8
(`finalize`)·§5(자기 진화 데이터)·§7(WH-1 콘텐츠 원천). 솔버가 `finalize`로 조립·검증한 완전 풀이
경로를 *적재*(`bank_solution`)하고, 학습/콘텐츠 소비가 *조회*(`get_verified`/`get_solutions`)한다.

★학습 안전(§3·R-S2 보상 해킹 차단): `bank_solution`은 등급 `verified`/`unverified`만 받는다
(`WhsSolutionGrade` enum에 failed 없음 — 구조 차단). `get_verified`는 **verified만** 반환한다 —
자기 진화 학습 데이터(§5)에 *판정 불가(unverified)는 절대 섞이지 않는다*. `unverified`는 보관하되
격리(§3) — 감사·재검증용이며 학습 배제.

저장소 패턴(`whs/node_store.py` 선례 답습):
  - 모든 함수는 `AsyncSession`을 *주입받는다*. 트랜잭션 commit은 호출자 관리.
  - **순수 ORM/쿼리빌더만**(원시 SQL 0). `bank_solution`은 새 행의 server_default(id·created_at)를
    호출자가 바로 쓰게 `flush`+`refresh`(commit은 호출자).

WH-S 오프라인(§7.5): `verified_solutions`는 *시스템이 스스로 푼* 풀이이며 학생 PII가 아니다
(redaction·암호화 무관). 학생 경로 미개입·API 노출 0(WH-1 소비 시 표현 계층은 후속).

범위 밖(후속): 솔버 `finalize`·자기진화 export(§5)·WH-1 콘텐츠 변환(§7)·중복 dedup. 본 모듈은
*검증 풀이 저장소 CRUD*만 둔다.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from whymath_backend.db.models.verified_solution import (
    VerifiedSolution,
    WhsSolutionGrade,
)

__all__ = [
    "bank_solution",
    "get_solutions",
    "get_verified",
]


async def bank_solution(
    session: AsyncSession,
    *,
    problem_id: uuid.UUID,
    grade: WhsSolutionGrade,
    solution_path: dict[str, Any],
    strategy_tag: str | None = None,
    answer: str | None = None,
    source_root_id: uuid.UUID | None = None,
) -> VerifiedSolution:
    """완전 풀이 경로 1개를 저장소에 적재한다(§2.4 — finalize 커밋 대상).

    `grade`는 `verified`(학습 채택 가능) 또는 `unverified`(격리·학습 배제)만 가능하다 —
    `WhsSolutionGrade` enum이 failed를 배제해 *틀린 풀이의 적재를 구조 차단*한다(§3·R-S2). 한 문제에
    여러 풀이(다중 전략)를 적재할 수 있다(problem_id UNIQUE 없음). `flush`+`refresh`로 새 행의
    `id`·`created_at`을 같은 트랜잭션에서 가시화(commit은 호출자).
    """
    solution = VerifiedSolution(
        problem_id=problem_id,
        grade=grade,
        solution_path=solution_path,
        strategy_tag=strategy_tag,
        answer=answer,
        source_root_id=source_root_id,
    )
    session.add(solution)
    await session.flush()
    await session.refresh(solution)
    return solution


async def get_solutions(session: AsyncSession, problem_id: uuid.UUID) -> list[VerifiedSolution]:
    """주어진 문제의 *모든* 적재 풀이(verified + unverified)를 조회한다(검사·다중 풀이 열람).

    `(problem_id, grade)` 인덱스의 선행 컬럼을 prefix로 탄다. `created_at`·`id` 정렬로 결정적 순서.
    학습 데이터로 쓰려면 `get_verified`를 써라(unverified 격리·R-S2).
    """
    stmt = (
        select(VerifiedSolution)
        .where(VerifiedSolution.problem_id == problem_id)
        .order_by(VerifiedSolution.created_at, VerifiedSolution.id)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_verified(session: AsyncSession, problem_id: uuid.UUID) -> list[VerifiedSolution]:
    """주어진 문제의 **verified 풀이만** 조회한다 — 자기 진화 학습 데이터 원천(§5·R-S2 안전).

    `unverified`(격리·§3)는 *절대 포함하지 않는다* — 판정 불가 풀이가 학습 데이터에 섞이는 것을
    저장소 차원에서 막는다(보상 해킹 차단). `(problem_id, grade)` 복합 인덱스를 정확히 탄다.
    """
    stmt = (
        select(VerifiedSolution)
        .where(
            VerifiedSolution.problem_id == problem_id,
            VerifiedSolution.grade == WhsSolutionGrade.VERIFIED,
        )
        .order_by(VerifiedSolution.created_at, VerifiedSolution.id)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())
