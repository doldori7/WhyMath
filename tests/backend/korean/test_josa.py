"""조사 받침 헬퍼 테스트 — 수 읽기(한자어) 기준 받침 판별·조사 선택 봉인(S2-08·S3-12).

봉인: ① 일의 자리 읽기 표 전수 ② 다자리·0으로 끝나는 수(십·백·천·영 지배) ③ 음수 부호 불변
④ 한글 단어 종성 ⑤ 판별 불가 문자열 None 폴백(√ 혼합 분수 등) ⑥ AI 검수 리뷰 실오류 정확 예시
(0→과·4→와·13→을·6→을·3→과) ⑦ (으)로 ㄹ 받침 예외 ⑧ S3-12 수식 꼬리 확장(거듭제곱=곱·정수
분수=분자 지배·소수=낱자·괄호/절댓값 묵음·후행 숫자·라틴 문자 읽기 — S3-09 감사 확정 조사
결함 실사례가 전부 판별된다). 순수 함수라 LLM·DB·IO 0.
"""

from __future__ import annotations

import pytest

from whymath_backend.korean.josa import (
    TailReading,
    eul_reul,
    eun_neun,
    euro_ro,
    has_batchim_hangul,
    has_batchim_number,
    has_batchim_text,
    i_ga,
    josa,
    tail_reading,
    wa_gwa,
)


class TestHasBatchimNumber:
    """정수 받침 판별 — 한자어 읽기의 마지막 음절 기준(표기 글자 아님)."""

    @pytest.mark.parametrize(
        ("digit", "expected"),
        [
            (0, True),  # 영(ㅇ)
            (1, True),  # 일(ㄹ)
            (2, False),  # 이
            (3, True),  # 삼(ㅁ)
            (4, False),  # 사
            (5, False),  # 오
            (6, True),  # 육(ㄱ)
            (7, True),  # 칠(ㄹ)
            (8, True),  # 팔(ㄹ)
            (9, False),  # 구
        ],
    )
    def test_ones_digit_table(self, digit: int, expected: bool) -> None:
        assert has_batchim_number(digit) is expected

    @pytest.mark.parametrize(
        ("n", "expected"),
        [
            (13, True),  # 십삼 → 삼(有)
            (81, True),  # 팔십일 → 일(有)
            (25, False),  # 이십오 → 오(無)
            (24, False),  # 이십사 → 사(無)
            (56, True),  # 오십육 → 육(有)
            (64, False),  # 육십사 → 사(無)
            (19, False),  # 십구 → 구(無)
            (31, True),  # 삼십일 → 일(有)
        ],
    )
    def test_multi_digit_ones_governs(self, n: int, expected: bool) -> None:
        assert has_batchim_number(n) is expected

    @pytest.mark.parametrize("n", [0, 10, 20, 30, 100, 1000, 2020])
    def test_zero_ending_always_batchim(self, n: int) -> None:
        # 일의 자리 0 → 십(ㅂ)·백(ㄱ)·천(ㄴ)·영(ㅇ) 모두 받침 有.
        assert has_batchim_number(n) is True

    @pytest.mark.parametrize(
        ("n", "expected"),
        [(-3, True), (-4, False), (-13, True), (-25, False), (-1, True)],
    )
    def test_negative_sign_invariant(self, n: int, expected: bool) -> None:
        # 부호는 읽기의 마지막 음절을 바꾸지 않는다(절댓값 지배).
        assert has_batchim_number(n) is expected


class TestHasBatchimHangul:
    """한글 음절 종성(받침) 판별."""

    @pytest.mark.parametrize(
        ("ch", "expected"),
        [("밑", True), ("값", True), ("항", True), ("수", False), ("나", False), ("가", False)],
    )
    def test_hangul_final(self, ch: str, expected: bool) -> None:
        assert has_batchim_hangul(ch) is expected

    def test_non_hangul_is_false(self) -> None:
        assert has_batchim_hangul("x") is False
        assert has_batchim_hangul("") is False


