"""WH-S 검증된 중간 결과 저장소 — `verified_lemmas` 멱등 적재·재사용 조회(설계 §2.2·§3 도구 7).

설계 정본: `docs/architecture/03b_wh_s_solver_harness.md` §2.2(검증된 중간 결과 저장소)·§3 도구 7
(`log_lemma`). 솔버가 verify 통과한 부분 결과를 *적재*(`log_lemma`)하고, 다른 가지가 같은 보조
목표에 닿으면 *재사용 조회*(`find_lemma`)로 중복 탐색을 제거한다(난해 문제 탐색 효율의 핵심).

저장소 패턴(`whs/dead_end_store.py`·`solution_bank.py` 선례 답습):
  - 모든 함수는 `AsyncSession`을 *주입받는다*. 트랜잭션 commit은 호출자 관리.
  - **순수 ORM/쿼리빌더만**(원시 SQL 0). 멱등 INSERT는 PG `ON CONFLICT DO NOTHING`을 쿼리빌더
    (`postgresql.insert`)로 표현한다.

★검증 전제(§2.2): 본 저장소는 *검증된* 보조정리만 담는다 — `log_lemma`는 verify 도구 통과 뒤
호출된다(미검증 부분 결과는 애초에 오지 않음). 등급 컬럼이 없는 이유(모델 docstring 참조).

WH-S 오프라인(§7.5): `verified_lemmas`는 *시스템 솔버 내부 중간 산출*이며 학생 PII가 아니다
(redaction·암호화 무관·API 노출 0).

범위 밖(후속): 솔버 루프(탐색이 `find_lemma`로 재사용·가지치기)·키 스킴 표준화. 본 모듈은 *검증
보조정리 CRUD*만 둔다.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from whymath_backend.db.models.verified_lemma import VerifiedLemma

__all__ = [
    "find_lemma",
    "get_lemmas",
    "log_lemma",
]


async def log_lemma(
    session: AsyncSession,
    *,
    problem_id: uuid.UUID,
    lemma_key: str,
    lemma_repr: dict[str, Any],
    statement: str | None = None,
    source_node_id: uuid.UUID | None = None,
) -> None:
    """검증된 보조정리 `(problem_id, lemma_key)`를 *멱등* 적재한다(§2.2 — verify 통과 후 호출).

    같은 보조정리를 두 가지가 독립 발견해도 한 행이다 — `ON CONFLICT (problem_id, lemma_key) DO
    NOTHING`(복합 UNIQUE). 즉 중복 적재해도 안전(예외·중복 행 없음). 이미 있던 행의 `lemma_repr`·
    `statement`는 덮어쓰지 않는다(최초 적재 보존 — DO NOTHING). 트랜잭션 commit은 호출자 관리.
    """
    stmt = (
        pg_insert(VerifiedLemma)
        .values(
            problem_id=problem_id,
            lemma_key=lemma_key,
            lemma_repr=lemma_repr,
            statement=statement,
            source_node_id=source_node_id,
        )
        .on_conflict_do_nothing(constraint="uq_verified_lemmas_problem_key")
    )
    await session.execute(stmt)


async def find_lemma(
    session: AsyncSession,
    *,
    problem_id: uuid.UUID,
    lemma_key: str,
) -> VerifiedLemma | None:
    """`(problem_id, lemma_key)`에 해당하는 검증된 보조정리를 재사용 조회한다 — 없으면 None.

    탐색 정책이 보조 목표에 닿을 때 이 키로 *이미 검증된 결과가 있는지* 확인해 중복 탐색을 가지친다
    (§2.2 재사용). 복합 UNIQUE 인덱스를 정확 매칭으로 탄다(유일하므로 단건).
    """
    stmt = select(VerifiedLemma).where(
        VerifiedLemma.problem_id == problem_id,
        VerifiedLemma.lemma_key == lemma_key,
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_lemmas(session: AsyncSession, problem_id: uuid.UUID) -> list[VerifiedLemma]:
    """주어진 문제의 검증된 보조정리 전체를 적재순으로 조회(검사·재사용 일괄 로드).

    복합 UNIQUE 인덱스의 선행 컬럼(`problem_id`)을 prefix로 탄다. `created_at`·`id` 정렬로 결정적
    순서를 보장한다.
    """
    stmt = (
        select(VerifiedLemma)
        .where(VerifiedLemma.problem_id == problem_id)
        .order_by(VerifiedLemma.created_at, VerifiedLemma.id)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())
