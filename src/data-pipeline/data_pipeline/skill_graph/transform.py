"""스킬 그래프 정형화 — `skills.jsonl`(자체작성) → `SkillNode` 모델 목록.

입력이 xlsx가 아니라 자체작성 `skills.jsonl`이라 `atom_graph`와 달리 별도 extract 단계가 없다
(택소노미가 우리 자산). 각 raw 레코드를 `SkillNode`로 구성하며(Pydantic 검증), 실패 행은 조용히
넘기지 않고 `skipped`에 사유를 기록한다(CLAUDE.md 신뢰 원칙). concept_graph/atom_graph transform의
`TransformResult`(모델 목록 + skipped + provenance 카운트) 패턴을 미러한다.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from pydantic import ValidationError

from data_pipeline.skill_graph.models import BEHAVIOR_AREAS, SkillNode


@dataclass(frozen=True, slots=True)
class TransformResult:
    """정형화 산출 — 스킬 노드 목록 + skip 사유 + provenance 카운트."""

    skills: list[SkillNode]
    skipped: list[str] = field(default_factory=list)
    provenance: dict[str, int] = field(default_factory=dict)

    def summary(self) -> str:
        """한 줄 요약(정형화 카운트)."""
        by_area = {area: 0 for area in BEHAVIOR_AREAS}
        for s in self.skills:
            by_area[s.behavior_area] = by_area.get(s.behavior_area, 0) + 1
        area_str = "·".join(f"{a} {n}" for a, n in by_area.items())
        return f"정형화: 스킬 {len(self.skills)}개({area_str}), skip {len(self.skipped)}건"


def transform_skills(records: list[dict[str, object]]) -> TransformResult:
    """raw 스킬 레코드 목록 → `SkillNode` 정형화(Pydantic 검증·실패 행 skip 기록).

    각 레코드를 `SkillNode(**record)`로 구성한다 — `extra="forbid"`·형식 검증(skill_id 패턴)·
    필수 필드 누락은 `ValidationError`로 잡아 `skipped`에 사유를 남긴다(조용한 누락 금지). 중복
    skill_id는 여기서 막지 않는다(컬렉션 레벨 검증 `validate_skills` 몫 — 분담).
    """
    skills: list[SkillNode] = []
    skipped: list[str] = []
    families: set[str] = set()
    for i, record in enumerate(records):
        try:
            skill = SkillNode(**record)  # type: ignore[arg-type]
        except ValidationError as exc:
            sid = record.get("skill_id", f"<index {i}>")
            skipped.append(f"{sid}: {exc.error_count()}개 검증 오류")
            continue
        skills.append(skill)
        families.add(skill.family)
    provenance = {
        "skills": len(skills),
        "families": len(families),
        "behavior_areas": len({s.behavior_area for s in skills}),
    }
    return TransformResult(skills=skills, skipped=skipped, provenance=provenance)
