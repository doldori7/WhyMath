"""MathSubjectAdapter — `SubjectAdapter` 계약의 수학 구현 (EOS-66 · Math Adapter Contract v1).

**이 모듈은 수학 로직을 한 줄도 새로 쓰지 않는다.** 전부 기존 함수 위임이다(계획서 006 §43
"전면 재작성 금지"). 하는 일은 두 가지뿐:

1. Core 중립 봉투(`schema.subject_adapter`) ↔ L3/L4 수학 타입의 **변환**
2. 수학 판정 함수로의 **디스패치**

위임 대상 3건 (2026-08-31 실측 경로):

| 계약 메서드 | 위임 대상 | 경로 |
|---|---|---|
| `evaluate_answer` | `verify_answer()` | `l3/verify_answer.py:272` |
| `detect_misconception` | `diagnose()` | `l4/misconception/diagnose.py:136` |
| `validate_problem` | `Verifier.verify()` | `l3/verifier.py:300` |

## 경계상의 위치

`docs/architecture/eos_core_adapter_boundary.md`의 배정에서 이 모듈은 **ADAPTER**다 — CORE인
`l4` 안에 살지만 배정은 파일 단위로 갈린다(선례: `l4.misconception.wrong_form_match`).
`BOUNDARY_MAP`에 그렇게 등재돼 있으므로, CORE 모듈이 이 파일을 import하면 EOS-67 계약이
위반으로 잡는다 — **그것이 의도다**. Core는 `schema.subject_adapter.SubjectAdapter`(Protocol)만
알아야 하고, 이 구현체는 조립 지점(DI)에서만 주입돼야 한다.

`l4`에 두는 이유: 계약상 `l3`(수학 검증)와 `l4.misconception`(오개념) 양쪽을 불러야 하는데,
7계층 단방향 계약에서 그 둘을 동시에 볼 수 있는 가장 낮은 자리가 `l4`다. 물리적
`subjects/math/` 이전은 전환 선언 §1.3-③이 보류한 범위라 여기서 하지 않는다.

## ⚠️ 정본화 ≠ 집행

이 어댑터를 **경유하는 서빙 코드 경로는 현재 0개**다. `api.coach` 등 11건은 여전히 수학 검증
함수를 직접 부른다. 그 경유 배선은 후속 태스크이며, 이 파일의 존재는 배선이 아니다.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Mapping, Sequence

from whymath_backend.l3.verifier import ProblemVerifyInput, Verifier
from whymath_backend.l3.verify_answer import verify_answer
from whymath_backend.l4.misconception.diagnose import diagnose
from whymath_backend.schema.subject_adapter import (
    AnswerEvaluation,
    MisconceptionSignal,
    ProblemStatement,
    ProblemValidation,
    SubjectAdapter,
)

_MACHINE_AXIS_NUMERIC = "numeric_substitution"
"""`verify_answer`가 닫는 축 이름 — 수치 대입 검산(Tier1).

Tier1은 *샘플 점에서의 만족*이지 증명이 아니다(`verify_answer` docstring 자인). 축 이름을
남기는 이유는 "무엇을 근거로 pass인가"가 판정과 함께 흘러야 하기 때문이다.
"""


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
