"""L3→L4 오케스트레이터 단위테스트 (hermetic·순수 결정).

학생 풀이 텍스트 → L3 결정론 관계 검증(=·<·>·≤·≥·≠) → L4 검산 코칭 결선을 검증한다.
*결선 동작*(신호 유무 → arithmetic_error bool → focus)에 집중하고, 개별 검증기의 망라
검사는 `tests/backend/l3/test_pregenerate.py`가 책임진다.
"""

from __future__ import annotations

import logging
import uuid

import pytest

from whymath_backend.config import get_settings
from whymath_backend.l3.pregenerate.models import PregenItem, ValidationSignal
from whymath_backend.l4.metacognitive_trigger import recommend_coaching
from whymath_backend.l4.solution_coaching import (
    SolutionCoaching,
    recommend_coaching_for_solution,
)
from whymath_backend.schema.enums import StepType


class _AlwaysFails:
    """SeedValidator 충족 스텁 — 입력 무관 항상 신호 반환(주입 검증용).

    kind는 "other"(비표준 검증기) — 오케스트레이터가 `signal.kind`를 그대로 error_kind로
    노출하므로, 주입 스텁의 종류가 error_kind="other"로 검증된다(slice 59).
    """

    def validate(self, item: PregenItem | None, response: str) -> ValidationSignal | None:
        return ValidationSignal(kind="other", reason="stub: always fails")


class _AlwaysPasses:
    """SeedValidator 충족 스텁 — 입력 무관 항상 통과(주입 검증용)."""

    def validate(self, item: PregenItem | None, response: str) -> ValidationSignal | None:
        return None


