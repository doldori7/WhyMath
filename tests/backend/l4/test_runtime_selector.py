"""Runtime Pedagogy Selector 테스트 — 선택 규칙표·2축 게이트·냉담 제공 차단 회귀.

핵심 회귀: **완전예제 냉담 제공 차단**(CLAUDE.md "학생이 막혔을 때 바로 정답 제공 금지"). REND-01
렌더
어댑터는 계층상 이를 막을 수 없어 L4 선택기가 유일한 방어선이다 — 이 파일이 그 방어선의 회귀
테스트다.
"""

from __future__ import annotations

from whymath_backend.l4.models import PolyaStage
from whymath_backend.l4.pedagogy.pack_registry import get_pack
from whymath_backend.l4.pedagogy.runtime_selector import (
    REASON_HINT_NOT_ESCALATED,
    REASON_PACK_FORBIDS_WORKED_FIRST,
    StudentSignals,
    decide,
    gate,
    select,
    selectable_strategies,
)
from whymath_backend.schema.enums import PedagogyStrategy


class TestSelectRuleTable:
    """규칙표 v1 — 우선순위대로 분기하는지."""

    def test_stuck_proposes_worked_example(self) -> None:
        # R1 — 막힘이면 완전예제를 *제안*한다(허용 여부는 게이트가 판정).
        signals = StudentSignals(turn_count=5)
        assert select(signals) is PedagogyStrategy.WORKED_EXAMPLE

    def test_misconception_selects_analogy(self) -> None:
        # R2 — 틀린 직관은 다른 직관으로 재구성.
        signals = StudentSignals(misconception_ids=("sign-flip-error",))
        assert select(signals) is PedagogyStrategy.ANALOGY

    def test_novice_after_wrong_answer_selects_direct(self) -> None:
        # R3 — 기반이 약한 학생에게 발문만 던지지 않는다.
        signals = StudentSignals(last_attempt_correct=False, mastery_level="초보")
        assert select(signals) is PedagogyStrategy.DIRECT

    def test_mastered_selects_problem_based(self) -> None:
        # R4 — 충분히 아는 학생에겐 문제를 먼저(생산적 고투).
        signals = StudentSignals(mastery_level="숙달")
        assert select(signals) is PedagogyStrategy.PROBLEM_BASED

    def test_default_is_socratic(self) -> None:
        # R5 — "답이 아닌, 이유를 묻는" 기본값.
        assert select(StudentSignals()) is PedagogyStrategy.SOCRATIC

    def test_stuck_wins_over_misconception(self) -> None:
        # 우선순위 확인 — 막힘(R1)이 오개념(R2)보다 앞선다.
        signals = StudentSignals(turn_count=5, misconception_ids=("sign-flip-error",))
        assert select(signals) is PedagogyStrategy.WORKED_EXAMPLE

    def test_select_is_deterministic(self) -> None:
        signals = StudentSignals(mastery_level="숙달", bkt_mastery=0.9)
        assert select(signals) is select(signals)


