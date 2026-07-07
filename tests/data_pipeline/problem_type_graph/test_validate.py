"""problem_type_graph validate 단위테스트 — 그래프 레벨 invariant.

hermetic: 모델 목록 → 검증(DB·네트워크 불요).
"""

from __future__ import annotations

from data_pipeline.problem_type_graph.models import ProblemTypeNode
from data_pipeline.problem_type_graph.validate import validate_problem_types


def _ptype(pid: str, family: str = "값_결정", skills: list[str] | None = None) -> ProblemTypeNode:
    return ProblemTypeNode(
        problem_type_id=pid,
        name_ko="유형",
        family=family,
        behavior_skills=skills or ["skill.linear-equation-solving"],
    )


def test_valid_graph_passes() -> None:
    """유일 id·비어있지 않은 skills·family 다중 → error 0(PASS)."""
    nodes = [
        _ptype("ptype.a", "값_결정"),
        _ptype("ptype.b", "값_결정"),
        _ptype("ptype.c", "최적화", ["skill.graph-sketching"]),
        _ptype("ptype.d", "최적화", ["skill.completing-square"]),
    ]
    report = validate_problem_types(nodes)
    assert report.success, report.report_text()
    assert report.errors == []


def test_duplicate_id_errors() -> None:
    """problem_type_id 중복 → error(join 붕괴)."""
    report = validate_problem_types([_ptype("ptype.dup"), _ptype("ptype.dup")])
    rules = {i.rule for i in report.errors}
    assert "problem_type_id_unique" in rules
    assert not report.success


def test_family_singleton_warns_not_errors() -> None:
    """family에 유형 1개뿐 → warning(에러 아님·구축 통과)."""
    report = validate_problem_types([_ptype("ptype.solo", "고립family")])
    assert report.success  # warning은 성공을 막지 않음
    assert any(i.rule == "family_singleton" for i in report.warnings)
