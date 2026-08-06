"""problem_type_graph 모델 단위테스트 — `ProblemTypeNode` 동결.

hermetic: 외부 의존·DB 불요(모델 introspection·검증만).
"""

from __future__ import annotations

import pytest
from data_pipeline.problem_type_graph.models import ProblemTypeNode
from pydantic import ValidationError


def _ptype(**overrides: object) -> ProblemTypeNode:
    """기본 유효 ProblemTypeNode(오버라이드 가능)."""
    payload: dict[str, object] = {
        "problem_type_id": "ptype.optimize-extremum",
        "name_ko": "최대·최소 구하기",
        "family": "최적화",
        "behavior_skills": ["skill.graph-sketching"],
    }
    payload.update(overrides)
    return ProblemTypeNode(**payload)  # type: ignore[arg-type]


class TestProblemTypeNodeConstruction:
    def test_minimal_valid(self) -> None:
        """필수 필드만으로 생성 — 나머지 기본값."""
        p = _ptype()
        assert p.problem_type_id == "ptype.optimize-extremum"
        assert p.behavior_skills == ["skill.graph-sketching"]
        assert p.mastery_estimable is True
        assert p.standard_codes == []
        assert p.description is None

    def test_full_fields_roundtrip(self) -> None:
        """전 필드 보존."""
        p = _ptype(
            behavior_skills=["skill.graph-sketching", "skill.completing-square"],
            mastery_estimable=False,
            description="함수의 최댓값·최솟값을 구한다",
            standard_codes=["2수03-01"],
            notes="검수됨",
        )
        assert p.behavior_skills == ["skill.graph-sketching", "skill.completing-square"]
        assert p.mastery_estimable is False
        assert p.standard_codes == ["2수03-01"]

    def test_extra_forbidden(self) -> None:
        """extra='forbid' — 알 수 없는 필드 거부."""
        with pytest.raises(ValidationError):
            _ptype(bogus="x")

    @pytest.mark.parametrize(
        "bad_id",
        ["optimize", "ptype.", "ptype.Optimize", "ptype.a_b", "PTYPE.x", "ptype.x.y "],
    )
    def test_problem_type_id_pattern_rejected(self, bad_id: str) -> None:
        """problem_type_id는 'ptype.<slug>'(소문자·숫자·하이픈)만 허용."""
        with pytest.raises(ValidationError):
            _ptype(problem_type_id=bad_id)

    @pytest.mark.parametrize("ok_id", ["ptype.x", "ptype.optimize-derivative", "ptype.a1-b2-c3"])
    def test_problem_type_id_pattern_accepted(self, ok_id: str) -> None:
        """유효 problem_type_id 통과."""
        assert _ptype(problem_type_id=ok_id).problem_type_id == ok_id

    def test_behavior_skills_required_nonempty(self) -> None:
        """behavior_skills는 ≥1개(min_length=1) — 빈 배열 거부(cognitive-action 표현 보장)."""
        with pytest.raises(ValidationError):
            _ptype(behavior_skills=[])

    @pytest.mark.parametrize("bad_skill", ["factorization", "skill.", "SKILL.x", "skill.A"])
    def test_behavior_skills_format_rejected(self, bad_skill: str) -> None:
        """behavior_skills 원소는 'skill.<slug>' 형식만 허용."""
        with pytest.raises(ValidationError):
            _ptype(behavior_skills=[bad_skill])

    def test_missing_required_rejected(self) -> None:
        """필수 필드 누락 거부."""
        with pytest.raises(ValidationError):
            ProblemTypeNode(problem_type_id="ptype.x", name_ko="x")  # type: ignore[call-arg]

    def test_no_surface_or_body_slots(self) -> None:
        """노드에 표면(SignaturePattern)·본문 슬롯 없음(순수 cognitive-action 택소노미)."""
        fields = set(ProblemTypeNode.model_fields)
        for forbidden in (
            "signature_pattern",
            "signature_patterns",
            "surface",
            "misconception_text",
            "formal_definition",
            "prompt",
        ):
            assert forbidden not in fields
