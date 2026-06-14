"""활성 오개념 가설 per-student 비동기 저장소 — `misconception_hypothesis` 영속 (§8.4 2단계).

설계 정본: `docs/architecture/04a_wh1_tutoring_harness.md` §8.4 2단계. 직전 슬라이스(#191)가
만든 *순수 결정 로직*(`l4/misconception/hypothesis.py` — `MisconceptionHypothesis`·`decay`·
`reinforce`·`update_hypotheses`·`select_focus`)을 per-student로 *영속*하는 seam이다. 본 모듈은
순수 로직을 **재사용**만 하고(재구현 0), ORM 레코드(`MisconceptionHypothesisRecord`) ↔ 순수
Pydantic(`MisconceptionHypothesis`)을 변환하며 활성 가설 세트를 로드·갱신·영속한다.

저장소 패턴(`l2/mastery_tracking.py`·`whs/node_store.py` 선례 답습):
  - 모든 함수는 `AsyncSession`을 *주입받는다*(엔진·세션 생성은 호출자 책임).
  - **트랜잭션(commit/rollback)은 호출자 관리** — 여기서 자동 commit하지 않는다. 새 행/갱신이
    같은 트랜잭션에서 가시화돼야 하는 경우만 `flush`한다(commit은 호출자).
  - **순수 ORM/쿼리빌더만 사용**(원시 SQL 0 — CLAUDE.md "ORM/쿼리 빌더").

개인정보(CLAUDE.md 절대 금기): 활성 오개념 가설은 *미성년 학생*에 결부된 **민감 데이터**다
(per-student 진단 후보). 오개념은 *후보일 뿐* 확정 라벨이 아니며(낙인 금지) 가지치기는
`is_active=false` 비활성화로 표현한다. 평문 저장·동의 없는 학습 사용 금지는 *저장·동의
계층*(암호화·미들웨어·PIPA 권한 매트릭스) 책임이다(ORM·저장소엔 가짜 CHECK·동의 게이트를
두지 않는다 — activity.py 패턴 동형).

범위 밖(후속 — 정직 스코프): `evidence_links`(증거→가설 연결·학생 풀이 증거·암호화·동의·
PIPA 권한 매트릭스)·coach/intervention 결선(가설→개입 발화·학생 세션 경로)·API 엔드포인트
노출(이 저장소는 WH-1 코어 내부 전용)·진단-실제 *일치율* 게이트는 모두 후속 슬라이스다.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from whymath_backend.db.models.misconception_hypothesis import (
    MisconceptionHypothesisRecord,
)
from whymath_backend.l4.misconception.hypothesis import (
    MisconceptionHypothesis,
    update_hypotheses,
)
from whymath_backend.l4.misconception.models import MisconceptionMatch

__all__ = [
    "apply_matches",
    "get_active_hypotheses",
]


def _to_pydantic(record: MisconceptionHypothesisRecord) -> MisconceptionHypothesis:
    """영속 Record → 순수 Pydantic 가설(Numeric→float 변환).

    `confidence`는 PG Numeric이라 DB 왕복 시 `Decimal`로 올 수 있어 `float`로 캐스팅한다
    (순수 모델은 float·[0,1] 검증). 그 외 필드는 동명 1:1 사본.
    """
    return MisconceptionHypothesis(
        misconception_id=record.misconception_id,
        confidence=float(record.confidence),
        turns_since_evidence=record.turns_since_evidence,
        evidence_count=record.evidence_count,
    )


async def get_active_hypotheses(
    session: AsyncSession, user_id: uuid.UUID
) -> list[MisconceptionHypothesis]:
    """학생의 *활성*(`is_active=true`) 오개념 가설을 confidence 내림차순으로 로드한다(순수 변환).

    `update_hypotheses`/`select_focus`가 가정하는 *내림차순 정렬*을 DB에서 보장한다(동률은
    misconception_id로 안정 tiebreak). 비활성(가지치기된) 행은 제외한다 — 활성 세트만 반환.
    읽기 전용이라 flush/commit 없음(commit은 호출자 관리·없어도 무방).
    """
    stmt = (
        select(MisconceptionHypothesisRecord)
        .where(
            MisconceptionHypothesisRecord.user_id == user_id,
            MisconceptionHypothesisRecord.is_active.is_(True),
        )
        .order_by(
            MisconceptionHypothesisRecord.confidence.desc(),
            MisconceptionHypothesisRecord.misconception_id,
        )
    )
    result = await session.execute(stmt)
    return [_to_pydantic(r) for r in result.scalars().all()]


async def apply_matches(
    session: AsyncSession,
    user_id: uuid.UUID,
    matches: Sequence[MisconceptionMatch],
    *,
    turns_elapsed: int = 1,
) -> list[MisconceptionHypothesis]:
    """학생 가설 세트를 1턴 갱신·영속한다 — #191 순수 로직 재사용 + upsert + 가지치기 비활성화.

    절차:
      1. `get_active_hypotheses`로 현재 활성 가설(순수)을 로드한다.
      2. **#191 `update_hypotheses(current, matches, turns_elapsed)` 재사용**(감쇠→강화/신규→
         가지치기→정렬 — 순수 로직 재구현 0). 결과가 *이번 턴의 활성 세트*다.
      3. 결과를 영속한다 — `(user_id, misconception_id)` 단위로:
           · 기존 행이 있으면 confidence·turns_since_evidence·evidence_count·is_active=true로
             갱신(가지치기됐다 다시 살아난 가설도 재활성화).
           · 없으면 새 행 insert.
         결과 세트에서 *빠진* 기존 활성 행(= 감쇠로 가지치기된 가설)은 `is_active=false`로
         비활성화한다(행 삭제 X — 증거 이력 보존·낙인 방지).
      4. 갱신된 활성 가설(= update_hypotheses 결과)을 반환한다.

    트랜잭션 commit은 호출자 관리(flush로 같은 트랜잭션 내 가시화). 순수 ORM/쿼리빌더만(원시
    SQL 0). 매치는 *증거*일 뿐 진단 알고리즘이 아니다(#191 불변·재구현 0).
    """
    # 1. 현재 활성 가설(순수) 로드.
    current = await get_active_hypotheses(session, user_id)

    # 2. #191 순수 로직 재사용 — 이번 턴 활성 세트 계산(재구현 0).
    updated = update_hypotheses(current, matches, turns_elapsed=turns_elapsed)

    # 3. 영속 — 기존 행을 (user_id, misconception_id)로 인덱싱(활성·비활성 모두 조회해 재활성
    #    가능하게 하고, 결과에서 빠진 *활성* 행만 비활성화한다).
    existing_stmt = select(MisconceptionHypothesisRecord).where(
        MisconceptionHypothesisRecord.user_id == user_id
    )
    existing_result = await session.execute(existing_stmt)
    by_mid: dict[str, MisconceptionHypothesisRecord] = {
        row.misconception_id: row for row in existing_result.scalars().all()
    }

    updated_mids: set[str] = set()
    for hyp in updated:
        updated_mids.add(hyp.misconception_id)
        record = by_mid.get(hyp.misconception_id)
        if record is not None:
            # upsert(갱신) — 가지치기됐다 다시 살아난 가설도 is_active=true로 재활성화.
            record.confidence = hyp.confidence
            record.turns_since_evidence = hyp.turns_since_evidence
            record.evidence_count = hyp.evidence_count
            record.is_active = True
        else:
            # upsert(insert) — 신규 가설.
            session.add(
                MisconceptionHypothesisRecord(
                    user_id=user_id,
                    misconception_id=hyp.misconception_id,
                    confidence=hyp.confidence,
                    turns_since_evidence=hyp.turns_since_evidence,
                    evidence_count=hyp.evidence_count,
                    is_active=True,
                )
            )

    # 결과 세트에서 빠진 *활성* 기존 행 = 감쇠로 가지치기된 가설 → 비활성화(삭제 X).
    pruned_mids = [
        mid for mid, record in by_mid.items() if record.is_active and mid not in updated_mids
    ]
    if pruned_mids:
        prune_stmt = (
            update(MisconceptionHypothesisRecord)
            .where(
                MisconceptionHypothesisRecord.user_id == user_id,
                MisconceptionHypothesisRecord.misconception_id.in_(pruned_mids),
            )
            .values(is_active=False)
        )
        await session.execute(prune_stmt)

    # server_default(id·타임스탬프)·갱신을 같은 트랜잭션에서 가시화(commit은 호출자).
    await session.flush()

    # 4. 이번 턴 활성 세트(순수) 반환.
    return updated
