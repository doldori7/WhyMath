"""skill_graph validate 단위테스트 — 그래프 레벨 invariant.

hermetic: DB 불요(SkillNode 목록만).
"""

from __future__ import annotations

from data_pipeline.skill_graph.models import BehaviorArea, SkillNode
from data_pipeline.skill_graph.validate import validate_skills


def _skill(skill_id: str, area: BehaviorArea = BehaviorArea.COMPUTE, **extra: object) -> SkillNode:
    payload: dict[str, object] = {
        "skill_id": skill_id,
        "name_ko": "스킬",
        "behavior_area": area,
        "family": "F",
    }
    payload.update(extra)
    return SkillNode(**payload)  # type: ignore[arg-type]


def _all_areas() -> list[SkillNode]:
    """6종 행동영역을 모두 덮는 최소 스킬셋(coverage warning 회피용)."""
    return [_skill(f"skill.a{i}", area=area) for i, area in enumerate(BehaviorArea)]


def test_valid_graph_passes() -> None:
    """유일·비순환·6종 커버 → PASS(error·warning 0)."""
    report = validate_skills(_all_areas())
    assert report.success
    assert report.errors == []
    assert report.warnings == []


def test_duplicate_skill_id_error() -> None:
    """skill_id 중복 → error."""
    skills = [*_all_areas(), _skill("skill.a0")]  # a0 재사용(중복)
    report = validate_skills(skills)
    assert not report.success
    assert any(i.rule == "skill_id_unique" for i in report.errors)


def test_prerequisite_dangling_error() -> None:
    """선수 스킬이 코퍼스에 없으면 error."""
    skills = [*_all_areas(), _skill("skill.x", prerequisite_skill_ids=["skill.ghost"])]
    report = validate_skills(skills)
    assert any(i.rule == "prerequisite_dangling" for i in report.errors)


def test_prerequisite_cycle_error() -> None:
    """선수 참조 순환 → error(DAG 위반)."""
    skills = [
        *_all_areas(),
        _skill("skill.p", prerequisite_skill_ids=["skill.q"]),
        _skill("skill.q", prerequisite_skill_ids=["skill.p"]),
    ]
    report = validate_skills(skills)
    assert any(i.rule == "prerequisite_cycle" for i in report.errors)


def test_valid_prerequisite_chain_passes() -> None:
    """비순환 선수 체인은 통과."""
    skills = [
        *_all_areas(),
        _skill("skill.p", prerequisite_skill_ids=["skill.q"]),
        _skill("skill.q", prerequisite_skill_ids=["skill.r"]),
        _skill("skill.r"),
    ]
    report = validate_skills(skills)
    assert report.success


def test_missing_behavior_area_coverage_warning() -> None:
    """6종 중 일부 미커버 → warning(에러 아님·구축 안 막음)."""
    report = validate_skills([_skill("skill.only", area=BehaviorArea.COMPUTE)])
    assert report.success  # warning뿐이라 여전히 성공
    coverage = [i for i in report.warnings if i.rule == "behavior_area_coverage"]
    assert len(coverage) == 5  # COMPUTE 제외 5종 미커버
