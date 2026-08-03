"""L4 오케스트레이션 — L1 조회 → `ProbeCandidate` 풀 조립 (REC-02 acceptance ②③④).

WH-1 하네스 도구6 `select_probe`가 라이브에서 늘 실패하는 근본 원인은 후보 공급선 부재다
(`l4/misconception/probe_selection.py`가 순수 결정 로직만 갖고 있고, 후보를 채우는 프로덕션
호출자가 0건). 이 모듈이 그 공급선이다 — `l1.misconception.probe_lookup`(DB 조회)을
`l4.misconception.probe_selection.ProbeCandidate`(L4 순수 모델)로 변환한다.

`l4/misconception/warmstart.py`와 동형 위치(L4·DB-aware 보조 모듈) — `probe_selection.py`
자체는 이 모듈을 몰라도 되고(호출 방향은 하네스가 이 모듈을 부르고, 그 결과를 순수 함수에
넘기는 구조), `probe_selection.py`는 한 줄도 바뀌지 않는다(acceptance ⑥ — L4 순수 계약은
`probe_selection.py` 한 파일에만 걸린 것이라 이 파일이 DB를 아는 것은 계약 위반이 아니다).

**ε-탐색 성립(③)**: `target_mids`는 턴 인덱스·탐색 여부와 *무관하게* 항상
"활성 가설 mids ∪ outside_mids"의 합집합이다. `resolve_probe_target`(무변경)이 그 턴에 활용
(활성 최상위)을 겨냥하든 탐색(외부 후보)을 겨냥하든, 대응하는 후보가 이미 풀에 있다 — 탐색
여부에 따라 조립 로직을 분기할 필요가 없다(오히려 분기하면 탐색 턴에만 후보가 있고 활용 턴엔
없는 식의 새로운 결손을 만들 위험).

**reactive retrieval 준수(②)**: 이 모듈의 반환값(`ProbeSupplyOutcome.candidates`)은 하네스가
`LLMTutorPolicy.probe_candidates`(사적 필드)로만 주입한다 — 프롬프트·코칭 context·레코드에는
흐르지 않는다(하네스 쪽 불변식, `wh1_llm_policy.py`/`wh1_shadow.py` 참조).
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from whymath_backend.l1.misconception.probe_lookup import lookup_probe_candidates_by_mids
from whymath_backend.l2.ability_estimation import resolve_item_difficulty_b
from whymath_backend.l4.misconception.hypothesis import MisconceptionHypothesis
from whymath_backend.l4.misconception.probe_selection import ProbeCandidate
from whymath_backend.l4.misconception.probe_supply_exclusions import (
    ProbeSupplyExclusions,
    log_probe_supply_exclusions,
)

__all__ = ["ProbeSupplyOutcome", "assemble_probe_candidates"]

# irt_a NULL·비양수 방어 폴백 — ProbeCandidate.discrimination은 gt=0 제약(Rasch 기본 1.0).
_DEFAULT_DISCRIMINATION = 1.0


@dataclass(frozen=True, slots=True)
class ProbeSupplyOutcome:
    """`assemble_probe_candidates` 결과 — 후보 풀 + 정직 회계(④)."""

    candidates: tuple[ProbeCandidate, ...]
    exclusions: ProbeSupplyExclusions


async def assemble_probe_candidates(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    active_hypotheses: Sequence[MisconceptionHypothesis],
    outside_mids: Sequence[str],
    seat: str,
) -> ProbeSupplyOutcome:
    """L1 역인덱스 조회 → `ProbeCandidate` 풀 조립 — 하네스 주입 좌석(REC-02 ②③④).

    `target_mids = 활성가설mids ∪ outside_mids`(합집합·턴 인덱스 무관 — ε-탐색 성립 근거는
    모듈 docstring 참조). 겨냥할 mid 자체가 없으면(둘 다 빈 시퀀스) 조회 없이 즉시 빈 풀 +
    `no_target_mids=1`. `ProbeCandidate.misconception_tags`엔 검색에 쓴 부분집합이 아니라
    **문항의 distractor_map 전체 mid 집합**을 담는다(`discriminates` 판정 정확성 — 경쟁 mid도
    태깅된 문항을 "경쟁 없음"으로 오판정하지 않도록). 난이도는 `resolve_item_difficulty_b`
    (L2, JMLE 보정값 우선·전문가 라벨 폴백) 재사용(재구현 0) — L1이 이미 `difficulty_overall
    is not None`인 행만 `kept`에 담으므로 실제로 None이 나올 일은 없다(방어적 처리만 유지).

    조립 결과는 매 호출마다 `log_probe_supply_exclusions`로 사유별 계상을 로깅한다(0건이면
    무로그).
    """
    target_mids = frozenset(h.misconception_id for h in active_hypotheses) | frozenset(outside_mids)
    if not target_mids:
        exclusions = ProbeSupplyExclusions(no_target_mids=1)
        log_probe_supply_exclusions(seat, exclusions, kept=0)
        return ProbeSupplyOutcome(candidates=(), exclusions=exclusions)

    lookup = await lookup_probe_candidates_by_mids(
        session, user_id=user_id, target_mids=target_mids
    )
    untagged_mids = target_mids - lookup.matched_target_mids

    candidates = tuple(
        ProbeCandidate(
            problem_id=str(row.problem_id),
            difficulty=resolve_item_difficulty_b(row.irt_difficulty_b, row.difficulty_overall)
            or 0.0,
            discrimination=(
                row.irt_a if row.irt_a is not None and row.irt_a > 0 else _DEFAULT_DISCRIMINATION
            ),
            misconception_tags=row.misconception_tags,
        )
        for row in lookup.kept
    )
    exclusions = ProbeSupplyExclusions(
        untagged_mid=len(untagged_mids),
        missing_difficulty=lookup.missing_difficulty,
        fully_administered=lookup.fully_administered,
    )
    log_probe_supply_exclusions(seat, exclusions, kept=len(candidates))
    return ProbeSupplyOutcome(candidates=candidates, exclusions=exclusions)
