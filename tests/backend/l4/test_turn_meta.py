"""PED-04 D1·D2 순수 파생 단위테스트 — `l4/turn_meta.py`.

핵심 invariant:
- 재계산 0: 여기 함수는 전부 이미 계산된 값의 사영이지 새 추정이 아니다.
- 날조 0: 생산자가 없는 축은 None(NULL).
- 복호 0: `derive_recent_categories`·`derive_polya_state`는 학생 원문을 보지 않는다
  (`TurnMetaRow`에 content 필드 자체가 없다 — 구조적 보장).
"""

from __future__ import annotations

from whymath_backend.l4.misconception.models import InterventionDecision, InterventionPattern
from whymath_backend.l4.models import PolyaStage, PolyaState
from whymath_backend.l4.socratic.categories import SocraticCategory
from whymath_backend.l4.turn_meta import (
    REACHABLE_STRATEGIES,
    TurnMetaRow,
    classify_student_intent,
    compose_understanding_signal,
    derive_polya_state,
    derive_recent_categories,
    detect_state_mismatch,
    resolve_socratic_strategy,
    stage_to_targeted_step,
)
from whymath_backend.schema.enums import SocraticStrategy, StudentIntent, TurnRole


def _intervention(pattern: InterventionPattern) -> InterventionDecision:
    return InterventionDecision(pattern=pattern, prompt="테스트 개입 발화", misconception_id="M001")


# ── resolve_socratic_strategy ────────────────────────────────────────────────
class TestResolveSocraticStrategy:
    def test_counterexample_pattern_maps_to_counterexample_strategy(self) -> None:
        result = resolve_socratic_strategy(
            intervention=_intervention(InterventionPattern.COUNTEREXAMPLE),
            reveals="next_concept_to_focus",
            target_stage=PolyaStage.EXECUTE,
        )
        assert result is SocraticStrategy.반례제시

    def test_reverse_reasoning_pattern_maps_to_condition_check_strategy(self) -> None:
        result = resolve_socratic_strategy(
            intervention=_intervention(InterventionPattern.REVERSE_REASONING),
            reveals="next_concept_to_focus",
            target_stage=PolyaStage.EXECUTE,
        )
        assert result is SocraticStrategy.조건확인

    def test_concrete_case_pattern_maps_to_example_strategy(self) -> None:
        result = resolve_socratic_strategy(
            intervention=_intervention(InterventionPattern.CONCRETE_CASE),
            reveals="next_concept_to_focus",
            target_stage=PolyaStage.EXECUTE,
        )
        assert result is SocraticStrategy.예시제시

    def test_visualization_pattern_maps_to_graph_strategy(self) -> None:
        result = resolve_socratic_strategy(
            intervention=_intervention(InterventionPattern.VISUALIZATION),
            reveals="next_concept_to_focus",
            target_stage=PolyaStage.EXECUTE,
        )
        assert result is SocraticStrategy.그래프그리기제안

    def test_no_intervention_but_step_decomposition_reveal_wins(self) -> None:
        """개입 없음 + hint_level≥2(step_flow) → 단계분해(개입보다 하위 우선순위 확인용 대조)."""
        for reveals in ("step_flow", "partial_steps_demo", "full_solution"):
            result = resolve_socratic_strategy(
                intervention=None, reveals=reveals, target_stage=PolyaStage.PLAN
            )
            assert result is SocraticStrategy.단계분해

    def test_intervention_present_overrides_reveal(self) -> None:
        """개입이 있으면 reveal 계열이 step_flow여도 개입 전략이 우선(사다리 1순위)."""
        result = resolve_socratic_strategy(
            intervention=_intervention(InterventionPattern.COUNTEREXAMPLE),
            reveals="step_flow",
            target_stage=PolyaStage.PLAN,
        )
        assert result is SocraticStrategy.반례제시

    def test_stage_default_understand(self) -> None:
        result = resolve_socratic_strategy(
            intervention=None, reveals="next_concept_to_focus", target_stage=PolyaStage.UNDERSTAND
        )
        assert result is SocraticStrategy.조건확인

    def test_stage_default_plan(self) -> None:
        result = resolve_socratic_strategy(
            intervention=None, reveals="next_concept_to_focus", target_stage=PolyaStage.PLAN
        )
        assert result is SocraticStrategy.유사문제

    def test_stage_default_execute(self) -> None:
        result = resolve_socratic_strategy(
            intervention=None, reveals="next_concept_to_focus", target_stage=PolyaStage.EXECUTE
        )
        assert result is SocraticStrategy.단계분해

    def test_stage_default_review_is_none_not_forced(self) -> None:
        """REVIEW는 6종 중 대응이 없다 — 억지 매핑 대신 정직하게 NULL."""
        result = resolve_socratic_strategy(
            intervention=None, reveals="next_concept_to_focus", target_stage=PolyaStage.REVIEW
        )
        assert result is None

    def test_reachable_strategies_matches_production_path_outputs(self) -> None:
        """REACHABLE_STRATEGIES는 *실제 생산 경로*(select_intervention이 실제로 반환하는
        패턴 2종: COUNTEREXAMPLE·REVERSE_REASONING)에서 도달 가능한 값의 집합이다.

        `InterventionPattern` 전체(4종)를 돌리면 VISUALIZATION·CONCRETE_CASE 매핑도 걸리지만,
        `select_intervention`은 그 둘을 *생산하지 않는다*(l4/misconception/intervene.py 실측) —
        그래서 이 테스트는 실제로 도달 가능한 경로만 돈다(측정 note의 정직 표기와 정합).
        """
        outputs: set[SocraticStrategy] = set()
        for pattern in (InterventionPattern.COUNTEREXAMPLE, InterventionPattern.REVERSE_REASONING):
            v = resolve_socratic_strategy(
                intervention=_intervention(pattern),
                reveals="next_concept_to_focus",
                target_stage=PolyaStage.EXECUTE,
            )
            if v is not None:
                outputs.add(v)
        for stage in PolyaStage:
            v = resolve_socratic_strategy(
                intervention=None, reveals="next_concept_to_focus", target_stage=stage
            )
            if v is not None:
                outputs.add(v)
        outputs.add(SocraticStrategy.단계분해)  # step_flow 경로(개입 무관)
        assert outputs == REACHABLE_STRATEGIES


