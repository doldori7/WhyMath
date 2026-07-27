"""formula_graph transform 단위테스트 — 정형화·skip 기록.

hermetic: dict 입력 → 모델 정형화(DB·네트워크 불요).
"""

from __future__ import annotations

from data_pipeline.formula_graph.transform import transform_formulas


def _rec(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "formula_id": "formula.multiplication.square-of-sum",
        "name_ko": "합의 제곱",
        "family": "곱셈공식",
        "latex": "(a+b)^2 = a^2 + 2ab + b^2",
        "dsl": "(a + b)**2 == a**2 + 2*a*b + b**2",
    }
    base.update(overrides)
    return base


def test_transforms_valid_records() -> None:
    """유효 레코드 정형화·provenance 카운트."""
    result = transform_formulas(
        [_rec(), _rec(formula_id="formula.geometry.pythagorean", family="기하공식")]
    )
    assert len(result.formulas) == 2
    assert result.skipped == []
    assert result.provenance["formulas"] == 2
    assert result.provenance["families"] == 2
    assert result.provenance["with_signature"] == 0


def test_invalid_record_skipped_not_dropped() -> None:
    """검증 실패 행은 조용히 누락되지 않고 skip 사유 기록(형식 위반·빈 dsl)."""
    result = transform_formulas(
        [
            _rec(),
            _rec(formula_id="BADID"),  # 형식 위반
            _rec(formula_id="formula.empty", dsl=""),  # 빈 dsl
        ]
    )
    assert len(result.formulas) == 1
    assert len(result.skipped) == 2


def test_with_signature_counted() -> None:
    """canonical_signature가 있는 수식은 provenance with_signature에 집계."""
    result = transform_formulas([_rec(canonical_signature="abc123"), _rec(formula_id="formula.x")])
    assert result.provenance["with_signature"] == 1


def test_with_constraints_and_mnemonic_counted() -> None:
    """S4-06 — constraints/mnemonic 보유 수식이 provenance에 집계(빈 배열·None은 미집계)."""
    result = transform_formulas(
        [
            _rec(constraints=["a ≠ 0"], mnemonic="팁"),
            _rec(formula_id="formula.x", constraints=[]),
        ]
    )
    assert result.provenance["with_constraints"] == 1
    assert result.provenance["with_mnemonic"] == 1