class TestHasBatchimText:
    """토큰 통합 판별 — 정수→수 읽기·한글끝→음절·그 외→None(정직 한계)."""

    def test_integer_string(self) -> None:
        assert has_batchim_text("13") is True
        assert has_batchim_text("4") is False
        assert has_batchim_text("-3") is True

    def test_hangul_word(self) -> None:
        assert has_batchim_text("밑") is True
        assert has_batchim_text("수") is False

    @pytest.mark.parametrize("token", ["√3/2", "sqrt(3)/2", "'", "±"])
    def test_undecidable_none(self, token: str) -> None:
        # 분자가 정수가 아닌 분수(√3/2 등)·읽기 관례가 갈리는 기호는 판별 불가 → None(정직 한계).
        assert has_batchim_text(token) is None

    @pytest.mark.parametrize(
        ("token", "expected"),
        [
            # S3-12 확장 — 구현 전에는 전부 None이던 형태(변별력: 구버전이면 이 케이스가 실패).
            ("sqrt(11)", True),  # 루트 십일 → 일(有)
            ("-3±2√2", False),  # … 이 루트 이 → 이(無)
            ("1/2", True),  # 이분의 일 → 일(有)
            ("2*sqrt(2)", False),  # 이 곱하기 루트 이 → 이(無)
        ],
    )
    def test_s3_12_previously_none_now_decided(self, token: str, expected: bool) -> None:
        assert has_batchim_text(token) is expected


class TestTailReadingS312:
    """S3-12 수식 꼬리 확장 — S3-09 감사 확정 조사 결함 실사례 전수 판별(변별력 봉인)."""

    @pytest.mark.parametrize(
        ("token", "batchim", "rieul"),
        [
            ("x²", True, False),  # 엑스제곱 → 곱(ㅂ) — 'x² 는'→은
            ("18²", True, False),  # 십팔제곱 → 곱 — '18² 로'→으로
            ("2²", True, False),  # '2²로'→으로
            ("10^5", True, False),  # 십의 오제곱 → 곱 — '10^5 로'→으로
            ("a**2", True, False),  # SymPy 표기 거듭제곱
            ("a^2+b^2", True, False),  # … 비제곱 → 곱 — 'a^2+b^2 가'→이
            ("17C3", True, False),  # 십칠 씨 삼 → 삼(ㅁ) — '17C3 를'→을
            ("(x - 6)", True, False),  # 괄호 묵음 → 육(ㄱ) — '(x-6)로'→으로
            ("f(-6)", True, False),  # 에프 마이너스 육 — 'f(-6)로'→으로
            ("f(1)", True, True),  # 에프 일 → 일(ㄹ) — 'f(1) 가'→이
            ("|x - 1|", True, True),  # 절댓값 막대 묵음 → 일(ㄹ) — '|x-1| 가'→이
            ("0.8", True, True),  # 영점팔 → 팔(ㄹ) — '0.8 는'→은
            ("40/10", True, False),  # 십분의 사십 → 십(ㅂ) — '40/10로'→으로
            ("1/5", True, True),  # 오분의 일 → 일(ㄹ) — '1/5 는'→은
            ("-46656", True, False),  # … 육 — '-46656로'→으로
            ("2πr", True, True),  # 이 파이 알 → 알(ㄹ) — '2πr 와'→과
            ("x", False, False),  # 엑스 → 스(無)
            ("5½", True, True),  # 오와 이분의 일 → 일(ㄹ) — '½로'는 옳다
            ("3.14", False, False),  # 삼점일사 → 사(無)
            ("0.20", True, False),  # 영점이영 → 영(ㅇ)
        ],
    )
    def test_audit_real_cases(self, token: str, batchim: bool, rieul: bool) -> None:
        assert tail_reading(token) == TailReading(batchim, rieul)

    def test_empty_and_unknown_none(self) -> None:
        assert tail_reading("") is None
        assert tail_reading("  ") is None
        assert tail_reading(")") is None  # 묵음 기호만 남으면 몸통이 없어 판별 불가


