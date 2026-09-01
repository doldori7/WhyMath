"""MathSubjectAdapter — `SubjectAdapter` 계약의 수학 구현 (EOS-66 v1 · EOS-69 v2).

**이 모듈은 수학 로직을 한 줄도 새로 쓰지 않는다.** 전부 기존 함수 위임이다(계획서 006 §43
"전면 재작성 금지"). 하는 일은 두 가지뿐:

1. Core 중립 봉투(`schema.subject_adapter`) ↔ L3/L4 수학 타입의 **변환**
2. 수학 판정 함수로의 **디스패치**

위임 대상 6건 (v1 3건 + EOS-69 3건):

| 계약 메서드 | 위임 대상 | 모듈 |
|---|---|---|
| `evaluate_answer` | `verify_answer()` | `l3/verify_answer.py` |
| `evaluate_final_answer` | `verify_final_answer()` | `l3/verify_final_answer.py` |
| `check_equivalence_claim` | `identity_status()` | `l3/symbolic_equivalence.py` |
| `check_content_seal` | `extract_equation()`+`classify_invariance_failure()` | `l3/equivalent/` |
| `detect_misconception` | `diagnose()` | `l4/misconception/diagnose.py` |
| `validate_problem` | `Verifier.verify()` | `l3/verifier.py` |

**상태 매핑은 전부 1:1이거나 "모름끼리만 접는다"** — 3상태 계약이 이 파일의 변환 지점에서
접히지 않게 하는 것이 위임의 전부다(각 매핑 상수의 docstring이 그 근거를 적는다).

## 경계상의 위치

`docs/architecture/eos_core_adapter_boundary.md`의 배정에서 이 모듈은 **ADAPTER**다 — CORE인
`l4` 안에 살지만 배정은 파일 단위로 갈린다(선례: `l4.misconception.wrong_form_match`).
`BOUNDARY_MAP`에 그렇게 등재돼 있으므로, CORE 모듈이 이 파일을 import하면 EOS-67 계약이
위반으로 잡는다 — **그것이 의도다**. Core는 `schema.subject_adapter.SubjectAdapter`(Protocol)만
알아야 하고, 이 구현체는 조립 지점(DI)에서만 주입돼야 한다.

`l4`에 두는 이유: 계약상 `l3`(수학 검증)와 `l4.misconception`(오개념) 양쪽을 불러야 하는데,
7계층 단방향 계약에서 그 둘을 동시에 볼 수 있는 가장 낮은 자리가 `l4`다. 물리적
`subjects/math/` 이전은 전환 선언 §1.3-③이 보류한 범위라 여기서 하지 않는다.

## 집행 — 경유 배선 완료(EOS-69)

EOS-66 시점에는 "이 어댑터를 경유하는 서빙 코드 경로가 0개"였다. `EOS-69`가 그 경로를 깔았다:
`api.coach`·`l3.render.adapters`·`l3.pedagogy.slot_generator`·`l6.blueprint.assembly`가 이제
수학 모듈을 직접 import하지 않는다(계약 목록은 `schema/subject_adapter.py` 모듈 docstring).

호출부는 이 클래스를 이름으로 알지 못한다 — 구현체는 조립 지점
`whymath_backend.subject_registry`가 심고, Core는 Protocol만 본다.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Mapping, Sequence

from whymath_backend.l3.equivalent.rephrase import classify_invariance_failure, extract_equation
from whymath_backend.l3.symbolic_equivalence import IdentityVerdict, identity_status
from whymath_backend.l3.verifier import ProblemVerifyInput, Verifier
from whymath_backend.l3.verify_answer import verify_answer
from whymath_backend.l3.verify_final_answer import FinalAnswerState, verify_final_answer
from whymath_backend.l4.misconception.diagnose import diagnose
from whymath_backend.schema.subject_adapter import (
    AnswerEvaluation,
    ContentSealBreach,
    MisconceptionSignal,
    ProblemAnswerKeyView,
    ProblemStatement,
    ProblemValidation,
    SubjectAdapter,
    VerificationState,
)

_MACHINE_AXIS_NUMERIC = "numeric_substitution"
"""`verify_answer`가 닫는 축 이름 — 수치 대입 검산(Tier1).

Tier1은 *샘플 점에서의 만족*이지 증명이 아니다(`verify_answer` docstring 자인). 축 이름을
남기는 이유는 "무엇을 근거로 pass인가"가 판정과 함께 흘러야 하기 때문이다.
"""

_MACHINE_AXIS_ANSWER_KEY = "answer_key_equivalence"
"""`verify_final_answer`가 닫는 축 이름 — 학생 최종답 ↔ 기대정답 값/식 동치.

