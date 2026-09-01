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


def test_contract_exposes_only_the_agreed_capabilities() -> None:
    """계약 표면을 동결한다 — 늘어나면 이 테스트가 먼저 막는다.

    v1(EOS-66) 3메서드 → v2(EOS-69) 6메서드. 늘린 3건은 계약 docstring의 추가 기준
    (a) 과목 보편성 (b) 실재 위임 대상 (c) 실재 Core 호출부를 **전부** 통과했고, 그 판정
    근거가 거기 적혀 있다. 여기 단언을 고치는 것이 곧 그 판정을 남기는 행위다.

    `explain`이 여전히 없는 것은 누락이 아니라 판정이다 — 위임할 공개 진입점이 0건이라
    기준 (b)를 통과하지 못한다(넣으면 `NotImplementedError` 좌석만 는다).
    """
    methods = {
        name
        for name, _ in inspect.getmembers(SubjectAdapter, inspect.isfunction)
        if not name.startswith("_")
    }
    assert methods == {
        "evaluate_answer",
        "evaluate_final_answer",
        "check_equivalence_claim",
        "check_content_seal",
        "detect_misconception",
        "validate_problem",
    }
    assert "explain" not in methods, "위임 대상 없는 메서드를 계약에 넣지 않는다(기준 b)"


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


# ──────────────────────────────────────────────────────────────────────
# EOS-69 v2 — 새 3메서드의 위임·3상태 보존·정답 비노출
# ──────────────────────────────────────────────────────────────────────


class _ProblemStub:
    """`ProblemAnswerKeyView`를 구조적으로 만족하는 최소 스텁(ORM 없이 판정 경로를 탄다)."""

    def __init__(
        self,
        *,
        answer: str | None,
        choices: list[str] | None = None,
        multiple_answers: dict[str, object] | None = None,
    ) -> None:
        self.answer = answer
        self.choices = choices
        self.question_format = None
        self.answer_format = None
        self.multiple_answers = multiple_answers


def test_final_answer_correct_maps_to_pass_and_records_its_axis() -> None:
    result = MathSubjectAdapter().evaluate_final_answer(_ProblemStub(answer="3"), "3")
    assert result.state == "pass"
    # 조건 대입 축과 *다른* 축이어야 한다 — 같은 이름을 쓰면 근거가 뭉개진다.
    assert result.checked_axes == ("answer_key_equivalence",)


def test_final_answer_wrong_maps_to_fail_and_claims_no_axis() -> None:
    result = MathSubjectAdapter().evaluate_final_answer(_ProblemStub(answer="3"), "5")
    assert result.state == "fail"
    assert result.checked_axes == ()


def test_final_answer_without_answer_key_is_unverifiable_not_fail() -> None:
    """채점 근거가 없는 것은 '학생이 틀림'이 아니다 — 3상태의 세 번째 칸이 지키는 것."""
    result = MathSubjectAdapter().evaluate_final_answer(_ProblemStub(answer=None), "3")
    assert result.state == "unverifiable"
    assert result.state != "fail"


def test_final_answer_never_echoes_the_expected_answer() -> None:
    """**정답 비노출 동결** — 판정 봉투 어디에도 기대정답이 실리지 않는다.

    이 봉투는 Core를 거쳐 로그·이벤트·응답으로 흐를 수 있다. 어댑터가 사유에 기대정답을
    반향하는 순간 무인증 표면으로 정답이 새는 경로가 생긴다. 오답·검증불가 양쪽을 본다
    (correct는 애초에 reason이 None이라 새어도 안 새는 것처럼 보이기 때문).
    """
    secret = "4242sentinel"
    for student in ("5", "", "판정불가한한국어문장"):
        result = MathSubjectAdapter().evaluate_final_answer(
            _ProblemStub(answer=secret, multiple_answers={"alt": "9999sentinel"}), student
        )
        dumped = repr(result.model_dump())
        assert secret not in dumped, f"기대정답이 판정 봉투로 새어 나왔다: {dumped}"
        assert "9999sentinel" not in dumped, f"복수 정답 후보가 새어 나왔다: {dumped}"


