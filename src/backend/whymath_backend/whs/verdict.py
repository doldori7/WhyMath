"""Tier1+2 판정 combiner — WH-S S0 슬라이스 1(설계 §4 판정 규칙·§3 unverified 격리).

설계안(`docs/architecture/03b_wh_s_solver_harness.md`) §4 판정 규칙:
  `최종 통과 = Tier1 통과 AND 모든 단계 Tier2 통과`
이중 체크로 "틀린 과정-맞는 답" 경로의 학습 데이터 유입을 차단한다(R-S2 보상 해킹 차단).

본 모듈은 두 검증기의 결과를 결합한다:
  - **Tier1**(수치 답 검산): `l3/verify_answer.AnswerVerdict`(state: pass/fail/unverifiable).
  - **Tier2**(기호 단계 동치): `l3/verify_solution.SolutionVerificationResult`
    (n_correct/n_incorrect/n_unverifiable·has_incorrect 등).

판정 규칙(§4·§3):
  - **failed**: Tier1 fail(답이 조건 위반) *또는* 어느 단계든 Tier2 incorrect(틀린 과정).
    틀린 과정은 *답이 맞아도* 차단한다(§4 이중 체크의 핵심).
  - **verified**: Tier1 pass *그리고* 모든 단계 correct(incorrect 0·**unverifiable 0**).
    즉 모든 단계가 결정론적으로 검증되고 답도 통과한 경우만 verified다.
  - **unverified**: 그 외(Tier1 unverifiable이거나 일부 단계 unverifiable·단 incorrect는 없음).
    설계 §3의 **격리 등급** — *학습 데이터로 절대 사용하지 않는다*(R-S2 보상 해킹 차단).
    "verify 없는 통과 거부"(§3): 약한 검증으로 통과를 위장하지 않고 격리한다.

정직성: Tier1 단독 pass를 최종 통과로 쓰지 않는다 — 반드시 Tier2(모든 단계 correct)와 결합해야
verified다. 판정 불가(unverifiable)는 pass로 위장하지 않고 unverified로 격리한다(verify_step
정직성 상속).

범위 밖(후속): Tier3(Lean4 형식 검증·증명 문제)·PRM·솔버 루프·저장소 커밋(§4·§9).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from whymath_backend.l3.verify_answer import AnswerVerdict
from whymath_backend.l3.verify_solution import SolutionVerificationResult

__all__ = [
    "WhsGrade",
    "WhsVerdict",
    "final_verdict",
]

WhsGrade = Literal["verified", "unverified", "failed"]
"""WH-S 최종 등급 — verified(학습 채택 가능)·unverified(격리·학습 배제)·failed(오답/틀린 과정)."""


class WhsVerdict(BaseModel):
    """`final_verdict`의 결과 — 최종 등급 + 사유 + 판정 근거 필드.

    `grade`는 3등급 중 하나다. `unverified`는 §3 격리 등급으로 *학습 데이터에서 배제*된다.
    `reason`은 한국어 판정 사유. 근거 필드(`answer_state`·`has_incorrect`·`n_unverifiable_steps`)는
    어떤 신호가 등급을 결정했는지 하류가 알 수 있게 전파한다(감사·디버그).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    grade: WhsGrade = Field(
        description=(
            "최종 등급 — verified(Tier1 pass+전 단계 correct)·"
            "unverified(판정 불가 격리·학습 배제·§3)·failed(답 fail 또는 단계 incorrect)."
        ),
    )
    reason: str = Field(
        description="판정 사유(한국어) — 어떤 규칙(§4)으로 이 등급이 났는지.",
    )
    answer_state: Literal["pass", "fail", "unverifiable"] = Field(
        description="Tier1 답 검산 상태(근거 전파).",
    )
    has_incorrect: bool = Field(
        description="Tier2 단계 중 incorrect가 하나라도 있었는지(틀린 과정 — failed 신호).",
    )
    n_unverifiable_steps: int = Field(
        description="Tier2 단계 중 unverifiable 개수(>0이면 verified 불가·unverified 격리).",
    )


