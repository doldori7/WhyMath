"""`parse_check_latex`·`demote_confidence_if_unparseable` 단위테스트 — SymPy 왕복(LLM 0).

검증: 파싱 가능 LaTeX는 ok=True, 깨진 LaTeX는 ok=False, 신뢰도 강등 동작.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError
from whymath_backend.l5.ocr.verify import (
    demote_confidence_if_unparseable,
    parse_check_latex,
)


@pytest.mark.parametrize(
    "latex",
    [
        "x = 2",
        "x^2 + 2*x + 1",
        "x + y = 3",
        "\\frac{1}{2}",
        "\\sqrt{x}",
        "1 + 1",
    ],
)
def test_parseable_latex_ok(latex: str) -> None:
    """파싱 가능한 LaTeX는 ok=True."""
    result = parse_check_latex(latex)
    assert result.ok is True
    assert result.reason is None


@pytest.mark.parametrize(
    "latex",
    [
        "",
        "   ",
        "x ++ )( ==",
        "= = =",
    ],
)
def test_unparseable_latex_not_ok(latex: str) -> None:
    """빈 문자열·깨진 LaTeX는 ok=False + 사유."""
    result = parse_check_latex(latex)
    assert result.ok is False
    assert result.reason is not None


def test_equation_both_sides_checked() -> None:
    """등식은 양변을 각각 파싱해 둘 다 되면 ok."""
    assert parse_check_latex("2*x + 1 = 5").ok is True


def test_equation_broken_side_not_ok() -> None:
    """등식 한 변이 깨지면 ok=False."""
    assert parse_check_latex("x = )(+ +").ok is False


def test_demote_keeps_confidence_when_parseable() -> None:
    """파싱되면 신뢰도 원값 유지."""
    assert demote_confidence_if_unparseable("x = 2", 0.9) == 0.9


def test_demote_lowers_confidence_when_unparseable() -> None:
    """파싱 불가면 신뢰도 강등(원값보다 낮음)."""
    demoted = demote_confidence_if_unparseable("x ++ )( ==", 1.0)
    assert demoted < 1.0
    assert demoted >= 0.0


def test_demote_clamps_to_unit_interval() -> None:
    """강등 결과는 0~1로 클램프된다."""
    demoted = demote_confidence_if_unparseable("broken )(", 0.4)
    assert 0.0 <= demoted <= 1.0


def test_result_is_frozen() -> None:
    """LatexParseResult는 frozen(불변·결정론 결과 보호)."""
    result = parse_check_latex("x = 1")
    with pytest.raises(ValidationError):
        result.ok = False  # type: ignore[misc]
