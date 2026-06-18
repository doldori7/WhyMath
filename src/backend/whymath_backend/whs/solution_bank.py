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

중복 dedup: `bank_solution(dedup=True)` + `solution_fingerprint`로 *정확 일치* 경로 재적재를
막는다(솔버 루프 데이터 위생). 솔버 `finalize`(`whs/harness.py`)가 이 옵션으로 호출해 재발견을
멱등 처리한다(#256 결선). 범위 밖(후속): 자기진화 export(§5)·WH-1 콘텐츠 변환(§7)·*본질적 동치*
dedup(표기 다른 동치 풀이 정규화). 본 모듈은 *검증 풀이 저장소 CRUD*만 둔다.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import AsyncIterator
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from whymath_backend.db.models.verified_solution import (
    VerifiedSolution,
    WhsSolutionGrade,
)

__all__ = [
    "bank_solution",
    "get_all_verified",
    "get_solutions",
    "get_verified",
    "solution_fingerprint",
    "stream_all_verified",
]


def solution_fingerprint(solution_path: dict[str, Any]) -> str:
    """풀이 경로의 *정규 지문* — 정렬 키 JSON의 sha256(바이트 동일 경로 식별·dedup용).

    키 순서·공백 무관하게 *내용이 같으면 같은 지문*(`sort_keys`·compact separators). 순수·결정론.
    **정확 일치만** 잡는다 — 표기는 달라도 수학적으로 동치인 풀이(다중 풀이 본질적 동치)는 못
    가린다(정규화·동치 판정은 후속). 솔버 루프가 *같은 경로를 재발견*해 저장소를 부풀리는 것을 막는
    1차 dedup 신호다.
    """
    canonical = json.dumps(solution_path, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


async def bank_solution(
    session: AsyncSession,
    *,
    problem_id: uuid.UUID,
    grade: WhsSolutionGrade,
    solution_path: dict[str, Any],
    strategy_tag: str | None = None,
    answer: str | None = None,
    source_root_id: uuid.UUID | None = None,
    dedup: bool = False,
) -> VerifiedSolution:
    """완전 풀이 경로 1개를 저장소에 적재한다(§2.4 — finalize 커밋 대상).

    `grade`는 `verified`(학습 채택 가능) 또는 `unverified`(격리·학습 배제)만 가능하다 —
    `WhsSolutionGrade` enum이 failed를 배제해 *틀린 풀이의 적재를 구조 차단*한다(§3·R-S2). 한 문제에
    여러 풀이(다중 전략)를 적재할 수 있다(problem_id UNIQUE 없음). `flush`+`refresh`로 새 행의
    `id`·`created_at`을 같은 트랜잭션에서 가시화(commit은 호출자).

    **dedup(opt-in)**: `dedup=True`면 적재 전 같은 문제의 *같은 grade* 풀이 중 `solution_path`가
    바이트 동일(같은 지문·`solution_fingerprint`)인 것이 있으면 *새로 적재하지 않고 기존 행을
    반환*한다(idempotent) — 솔버 루프가 같은 경로를 재발견해 자기진화 저장소를 부풀리는 것을
    막는다(데이터 위생·R-S2 인접). 정확 일치만 dedup(다중 풀이 *본질적 동치*는 후속). 기본 False는
    종전대로 항상 적재(다중 전략·하위호환).
    """
    if dedup:
        fingerprint = solution_fingerprint(solution_path)
        for existing in await get_solutions(session, problem_id):
            if (
                existing.grade == grade
                and solution_fingerprint(existing.solution_path) == fingerprint
            ):
                return existing  # 같은 grade·동일 경로 이미 적재 — 중복 적재 skip(idempotent).
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


async def get_all_verified(session: AsyncSession) -> list[VerifiedSolution]:
    """**전 문제**의 verified 풀이를 결정적 순서로 조회한다 — 자기 진화 SFT export 원천(§5).

    `get_verified`(문제 1개)의 *전역* 버전 — 라운드별 SFT 데이터셋(§5)을 뽑을 때 솔버가 지금까지
    적재한 검증 풀이 전부를 한데 모은다. `unverified`는 *절대 포함하지 않는다*(R-S2 안전·학습 누수
    0). `(problem_id, created_at, id)` 정렬로 결정적(재현 가능한 export). 대규모 시 스트리밍은 후속.
    """
    stmt = (
        select(VerifiedSolution)
        .where(VerifiedSolution.grade == WhsSolutionGrade.VERIFIED)
        .order_by(
            VerifiedSolution.problem_id,
            VerifiedSolution.created_at,
            VerifiedSolution.id,
        )
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def stream_all_verified(session: AsyncSession) -> AsyncIterator[VerifiedSolution]:
    """`get_all_verified`의 **스트리밍판** — 전 문제 verified를 1건씩 yield(§5·대규모 가드).

    `get_all_verified`와 *완전히 같은 WHERE/ORDER BY*(grade==verified·`(problem_id,
    created_at, id)` 결정적 순서·R-S2 안전·verified만)지만, 결과 전부를 `list`로 메모리에
    적재하는 대신 `stream_scalars`(서버측 커서)로 행을 *한 건씩* 흘린다. 자기 진화 export(§5)가
    수만~수십만 검증 풀이를 JSONL로 쏟을 때 메모리를 행 1건 + 소비자 dedup 키셋으로만
    바운드한다(전량 적재 회피).

    소비자(`self_evolution.stream_sft_jsonl`)가 `async for`로 받아 verified 필터·dedup·직렬화를
    스트리밍한다. 세션은 스트림이 소진될 때까지 살아 있어야 한다(호출자가 `async with`로 유지).
    읽기 전용이라 commit 없음(저장소 패턴).
    """
    stmt = (
        select(VerifiedSolution)
        .where(VerifiedSolution.grade == WhsSolutionGrade.VERIFIED)
        .order_by(
            VerifiedSolution.problem_id,
            VerifiedSolution.created_at,
            VerifiedSolution.id,
        )
    )
    result = await session.stream_scalars(stmt)
    async for solution in result:
        yield solution
