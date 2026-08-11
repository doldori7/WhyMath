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
from sympy.parsing.sympy_parser import parse_expr

from whymath_backend.l3.symbolic_equivalence import (
    _PARSE_TRANSFORMS,
    latex_to_plain,
    to_sympy_source,
)
from whymath_backend.l3.verify_step import VerifyStepState, verify_step

# tests/backend/l3/ → parents[3] = 레포 루트(tests/backend/conftest.py의 parents[2]와 동일 기준).
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_FIXTURE = _PROJECT_ROOT / "data" / "notation_contract.json"


def _load_contract() -> dict[str, Any]:
    """계약 fixture 로드 — 부재는 **skip이 아니라 실패**다(MATH-01 ③).

    이전에는 `pytest.skip`으로 흡수했다. 그건 fixture가 사라져도 스위트가 green으로 보인다는
    뜻이고(모듈 스코프 호출이라 *전체 모듈*이 조용히 사라진다), 계약 골든의 존재 이유를 정면으로
    거스른다 — "성공/실패 양쪽에서 같은 값을 내는 검사는 검증이 아니라 위장"(CLAUDE.md).
    Dart(`segmentation_contract_test.dart`)·JS(`notation_contract.test.js`)가 이미 부재를 실패로
    다루므로 3자 규칙을 여기서도 맞춘다.
    """
    if not _FIXTURE.exists():
        raise AssertionError(
            f"표기 계약 fixture를 찾지 못했습니다: {_FIXTURE} — "
            "레포에 동봉된 파일이라 부재는 계약 파손이다(skip 아님)."
        )
    return json.loads(_FIXTURE.read_text(encoding="utf-8"))


_CONTRACT = _load_contract()
_NUMERIC_CASES = _CONTRACT["numeric_cases"]
_EQUIVALENCE_CASES = _CONTRACT["equivalence_cases"]
_LATEX_CASES = _CONTRACT["latex_cases"]
# 수치 검증 대상 — `value`를 가진 케이스만. 관계식·미해석 매크로 케이스는 단일 수치로 평가되지
# 않으므로 제외한다(케이스별 분기가 아니라 "수치 필드 유무" 한 가지 규칙).
_NUMERIC_LATEX_CASES = [c for c in _LATEX_CASES if "value" in c]


@pytest.mark.parametrize("case", _NUMERIC_CASES, ids=[c["id"] for c in _NUMERIC_CASES])
def test_sympy_evaluates_contract_notation(case: dict[str, Any]) -> None:
    """canonical 표기(명시 `*`·caret `^`)를 SymPy가 기대 수치로 해석 — mathjs와 동일 입력·값."""
    expr = sympy.sympify(case["expr"], convert_xor=True)
    subs = {sympy.Symbol(name): val for name, val in case["vars"].items()}
    result = float(expr.evalf(subs=subs))
    assert result == pytest.approx(case["value"], abs=case.get("tol", 1e-9))


@pytest.mark.parametrize("case", _LATEX_CASES, ids=[c["id"] for c in _LATEX_CASES])
def test_latex_to_plain_matches_contract(case: dict[str, Any]) -> None:
    """LaTeX→평문 산출이 계약 `plain`과 **문자열 일치** — 모바일 Dart 미러가 같은 fixture를 읽는다.

    이 단언이 py↔dart 규칙 드리프트를 동결한다(MATH-01 ③). 웹은 렌더 전용이라 문자열이 아니라
    수치로 같은 fixture를 검증한다(`notation_contract.test.js`).
    """
    assert latex_to_plain(case["latex"]) == case["plain"], case["id"]


@pytest.mark.parametrize("case", _NUMERIC_LATEX_CASES, ids=[c["id"] for c in _NUMERIC_LATEX_CASES])
def test_numeric_latex_case_plain_evaluates_to_contract_value(case: dict[str, Any]) -> None:
    """수치 필드를 가진 케이스는 `plain`이 **실제로 그 값으로 평가**돼야 한다 — 웹과 같은 값.

    문자열 일치만 보면 계약이 *쓸모없는 산출*을 동결할 수 있다(예: 파싱 안 되는 문자열).
    수치 케이스에 한해 상류 파싱 경로(`to_sympy_source` + 암묵곱·caret 변환)를 그대로 태워
    계약의 `value`와 대조한다 — 웹은 자신의 `latexToMath` 산출을 같은 `value`와 대조하므로,
    이 두 단언이 만나 **py의 문자열 산출과 js의 렌더 산출이 같은 수를 뜻함**을 보증한다.

    수치 필드가 없는 케이스는 제외한다 — 그것들은 관계식(`x <= 5`)이거나 미해석 매크로가
    의도적으로 남는 케이스(`a \\rightarrow b`)라 단일 수치로 평가되지 않는다. 케이스별 분기
    없이 "수치 필드 유무"라는 한 가지 규칙으로 나눈다(계약에 조건 분기 금지 — MATH-01 ⑥-c).
    """
    expr = parse_expr(to_sympy_source(case["plain"]), transformations=_PARSE_TRANSFORMS)
    subs = {sympy.Symbol(name): val for name, val in case["vars"].items()}
    result = float(expr.evalf(subs=subs))
    assert result == pytest.approx(case["value"], abs=case.get("tol", 1e-9)), case["id"]


@pytest.mark.parametrize("case", _EQUIVALENCE_CASES, ids=[c["id"] for c in _EQUIVALENCE_CASES])
def test_verify_step_authority_matches_contract(case: dict[str, Any]) -> None:
    """동치 케이스를 verify_step(동치 권위)이 옳게 판정 — equivalent↔correct / 아니면 incorrect."""
    result = verify_step(case["a"], case["b"])
    expected = VerifyStepState.correct if case["equivalent"] else VerifyStepState.incorrect
    assert result.state == expected, f"{case['id']}: {result.state} (reason={result.reason})"