class TestRecommendCoachingForSolution:
    def test_arithmetic_slip_routes_verify(self) -> None:
        """거짓 등식("2 + 3 = 6") → arithmetic_error·verify·신호 노출."""
        result = recommend_coaching_for_solution("2 + 3 = 6", 0.9, 2.0)
        assert result.arithmetic_error is True
        assert result.trigger.focus == "verify"
        assert result.validation_signal is not None
        assert "arithmetic error" in result.validation_signal

    def test_inequality_slip_routes_verify(self) -> None:
        """거짓 부등식("5 < 3") → arithmetic_error·verify(검증기 패밀리 결선 확인)."""
        result = recommend_coaching_for_solution("5 < 3", 0.9, 2.0)
        assert result.arithmetic_error is True
        assert result.trigger.focus == "verify"
        assert result.validation_signal is not None
        assert "inequality error" in result.validation_signal

    def test_prose_adjacent_slip_now_detected(self) -> None:
        """slice 54 — 한글 산문에 인접한 계산 슬립도 검출(한글=산문 경계).

        slice 52에서는 `_is_standalone`이 공백 건너뛴 뒤 한글(alnum)을 만나 보수적으로
        건너뛰었으나, slice 54가 한글을 *단어 경계*로 인식해 "따라서 2 + 3 = 6 이다."
        같은 한국어 풀이의 슬립도 verify로 잡는다(한국 학생 실사용 핵심).
        """
        result = recommend_coaching_for_solution("따라서 2 + 3 = 6 이다.", 0.9, 2.0)
        assert result.arithmetic_error is True
        assert result.trigger.focus == "verify"
        assert result.validation_signal is not None
        assert "arithmetic error" in result.validation_signal

    def test_not_equal_slip_routes_verify(self) -> None:
        """거짓 부등("12 / 4 ≠ 3", 유니코드 ≠ 정규화) → arithmetic_error·verify."""
        result = recommend_coaching_for_solution("12 / 4 ≠ 3", 0.9, 2.0)
        assert result.arithmetic_error is True
        assert result.trigger.focus == "verify"
        assert result.validation_signal is not None
        assert "not-equal error" in result.validation_signal

    def test_algebra_solution_slip_routes_verify(self) -> None:
        """slice 56 — 틀린 단변수 해("2x+1=7 이므로 x=5")도 verify로 처방(대수 슬립)."""
        result = recommend_coaching_for_solution("2x + 1 = 7 이므로 x = 5", 0.9, 2.0)
        assert result.arithmetic_error is True
        assert result.trigger.focus == "verify"
        assert result.validation_signal is not None
        assert "solution error" in result.validation_signal

    def test_clean_solution_high_mastery_advance(self) -> None:
        """참 등식("3 × 4 = 12")·고숙달 → arithmetic_error 없이 BKT↔IRT 경로(advance)."""
        result = recommend_coaching_for_solution("3 × 4 = 12 이므로 끝.", 0.9, 2.0)
        assert result.arithmetic_error is False
        assert result.validation_signal is None
        assert result.trigger.focus == "advance"

    def test_clean_solution_low_mastery_foundation(self) -> None:
        """참 계산·저숙달 합의 → foundation(계산오류 없으면 기존 코칭 그대로)."""
        result = recommend_coaching_for_solution("3 × 4 = 12", 0.5, 0.0)
        assert result.arithmetic_error is False
        assert result.trigger.focus == "foundation"

    def test_empty_solution_no_false_positive(self) -> None:
        """빈 풀이 → 위생 검사 없는 검증기라 신호 0(빈 풀이는 슬립이 아님)."""
        result = recommend_coaching_for_solution("", 0.1, 4.0)
        assert result.arithmetic_error is False
        assert result.validation_signal is None
        # 계산오류 없으니 BKT↔IRT 불일치 경로(맞히나 숙달↓) = consolidate.
        assert result.trigger.focus == "consolidate"

    def test_symbolic_solution_no_false_positive(self) -> None:
        """심볼릭 등식("x + 1 = 2") → 자유변수라 판정 불가(통과)·신호 0."""
        result = recommend_coaching_for_solution("x + 1 = 2 에서 x = 1", None, None)
        assert result.arithmetic_error is False
        assert result.validation_signal is None
        # 신호 둘 다 없음 → diagnose(교차검증 불가).
        assert result.trigger.focus == "diagnose"

    def test_slip_priority_over_low_mastery(self) -> None:
        """계산오류는 저숙달보다 우선 — foundation이 아니라 verify(슬립 vs 오개념)."""
        result = recommend_coaching_for_solution("2 + 3 = 6", 0.1, -2.0)
        assert result.arithmetic_error is True
        assert result.trigger.focus == "verify"

    def test_slip_priority_over_missing_signals(self) -> None:
        """신호가 둘 다 없어도 계산오류면 diagnose 아닌 verify(즉시 코칭)."""
        result = recommend_coaching_for_solution("2 + 3 = 6", None, None)
        assert result.arithmetic_error is True
        assert result.trigger.focus == "verify"

    def test_signal_matches_l3_validator_output(self) -> None:
        """노출 신호는 L3 검증기 출력 그대로 — 사유에 구체적 거짓 관계가 담긴다."""
        result = recommend_coaching_for_solution("2 + 3 = 6", 0.9, 2.0)
        assert result.validation_signal is not None
        # 거짓 등식의 좌우항과 SymPy 판정이 사유에 포함(L5가 어디가 어긋났는지 단서로 사용).
        assert "5 != 6" in result.validation_signal

    def test_custom_validator_injection_forces_error(self) -> None:
        """주입 검증기가 사유를 내면(풀이 내용 무관) arithmetic_error·verify."""
        result = recommend_coaching_for_solution("내용 무관", 0.9, 2.0, validator=_AlwaysFails())
        assert result.arithmetic_error is True
        assert result.trigger.focus == "verify"
        assert result.validation_signal == "stub: always fails"

    def test_custom_validator_injection_forces_pass(self) -> None:
        """주입 검증기가 통과시키면 거짓 등식이 있어도 신호 0(주입 우선)."""
        result = recommend_coaching_for_solution("2 + 3 = 6", 0.9, 2.0, validator=_AlwaysPasses())
        assert result.arithmetic_error is False
        assert result.validation_signal is None
        assert result.trigger.focus == "advance"

    def test_forwards_discrepancy_tol(self) -> None:
        """discrepancy_tol을 recommend_coaching에 위임 — 같은 차이도 분류가 바뀐다."""
        # 차 0.382(프록시 0.882 - 0.5): 기본 tol 0.2면 불일치(consolidate).
        assert recommend_coaching_for_solution("끝.", 0.5, 2.0).trigger.focus == "consolidate"
        # tol 0.5면 합의 → 평균 0.69 ≥ 0.6 → advance.
        assert (
            recommend_coaching_for_solution("끝.", 0.5, 2.0, discrepancy_tol=0.5).trigger.focus
            == "advance"
        )

    def test_forwards_mastery_threshold(self) -> None:
        """mastery_threshold 위임 — 합의 시 기초/심화 임계 조정."""
        # 합의(BKT 0.5·θ=0 프록시 0.5)·평균 0.5: 기본 임계 0.6이면 foundation.
        assert recommend_coaching_for_solution("끝.", 0.5, 0.0).trigger.focus == "foundation"
        # 임계 0.4로 낮추면 0.5 ≥ 0.4 → advance.
        assert (
            recommend_coaching_for_solution("끝.", 0.5, 0.0, mastery_threshold=0.4).trigger.focus
            == "advance"
        )

    def test_orchestrator_matches_manual_wiring(self) -> None:
        """오케스트레이터 = L3 신호→bool→recommend_coaching의 *동치* (결선 정합 증명)."""
        clean = recommend_coaching_for_solution("3 × 4 = 12", 0.9, 2.0)
        assert clean.trigger == recommend_coaching(0.9, 2.0, arithmetic_error=False)
        slip = recommend_coaching_for_solution("2 + 3 = 6", 0.9, 2.0)
        assert slip.trigger == recommend_coaching(0.9, 2.0, arithmetic_error=True)

    def test_deterministic(self) -> None:
        """같은 입력 → 같은 결정(순수)."""
        a = recommend_coaching_for_solution("2 + 3 = 6", 0.3, 1.0)
        b = recommend_coaching_for_solution("2 + 3 = 6", 0.3, 1.0)
        assert a == b

    def test_result_is_frozen(self) -> None:
        """SolutionCoaching은 불변(frozen)."""
        result = recommend_coaching_for_solution("2 + 3 = 6", 0.9, 2.0)
        assert isinstance(result, SolutionCoaching)
        try:
            result.arithmetic_error = False  # type: ignore[misc]
        except Exception as exc:  # pydantic ValidationError(frozen)
            assert "frozen" in str(exc).lower() or "instance" in str(exc).lower()
        else:  # pragma: no cover
            raise AssertionError("frozen 모델이 변경을 허용함")


