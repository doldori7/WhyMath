"""활성 오개념 가설 per-student 비동기 저장소 — `misconception_hypothesis` 영속 (§8.4 2단계).

설계 정본: `docs/architecture/04a_wh1_tutoring_harness.md` §8.4 2단계·§2.2·§3 도구4
(`curate_hypothesis`). 직전 슬라이스(#191)가 만든 *순수 결정 로직*(`l4/misconception/
hypothesis.py` — `MisconceptionHypothesis`·`decay`·`reinforce`·`update_hypotheses`·`curate`·
`select_focus`)을 per-student로 *영속*하는 seam이다. 본 모듈은 순수 로직을 **재사용**만 하고
(재구현 0), ORM 레코드(`MisconceptionHypothesisRecord`) ↔ 순수 Pydantic
(`MisconceptionHypothesis`)을 변환하며 활성 가설 세트를 로드·갱신·영속한다.

함수 2종(공유 영속 헬퍼 `_persist_active_set` 위에 구축):
  · `apply_matches` — 매치(증거 신호)만 반영하는 하위 좌석(감쇠·강화·임계 가지치기·영속).
  · `curate_hypothesis`(§3 도구4) — 그 위에 **`evidence_links` 순지지도(`net_support`)로 반박된
    가설 archived** + **최대 5개 캡**(§2.2 큐레이션 규칙)을 더한 하네스 도구. 반박 판정이
    LLM 추론이 아닌 증거 그래프 SQL 집계에서 나온다(확증편향 방지·신뢰 근거).

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

범위 밖(후속 — 정직 스코프): `log_evidence` *적재* 자체는 증거 저장소(`evidence_store`) 몫이고
본 모듈은 그 집계(`net_support`)를 *소비*만 한다. coach/intervention 결선(`curate_hypothesis`→
개입 발화·학생 세션 경로)·`select_probe`(ε-탐색 문항)·API 엔드포인트 노출·진단-실제 *일치율*
게이트는 모두 후속 슬라이스다.

오개념 crosswalk shadow(게이트 공존 배선·math_dsl_risk_register.md Q10-⑥): `_persist_active_set`은
kebab-id `misconception_id`를 *런타임 키로 영속*하는 게이트라, `evidence_store.log_evidence`와
동일하게 `misconception_crosslink_mode == "shadow"`에서 영속 kebab-id의 canonical M-id 매핑
coverage를 *비노출·비차단*으로 관측한다(노출·DB 저장은 kebab-id 그대로 불변).
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from whymath_backend.config import get_settings
from whymath_backend.db.models.misconception_hypothesis import (
    MisconceptionHypothesisRecord,
)
from whymath_backend.l4.misconception.crosslink_shadow import observe_crosslink_shadow_async
from whymath_backend.l4.misconception.evidence_store import get_evidence_for_student, net_support
from whymath_backend.l4.misconception.hypothesis import (
    MisconceptionHypothesis,
    curate,
    update_hypotheses,
)
from whymath_backend.l4.misconception.models import MisconceptionMatch

__all__ = [
    "MisconceptionRecurrenceSignal",
    "apply_matches",
    "curate_hypothesis",
    "get_active_hypotheses",
    "get_recurrence_signals",
    "order_mids_by_recurrence",
    "persist_hypotheses",
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

    # 3. 영속(upsert + 빠진 활성 행 비활성화) — curate_hypothesis와 공유하는 헬퍼(중복 0).
    await _persist_active_set(session, user_id, updated)

    # 4. 이번 턴 활성 세트(순수) 반환.
    return updated


async def persist_hypotheses(
    session: AsyncSession,
    user_id: uuid.UUID,
    hypotheses: Sequence[MisconceptionHypothesis],
) -> None:
    """활성 가설 세트를 그대로 영속한다(upsert + 빠진 활성 행 비활성화) — 공개 커밋 진입점.

    WH-1 턴 루프(`harness/wh1_loop.py`)가 *in-memory로 갱신한* 최종 가설 세트를 턴 종료 시 영속할
    때 쓰는 좌석이다(매치 재계산 없이 *결과 세트*만 커밋). 내부 영속 로직(`_persist_active_set`)에
    위임한다(중복 0). 트랜잭션 commit은 호출자 관리(flush로 같은 트랜잭션 가시화).
    """
    await _persist_active_set(session, user_id, hypotheses)


async def _persist_active_set(
    session: AsyncSession,
    user_id: uuid.UUID,
    active: Sequence[MisconceptionHypothesis],
) -> None:
    """이번 턴 *활성 가설 세트*를 영속한다 — upsert + 빠진 활성 행 비활성화(공통 영속 절차).

    `apply_matches`(매치만 반영)·`curate_hypothesis`(증거·캡까지 반영)가 *공유*하는 영속 로직이다
    (재구현 0). 기존 행을 `(user_id, misconception_id)`로 인덱싱하고(활성·비활성 모두 조회):
      · `active`에 든 가설은 갱신(가지치기/반박됐다 다시 살아난 가설도 `is_active=true`로 재활성화),
        없으면 새 행 insert.
      · `active`에서 *빠진* 기존 *활성* 행(= 가지치기·반박·최대 N 캡 탈락)은 `is_active=false`로
        비활성화한다(행 삭제 X — 증거 이력 보존·낙인 방지·§5.1 archived 보존).
    server_default(id·타임스탬프)·갱신을 같은 트랜잭션에서 가시화하도록 `flush`(commit은 호출자).
    """
    existing_stmt = select(MisconceptionHypothesisRecord).where(
        MisconceptionHypothesisRecord.user_id == user_id
    )
    existing_result = await session.execute(existing_stmt)
    by_mid: dict[str, MisconceptionHypothesisRecord] = {
        row.misconception_id: row for row in existing_result.scalars().all()
    }

    active_mids: set[str] = set()
    for hyp in active:
        active_mids.add(hyp.misconception_id)
        record = by_mid.get(hyp.misconception_id)
        if record is not None:
            # upsert(갱신) — 가지치기/반박됐다 다시 살아난 가설도 is_active=true로 재활성화.
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

    # 활성 세트에서 빠진 *활성* 기존 행 = 가지치기·반박·캡 탈락 → 비활성화(삭제 X).
    pruned_mids = [
        mid for mid, record in by_mid.items() if record.is_active and mid not in active_mids
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

    # crosswalk shadow(비노출·비차단 측정·게이트 공존 배선) — 이 좌석은 kebab-id를 *런타임 키로
    # 영속*하는 또 하나의 게이트다(evidence_store와 평행). mode != "off"면 영속된 활성 가설 각각의
    # kebab-id가 canonical M-id로 어떻게 매핑되는지를 *로그로만* 관측한다(crosslink_shadow·
    # math_dsl_risk_register.md Q10-⑥·remediation §1.3 step3). 노출·위 DB 저장은 kebab-id 그대로
    # 불변이고, resolve 실패도 영속을 막지 않는다(never-break). 기본 off라 측정 윈도에서만 켠다.
    if get_settings().misconception_crosslink_mode != "off":
        for hyp in active:
            await observe_crosslink_shadow_async(hyp.misconception_id)


async def curate_hypothesis(
    session: AsyncSession,
    *,
    student_id: uuid.UUID,
    matches: Sequence[MisconceptionMatch],
    turns_elapsed: int = 1,
    max_active: int = 5,
) -> list[MisconceptionHypothesis]:
    """증거 그래프를 반영해 학생 활성 가설 세트를 *큐레이션*·영속한다(§3 도구4·§2.2).

    `apply_matches`(매치만 반영)에서 한 걸음 더 — **`evidence_links` 순지지도(`net_support`)로
    반박된 가설을 archived**하고 **최대 N개로 캡**한다(설계 §2.2 큐레이션 규칙·§5.1):
      1. `get_active_hypotheses`로 현재 활성 가설(순수)을 로드한다.
      2. 이번 턴 후보 오개념(현재 활성 가설 ∪ 새 매치) 각각의 `evidence_store.net_support`를
         조회 — *음수*(반박 우세)면 `refuted` 집합에 넣는다. "이 가설은 틀렸다"가 LLM 추측이
         아니라 증거 그래프 SQL 집계에서 나온다(학부모 리포트 신뢰 근거·확증편향 방지).
      3. **#191 순수 `curate(current, matches, turns_elapsed, refuted, max_active)` 재사용** —
         감쇠→강화/신규→임계 가지치기→반박 제거→내림차순→최대 N 캡(재구현 0).
      4. `_persist_active_set`으로 영속(upsert + 탈락 비활성화) 후 활성 세트를 반환한다.

    트랜잭션 commit은 호출자 관리(`_persist_active_set`이 flush로 같은 트랜잭션 가시화). 순수
    ORM/쿼리빌더만(원시 SQL 0). 반박 판정이 *현재까지 누적된 증거*(prior `log_evidence`) 기준이라,
    반박된 가설은 증거 순지지도가 양으로 돌아서기 전엔 새 매치만으로 부활하지 않는다(R4 확증편향
    방지 — 매치는 confidence를 강화하지만 archived 여부는 증거 원장이 결정).
    """
    # 1. 현재 활성 가설(순수) 로드.
    current = await get_active_hypotheses(session, student_id)

    # 2. 후보 오개념(현재 가설 ∪ 새 매치)별 증거 순지지도 → 음수면 반박(archived 신호·§5.1).
    candidate_mids: set[str] = {h.misconception_id for h in current}
    candidate_mids.update(m.misconception.id for m in matches)
    refuted: set[str] = set()
    for mid in candidate_mids:
        if await net_support(session, student_id, mid) < 0.0:
            refuted.add(mid)

    # 3. #191 순수 큐레이션 재사용(감쇠·강화·가지치기·반박 제거·최대 N 캡) — 재구현 0.
    active = curate(
        current,
        matches,
        turns_elapsed=turns_elapsed,
        refuted=frozenset(refuted),
        max_active=max_active,
    )

    # 4. 영속(upsert + 탈락 비활성화) 후 활성 세트 반환.
    await _persist_active_set(session, student_id, active)
    return active


# ===========================================================================
# 재발신호 (MISC-06 — 04e §4 "오개념 예측"의 WhyMath 정합 축소: 읽기 전용·probe 우선순위 전용)
# ===========================================================================


class MisconceptionRecurrenceSignal(BaseModel):
    """(학생, *비활성* 오개념) 1쌍의 재발신호 — 과거 지지 이력 요약(읽기 전용·관측). 불변(frozen).

    04e §4의 좁힌 "예측" 정의("같은 오개념의 재발 가능성"만)의 코드 표현이다. 소비는
    `order_mids_by_recurrence`(outside_mids 재정렬 → `resolve_probe_target`의 ε-탐색 표적 우선순위)
    **한 경로뿐**이다 — 학생 노출 라벨·코칭 강도 결정·intervene 경로엔 결코 흐르지 않는다(낙인
    방지·acceptance ①②). BKT/DKT θ와는 어떤 수식으로도 융합하지 않는다(원칙6 — θ를 읽지도 않음).

    `had_hypothesis_row`의 정직 한계: 스냅샷 행이 있으면(`is_active=False`) "한때 가설로 형성됐다
    가라앉았다"는 뜻이지만, 그 사유가 *감쇠 소멸*인지 *증거 반박(archived)*인지는 스냅샷에서
    구별 불가하다(둘 다 같은 `is_active=False` upsert — `misconception_slip_report.py` 데이터 소스
    절과 동일 실측). 행이 없으면 증거만 있고 가설은 형성·큐레이션되지 않았던 이력이다.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    misconception_id: str = Field(description="재발 후보 오개념 id(현재 활성 세트 *밖*).")
    prior_support_count: int = Field(
        ge=1,
        description="evidence_links의 지지(polarity=+1) 레코드 수 — ≥1이면 과거 의심 이력.",
    )
    last_support_at: datetime = Field(
        description="가장 최근 지지(+1) 증거의 created_at — 재발 최근성(동률 tiebreak)."
    )
    had_hypothesis_row: bool = Field(
        description="misconception_hypothesis 스냅샷 행 존재 여부(있으면 is_active=False — "
        "감쇠 소멸 vs 반박 archived는 구별 불가·정직 한계)."
    )


