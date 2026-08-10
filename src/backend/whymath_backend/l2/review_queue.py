"""L2 학습자 모델 — BKT 망각(P_forget) 역산 기반 복습 우선순위 큐.

`bkt.py::apply_forgetting`(순수 함수, `P(L') = P(L0) + (P(L)-P(L0))·exp(-λ·경과일)`)를
`concept_diagnosis.py::mastery_stmt`와 동일한 `ConceptMasteryHistory` DISTINCT ON 조회에
적용해, "지금 조회하는 시점" 기준으로 감쇠된 숙달이 낮은(=복습이 급한) 개념부터 정렬한다.

**저장 컬럼을 의도적으로 두지 않는다.** `next_review_at` 같은 컬럼·마이그레이션은 만들지
않고, 매 호출마다 최신 `ConceptMasteryHistory` 스냅샷에서 순수 재계산한다(신선도 보장·
갱신 파이프라인 불요·마이그레이션 0). 관측 이력이 전혀 없는 개념은 `ConceptMasteryHistory`
SELECT 결과 집합에 애초에 없으므로(그 개념에 대한 행 자체가 없음) 별도 필터 없이 자동으로
복습 큐에서 제외된다 — "측정 안 됨"과 "복습 불필요"를 혼동하지 않는다.

전역 `bkt.DEFAULT_BKT_PARAMETERS`는 `p_forget=0`(하위 호환 무영향)이라 그대로 쓰면 이
모듈의 감쇠가 항상 no-op이 된다. 그래서 이 모듈 전용 `REVIEW_QUEUE_PARAMETERS`를
별도로 둔다(전역 기본 파라미터는 건드리지 않음 — 다른 소비처 회귀 방지).
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from whymath_backend.db.models.assessment import ConceptMasteryHistory
from whymath_backend.db.models.concept import Concept
from whymath_backend.l2.bkt import BktParameters, apply_forgetting

# 감쇠 모델 라벨 — `ReviewQueue.decay_model`이 그대로 노출(어떤 모델을 썼는지 정직 표기).
DECAY_MODEL_LABEL: Literal["bkt_p_forget"] = "bkt_p_forget"

# 문헌 전형값(개별 학생·개념 적합 전까지의 합리적 기본값 — `bkt.py`의 _DEFAULT_P_INIT 등과
# 동일한 관례). 망각률 λ=0.05/일은 반감기 약 2주(exp(-0.05·14) ≈ 0.497)에 해당해, 시험 대비
# 복습 주기(2~4주)의 문헌 상 전형 범위에 든다. 개인·개념별 EM 적합은 후속(적합 전까지는
# `ReviewQueue.calibrated=False`로 정직 표기).
_REVIEW_QUEUE_LAMBDA = 0.05

# 전역 DEFAULT_BKT_PARAMETERS(p_forget=0)는 건드리지 않는다 — 이 모듈 전용 파라미터.
REVIEW_QUEUE_PARAMETERS = BktParameters(p_forget=_REVIEW_QUEUE_LAMBDA)

# DB 조회 결과(concept_id, concept_code, concept_name, mastery, measured_at) 1행의 순수 형태
# — `_rank_items`가 DB 세션 없이도 hermetic하게 테스트되도록 plain tuple로 받는다.
_MasteryRow = tuple[uuid.UUID, str | None, str | None, float | None, datetime]
# `_rank_items` 내부 감쇠 계산 결과 1행(concept_id, code, name, raw_mastery, measured_at,
# days_since_practice, decayed_mastery) — 정렬 키 함수 시그니처를 짧게 유지하기 위한 별칭.
_DecayedRow = tuple[uuid.UUID, str | None, str | None, float, datetime, float, float]


class ReviewQueueItem(BaseModel):
    """복습 우선순위 큐 항목 1건 — 개념 하나의 감쇠 반영 숙달과 순위."""

    concept_id: uuid.UUID = Field(description="개념 id.")
    concept_code: str | None = Field(default=None, description="개념 코드(orphan이면 null).")
    concept_name: str | None = Field(default=None, description="개념명(orphan이면 null).")
    raw_mastery: float = Field(description="측정값 그대로(BKT 최신 숙달 P(L), 감쇠 미적용).")
    decayed_mastery: float = Field(
        description="조회시점 망각 감쇠 적용 후 숙달(`apply_forgetting` 결과)."
    )
    measured_at: datetime = Field(description="`raw_mastery`가 측정된 시각.")
    days_since_practice: float = Field(
        description="측정 이후 경과일 — 반올림 없음, 시계 역행은 0.0으로 클램프."
    )
    due_rank: int = Field(
        description="복습 우선순위(1부터) — decayed_mastery 오름차순, 동률은 concept_code 순."
    )


class ReviewQueue(BaseModel):
    """학생 1인의 복습 우선순위 큐 — `decayed_mastery` 오름차순(복습이 급한 순)."""

    items: list[ReviewQueueItem] = Field(default_factory=list, description="우선순위순 항목.")
    decay_model: Literal["bkt_p_forget"] = Field(
        default=DECAY_MODEL_LABEL, description="감쇠 모델 식별자."
    )
    calibrated: bool = Field(
        default=False,
        description=(
            "λ가 개인·개념별 적합값이 아니라 문헌 전형값임을 나타내는 정직 표기 "
            "(EM 적합이 붙기 전까지 항상 False)."
        ),
    )


def _rank_items(
    rows: Sequence[_MasteryRow],
    as_of: datetime,
    params: BktParameters = REVIEW_QUEUE_PARAMETERS,
) -> list[ReviewQueueItem]:
    """순수 정렬·감쇠 로직(DB 세션 불요) — hermetic 단위테스트의 직접 대상.

    `mastery`가 None인 행(측정값 없는 스냅샷 — 방어적 처리, `concept_mastery_history.mastery`는
    nullable)은 감쇠 대상 자체가 없으므로 제외한다. 정렬은 `decayed_mastery` 오름차순(낮을수록
    급함)이며, 동률은 `concept_code` 오름차순(None은 맨 뒤)으로 결정론적으로 tie-break한다.
    """
    decayed_rows: list[_DecayedRow] = []
    for concept_id, code, name, mastery, measured_at in rows:
        if mastery is None:
            continue
        raw = float(mastery)
        days = max((as_of - measured_at).total_seconds() / 86400.0, 0.0)
        decayed = apply_forgetting(raw, days, params)
        decayed_rows.append((concept_id, code, name, raw, measured_at, days, decayed))

    def _sort_key(row: _DecayedRow) -> tuple[float, int, str]:
        _cid, code, _name, _raw, _measured_at, _days, decayed = row
        # None은 맨 뒤(1) → 같은 decayed_mastery 그룹 안에서만 유효한 tie-break.
        return (decayed, 0 if code is not None else 1, code or "")

    decayed_rows.sort(key=_sort_key)

    return [
        ReviewQueueItem(
            concept_id=cid,
            concept_code=code,
            concept_name=name,
            raw_mastery=raw,
            decayed_mastery=decayed,
            measured_at=measured_at,
            days_since_practice=days,
            due_rank=rank,
        )
        for rank, (cid, code, name, raw, measured_at, days, decayed) in enumerate(
            decayed_rows, start=1
        )
    ]


async def fetch_review_queue(
    session: AsyncSession,
    user_id: uuid.UUID,
    *,
    as_of: datetime | None = None,
) -> ReviewQueue:
    """사용자 1인의 복습 우선순위 큐 조립 — 매 호출 순수 재계산(저장 컬럼 없음).

    `concept_diagnosis.py::mastery_stmt`와 동형인 DISTINCT ON 쿼리로 개념별 *최신* 측정 1건만
    (`measured_at`도 함께) 가져온 뒤, 순수 헬퍼 `_rank_items`에 위임한다. `as_of` 생략 시
    `datetime.now(UTC)`(테스트에서 결정론 주입 가능하도록 인자로 노출).
    """
    resolved_as_of = as_of if as_of is not None else datetime.now(UTC)

    stmt = (
        select(
            ConceptMasteryHistory.concept_id,
            Concept.code,
            Concept.name_ko,
            ConceptMasteryHistory.mastery,
            ConceptMasteryHistory.measured_at,
        )
        .outerjoin(Concept, ConceptMasteryHistory.concept_id == Concept.concept_id)
        .where(ConceptMasteryHistory.user_id == user_id)
        .distinct(ConceptMasteryHistory.concept_id)
        .order_by(
            ConceptMasteryHistory.concept_id,
            ConceptMasteryHistory.measured_at.desc(),
        )
    )
    rows = (await session.execute(stmt)).all()
    plain_rows: list[_MasteryRow] = [
        (concept_id, code, name, mastery, measured_at)
        for concept_id, code, name, mastery, measured_at in rows
    ]
    return ReviewQueue(items=_rank_items(plain_rows, resolved_as_of))


__all__ = [
    "DECAY_MODEL_LABEL",
    "REVIEW_QUEUE_PARAMETERS",
    "ReviewQueue",
    "ReviewQueueItem",
    "fetch_review_queue",
]
