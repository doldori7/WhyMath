"""L2 — IRT 능력 θ *추정*(채점 풀이 이력 → θ·SE·응답수).

학습자 모델 추정은 L2 책임(7계층). `irt.py`(순수 IRT 알고리즘)·`mastery_tracking.py`(BKT
추정+영속)와 대칭으로, 이 모듈은 *채점 이력에서 IRT θ를 추정*한다(난이도 b 변환 + `estimate_ability`
조율 + DB 조회). *현재값 읽기*는 `ability_tracking`(`get_current_theta`/`get_current_ability`)·
*스냅샷 영속*은 api/me 오케스트레이션(`_add_ability_snapshot_if_attempts` 등) 책임 — 추정/읽기/
영속을 분리한다(slice 78에 api/me L5에서 이관 — L2→L5 역방향 의존 제거).
"""

from __future__ import annotations

import math
import uuid

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from whymath_backend.db.models.activity import ProblemAttempt
from whymath_backend.db.models.concept import Concept, ProblemConcept
from whymath_backend.db.models.problem import Problem
from whymath_backend.l2.irt import IrtItem, ability_standard_error, estimate_ability
from whymath_backend.l2.mastery_tracking import _ASSESSED_ROLES

_DIFFICULTY_MIDPOINT = 3.0  # Problem.difficulty_overall(1~5)의 중앙 → logit 0


def difficulty_to_logit(difficulty: float) -> float:
    """`difficulty_overall`(1~5) → IRT 난이도 b(logit). 휴리스틱 프록시(중앙 3=b0·범위 [-2,2]).

    *보정된* b는 응답 데이터로 `fit_jmle`(slice 10) 적합이 정답이나, 그 전까지 전문가 난이도
    라벨(1~5)을 선형 매핑해 능력 추정에 쓴다(difficulty 1=쉬움→b=-2·5=어려움→b=+2).
    """
    return difficulty - _DIFFICULTY_MIDPOINT


class ConceptAbilityItem(BaseModel):
    """개념별 IRT 능력 — `GET /v1/me/ability/by-concept`의 한 개념 항목."""

    concept_id: uuid.UUID = Field(description="개념 id.")
    concept_code: str | None = Field(default=None, description="개념 코드(orphan이면 null).")
    concept_name: str | None = Field(default=None, description="개념명(orphan이면 null).")
    theta: float = Field(description="이 개념 문항들로 추정한 능력 θ(logit).")
    response_count: int = Field(description="이 개념 추정에 쓰인 채점 풀이 수.")
    standard_error: float | None = Field(
        default=None, description="θ 표준오차 SE=1/√I(θ). 측정 불가면 null."
    )


async def estimate_global_ability(
    session: AsyncSession, user_id: uuid.UUID
) -> tuple[float, float | None, int]:
    """채점 풀이 이력에서 전 과목 단일 θ·SE·응답수 추정 — `/ability`·snapshot 캡처 공유.

    `problem_attempt`(채점됨)를 `problem` JOIN해 (난이도→b, 정답) 응답을 만들고 θ·SE 산출.
    SE는 정보 0(응답 없음)이면 None(측정 불가). 난이도 NULL 문항 제외.
    """
    stmt = (
        select(ProblemAttempt.is_correct, Problem.difficulty_overall)
        .join(Problem, ProblemAttempt.problem_id == Problem.problem_id)
        .where(
            ProblemAttempt.user_id == user_id,
            ProblemAttempt.is_correct.isnot(None),
        )
    )
    responses = [
        (IrtItem(difficulty=difficulty_to_logit(float(difficulty))), bool(is_correct))
        for is_correct, difficulty in (await session.execute(stmt)).all()
        if difficulty is not None
    ]
    theta = estimate_ability(responses)
    se = ability_standard_error(theta, [item for item, _ in responses])
    return theta, (None if math.isinf(se) else se), len(responses)


async def compute_concept_abilities(
    session: AsyncSession, user_id: uuid.UUID
) -> list[ConceptAbilityItem]:
    """개념별 IRT θ·SE·응답수·메타 산출(정렬 전) — `/ability/by-concept`·snapshot 캡처 공유."""
    stmt = (
        select(
            ProblemConcept.concept_id,
            Concept.code,
            Concept.name_ko,
            ProblemAttempt.is_correct,
            Problem.difficulty_overall,
        )
        .join(Problem, ProblemAttempt.problem_id == Problem.problem_id)
        .join(ProblemConcept, ProblemConcept.problem_id == Problem.problem_id)
        .outerjoin(Concept, ProblemConcept.concept_id == Concept.concept_id)
        .where(
            ProblemAttempt.user_id == user_id,
            ProblemAttempt.is_correct.isnot(None),
            ProblemConcept.role.in_(_ASSESSED_ROLES),
            Problem.difficulty_overall.isnot(None),
        )
    )
    grouped: dict[uuid.UUID, list[tuple[IrtItem, bool]]] = {}
    meta: dict[uuid.UUID, tuple[str | None, str | None]] = {}
    for concept_id, code, name, is_correct, difficulty in (await session.execute(stmt)).all():
        item = IrtItem(difficulty=difficulty_to_logit(float(difficulty)))
        grouped.setdefault(concept_id, []).append((item, bool(is_correct)))
        meta[concept_id] = (code, name)

    items = []
    for concept_id, responses in grouped.items():
        theta = estimate_ability(responses)
        se = ability_standard_error(theta, [it for it, _ in responses])
        code, name = meta[concept_id]
        items.append(
            ConceptAbilityItem(
                concept_id=concept_id,
                concept_code=code,
                concept_name=name,
                theta=theta,
                response_count=len(responses),
                standard_error=None if math.isinf(se) else se,
            )
        )
    return items


__all__ = [
    "ConceptAbilityItem",
    "compute_concept_abilities",
    "difficulty_to_logit",
    "estimate_global_ability",
]