class TestColdWorkedExampleBlocked:
    """냉담 완전예제 차단 — 이 테스트가 깨지면 학생이 막힌 순간 정답을 받는다."""

    def test_concept_pack_blocks_worked_example_before_attempt(self) -> None:
        # 축① — CONCEPT 팩은 완전예제 선행을 금지한다. 시도 전(UNDERSTAND) 요청은 강등.
        pack = get_pack("CONCEPT")
        assert pack is not None
        signals = StudentSignals(polya_stage=PolyaStage.UNDERSTAND, hint_level=1)
        result = gate(PedagogyStrategy.WORKED_EXAMPLE, signals, pack=pack)

        assert result.allowed is False
        assert result.strategy is PedagogyStrategy.SOCRATIC  # 말하기 대신 묻기
        assert result.reason_code == REASON_PACK_FORBIDS_WORKED_FIRST
        assert result.requested is PedagogyStrategy.WORKED_EXAMPLE

    def test_stuck_without_hint_escalation_is_blocked(self) -> None:
        # 축② — 막혔는데 힌트가 안 올라갔으면 팩과 무관하게 차단.
        signals = StudentSignals(polya_stage=PolyaStage.EXECUTE, turn_count=5, hint_level=1)
        result = gate(PedagogyStrategy.WORKED_EXAMPLE, signals, pack=None)

        assert result.allowed is False
        assert result.strategy is PedagogyStrategy.SOCRATIC
        assert result.reason_code == REASON_HINT_NOT_ESCALATED

    def test_missing_pack_does_not_open_cold_delivery(self) -> None:
        # fail-safe — 팩 조회 실패가 냉담 제공을 열어주면 안 된다.
        signals = StudentSignals(polya_stage=PolyaStage.UNDERSTAND, turn_count=6, hint_level=None)
        result = gate(PedagogyStrategy.WORKED_EXAMPLE, signals, pack=None)
        assert result.allowed is False

    def test_end_to_end_stuck_student_never_gets_cold_answer(self) -> None:
        # decide() 합성 경로 — 막힌 개념형 학생은 완전예제를 받지 못한다.
        signals = StudentSignals(
            polya_stage=PolyaStage.UNDERSTAND, turn_count=5, hint_level=1, mastery_level="초보"
        )
        result = decide(signals, k_type="CONCEPT")
        assert result.strategy is not PedagogyStrategy.WORKED_EXAMPLE
        assert result.allowed is False


class TestEarnedWorkedExampleAllowed:
    """정당한 완전예제는 통과해야 한다 — 게이트가 과잉 차단이 아님을 확인(변별력의 반대 방향)."""

    def test_escalated_hint_allows_worked_example(self) -> None:
        # 축② 충족 — 방향(1)·흐름(2)을 거쳐 부분 시연(3)에 도달하면 열린다.
        signals = StudentSignals(polya_stage=PolyaStage.EXECUTE, turn_count=5, hint_level=3)
        result = gate(PedagogyStrategy.WORKED_EXAMPLE, signals, pack=None)
        assert result.allowed is True
        assert result.strategy is PedagogyStrategy.WORKED_EXAMPLE

    def test_procedure_pack_preserves_worked_example_entry(self) -> None:
        # PROCEDURE 팩은 완전예제 선행을 *의도*한다(fading_schedule) — 차단되면 설계 위반.
        pack = get_pack("PROCEDURE")
        assert pack is not None
        assert "WORKED_EXAMPLE_FIRST" not in pack.forbidden_modes  # 전제 실측
        signals = StudentSignals(polya_stage=PolyaStage.UNDERSTAND, hint_level=1)
        result = gate(PedagogyStrategy.WORKED_EXAMPLE, signals, pack=pack)
        assert result.allowed is True

    def test_non_worked_example_strategies_pass_through(self) -> None:
        pack = get_pack("CONCEPT")
        signals = StudentSignals(polya_stage=PolyaStage.UNDERSTAND)
        for strategy in (PedagogyStrategy.SOCRATIC, PedagogyStrategy.ANALOGY):
            result = gate(strategy, signals, pack=pack)
            assert result.allowed is True
            assert result.strategy is strategy