def final_verdict(
    answer: AnswerVerdict,
    steps: SolutionVerificationResult,
) -> WhsVerdict:
    """Tier1(answer) + Tier2(steps) 결합 최종 판정 — 순수·결정론(설계 §4 규칙·§3 격리).

    판정 우선순위(§4):
      1. **failed** — Tier1 답이 `fail`(조건 위반) *또는* 어느 단계든 `incorrect`(틀린 과정).
         틀린 과정은 답이 맞아도 차단한다(이중 체크의 핵심·"틀린 과정-맞는 답" 유입 차단).
      2. **verified** — Tier1 답 `pass` *그리고* 모든 단계 correct(incorrect 0·unverifiable 0).
         결정론적으로 전부 검증되고 답도 통과한 경우만.
      3. **unverified** — 그 외(Tier1 unverifiable이거나 일부 단계 unverifiable·단 incorrect 없음).
         설계 §3 **격리 등급**: *학습 데이터로 절대 사용하지 않는다*(R-S2 보상 해킹 차단).

    정직성(§3 "verify 없는 통과 거부"): Tier1 단독 pass를 최종 통과로 쓰지 않는다 — Tier2 전 단계
    correct가 함께여야 verified다. 판정 불가는 pass로 위장하지 않고 unverified로 격리한다.

    범위 밖(후속): Tier3(증명 문제 + Lean4)·PRM·저장소 커밋(§4·§9).
    """
    answer_state = answer.state
    has_incorrect = steps.has_incorrect
    n_unverifiable_steps = steps.n_unverifiable

    # ① failed — 답 fail 또는 틀린 과정(어느 단계든 incorrect). 답이 맞아도 과정이 틀리면 차단.
    if answer_state == "fail":
        return WhsVerdict(
            grade="failed",
            reason="Tier1 답 검산 실패(조건 위반) — 오답.",
            answer_state=answer_state,
            has_incorrect=has_incorrect,
            n_unverifiable_steps=n_unverifiable_steps,
        )
    if has_incorrect:
        return WhsVerdict(
            grade="failed",
            reason="Tier2 단계 중 incorrect 존재(틀린 과정) — 답 무관 차단(§4 이중 체크).",
            answer_state=answer_state,
            has_incorrect=has_incorrect,
            n_unverifiable_steps=n_unverifiable_steps,
        )

    # ② verified — Tier1 pass AND 모든 단계 correct(incorrect 0·unverifiable 0).
    if answer_state == "pass" and not has_incorrect and n_unverifiable_steps == 0:
        return WhsVerdict(
            grade="verified",
            reason="Tier1 답 통과 + 모든 단계 Tier2 correct — 검증 완료(§4 판정 규칙).",
            answer_state=answer_state,
            has_incorrect=has_incorrect,
            n_unverifiable_steps=n_unverifiable_steps,
        )

    # ③ unverified — 판정 불가(Tier1 unverifiable 또는 일부 단계 unverifiable·incorrect 없음).
    #    §3 격리 등급: 학습 데이터 배제(R-S2). verify 없는 통과를 위장하지 않는다.
    if answer_state == "unverifiable":
        reason = "Tier1 답 검산 판정 불가 — 격리(학습 배제·§3)."
    else:  # answer pass인데 단계에 unverifiable 존재.
        reason = (
            f"Tier1 통과이나 Tier2 단계 {n_unverifiable_steps}개 판정 불가 — "
            "격리(학습 배제·§3·verify 없는 통과 거부)."
        )
    return WhsVerdict(
        grade="unverified",
        reason=reason,
        answer_state=answer_state,
        has_incorrect=has_incorrect,
        n_unverifiable_steps=n_unverifiable_steps,
    )
