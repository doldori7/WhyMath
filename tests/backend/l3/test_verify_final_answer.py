"""순수 `verify_final_answer` 3상태 검증 단위테스트 — 서버 권위 채점 primitive(S3-32·hermetic).

correct(학생 최종답 ≡ 기대정답·등식/자연표기/객관식)·incorrect(불일치 확정)·unverifiable(기대정답
미보유·빈 입력·판정 불가) + 데모형 정답 + 서버 정직성(unverifiable을 correct로 위장 안 함) 가드.

DB·네트워크 0(순수 함수). 서버 권위 *배선*(코치 완료 흐름)은 api/test_coach_completion.py가
검증한다 — 여긴 판정 primitive만.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from whymath_backend.l3.verify_final_answer import (
    FinalAnswerState,
    verify_final_answer,
)
from whymath_backend.schema.enums import QuestionFormat


def _prob(
    *,
    answer: str | None = None,
    choices: list[str] | None = None,
    question_format: Any = None,
    answer_format: Any = None,
    multiple_answers: dict[str, Any] | None = None,
) -> Any:
    """`verify_final_answer`가 읽는 필드만 담은 문항 스텁(duck-typed·ORM Problem 대역)."""
    return SimpleNamespace(
        answer=answer,
        choices=choices,
        question_format=question_format,
        answer_format=answer_format,
        multiple_answers=multiple_answers,
    )


class TestCorrect:
    """기본 정답 형태 — 등식/자연표기/객관식."""

    def test_larger_root_equation_form(self) -> None:
        # 기대정답 "3", 학생 "x=3"(등식 형태) → correct.
        result = verify_final_answer("x=3", _prob(answer="3"))
        assert result.state == FinalAnswerState.correct
        assert result.reason is None

    def test_smaller_root_equation_form(self) -> None:
        result = verify_final_answer("x=2", _prob(answer="2"))
        assert result.state == FinalAnswerState.correct

    def test_axis_answer_uses_variable_a(self) -> None:
        # 기대정답 "2", 학생 "a=2"(변수명 a) → correct(값 해집합 {2} 동일).
        result = verify_final_answer("a=2", _prob(answer="2"))
        assert result.state == FinalAnswerState.correct

    def test_root_count_mc_value(self) -> None:
        # 객관식, 기대정답 "2", 학생 "2" → correct.
        result = verify_final_answer(
            "2",
            _prob(answer="2", choices=["0", "1", "2", "3"], question_format=QuestionFormat.객관식),
        )
        assert result.state == FinalAnswerState.correct

    def test_root_count_mc_counter_suffix(self) -> None:
        # 학생이 "2개"로 답해도 수량 접미사 정규화로 정답 "2"와 correct.
        result = verify_final_answer(
            "2개",
            _prob(answer="2", choices=["0", "1", "2", "3"], question_format=QuestionFormat.객관식),
        )
        assert result.state == FinalAnswerState.correct


class TestNaturalNotation:
    """자연 표기 변형 — 학생이 실제로 쓰는 연쇄 등식·맨 표현식."""

    def test_chained_equation_natural(self) -> None:
        # "x=(5+1)/2=3" — 연쇄 등식(내부 참: (5+1)/2=3)이 x=3으로 정규화 → 기대정답 3과 correct.
        result = verify_final_answer("x=(5+1)/2=3", _prob(answer="3"))
        assert result.state == FinalAnswerState.correct

    def test_bare_number_matches(self) -> None:
        # 맨 표현식 "3" ≡ 기대정답 "3"(앵커 등식 값 해집합 {3}).
        result = verify_final_answer("3", _prob(answer="3"))
        assert result.state == FinalAnswerState.correct

    def test_arithmetic_expression_evaluates(self) -> None:
        # "(1+3)/2" = 2 ≡ 기대정답 "2"(수치 평가 동치).
        result = verify_final_answer("(1+3)/2", _prob(answer="2"))
        assert result.state == FinalAnswerState.correct

    def test_fraction_equation_form(self) -> None:
        # "x=1/2" ≡ 기대정답 "1/2"(유리수 해집합 동일).
        result = verify_final_answer("x=1/2", _prob(answer="1/2"))
        assert result.state == FinalAnswerState.correct

    def test_negative_value(self) -> None:
        result = verify_final_answer("x=-3", _prob(answer="-3"))
        assert result.state == FinalAnswerState.correct

    def test_chained_equation_internal_violation_not_correct(self) -> None:
        # "x=(1+3)/2=3" — (1+3)/2=2≠3(내부 모순) → 값 추출 보류 → correct 아님(정직).
        result = verify_final_answer("x=(1+3)/2=3", _prob(answer="3"))
        assert result.state != FinalAnswerState.correct


class TestIncorrect:
    """불일치 확정 → incorrect(서버가 오답을 확인)."""

    def test_wrong_value_equation(self) -> None:
        # 기대정답 "3", 학생 "x=5" → 값 해집합 {5}≠{3} → incorrect.
        result = verify_final_answer("x=5", _prob(answer="3"))
        assert result.state == FinalAnswerState.incorrect
        assert result.reason is not None
        assert "3" not in (result.reason or "")  # 기대정답 원문 미노출(사유엔 학생 원문만)

    def test_wrong_bare_number(self) -> None:
        result = verify_final_answer("7", _prob(answer="2"))
        assert result.state == FinalAnswerState.incorrect

    def test_mc_other_choice_is_incorrect(self) -> None:
        # 객관식 기대정답 "2", 학생 "1"(다른 선택지 값) → incorrect.
        result = verify_final_answer(
            "1",
            _prob(answer="2", choices=["0", "1", "2", "3"], question_format=QuestionFormat.객관식),
        )
        assert result.state == FinalAnswerState.incorrect

    def test_mc_counter_suffix_wrong(self) -> None:
        # "3개" → "3" ≠ 정답 "2" → incorrect.
        result = verify_final_answer(
            "3개",
            _prob(answer="2", choices=["0", "1", "2", "3"], question_format=QuestionFormat.객관식),
        )
        assert result.state == FinalAnswerState.incorrect


class TestUnverifiable:
    """서버 검증 불가 → unverifiable(정직 — 절대 correct 위장 안 함, 절대 optimistic-correct 없음)."""

    def test_no_expected_answer(self) -> None:
        # 기대정답 미보유(서술형·본문 미보유 출처 등) → unverifiable.
        result = verify_final_answer("x=3", _prob(answer=None))
        assert result.state == FinalAnswerState.unverifiable

    def test_empty_expected_answer(self) -> None:
        result = verify_final_answer("x=3", _prob(answer="   "))
        assert result.state == FinalAnswerState.unverifiable

    def test_empty_student_answer(self) -> None:
        result = verify_final_answer("   ", _prob(answer="3"))
        assert result.state == FinalAnswerState.unverifiable

    def test_none_student_answer(self) -> None:
        result = verify_final_answer(None, _prob(answer="3"))
        assert result.state == FinalAnswerState.unverifiable

    def test_none_problem(self) -> None:
        # 문항 미조회(session.get→None) → unverifiable(호출자 클라 폴백).
        result = verify_final_answer("x=3", None)
        assert result.state == FinalAnswerState.unverifiable

    def test_unparseable_student_answer_not_correct(self) -> None:
        # 파싱 불가 텍스트 답 → correct로 위장하지 않는다(정직·incorrect도 아님).
        result = verify_final_answer("잘 모르겠어요", _prob(answer="3"))
        assert result.state == FinalAnswerState.unverifiable

    def test_partial_roots_is_unverifiable(self) -> None:
        # 기대정답이 두 근(x=2, x=3)인데 학생이 한 근만(x=2) → 진부분집합 가드 → unverifiable
        # (답 선택 vs 근 유실 구별 불가·거짓 incorrect 회피). correct는 아니다.
        result = verify_final_answer("x=2", _prob(answer="x=2, x=3"))
        assert result.state == FinalAnswerState.unverifiable

    def test_never_optimistic_correct_across_many_unverifiable_inputs(self) -> None:
        # unverifiable을 correct로 낙관 판정하는 경로가 없음을 여러 입력에 걸쳐 재확인(회귀 가드).
        unverifiable_cases: list[tuple[str | None, Any]] = [
            (None, _prob(answer="3")),
            ("", _prob(answer="3")),
            ("   ", _prob(answer="3")),
            ("x=3", _prob(answer=None)),
            ("x=3", _prob(answer="")),
            ("x=3", None),
            ("모르겠어요 이해가 안 돼요", _prob(answer="3")),
        ]
        for student, problem in unverifiable_cases:
            result = verify_final_answer(student, problem)
            assert result.state != FinalAnswerState.correct
            assert result.state == FinalAnswerState.unverifiable


class TestExpressionAnswer:
    """식 정답(answer_format '식') — 값 해집합 대신 표현식 심볼릭 동치 폴백."""

    def test_expression_equivalent(self) -> None:
        # 기대정답 "2x+1", 학생 "2*x+1"(암묵곱·동치) → correct.
        result = verify_final_answer("2*x+1", _prob(answer="2x+1"))
        assert result.state == FinalAnswerState.correct

    def test_expression_distributed_equivalent(self) -> None:
        # "2(x+1)" ≡ 기대정답 "2x+2" → correct(전개 동치).
        result = verify_final_answer("2(x+1)", _prob(answer="2x+2"))
        assert result.state == FinalAnswerState.correct

    def test_expression_wrong(self) -> None:
        # "2x+2" ≠ 기대정답 "2x+1"(상수 차 확정) → incorrect.
        result = verify_final_answer("2x+2", _prob(answer="2x+1"))
        assert result.state == FinalAnswerState.incorrect


class TestRootsEnumeration:
    """근 나열(두 근 모두 요구) — 해집합 union 동치."""

    def test_both_roots_correct_reordered(self) -> None:
        # 기대정답 "x=2, x=3", 학생 "x=3, x=2"(순서 무관) → correct(해집합 {2,3} 동일).
        result = verify_final_answer("x=3, x=2", _prob(answer="x=2, x=3"))
        assert result.state == FinalAnswerState.correct

    def test_extra_root_incorrect(self) -> None:
        # 기대정답 "x=2, x=3", 학생 "x=2, x=4"(원소 교체·부분집합 아님) → incorrect.
        result = verify_final_answer("x=2, x=4", _prob(answer="x=2, x=3"))
        assert result.state == FinalAnswerState.incorrect


class TestMultipleAnswers:
    """multiple_answers(복수해·출제오류 검증 JSONB) — 추가 정답 허용(넓히기 전용)."""

    def test_alternate_answer_accepted(self) -> None:
        # 기대정답 "3"이나 multiple_answers에 "5"도 유효 → 학생 "x=5" correct.
        result = verify_final_answer(
            "x=5",
            _prob(answer="3", multiple_answers={"accepted": ["3", "5"]}),
        )
        assert result.state == FinalAnswerState.correct

    def test_non_listed_still_incorrect(self) -> None:
        # multiple_answers에 없는 값(x=9) → incorrect(넓히기만·거짓 correct 0).
        result = verify_final_answer(
            "x=9",
            _prob(answer="3", multiple_answers={"accepted": ["3", "5"]}),
        )
        assert result.state == FinalAnswerState.incorrect


class TestAnswerNotLeaked:
    """정답 비노출 계약 — 어떤 상태의 결과에도 기대정답 원문이 실리지 않는다."""

    def test_incorrect_reason_never_contains_expected_answer(self) -> None:
        result = verify_final_answer("x=999", _prob(answer="42"))
        assert result.state == FinalAnswerState.incorrect
        assert result.reason is not None
        assert "42" not in result.reason

    def test_unverifiable_reason_never_contains_expected_answer(self) -> None:
        result = verify_final_answer("잘 모르겠어요", _prob(answer="42"))
        assert result.state == FinalAnswerState.unverifiable
        assert result.reason is not None
        assert "42" not in result.reason

    def test_correct_result_has_no_reason_at_all(self) -> None:
        # correct는 사유가 아예 없다 — 노출 표면 자체가 없다(정답 원문이 실릴 자리 없음).
        result = verify_final_answer("x=3", _prob(answer="3"))
        assert result.reason is None

    def test_mc_incorrect_reason_is_fixed_template(self) -> None:
        # 객관식 불일치 사유는 결정론 고정 템플릿뿐 — 기대정답 값이 문구에 끼어들 여지가 없다.
        result = verify_final_answer(
            "1",
            _prob(answer="2", choices=["0", "1", "2", "3"], question_format=QuestionFormat.객관식),
        )
        assert result.state == FinalAnswerState.incorrect
        assert result.reason == "다른 선택지 값 제출 — 객관식 불일치"


class TestResultShape:
    """결과 모델 계약 — 3상태·frozen·correct이면 reason None."""

    def test_correct_reason_none(self) -> None:
        result = verify_final_answer("x=3", _prob(answer="3"))
        assert result.state == FinalAnswerState.correct
        assert result.reason is None

    def test_state_is_str_enum(self) -> None:
        # str-Enum이라 문자열 값과 동등(응답 직렬화 시 "correct" 등).
        result = verify_final_answer("x=3", _prob(answer="3"))
        assert result.state == "correct"
