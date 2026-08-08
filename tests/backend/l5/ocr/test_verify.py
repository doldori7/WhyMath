"""`parse_check_latex`·`demote_confidence_if_unparseable` 단위테스트 — SymPy 왕복(LLM 0).

검증: 파싱 가능 LaTeX는 ok=True, 깨진 LaTeX는 ok=False, 신뢰도 강등 동작.
"""

from __future__ import annotations

import logging

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


def test_antlr_path_failure_logs_exception_type(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """antlr 파서 경로가 실패하면 예외 타입명이 로그에 남는다(침묵 실패 금지·CLAUDE.md).

    실 환경 상태(antlr 미설치)에 의존하지 않도록 `parse_latex` 자체를 강제 실패시켜 검증한다
    — 변별력 확인: 타입명이 없는 "실패했다"류 메시지만 찍혔다면 이 테스트는 실패해야 한다.
    """

    def _boom(_text: str) -> None:
        raise RuntimeError("antlr 파서 강제 실패(테스트)")

    monkeypatch.setattr("sympy.parsing.latex.parse_latex", _boom)
    with caplog.at_level(logging.WARNING, logger="whymath.l5.ocr.verify"):
        parse_check_latex("x = 2")
    warnings = [r for r in caplog.records if r.name == "whymath.l5.ocr.verify"]
    assert warnings, "antlr 경로 실패가 로그로 관측돼야 한다"
    assert any("RuntimeError" in r.getMessage() for r in warnings)  # 예외 타입명이 로그에 남음
    # 트레이스백(exc_info)은 의도적으로 미사용 — 파서 예외 메시지에 원문이 섞일 위험 회피.
    assert all(r.exc_info is None for r in warnings)


def test_antlr_not_installed_surfaces_as_import_error(caplog: pytest.LogCaptureFixture) -> None:
    """실측(2026-08): 이 프로젝트 의존성엔 antlr4가 없어 `parse_latex` 호출이 항상 `ImportError`로
    실패한다(영구 열화) — 파싱 자체는 폴백(sympify)으로 성공해야 하고, 실패 원인(ImportError)이
    타입명으로 로그에 남아 "미설치"와 "파싱 실패"를 구분할 수 있어야 한다(요구사항 특별 조항)."""
    with caplog.at_level(logging.WARNING, logger="whymath.l5.ocr.verify"):
        result = parse_check_latex("x = 2")
    assert result.ok is True  # 폴백(sympify)으로 정상 파싱
    warnings = [r for r in caplog.records if r.name == "whymath.l5.ocr.verify"]
    assert warnings, "antlr 미설치가 로그로 관측돼야 한다"
    assert any("ImportError" in r.getMessage() for r in warnings)
