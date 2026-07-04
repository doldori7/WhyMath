"""개념 code → 행동영역(BehaviorArea) 런타임 해소 — concept→skill 조인 접근자(S5k).

L4 장면 생성기의 *행동영역 축* 입력원. `concept_node.behavior_skills`(concept→skill·#419)를
`skill_node.behavior_area`(정본 6종·#418)로 조인해 개념이 요구하는 행동영역 목록을 돌려준다.
`get_visualizability`(concept_visualization) 미러 — 런타임 async·미매핑이면 빈 목록(중립).

계층: L1(프로젝션 조회). L5(api)가 세션으로 호출해 L4 생성기에 주입한다(역의존 0). 본문·오개념 등
실체는 담지 않는다(안전 메타 조인만·concept_node/skill_node 순수성).
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from whymath_backend.db.models.concept_node import ConceptNode
from whymath_backend.db.models.skill_node import SkillNode
from whymath_backend.schema.enums import BehaviorArea


async def get_behavior_areas(session: AsyncSession, code: str) -> list[BehaviorArea]:
    """개념 code의 행동영역 목록 — `concept_node.behavior_skills` → `skill_node.behavior_area` 조인.

    concept_node 부재·매핑 없음·매칭 skill 0이면 빈 목록(미매핑=중립 → 생성기가 탐구 진입·focus 0).
    결정론을 위해 중복 제거 후 enum 값 기준 정렬해 돌려준다(반환 목록 안정성). code는 UC
    (`concept_node.concept_id` PK)이며 backend `concept.code`와 동일.
    """
    node = await session.get(ConceptNode, code)
    if node is None or not node.behavior_skills:
        return []
    rows = await session.execute(
        select(SkillNode.behavior_area).where(SkillNode.skill_id.in_(node.behavior_skills))
    )
    areas = {BehaviorArea(area) for area in rows.scalars().all()}
    return sorted(areas, key=lambda a: a.value)
