"""순수 `verify_final_answer` 3상태 검증 단위테스트 — S3-32 learning-loop-closure.

correct(해집합 동치·SymPy 항등)·incorrect(비동치 확정·학생 제출 내부 모순)·unverifiable(빈
입력·파싱 불가·혼합 형태·기대정답 데이터 이상) 전수 + 환각 금지 회귀(unverifiable이 correct로
새지 않음) + 정답 비노출 회귀(`VerifyFinalAnswerResult`가 `state` 하나만 담음)를 확인한다.

`l3/verify_step.py` 재사용 재료(`l3/solution_set.py`·`l3/symbolic_equivalence.py`)는 이미
`tests/backend/l3/test_verify_step.py`·`test_solution_set.py`가 전수 검증했으므로, 여기서는
"최종답 동치 비교"라는 *용도*에 특화된 케이스(대칭 correct/incorrect 판정·정답 비노출)만 본다.
"""

from __future__ import annotations

import pytest

from whymath_backend.l3.verify_final_answer import (
    VerifyFinalAnswerResult,
    VerifyFinalAnswerState,
    verify_final_answer,
)


class TestCorrect:
    """학생 최종답 ≡ 기대정답 — correct."""

    def test_equation_solution_set_match(self) -> None:
        # 둘 다 등식 형태·같은 해집합({2}) — 해집합 보존 동치 경로(l3/solution_set.py).
        result = verify_final_answer("x=2", "x=2")
        assert result.state is VerifyFinalAnswerState.correct

    def test_equation_solution_set_match_different_surface_form(self) -> None:
        # 기대정답이 연쇄 등식(x=(1+3)/2)이어도 정규화되어 최초=최종 해집합({2})으로 접힌다.
        result = verify_final_answer("x=2", "x=(1+3)/2")
        assert result.state is VerifyFinalAnswerState.correct

    def test_plain_value_sympy_identity(self) -> None:
        # 둘 다 등식이 아닌 순수 값 — SymPy 항등 비교 경로(identity_status).
        result = verify_final_answer("2", "2")
        assert result.state is VerifyFinalAnswerState.correct

    def test_plain_value_equivalent_fraction(self) -> None:
        result = verify_final_answer("1/2", "0.5")
        assert result.state is VerifyFinalAnswerState.correct

    def test_roots_enumeration_match(self) -> None:
        # 근 나열(S3-06 ②) — 같은 변수 해집합 union 비교도 correct 경로.
        result = verify_final_answer("x=2, x=3", "x=2, x=3")
        assert result.state is VerifyFinalAnswerState.correct


class TestIncorrect:
    """학생 최종답 ≢ 기대정답 — incorrect(0-아님 확정 또는 해집합 비보존)."""

    def test_equation_solution_set_mismatch(self) -> None:
        result = verify_final_answer("x=3", "x=2")
        assert result.state is VerifyFinalAnswerState.incorrect

    def test_plain_value_sympy_not_identity(self) -> None:
        result = verify_final_answer("2+2", "5")
        assert result.state is VerifyFinalAnswerState.incorrect

    def test_student_internal_chain_contradiction_is_incorrect(self) -> None:
        # 학생 제출 자체의 연쇄 등식 내부 모순((1+3)/2≠3) — 기대정답과 무관하게 학생 진술이
        # 거짓으로 *증명*됨(verify_step S3-06 ①과 동형) → incorrect 승격이 안전하다.
        result = verify_final_answer("x=(1+3)/2=3", "x=2")
        assert result.state is VerifyFinalAnswerState.incorrect


