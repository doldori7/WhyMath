"""L2 개념 진단 — BKT 숙달 ↔ IRT 능력 θ 교차검증(순수 신호).

같은 개념 축에서 BKT 최신 숙달 P(L)과 IRT 능력 θ(logistic 프록시)를 비교해 *합의/불일치* 신호
(agree·irt_higher·bkt_higher·insufficient)를 분류한다. 학습자 모델(L2) 두 추정(BKT·IRT)의 교차
검증이므로 L2 책임 — 코칭 *결정*은 L4(`recommend_coaching`)·노출은 L5(api/me) 후처리. 역방향
의존 회피: L2는 *순수 신호*만 반환하고 coaching은 미포함(L5가 부착).

설계: BKT 최신 숙달(`ConceptMasteryHistory` DISTINCT ON)과 IRT θ(`compute_concept_abilities`
재사용)를 조합 — slice 82에 api/me(L5)에서 이관(IRT 쿼리 중복 제거·경계 정리·코칭 분리).
"""

from __future__ import annotations

import math
import uuid
from typing import Literal

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from whymath_backend.db.models.assessment import ConceptMasteryHistory
from whymath_backend.db.models.concept import Concept
from whymath_backend.l2.ability_estimation import compute_concept_abilities
from whymath_backend.l2.irt import theta_to_mastery_proxy

# BKT 숙달 P(L)과 IRT 능력 프록시(logistic θ)의 차가 이 임계를 넘으면 *불일치 신호*로 분기.
_DIAGNOSIS_TOL = 0.2

Agreement = Literal["agree", "irt_higher", "bkt_higher", "insufficient"]


def diagnosis_agreement(bkt_mastery: float | None, irt_proxy: float | None) -> Agreement:
    """BKT 숙달과 IRT 능력 프록시의 일치 신호 — 둘 다 있을 때만 차이로 분기.

    `irt_proxy - bkt_mastery` > tol → `irt_higher`(문항은 맞히나 BKT는 미숙달로 봄·BKT 지연/추측
    의심)·< -tol → `bkt_higher`(BKT는 숙달이나 IRT 능력 낮음·망각/고난도 의심)·이내면 `agree`.
    한쪽이라도 없으면 `insufficient`(교차검증 불가). 순수·결정론.
    """
    if bkt_mastery is None or irt_proxy is None:
        return "insufficient"
    diff = irt_proxy - bkt_mastery
    if diff > _DIAGNOSIS_TOL:
        return "irt_higher"
    if diff < -_DIAGNOSIS_TOL:
        return "bkt_higher"
    return "agree"


class ConceptDiagnosis(BaseModel):
    """개념별 BKT↔IRT 교차검증 신호(코칭 입력용) — coaching은 L5 후처리에서 부착."""

    concept_id: uuid.UUID = Field(description="개념 id.")
    concept_code: str | None = Field(default=None, description="개념 코드(orphan이면 null).")
    concept_name: str | None = Field(default=None, description="개념명(orphan이면 null).")
    bkt_mastery: float | None = Field(
        default=None, description="BKT 최신 숙달 P(L). 측정 없으면 null."
    )
    irt_theta: float | None = Field(
        default=None, description="개념별 IRT 능력 θ. 채점 풀이 없으면 null."
    )
    irt_mastery_proxy: float | None = Field(
        default=None, description="logistic(θ)∈[0,1] — BKT 숙달과 비교용. θ 없으면 null."
    )
    response_count: int = Field(description="개념별 IRT 추정에 쓰인 채점 풀이 수.")
    agreement: Agreement = Field(
        description="BKT↔IRT 일치 신호(agree·irt_higher·bkt_higher·insufficient)."
    )


async def compute_concept_diagnoses(
    session: AsyncSession, user_id: uuid.UUID
) -> list[ConceptDiagnosis]:
    """개념별 BKT↔IRT 교차검증을 계산·*약점 먼저* 정렬해 반환(필터·상한·코칭 미포함).

    ① BKT 최신 숙달 스냅샷(DISTINCT ON) → ② IRT θ는 `compute_concept_abilities` 재사용(개념별
    θ·응답수·메타) → ③ 둘 중 하나라도 있는 개념을 합집합으로 모아 proxy·agreement·약점 정렬.
    쿼리 순서는 BKT→IRT(엔드포인트 FakeSession 큐·동작 보존). meta는 BKT 우선·ability 폴백.
    """
    mastery_stmt = (
        select(
            ConceptMasteryHistory.concept_id,
            Concept.code,
            Concept.name_ko,
            ConceptMasteryHistory.mastery,
        )
        .outerjoin(Concept, ConceptMasteryHistory.concept_id == Concept.concept_id)
        .where(ConceptMasteryHistory.user_id == user_id)
        .distinct(ConceptMasteryHistory.concept_id)
        .order_by(
            ConceptMasteryHistory.concept_id,
            ConceptMasteryHistory.measured_at.desc(),
        )
    )
    bkt: dict[uuid.UUID, float | None] = {}
    meta: dict[uuid.UUID, tuple[str | None, str | None]] = {}
    for cid, code, name, mastery in (await session.execute(mastery_stmt)).all():
        bkt[cid] = float(mastery) if mastery is not None else None
        meta[cid] = (code, name)

    abilities = {a.concept_id: a for a in await compute_concept_abilities(session, user_id)}

    out: list[ConceptDiagnosis] = []
    for cid in bkt.keys() | abilities.keys():
        ability = abilities.get(cid)
        theta = ability.theta if ability is not None else None
        proxy = theta_to_mastery_proxy(theta) if theta is not None else None
        if cid in meta:
            code, name = meta[cid]
        elif ability is not None:
            code, name = ability.concept_code, ability.concept_name
        else:  # pragma: no cover — 합집합이라 둘 중 하나엔 존재(도달 불가)
            code, name = None, None
        out.append(
            ConceptDiagnosis(
                concept_id=cid,
                concept_code=code,
                concept_name=name,
                bkt_mastery=bkt.get(cid),
                irt_theta=theta,
                irt_mastery_proxy=proxy,
                response_count=ability.response_count if ability is not None else 0,
                agreement=diagnosis_agreement(bkt.get(cid), proxy),
            )
        )

    def _weakness(d: ConceptDiagnosis) -> tuple[float, str]:
        # 약점(두 신호 중 최저) 먼저. 비교 가능한 신호 없으면 맨 뒤(inf).
        signals = [v for v in (d.bkt_mastery, d.irt_mastery_proxy) if v is not None]
        return (min(signals) if signals else math.inf, str(d.concept_id))

    out.sort(key=_weakness)
    return out


__all__ = [
    "Agreement",
    "ConceptDiagnosis",
    "compute_concept_diagnoses",
    "diagnosis_agreement",
]
