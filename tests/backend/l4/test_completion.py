"""`l4.completion.decide_completion` 조합 단위테스트 — S3-32 learning-loop-closure.

`decide_completion`은 L3 서버검증 3상태(`VerifyFinalAnswerState`)와 기존 Polya 엔진의
`PolyaState.current_stage`(`l4/polya/transitions.py`가 이미 결정한 값)를 *조합*만 한다 —
전이 로직 자체는 재구현하지 않는다(모듈 docstring). 이 테스트는 그 조합 표를 전수 확인한다.

핵심 계약: "정답을 빠르게" KPI 금지 — `correct` 판정은 `current_stage`가 이미 REVIEW일 때만
완료로 이어진다. UNDERSTAND/PLAN/EXECUTE에서는(REVIEW 단계를 아직 거치지 않았으므로) correct여도
완료가 아니다. 이게 이 태스크의 핵심 규약이라 4단계 전부를 파라미터화해 낱낱이 확인한다.
"""

from __future__ import annotations

import re

import pytest

from whymath_backend.l3.verify_final_answer import VerifyFinalAnswerState
from whymath_backend.l4.completion import RECONSIDER_PROMPT, CompletionDecision, decide_completion
from whymath_backend.l4.models import PolyaStage, PolyaState

# 정답값(숫자·등호 뒤 값) 패턴이 재고 유도 문구에 섞여 있지 않은지 보는 정규식 — "x=42" 같은
# 등식·"답은 3" 류를 넓게 잡는다(재고 유도 문구는 애초에 값을 다루지 않으므로 매치 자체가 없어야
# 정상이다). 순수 자릿수 나열도 없어야 한다(예: "3가지" 같은 우연한 숫자조차 이 문구엔 없다).
_ANSWER_LEAK_PATTERN = re.compile(r"\d")


def _state(stage: PolyaStage) -> PolyaState:
    return PolyaState(current_stage=stage)


class TestNoVerificationContext:
    """verify_state=None(검증 컨텍스트 없음) — 어느 단계든 완료 아님·재고 유도도 없음."""

    @pytest.mark.parametrize("stage", list(PolyaStage))
    def test_none_verify_state_never_completes(self, stage: PolyaStage) -> None:
        decision = decide_completion(_state(stage), None)
        assert decision.completed is False
        assert decision.verify_state is None
        assert decision.reconsider_prompt is None


class TestIncorrect:
    """verify_state=incorrect — 완료 아님 + 정답 미노출 재고 유도 문구."""

    @pytest.mark.parametrize("stage", list(PolyaStage))
    def test_incorrect_never_completes_and_sets_reconsider_prompt(self, stage: PolyaStage) -> None:
        decision = decide_completion(_state(stage), VerifyFinalAnswerState.incorrect)
        assert decision.completed is False
        assert decision.verify_state is VerifyFinalAnswerState.incorrect
        assert decision.reconsider_prompt == RECONSIDER_PROMPT

    def test_reconsider_prompt_does_not_leak_answer(self) -> None:
        # 정답 값(숫자)이 문구에 없어야 한다 — "부정적 피드백 정서 강화 금지" + "정답 미노출".
        assert not _ANSWER_LEAK_PATTERN.search(RECONSIDER_PROMPT)

    def test_reconsider_prompt_has_no_forbidden_emotional_words(self) -> None:
        # CLAUDE.md 정서 안전 금지어(tone_filter 대상과 동일 기준) — 틀렸·못하·잘못된·실수·
        # 바보·포기가 재고 유도 문구에 섞이지 않는지 확인.
        forbidden = ("틀렸", "못하", "잘못된", "실수", "바보", "포기")
        for word in forbidden:
            assert word not in RECONSIDER_PROMPT, word


class TestCorrectRequiresReviewGate:
    """verify_state=correct — "정답을 빠르게" KPI 금지의 핵심 규약(모듈 docstring)."""

    def test_correct_at_review_completes(self) -> None:
        decision = decide_completion(_state(PolyaStage.REVIEW), VerifyFinalAnswerState.correct)
        assert decision.completed is True
        assert decision.verify_state is VerifyFinalAnswerState.correct
        assert decision.reconsider_prompt is None

    @pytest.mark.parametrize("stage", [PolyaStage.UNDERSTAND, PolyaStage.PLAN, PolyaStage.EXECUTE])
    def test_correct_before_review_never_completes(self, stage: PolyaStage) -> None:
        """REVIEW 미도달 상태의 correct는 *아직* 완료가 아니다 — 4단계 전부 낱낱이 확인."""
        decision = decide_completion(_state(stage), VerifyFinalAnswerState.correct)
        assert decision.completed is False, stage
        assert decision.verify_state is VerifyFinalAnswerState.correct
        assert decision.reconsider_prompt is None

    def test_all_four_stages_parametrized_exhaustively(self) -> None:
        """PolyaStage 전체 열거가 정확히 4종이고, REVIEW만 completed=True를 낸다는 것을 재확인.

        위 두 테스트가 개별로 커버하지만, 이 테스트는 "PolyaStage가 늘어나도(예: 5단계로
        확장) 이 계약이 깨지지 않고 드러난다"를 구조적으로 보장한다.
        """
        results = {
            stage: decide_completion(_state(stage), VerifyFinalAnswerState.correct).completed
            for stage in PolyaStage
        }
        assert results == {
            PolyaStage.UNDERSTAND: False,
            PolyaStage.PLAN: False,
            PolyaStage.EXECUTE: False,
            PolyaStage.REVIEW: True,
        }


class TestUnverifiable:
    """verify_state=unverifiable — 완료도 재고 유도도 아니다(단정하지 않는다)."""

    @pytest.mark.parametrize("stage", list(PolyaStage))
    def test_unverifiable_never_completes_and_no_reconsider(self, stage: PolyaStage) -> None:
        decision = decide_completion(_state(stage), VerifyFinalAnswerState.unverifiable)
        assert decision.completed is False
        assert decision.verify_state is VerifyFinalAnswerState.unverifiable
        assert decision.reconsider_prompt is None


class TestCompletionDecisionShape:
    """`CompletionDecision` 자체의 계약 — extra 금지·frozen."""

    def test_extra_field_rejected(self) -> None:
        with pytest.raises(Exception):  # noqa: B017 — pydantic ValidationError
            CompletionDecision(completed=False, bogus=True)  # type: ignore[call-arg]

    def test_frozen(self) -> None:
        decision = decide_completion(_state(PolyaStage.REVIEW), VerifyFinalAnswerState.correct)
        with pytest.raises(Exception):  # noqa: B017 — pydantic ValidationError(frozen)
            decision.completed = False  # type: ignore[misc]
