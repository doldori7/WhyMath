"""교수학 평가 루브릭 — answer-leakage 탐지기·금기 봉인 회귀 게이트(순수·hermetic).

세 축을 검증한다:
① 탐지기 순수 단위 — leaked(정답 값 노출)·clean(소크라테스 발문)·undecidable(짧음/모호)·수치
   단어경계 오탐 차단·LaTeX/전각 정규화·빈 입력.
② **금기 봉인**(핵심 소비처) — 실제 `wh1_loop._end_turn_utterance`를 억제 verdict(incorrect·
   unverifiable)로 호출한 파생 발화를 표본 정답들에 대해 검사 → **전부 non-leaked** 단언. 정책이
   정답을 발화에 실어도(억제 백스톱) 내용상 정답이 새지 않음을 교차 검증(CLAUDE.md #1 금기).
③ 루브릭 스코어러 — 정답 유출 발화=실패·소크라테스 발화=통과.
"""

from __future__ import annotations

import pytest
from whymath_backend.harness.pedagogical_rubric import (
    LeakageVerdict,
    detect_answer_leakage,
    score_tutoring_response,
)
from whymath_backend.harness.wh1_loop import (
    _ANSWER_SUPPRESSED_VERDICTS,
    EndTurnAction,
    EndTurnType,
    TurnState,
    _end_turn_utterance,
)


class TestDetectAnswerLeakage:
    def test_leaked_plain_answer(self) -> None:
        """정답 값이 그대로 노출되면 leaked."""
        assert detect_answer_leakage("정답은 42야.", "42") is LeakageVerdict.leaked

    def test_clean_socratic(self) -> None:
        """정답 미노출 소크라테스 발화는 clean."""
        assert (
            detect_answer_leakage("어떤 근거로 그렇게 계산했는지 말해줄래?", "42")
            is LeakageVerdict.clean
        )

    def test_numeric_word_boundary_no_false_positive(self) -> None:
        """수치 정답 '13'은 '130'·'413'·'13.5'에 오탐되지 않는다(단어 경계)."""
        verdict = detect_answer_leakage("130과 413, 그리고 13.5를 보자.", "13")
        assert verdict is LeakageVerdict.clean

    def test_numeric_multichar_boundary(self) -> None:
        """'13'은 독립 등장할 때만 leaked."""
        assert detect_answer_leakage("남은 값은 13이다.", "13") is LeakageVerdict.leaked

    def test_latex_and_fullwidth_normalized(self) -> None:
        """LaTeX 마크업·전각 숫자를 정규화해 값으로 비교한다."""
        # 응답의 전각 '４２' → NFKC로 '42', 정답 '42'와 일치.
        assert detect_answer_leakage("답: ４２", "42") is LeakageVerdict.leaked
        # LaTeX 마크업 제거 후 'x=7' 값 노출.
        assert detect_answer_leakage(r"따라서 $x = 7$ 이다.", "x=7") is LeakageVerdict.leaked

    def test_short_answer_undecidable(self) -> None:
        """≤1자 정답은 오탐 위험이 커 undecidable(보수)."""
        assert detect_answer_leakage("정답은 3이야.", "3") is LeakageVerdict.undecidable

    def test_ambiguous_token_undecidable(self) -> None:
        """흔한 토큰('참')은 우연 일치가 잦아 undecidable."""
        verdict = detect_answer_leakage("이 명제가 참인지 살펴보자.", "참")
        assert verdict is LeakageVerdict.undecidable

    def test_empty_answer_undecidable(self) -> None:
        assert detect_answer_leakage("무엇이든 말해봐", "") is LeakageVerdict.undecidable


# 억제 verdict에서 파생 발화가 절대 담지 말아야 할 표본 정답들(수치·식·다자리).
_SAMPLE_ANSWERS: tuple[str, ...] = ("42", "13", "x=7", "3.14", "100")
# 파생 경로를 모두 훑는 end_turn 유형(정책 명시 발화는 억제되어 무시됨).
_END_TURN_TYPES: tuple[EndTurnType, ...] = ("질문", "힌트", "출제", "격려")


def _state(verdict: str) -> TurnState:
    """억제 verdict를 실은 최소 TurnState — 가설·probe 없음(중립 파생 경로)."""
    state = TurnState(turn_index=0, has_solution_steps=False, hypotheses=[])
    state.last_verdict = verdict  # type: ignore[assignment]  # 3-state 문자열 주입
    return state


class TestTabooSeal:
    """CLAUDE.md #1 금기 봉인 — 억제 백스톱 파생 발화는 정답을 내용상으로도 흘리지 않는다."""

    @pytest.mark.parametrize("verdict", _ANSWER_SUPPRESSED_VERDICTS)
    @pytest.mark.parametrize("action_type", _END_TURN_TYPES)
    @pytest.mark.parametrize("answer", _SAMPLE_ANSWERS)
    def test_suppressed_derived_utterance_never_leaks(
        self, verdict: str, action_type: EndTurnType, answer: str
    ) -> None:
        """억제 verdict에서 정책이 정답을 발화에 실어도 파생 발화는 non-leaked여야 한다."""
        action = EndTurnAction(action_type=action_type, utterance=f"정답은 {answer}야.")
        utterance = _end_turn_utterance(_state(verdict), action)
        # 파생 발화(소크라테스 개입·출제·중립)는 정책 명시 발화를 버리므로 정답이 새지 않는다.
        assert detect_answer_leakage(utterance, answer) is not LeakageVerdict.leaked

    def test_correct_verdict_passes_through(self) -> None:
        """대조군 — correct 턴은 억제 안 함(정책 명시 발화 존중)이라 값이 그대로 나온다."""
        state = TurnState(turn_index=0, has_solution_steps=False, hypotheses=[])
        state.last_verdict = "correct"
        action = EndTurnAction(action_type="격려", utterance="정답은 42야.")
        assert _end_turn_utterance(state, action) == "정답은 42야."


class TestScoreTutoringResponse:
    def test_leaked_answer_fails(self) -> None:
        score = score_tutoring_response("정답은 42야.", answer="42")
        assert score.passed is False
        assert score.no_answer_leak is False
        assert score.leakage is LeakageVerdict.leaked

    def test_socratic_clean_passes(self) -> None:
        score = score_tutoring_response("어떤 근거로 그렇게 했는지 말해줄래?", answer="42")
        assert score.passed is True
        assert score.no_answer_leak is True
        assert score.has_socratic_prompt is True

    def test_clean_but_no_socratic_fails(self) -> None:
        """정답은 안 흘렸지만 발문이 없으면 통과 아님(발문 준거 실패)."""
        score = score_tutoring_response("좋아, 다음으로 가보자.", answer="42")
        assert score.no_answer_leak is True
        assert score.has_socratic_prompt is False
        assert score.passed is False

    def test_undecidable_passes_conservatively(self) -> None:
        """짧은 정답으로 유출 판정 불가여도 발문이 있으면 보수적으로 통과."""
        score = score_tutoring_response("무엇을 근거로 그렇게 했을까?", answer="3")
        assert score.leakage is LeakageVerdict.undecidable
        assert score.no_answer_leak is True
        assert score.passed is True
