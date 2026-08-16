"""품질 게이트 테스트 — 수학 정답 FAIL은 전체 FAIL."""

import pytest

from whymath_backend.l3.dsl.models import ValidationReport
from whymath_backend.l3.dsl.quality_gate import QualityGate


def test_quality_gate_pass_when_all_pass() -> None:
    report = ValidationReport(
        syntax="PASS",
        schema_validation="PASS",
        semantic="PASS",
        math="PASS",
        education="PASS",
        duplicate="PASS",
        publishable=True,
    )
    gate = QualityGate()
    result = gate.evaluate(report)
    assert result.publishable is True
    assert result.quality_score == pytest.approx(0.975, abs=0.01)


def test_quality_gate_fail_when_math_fails() -> None:
    report = ValidationReport(
        syntax="PASS",
        schema_validation="PASS",
        semantic="PASS",
        math="FAIL",
        education="PASS",
        duplicate="PASS",
        publishable=True,
    )
    gate = QualityGate()
    result = gate.evaluate(report)
    assert result.publishable is False
    assert result.quality_score == 0.0


def test_quality_gate_unverifiable_math_is_not_pass() -> None:
    report = ValidationReport(
        syntax="PASS",
        schema_validation="PASS",
        semantic="PASS",
        math="UNVERIFIABLE",
        education="PASS",
        duplicate="PASS",
        publishable=True,
    )
    gate = QualityGate()
    result = gate.evaluate(report)
    assert result.publishable is False
    assert result.quality_score == 0.0


def test_quality_gate_requires_score_threshold() -> None:
    # math PASS지만 semantic FAIL로 점수가 낮으면 publishable=False
    report = ValidationReport(
        syntax="PASS",
        schema_validation="PASS",
        semantic="FAIL",
        math="PASS",
        education="PASS",
        duplicate="PASS",
        publishable=True,
    )
    gate = QualityGate()
    result = gate.evaluate(report)
    # 0.25 + 0.20 + 0.00 + 0.135 + 0.09 + 0.10 + 0.05 = 0.825 < 0.95
    assert result.publishable is False