def test_final_answer_multiple_choice_path_survives_the_contract() -> None:
    """선택지·복수정답을 *뷰로* 넘기므로 객관식 경로가 살아 있다(값 복사였다면 죽는 자리).

    `ProblemStatement`(값 봉투)로 옮겨 담았다면 `choices`가 빠져 객관식이 일반 경로로
    떨어졌을 것이다 — 뷰를 택한 이유가 이것이라 그 사실을 동결한다.
    """
    problem = _ProblemStub(answer="2", choices=["1", "2", "3"])
    assert MathSubjectAdapter().evaluate_final_answer(problem, "3").state == "fail"
    assert MathSubjectAdapter().evaluate_final_answer(problem, "2개").state == "pass"


def test_equivalence_claim_true_false_and_undecided_are_three_distinct_states() -> None:
    """4상태 → 3상태 매핑에서 접히는 것은 *두 종류의 모름*뿐임을 동결한다."""
    adapter = MathSubjectAdapter()
    assert adapter.check_equivalence_claim("(2)**2 - 4*(2) + 3", "-1").state == "pass"
    assert adapter.check_equivalence_claim("1", "2").state == "fail"
    # 파싱 불가 — 반증이 아니라 판정 불가. fail로 접으면 "읽지 못함"이 "틀림"이 된다.
    assert adapter.check_equivalence_claim("", "1").state == "unverifiable"
    assert adapter.check_equivalence_claim("$$$", "1").state == "unverifiable"
    # 미결정(undecidable) — *읽기는 했는데* 증명도 반증도 못 한 경우. parse_error와 사유가
    # 다르므로 별도 사례가 필요하다: 앞의 두 줄만으로는 undecidable→fail 결함을 못 잡는다
    # (뮤테이션 M1 실측 — 앵커를 parse_error로만 잡아 두면 검사에 변별력이 없다).
    assert adapter.check_equivalence_claim("sqrt(x**2)", "x").state == "unverifiable"
    assert adapter.check_equivalence_claim("a", "b + 1").state == "unverifiable"


def test_equivalence_claim_pass_records_axis_and_hides_no_verdict_name() -> None:
    adapter = MathSubjectAdapter()
    passed = adapter.check_equivalence_claim("2*x", "x + x")
    assert passed.state == "pass"
    assert passed.checked_axes == ("symbolic_identity",)
    assert passed.reason is None
    failed = adapter.check_equivalence_claim("1", "2")
    assert failed.reason == "not_identity", "사유는 판정 taxonomy를 그대로 옮긴다(새 문장 금지)"


def test_content_seal_passes_when_there_is_nothing_to_seal() -> None:
    """봉인 대상이 없는 원문은 검사 대상이 아니다 — 위반으로 만들지 않는다."""
    assert MathSubjectAdapter().check_content_seal("수식이 없는 설명 문장", ["아무 텍스트"]) is None


def test_content_seal_detects_alteration_and_points_at_the_offending_text() -> None:
    source = "이차방정식 3x^2 - 7x + 4 = 0 을 풀어라."
    intact = "3x^2 - 7x + 4 = 0 을 생각해 봅시다."
    altered = "3x^2 - 7x + 5 = 0 을 생각해 봅시다."
    breach = MathSubjectAdapter().check_content_seal(source, [intact, altered])
    assert breach is not None
    assert breach.reason == "EQUATION_ALTERED"
    # 인덱스는 호출자가 넘긴 순서 그대로여야 한다(호출자가 자기 어휘로 되짚는 유일한 실마리).
    assert breach.derived_index == 1


def test_content_seal_ignores_texts_that_do_not_carry_the_notation() -> None:
    """표기를 싣지 않은 조각은 검사 대상 밖 — 있지도 않은 훼손을 만들지 않는다."""
    source = "이차방정식 3x^2 - 7x + 4 = 0 을 풀어라."
    breach = MathSubjectAdapter().check_content_seal(source, ["제목", "3x^2 - 7x + 4 = 0"])
    assert breach is None
