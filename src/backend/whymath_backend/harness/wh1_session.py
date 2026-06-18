"""WH-1 영속 턴 — 순수 루프 골격(`wh1_loop`)을 실제 스토어에 결선하는 *가동* 좌석.

설계 정본: `docs/architecture/04a_wh1_tutoring_harness.md` §2.1·§2.2·§2.4. `run_tutoring_turn`(순수·
in-memory 작업 메모리)을 **웜 스타트(로드) → 실행 → 영속(커밋)** 으로 감싸 한 턴을 *실가동*한다.
순수 골격은 재구현 0으로 *재사용만* 하고, 본 모듈은 그 in-memory 작업 메모리(가설 세트·증거 원장)를
PostgreSQL 스토어에 연결한다(§2.2 "가설 세트 = Redis + PostgreSQL 스냅샷"·§2.3 evidence_links).

절차(한 턴):
  1. **웜 스타트**(§2.2·§4): `get_active_hypotheses`로 *직전 턴 스냅샷*(활성 가설 세트)을 복원한다.
     누적 감쇠·강화·반박이 baked-in된 세트라, 루프는 "백지 진단"이 아닌 "초안 검증·보완"으로 시작.
  2. **순수 턴 실행**: `run_tutoring_turn`(도구 8종 디스패치+불변식·작업 메모리 in-memory).
  3. **영속(커밋 좌석)**: 이 턴 증거 엣지 → `evidence_store.log_evidence`(카탈로그·극성 게이트
     재통과)·최종 활성 가설 세트 → `hypothesis_store.persist_hypotheses`(upsert + 탈락 비활성화).
     둘 다 *같은 트랜잭션*(호출자 session)에 합류하고 **commit은 호출자**(flush만·저장소 패턴 일관).
     즉 발화·증거·가설이 원자적으로 영속된다.

정합(이중 적용 방지): 루프 curate가 *이미* 이 턴 증거로 반박을 반영해 `outcome.hypotheses`를
냈으므로, 본 모듈은 그 *결과 세트*를 그대로 커밋한다(DB 재-curate 없음 — 증거는 감사·다음 턴
net_support용 별도 적재). 웜 스타트가 직전 누적 세트를 싣고 이 턴 델타만 반영하므로 역사 반박은
로드된 세트에 이미 녹아 있다(중복·누락 0).

저장소 패턴(`hypothesis_store`·`evidence_store` 선례): `AsyncSession` 주입·**commit은 호출자**·순수
ORM/쿼리빌더만. 범위 밖(후속): Redis 작업 메모리 스냅샷(§2.1)·BKT 커밋 큐(§2.4)·`/v1/coach/sessions`
멀티턴 엔드포인트 결선·LLM 정책 모델·fast path(§5.3).
"""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from whymath_backend.harness.wh1_loop import TurnOutcome, TutorPolicy, run_tutoring_turn
from whymath_backend.l4.misconception.evidence_store import log_evidence
from whymath_backend.l4.misconception.hypothesis_store import (
    get_active_hypotheses,
    persist_hypotheses,
)
from whymath_backend.l4.misconception.probe_selection import _EXPLORE_PERIOD

__all__ = ["run_persisted_turn"]


async def run_persisted_turn(
    session: AsyncSession,
    *,
    student_id: uuid.UUID,
    session_id: uuid.UUID,
    policy: TutorPolicy,
    turn_index: int = 1,
    has_solution_steps: bool = False,
    max_tool_calls: int = 16,
    explore_period: int = _EXPLORE_PERIOD,
) -> TurnOutcome:
    """WH-1 한 턴을 *실가동*한다 — 웜 스타트(로드) → 순수 루프 실행 → 영속(증거+가설 커밋).

    `run_tutoring_turn`(순수 골격)을 재사용만 하고(재구현 0), 그 in-memory 작업 메모리를 스토어에
    결선한다. 트랜잭션 commit은 호출자 관리(저장소 패턴) — 본 함수는 `log_evidence`/
    `persist_hypotheses`의 flush까지만 한다(발화·증거·가설 영속이 호출자 한 트랜잭션에서 원자적).

    `turn_index`(세션 누적·1-기반)는 ε-탐색 주기(§2.2)에·`has_solution_steps`는 verify 의무
    (§3.1)에 쓰인다. 반환은 순수 `TurnOutcome`(학생 발화·갱신된 가설 세트·증거 엣지·트레이스)이다.
    """
    # 1. 웜 스타트 — DB 스냅샷에서 활성 가설 세트 복원(§2.2·§4).
    initial = await get_active_hypotheses(session, student_id)

    # 2. 순수 턴 루프 실행(작업 메모리 in-memory·재구현 0).
    outcome = await run_tutoring_turn(
        policy=policy,
        turn_index=turn_index,
        has_solution_steps=has_solution_steps,
        initial_hypotheses=initial,
        max_tool_calls=max_tool_calls,
        explore_period=explore_period,
    )

    # 3. 영속 — 이 턴 증거 엣지 → evidence_links(게이트 재통과·감사·다음 턴 net_support).
    for edge in outcome.evidence:
        await log_evidence(
            session,
            session_id=session_id,
            student_id=student_id,
            misconception_id=edge.misconception_id,
            polarity=edge.polarity,
            weight=edge.weight,
        )

    # 4. 최종 활성 가설 세트 → misconception_hypothesis(upsert + 탈락 비활성화·결과 세트 그대로).
    await persist_hypotheses(session, student_id, outcome.hypotheses)

    return outcome