`numeric_substitution`(조건 대입)과 **다른 축**이다. 같은 이름을 쓰면 "무엇을 근거로 통과인가"
가 뭉개진다 — 조건을 만족했다는 것과 정답 키와 같다는 것은 서로를 함의하지 않는다.
"""

_MACHINE_AXIS_CLAIM_IDENTITY = "symbolic_identity"
"""`identity_status`가 닫는 축 이름 — 두 표현의 기호적 항등성.

`identity`(항등 확정)일 때만 축을 닫았다고 말한다. undecidable/parse_error는 축을 못 닫은
것이지 반증한 것이 아니므로 `unverifiable`로 간다(아래 `_CLAIM_STATE` 참조).
"""

_CLAIM_STATE: dict[IdentityVerdict, VerificationState] = {
    IdentityVerdict.identity: "pass",
    IdentityVerdict.not_identity: "fail",
    IdentityVerdict.undecidable: "unverifiable",
    IdentityVerdict.parse_error: "unverifiable",
}
"""`identity_status`의 4상태 → 계약 3상태 매핑 — **접히는 것은 두 종류의 '모름'뿐이다**.

`undecidable`(증명도 반증도 못 함)과 `parse_error`(읽지도 못함)는 사유는 다르지만 Core가 할
일은 같다 — 확언하지 않는 것. 반면 `not_identity`(반증 확정)를 `unverifiable`로 접거나 그
반대로 접으면 3상태 계약이 무너진다. 그 두 칸은 절대 섞지 않는다.
"""

_FINAL_ANSWER_STATE: dict[FinalAnswerState, VerificationState] = {
    FinalAnswerState.correct: "pass",
    FinalAnswerState.incorrect: "fail",
    FinalAnswerState.unverifiable: "unverifiable",
}
"""`verify_final_answer`의 3상태 → 계약 3상태 — 어휘만 바뀌고 칸은 1:1이다(접힘 0)."""


class MathSubjectAdapter:
    """`SubjectAdapter` Protocol의 수학 구현 — 위임 전용.

    `Verifier`를 주입할 수 있다(교차검증기 결선 등 호출측 결정). 주입하지 않으면 기본
    `Verifier()`를 쓴다 — 그 경우 잔여 축은 교차검증 없이 `unverifiable`로 회피된다
    (보수적·거짓 pass 금지).
    """

    subject_id = "math"

    def __init__(self, *, verifier: Verifier | None = None) -> None:
        self._verifier = verifier if verifier is not None else Verifier()

    def evaluate_answer(
        self, problem: ProblemStatement, answer: Mapping[str, str]
    ) -> AnswerEvaluation:
        """`l3.verify_answer.verify_answer`에 위임하고 3상태를 그대로 옮긴다.

        상태를 재해석하지 않는다 — 특히 `unverifiable`을 `fail`로 접지 않는다(측정 실패를
        오답으로 위장 금지). `checked_axes`는 pass일 때만 채운다: fail·unverifiable에서
        "축을 닫았다"고 말하면 거짓이 된다.
        """
        verdict = verify_answer(problem.conditions, answer)
        return AnswerEvaluation(
            state=verdict.state,
            reason=verdict.reason,
            checked_axes=(_MACHINE_AXIS_NUMERIC,) if verdict.state == "pass" else (),
        )

    def evaluate_final_answer(
        self, problem: ProblemAnswerKeyView, student_answer: str | None
    ) -> AnswerEvaluation:
        """`l3.verify_final_answer.verify_final_answer`에 위임하고 3상태를 1:1로 옮긴다 (EOS-69).

        문항은 뷰 그대로 넘긴다 — `ProblemAnswerKeyView`(계약)와 `ProblemAnswerView`(L3 내부)는
        같은 5필드를 요구하는 구조적 Protocol이라 변환할 것이 없다. **변환이 없다는 게 요점**
        이다: 값을 복사하면 정답 사본이 하나 늘고, 필드를 빠뜨리면 객관식·복수정답 경로가
        조용히 죽는다(둘 다 이 자리에서 일어나기 쉬운 사고다).

        **정답 비노출 승계**: `verify_final_answer`는 상태와 사유만 돌려주고 사유에 기대정답을
        싣지 않는다(그쪽 모듈 docstring의 계약). 이 메서드는 그 사유를 *그대로* 옮길 뿐 새
        문자열을 만들지 않으므로 계약이 그대로 승계된다 — 여기서 문항 정보를 덧붙이면 그
        순간 계약이 깨진다.

        `checked_axes`는 pass일 때만 채운다(fail·unverifiable에서 "축을 닫았다"고 말하면 거짓).
        """
        result = verify_final_answer(student_answer, problem)
        state = _FINAL_ANSWER_STATE[result.state]
        return AnswerEvaluation(
            state=state,
            reason=result.reason,
            checked_axes=(_MACHINE_AXIS_ANSWER_KEY,) if state == "pass" else (),
        )

    def check_equivalence_claim(self, left: str, right: str) -> AnswerEvaluation:
        """`l3.symbolic_equivalence.identity_status`(동치 판정 단일 권위)에 위임한다 (EOS-69).

        4상태(identity/not_identity/undecidable/parse_error)를 계약 3상태로 옮기되, 접는 것은
        *두 종류의 모름*뿐이다(`_CLAIM_STATE` docstring). 새 SymPy 로직은 한 줄도 만들지
        않는다 — 동치 판정 권위는 SymPy 단일이라는 규약이 여기서도 그대로다.

        `reason`은 판정 verdict 이름을 그대로 남긴다(진단용·과목 어휘). 사람 문장을 새로
        지어내면 taxonomy가 둘이 된다.
        """
        verdict = identity_status(left, right)
        state = _CLAIM_STATE[verdict]
        return AnswerEvaluation(
            state=state,
            reason=None if state == "pass" else verdict.value,
            checked_axes=(_MACHINE_AXIS_CLAIM_IDENTITY,) if state == "pass" else (),
        )

    def check_content_seal(
        self, source_text: str, derived_texts: Sequence[str]
    ) -> ContentSealBreach | None:
        """원문 수식이 파생 텍스트에서 바이트 그대로 살아남았는지 판정한다 — 통과면 None (EOS-69).

        위임 대상 2개(`extract_equation`으로 봉인 대상 추출 → `classify_invariance_failure`로
        위반 분류)는 rephrase 게이트의 단일 진실 원천이며, 여기서 판정 로직을 재구현하지 않는다.

        **캐리어 선별이 어댑터에 있는 이유**: "어느 파생 조각이 이 수식을 실었는가"를 고르려면
        `equation in text` 또는 `"=" in text` 같은 *수학 표기 지식*이 필요하다. Core가 이
        조건을 들고 있으면 Core가 등호를 아는 것이다 — 그래서 조건은 이쪽에 있고, Core는
        "본문이 흘러들 수 있는 조각"만 골라 넘긴다(그건 Core의 세그먼트 지식이다).

        원문에서 수식을 못 찾으면 검사 대상이 아니라 None(통과)이다 — 봉인할 것이 없는 텍스트를
        위반으로 만들지 않는다.
        """
        equation = extract_equation(source_text)
        if equation is None:
            return None  # 봉인 대상 부재 — 검사 대상이 아니다(위반 아님).
        for index, text in enumerate(derived_texts):
            if equation not in text and "=" not in text:
                continue  # 이 조각은 수식을 싣지 않았다 — 봉인 검사 대상 밖.
            reason = classify_invariance_failure(text, equation=equation)
            if reason is not None:
                return ContentSealBreach(reason=reason, derived_index=index)
        return None

    def detect_misconception(
        self, student_work: str, *, top_k: int = 3
    ) -> Sequence[MisconceptionSignal]:
        """`l4.misconception.diagnose.diagnose`에 위임하고 식별자·신뢰도만 추린다.

        오개념 *내용*(정의·반례·개입)은 의도적으로 버린다 — Core는 코드만 받고 필요할 때
        reactive 조회한다(구축 플레이북: 오개념 초기 context preload 금지).
        """
        return tuple(
            MisconceptionSignal(
                code=match.misconception.id,
                confidence=match.confidence,
                matched_signals=match.matched_signals + match.matched_regex_signals,
            )
            for match in diagnose(student_work, top_k=top_k)
        )

    async def validate_problem(self, problem: ProblemStatement) -> ProblemValidation:
        """`l3.verifier.Verifier.verify`(통합 수학 검증기 v2)에 위임한다.

        중립 봉투 → `ProblemVerifyInput` 변환이 이 메서드의 실질이다. `tier`·`audit_labels`는
        수학 검증 내부 개념이라 계약으로 넘기지 않는다 — 대신 닫힌 축/잔여 축만 넘긴다.
        """
        verdict = await self._verifier.verify(
            ProblemVerifyInput(
                slug=problem.problem_ref,
                question_text=problem.question_text,
                answer=problem.answer,
                answer_kind=problem.answer_kind,
                conditions=problem.conditions,
            )
        )
        return ProblemValidation(
            state=verdict.state,
            reason=verdict.reason,
            machine_axes=verdict.machine_axes,
            residual_axes=verdict.residual_axes,
        )


if TYPE_CHECKING:
    # 구조적 적합성 증명 — `mypy --strict`(CI backend 잡)가 이 대입을 검사한다.
    # 런타임 `isinstance`(runtime_checkable)는 *메서드 이름 존재*만 보고 시그니처를 보지
    # 않으므로, 인자·반환 타입까지 계약과 맞는지는 이 줄이 유일하게 잡는다.
    # 계약이 바뀌었는데 구현이 안 따라오면 여기서 CI가 적색이 된다.
    _CONFORMANCE_PROOF: SubjectAdapter = MathSubjectAdapter()