class TestErrorKindClassification:
    """슬립 종류 분류 — 검증기가 `ValidationSignal.kind`로 직접 선언(slice 58→59). L5/L7용."""

    def test_arithmetic_kind(self) -> None:
        assert recommend_coaching_for_solution("2 + 3 = 6", 0.9, 2.0).error_kind == "arithmetic"

    def test_inequality_kind(self) -> None:
        assert recommend_coaching_for_solution("5 < 3", 0.9, 2.0).error_kind == "inequality"

    def test_not_equal_kind(self) -> None:
        assert recommend_coaching_for_solution("12 / 4 ≠ 3", 0.9, 2.0).error_kind == "not_equal"

    def test_solution_kind(self) -> None:
        result = recommend_coaching_for_solution("2x + 1 = 7 이므로 x = 5", 0.9, 2.0)
        assert result.error_kind == "solution"

    def test_no_error_kind_none(self) -> None:
        # 오류 없음 → error_kind None(arithmetic_error False와 정합).
        result = recommend_coaching_for_solution("3 × 4 = 12", 0.9, 2.0)
        assert result.arithmetic_error is False
        assert result.error_kind is None

    def test_unknown_signal_classified_other(self) -> None:
        # 비표준 검증기(kind="other" 선언) → error_kind="other"(검증기 선언 그대로).
        result = recommend_coaching_for_solution("내용", 0.9, 2.0, validator=_AlwaysFails())
        assert result.arithmetic_error is True
        assert result.error_kind == "other"


class TestErrorSpan:
    """slice 60 — 오류 위치 span 노출(`ValidationSignal.span` → `error_span`·L5 하이라이트)."""

    def test_arithmetic_span_points_at_relation(self) -> None:
        # 한글 산문 속 거짓 관계도 span은 *관계만* 가리킨다.
        text = "따라서 2 + 3 = 6 이다"
        result = recommend_coaching_for_solution(text, 0.9, 2.0)
        assert result.error_span is not None
        s, e = result.error_span
        assert text[s:e] == "2 + 3 = 6"

    def test_solution_span_points_at_claim(self) -> None:
        # 대수 슬립은 틀린 *해 주장*("x = 5")을 가리킨다(방정식 아님).
        text = "2x + 1 = 7 이므로 x = 5"
        result = recommend_coaching_for_solution(text, 0.9, 2.0)
        assert result.error_span is not None
        s, e = result.error_span
        assert text[s:e] == "x = 5"

    def test_no_error_span_none(self) -> None:
        # 오류 없음 → error_span None(arithmetic_error False와 정합).
        result = recommend_coaching_for_solution("3 × 4 = 12", 0.9, 2.0)
        assert result.arithmetic_error is False
        assert result.error_span is None

    def test_unicode_span_none_but_kind_set(self) -> None:
        # 유니코드 ≤는 1→2 정규화라 span=None(가드)이나 error_kind는 정상(slice 59b 계승).
        result = recommend_coaching_for_solution("5 ≤ 3", 0.9, 2.0)
        assert result.error_kind == "inequality"
        assert result.error_span is None


