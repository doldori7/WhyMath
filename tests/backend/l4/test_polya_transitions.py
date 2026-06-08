"""L4 단계 전이 휴리스틱 단위테스트.

핵심: false-positive(잘못 next) 제로 — 모호 시 항상 stay(생산적 막힘 우선).
"""

from __future__ import annotations

from whymath_backend.l4.models import PolyaStage, PolyaState
from whymath_backend.l4.polya.transitions import should_advance


def _state(stage: PolyaStage) -> PolyaState:
    return PolyaState(current_stage=stage)


class TestUnderstand:
    """길이 + 문장 부호로 재진술 신호 감지."""

    def test_long_restatement_with_punct_advances(self) -> None:
        # 자기 언어로 충분히 길고 문장 부호 있음
        s = _state(PolyaStage.UNDERSTAND)
        text = "이 문제는 함수 f의 최댓값을 구하는 문제고, 조건은 x≥0이야."
        assert should_advance(s, text) == "next"

    def test_short_acknowledgement_stays(self) -> None:
        s = _state(PolyaStage.UNDERSTAND)
        assert should_advance(s, "네.") == "stay"
        assert should_advance(s, "음") == "stay"

    def test_long_but_no_punct_stays(self) -> None:
        # 길지만 문장 구조 없음(단어 나열)
        s = _state(PolyaStage.UNDERSTAND)
        assert should_advance(s, "함수 최댓값 조건 미지수 정의역 부등식") == "stay"


class TestPlan:
    """전략 키워드 1+ → next."""

    def test_strategy_keyword_advances(self) -> None:
        s = _state(PolyaStage.PLAN)
        for w in ("공식 쓸까", "비슷한 문제 본 적 있어", "그림 그려볼게", "치환해볼까"):
            assert should_advance(s, w) == "next", w

    def test_no_strategy_keyword_stays(self) -> None:
        s = _state(PolyaStage.PLAN)
        assert should_advance(s, "잘 모르겠어") == "stay"
        assert should_advance(s, "어렵네") == "stay"


class TestExecute:
    """결과 토큰 + 등호 + 다중 줄 — 셋 모두 필요(보수적)."""

    def test_all_signals_advances(self) -> None:
        s = _state(PolyaStage.EXECUTE)
        text = "f'(x) = 2x - 4\n2x - 4 = 0\n따라서 x = 2"
        assert should_advance(s, text) == "next"

    def test_missing_equals_stays(self) -> None:
        s = _state(PolyaStage.EXECUTE)
        text = "따라서 답은 2\n그러므로 끝"
        assert should_advance(s, text) == "stay"

    def test_missing_answer_token_stays(self) -> None:
        s = _state(PolyaStage.EXECUTE)
        text = "f'(x) = 2x - 4\n2x - 4 = 0"
        assert should_advance(s, text) == "stay"

    def test_single_line_stays(self) -> None:
        s = _state(PolyaStage.EXECUTE)
        text = "답 = 2"
        assert should_advance(s, text) == "stay"


class TestReview:
    """REVIEW는 종착 — 어떤 입력이든 stay(자동 전이 없음)."""

    def test_terminal_always_stays(self) -> None:
        s = _state(PolyaStage.REVIEW)
        for w in ("다른 방법으로도 풀려", "검산해보니 맞아", "왜 이렇게 풀었지", ""):
            assert should_advance(s, w) == "stay", w


class TestNeverAutoPrevious:
    """자동 previous는 절대 없음(스펙 L101: 학생 *명시* 후퇴 신호로만)."""

    def test_no_branch_returns_previous(self) -> None:
        for stage in PolyaStage:
            for text in ("", "모르겠어", "다시", "?"):
                assert should_advance(_state(stage), text) != "previous"


class TestMasteryAdjustment:
    """slice 71: UNDERSTAND→PLAN 재진술 길이 임계가 숙달도로 ∓5(숙달 빨리·초보 충실)."""

    def test_mastery_lowers_threshold(self) -> None:
        # 16자(∈[15,19])·문장부호 — 기본(20) stay·숙달(15) next.
        s = _state(PolyaStage.UNDERSTAND)
        text = "f의 최댓값을 구해, x>0."
        assert should_advance(s, text) == "stay"
        assert should_advance(s, text, mastery_level="숙달") == "next"

    def test_novice_raises_threshold(self) -> None:
        # 21자(∈[20,24])·문장부호 — 기본(20) next·초보(25) stay.
        s = _state(PolyaStage.UNDERSTAND)
        text = "이 문제는 f의 최댓값을 구하는 거야."
        assert should_advance(s, text) == "next"
        assert should_advance(s, text, mastery_level="초보") == "stay"

    def test_developing_uses_default(self) -> None:
        s = _state(PolyaStage.UNDERSTAND)
        text = "이 문제는 f의 최댓값을 구하는 거야."
        assert should_advance(s, text, mastery_level="발전 중") == "next"

    def test_none_preserves_default(self) -> None:
        s = _state(PolyaStage.UNDERSTAND)
        text = "이 문제는 f의 최댓값을 구하는 거야."
        assert should_advance(s, text, mastery_level=None) == should_advance(s, text)

    def test_understand_adjustment_is_stage_scoped(self) -> None:
        # slice 71 길이 임계는 UNDERSTAND 전용 — PLAN은 키워드 없으면 길이·숙달 무관 stay.
        s = _state(PolyaStage.PLAN)
        text = "특별한 신호가 하나도 없는 긴 문장입니다."
        assert should_advance(s, text, mastery_level="숙달") == "stay"


class TestMasteryStageTransitions:
    """slice 72: PLAN→EXECUTE 초보 길이 요구·EXECUTE→REVIEW 숙달 다중줄 면제."""

    def test_novice_short_strategy_stays(self) -> None:
        # 초보: 단답 키워드("공식")만으론 미진행(len<10).
        s = _state(PolyaStage.PLAN)
        assert should_advance(s, "공식") == "next"  # 기본(None)은 진행
        assert should_advance(s, "공식", mastery_level="초보") == "stay"

    def test_novice_full_strategy_advances(self) -> None:
        s = _state(PolyaStage.PLAN)
        text = "공식을 써서 양변을 정리해볼게"  # 16자 ≥ 10
        assert should_advance(s, text, mastery_level="초보") == "next"

    def test_master_short_strategy_advances(self) -> None:
        # 숙달은 길이 요구 없음(키워드만으로 진행·불변).
        s = _state(PolyaStage.PLAN)
        assert should_advance(s, "공식", mastery_level="숙달") == "next"

    def test_master_single_line_execute_advances(self) -> None:
        # 숙달: = + 답 토큰이면 다중줄 없어도 REVIEW 진입.
        s = _state(PolyaStage.EXECUTE)
        text = "x = 2 따라서 답"  # 한 줄·등호+답
        assert should_advance(s, text) == "stay"  # 기본은 다중줄 요구
        assert should_advance(s, text, mastery_level="숙달") == "next"

    def test_novice_execute_unchanged(self) -> None:
        # 초보/발전중은 EXECUTE 다중줄 요구 불변(한 줄 → stay).
        s = _state(PolyaStage.EXECUTE)
        text = "x = 2 따라서 답"
        assert should_advance(s, text, mastery_level="초보") == "stay"
