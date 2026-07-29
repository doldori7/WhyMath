"""답 미루기 4단계 graded hint 단위테스트 — 스펙 L31-61 정본 정렬.

핵심 invariant:
- 모호 시 hint_level=1(가장 빠른 단계 — 생산적 막힘 우선)
- 점진 상승 min(4, prev+1) — 시나리오 3·4(socratic_template)
- 5회+ 막힘 → 최소 3(스펙 L37) but prev 이하로 내려가지 않음
- REVEALS 라벨이 PRD 정렬과 1:1
"""

from __future__ import annotations

import pytest
from whymath_backend.l4.hint_deferral import REVEALS, decide_hint_level
from whymath_backend.l4.lthc.models import MasteryLevel


class TestDefaultLevelOne:
    """모호한 입력(신호 없음·5회 미만) → 1(가장 은근·가장 빠른 단계)."""

    def test_empty_input_first_turn(self) -> None:
        assert decide_hint_level(student_input="", turn_count=0, prev_hint_level=None) == 1

    def test_neutral_input_returns_1_even_if_prev_higher(self) -> None:
        # prev_hint_level이 높아도 신호 사라지면 1로 복귀(가장 빠른 단계에서 멈춤).
        assert (
            decide_hint_level(student_input="네, 그렇게 해볼게요", turn_count=2, prev_hint_level=3)
            == 1
        )


class TestFrustrationSignal:
    """좌절 신호 → min(4, prev+1) 점진 상승(socratic_template 시나리오 4)."""

    @pytest.mark.parametrize("text", ["잘 모르겠어", "막혔어", "너무 어려워", "헷갈려"])
    def test_frustration_keywords_advance(self, text: str) -> None:
        assert decide_hint_level(student_input=text, turn_count=1, prev_hint_level=1) == 2
        assert decide_hint_level(student_input=text, turn_count=1, prev_hint_level=2) == 3
        assert decide_hint_level(student_input=text, turn_count=1, prev_hint_level=3) == 4

    def test_frustration_caps_at_4(self) -> None:
        assert decide_hint_level(student_input="너무 어려워", turn_count=1, prev_hint_level=4) == 4


class TestDemandAnswerSignal:
    """답 요구 신호 → min(4, prev+1) 점진 상승(시나리오 3)."""

    @pytest.mark.parametrize("text", ["답 알려줘", "그냥 답이 뭐야", "정답 알려줘", "풀이 좀 해줘"])
    def test_demand_keywords_advance(self, text: str) -> None:
        assert decide_hint_level(student_input=text, turn_count=1, prev_hint_level=1) == 2
        assert decide_hint_level(student_input=text, turn_count=1, prev_hint_level=2) == 3

    def test_demand_caps_at_4(self) -> None:
        assert decide_hint_level(student_input="답 알려줘", turn_count=1, prev_hint_level=4) == 4


class TestStuckThreshold:
    """turn_count ≥ 5 → 최소 3(스펙 L37 "5회+ 막힘 → 부분 풀이")."""

    def test_five_turns_no_signal_jumps_to_3(self) -> None:
        # 신호 없어도 5회 막혔으면 3으로 점프(보수적 디폴트보다 우선).
        assert decide_hint_level(student_input="음...", turn_count=5, prev_hint_level=1) == 3

    def test_five_turns_prev_4_stays_4(self) -> None:
        # prev=4면 3으로 내려가지 않음(max).
        assert decide_hint_level(student_input="음...", turn_count=5, prev_hint_level=4) == 4

    def test_four_turns_still_default(self) -> None:
        # 임계 미만(4회)은 기본 규칙 적용.
        assert decide_hint_level(student_input="음...", turn_count=4, prev_hint_level=1) == 1


class TestPriorityOrder:
    """5회+ 막힘이 다른 신호보다 우선(임계가 가장 강력)."""

    def test_stuck_beats_demand_signal(self) -> None:
        # 5회+ 막힘 + 답 요구 → 막힘 규칙 적용(max(prev, 3)).
        # prev=1일 때: max(1, 3) = 3 (demand의 min(4, 2)=2보다 큼 — 임계 우선)
        assert decide_hint_level(student_input="답 알려줘", turn_count=5, prev_hint_level=1) == 3