async def get_recurrence_signals(
    session: AsyncSession, user_id: uuid.UUID
) -> dict[str, MisconceptionRecurrenceSignal]:
    """학생 1명의 오개념 재발신호를 *읽기 전용*으로 산출한다(04e §4·MISC-06 — 쓰기 0).

    **문서 정정 발견(04e §4 — 기록만·문서 직접 수정은 범위 밖)**: 04e §4는 `misconception_
    hypothesis`를 "이미 존재하는 시계열"이라 부르지만 실측(MISC-05·`misconception_slip_report.py`
    데이터 소스 절)으론 **스냅샷 테이블**이다 — `(user_id, misconception_id)` UNIQUE·매 턴
    confidence/evidence_count 덮어씀·`is_active`만 상태로 남고, 가지치기→부활 재활성화도 같은 행
    in-place upsert라 스냅샷 단독으론 재발을 감지할 수 없다(`test_pruned_hypothesis_reactivates_
    on_new_evidence_on_live_pg`가 "행 1개 upsert"를 동결). 강화/감쇠 *추세*는 append-only
    `evidence_links`(polarity ±1·weight·created_at)에서만 재구성된다. 그래서 본 함수는 문서 표현과
    달리 **스냅샷(활성 제외·행 존재) × evidence_links(지지 이력) 교차**로 재발신호를 만든다
    (MISC-05 `_JUDGE_DOCSTRING_STALE_NOTE` 관례의 docstring 기록).

    조작적 정의 — (user_id, mid)별로, **현재 활성 집합에 없는** mid에 대해:
      · `prior_support_count` = 지지(polarity=+1) 레코드 수(≥1 = "의심됐다 가라앉은" 이력).
        반박(−1)은 재발 이력이 아니므로 카운트에 섞지 않는다.
      · `last_support_at` = 지지 레코드의 최신 `created_at`(재발 최근성).
      · 감쇠 재시뮬레이션은 하지 않는다 — `created_at`은 벽시계이고 감쇠(`_HALF_LIFE_TURNS`)는
        *턴 인덱스*라 "prune된 시점" 역산 근사가 성립하지 않는다(MISC-05 동일 판단 — 있는
        신호(지지 횟수·최근성)만 쓴다).

    쿼리 2회 고정(N+1 없음): ①스냅샷 최소 투영(mid·is_active — 활성 제외 + 행 존재), ②학생 1명분
    증거 전량(`get_evidence_for_student` 재사용) 후 파이썬 mid별 집계. **reactive retrieval**(원칙6)
    — probe 타깃팅 시점에만 호출되며 초기 context에 preload하지 않는다(호출자 계약).
    """
    # ① 스냅샷 최소 투영(활성·비활성 모두) — 활성 집합은 재발 후보가 아니고(지금 의심 중),
    #    비활성 행 존재는 "한때 가설이었다"의 표식이다(사유 구별 불가 — 모델 docstring).
    snapshot_stmt = select(
        MisconceptionHypothesisRecord.misconception_id,
        MisconceptionHypothesisRecord.is_active,
    ).where(MisconceptionHypothesisRecord.user_id == user_id)
    snapshot_rows = (await session.execute(snapshot_stmt)).all()
    active_mids = {mid for mid, is_active in snapshot_rows if is_active}
    snapshot_mids = {mid for mid, _is_active in snapshot_rows}

    # ② 학생 1명분 증거 전량 단일 쿼리(재사용) → 파이썬 mid별 집계(지지만·반박 −1 제외).
    links = await get_evidence_for_student(session, user_id)
    support_count: dict[str, int] = {}
    last_support: dict[str, datetime] = {}
    for link in links:
        if link.polarity != 1:
            continue  # 반박(−1)은 재발 이력이 아니다 — 카운트·최근성 어느 쪽에도 안 섞는다.
        mid = link.misconception_id
        support_count[mid] = support_count.get(mid, 0) + 1
        prev = last_support.get(mid)
        if prev is None or link.created_at > prev:
            last_support[mid] = link.created_at

    # ③ 활성 집합 제외 — 재발신호는 "지금은 비활성인데 과거 지지 이력이 있는" mid만 담는다.
    return {
        mid: MisconceptionRecurrenceSignal(
            misconception_id=mid,
            prior_support_count=count,
            last_support_at=last_support[mid],
            had_hypothesis_row=mid in snapshot_mids,
        )
        for mid, count in support_count.items()
        if mid not in active_mids
    }