# ── compose_understanding_signal ─────────────────────────────────────────────
class TestComposeUnderstandingSignal:
    def test_all_axes_absent_but_stuck_always_present_returns_value(self) -> None:
        """stuck 축은 항상 가용이라 mastery·verify가 둘 다 None이어도 None이 아니다."""
        result = compose_understanding_signal(mastery=None, verify_passed=None, stuck_turns=0)
        assert result is not None

    def test_high_mastery_verify_pass_no_stuck_near_one(self) -> None:
        result = compose_understanding_signal(mastery=1.0, verify_passed=True, stuck_turns=0)
        assert result == 1.0

    def test_low_mastery_verify_fail_stuck_near_zero(self) -> None:
        result = compose_understanding_signal(mastery=0.0, verify_passed=False, stuck_turns=10)
        assert result == 0.0

    def test_output_clamped_to_unit_interval(self) -> None:
        result = compose_understanding_signal(mastery=0.5, verify_passed=True, stuck_turns=0)
        assert result is not None
        assert 0.0 <= result <= 1.0

    def test_output_rounded_to_two_decimals(self) -> None:
        result = compose_understanding_signal(mastery=0.333333, verify_passed=None, stuck_turns=2)
        assert result is not None
        # Numeric(3,2) 계약 — 소수 2자리 초과 정밀도가 남지 않아야 세션 생성이 ValidationError로
        # 죽지 않는다(schema/dialogue.py ge=0 le=1 검증과의 상호작용).
        assert round(result, 2) == result

    def test_stuck_turns_at_threshold_zeroes_stuck_axis(self) -> None:
        """5회 이상 막힘 → stuck 축 0. mastery·verify 둘 다 없으면 신호는 0.0 근처."""
        result = compose_understanding_signal(mastery=None, verify_passed=None, stuck_turns=5)
        assert result == 0.0