class TestStepVerifyPrompt:
    """slice 61 — solution 슬립(다단계 대수)일 때만 verify 발화가 단계 자가검산으로 변형."""

    def test_solution_slip_uses_step_self_check(self) -> None:
        # 대수 슬립(kind="solution") → 단계 자가검산 prompt(위치 비지목).
        result = recommend_coaching_for_solution("2x + 1 = 7 이므로 x = 5", 0.9, 2.0)
        assert result.error_kind == "solution"
        assert result.trigger.focus == "verify"
        assert "한 줄씩" in result.trigger.prompt

    def test_arithmetic_slip_keeps_generic_verify(self) -> None:
        # 순수 수치 슬립(kind="arithmetic") → 기존 계산 검산 prompt(단계 변형 아님).
        result = recommend_coaching_for_solution("2 + 3 = 6", 0.9, 2.0)
        assert result.error_kind == "arithmetic"
        assert result.trigger.focus == "verify"
        assert "숫자가 어긋났는지" in result.trigger.prompt
        assert "한 줄씩" not in result.trigger.prompt

    def test_inequality_slip_keeps_generic_verify(self) -> None:
        # 부등식 슬립도 단계 변형 아님(solution kind만 변형).
        result = recommend_coaching_for_solution("5 < 3", 0.9, 2.0)
        assert result.error_kind == "inequality"
        assert "한 줄씩" not in result.trigger.prompt


