"""problem_type_graph transform 단위테스트 — 정형화·skip 기록.

hermetic: dict 입력 → 모델 정형화(DB·네트워크 불요).
"""

from __future__ import annotations

from data_pipeline.problem_type_graph.transform import transform_problem_types


def _rec(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "problem_type_id": "ptype.solve-for-unknown",
        "name_ko": "미지수 값 구하기",
        "family": "값_결정",
        "behavior_skills": ["skill.linear-equation-solving"],
    }
    base.update(overrides)
    return base


def test_transforms_valid_records() -> None:
    """유효 레코드 정형화·provenance 카운트."""
    result = transform_problem_types([_rec(), _rec(problem_type_id="ptype.evaluate-expression")])
    assert len(result.problem_types) == 2
    assert result.skipped == []
    assert result.provenance["problem_types"] == 2
    assert result.provenance["families"] == 1
    assert result.provenance["referenced_skills"] == 1


def test_invalid_record_skipped_not_dropped() -> None:
    """검증 실패 행은 조용히 누락되지 않고 skip 사유 기록(형식 위반·빈 skills)."""
    result = transform_problem_types(
        [
            _rec(),
            _rec(problem_type_id="BADID"),  # 형식 위반
            _rec(problem_type_id="ptype.empty", behavior_skills=[]),  # ≥1 위반
        ]
    )
    assert len(result.problem_types) == 1
    assert len(result.skipped) == 2


def test_referenced_skills_deduped_across_types() -> None:
    """provenance referenced_skills는 유형 간 중복 제거된 distinct 스킬 수."""
    result = transform_problem_types(
        [
            _rec(behavior_skills=["skill.a", "skill.b"]),
            _rec(problem_type_id="ptype.two", behavior_skills=["skill.b", "skill.c"]),
        ]
    )
    assert result.provenance["referenced_skills"] == 3  # a·b·c
