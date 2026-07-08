"""formula_graph models 단위테스트 — FormulaNode 검증(형식·필수·extra forbid).

hermetic: 모델 생성만(DB·네트워크 불요).
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from data_pipeline.formula_graph.models import FORMULA_ID_PATTERN, FormulaNode


def _valid(**overrides: object) -> FormulaNode:
    base: dict[str, object] = {
        "formula_id": "formula.quadratic.roots",
        "name_ko": "근의 공식",
        "family": "근의공식",
        "latex": "x = \\frac{-b \\pm \\sqrt{b^2-4ac}}{2a}",
        "dsl": "x == (-b + sqrt(b**2 - 4*a*c))/(2*a)",
    }
    base.update(overrides)
    return FormulaNode(**base)  # type: ignore[arg-type]


def test_valid_formula() -> None:
    """유효 수식 — 필수 필드·기본값(aliases/standard_codes=[]·signature=None)."""
    node = _valid()
    assert node.formula_id == "formula.quadratic.roots"
    assert node.aliases == []
    assert node.standard_codes == []
    assert node.canonical_signature is None


def test_formula_id_pattern() -> None:
    """formula_id는 'formula.<slug>' 형식(점 계층 허용·대문자/공백 거부)."""
    assert FORMULA_ID_PATTERN.match("formula.pythagorean")
    assert FORMULA_ID_PATTERN.match("formula.trig.sine-addition")
    for bad in ("Formula.x", "formula.", "formula.X", "ptype.x", "formula. x"):
        with pytest.raises(ValidationError):
            _valid(formula_id=bad)


def test_required_fields_nonempty() -> None:
    """name_ko·family·latex·dsl은 비어있으면 거부(min_length=1)."""
    for field in ("name_ko", "family", "latex", "dsl"):
        with pytest.raises(ValidationError):
            _valid(**{field: ""})


def test_extra_forbidden() -> None:
    """extra='forbid' — 미정의 키(변형 열거 등) 유입 차단."""
    with pytest.raises(ValidationError):
        _valid(equivalence_class="e1")  # canonical-only 위반 필드
