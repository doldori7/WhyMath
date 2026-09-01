"""답 형태 계약 — 판정 변별력 + **교수학 금기의 기계화** (EOS-28).

이 파일의 절반은 "형태를 제대로 판정하는가"이고, 나머지 절반은 **"형태 판정이 학생을 다치게
하지 않는가"**다. 후자가 더 중요하다 — 형태 검사는 잘못 붙이면 맞은 답에 오답 표시를 하거나
제출을 막는 기능이 되고, 그건 이 프로젝트가 하지 않기로 한 것이다(CLAUDE.md 교수학 금기).

산문으로 적은 금기는 다음 세션이 모르고 어긴다. 그래서 여기서 코드로 동결한다.
"""

from __future__ import annotations

import inspect

import pytest

from whymath_backend.l3 import verify_answer_form as vaf
from whymath_backend.schema.answer_form import ExpectedForm, FormVerdict, strict_expected_form_of

REDUCED = ExpectedForm.reduced_fraction


# ──────────────────────────────────────────────────────────────────────────
# ① 변별력 — 값이 같은 것들 사이를 실제로 가르는가
# ──────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize(
    ("submitted", "expected"),
    [
        ("1/36", FormVerdict.satisfied),
        ("2/72", FormVerdict.violated),  # 값은 1/36과 같다 — 형태만 다르다
        ("5/180", FormVerdict.violated),  # 동상
        ("6/8", FormVerdict.violated),
        ("3", FormVerdict.satisfied),  # 정수는 이미 기약(gcd(3,1)=1)
        ("-2/72", FormVerdict.violated),  # 부호가 판정을 흐리지 않는다
        ("-1/36", FormVerdict.satisfied),
        ("1 / 36", FormVerdict.satisfied),  # 공백은 형태 위반이 아니다
    ],
)
def test_reduced_fraction_discriminates(submitted: str, expected: FormVerdict) -> None:
    """`1/36`과 `2/72`는 **값이 같다**. 이 판정이 둘을 가르지 못하면 존재 이유가 없다."""
    assert vaf.verify_answer_form(submitted, REDUCED) is expected


def test_decimal_is_not_a_fraction() -> None:
    """소수 표기는 분수 표기가 아니다 — 이 검사가 없으면 `0.5`가 gcd 검사를 통과한다.

    `fraction(0.5)`가 `(0.5, 1)`을 주므로 분모 1이 되어 정수와 구별되지 않는다. 타입으로
    먼저 가르지 않으면 소수가 조용히 `satisfied`가 된다(실측으로 확인한 함정).
    """
    assert vaf.verify_answer_form("0.0277777777", REDUCED) is FormVerdict.violated
    assert vaf.verify_answer_form("0.5", REDUCED) is FormVerdict.violated


@pytest.mark.parametrize("submitted", ["x/2", "", "   ", "이건 수식이 아니다", "1/0"])
def test_undecidable_never_becomes_a_violation(submitted: str) -> None:
    """판정 못 한 것을 위반이라 부르면 **맞은 답에 부정 피드백**이 간다.

    빈 제출·문자식·파싱 실패는 전부 `unverifiable`이며 `violated`가 아니다. 이 구분이
    무너지면 학생은 자기가 뭘 잘못했는지 알 수 없는 지적을 받는다.
    """
    assert vaf.verify_answer_form(submitted, REDUCED) is FormVerdict.unverifiable


def test_no_requirement_is_not_satisfaction() -> None:
    """요구 없음 ≠ 지켰음 — 합치면 형태 준수율이 99%로 부풀어 오른다(None-vs-zero)."""
    assert vaf.verify_answer_form("2/72", None) is FormVerdict.not_required
    assert FormVerdict.not_required is not FormVerdict.satisfied


