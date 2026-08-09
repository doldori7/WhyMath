"""코치 대화 "완료" 전이 관장 — S3-32 "learning-loop-closure".

지금까지 코치 대화 흐름은 학생이 정답에 도달해도 대화가 "끝났다"는 걸 서버가 판단하는
지점이 없었다. 본 모듈은 L3 `verify_final_answer`(3상태 서버검증)와 기존 Polya 엔진
(`l4/polya/`)의 상태를 *조합*해 "이번 턴으로 코치 대화가 완료되는가"를 결정한다.

**"정답을 빠르게" KPI 금지(CLAUDE.md)**: `correct` 판정이라고 즉시 완료 처리하지 않는다.
Polya 4단계의 마지막 단계 REVIEW(검산·다른 풀이·메타인지·전이)를 *이미 거친 뒤*에만 완료를
허용한다 — 정답에 빨리 도달하는 것 자체가 아니라, 검산·메타인지 회상까지 거친 뒤에야 "다
배웠다"로 본다.

**재구현 금지 — 조합만**: 단계 전이 자체(`should_advance`·`next_polya_stage`)는
`l4/polya/transitions.py`·`l4/models.py`가 이미 담당한다. 이 모듈은 그 결과인
`PolyaState.current_stage`를 *읽기만* 한다 — 전이 로직을 새로 만들지 않는다. "REVIEW를 거친
뒤"의 판정도 새 휴리스틱을 발명하지 않고, 단순히 *이번 턴이 시작되는 시점에 이미
`current_stage`가 REVIEW였는가*로 판단한다: REVIEW는 `l4/models.py`의
`next_polya_stage`에서 자기 자신으로 셀프루프하는 종착 단계라, `state.current_stage is
PolyaStage.REVIEW`가 참이라는 것은 *이전 턴에서* 이미 EXECUTE→REVIEW 전이가 일어나
(`should_advance`가 결정) 학생이 검토 단계 프롬프트를 받았다는 뜻이다. 그 상태에서 이번
턴의 최종답이 correct로 검증되면, 학생은 이미 검산·메타인지 질문을 한 차례 거친 뒤 완료에
도달한 것이다.

**정답 비노출**: `decide_completion`은 `VerifyFinalAnswerState`(3상태, 정답 값 자체를 담지
않음)만 입력받는다 — 이 모듈도 정답 문자열을 다루지 않는다.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from whymath_backend.l3.verify_final_answer import VerifyFinalAnswerState
from whymath_backend.l4.models import PolyaStage, PolyaState

__all__ = [
    "RECONSIDER_PROMPT",
    "CompletionDecision",
    "decide_completion",
]


# incorrect 판정 시 정답을 노출하지 않고 재고를 유도하는 문구 — CLAUDE.md "부정적 피드백을
# 정서적으로 강화하는 표현 금지"(틀렸·못하·잘못된·실수·바보·포기 금지어 미포함, `tone_filter`
# 금지 패턴과 동일 기준) + "학생이 막혔을 때 바로 정답 제공 금지"(정답값 미포함).
RECONSIDER_PROMPT = (
    "음, 지금까지 온 걸 잠깐 다시 짚어보자. 처음 조건으로 돌아가서, 혹시 다르게 볼 수 있는 "
    "부분이 있을까? 어느 단계가 제일 자신 없었는지부터 같이 얘기해볼까?"
)


class CompletionDecision(BaseModel):
    """이번 턴의 완료 판정 결과 — L3 서버검증 3상태 + Polya REVIEW 게이트 조합.

    `completed=True`는 다음 두 조건을 *모두* 만족할 때만 성립한다:
      1. 이번 턴의 서버검증(`verify_state`)이 `correct`.
      2. 이번 턴이 시작되는 시점에 `PolyaState.current_stage`가 이미 `REVIEW`(검토 단계를
         이전 턴에서 이미 거쳤음 — 모듈 docstring).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    completed: bool = Field(
        description=(
            "이번 턴으로 코치 대화가 완료되는지. correct 판정만으로는 True가 되지 않는다 — "
            "REVIEW 단계를 이미 거친 뒤의 correct일 때만 True(모듈 docstring)."
        )
    )
    verify_state: VerifyFinalAnswerState | None = Field(
        default=None,
        description="이번 턴 서버검증 결과(3상태). 검증을 시도하지 않았으면(컨텍스트 없음) None.",
    )
    reconsider_prompt: str | None = Field(
        default=None,
        description=(
            "verify_state=incorrect일 때만 채워지는 정답 미노출 재고 유도 문구. "
            "그 외(correct·unverifiable·미시도)엔 None."
        ),
    )


def decide_completion(
    state: PolyaState, verify_state: VerifyFinalAnswerState | None
) -> CompletionDecision:
    """Polya 상태 + L3 서버검증 3상태 → 완료 판정 조합(순수·LLM 0회·DB 0).

    `verify_state=None`(검증 컨텍스트 없음 — 문항 미연결·정답 데이터 없음·학생 풀이 텍스트
    없음 등, 호출자가 판단)이면 완료 판정을 시도하지 않고 `completed=False`(중립·정직).

    `verify_state=incorrect`면 REVIEW 단계 도달 여부와 무관하게 완료가 아니고,
    `reconsider_prompt`를 채워 호출자(coach.py)가 이번 턴 코칭 발화를 정답 미노출 재고
    유도로 대체할 수 있게 한다.

    `verify_state=correct`면 `state.current_stage is PolyaStage.REVIEW`(이미 REVIEW 단계에
    있었음 — 모듈 docstring)일 때만 `completed=True`. UNDERSTAND/PLAN/EXECUTE 단계에서
    correct가 나와도(예: 학생이 EXECUTE 중 최종 결론을 먼저 던진 경우) *아직* 완료가 아니다
    — 다음 턴에 REVIEW 프롬프트를 먼저 받아야 한다("정답을 빠르게" KPI 금지).

    `verify_state=unverifiable`이면 판정 보류 — completed=False·reconsider_prompt=None
    (틀렸다고 단정하지 않는다·정직).
    """
    if verify_state is None:
        return CompletionDecision(completed=False, verify_state=None, reconsider_prompt=None)

    if verify_state is VerifyFinalAnswerState.incorrect:
        return CompletionDecision(
            completed=False,
            verify_state=verify_state,
            reconsider_prompt=RECONSIDER_PROMPT,
        )

    if verify_state is VerifyFinalAnswerState.correct and state.current_stage is PolyaStage.REVIEW:
        return CompletionDecision(completed=True, verify_state=verify_state, reconsider_prompt=None)

    # correct이지만 아직 REVIEW 미도달 · unverifiable — 완료 아님, 재고 유도도 아님(정직 중립).
    return CompletionDecision(completed=False, verify_state=verify_state, reconsider_prompt=None)