class TestRevealsMap:
    """REVEALS 매핑이 PRD 정렬(스펙 L41-49)과 1:1."""

    def test_all_four_levels_have_reveals(self) -> None:
        assert set(REVEALS.keys()) == {1, 2, 3, 4}
        for label in REVEALS.values():
            assert label  # 비공 문자열

    def test_canonical_reveals_labels(self) -> None:
        assert REVEALS[1] == "next_concept_to_focus"
        assert REVEALS[2] == "step_flow"
        assert REVEALS[3] == "partial_steps_demo"
        assert REVEALS[4] == "full_solution"


class TestNoFalsePositives:
    """합법 토큰 부분일치로 신호 오작동 — 보수적 디자인 한계 문서화."""

    def test_short_neutral_phrasing_stays_1(self) -> None:
        # 좌절 토큰("어렵") 없는 자연스러운 응답
        assert (
            decide_hint_level(student_input="이 부분이 흥미롭네요", turn_count=2, prev_hint_level=2)
            == 1
        )


class TestMasteryConservatism:
    """능력 라벨 양방향 조정(slice 69 숙달·slice 77 초보) — 숙달 −1·초보 +1·발전중/None 불변."""

    def test_master_demand_lowered_to_1(self) -> None:
        # 답요구 prev=1: base 2 → max(1, 2-1)=1(가장 은근).
        assert (
            decide_hint_level(
                student_input="답 알려줘",
                turn_count=1,
                prev_hint_level=1,
                mastery_level="숙달",
            )
            == 1
        )

    def test_master_stuck_lowered_to_2(self) -> None:
        # 5회+ 막힘 prev=1: base 3 → max(1, 3-1)=2.
        assert (
            decide_hint_level(
                student_input="음...",
                turn_count=5,
                prev_hint_level=1,
                mastery_level="숙달",
            )
            == 2
        )

    def test_master_neutral_stays_1(self) -> None:
        # 중립 base 1 → max(1, 0)=1(클램프 — 숙달도 방향 힌트는 보장·정서 안전).
        assert (
            decide_hint_level(
                student_input="네, 해볼게요",
                turn_count=1,
                prev_hint_level=1,
                mastery_level="숙달",
            )
            == 1
        )

    def test_master_demand_prev3_lowered_to_3(self) -> None:
        # 답요구 prev=3: base min(4,4)=4 → 3(전체풀이 안전망 회피).
        assert (
            decide_hint_level(
                student_input="답 알려줘",
                turn_count=1,
                prev_hint_level=3,
                mastery_level="숙달",
            )
            == 3
        )

    @pytest.mark.parametrize("level", [None, "발전 중"])
    def test_neutral_levels_unchanged(self, level: MasteryLevel | None) -> None:
        # 발전중·None은 조정 안 함(답요구 prev=1 → 2) — 하위호환(숙달/초보만 조정).
        assert (
            decide_hint_level(
                student_input="답 알려줘",
                turn_count=1,
                prev_hint_level=1,
                mastery_level=level,
            )
            == 2
        )

    def test_novice_demand_raised_to_3(self) -> None:
        # slice 77: 답요구 prev=1 → base 2 → 초보 min(4, 2+1)=3(세분화·숙달의 대칭).
        assert (
            decide_hint_level(
                student_input="답 알려줘",
                turn_count=1,
                prev_hint_level=1,
                mastery_level="초보",
            )
            == 3
        )

    def test_novice_neutral_raised_to_2(self) -> None:
        # slice 77: 중립 base 1 → 초보 min(4, 2)=2(능력 낮음 → 한 단계 구체화).
        assert (
            decide_hint_level(
                student_input="네, 해볼게요",
                turn_count=1,
                prev_hint_level=1,
                mastery_level="초보",
            )
            == 2
        )

    def test_novice_stuck_capped_at_4(self) -> None:
        # slice 77: 5회+ 막힘 prev=3 → base 3 → 초보 min(4, 4)=4(클램프 — 전체풀이 상한).
        assert (
            decide_hint_level(
                student_input="음...",
                turn_count=5,
                prev_hint_level=3,
                mastery_level="초보",
            )
            == 4
        )

    def test_omitted_mastery_arg_unchanged(self) -> None:
        # mastery_level 인자 생략 → 기존 동작(기본 None).
        assert decide_hint_level(student_input="답 알려줘", turn_count=1, prev_hint_level=1) == 2