# ──────────────────────────────────────────────────────────────────────────
# ② fail-closed — 저작 오타가 조용히 무시되지 않는가
# ──────────────────────────────────────────────────────────────────────────
def test_unknown_vocabulary_is_unverifiable_not_absent() -> None:
    """제약에 *적혀 있는데* 모르는 어휘면 '요구 없음'이 아니라 판정 불가다.

    `not_required`로 흘리면 저작 오타(`expected_form: "기약분수"`)가 조용히 무시되고,
    형태 검사가 있는 척하면서 아무것도 안 하는 상태가 된다(침묵 실패 금지).
    """
    assert vaf.form_verdict_for("2/72", {"expected_form": "reduced_fractoin"}) is (
        FormVerdict.unverifiable
    )
    form, known = strict_expected_form_of({"expected_form": "reduced_fractoin"})
    assert form is None and known is False


@pytest.mark.parametrize("constraint", [None, {}, {"min": 0}, "문자열", 42])
def test_absent_requirement_reads_as_not_required(constraint: object) -> None:
    """제약이 없거나 형태 키가 없으면 요구 없음 — 여기서 예외를 던지면 채점이 500이 된다."""
    assert vaf.form_verdict_for("2/72", constraint) is FormVerdict.not_required


def test_reads_the_requirement_from_the_constraint() -> None:
    """실제 코퍼스 백필 형태(`answer_constraint.expected_form`)를 읽는다."""
    assert vaf.form_verdict_for("2/72", {"expected_form": "reduced_fraction"}) is (
        FormVerdict.violated
    )
    assert vaf.form_verdict_for("1/36", {"expected_form": "reduced_fraction"}) is (
        FormVerdict.satisfied
    )


# ──────────────────────────────────────────────────────────────────────────
# ③ 교수학 금기의 **구조적** 동결 — 형태가 정오에 스며들 경로가 코드에 없는가
# ──────────────────────────────────────────────────────────────────────────
def test_form_verdict_vocabulary_cannot_express_wrongness() -> None:
    """형태 어휘에 `correct`/`incorrect`가 **없다**.

    값 3상태를 재사용했다면 "형태가 incorrect"라는 문장이 만들어지고, 그 순간 형태 위반이
    오답으로 읽힌다. 어휘 분리가 이 혼동의 1차 방어이므로 어휘 자체를 동결한다.
    """
    values = {v.value for v in FormVerdict}
    assert values == {"satisfied", "violated", "not_required", "unverifiable"}
    assert "correct" not in values and "incorrect" not in values


def test_form_checker_never_sees_the_expected_answer() -> None:
    """형태 판정기는 **정답을 인자로 받지 않는다**.

    받지 않으면 정답이 이 경로로 샐 수 없다(구조적 보장 > 규율). 시그니처를 동결해,
    누군가 "정답도 있으면 편하겠다"며 인자를 추가하면 CI가 먼저 묻게 한다.
    """
    params = list(inspect.signature(vaf.verify_answer_form).parameters)
    assert params == ["student_answer", "expected"]
    for name in ("answer", "expected_answer", "correct_answer", "problem"):
        assert name not in params


def test_form_module_does_not_touch_value_verdicts() -> None:
    """형태 모듈이 값 판정 어휘를 **코드로** 참조하지 않는다 — 두 축의 독립을 모듈 경계로 강제.

    참조가 없으면 이 모듈은 값 판정을 바꿀 수 없다. 규율이 아니라 구조가 막는다.

    **AST로 보는 이유**: 원문 문자열 검사는 docstring의 산문 참조("값 동치는
    `verify_final_answer`가 본다")까지 의존으로 세어 정상 상태에서 실패한다 — 실제로 이
    테스트의 1차 버전이 그렇게 실패했다. 검사 대상은 *설명*이 아니라 *코드*다.
    """
    import ast
    import pathlib

    tree = ast.parse(pathlib.Path(vaf.__file__).read_text(encoding="utf-8"))
    forbidden = {"VerificationOutcome", "verify_final_answer", "verify_answer", "verify_step"}

    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            imported |= {alias.name for alias in node.names}
            if node.module:
                imported.add(node.module.rsplit(".", 1)[-1])
        elif isinstance(node, ast.Import):
            imported |= {alias.name.rsplit(".", 1)[-1] for alias in node.names}
    assert not (imported & forbidden), f"값 판정 심볼을 import한다: {imported & forbidden}"

    referenced = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    referenced |= {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    assert not (referenced & forbidden), f"값 판정 심볼을 참조한다: {referenced & forbidden}"
