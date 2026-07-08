"""formula_graph validate 단위테스트 — 그래프 레벨 invariant.

hermetic: 모델 목록 → 검증(DB·네트워크 불요).
"""

from __future__ import annotations

from data_pipeline.formula_graph.models import FormulaNode
from data_pipeline.formula_graph.validate import validate_formulas


def _f(fid: str, family: str = "곱셈공식") -> FormulaNode:
    return FormulaNode(
        formula_id=fid,
        name_ko="수식",
        family=family,
        latex="a = b",
        dsl="a == b",
    )


def test_valid_graph_passes() -> None:
    """유일 id·family 다중 → error 0(PASS)."""
    nodes = [
        _f("formula.a", "곱셈공식"),
        _f("formula.b", "곱셈공식"),
        _f("formula.c", "기하공식"),
        _f("formula.d", "기하공식"),
    ]
    report = validate_formulas(nodes)
    assert report.success, report.report_text()
    assert report.errors == []


def test_duplicate_id_errors() -> None:
    """formula_id 중복 → error(canonical 중복·join 붕괴)."""
    report = validate_formulas([_f("formula.dup"), _f("formula.dup")])
    rules = {i.rule for i in report.errors}
    assert "formula_id_unique" in rules
    assert not report.success


def test_family_singleton_warns_not_errors() -> None:
    """family에 수식 1개뿐 → warning(에러 아님·구축 통과)."""
    report = validate_formulas([_f("formula.solo", "고립family")])
    assert report.success
    assert any(i.rule == "family_singleton" for i in report.warnings)