def order_mids_by_recurrence(
    mids: Sequence[str],
    signals: Mapping[str, MisconceptionRecurrenceSignal],
) -> list[str]:
    """outside_mids를 재발신호 강도순으로 재정렬한다(순수·결정론·입력 비변형 — MISC-06 유일 소비).

    정렬 키: 신호 있는 mid 먼저 → `prior_support_count` 내림차순 → `last_support_at` 최신순 →
    동률·신호 없음은 **원래 순서 보존**(파이썬 안정 정렬 — 신호가 전무하면 입력과 완전 동일,
    하위호환). `signals`에만 있고 `mids`에 없는 id는 결코 *추가되지 않는다* — 재발신호는 탐색
    표적 풀의 **우선순위 신호일 뿐 신규 공급원이 아니다**(04e §5 "REC-02 확장하지 않는다" 정합·
    후보 조립은 warmstart 2원천 그대로).

    소비처는 `assemble_warmstart_probe_hints`(→ `resolve_probe_target`이 ε-탐색 턴에
    `outside_mids[0]` 소비) 한 경로뿐이다 — 활성 가설(`active_hypotheses`) 순서·내용, 개입
    (`select_intervention_from_hypotheses`)·코칭 경로엔 어떤 영향도 없다(acceptance ①·낙인 방지).
    """

    def _key(mid: str) -> tuple[int, int, float]:
        sig = signals.get(mid)
        if sig is None:
            return (1, 0, 0.0)  # 신호 없음 → 뒤·동률(안정 정렬이 원래 순서 보존)
        # 최신순은 epoch 초의 음수로 표현(datetime은 부호 반전 불가) — 동률은 안정 정렬이 원순서.
        return (0, -sig.prior_support_count, -sig.last_support_at.timestamp())

    return sorted(mids, key=_key)