class TestSolutionStepsWiring:
    """WH-1 1단계 결선 — `solution_steps` 제공 시 verify_solution 연쇄 검증을 OR 결합.

    텍스트→단계 *분해*는 L5 책임(범위 밖)이라 여기선 *이미 분해된* 표현식 리스트를 직접 준다.
    """

    def test_incorrect_steps_route_verify(self) -> None:
        """단계 시퀀스에 incorrect 전이 → arithmetic_error·verify·solution_verification 채워짐."""
        # 텍스트는 깨끗(슬립 없음)·고숙달이라 단계 없으면 advance지만, 단계 incorrect가 verify로.
        result = recommend_coaching_for_solution(
            "풀이", 0.9, 2.0, solution_steps=["2*x + 4", "2*x + 5"]
        )
        assert result.arithmetic_error is True
        assert result.trigger.focus == "verify"
        assert result.solution_verification is not None
        assert result.solution_verification.has_incorrect is True
        assert result.solution_verification.first_incorrect_index == 0

    def test_incorrect_steps_use_step_self_check_prompt(self) -> None:
        """단계 레벨 incorrect → verify 발화가 단계 자가검산 변형(verify_steps OR)."""
        result = recommend_coaching_for_solution(
            "풀이", 0.9, 2.0, solution_steps=["x + 1", "x + 1", "x + 2"]
        )
        assert result.trigger.focus == "verify"
        assert "한 줄씩" in result.trigger.prompt
        assert result.solution_verification is not None
        assert result.solution_verification.first_incorrect_index == 1

    def test_incorrect_steps_position_aware_prompt(self) -> None:
        """단계 incorrect → 발화가 *위치 인지*(앞단계 확인+그 지점 재검산)·focus_step_index 전달."""
        # 전이 1(steps[1]→steps[2])이 incorrect → 2줄 통과(k=2)·3번째 줄 재검산(m=3).
        result = recommend_coaching_for_solution(
            "풀이", 0.9, 2.0, solution_steps=["x + 1", "x + 1", "x + 2"]
        )
        assert result.trigger.focus == "verify"
        assert result.solution_verification is not None
        assert result.solution_verification.first_incorrect_index == 1
        # 위치 인지 발화 + 구조화 메타데이터(first_incorrect_index 그대로).
        assert "잘 따라왔어" in result.trigger.prompt
        assert "처음 2줄까지는 잘 따라왔어" in result.trigger.prompt
        assert "3번째 줄" in result.trigger.prompt
        assert result.trigger.focus_step_index == 1
        # 교수학 금기 가드 — 정답·수정·'틀렸다' 부재.
        for forbidden in ("틀렸", "정답은", "고치", "수정", "="):
            assert forbidden not in result.trigger.prompt

    def test_text_only_slip_no_focus_step_index(self) -> None:
        """텍스트 슬립만(단계 미제공) → focus_step_index None·기존 일반 발화(하위호환)."""
        result = recommend_coaching_for_solution("2 + 3 = 6", 0.9, 2.0)
        assert result.trigger.focus == "verify"
        assert result.trigger.focus_step_index is None
        assert "잘 따라왔어" not in result.trigger.prompt

    def test_correct_steps_no_step_signal(self) -> None:
        """전부 correct 전이 → 단계 신호 없음(텍스트 신호만)
        ·verification은 채워지되 has_incorrect False."""
        result = recommend_coaching_for_solution(
            "풀이", 0.9, 2.0, solution_steps=["2*x + 4", "2*(x + 2)"]
        )
        assert result.arithmetic_error is False
        assert result.trigger.focus == "advance"  # 단계 신호 0 → 기존 BKT↔IRT 경로
        assert result.solution_verification is not None
        assert result.solution_verification.has_incorrect is False
        assert result.solution_verification.n_correct == 1

    def test_or_combination_text_clean_step_incorrect(self) -> None:
        """OR 결합 — 텍스트 OK여도 단계 incorrect면 verify(추가적·기존 신호 약화 안 함)."""
        # 텍스트 신호 없음(validation_signal None) + 단계 incorrect → arithmetic_error True.
        result = recommend_coaching_for_solution(
            "풀이", 0.9, 2.0, solution_steps=["2*x + 4", "2*x + 5"]
        )
        assert result.validation_signal is None  # 텍스트 레벨 신호 없음
        assert result.error_kind is None  # 텍스트 슬립 없음(단계 신호는 error_kind를 안 채움)
        assert result.arithmetic_error is True  # 단계 incorrect가 OR로 추가
        assert result.trigger.focus == "verify"

    def test_or_combination_text_slip_steps_correct(self) -> None:
        """OR 결합 — 텍스트 슬립이 있으면 단계가 correct여도 텍스트 신호 보존(약화 안 함)."""
        result = recommend_coaching_for_solution("2 + 3 = 6", 0.9, 2.0, solution_steps=["x", "x"])
        assert result.arithmetic_error is True
        assert result.error_kind == "arithmetic"  # 텍스트 신호 그대로 보존
        assert result.validation_signal is not None
        assert result.solution_verification is not None
        assert result.solution_verification.has_incorrect is False

    def test_steps_not_provided_fully_unchanged(self) -> None:
        """단계 미제공 → solution_verification None·기존 동작 완전 불변(하위호환)."""
        with_steps = recommend_coaching_for_solution("3 × 4 = 12 이므로 끝.", 0.9, 2.0)
        assert with_steps.solution_verification is None
        assert with_steps.arithmetic_error is False
        assert with_steps.trigger.focus == "advance"
        # 단계 None 명시도 동일(완전 불변).
        explicit = recommend_coaching_for_solution(
            "3 × 4 = 12 이므로 끝.", 0.9, 2.0, solution_steps=None
        )
        assert explicit == with_steps

    def test_single_step_no_transition_verification_none(self) -> None:
        """단계 1개(전이 0) → verification None(검증할 전이 없음)·기존 동작 불변."""
        result = recommend_coaching_for_solution("풀이", 0.9, 2.0, solution_steps=["2*x + 4"])
        assert result.solution_verification is None
        assert result.arithmetic_error is False
        assert result.trigger.focus == "advance"

    def test_step_types_forwarded(self) -> None:
        """solution_step_types 전달
        — 비대수 단계는 unverifiable로 보수 처리(거짓 incorrect 회피)."""
        # 케이스분류 전이는 SymPy 검증 안 함 → unverifiable(incorrect 아님).
        result = recommend_coaching_for_solution(
            "풀이",
            0.9,
            2.0,
            solution_steps=["2*x + 4", "2*x + 5"],
            solution_step_types=[StepType.케이스분류],
        )
        assert result.solution_verification is not None
        assert result.solution_verification.has_incorrect is False
        assert result.solution_verification.n_unverifiable == 1
        assert result.arithmetic_error is False  # 단계 신호 없음 → 기존 경로

    def test_solution_verification_deterministic(self) -> None:
        """같은 단계 입력 → 같은 결과(순수)."""
        a = recommend_coaching_for_solution("풀이", 0.3, 1.0, solution_steps=["2*x + 4", "2*x + 5"])
        b = recommend_coaching_for_solution("풀이", 0.3, 1.0, solution_steps=["2*x + 4", "2*x + 5"])
        assert a == b