class TestGateDiscriminativePower:
    """변별력 — 게이트가 *실제로* 판정을 바꾸는지(성공/실패 양쪽에서 같은 값을 내면 위장이다).

    CLAUDE.md "변별력 없는 검증 스텝 금지"의 적용. 위 차단 테스트가 항상 통과하는 위장이 아님을
    확인한다.
    """

    def test_same_request_differs_by_hint_level_only(self) -> None:
        # 단 하나의 변수(hint_level)만 바꿨을 때 판정이 뒤집혀야 게이트가 의미를 갖는다.
        base = {"polya_stage": PolyaStage.EXECUTE, "turn_count": 5}
        blocked = gate(
            PedagogyStrategy.WORKED_EXAMPLE, StudentSignals(**base, hint_level=1), pack=None
        )
        allowed = gate(
            PedagogyStrategy.WORKED_EXAMPLE, StudentSignals(**base, hint_level=3), pack=None
        )
        assert blocked.allowed is False
        assert allowed.allowed is True

    def test_same_request_differs_by_pack_only(self) -> None:
        # 팩만 바꿨을 때 축①이 뒤집혀야 한다(CONCEPT 금지 vs PROCEDURE 허용).
        signals = StudentSignals(polya_stage=PolyaStage.UNDERSTAND, hint_level=1)
        concept = gate(PedagogyStrategy.WORKED_EXAMPLE, signals, pack=get_pack("CONCEPT"))
        procedure = gate(PedagogyStrategy.WORKED_EXAMPLE, signals, pack=get_pack("PROCEDURE"))
        assert concept.allowed is False
        assert procedure.allowed is True

    def test_stage_alone_flips_axis_one(self) -> None:
        # 같은 CONCEPT 팩이라도 시도 후(EXECUTE)면 "선행"이 아니므로 축①은 걸리지 않는다.
        pack = get_pack("CONCEPT")
        before = gate(
            PedagogyStrategy.WORKED_EXAMPLE,
            StudentSignals(polya_stage=PolyaStage.UNDERSTAND, hint_level=1),
            pack=pack,
        )
        after = gate(
            PedagogyStrategy.WORKED_EXAMPLE,
            StudentSignals(polya_stage=PolyaStage.EXECUTE, hint_level=1),
            pack=pack,
        )
        assert before.reason_code == REASON_PACK_FORBIDS_WORKED_FIRST
        assert after.allowed is True  # 막힘 신호도 없으므로 축②도 미적용


class TestStudentSignals:
    """L2 입력 소비 — 실재 신호만 담고, 파생 판정이 맞는지."""

    def test_consumes_l2_signals(self) -> None:
        signals = StudentSignals(
            mastery_level="발전 중",
            bkt_mastery=0.55,
            irt_theta=0.2,
            last_attempt_correct=False,
            time_vs_expected=1.8,
            used_hint=True,
            misconception_ids=("sign-flip-error",),
        )
        assert signals.bkt_mastery == 0.55
        assert signals.misconception_ids == ("sign-flip-error",)

    def test_absent_axes_have_no_fields(self) -> None:
        # 생산자 없는 축(집중도·학습시간·선호)은 필드를 만들지 않는다 — 가짜 통과 금지.
        fields = set(StudentSignals.__dataclass_fields__)
        assert not fields & {
            "focus_score",
            "engagement_score",
            "session_minutes",
            "preferred_solution_style",
        }

    def test_is_stuck_derivation(self) -> None:
        assert StudentSignals(hint_level=2).is_stuck is True
        assert StudentSignals(turn_count=5).is_stuck is True
        assert StudentSignals(hint_level=1, turn_count=1).is_stuck is False

    def test_hint_escalated_derivation(self) -> None:
        assert StudentSignals(hint_level=3).hint_escalated is True
        assert StudentSignals(hint_level=2).hint_escalated is False
        assert StudentSignals(hint_level=None).hint_escalated is False


class TestSelectorGovernance:
    """거버넌스 — 선택기가 렌더 불가 전략을 내면 호출자가 LookupError를 맞는다."""

    def test_select_output_is_renderable(self) -> None:
        # 대표 신호 조합 전수 — 모든 출력이 등록 어댑터 집합에 속해야 한다.
        cases = [
            StudentSignals(),
            StudentSignals(turn_count=5),
            StudentSignals(misconception_ids=("m1",)),
            StudentSignals(last_attempt_correct=False, mastery_level="초보"),
            StudentSignals(mastery_level="숙달"),
            StudentSignals(mastery_level="발전 중", last_attempt_correct=True),
        ]
        renderable = selectable_strategies()
        for signals in cases:
            assert select(signals) in renderable

    def test_gate_fallback_is_renderable(self) -> None:
        # 강등 대상(SOCRATIC)이 등록돼 있어야 폴백이 실패하지 않는다.
        assert PedagogyStrategy.SOCRATIC in selectable_strategies()

    def test_selectable_matches_render_registry(self) -> None:
        from whymath_backend.l3.render.registry import registered_strategies

        assert selectable_strategies() == registered_strategies()
