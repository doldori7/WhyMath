"""S3-08 진부분집합 전이 문맥 가드 — 2026-07-20 대본 측정 턴4 실측 픽스처·acceptance 동결(hermetic).

실측 확정 결함: 학생이 "이차방정식의 큰 근을 구하시오"에 정당한 풀이를 제출 —
    (x-2)(x-3)=0  →  x=2, x=3  →  x=3   (← 답 고르기·선택)
마지막 전이 {2,3}→{3}이 해집합 변화로 incorrect 판정 → "다시 살펴볼 지점이 있어요" 노출.
정당한 풀이를 틀렸다고 말하는 **거짓 incorrect**("거짓 판정 0" 계약 위반 실해악)였다.

원인: finite↔finite *진부분집합* 전이는 "답 선택"(정당)과 "근 유실"(오류·`x^2=4 → x=2`)이
구조적으로 동일해 문맥(기대정답) 없이 구별 불가. 방향(의사결정 우선순위 3 교수학 > 4 학습효과):
비어있지 않은 진부분집합 전이는 보수적으로 unverifiable — 검출 회복은 기대정답 앵커 후속
(`solset_transition_status` docstring 설계 노트).

동결 항목:
  ① Kiki 실측 픽스처 — `x=2, x=3 → x=3` 전이가 incorrect가 아님(unverifiable·턴4 재현).
  ② 작은 근 선택(`x=2, x=3 → x=2`)도 동일.
  ③ 비부분집합 오류({2,3}→{2,4} 원소 교체 등)는 여전히 incorrect — 검출 후퇴 없음 단언.
  ④ verify_solution 집계 수준에서도 대본 전체가 거짓 incorrect 0.
"""

from __future__ import annotations

from whymath_backend.l3.verify_solution import verify_solution
from whymath_backend.l3.verify_step import VerifyStepState, verify_step

# 2026-07-20 대본 측정 원문 — 문제: "이차방정식의 큰 근을 구하시오"(정당한 풀이 3단계).
SCRIPT_STEP1 = "(x-2)(x-3)=0"
SCRIPT_STEP2 = "x=2, x=3"
SCRIPT_STEP3 = "x=3"  # 답 고르기(선택) — 문항이 큰 근을 요구


class TestScriptTurn4Fixture:
    """① 턴4 재현 — 답 선택 전이가 거짓 incorrect가 아님(acceptance 핵심)."""

    def test_answer_selection_is_not_incorrect(self) -> None:
        # {2,3}→{3} 진부분집합 전이: 답 선택(정당)·근 유실(오류) 구별 불가 → unverifiable(보수).
        # S3-06까지는 해집합 변화로 incorrect였다 — 정당한 풀이에 거짓 판정이 노출된 실측 결함.
        result = verify_step(SCRIPT_STEP2, SCRIPT_STEP3)
        assert result.state == VerifyStepState.unverifiable
        assert result.state != VerifyStepState.incorrect
        assert result.evidence_weight == 0.5

    def test_smaller_root_selection_is_not_incorrect(self) -> None:
        # ② 작은 근 선택(x=2, x=3 → x=2)도 동일 — 진부분집합이면 어느 원소를 골라도 보수.
        result = verify_step(SCRIPT_STEP2, "x=2")
        assert result.state == VerifyStepState.unverifiable
        assert result.state != VerifyStepState.incorrect

    def test_factoring_to_roots_still_correct(self) -> None:
        # 대본 전이 1(인수분해 → 근 나열·{2,3} 보존)은 기존대로 correct — 회귀 없음.
        result = verify_step(SCRIPT_STEP1, SCRIPT_STEP2)
        assert result.state == VerifyStepState.correct
        assert result.evidence_weight == 1.0


class TestScriptAggregateZeroFalseIncorrect:
    """④ 집계 수준 — 대본 3단계 전체에서 거짓 incorrect 0(학생 UI 오노출 재발 방지)."""

    def test_full_script_has_zero_incorrect(self) -> None:
        aggregate = verify_solution([SCRIPT_STEP1, SCRIPT_STEP2, SCRIPT_STEP3])
        assert aggregate.n_transitions == 2
        assert aggregate.n_incorrect == 0
        assert aggregate.has_incorrect is False
        # 전이 1(인수분해→근 나열)은 결정론 correct 유지 — 보수화가 검증력을 통째로 죽이지 않음.
        assert aggregate.n_correct == 1
        assert aggregate.n_unverifiable == 1


class TestNonSubsetDetectionPreserved:
    """③ 비부분집합 오류 검출 유지 — 진부분집합 가드가 검출력을 후퇴시키지 않음 단언."""

    def test_element_swap_still_incorrect(self) -> None:
        # {2,3}→{2,4}(원소 교체·4 ∉ {2,3} — 진부분집합 아님) → 여전히 incorrect.
        result = verify_step(SCRIPT_STEP2, "x=2, x=4")
        assert result.state == VerifyStepState.incorrect
        assert result.evidence_weight == 1.0
        assert result.reason is not None
        assert "해집합 비보존" in result.reason

    def test_factored_to_wrong_roots_still_incorrect(self) -> None:
        # (x-2)(x-3)=0 → x=2, x=4 : 근 나열이 원집합과 다름(비부분집합) → incorrect 유지.
        result = verify_step(SCRIPT_STEP1, "x=2, x=4")
        assert result.state == VerifyStepState.incorrect

    def test_element_added_still_incorrect(self) -> None:
        # x=2 → x^2=2x : {2}→{0,2}(근 추가·superset — 진부분집합의 역방향) → incorrect 유지.
        result = verify_step("x=2", "x^2=2*x")
        assert result.state == VerifyStepState.incorrect

    def test_totally_different_root_still_incorrect(self) -> None:
        # 2x=6 → 2x=8 : {3}→{4}(전혀 다름) → incorrect 유지.
        result = verify_step("2x=6", "2x=8")
        assert result.state == VerifyStepState.incorrect