class TestUnverifiable:
    """판정 불가 — *절대* correct로 낙관 판정하지 않는다(환각 금지 원칙)."""

    def test_empty_student_answer(self) -> None:
        result = verify_final_answer("", "x=2")
        assert result.state is VerifyFinalAnswerState.unverifiable

    def test_empty_expected_answer(self) -> None:
        result = verify_final_answer("x=2", "")
        assert result.state is VerifyFinalAnswerState.unverifiable

    def test_whitespace_only_inputs(self) -> None:
        result = verify_final_answer("   ", "x=2")
        assert result.state is VerifyFinalAnswerState.unverifiable

    def test_unparseable_student_answer(self) -> None:
        result = verify_final_answer("???", "x=2")
        assert result.state is VerifyFinalAnswerState.unverifiable

    def test_unparseable_expected_answer(self) -> None:
        result = verify_final_answer("x=2", "???")
        assert result.state is VerifyFinalAnswerState.unverifiable

    def test_mixed_form_equation_vs_plain_value(self) -> None:
        # 학생은 방정식 형태, 기대정답은 순수 값 — 비교 대상 불일치(verify_step 혼합 처리 동형).
        result = verify_final_answer("x=2", "2")
        assert result.state is VerifyFinalAnswerState.unverifiable

    def test_mixed_form_plain_value_vs_equation(self) -> None:
        result = verify_final_answer("2", "x=2")
        assert result.state is VerifyFinalAnswerState.unverifiable

    def test_expected_answer_internal_chain_contradiction_is_unverifiable(self) -> None:
        # 기대정답 데이터 자체가 내부 모순 연쇄(코퍼스 이상) — *학생 탓이 아니므로* incorrect로
        # 위장하지 않고 unverifiable로 보수 처리한다.
        result = verify_final_answer("x=2", "x=(1+3)/2=3")
        assert result.state is VerifyFinalAnswerState.unverifiable

    def test_different_free_symbols_is_unverifiable(self) -> None:
        # 변수 집합이 다른 치환(맥락 의존) — 거짓 incorrect 회피(verify_step 동형).
        result = verify_final_answer("a", "b+1")
        assert result.state is VerifyFinalAnswerState.unverifiable

    @pytest.mark.parametrize(
        ("student", "expected"),
        [
            ("", "x=2"),
            ("x=2", ""),
            ("???", "x=2"),
            ("x=2", "???"),
            ("x=2", "2"),
            ("2", "x=2"),
            ("x=2", "x=(1+3)/2=3"),
            ("a", "b+1"),
        ],
    )
    def test_never_optimistically_correct(self, student: str, expected: str) -> None:
        """환각 금지 회귀 — 판정 불가 케이스가 *절대* correct로 새지 않는다(CLAUDE.md).

        unverifiable을 correct로 낙관 판정하는 것은 CLAUDE.md 절대 금기다. 이 파라미터화
        테스트는 위 개별 unverifiable 케이스를 한데 모아 "correct가 아니다"만 명시적으로
        재확인한다(개별 테스트가 흔들려도 이 회귀 가드는 독립적으로 남는다).
        """
        result = verify_final_answer(student, expected)
        assert result.state is not VerifyFinalAnswerState.correct


class TestAnswerNotExposed:
    """정답 비노출 회귀 — `VerifyFinalAnswerResult`는 `state` 하나만 담는다(구조적 확인)."""

    def test_result_has_only_state_field(self) -> None:
        # 필드셋 자체를 구조적으로 확인 — 향후 누군가 `reason`처럼 값을 반향하는 필드를
        # 추가해도 이 테스트가 즉시 깨진다(정답 노출 위험을 코드리뷰 없이도 잡는 가드).
        assert set(VerifyFinalAnswerResult.model_fields.keys()) == {"state"}

    def test_expected_answer_value_not_echoed_anywhere(self) -> None:
        sentinel_expected = "x=424242"
        result = verify_final_answer("x=2", sentinel_expected)
        assert result.state is VerifyFinalAnswerState.incorrect
        dumped = result.model_dump_json()
        assert "424242" not in dumped

    def test_result_is_frozen(self) -> None:
        result = verify_final_answer("x=2", "x=2")
        with pytest.raises(Exception):  # noqa: B017 — pydantic ValidationError(frozen)
            result.state = VerifyFinalAnswerState.incorrect  # type: ignore[misc]
