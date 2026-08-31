"""SubjectAdapter 계약 + MathSubjectAdapter 위임 (EOS-66).

이 스위트의 핵심은 동작 테스트가 아니라 **경계 테스트**다(§계약 순수성). 계약이 수학을 알게
되는 순간 EOS 전환은 형식만 남으므로, 그 오염을 기계가 잡게 한다.
"""

from __future__ import annotations

import ast
import inspect
import pathlib
import re

import pytest

from whymath_backend.l4.subject_adapter_math import MathSubjectAdapter
from whymath_backend.schema import subject_adapter as contract
from whymath_backend.schema.subject_adapter import (
    AnswerEvaluation,
    MisconceptionSignal,
    ProblemStatement,
    ProblemValidation,
    SubjectAdapter,
)

# ──────────────────────────────────────────────────────────────────────
# 계약 순수성 — EOS-66 acceptance ④ "수학 전용 개념이 시그니처에 새지 않았는가"
# ──────────────────────────────────────────────────────────────────────

_MATH_LEAK_TOKENS = re.compile(
    r"\b(sympy|Expr|Symbol|latex|LaTeX|ast|AST|equation|polynomial|quadratic|"
    r"derivative|integral|geometry|theorem)\b"
)


def _contract_source() -> str:
    return pathlib.Path(inspect.getfile(contract)).read_text(encoding="utf-8")


def test_contract_imports_no_layer_package() -> None:
    """계약은 `l1`~`l6` 중 어느 것도 import하지 않는다.

    `schema`는 7계층 계약의 최하위다. 계약이 어떤 계층이든 import하는 순간 Core가 Adapter를
    알게 되고, 그러면 이 파일은 경계가 아니라 경계 위반이 된다.
    """
    tree = ast.parse(_contract_source())
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)
        elif isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)

    layer_imports = [name for name in imported if re.match(r"^whymath_backend\.l[1-6](\.|$)", name)]
    assert layer_imports == [], f"계약이 계층 패키지를 import한다: {layer_imports}"


def test_contract_signatures_have_no_math_tokens() -> None:
    """Protocol 메서드의 **시그니처**(인자·반환 타입)에 수학 전용 어휘가 없다.

    docstring은 검사 대상이 아니다 — 설명은 수학을 예로 들 수 있다. 금지되는 것은 *타입*이
    수학을 아는 것이다.
    """
    leaks: list[str] = []
    for name, member in inspect.getmembers(SubjectAdapter, inspect.isfunction):
        if name.startswith("_"):
            continue
        rendered = f"{name}{inspect.signature(member)}"
        found = _MATH_LEAK_TOKENS.findall(rendered)
        if found:
            leaks.append(f"{rendered} → {found}")
    assert leaks == [], f"계약 시그니처에 수학 전용 개념 누출: {leaks}"


def test_contract_exposes_only_the_three_agreed_capabilities() -> None:
    """계약 표면은 3메서드로 동결한다 — 늘어나면 이 테스트가 먼저 막는다.

    `explain`이 없는 것은 누락이 아니라 판정이다(위임할 공개 진입점 0건 — 모듈 docstring).
    추가하려면 "이 능력이 Physics·History에도 반드시 있는가"를 통과해야 하고, 그 판정을
    이 단언 수정과 함께 남기게 한다.
    """
    methods = {
        name
        for name, _ in inspect.getmembers(SubjectAdapter, inspect.isfunction)
        if not name.startswith("_")
    }
    assert methods == {"evaluate_answer", "detect_misconception", "validate_problem"}


def test_math_adapter_satisfies_protocol_at_runtime() -> None:
    adapter = MathSubjectAdapter()
    assert isinstance(adapter, SubjectAdapter)
    assert adapter.subject_id == "math"


# ──────────────────────────────────────────────────────────────────────
# 위임 — 상태를 재해석하지 않는가
# ──────────────────────────────────────────────────────────────────────


def _problem(**kw: str) -> ProblemStatement:
    base = {
        "problem_ref": "problem.math.test.0001",
        "question_text": "x**2 - 5*x + 6 = 0 을 풀어라",
        "answer": "3",
        "answer_kind": "numeric",
        "conditions": "x**2 - 5*x + 6 = 0",
    }
    base.update(kw)
    return ProblemStatement(**base)  # type: ignore[arg-type]


def test_evaluate_answer_pass_records_the_axis_it_closed() -> None:
    result = MathSubjectAdapter().evaluate_answer(_problem(), {"x": "3"})
    assert isinstance(result, AnswerEvaluation)
    assert result.state == "pass"
    # pass일 때만 축을 채운다 — "무엇을 근거로 통과인가"가 판정과 함께 흘러야 한다
    assert result.checked_axes == ("numeric_substitution",)


def test_evaluate_answer_fail_claims_no_closed_axis() -> None:
    result = MathSubjectAdapter().evaluate_answer(_problem(), {"x": "5"})
    assert result.state == "fail"
    assert result.checked_axes == (), "실패인데 축을 닫았다고 말하면 거짓이다"


def test_evaluate_answer_keeps_unverifiable_distinct_from_fail() -> None:
    """측정 실패를 오답으로 접지 않는다 — 이 저장소의 검증 권위 서열이 타입에 걸린 지점."""
    result = MathSubjectAdapter().evaluate_answer(
        _problem(conditions="이것은 수식이 아니라 한국어 문장이다"), {"x": "3"}
    )
    assert result.state == "unverifiable"
    assert result.state != "fail"
    assert result.checked_axes == ()


def test_detect_misconception_returns_empty_rather_than_inventing() -> None:
    signals = MathSubjectAdapter().detect_misconception("")
    assert list(signals) == [], "매칭 0은 정상 응답이다 — 없는 오개념을 지어내지 않는다"


def test_detect_misconception_carries_only_identifier_and_confidence() -> None:
    """오개념 *내용*은 계약을 넘지 않는다 — Core는 코드만 받고 reactive 조회한다."""
    signals = MathSubjectAdapter().detect_misconception("아무 풀이나", top_k=3)
    for signal in signals:
        assert isinstance(signal, MisconceptionSignal)
        assert set(signal.model_dump()) == {"code", "confidence", "matched_signals"}


@pytest.mark.asyncio
async def test_validate_problem_unknown_kind_is_unverifiable_not_fail() -> None:
    result = await MathSubjectAdapter().validate_problem(_problem(answer_kind="등록되지_않은_종류"))
    assert isinstance(result, ProblemValidation)
    assert result.state == "unverifiable"
    assert result.reason is not None
