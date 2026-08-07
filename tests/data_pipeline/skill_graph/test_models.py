"""skill_graph 모델·enum 단위테스트 — `SkillNode`·`BehaviorArea` 동결.

hermetic: 외부 의존·DB 불요(모델 introspection·검증만).
"""

from __future__ import annotations

import pytest
from data_pipeline.skill_graph.models import (
    BEHAVIOR_AREAS,
    BehaviorArea,
    SkillNode,
)
from pydantic import ValidationError


def _skill(**overrides: object) -> SkillNode:
    """기본 유효 SkillNode(오버라이드 가능)."""
    payload: dict[str, object] = {
        "skill_id": "skill.factorization",
        "name_ko": "인수분해",
        "behavior_area": BehaviorArea.TRANSFORM,
        "family": "인수분해와 전개",
    }
    payload.update(overrides)
    return SkillNode(**payload)  # type: ignore[arg-type]


class TestBehaviorAreaFrozen:
    """BehaviorArea 폐쇄 6종 동결 — 추가/변경 시 ADR 갱신 강제(무분별 증식 방지)."""

    def test_exactly_six_members(self) -> None:
        """행동영역은 정확히 6종(2026-07-03 확정)."""
        assert len(BehaviorArea) == 6

    def test_value_set_frozen(self) -> None:
        """6종 값 집합 동결 — English enum value."""
        assert {a.value for a in BehaviorArea} == {
            "COMPUTE",
            "TRANSFORM",
            "INTERPRET",
            "REPRESENT",
            "REASON",
            "VERIFY",
        }

    def test_behavior_areas_mirror(self) -> None:
        """BEHAVIOR_AREAS 튜플이 enum 값과 일치(단일 진실)."""
        assert BEHAVIOR_AREAS == tuple(a.value for a in BehaviorArea)


class TestSkillNodeConstruction:
    def test_minimal_valid(self) -> None:
        """필수 필드만으로 생성 — 나머지 기본값."""
        s = _skill()
        assert s.skill_id == "skill.factorization"
        assert s.behavior_area == "TRANSFORM"  # use_enum_values=True → 문자열
        assert s.mastery_estimable is True
        assert s.prerequisite_skill_ids == []
        assert s.standard_codes == []
        assert s.description is None

    def test_full_fields_roundtrip(self) -> None:
        """전 필드 보존."""
        s = _skill(
            mastery_estimable=False,
            description="식을 인수의 곱으로 변형",
            prerequisite_skill_ids=["skill.expansion"],
            standard_codes=["2수03-01"],
            notes="검수됨",
        )
        assert s.mastery_estimable is False
        assert s.prerequisite_skill_ids == ["skill.expansion"]
        assert s.standard_codes == ["2수03-01"]

    def test_extra_forbidden(self) -> None:
        """extra='forbid' — 알 수 없는 필드 거부."""
        with pytest.raises(ValidationError):
            _skill(bogus="x")

    @pytest.mark.parametrize(
        "bad_id",
        ["factorization", "skill.", "skill.Factor", "skill.a_b", "SKILL.x", "skill.x.y "],
    )
    def test_skill_id_pattern_rejected(self, bad_id: str) -> None:
        """skill_id는 'skill.<slug>'(소문자·숫자·하이픈)만 허용."""
        with pytest.raises(ValidationError):
            _skill(skill_id=bad_id)

    @pytest.mark.parametrize("ok_id", ["skill.x", "skill.polynomial-division", "skill.a1-b2-c3"])
    def test_skill_id_pattern_accepted(self, ok_id: str) -> None:
        """유효 skill_id 통과."""
        assert _skill(skill_id=ok_id).skill_id == ok_id

    def test_missing_required_rejected(self) -> None:
        """필수 필드 누락 거부."""
        with pytest.raises(ValidationError):
            SkillNode(skill_id="skill.x", name_ko="x")  # type: ignore[call-arg]

    def test_no_body_slots(self) -> None:
        """노드에 본문·오개념 슬롯 없음(순수 스킬 택소노미 — 개념 노드와 동형)."""
        fields = set(SkillNode.model_fields)
        for forbidden in ("misconception_text", "formal_definition", "prompt", "renderer"):
            assert forbidden not in fields