# ── classify_student_intent ──────────────────────────────────────────────────
class TestClassifyStudentIntent:
    def test_empty_input_no_solution_returns_none(self) -> None:
        assert classify_student_intent(student_input="", has_solution=False) is None

    def test_empty_input_with_solution_returns_attempt_intent(self) -> None:
        """빈 발화라도 풀이가 실려 있으면(인라인 발화 없는 풀이 제출) 답시도로 분류."""
        assert classify_student_intent(student_input="", has_solution=True) is StudentIntent.답시도

    def test_demand_answer_token_returns_giveup_intent(self) -> None:
        assert (
            classify_student_intent(student_input="그냥 답 알려주세요", has_solution=False)
            is StudentIntent.포기
        )

    def test_frustration_token_returns_stuck_intent(self) -> None:
        assert (
            classify_student_intent(student_input="모르겠어요 너무 어려워요", has_solution=False)
            is StudentIntent.막힘표현
        )

    def test_question_signal_token_returns_question_intent(self) -> None:
        assert (
            classify_student_intent(student_input="왜 그렇게 되나요?", has_solution=False)
            is StudentIntent.질문
        )

    def test_demand_answer_takes_priority_over_question_signal(self) -> None:
        """답 요구·질문 신호가 동시에 있으면 포기(1순위)가 이긴다."""
        result = classify_student_intent(
            student_input="왜 그런지 모르겠고 그냥 답 알려줘", has_solution=False
        )
        assert result is StudentIntent.포기

    def test_solution_present_no_special_token_returns_attempt_intent(self) -> None:
        assert (
            classify_student_intent(student_input="x=3이라고 생각해요", has_solution=True)
            is StudentIntent.답시도
        )

    def test_neutral_text_no_solution_returns_confirmation_intent(self) -> None:
        assert (
            classify_student_intent(student_input="네 알겠습니다", has_solution=False)
            is StudentIntent.이해확인
        )


# ── derive_recent_categories ─────────────────────────────────────────────────
def _row(order: int, role: TurnRole, step: int | None, intent: StudentIntent | None) -> TurnMetaRow:
    return TurnMetaRow(turn_order=order, role=role, targeted_step=step, student_intent=intent)


class TestDeriveRecentCategories:
    def test_empty_rows_returns_empty(self) -> None:
        assert derive_recent_categories([]) == ()

    def test_no_decrypt_surface_by_construction(self) -> None:
        """TurnMetaRow에는 content 필드가 존재하지 않는다 — 복호 0이 타입으로 보장됨."""
        assert not hasattr(TurnMetaRow, "content")
        assert TurnMetaRow._fields == ("turn_order", "role", "targeted_step", "student_intent")

    def test_three_consecutive_understand_turns_yields_clarification_tail(self) -> None:
        rows = [
            _row(1, TurnRole.student, None, StudentIntent.이해확인),
            _row(2, TurnRole.assistant, 1, None),  # UNDERSTAND → CLARIFICATION
            _row(3, TurnRole.student, None, StudentIntent.이해확인),
            _row(4, TurnRole.assistant, 1, None),
            _row(5, TurnRole.student, None, StudentIntent.이해확인),
            _row(6, TurnRole.assistant, 1, None),
        ]
        result = derive_recent_categories(rows)
        assert result == (
            SocraticCategory.CLARIFICATION,
            SocraticCategory.CLARIFICATION,
            SocraticCategory.CLARIFICATION,
        )

    def test_window_caps_at_three(self) -> None:
        rows = []
        for i in range(5):
            rows.append(_row(2 * i + 1, TurnRole.student, None, StudentIntent.이해확인))
            rows.append(_row(2 * i + 2, TurnRole.assistant, 1, None))
        result = derive_recent_categories(rows, window=3)
        assert len(result) == 3

    def test_stops_at_null_targeted_step(self) -> None:
        """구 데이터(targeted_step NULL)를 만나면 그 이전은 보지 않는다."""
        rows = [
            _row(1, TurnRole.student, None, StudentIntent.이해확인),
            _row(2, TurnRole.assistant, None, None),  # 구 데이터
            _row(3, TurnRole.student, None, StudentIntent.이해확인),
            _row(4, TurnRole.assistant, 1, None),
        ]
        result = derive_recent_categories(rows)
        assert result == (SocraticCategory.CLARIFICATION,)

    def test_stops_at_override_suspect_intent(self) -> None:
        """꼬리 AI 턴(4)의 짝 학생 턴(3) 의도가 오버라이드 의심(질문)이면, *그 AI 턴 자체*가
        발화 신호 오버라이드였을 수 있어 즉시 절단한다(그 이전 턴은 보지도 않는다) — 보수적."""
        rows = [
            _row(1, TurnRole.student, None, StudentIntent.이해확인),
            _row(2, TurnRole.assistant, 1, None),
            _row(3, TurnRole.student, None, StudentIntent.질문),  # 오버라이드 의심
            _row(4, TurnRole.assistant, 1, None),
        ]
        result = derive_recent_categories(rows)
        assert result == ()

    def test_non_suspect_pair_before_suspect_pair_is_included(self) -> None:
        """의심 턴은 절단하되, 그 *앞* 안전한 턴이 꼬리에 있다면(의심 턴이 중간에 있지 않고
        맨 끝일 때) 절단 이전 항목은 영향받지 않는다 — 의심 턴이 맨 끝이 아닌 경우의 대조."""
        rows = [
            _row(1, TurnRole.student, None, StudentIntent.이해확인),
            _row(2, TurnRole.assistant, 1, None),  # 안전 — 포함
            _row(3, TurnRole.student, None, StudentIntent.이해확인),
            _row(4, TurnRole.assistant, 1, None),  # 안전 — 포함
        ]
        result = derive_recent_categories(rows)
        assert result == (SocraticCategory.CLARIFICATION, SocraticCategory.CLARIFICATION)


