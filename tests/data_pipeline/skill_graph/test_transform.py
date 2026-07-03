"""skill_graph transform 단위테스트 — `transform_skills`(정형화·skip·provenance).

hermetic: 파일 IO·DB 불요(dict 입력만).
"""

from __future__ import annotations

from data_pipeline.skill_graph.transform import transform_skills


def _rec(skill_id: str, area: str = "COMPUTE", family: str = "F", **extra: object) -> dict:
    base: dict[str, object] = {
        "skill_id": skill_id,
        "name_ko": "테스트 스킬",
        "behavior_area": area,
        "family": family,
    }
    base.update(extra)
    return base


def test_transform_happy_path() -> None:
    """유효 레코드 → SkillNode 목록·skip 0."""
    result = transform_skills([_rec("skill.a"), _rec("skill.b", area="REASON")])
    assert len(result.skills) == 2
    assert result.skipped == []
    assert result.provenance["skills"] == 2
    assert result.provenance["behavior_areas"] == 2


def test_transform_skips_invalid_and_records_reason() -> None:
    """검증 실패 행은 조용히 넘기지 않고 skip 사유 기록(신뢰 원칙)."""
    result = transform_skills(
        [
            _rec("skill.ok"),
            {"skill_id": "invalid id", "name_ko": "x", "behavior_area": "COMPUTE", "family": "F"},
            {"skill_id": "skill.missing-area", "name_ko": "x", "family": "F"},  # area 누락
        ]
    )
    assert len(result.skills) == 1
    assert len(result.skipped) == 2
    assert any("invalid id" in s for s in result.skipped)


def test_transform_family_count() -> None:
    """provenance families = 유일 family 수."""
    result = transform_skills(
        [_rec("skill.a", family="F1"), _rec("skill.b", family="F1"), _rec("skill.c", family="F2")]
    )
    assert result.provenance["families"] == 2


def test_transform_empty() -> None:
    """빈 입력 → 빈 산출(예외 없음)."""
    result = transform_skills([])
    assert result.skills == []
    assert result.provenance["skills"] == 0
