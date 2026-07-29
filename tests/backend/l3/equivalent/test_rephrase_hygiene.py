"""rephrase 발문 위생 게이트(S3-12) — 결정론 검출 5축 봉인(hermetic·LLM 0).

변별력: 각 결함 케이스는 S3-09 감사 확정 **실사례 문면**이라, 게이트가 없거나 축이 빠지면
해당 테스트가 실패한다(결함 상태에서 실패 확인 가능). 정상 발문 통과(오탐 0)도 함께 동결한다.
"""

from __future__ import annotations

import pytest

from whymath_backend.l3.equivalent.rephrase_hygiene import (
    REASON_FOREIGN_SCRIPT,
    REASON_JOSA_ERROR,
    REASON_META_LABEL_LEAK,
    REASON_NONSTANDARD_TERM,
    REASON_REQUEST_ANSWER_MISMATCH,
    question_hygiene_violations,
)


def _codes(text: str) -> set[str]:
    return {v.split(":", 1)[0] for v in question_hygiene_violations(text)}


class TestForeignScript:
    """① 비한글 스크립트 — CJK 한자·가나 주입(감사 실사례 '두解'·'となる')."""

    @pytest.mark.parametrize(
        "text",
        [
            "이차방정식 x^2 - 9x + 20 = 0 의 두解 중 더 큰 解의 값을 구하시오.",  # 한자 주입
            "이차방정식 x^2 - 5x + 6 = 0 의 두解となる 근을 구하시오.",  # 가나 주입
            "(으咧) 이차방정식 (x + 4)^2 = 6 의 큰 근을 구하시오.",  # 한자 주입(실측)
        ],
    )
    def test_rejects_cjk_kana(self, text: str) -> None:
        assert REASON_FOREIGN_SCRIPT in _codes(text)

    def test_latin_and_math_symbols_allowed(self) -> None:
        # 라틴 변수·수식 기호·π는 수학 표기라 허용(비한글 축은 한자·가나 범위만 검사).
        clean = "함수 f(x) = 2x^2 + 3x 의 최솟값과 y = sin(πx) 의 주기를 구하시오."
        assert REASON_FOREIGN_SCRIPT not in _codes(clean)


class TestMetaLabelLeak:
    """② 재서술 메타 라벨 누출 — '원 발문:'·'원판'·'재서술'(감사 실사례)."""

    @pytest.mark.parametrize(
        "text",
        [
            "원 발문: 이차방정식 x^2 - 3x + 2 = 0 의 큰 근을 구하시오.",
            "원판을 다루는 문제로, x^2 - 3x + 2 = 0 의 작은 근을 구하시오.",
            "재서술: x^2 - 3x + 2 = 0 의 해를 구하시오.",
        ],
    )
    def test_rejects_meta_labels(self, text: str) -> None:
        assert REASON_META_LABEL_LEAK in _codes(text)


class TestNonstandardTerm:
    """③ 비표준 용어 — '원시방정식'·'다차방정식'·'원시적'(감사 확정 폐쇄 목록)."""

    @pytest.mark.parametrize(
        "text",
        [
            "원시방정식 x^2 + 6x = 0 을 풀어 큰 근을 구하시오.",
            "원시 방정식 x^2 + 6x = 0 을 풀어 큰 근을 구하시오.",  # 띄어쓰기 변형(실측)
            "다차방정식 x^2 - 8x = 0 의 두 근 중 큰 근을 구하시오.",
            "이 식이 원시적으로 무엇인지 구하시오. log_5 x = 2",
        ],
    )
    def test_rejects_nonstandard_terms(self, text: str) -> None:
        assert REASON_NONSTANDARD_TERM in _codes(text)

    def test_wonsi_hamsu_is_allowed(self) -> None:
        # '원시함수'(부정적분 정상 용어)는 오탐하지 않는다 — 폐쇄 목록 정확 문자열만.
        assert _codes("함수 f(x) = 2x 의 원시함수 F(x) 를 구하시오.") == set()


class TestRequestAnswerMismatch:
    """④ 요구-정답 부정합 — 값 문항에 '방법'·'어떨까요' 요구 이탈(감사 statement_mismatch)."""

    @pytest.mark.parametrize(
        "text",
        [
            "이차방정식 2x^2 + 5x + 2 = 0 의 작은 근을 구하는 방법을 서술하시오.",
            "이차방정식 x^2 + 16x + 64 = 0 의 근을 찾는 방법은 어떨까요?",
        ],
    )
    def test_rejects_method_asking(self, text: str) -> None:
        assert REASON_REQUEST_ANSWER_MISMATCH in _codes(text)


class TestJosaError:
    """⑤ 조사 오류 — 수·수식 꼬리 읽기로 판별 가능한 받침 부정합(S3-12 josa 판별기 재사용)."""

    @pytest.mark.parametrize(
        "text",
        [
            "이차방정식 x^2 - 7x + 10 = 0 의 두 근의 합 10 를 구하시오.",  # 십→을
            "지수방정식 2^x = 256 에서 256를 만드는 x 를 구하시오.",  # 육→을
            "로그방정식 log_2 x = 2 에서 2 을 밑으로 한 값은?",  # 이→를
            "함수 f(x) = x^3 + 9x^2 가 극소가 되는 x 의 값을 구하시오.",  # 제곱→이(실측)
            "값이 4 이 되는 로그방정식 log_2 x = 4 의 해를 구하시오.",  # 사→가
        ],
    )
    def test_rejects_wrong_josa(self, text: str) -> None:
        assert REASON_JOSA_ERROR in _codes(text)

    @pytest.mark.parametrize(
        "text",
        [
            "이차방정식 x^2 - 7x + 10 = 0 의 두 근 중 큰 근을 구하시오.",
            "이차방정식 3x^2 - 7x + 4 = 0 을 풀어 더 큰 해를 구하시오.",  # 0(영)→을 정합
            "등차수열의 첫째항이 2, 공차가 5 일 때 제10항을 구하시오.",
            "x = 25 이다.",  # '이다' 활용은 조사 아님 — lookahead가 배제
            "√3/2 와 비교하시오.",  # 판별 불가 토큰은 침묵(오탐 0)
        ],
    )
    def test_correct_or_undecidable_pass(self, text: str) -> None:
        assert REASON_JOSA_ERROR not in _codes(text)


class TestCleanPass:
    def test_skeleton_original_passes(self) -> None:
        # 스켈레톤 원 발문(rephrase 소스) 대표 문면 — 전 축 통과(게이트가 원문을 다치지 않음).
        clean = "이차방정식 3x^2 - 7x + 4 = 0 의 두 근 중 큰 근을 구하시오."
        assert question_hygiene_violations(clean) == ()
