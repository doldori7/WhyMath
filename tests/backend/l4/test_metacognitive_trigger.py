"""L4 메타인지 코칭 트리거 단위테스트 (hermetic·순수 결정).

L2 두 신호(BKT 숙달·IRT θ)+계산오류 신호에서 코칭 포커스 6종을 결정론적으로 검증한다.
"""

from __future__ import annotations

from whymath_backend.l4.metacognitive_trigger import (
    CoachingTrigger,
    focus_to_socratic_category,
    recommend_coaching,
)
from whymath_backend.l4.socratic.categories import SocraticCategory


class TestRecommendCoaching:
    def test_arithmetic_error_routes_verify(self) -> None:
        """계산 오류 감지 → verify(검산), 다른 신호와 무관."""
        trig = recommend_coaching(0.9, 2.0, arithmetic_error=True)
        assert trig.focus == "verify"
        assert trig.socratic_category == SocraticCategory.EVIDENCE
        assert trig.rationale and trig.prompt

    def test_arithmetic_error_priority_over_missing(self) -> None:
        """신호가 없어도(둘 다 None) 계산 오류면 diagnose 아닌 verify(즉시 코칭)."""
        assert recommend_coaching(None, None, arithmetic_error=True).focus == "verify"

    def test_arithmetic_error_priority_over_mastery_focus(self) -> None:
        """저숙달이라도 계산 오류 신호면 foundation 아닌 verify(슬립 우선)."""
        assert recommend_coaching(0.1, -2.0, arithmetic_error=True).focus == "verify"

    def test_no_arithmetic_error_default_unchanged(self) -> None:
        """arithmetic_error 기본 False → 기존 mastery 기반 동작 불변."""
        assert recommend_coaching(0.9, 2.0).focus == "advance"
        assert recommend_coaching(0.9, 2.0, arithmetic_error=False).focus == "advance"

    def test_verify_steps_uses_step_self_check_prompt(self) -> None:
        """verify_steps=True(다단계 대수 슬립) → verify·단계 자가검산 prompt·EVIDENCE 유지."""
        trig = recommend_coaching(0.9, 2.0, arithmetic_error=True, verify_steps=True)
        assert trig.focus == "verify"
        assert trig.socratic_category == SocraticCategory.EVIDENCE  # 카테고리 불변
        assert "한 줄씩" in trig.prompt  # 단계 자가검산 변형 발화

    def test_verify_steps_default_keeps_generic_prompt(self) -> None:
        """verify_steps 기본 False → 기존 계산 검산 prompt(backward-compat·위치 비변형)."""
        generic = recommend_coaching(0.9, 2.0, arithmetic_error=True)
        assert generic.focus == "verify"
        assert "숫자가 어긋났는지" in generic.prompt and "한 줄씩" not in generic.prompt
        # 명시 False도 동일(기존 verify 테스트와 동치).
        assert recommend_coaching(0.9, 2.0, arithmetic_error=True, verify_steps=False) == generic

    def test_verify_steps_ignored_without_arithmetic_error(self) -> None:
        """arithmetic_error 없으면 verify 분기 미진입 → verify_steps 무효(mastery 경로)."""
        assert recommend_coaching(0.9, 2.0, verify_steps=True).focus == "advance"

    def test_position_aware_verify_prompt(self) -> None:
        """verify_steps=True + incorrect_step_index → *위치 인지* 점층 발화·focus_step_index."""
        trig = recommend_coaching(
            0.9, 2.0, arithmetic_error=True, verify_steps=True, incorrect_step_index=2
        )
        assert trig.focus == "verify"
        assert trig.socratic_category == SocraticCategory.EVIDENCE  # 카테고리 불변
        # 위치 인지형 — 앞단계 통과 확인 + 그 지점부터 스스로 재검산(질문형·소크라테스).
        assert "잘 따라왔어" in trig.prompt
        assert "다시 확인해볼까" in trig.prompt
        # 구조화 메타데이터(발화와 별도 채널) — 전이 인덱스 그대로.
        assert trig.focus_step_index == 2

    def test_position_aware_off_by_one_mapping(self) -> None:
        """off-by-one 핀 — 전이 i → 사람 줄번호 k=i+1(통과)·m=i+2(재검산 대상 줄)."""
        # 전이 0(steps[0]→steps[1]): 1줄까지 통과(k=1)·2번째 줄 재검산(m=2).
        p0 = recommend_coaching(
            0.9, 2.0, arithmetic_error=True, verify_steps=True, incorrect_step_index=0
        ).prompt
        assert "처음 1줄까지는 잘 따라왔어" in p0
        assert "2번째 줄" in p0
        # 전이 3(steps[3]→steps[4]): 4줄까지 통과(k=4)·5번째 줄 재검산(m=5).
        p3 = recommend_coaching(
            0.9, 2.0, arithmetic_error=True, verify_steps=True, incorrect_step_index=3
        ).prompt
        assert "처음 4줄까지는 잘 따라왔어" in p3
        assert "5번째 줄" in p3

    def test_position_aware_no_answer_or_negation(self) -> None:
        """교수학 금기 가드 — 위치 인지 발화에 정답·수정·'틀렸다' 부정 단정 부재."""
        prompt = recommend_coaching(
            0.9, 2.0, arithmetic_error=True, verify_steps=True, incorrect_step_index=1
        ).prompt
        for forbidden in ("틀렸", "틀린", "오답", "정답은", "고치", "수정", "이렇게 하면", "="):
            assert forbidden not in prompt
        # 효능감(앞단계 확인) + 질문형(소크라테스) 존재.
        assert "잘 따라왔어" in prompt and prompt.rstrip().endswith("?")

    def test_index_none_keeps_generic_step_prompt(self) -> None:
        """incorrect_step_index 없음
        → 기존 위치 비지목 _PROMPT_VERIFY_STEPS·focus_step_index None."""
        trig = recommend_coaching(
            0.9, 2.0, arithmetic_error=True, verify_steps=True, incorrect_step_index=None
        )
        assert "한 줄씩" in trig.prompt
        assert "잘 따라왔어" not in trig.prompt  # 위치 인지형 아님
        assert trig.focus_step_index is None
        # 인덱스 키워드 미지정도 동일(완전 하위호환).
        assert recommend_coaching(0.9, 2.0, arithmetic_error=True, verify_steps=True) == trig

    def test_index_without_verify_steps_metadata_only(self) -> None:
        """verify_steps=False + index → 발화는 일반 verify(위치 비지목)·focus_step_index만 채움."""
        trig = recommend_coaching(
            0.9, 2.0, arithmetic_error=True, verify_steps=False, incorrect_step_index=2
        )
        assert trig.focus == "verify"
        assert "숫자가 어긋났는지" in trig.prompt  # 일반 verify 발화(변형 아님)
        assert "잘 따라왔어" not in trig.prompt and "한 줄씩" not in trig.prompt
        assert trig.focus_step_index == 2  # 메타데이터만 노출(발화 별도 채널)

    def test_index_ignored_when_not_verify_focus(self) -> None:
        """verify 포커스가 아니면(mastery 경로) focus_step_index는 항상 None."""
        trig = recommend_coaching(0.9, 2.0, incorrect_step_index=2)
        assert trig.focus == "advance"
        assert trig.focus_step_index is None

    def test_hint_level_none_keeps_verify_prompt_unchanged(self) -> None:
        """hint_level=None → 기존 verify 발화·반환 완전 불변(회귀)."""
        # 위치 비지목 — 기존 단계 자가검산 발화 그대로.
        generic = recommend_coaching(0.9, 2.0, arithmetic_error=True, verify_steps=True)
        with_none = recommend_coaching(
            0.9, 2.0, arithmetic_error=True, verify_steps=True, hint_level=None
        )
        assert with_none == generic
        assert with_none.hint_level is None
        # 위치 인지 — 기존 위치 인지 발화 그대로.
        at = recommend_coaching(
            0.9, 2.0, arithmetic_error=True, verify_steps=True, incorrect_step_index=2
        )
        at_none = recommend_coaching(
            0.9,
            2.0,
            arithmetic_error=True,
            verify_steps=True,
            incorrect_step_index=2,
            hint_level=None,
        )
        assert at_none == at
        assert at_none.hint_level is None

    def test_hint_level_1_2_no_escalation_metadata_filled(self) -> None:
        """verify+steps+hint_level 1·2 → 발화 점층 안 됨(기존 발화)·hint_level 메타데이터만 채움."""
        for level in (1, 2):
            # 위치 비지목.
            generic = recommend_coaching(0.9, 2.0, arithmetic_error=True, verify_steps=True)
            trig = recommend_coaching(
                0.9, 2.0, arithmetic_error=True, verify_steps=True, hint_level=level  # type: ignore[arg-type]
            )
            assert trig.prompt == generic.prompt  # 발화 불변(점층 아님)
            assert trig.hint_level == level  # 메타데이터만 채움(별도 채널)
            # 위치 인지.
            at = recommend_coaching(
                0.9, 2.0, arithmetic_error=True, verify_steps=True, incorrect_step_index=2
            )
            trig_at = recommend_coaching(
                0.9,
                2.0,
                arithmetic_error=True,
                verify_steps=True,
                incorrect_step_index=2,
                hint_level=level,  # type: ignore[arg-type]
            )
            assert trig_at.prompt == at.prompt  # 발화 불변
            assert trig_at.hint_level == level

    def test_hint_level_3_4_escalates_without_index(self) -> None:
        """verify+steps+hint_level 3·4(step_index 없음) → 점층 과정-비계 발화로 바뀜."""
        baseline = recommend_coaching(0.9, 2.0, arithmetic_error=True, verify_steps=True).prompt
        for level in (3, 4):
            trig = recommend_coaching(
                0.9, 2.0, arithmetic_error=True, verify_steps=True, hint_level=level  # type: ignore[arg-type]
            )
            assert trig.focus == "verify"
            assert trig.socratic_category == SocraticCategory.EVIDENCE  # 카테고리 불변
            assert trig.prompt != baseline  # 점층으로 바뀜
            # 과정 재구성 비계 — "어떤 규칙"을 한 단계씩 말로 다시 세우기.
            assert "어떤 규칙" in trig.prompt and "한 줄씩" in trig.prompt
            assert trig.hint_level == level
            assert trig.focus_step_index is None  # 위치 미제공

    def test_hint_level_3_4_escalates_with_index_off_by_one(self) -> None:
        """verify+steps+hint_level 3·4(step_index 있음) → 위치 인지 점층·off-by-one(k/m) 정확."""
        # 전이 2(steps[2]→steps[3]): 3줄까지 통과(k=3)·4번째 줄 재구성(m=4).
        for level in (3, 4):
            trig = recommend_coaching(
                0.9,
                2.0,
                arithmetic_error=True,
                verify_steps=True,
                incorrect_step_index=2,
                hint_level=level,  # type: ignore[arg-type]
            )
            assert trig.focus == "verify"
            # 효능감(앞 k줄 통과) 유지 + 과정 재구성 비계(m번째 줄 규칙).
            assert "처음 3줄까지는 잘 따라왔어" in trig.prompt
            assert "4번째 줄" in trig.prompt
            assert "어떤 규칙" in trig.prompt
            assert trig.hint_level == level
            assert trig.focus_step_index == 2
        # 전이 0(steps[0]→steps[1]): 1줄 통과(k=1)·2번째 줄 재구성(m=2).
        p0 = recommend_coaching(
            0.9, 2.0, arithmetic_error=True, verify_steps=True, incorrect_step_index=0, hint_level=3
        ).prompt
        assert "처음 1줄까지는 잘 따라왔어" in p0 and "2번째 줄" in p0

    def test_escalated_prompt_no_answer_or_negation(self) -> None:
        """교수학 금기 가드 — 점층 발화(위치 유/무)에 정답·수정·'틀렸다' 부정 단정 부재."""
        forbidden = ("틀렸", "틀린", "잘못", "오답", "정답은", "고치", "수정", "이렇게 하면", "=")
        # 위치 비지목 점층.
        no_idx = recommend_coaching(
            0.9, 2.0, arithmetic_error=True, verify_steps=True, hint_level=4
        ).prompt
        # 위치 인지 점층.
        with_idx = recommend_coaching(
            0.9,
            2.0,
            arithmetic_error=True,
            verify_steps=True,
            incorrect_step_index=1,
            hint_level=4,
        ).prompt
        for prompt in (no_idx, with_idx):
            for token in forbidden:
                assert token not in prompt
            # 질문형(소크라테스)으로 끝남.
            assert prompt.rstrip().endswith("?")

    def test_hint_level_ignored_when_not_verify_focus(self) -> None:
        """비-verify 포커스(mastery 경로)에 hint_level 줘도 발화 불변·hint_level None."""
        baseline = recommend_coaching(0.9, 2.0)  # advance(mastery 경로)
        trig = recommend_coaching(0.9, 2.0, hint_level=4)
        assert trig.focus == "foundation" or trig.focus == "advance"
        assert trig.prompt == baseline.prompt  # 발화 불변
        assert trig.hint_level is None  # verify 아니면 항상 None
        # foundation 경로도 동일.
        found = recommend_coaching(0.5, 0.0, hint_level=3)
        assert found.focus == "foundation"
        assert found.hint_level is None

    def test_hint_level_ignored_without_verify_steps(self) -> None:
        """verify이나 steps=False면 발화는 일반 verify·hint_level 메타데이터만 채움(점층 없음)."""
        generic = recommend_coaching(0.9, 2.0, arithmetic_error=True)  # 일반 verify
        trig = recommend_coaching(0.9, 2.0, arithmetic_error=True, verify_steps=False, hint_level=4)
        assert trig.focus == "verify"
        assert trig.prompt == generic.prompt  # 점층 없음(steps=False)
        assert "숫자가 어긋났는지" in trig.prompt
        assert trig.hint_level == 4  # 메타데이터(별도 채널)는 verify면 채움

    def test_missing_signal_diagnose(self) -> None:
        """한쪽 신호라도 없으면 diagnose(교차검증 불가)."""
        assert recommend_coaching(None, 1.0).focus == "diagnose"
        assert recommend_coaching(0.5, None).focus == "diagnose"
        assert recommend_coaching(None, None).focus == "diagnose"

    def test_irt_higher_consolidate(self) -> None:
        """맞히나(θ=4·프록시≈0.98) 숙달 낮음(0.1) → consolidate."""
        trig = recommend_coaching(0.1, 4.0)
        assert trig.focus == "consolidate"

    def test_bkt_higher_retrieval(self) -> None:
        """숙달 높(0.9)으나 능력 낮음(θ=-4·프록시≈0.02) → retrieval."""
        assert recommend_coaching(0.9, -4.0).focus == "retrieval"

    def test_agree_low_foundation(self) -> None:
        """합의(θ=0·프록시 0.5 = BKT 0.5)·수준<0.6 → foundation."""
        assert recommend_coaching(0.5, 0.0).focus == "foundation"

    def test_agree_high_advance(self) -> None:
        """합의(BKT 0.9·θ=2 프록시≈0.88)·수준≥0.6 → advance."""
        assert recommend_coaching(0.9, 2.0).focus == "advance"

    def test_threshold_boundary_advance(self) -> None:
        """수준이 정확히 임계(0.6)면 advance(>= 분기)."""
        # BKT=0.6·θ=0(프록시 0.5) 차 0.1≤tol → 합의·평균 0.55<0.6 → foundation
        assert recommend_coaching(0.6, 0.0).focus == "foundation"
        # BKT=0.7·θ=0(프록시 0.5) 차 -0.2 = -tol(엄격 < 아님) → 합의·평균 0.6≥0.6 → advance
        assert recommend_coaching(0.7, 0.0).focus == "advance"

    def test_custom_tolerance(self) -> None:
        """discrepancy_tol을 키우면 같은 차이도 합의로 분류."""
        # 차 0.382(프록시 0.882 - 0.5) — 기본 tol 0.2면 consolidate
        assert recommend_coaching(0.5, 2.0).focus == "consolidate"
        # tol 0.5면 합의 → 평균 0.69 ≥ 0.6 → advance
        assert recommend_coaching(0.5, 2.0, discrepancy_tol=0.5).focus == "advance"

    def test_returns_rationale_and_prompt(self) -> None:
        """결정엔 근거·학생 발화가 채워지고 frozen."""
        trig = recommend_coaching(0.1, 4.0)
        assert isinstance(trig, CoachingTrigger)
        assert trig.rationale
        assert trig.prompt
        # frozen
        try:
            trig.focus = "advance"  # type: ignore[misc]
        except Exception as exc:  # pydantic ValidationError(frozen)
            assert "frozen" in str(exc).lower() or "instance" in str(exc).lower()
        else:  # pragma: no cover
            raise AssertionError("frozen 모델이 변경을 허용함")

    def test_deterministic(self) -> None:
        assert recommend_coaching(0.3, 1.0) == recommend_coaching(0.3, 1.0)

    def test_includes_socratic_category(self) -> None:
        """결정에 대화 진입 소크라테스 카테고리가 포함(focus 매핑 일치)."""
        # consolidate(맞히나 숙달↓) → EVIDENCE(근거·추측 검증)
        trig = recommend_coaching(0.1, 4.0)
        assert trig.focus == "consolidate"
        assert trig.socratic_category == SocraticCategory.EVIDENCE


class TestFocusToSocraticCategory:
    def test_all_focus_mapped(self) -> None:
        assert focus_to_socratic_category("verify") == SocraticCategory.EVIDENCE
        assert focus_to_socratic_category("consolidate") == SocraticCategory.EVIDENCE
        assert focus_to_socratic_category("retrieval") == SocraticCategory.META
        assert focus_to_socratic_category("foundation") == SocraticCategory.CLARIFICATION
        assert focus_to_socratic_category("advance") == SocraticCategory.PERSPECTIVE
        assert focus_to_socratic_category("diagnose") == SocraticCategory.CLARIFICATION
