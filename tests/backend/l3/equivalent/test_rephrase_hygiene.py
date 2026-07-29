"""rephrase 발문 위생 게이트(S3-12) — 결정론 검출 5축 봉인(hermetic·LLM 0).

변별력: 각 결함 케이스는 S3-09 감사 확정 **실사례 문면**이라, 게이트가 없거나 축이 빠지면
해당 테스트가 실패한다(결함 상태에서 실패 확인 가능). 정상 발문 통과(오탐 0)도 함께 동결한다.
"""

from __future__ import annotations

import pytest

from whymath_backend.l3.equivalent.rephrase_hygiene import (
    REASON_DANGLING_EXPONENT_PHRASE,
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

    @pytest.mark.parametrize(
        "text",
        [
            "이차방정식 x^2 - 3x + 2 = 0 의 (원래와 같은 표현으로) 큰 근을 구하시오.",
            "다음 방정식 (대입과 계산을 통해) x^2 - 5x + 6 = 0 의 근을 구하시오.",
            "이차방정식 x^2 - 3x + 2 = 0 의 (더 작은) 근을 구하시오.",
            "(주어진 방정식) x^2 - 3x + 2 = 0 의 두 근을 구하시오.",
        ],
    )
    def test_rejects_parenthetical_meta_leak(self, text: str) -> None:
        # rotation-1 실사례 괄호 삽입구 4건(폐쇄 목록 — 아래 test_legitimate_parenthetical_*
        # 참조: 애초 "괄호+한글+공백" 일반 규칙이었으나 misconception_eval_mc_generator의
        # 정당한 설명과 충돌해 폐쇄 목록으로 후퇴했다, 2026-07-29).
        assert REASON_META_LABEL_LEAK in _codes(text)

    def test_condition_label_parens_allowed(self) -> None:
        # 조건 나열형 (가)(나)는 폐쇄 목록에 없어 매치하지 않는다.
        clean = "다음 조건을 만족하는 수열 a_n이 있다. (가) a_1 = 3 (나) a_n+1 = a_n + 2"
        assert REASON_META_LABEL_LEAK not in _codes(clean)

    @pytest.mark.parametrize(
        "text",
        [
            "근과 계수 관계로 두 근의 합은 -(일차항 계수) = -16 = -16 이다.",
            "2와 15의 최소공배수는 30 이다(최대공약수는 1).",
            "다음 각을 구하시오(단위: 도).",
        ],
    )
    def test_legitimate_parenthetical_math_annotation_allowed(self, text: str) -> None:
        # 2026-07-29 실측 발견 오탐 3건 — misconception_eval_mc_generator(vieta_sum·gcd_lcm·
        # polygon_angle_sum)의 정당한 괄호 설명. "괄호+한글+공백" 일반 규칙이 이 문구들도
        # 잡아 폐쇄 목록으로 후퇴한 계기(TestTextHygieneS312 회귀로 실측 확인).
        assert REASON_META_LABEL_LEAK not in _codes(text)


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

    @pytest.mark.parametrize(
        "text",
        [
            "두 차원의 이차방정식 x^2 - 5x + 6 = 0 의 근을 구하시오.",
            "두 차원의 원에 해당하는 x^2 + y^2 = 9 를 만족하는 값을 구하시오.",
            "두차원 공간에서 x^2 - 4 = 0 의 해를 구하시오.",
        ],
    )
    def test_rejects_dimension_mislabel(self, text: str) -> None:
        # 1변수 방정식·수 계산 문항에 기하학적 차원·공간 개념 허위 부여(rotation-1 실사례).
        assert REASON_NONSTANDARD_TERM in _codes(text)

    @pytest.mark.parametrize(
        "text",
        [
            "이차방정식 x^2 - 3x + 2 = 0 의 두 근 중 큰 극을 구하시오.",
            "이차방정식 x^2 - 3x + 2 = 0 의 두 근 중 작은 극을 구하시오.",
        ],
    )
    def test_rejects_concept_substitution(self, text: str) -> None:
        # '큰/작은 극'(이차방정식 근 문항에 극값 어휘 오적용) — 이 코퍼스 맥락 정상 용법 미관찰.
        assert REASON_NONSTANDARD_TERM in _codes(text)

    def test_geukgap_calculus_terms_allowed(self) -> None:
        # '극값'·'극대'·'극소'는 미적분 정상 용어라 오탐하지 않는다(부정 lookahead).
        clean = "함수 f(x) = x^3 - 3x 의 극값을 구하고, 극대인지 극소인지 판정하시오."
        assert REASON_NONSTANDARD_TERM not in _codes(clean)

    def test_midpoint_is_legitimate_usage_not_flagged(self) -> None:
        # '중점'은 애초 이 패턴에 있었으나 misconception_eval_mc_generator의
        # midpoint-sum-only 밴드가 좌표 중점을 정상 용법으로 쓰는 것이 실측돼 제외했다
        # (2026-07-29 — rephrase_hygiene.py 모듈 docstring "재검토 실측" 참조).
        assert REASON_NONSTANDARD_TERM not in _codes(
            "이차방정식 x^2 - 5x + 6 = 0 의 두 근의 중점을 구하시오."
        )


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


class TestDanglingExponentPhrase:
    """⑥ 지수 서술구 허상 삽입 — S3-12 rotation-1 재검수 잔존 확인 실사례 3건(전건 결함).

    스켈레톤 원 발문(등식 직접 진술)에는 없는 rephrase 특유 구문 — "N의 (제곱|세제곱|
    거듭제곱근|제곱근)"이 verify 계약과 무관하게 삽입돼 허위·무의미 주장이 된다.
    """

    @pytest.mark.parametrize(
        "text",
        [
            "5의 제곱에 해당하는 값이면 x인가? log_5 x = 3 문제에서 x의 값을 찾아보세.",
            "5의 거듭제곱근이면 x인가? log_5 x = 1 때 x는 얼마나 되는가?",
            "625의 제곱근이면, x에 대한 방정식 5^x = 625의 해는?",
            "3의 5제곱근을 구하시오. 2^x = 32 의 해 x는?",  # N제곱근 변형
        ],
    )
    def test_rejects_dangling_exponent_phrase(self, text: str) -> None:
        assert REASON_DANGLING_EXPONENT_PHRASE in _codes(text)

    def test_normal_root_word_without_number_prefix_passes(self) -> None:
        # "제곱근"이 숫자+'의' 앞에 붙지 않은 일반 서술(수학적으로 참인 정의문 등)은 통과 —
        # 패턴이 요구하는 '숫자 의' 접두 없이는 매치하지 않는다(오탐 범위 최소화).
        assert _codes("제곱근의 정의를 설명하시오.") == set()

    def test_true_statement_connected_by_imeuro_allowed(self) -> None:
        # 2026-07-29 실측 발견 오탐 24건 — misconception_eval_mc_generator(sqrt_sum 밴드)의
        # "N의 제곱이므로 그 제곱근은 N"류는 참으로 연결된 서술이라 허상이 아니다(부정
        # lookahead로 제외). 허상 실사례 3건은 전부 '이면'(가정)·'구하시오'(명령)로 이어져
        # 이 제외에 걸리지 않는다(TestTextHygieneS312 회귀로 실측 확인).
        clean = "근호 안의 합 8281 은 91 의 제곱이므로 그 제곱근은 91 이다."
        assert REASON_DANGLING_EXPONENT_PHRASE not in _codes(clean)


class TestCleanPass:
    def test_skeleton_original_passes(self) -> None:
        # 스켈레톤 원 발문(rephrase 소스) 대표 문면 — 전 축 통과(게이트가 원문을 다치지 않음).
        clean = "이차방정식 3x^2 - 7x + 4 = 0 의 두 근 중 큰 근을 구하시오."
        assert question_hygiene_violations(clean) == ()