class TestJosaSelectors:
    """조사 편의 래퍼 — 을/를·와/과·은/는·이/가·(으)로."""

    def test_review_actual_errors(self) -> None:
        # AI 검수 리뷰 실오류(표본 02·04·06·09·11·29)의 올바른 조사.
        assert wa_gwa("0") == "과"  # "0과 4"
        assert wa_gwa("4") == "와"  # "4와"
        assert wa_gwa("3") == "과"  # "3과 9"
        assert wa_gwa("-3") == "과"  # "−3과"
        assert eul_reul("13") == "을"  # "13을 풀어"
        assert eul_reul("0") == "을"  # "0을 풀어"
        assert eul_reul("6") == "을"  # "밑 6을"

    def test_eul_reul(self) -> None:
        assert eul_reul("4") == "를"
        assert eul_reul("81") == "을"
        assert eul_reul("2") == "를"

    def test_eun_neun(self) -> None:
        assert eun_neun("3") == "은"
        assert eun_neun("2") == "는"
        assert eun_neun("수") == "는"

    def test_i_ga(self) -> None:
        assert i_ga("1") == "이"
        assert i_ga("2") == "가"
        assert i_ga("값") == "이"

    def test_none_fallback_default_batchim(self) -> None:
        # 판별 불가 문자열(√ 혼합 분수)은 안전 기본(받침 有) — 을/과/은/이 선택.
        assert eul_reul("√3/2") == "을"
        assert wa_gwa("√3/2") == "과"

    def test_josa_default_override(self) -> None:
        # default_batchim=False면 판별 불가 시 받침 無 계열 선택.
        assert josa("√3/2", "을", "를", default_batchim=False) == "를"


class TestEuroRo:
    """(으)로 — ㄹ 받침 예외(일·칠·팔) 및 한글 종성 ㄹ."""

    @pytest.mark.parametrize(
        ("n", "expected"),
        [
            ("1", "로"),  # 일(ㄹ)
            ("7", "로"),  # 칠(ㄹ)
            ("8", "로"),  # 팔(ㄹ)
            ("3", "으로"),  # 삼(ㅁ)
            ("6", "으로"),  # 육(ㄱ)
            ("2", "로"),  # 이(無)
            ("4", "로"),  # 사(無)
            ("10", "으로"),  # 십(ㅂ) — ㄹ 아님
            ("100", "으로"),  # 백(ㄱ)
        ],
    )
    def test_number_euro_ro(self, n: str, expected: str) -> None:
        assert euro_ro(n) == expected

    def test_hangul_euro_ro(self) -> None:
        assert euro_ro("물") == "로"  # ㄹ 받침
        assert euro_ro("값") == "으로"  # ㅄ 받침
        assert euro_ro("수") == "로"  # 받침 없음

    def test_unparseable_default(self) -> None:
        # S3-12: sqrt(2)는 이제 꼬리 판별("루트 이" → 받침 無)로 '로'가 맞다(구버전 '으로' 폐기).
        assert euro_ro("sqrt(2)") == "로"
        # 진짜 판별 불가(√ 혼합 분수)만 안전 기본 '으로'.
        assert euro_ro("√3/2") == "으로"

    @pytest.mark.parametrize(
        ("token", "expected"),
        [
            ("18²", "으로"),  # 제곱 → 곱(ㅂ)
            ("(x - 6)", "으로"),  # 육(ㄱ)
            ("f(1)", "로"),  # 일(ㄹ) — ㄹ 받침 예외
            ("40/10", "으로"),  # 십(ㅂ)
            ("5½", "로"),  # 일(ㄹ)
            ("0.8", "로"),  # 팔(ㄹ)
        ],
    )
    def test_s3_12_tail_euro_ro(self, token: str, expected: str) -> None:
        assert euro_ro(token) == expected