# ── derive_polya_state ───────────────────────────────────────────────────────
class TestDerivePolyaState:
    def test_empty_rows_returns_default_understand(self) -> None:
        state = derive_polya_state([], prev_hint_level=2)
        assert state.current_stage is PolyaStage.UNDERSTAND
        assert state.turn_count == 0
        assert state.history == []
        assert state.prev_hint_level == 2

    def test_single_stage_turn_count_accumulates(self) -> None:
        rows = [
            _row(1, TurnRole.student, None, None),
            _row(2, TurnRole.assistant, 1, None),
            _row(3, TurnRole.student, None, None),
            _row(4, TurnRole.assistant, 1, None),
            _row(5, TurnRole.student, None, None),
            _row(6, TurnRole.assistant, 1, None),
        ]
        state = derive_polya_state(rows, prev_hint_level=None)
        assert state.current_stage is PolyaStage.UNDERSTAND
        assert state.turn_count == 3
        assert state.history == []

    def test_stage_transition_resets_turn_count_and_appends_history(self) -> None:
        rows = [
            _row(1, TurnRole.student, None, None),
            _row(2, TurnRole.assistant, 1, None),  # UNDERSTAND
            _row(3, TurnRole.student, None, None),
            _row(4, TurnRole.assistant, 2, None),  # → PLAN
            _row(5, TurnRole.student, None, None),
            _row(6, TurnRole.assistant, 2, None),  # PLAN 유지
        ]
        state = derive_polya_state(rows, prev_hint_level=None)
        assert state.current_stage is PolyaStage.PLAN
        assert state.turn_count == 2  # PLAN에서 연속 2턴
        assert state.history == [PolyaStage.UNDERSTAND]

    def test_ignores_null_targeted_step_rows(self) -> None:
        rows = [
            _row(1, TurnRole.assistant, None, None),  # 결손 — 무시
            _row(2, TurnRole.assistant, 1, None),
        ]
        state = derive_polya_state(rows, prev_hint_level=None)
        assert state.current_stage is PolyaStage.UNDERSTAND
        assert state.turn_count == 1


class TestDetectStateMismatch:
    def test_identical_states_no_mismatch(self) -> None:
        state = PolyaState(current_stage=PolyaStage.PLAN, turn_count=2, prev_hint_level=1)
        assert detect_state_mismatch(state, state) == ()

    def test_current_stage_mismatch_detected(self) -> None:
        client = PolyaState(current_stage=PolyaStage.EXECUTE)
        server = PolyaState(current_stage=PolyaStage.UNDERSTAND)
        assert "current_stage" in detect_state_mismatch(client, server)

    def test_turn_count_mismatch_detected(self) -> None:
        client = PolyaState(turn_count=99)
        server = PolyaState(turn_count=1)
        assert "turn_count" in detect_state_mismatch(client, server)

    def test_history_difference_not_flagged(self) -> None:
        """history는 비교 축이 아니다 — 클라가 안 보내는 게 정상이라 노이즈 방지."""
        client = PolyaState(history=[])
        server = PolyaState(history=[PolyaStage.UNDERSTAND, PolyaStage.PLAN])
        assert detect_state_mismatch(client, server) == ()

    def test_multiple_mismatches_all_reported(self) -> None:
        client = PolyaState(current_stage=PolyaStage.REVIEW, turn_count=5, prev_hint_level=4)
        server = PolyaState(current_stage=PolyaStage.UNDERSTAND, turn_count=0, prev_hint_level=1)
        fields = detect_state_mismatch(client, server)
        assert set(fields) == {"current_stage", "turn_count", "prev_hint_level"}


class TestStageToTargetedStep:
    def test_one_based_ordering(self) -> None:
        assert stage_to_targeted_step(PolyaStage.UNDERSTAND) == 1
        assert stage_to_targeted_step(PolyaStage.PLAN) == 2
        assert stage_to_targeted_step(PolyaStage.EXECUTE) == 3
        assert stage_to_targeted_step(PolyaStage.REVIEW) == 4
