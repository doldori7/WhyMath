"""L4 교수법 효과 집계 — (전략 × k_type × objective)별 성과를 `evidence_event`에서 읽는다 (PED-03).

04d §3.2("측정 없는 도입 없음")의 구현. 처치(`pedagogy_render`)와 결과(`pedagogy_outcome`)를
`session_id` 축으로 이어 "어떤 교수법이 어떤 상황에서 실제로 효과가 있었는가"를 센다.

────────────────────────────────────────────────────────────────────────────
판정치 규약 — 표본 0은 0%가 아니라 **미상**
────────────────────────────────────────────────────────────────────────────
`success_rate`·`success_rate_lower`는 표본이 없으면 **`None`** 이다. 0.0을 돌려주면 "측정해 봤더니
0%"와 "측정 자체가 안 됐음"이 같은 값이 되어, 데이터가 한 건도 없는 상태가 "성과 미달"로 위장된다
(`SupplyTally.dsl_render_rate` 선례·`ops/cost_probe`가 존재하는 이유와 같은 축).

게이트 판정은 점추정이 아니라 **Wilson 단측 하한**으로 한다(`harness/wilson.py` 재사용) — 표본이
얇을수록 크게 깎여 과신을 막는다.

────────────────────────────────────────────────────────────────────────────
현재 상태에 대한 정직한 표기
────────────────────────────────────────────────────────────────────────────
이 좌석이 읽는 행은 `api/study.py`가 학생 요청을 처리할 때 생긴다. 클라이언트가 그 엔드포인트를
호출하기 전까지 **집계 결과는 전부 표본 0(=`None`)** 이다. 그것이 결함이 아니라 현재의 사실이며,
`harness/pedagogy_policy_eval.py`가 그 상태를 "측정 미달"로 exit 1 처리한다.

7계층: L4가 L2 데이터(`evidence_event`)를 *조회*만 한다(L_n→L_{n-1} 허용). 기록은 L2
(`l2/pedagogy_evidence.py`) 소관이고 여기서 쓰지 않는다.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from whymath_backend.db.models.evidence_event import EvidenceEvent
from whymath_backend.harness.wilson import wilson_lower_bound
from whymath_backend.l2.pedagogy_evidence import (
    EVENT_TYPE_OUTCOME,
    EVENT_TYPE_TREATMENT,
    META_KEY_STRATEGY,
)
from whymath_backend.schema.enums import KnowledgeType


@dataclass(frozen=True, slots=True)
class EffectivenessKey:
    """집계 축 — 04d §3.2의 "(학생군 × 개념 × 오개념유형)"을 현 데이터로 실현 가능한 형태.

    학생군은 `k_type`(지식 유형)이, 개념은 `objective_id`가 대신한다. 오개념 유형 축은 지금
    처치 기록에 담기지 않으므로 **키에 넣지 않는다** — 없는 축을 키에 넣으면 항상 단일 버킷이
    되어 "쪼갰다"는 착시만 준다(가짜 세분화 금지). 오개념 축이 필요해지면 처치 기록에 그 필드를
    *먼저* 추가하고 그때 연다.
    """

    strategy: str
    k_type: str
    objective_id: str


@dataclass(slots=True)
class EffectivenessStat:
    """한 축의 성과 — 시도 수·정답 수·소요시간 합계에서 파생 지표를 낸다."""

    trials: int = 0
    successes: int = 0
    rt_ms_total: int = 0
    rt_ms_samples: int = 0

    @property
    def success_rate(self) -> float | None:
        """정답률 점추정. **표본 0이면 None**(미상을 0%로 위장하지 않는다)."""
        if self.trials == 0:
            return None
        return self.successes / self.trials

    @property
    def success_rate_lower(self) -> float | None:
        """정답률 Wilson 단측 95% 하한 — 게이트 판정축. 표본 0이면 None."""
        if self.trials == 0:
            return None
        return wilson_lower_bound(self.successes, self.trials)

    @property
    def mean_rt_ms(self) -> float | None:
        """평균 소요 시간(체류 대용). 측정된 표본이 없으면 None."""
        if self.rt_ms_samples == 0:
            return None
        return self.rt_ms_total / self.rt_ms_samples

    def to_json(self) -> dict[str, Any]:
        """사람·자동화가 읽는 요약 — 미상은 None으로 남긴다."""
        return {
            "trials": self.trials,
            "successes": self.successes,
            "success_rate": self.success_rate,
            "success_rate_lower": self.success_rate_lower,
            "mean_rt_ms": self.mean_rt_ms,
        }


@dataclass(slots=True)
class EffectivenessReport:
    """축별 성과 묶음 + 전체 표본 수."""

    stats: dict[EffectivenessKey, EffectivenessStat] = field(default_factory=dict)

    @property
    def total_trials(self) -> int:
        return sum(s.trials for s in self.stats.values())

    def to_json(self) -> dict[str, Any]:
        return {
            "total_trials": self.total_trials,
            "cells": [
                {
                    "strategy": key.strategy,
                    "k_type": key.k_type,
                    "objective_id": key.objective_id,
                    **stat.to_json(),
                }
                for key, stat in sorted(
                    self.stats.items(),
                    key=lambda kv: (kv[0].strategy, kv[0].k_type, kv[0].objective_id),
                )
            ],
        }


def _strategy_of(row: EvidenceEvent) -> str | None:
    """처치 행의 `meta`에서 전략명을 꺼낸다. 없거나 형이 다르면 None(그 세션은 집계 제외)."""
    meta = row.meta
    if not isinstance(meta, dict):
        return None
    value = meta.get(META_KEY_STRATEGY)
    return value if isinstance(value, str) else None


def aggregate_effectiveness(rows: list[EvidenceEvent]) -> EffectivenessReport:
    """`evidence_event` 행들 → 축별 성과(순수 함수·DB 비의존).

    처치와 결과를 **`session_id`** 로 잇는다: 한 세션의 처치가 정한 전략을, 같은 세션의 결과
    행들에 귀속시킨다. 처치가 없는 세션의 결과는 **버린다** — 무엇을 보여줬는지 모르는 결과는
    효과 비교에 쓸 수 없다(귀속 불가를 임의 전략에 배정하면 측정이 오염된다).

    한 세션에 처치가 여러 건이면 **가장 이른 처치**를 그 세션의 전략으로 본다(결과가 그 처치
    이후에 발생했다는 인과 순서를 보수적으로 유지). 이 규약은 세션이 단일 학습 단위라는 전제에
    기댄다 — 세션 안에서 전략을 갈아 끼우는 흐름이 생기면 처치 시각 기준 구간 귀속으로 정교화해야
    한다(그때까지는 이 단순 규약이 정직하다).
    """
    treatment_by_session: dict[uuid.UUID, EvidenceEvent] = {}
    outcomes: list[EvidenceEvent] = []
    for row in rows:
        if row.event_type == EVENT_TYPE_TREATMENT:
            prev = treatment_by_session.get(row.session_id)
            if prev is None or row.time < prev.time:
                treatment_by_session[row.session_id] = row
        elif row.event_type == EVENT_TYPE_OUTCOME:
            outcomes.append(row)

    stats: dict[EffectivenessKey, EffectivenessStat] = defaultdict(EffectivenessStat)
    for outcome in outcomes:
        treatment = treatment_by_session.get(outcome.session_id)
        if treatment is None:
            continue  # 처치 미상 — 귀속 불가라 버린다(임의 배정 금지).
        strategy = _strategy_of(treatment)
        if strategy is None:
            continue  # 전략 메타 없음 — 같은 이유로 제외.
        if outcome.correct is None:
            continue  # 정답 여부 미기록 — 정답률 분모에 넣지 않는다.
        key = EffectivenessKey(
            strategy=strategy,
            # PG native enum 경유 행은 k_type이 KnowledgeType 멤버로 온다 — str(멤버)는
            # "KnowledgeType.CONCEPT"(라벨 집합 밖 맹글링)이므로 .value로 정규화한다
            # (api/study.py 동일 사고 2026-08-11 실 PG 실측·test_study_k_type_enum_binding 참조).
            # 멱등: 평문 라벨 문자열이 와도 KnowledgeType("CONCEPT").value == "CONCEPT".
            k_type=KnowledgeType(outcome.k_type).value,
            objective_id=outcome.objective_id,
        )
        stat = stats[key]
        stat.trials += 1
        if outcome.correct:
            stat.successes += 1
        if outcome.rt_ms is not None:
            stat.rt_ms_total += outcome.rt_ms
            stat.rt_ms_samples += 1

    return EffectivenessReport(stats=dict(stats))


async def load_pedagogy_events(
    session: AsyncSession, *, objective_id: str | None = None, limit: int = 100_000
) -> list[EvidenceEvent]:
    """집계 대상 `evidence_event` 행 조회 — 교수법 두 유형만(다른 팩 이벤트 배제).

    `limit`은 폭주 방어(운영 규모가 커지면 시간 창 필터로 정교화). 정렬은 `time` 오름차순으로
    고정해 "가장 이른 처치" 선택이 결정론이 되게 한다.
    """
    stmt = select(EvidenceEvent).where(
        EvidenceEvent.event_type.in_([EVENT_TYPE_TREATMENT, EVENT_TYPE_OUTCOME])
    )
    if objective_id is not None:
        stmt = stmt.where(EvidenceEvent.objective_id == objective_id)
    stmt = stmt.order_by(EvidenceEvent.time.asc()).limit(limit)
    return list((await session.execute(stmt)).scalars().all())


__all__ = [
    "EffectivenessKey",
    "EffectivenessReport",
    "EffectivenessStat",
    "aggregate_effectiveness",
    "load_pedagogy_events",
]