class TestOcrConfidenceGating:
    """WH-1 1단계 — 저신뢰 OCR이면 step-incorrect 신호를 verify 코칭에서 누그러뜨린다.

    분해 단계 텍스트가 OCR 오인식일 수 있어, verify가 낸 incorrect가 *학생 오류가 아니라 OCR
    오류*일 수 있다(정확성 #1·거짓 지적 방지). 저신뢰 OCR이면 결정에서 보류하되 원 verdict는
    투명성 위해 노출하고 `verification_ocr_gated`로 보류 사실을 정직히 알린다. 텍스트 레벨 신호는
    게이팅하지 않는다(OCR 분해와 무관).
    """

    def test_low_confidence_suppresses_step_signal(self) -> None:
        """incorrect 단계 + 저신뢰 OCR(0.5) → step 기인 arithmetic_error 안 됨·verify 아님."""
        result = recommend_coaching_for_solution(
            "풀이", 0.9, 2.0, solution_steps=["2*x + 4", "2*x + 5"], ocr_confidence=0.5
        )
        # 텍스트 신호 없음 + 저신뢰 OCR로 step 보류 → arithmetic_error False(고숙달 advance).
        assert result.arithmetic_error is False
        assert result.trigger.focus != "verify"
        assert result.trigger.focus == "advance"

    def test_low_confidence_no_position_pointing(self) -> None:
        """저신뢰 OCR → incorrect_step_index/위치 발화 없음(거짓 위치 지목 방지)."""
        result = recommend_coaching_for_solution(
            "풀이", 0.9, 2.0, solution_steps=["x + 1", "x + 1", "x + 2"], ocr_confidence=0.5
        )
        assert result.trigger.focus_step_index is None
        assert "잘 따라왔어" not in result.trigger.prompt
        assert "번째 줄" not in result.trigger.prompt

    def test_low_confidence_sets_ocr_gated_flag(self) -> None:
        """저신뢰 OCR + step incorrect → verification_ocr_gated True(보류 사실 노출)."""
        result = recommend_coaching_for_solution(
            "풀이", 0.9, 2.0, solution_steps=["2*x + 4", "2*x + 5"], ocr_confidence=0.5
        )
        assert result.verification_ocr_gated is True

    def test_low_confidence_preserves_raw_verdict(self) -> None:
        """투명성 — 보류해도 solution_verification 원 verdict는 has_incorrect True 그대로."""
        result = recommend_coaching_for_solution(
            "풀이", 0.9, 2.0, solution_steps=["2*x + 4", "2*x + 5"], ocr_confidence=0.5
        )
        assert result.solution_verification is not None
        assert result.solution_verification.has_incorrect is True
        assert result.solution_verification.first_incorrect_index == 0

    def test_high_confidence_keeps_verify(self) -> None:
        """고신뢰 OCR(0.9) → 기존대로 verify·위치 발화·gated False."""
        result = recommend_coaching_for_solution(
            "풀이", 0.9, 2.0, solution_steps=["x + 1", "x + 1", "x + 2"], ocr_confidence=0.9
        )
        assert result.arithmetic_error is True
        assert result.trigger.focus == "verify"
        assert result.trigger.focus_step_index == 1
        assert "잘 따라왔어" in result.trigger.prompt
        assert result.verification_ocr_gated is False

    def test_confidence_none_unchanged(self) -> None:
        """OCR 미제공(None) → 기존 동작 완전 불변(verify·위치)·gated False(하위호환)."""
        baseline = recommend_coaching_for_solution(
            "풀이", 0.9, 2.0, solution_steps=["x + 1", "x + 1", "x + 2"]
        )
        explicit = recommend_coaching_for_solution(
            "풀이", 0.9, 2.0, solution_steps=["x + 1", "x + 1", "x + 2"], ocr_confidence=None
        )
        # 미제공 = None 명시 → 완전 동일(gated 포함).
        assert explicit == baseline
        assert explicit.arithmetic_error is True
        assert explicit.trigger.focus == "verify"
        assert explicit.trigger.focus_step_index == 1
        assert explicit.verification_ocr_gated is False

    def test_text_signal_not_gated_by_low_ocr(self) -> None:
        """텍스트 거짓 등식 + 저신뢰 OCR → 텍스트 신호는 *여전히* verify(게이팅 안 됨)."""
        # 텍스트 슬립("2 + 3 = 6") + 저신뢰 OCR + step도 incorrect.
        result = recommend_coaching_for_solution(
            "2 + 3 = 6", 0.9, 2.0, solution_steps=["x", "x + 1"], ocr_confidence=0.5
        )
        # 텍스트 신호는 OCR 분해와 무관 → 게이팅 안 됨 → verify 유지.
        assert result.arithmetic_error is True
        assert result.trigger.focus == "verify"
        assert result.error_kind == "arithmetic"
        assert result.validation_signal is not None
        # step은 저신뢰로 보류됐으나(verification_ocr_gated) verdict는 노출.
        assert result.verification_ocr_gated is True
        assert result.solution_verification is not None
        assert result.solution_verification.has_incorrect is True

    def test_threshold_boundary_exactly_at_floor(self) -> None:
        """임계 경계(0.8) — 정확히 0.8은 *신뢰*(< 0.8만 저신뢰)·0.79는 저신뢰."""
        at_floor = recommend_coaching_for_solution(
            "풀이", 0.9, 2.0, solution_steps=["2*x + 4", "2*x + 5"], ocr_confidence=0.8
        )
        # 0.8은 임계 *미만*이 아님 → 신뢰 → verify·gated False.
        assert at_floor.arithmetic_error is True
        assert at_floor.trigger.focus == "verify"
        assert at_floor.verification_ocr_gated is False
        below = recommend_coaching_for_solution(
            "풀이", 0.9, 2.0, solution_steps=["2*x + 4", "2*x + 5"], ocr_confidence=0.79
        )
        # 0.79는 임계 미만 → 저신뢰 → 보류·gated True.
        assert below.arithmetic_error is False
        assert below.verification_ocr_gated is True

    def test_correct_steps_low_ocr_not_gated(self) -> None:
        """전부 correct 단계 + 저신뢰 OCR → 보류할 신호 없음·gated False(step-incorrect 없음)."""
        result = recommend_coaching_for_solution(
            "풀이", 0.9, 2.0, solution_steps=["2*x + 4", "2*(x + 2)"], ocr_confidence=0.5
        )
        assert result.verification_ocr_gated is False
        assert result.solution_verification is not None
        assert result.solution_verification.has_incorrect is False

    def test_gated_deterministic(self) -> None:
        """같은 저신뢰 OCR 입력 → 같은 결과(순수)."""
        a = recommend_coaching_for_solution(
            "풀이", 0.3, 1.0, solution_steps=["2*x + 4", "2*x + 5"], ocr_confidence=0.5
        )
        b = recommend_coaching_for_solution(
            "풀이", 0.3, 1.0, solution_steps=["2*x + 4", "2*x + 5"], ocr_confidence=0.5
        )
        assert a == b


