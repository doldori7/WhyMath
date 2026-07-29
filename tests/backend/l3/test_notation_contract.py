"""SymPy ↔ mathjs 수식 표기 계약 Golden Test (backend·SymPy 측).

`data/notation_contract.json`(공유 fixture)을 읽어 ① canonical 표기(명시 `*`·caret `^`)를
SymPy가 기대 수치로 해석하는지, ② 동치 케이스를 `verify_step`(동치·정오 단일 권위)이 옳게
판정하는지 검증한다. 웹 `notation_contract.test.js`가 *같은 fixture*로 mathjs 측을 검증해, 두
파서가 같은 입력을 같은 수치로 해석함을 교차 보증한다(표기 drift 방지·notation_contract.md).

권위 경계: SymPy = 동치·정오 판정 단일 권위. mathjs = 렌더·수치 평가 전용(동치 판정 미관여).
계약 범위: canonical 형태만(SymPy sympify는 implicit multiplication 미지원이라 명시 `*` 필요).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import sympy
from whymath_backend.l3.verify_step import VerifyStepState, verify_step

# tests/backend/l3/ → parents[3] = 레포 루트(tests/backend/conftest.py의 parents[2]와 동일 기준).
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_FIXTURE = _PROJECT_ROOT / "data" / "notation_contract.json"


def _load_contract() -> dict[str, Any]:
    if not _FIXTURE.exists():  # pragma: no cover - fixture는 레포에 동봉
        pytest.skip(f"표기 계약 fixture 없음: {_FIXTURE}")
    return json.loads(_FIXTURE.read_text(encoding="utf-8"))


_CONTRACT = _load_contract()
_NUMERIC_CASES = _CONTRACT["numeric_cases"]
_EQUIVALENCE_CASES = _CONTRACT["equivalence_cases"]


@pytest.mark.parametrize("case", _NUMERIC_CASES, ids=[c["id"] for c in _NUMERIC_CASES])
def test_sympy_evaluates_contract_notation(case: dict[str, Any]) -> None:
    """canonical 표기(명시 `*`·caret `^`)를 SymPy가 기대 수치로 해석 — mathjs와 동일 입력·값."""
    expr = sympy.sympify(case["expr"], convert_xor=True)
    subs = {sympy.Symbol(name): val for name, val in case["vars"].items()}
    result = float(expr.evalf(subs=subs))
    assert result == pytest.approx(case["value"], abs=case.get("tol", 1e-9))


@pytest.mark.parametrize("case", _EQUIVALENCE_CASES, ids=[c["id"] for c in _EQUIVALENCE_CASES])
def test_verify_step_authority_matches_contract(case: dict[str, Any]) -> None:
    """동치 케이스를 verify_step(동치 권위)이 옳게 판정 — equivalent↔correct / 아니면 incorrect."""
    result = verify_step(case["a"], case["b"])
    expected = VerifyStepState.correct if case["equivalent"] else VerifyStepState.incorrect
    assert result.state == expected, f"{case['id']}: {result.state} (reason={result.reason})"