class TestStepShadowNonExposure:
    """slice 63 — 중간 step shadow 관측이 SolutionCoaching 반환을 *바꾸지 않음*(비노출)."""

    def test_result_identical_gate_on_vs_off(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # 단계 비보존 입력(shadow가 검출)에도 반환은 게이트 on/off 무관하게 동일(반환 무반영).
        text = "2x = 6 따라서 3x = 12"
        monkeypatch.setenv("WHYMATH_L4_STEP_SHADOW_ENABLED", "false")
        get_settings.cache_clear()
        try:
            off = recommend_coaching_for_solution(text, 0.9, 2.0)
        finally:
            get_settings.cache_clear()
        monkeypatch.setenv("WHYMATH_L4_STEP_SHADOW_ENABLED", "true")
        get_settings.cache_clear()
        try:
            on = recommend_coaching_for_solution(text, 0.9, 2.0)
        finally:
            get_settings.cache_clear()
        assert on == off  # shadow는 None 반환·result 불변 — 게이트가 반환을 못 바꾼다

    def test_problem_context_does_not_change_result(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # slice 64: problem_id·expected_answer를 줘도 반환은 *동일*(맥락은 shadow 로그로만 흐름·
        # 특히 expected_answer는 응답에 안 실림 = 정답 누출 차단).
        text = "2x = 6 따라서 3x = 12"
        monkeypatch.setenv("WHYMATH_L4_STEP_SHADOW_ENABLED", "true")
        get_settings.cache_clear()
        pid = uuid.UUID("00000000-0000-0000-0000-0000000000bb")
        try:
            without = recommend_coaching_for_solution(text, 0.9, 2.0)
            with_ctx = recommend_coaching_for_solution(
                text, 0.9, 2.0, problem_id=pid, expected_answer="x = 3"
            )
        finally:
            get_settings.cache_clear()
        assert with_ctx == without

    def test_problem_context_reaches_shadow_log(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        # slice 64: 오케스트레이터가 맥락을 observe_step_breaks로 전달 → shadow 로그에 도달(결선).
        text = "2x = 6 따라서 3x = 12"
        monkeypatch.setenv("WHYMATH_L4_STEP_SHADOW_ENABLED", "true")
        get_settings.cache_clear()
        pid = uuid.UUID("00000000-0000-0000-0000-0000000000cc")
        try:
            with caplog.at_level(logging.INFO, logger="whymath.l4.step_shadow"):
                recommend_coaching_for_solution(
                    text, 0.9, 2.0, problem_id=pid, expected_answer="x = 3"
                )
            msgs = [r.getMessage() for r in caplog.records if r.name == "whymath.l4.step_shadow"]
            assert any(str(pid) in m and "expected='x = 3'" in m for m in msgs)
        finally:
            get_settings.cache_clear()


class TestHintLevelEscalation:
    """hint 점층 결선 — `hint_level`을 `recommend_coaching`에 위임(단계 자가검산 3·4 점층)."""

    # step-incorrect 시퀀스(2x+4 ≠ 2x+5) → verify_steps=True 경로(점층 대상).
    _STEPS = ["2*x + 4", "2*x + 5"]

    def test_hint_level_none_keeps_step_prompt(self) -> None:
        """hint_level 미제공 → 단계 자가검산 발화 불변·trigger.hint_level None(하위호환)."""
        base = recommend_coaching_for_solution("풀이", 0.9, 2.0, solution_steps=self._STEPS)
        assert base.trigger.focus == "verify"
        assert base.trigger.hint_level is None
        assert "어떤 규칙" not in base.trigger.prompt  # 점층 아님

    def test_hint_level_3_4_escalates_step_prompt(self) -> None:
        """verify_steps + hint_level 3·4 → 과정 재구성 비계 점층·trigger.hint_level 전달."""
        base = recommend_coaching_for_solution("풀이", 0.9, 2.0, solution_steps=self._STEPS)
        for level in (3, 4):
            esc = recommend_coaching_for_solution(
                "풀이", 0.9, 2.0, solution_steps=self._STEPS, hint_level=level  # type: ignore[arg-type]
            )
            assert esc.trigger.focus == "verify"
            assert esc.trigger.hint_level == level
            assert esc.trigger.prompt != base.trigger.prompt  # 점층으로 바뀜
            assert "어떤 규칙" in esc.trigger.prompt

    def test_hint_level_1_2_no_escalation(self) -> None:
        """verify_steps + hint_level 1·2 → 발화 불변(점층 아님)·메타데이터만 채움."""
        base = recommend_coaching_for_solution("풀이", 0.9, 2.0, solution_steps=self._STEPS)
        for level in (1, 2):
            r = recommend_coaching_for_solution(
                "풀이", 0.9, 2.0, solution_steps=self._STEPS, hint_level=level  # type: ignore[arg-type]
            )
            assert r.trigger.prompt == base.trigger.prompt  # 발화 불변
            assert r.trigger.hint_level == level

    def test_hint_level_ignored_for_plain_arithmetic_slip(self) -> None:
        """단계 시퀀스 없는 순수 산술 슬립(verify_steps=False)은 hint_level 3이어도 점층 안 됨."""
        r = recommend_coaching_for_solution("2 + 3 = 6", 0.9, 2.0, hint_level=3)
        assert r.trigger.focus == "verify"
        assert "어떤 규칙" not in r.trigger.prompt  # verify_steps 경로 아님 → 점층 미적용
