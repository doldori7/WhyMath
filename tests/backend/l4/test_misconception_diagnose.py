"""오개념 진단 매처 단위테스트 — top-K · confidence · 동률 안정 정렬."""

from __future__ import annotations

import re

from whymath_backend.l4.misconception import (
    MisconceptionMatch,
    correct_form_present,
    diagnose,
)
from whymath_backend.l4.misconception.catalog import (
    CATALOG,
    CATALOG_BY_ID,
    ZERO_ROOT_MENTION,
)
from whymath_backend.l4.misconception.diagnose import _normalize, _signal_hit
from whymath_backend.l4.misconception.match_gate import apply_match_quality_gate
from whymath_backend.l4.misconception.models import Misconception


class TestSingleMatch:
    def test_full_signal_co_occurrence_confidence_1(self) -> None:
        # distribution-over-power: signals=("(a+b)", "a² + b²")
        text = "내 풀이는 (a+b)² = a² + b²로 전개했어"
        matches = diagnose(text)
        assert len(matches) >= 1
        top = matches[0]
        assert top.misconception.id == "distribution-over-power"
        assert top.confidence == 1.0
        assert set(top.matched_signals) == {"(a+b)", "a² + b²"}

    def test_partial_match_lower_confidence(self) -> None:
        # 두 signal 중 하나만 — 0.5
        text = "(a+b)² 까지만 적었어"
        matches = diagnose(text)
        ids = {m.misconception.id for m in matches}
        assert "distribution-over-power" in ids
        m = next(x for x in matches if x.misconception.id == "distribution-over-power")
        assert m.confidence == 0.5

    def test_no_match_returns_empty(self) -> None:
        assert diagnose("그냥 자연스러운 풀이") == []
        assert diagnose("") == []

    def test_suneung_trig_period_entry_matches(self) -> None:
        # 신규 수능 항목(삼각함수)이 매처를 통과하는지 — period-of-scaled-sine
        text = "y=sin(2x)의 주기는 2π 라고 적었어"
        matches = diagnose(text)
        top = matches[0]
        assert top.misconception.id == "period-of-scaled-sine"
        assert top.confidence == 1.0
        assert top.misconception.domain == "삼각함수"

    def test_suneung_sine_distribution_full_match(self) -> None:
        # sin(a+b) = sin a + sin b — 신규 삼각함수 오개념 풀 매칭
        matches = diagnose("sin(a+b) = sin a + sin b 로 풀었어")
        top = matches[0]
        assert top.misconception.id == "sine-distributes-over-sum"
        assert top.confidence == 1.0


class TestCorrectFormPresent:
    """`correct_form_present` — 검증 풀이에 오개념의 *정정 형태*가 나타나는지(정밀 반박 신호).

    `signals`와 동일한 `_normalize`(NFKC+공백제거)로 흡수하므로 공백·위첨자 표기 변이에 불변.
    `correct_form`이 None인 오개념·정정 부재 텍스트는 False(기존 약한 반박 동작 보존).
    """

    _DISTRIBUTION = CATALOG_BY_ID[
        "distribution-over-power"
    ]  # correct_form="(a+b)² = a² + 2ab + b²"

    def test_detected_when_present(self) -> None:
        assert correct_form_present(self._DISTRIBUTION, "전개하면 (a+b)² = a² + 2ab + b²")

    def test_notation_invariant_spacing_and_superscript(self) -> None:
        # 공백 변이·위첨자 `²`↔평문 `2`(NFKC)에 불변 — 같은 정규형으로 흡수.
        assert correct_form_present(self._DISTRIBUTION, "  (a+b)2  =  a2 + 2 a b + b2  ")

    def test_absent_when_only_wrong_form(self) -> None:
        # 틀린 형태만 있는 풀이엔 정정 형태가 없음 → False(약한 경로로 빠짐).
        assert not correct_form_present(self._DISTRIBUTION, "(a+b)² = a² + b²")

    def test_none_correct_form_disabled(self) -> None:
        # correct_form 미부여 오개념(예: sign-flip-in-inequality)은 항상 False.
        none_cf = CATALOG_BY_ID["sign-flip-in-inequality"]
        assert none_cf.correct_form is None
        assert not correct_form_present(none_cf, none_cf.canonical_statement)

    def test_empty_normalized_form_not_whole_match(self) -> None:
        # 정규형이 빈 문자열인 correct_form(공백만)은 전체 매칭을 일으키지 않는다(가드).
        blank = Misconception(
            id="x",
            name_kr="x",
            domain="대수",
            canonical_statement="x",
            counterexample="x",
            signals=("x",),
            correct_form="   ",
        )
        assert not correct_form_present(blank, "아무 텍스트")


class TestSliceCatalogExpansionMatches:
    """슬 §5.4 신규 8종의 *진단 매칭* — 학생의 틀린 주장 텍스트 → 해당 id 매칭(confidence 1.0).

    각 텍스트는 *positive 오류 단편*(학생이 틀린 명제를 직접 적은 형태)으로, 두 signal
    토큰이 모두 공출현해 풀매칭(1.0)이 떠야 한다.
    """

    def _find(self, text: str, mid: str) -> MisconceptionMatch | None:
        return next((m for m in diagnose(text, top_k=8) if m.misconception.id == mid), None)

    def test_discriminant_negative_no_real_root(self) -> None:
        m = self._find("판별식이 음수라서 해가 없다고 했어", "discriminant-negative-no-real-root")
        assert m is not None
        assert m.confidence == 1.0
        assert m.misconception.domain == "대수"

    def test_root_loss_by_dividing(self) -> None:
        m = self._find("x²=2x에서 양변을 x로 나누면 x=2", "root-loss-by-dividing")
        assert m is not None
        assert m.confidence == 1.0

    def test_circle_radius_squared(self) -> None:
        m = self._find("x²+y²=9의 반지름은 r²=9 라고 적었어", "circle-radius-squared")
        assert m is not None
        assert m.confidence == 1.0
        assert m.misconception.domain == "기하"

    def test_mutually_exclusive_implies_independent(self) -> None:
        m = self._find("두 사건이 배반이니까 독립이야", "mutually-exclusive-implies-independent")
        assert m is not None
        assert m.confidence == 1.0
        assert m.misconception.domain == "확률통계"

    def test_composite_function_commutes(self) -> None:
        m = self._find("f∘g = g∘f 라서 합성 순서는 상관없어", "composite-function-commutes")
        assert m is not None
        assert m.confidence == 1.0
        assert m.misconception.domain == "함수"

    def test_translation_sign_flip(self) -> None:
        m = self._find("y=f(x-a)는 왼쪽으로 평행이동한 거야", "translation-sign-flip")
        assert m is not None
        assert m.confidence == 1.0
        assert m.misconception.domain == "함수"

    def test_continuity_implies_differentiability(self) -> None:
        # doc 함수 슬롯 #15이나 domain=미적분([H:12미적Ⅰ02-02])
        m = self._find("이 함수는 연속이니까 미분가능해", "continuity-implies-differentiability")
        assert m is not None
        assert m.confidence == 1.0
        assert m.misconception.domain == "미적분"

    def test_critical_point_implies_extremum(self) -> None:
        m = self._find("f′=0이면 극값을 가져", "critical-point-implies-extremum")
        assert m is not None
        assert m.confidence == 1.0
        assert m.misconception.domain == "미적분"

    def test_unrelated_solution_matches_no_new_entry(self) -> None:
        # 무관한 풀이는 신규 8종 어디에도 풀매칭(1.0)되지 않는다(두 토큰 AND·과잉 단일토큰 회피).
        new_ids = {
            "discriminant-negative-no-real-root",
            "root-loss-by-dividing",
            "circle-radius-squared",
            "mutually-exclusive-implies-independent",
            "composite-function-commutes",
            "translation-sign-flip",
            "continuity-implies-differentiability",
            "critical-point-implies-extremum",
        }
        text = "일차함수 y=2x+3의 그래프를 그리고 기울기를 구했어"
        for m in diagnose(text, top_k=10):
            if m.misconception.id in new_ids:
                assert m.confidence < 1.0


class TestRankingAndTopK:
    def test_higher_confidence_first(self) -> None:
        # 두 오개념 동시 등장(부분/전체 매칭)
        text = "(a+b)² = a² + b²로 전개했어. 그리고 log(a+b)는 그냥 log a + log b 정도일 거 같아"
        matches = diagnose(text)
        # 둘 다 매칭(둘 다 1.0 신뢰도)
        ids = [m.misconception.id for m in matches]
        assert "distribution-over-power" in ids
        assert "log-distribution" in ids
        # 모두 1.0이라 동률 — catalog 순서가 안정 유지(대수 distribution-over-power 먼저)
        assert matches[0].confidence == 1.0
        assert matches[1].confidence == 1.0

    def test_top_k_default_three(self) -> None:
        # 카탈로그 14개 중 부분 매칭 다수 발생할 만한 단순 토큰
        # "0"이 sign-flip-in-inequality·division-by-zero·exponent-zero에 모두 등장 가능
        text = "분모 0, a⁰, 음수, 곱, 0, 0"
        matches = diagnose(text)
        assert len(matches) <= 3

    def test_top_k_param_overrides(self) -> None:
        text = "분모 0, a⁰, 음수, 곱, 0, 0"
        few = diagnose(text, top_k=1)
        assert len(few) <= 1


class TestStableOrderingOnTie:
    """동률 confidence 시 catalog 순서(=doc 명시 순서) 유지."""

    def test_algebra_before_geometry_on_tie(self) -> None:
        # 대수(distribution-over-power)와 기하(닮음·합동) 두 케이스가 모두 풀 매칭
        text = "(a+b)² = a² + b² 그리고 닮음은 합동이야"
        matches = diagnose(text, top_k=5)
        # 둘 다 1.0이면 catalog 순서(algebra 먼저)
        assert matches[0].misconception.id == "distribution-over-power"
        assert any(m.misconception.id == "similarity-vs-congruence" for m in matches)


class TestNotationNormalization:
    """v1.1 표기 정규화 — 공백·유니코드 변이에 의한 거짓음성 제거(슬 101)."""

    def test_whitespace_insensitive_full_match(self) -> None:
        # 학생이 공백 없이 쓴 표기: signal "a² + b²"(공백)도 "a²+b²"에 매칭돼야 함
        matches = diagnose("(a+b)²=a²+b²")
        top = matches[0]
        assert top.misconception.id == "distribution-over-power"
        assert top.confidence == 1.0  # v1(공백 민감)이라면 0.5에 그쳤을 케이스

    def test_superscript_normalized_to_digit(self) -> None:
        # NFKC: 위첨자 "²" → "2". signal "a² + b²"가 평문 "a2 + b2"에도 매칭
        matches = diagnose("(a+b)2 = a2 + b2 로 전개")
        ids = {m.misconception.id for m in matches}
        assert "distribution-over-power" in ids

    def test_matched_signals_keep_original_form(self) -> None:
        # 정규화는 비교에만 — 표시되는 matched_signals는 원본 신호 문자열 유지
        top = diagnose("(a+b)²=a²+b²")[0]
        assert set(top.matched_signals) == {"(a+b)", "a² + b²"}


class TestLatexNotationNormalization:
    """MISC-17 — OCR·MathLive 산출물은 계약상 LaTeX(`OcrResult.plain_latex`→`student_solution`).

    NFKC는 `²`→`2`만 펴고 `^`·`{}`·`\\left`/`\\right`는 남겨, 인식기의 정상 출력 `(a+b)^2=a^2+b^2`가
    신호 2개 중 1개(0.5)만 맞아 게이트 ①(0.65)에서 탈락하던 실측 결함(PR #1034 Codex P1).
    카탈로그 `signals`·`correct_form`에는 이 문자가 0건이라 양변 정규화의 일관성이 유지된다.
    """

    def test_caret_exponent_full_match(self) -> None:
        # 인식기 기본형 `^2` — 유니코드 `²`와 같은 정규형 `a2+b2`로 접혀야 풀매칭.
        top = diagnose("(a+b)^2 = a^2+b^2")[0]
        assert top.misconception.id == "distribution-over-power"
        assert top.confidence == 1.0

    def test_braced_exponent_full_match(self) -> None:
        top = diagnose("(a+b)^{2} = a^{2}+b^{2}")[0]
        assert top.misconception.id == "distribution-over-power"
        assert top.confidence == 1.0

    def test_left_right_delimiters_full_match(self) -> None:
        # `\left(`·`\right)`는 크기 조정 표식일 뿐 — 괄호 자체만 남긴다.
        top = diagnose(r"\left(a+b\right)^2 = a^2+b^2")[0]
        assert top.misconception.id == "distribution-over-power"
        assert top.confidence == 1.0

    def test_correct_latex_expansion_stays_partial(self) -> None:
        # 올바른 전개의 LaTeX형은 유니코드형(`test_symbolic_distribution_unchanged_partial`)과
        # 동일하게 부분(0.5)에 머문다 — 정규화가 거짓양성을 만들지 않는다.
        matches = [
            m
            for m in diagnose("(a+b)^2 = a^2+2ab+b^2")
            if m.misconception.id == "distribution-over-power"
        ]
        assert matches and matches[0].confidence == 0.5

    def test_correct_form_detected_in_latex(self) -> None:
        # 정정 형태 탐지(강한 반박)도 같은 `_normalize`를 쓰므로 LaTeX형에서 성립해야 한다.
        entry = CATALOG_BY_ID["distribution-over-power"]
        assert entry.correct_form is not None  # 카탈로그 전제 — 없으면 이 검사는 공허하다.
        assert correct_form_present(entry, "(a+b)^2 = a^2+2ab+b^2")


class TestSignalPrecision:
    """v1.1 신호 정밀화 — 공통어 거짓양성 축소(슬 101·invertibility)."""

    def test_invertibility_full_match_on_real_misconception(self) -> None:
        top = diagnose("모든 함수는 역함수를 갖는다고 생각했어")[0]
        assert top.misconception.id == "invertibility-without-1-1"
        assert top.confidence == 1.0

    def test_invertibility_not_confident_on_benign_modeun(self) -> None:
        # "모든 구간"처럼 무관한 '모든'은 더 이상 풀매칭을 만들지 않음
        # (v1 신호 "모든"이었다면 역함수+모든 → 1.0 거짓양성)
        benign = "이 함수의 역함수를 모든 구간에서 구했어"
        m = next(
            (x for x in diagnose(benign) if x.misconception.id == "invertibility-without-1-1"),
            None,
        )
        assert m is None or m.confidence < 1.0


class TestNumericSubstitutionDetection:
    """v1.2 정규식 보조 탐지 — *거짓 항등식의 수치 대입*(슬 102 헤드라인).

    학생이 기호 substring 없이 *구체 수치로* 거짓 항등식을 계산한 흔적을 잡는다.
    """

    def _find(self, text: str, mid: str) -> MisconceptionMatch | None:
        return next((m for m in diagnose(text, top_k=5) if m.misconception.id == mid), None)

    def test_distribution_numeric_substitution_detected(self) -> None:
        # 기호 signals "(a+b)"·"a² + b²" 부재(학생은 *수*를 적음) → v1.1이면 미탐지.
        # v1.2 정규식이 (3+4)²=3²+4² 흔적을 잡아 *추가* 탐지.
        m = self._find("(3+4)² = 3² + 4² = 25", "distribution-over-power")
        assert m is not None
        # 분모=2(substr signals), 정규식만 매치 → 0/2 + 1/2 = 0.5
        assert m.confidence == 0.5
        assert m.matched_signals == ()  # 기호 substring 0
        assert len(m.matched_regex_signals) == 1

    def test_square_root_numeric_substitution_detected(self) -> None:
        # √((-3)²)=-3 — 음수 대입으로 거짓 항등식이 드러난 흔적
        m = self._find("√((-3)²) = -3", "square-root-positivity")
        assert m is not None
        assert len(m.matched_regex_signals) == 1

    def test_fraction_numeric_substitution_detected(self) -> None:
        # (2+4)/2=4 — 분자 합에서 분모와 같은 항을 통째로 약분한 수치 흔적
        m = self._find("(2+4)/2 = 4", "fraction-cancellation")
        assert m is not None
        assert m.confidence == 0.5
        assert m.matched_signals == ()
        assert len(m.matched_regex_signals) == 1

    def test_correct_computation_not_flagged_by_regex(self) -> None:
        # 거짓양성 가드: *올바른* 계산은 정규식이 잡지 않는다(역참조 불일치).
        for text, mid in (
            ("(3+4)² = 49 로 계산", "distribution-over-power"),
            ("√((-3)²) = 3", "square-root-positivity"),
            ("(2+4)/2 = 3", "fraction-cancellation"),
        ):
            m = self._find(text, mid)
            # 후보가 떠도(다른 weak substring 때문) 정규식은 미발화여야 함
            assert m is None or m.matched_regex_signals == ()

    def test_log_distribution_numeric_substitution_detected(self) -> None:
        # 슬 102 후속(보수적 확장): 로그를 합에 분배해 *수치로* 거짓 항등식을 계산한 흔적
        # `log(2+3)=log2+log3`을 잡는다. 기호 signals "log(a+b)"·"log a + log b" 부재(학생은
        # *수*만 적음) → v1.1이면 미탐지. v1.2 정규식이 *추가* 탐지.
        m = self._find("log(2+3) = log2 + log3", "log-distribution")
        assert m is not None
        # 분모=2(substr signals), 정규식만 매치 → 0/2 + 1/2 = 0.5
        assert m.confidence == 0.5
        assert m.matched_signals == ()  # 기호 substring 0
        assert len(m.matched_regex_signals) == 1

    def test_log_correct_product_law_not_flagged_by_regex(self) -> None:
        # FP 0 증명: 올바른 곱 법칙 `log(2·3)=log2+log3`은 괄호 안이 *곱*(·)이라 정규식
        # `\d+\+\d+`(합)에 미매치 — 정상 풀이를 오개념으로 거짓 매칭하지 않는다(낙인 방지).
        # 동시에 올바른 값 `log(2+3)=log5`(우변 단항)·기호식 `log(a+b)=log a+log b`(문자)도 미발화.
        for text in (
            "log(2·3) = log2 + log3",  # 올바른 곱 법칙(분배 대상은 곱)
            "log(2+3) = log5",  # 올바른 값 계산
            "log(a+b) = log a + log b",  # 기호식(substring 경로 담당·regex 미발화)
            "log(2+3) = log2 + log4",  # 역참조 불일치(진수 b: 3≠4)
        ):
            m = self._find(text, "log-distribution")
            assert m is None or m.matched_regex_signals == ()


class TestRegexBackwardCompatibility:
    """v1.2 정규식 도입이 v1.1 기호식 매칭(confidence·matched_signals)을 *불변*으로 유지."""

    def test_symbolic_distribution_unchanged_full(self) -> None:
        # 기호 풀매칭은 여전히 1.0·동일 matched_signals, 정규식은 미발화
        m = next(
            x
            for x in diagnose("(a+b)² = a² + b²로 전개")
            if x.misconception.id == "distribution-over-power"
        )
        assert m.confidence == 1.0
        assert set(m.matched_signals) == {"(a+b)", "a² + b²"}
        assert m.matched_regex_signals == ()

    def test_symbolic_distribution_unchanged_partial(self) -> None:
        m = next(
            x for x in diagnose("(a+b)² 까지만") if x.misconception.id == "distribution-over-power"
        )
        assert m.confidence == 0.5
        assert m.matched_regex_signals == ()

    def test_symbolic_fraction_unchanged_full(self) -> None:
        # 슬: 신호 정밀화로 둘째 signal `b`→`= b`(틀린 RHS) — 틀린 형태는 여전히 풀매칭 1.0.
        m = next(
            x
            for x in diagnose("(a+b)/a = b 로 약분")
            if x.misconception.id == "fraction-cancellation"
        )
        assert m.confidence == 1.0
        assert set(m.matched_signals) == {"(a+b)/a", "= b"}
        assert m.matched_regex_signals == ()


# ──────────────────────────────────────────────────────────────────────────
# v1.3 (슬109) — 짧은 영숫자 signal 경계 매칭: 실증 라이브 FP의 영구 회귀 잠금
# ──────────────────────────────────────────────────────────────────────────
class TestSignalBoundaryV13:
    """전문가 리뷰가 실증한 라이브 결함의 회귀 가드.

    결함: `'0' ∈ '10'` 같은 *토큰 내부* 부분문자열 매칭으로, 완전히 올바른 진술
    ("분모가 10인 분수를 약분했어요")이 division-by-zero **풀매칭(1.0) → COUNTEREXAMPLE
    개입 발화**. v1.3은 숫자-only·단일 ASCII 문자 signal을 영숫자 경계로 매칭해 차단한다.
    """

    def _by_id(self, text: str, mid: str) -> MisconceptionMatch | None:
        return next((m for m in diagnose(text, top_k=30) if m.misconception.id == mid), None)

    def test_demonstrated_live_fp_no_longer_full_matches(self) -> None:
        # 실증 케이스 그대로: '10'의 '0'이 더는 매칭되지 않아 풀매칭(1.0)이 사라진다.
        m = self._by_id("분모가 10인 분수를 약분했어요", "division-by-zero")
        assert m is not None  # '분모'는 여전히 부분매칭(알려진 트레이드오프)
        assert m.matched_signals == ("분모",)  # '0'은 미매칭
        assert m.confidence == 0.5  # 1.0 풀매칭 소멸

    def test_demonstrated_live_fp_counterexample_no_longer_fires(self) -> None:
        # 피해 지점 회귀: conf 1.0 → COUNTEREXAMPLE(단정적 개입)이 더는 발화하지 않는다.
        # 부분매칭 0.5 → REVERSE_REASONING은 substring 설계의 문서화된 잔여 트레이드오프
        # (정밀 해법은 semantic/judge 계층 — 슬104~108·측정 대기)라
        # 여기선 "단정 개입 소멸"만 잠근다.
        from whymath_backend.l4.misconception import select_intervention
        from whymath_backend.l4.misconception.models import InterventionPattern

        matches = diagnose("분모가 10인 분수를 약분했어요")
        assert matches, "부분매칭은 존재(트레이드오프)"
        iv = select_intervention(matches[0])
        assert iv is None or iv.pattern is not InterventionPattern.COUNTEREXAMPLE

    def test_zero_inside_decimal_not_matched(self) -> None:
        # '0.5'·'1.0' 내부의 0은 소수점 경계로 차단.
        m = self._by_id("계산하면 0.5가 나와요", "exponent-zero")
        assert m is None or "0" not in m.matched_signals

    def test_zero_after_nfkc_subscript_not_matched(self) -> None:
        # 'a₀'는 NFKC로 'a0'이 된다 — 식별자 내부 0은 차단(수열 첨자 오매칭 방지).
        m = self._by_id("수열 a₀의 값을 구했다", "division-by-zero")
        assert m is None  # '분모'도 '0'도 없음

    def test_legitimate_zero_still_matches(self) -> None:
        # 정당한 사용처(한글 조사 이웃)는 계속 풀매칭 — 거짓음성 추가 없음 회귀.
        m = self._by_id("분모가 0이 되어도 항상 정의된다고 생각했어", "division-by-zero")
        assert m is not None
        assert set(m.matched_signals) == {"분모", "0"}
        assert m.confidence == 1.0

    def test_single_latin_b_inside_identifier_not_matched(self) -> None:
        # 슬: fraction-cancellation 신호가 `("(a+b)/a","= b")`로 정밀화돼 단일 `b`는 사라졌다.
        # `ab를 전개…`는 LHS식·`= b` 둘 다 없어 미매칭 — 임의 텍스트 오매칭 차단(정밀화 후 유지).
        m = self._by_id("ab를 전개해서 정리했어요", "fraction-cancellation")
        assert m is None

    def test_180_inside_larger_number_not_matched(self) -> None:
        # '1800' 내부의 '180'은 차단·정당한 '180'(비숫자 이웃)은 유지.
        wrong = self._by_id("내각의 합이 1800이라고 적었다", "angle-sum-non-triangle")
        assert wrong is not None and "180" not in wrong.matched_signals
        right = self._by_id("내각의 합은 180이라고 했다", "angle-sum-non-triangle")
        assert right is not None and "180" in right.matched_signals

    def test_catalog_short_signal_ratchet(self) -> None:
        # 래칫 가드: 경계 매칭 대상(숫자-only·단일 문자) signal의 전수 스냅숏.
        # 새 항목이 짧은/숫자 signal을 추가하면 이 테스트가 깨져 의식적 리뷰를 강제한다
        # (v1.1 "signals 작성 원칙"의 코드 강제 — 종전엔 권고뿐이라 라이브 FP가 들어왔다).
        from whymath_backend.l4.misconception.catalog import CATALOG

        short_or_digit = {
            (m.id, s) for m in CATALOG for s in m.signals if len(s) <= 1 or s.isdigit()
        }
        # 슬: 신호 정밀화로 square-root(`√`)·fraction(`b`)의 짧은 signal이 LHS식+틀린 RHS로 대체돼
        # 래칫에서 빠졌다(정답 거짓 COUNTEREXAMPLE 제거 부수효과 — 짧은 signal 오매칭면 축소).
        assert short_or_digit == {
            ("sign-flip-in-inequality", "곱"),  # 한글 형태소 — substring 유지(내용성)
            ("division-by-zero", "0"),  # 경계 매칭
            ("exponent-zero", "0"),  # 경계 매칭
            ("angle-sum-non-triangle", "180"),  # 경계 매칭(숫자-only)
        }


class TestUnsafeSignalTightening:
    """LHS-only 느슨 신호 정밀화 — 정답 작업의 거짓 COUNTEREXAMPLE 개입 제거(우선순위 #1·#109 동류).

    세 오개념(square-root-positivity·fraction-cancellation·chain-rule)의 `signals`가 *틀린 RHS*를
    포함하지 않아 정답 형태(`√(x²)=|x|`·`(a+b)/a=1+b/a`·`d/dx[sin(2x)]=2cos(2x)`)를 1.0 풀매칭 →
    judge 기본 off라 COUNTEREXAMPLE 낙인 발화가 학생에 도달했다. LHS식+틀린 RHS로 좁혀 정답은 0.5
    (게이트 0.65 미만)·틀린 형태만 1.0이 되게 한다. 각 ① 정답 미발화 ② 틀림 1.0 ③ 정답에 단정
    개입 소멸(#109 미러)을 잠근다.
    """

    # (id, 정답 형태, 틀린 형태)
    _CASES = (
        ("square-root-positivity", "√(x²) = |x|", "√(x²) = x"),
        ("fraction-cancellation", "(a+b)/a = 1 + b/a", "(a+b)/a = b"),
        (
            "chain-rule-inner-derivative-omitted",
            "d/dx[sin(2x)] = 2cos(2x)",
            "d/dx[sin(2x)] = cos(2x)",
        ),
    )

    def _find(self, text: str, mid: str) -> MisconceptionMatch | None:
        return next((m for m in diagnose(text, top_k=30) if m.misconception.id == mid), None)

    def test_correct_form_below_gate(self) -> None:
        # 정답 형태는 자기 오개념을 신뢰 게이트(0.65) 이상으로 내지 않는다(거짓양성 소멸).
        for mid, correct, _wrong in self._CASES:
            m = self._find(correct, mid)
            assert m is None or m.confidence < 0.65, (mid, correct)

    def test_wrong_form_full_match(self) -> None:
        # 틀린 형태는 여전히 1.0 풀매칭(정밀화가 탐지력을 죽이지 않음).
        for mid, _correct, wrong in self._CASES:
            m = self._find(wrong, mid)
            assert m is not None and m.confidence == 1.0, (mid, wrong)

    def test_correct_form_no_counterexample_intervention(self) -> None:
        # #109 미러 — 정답 형태에 단정적 COUNTEREXAMPLE 개입이 발화하지 않는다(낙인 방지).
        from whymath_backend.l4.misconception import select_intervention
        from whymath_backend.l4.misconception.models import InterventionPattern

        for mid, correct, _wrong in self._CASES:
            m = self._find(correct, mid)
            if m is None:
                continue
            iv = select_intervention(m)
            assert iv is None or iv.pattern is not InterventionPattern.COUNTEREXAMPLE, (
                mid,
                correct,
            )


class TestRefutingRegex:
    """반박 조건(MISC-23) — 오개념을 *저지른* 풀이와 그것을 *설명한 정답*을 가른다.

    왜 필요했나
    -----------
    `signals` 공출현(AND)은 양성 단편만 센다. `root-loss-by-dividing`의
    `("양변", "x로 나누")`는 근 손실을 저지른 풀이에도, 그 함정을 정확히 설명한 정답에도
    똑같이 발화한다 — 둘 다 "양변을 x로 나누"를 쓰기 때문이다. 그래서 정답이 confidence
    1.0을 받아 품질 게이트(0.65)를 넘어 학생에게 확신 오진단으로 나갔다(실측).

    설계 판정: 감점이 아니라 **거부**다. 오개념 귀속이 *반박된* 것이지 *덜 확실한* 것이
    아니며, 낮은 confidence로 남기면 하류가 그것을 약한 증거로 취급한다.
    """

    #: 전부 **정답**이다 — 0을 근으로 남겼거나, 그 함정을 경고하는 서술이다.
    CORRECT_ANSWERS = (
        "x²=2x에서 양변을 x로 나누면 x=2만 나와서 안 되고 해는 0과 2다",
        "x²=3x 에서 양변을 x로 나누면 안 된다 — x=0 근을 잃는다",
        "x²=5x 이므로 x(x-5)=0, 따라서 x=0 또는 x=5",
        "양변을 x로 나누는 순간 x=0 이라는 근이 사라진다",
        "x²=7x, 양변을 x로 나누면 x=7 만 남아 x=0 을 잃는다",
        "x²=10x 의 두 근은 0이나 10 이다 — 양변을 x로 나누면 안 된다",
    )

    #: 전부 **오개념**이다 — 0을 어디에도 근으로 적지 않았다.
    ACTUAL_MISCONCEPTIONS = (
        "x²=2x 양변을 x로 나누면 x=2",
        "x² = 5x 이므로 양변을 x로 나눠 x=5",
        "ax²=bx 의 양변을 x로 나누면 x=b/a 라고 했다",
        "양변을 x로 나누어 x=12 를 얻었다",
    )

    def test_correct_answers_are_refuted(self) -> None:
        """정답은_반박돼_후보에서_빠진다"""
        for text in self.CORRECT_ANSWERS:
            ids = [m.misconception.id for m in diagnose(text)]
            assert "root-loss-by-dividing" not in ids, text

    #: 제로근을 **부정한** 오답들 — 리터럴 `x=0`·`0은`이 있지만 *주장이 아니라 부정*이다.
    #: 이것을 반박으로 세면 명백한 오개념을 통째로 놓친다(PR #1039 Codex P2).
    #: 부정 어미를 **하나씩 다르게** 쓴다 — 목록을 좁히는 뮤테이션이 살아남지 않게 하기 위해서다
    #: (실측: 어미를 `아니` 하나로 줄인 뮤테이션 P3가 처음엔 생존했다).
    NEGATED_ZERO_ROOT = (
        "x²=2x에서 x=0은 근이 아니므로 양변을 x로 나누면 x=2다",  # 아니
        "x=0 은 근이 될 수 없으니 양변을 x로 나눠 x=5",  # 없
        "0은 근에서 제외하고, 양변을 x로 나누면 x=7",  # 제외
        "x=0 은 무시해도 되니까 양변을 x로 나누어 x=3",  # 무시
        "x=0 은 버리고 양변을 x로 나누면 x=9",  # 버리
        "x=0 은 빼고 생각해서 양변을 x로 나누면 x=11",  # 빼
    )

    def test_negated_zero_root_is_not_a_refutation(self) -> None:
        """제로근을_부정한_오답은_반박으로_치지_않는다 — 미검출 방향 회귀 차단

        반박은 탐지를 *끄는* 방향이라 과잉 발동이 곧 미검출이고, 미검출은 오검출과 달리
        아무도 소리내지 않는다.
        """
        for text in self.NEGATED_ZERO_ROOT:
            ids = [m.misconception.id for m in diagnose(text)]
            assert "root-loss-by-dividing" in ids, text

    def test_actual_misconceptions_still_detected(self) -> None:
        """진짜_근_손실은_여전히_검출된다 — 반박을 넓히다 오개념을 죽이지 않았는지"""
        for text in self.ACTUAL_MISCONCEPTIONS:
            ids = [m.misconception.id for m in diagnose(text)]
            assert "root-loss-by-dividing" in ids, text

    def test_refuted_answers_do_not_reach_the_serving_gate(self) -> None:
        """반박된_정답은_서빙_품질_게이트에_도달하지_않는다 — 실제 해악 지점의 대조

        `diagnose`에서 빠졌다는 것과 학생에게 안 나간다는 것은 다른 사실이므로 따로 단언한다.
        수정 전에는 이 두 문장이 conf 1.0으로 게이트를 통과했다.
        """
        for text in self.CORRECT_ANSWERS:
            gated = apply_match_quality_gate(diagnose(text))
            surfaced = [m.misconception.id for m in gated.matches]
            assert "root-loss-by-dividing" not in surfaced, text

    def test_refutation_is_checked_before_signal_counting(self) -> None:
        """반박은_신호를_세기_전에_판정된다 — 감점이 아니라 거부임을 계약으로 고정

        신호가 **전부** 맞는 문장(공출현 2/2)인데도 후보가 아예 없어야 한다. 감점 방식이었다면
        낮은 confidence로 남았을 자리다.
        """
        text = "x²=2x에서 양변을 x로 나누면 x=2만 나와서 안 되고 해는 0과 2다"
        entry = CATALOG_BY_ID["root-loss-by-dividing"]
        norm = _normalize(text)
        assert all(_signal_hit(s, norm) for s in entry.signals), "전제: 두 신호가 다 맞는 문장"
        assert not [m for m in diagnose(text) if m.misconception.id == entry.id]

    #: 끝자리가 0인 수 뒤에 제로근 조사(`과`·`와`·`또는`·`이나`·`,`)가 붙는 문장들.
    #: `(?<!\d)` 경계가 없으면 `10과`의 `0과`가 제로근 언급으로 오인돼 **반박이 과잉 발동**하고,
    #: 진짜 오개념이 통째로 미검출된다. 미검출은 오검출과 달리 아무도 소리내지 않는다.
    BOUNDARY_MISCONCEPTIONS = (
        "x²=10x 양변을 x로 나누면 x=10과 같다",
        "x²=20x 이므로 양변을 x로 나누어 x=20와 같은 값을 얻었다",
        "양변을 x로 나누면 x=30 또는 그 근처다",
        "x²=40x, 양변을 x로 나누면 x=40이나 마찬가지다",
        "양변을 x로 나누어 x=50, 이것이 답이다",
    )

    def test_number_boundary_is_respected(self) -> None:
        """숫자_경계 — 끝자리 0인 수에 붙은 조사를 제로근으로 오인하지 않는다

        경계가 없으면 반박이 과잉 발동해 진짜 오개념을 놓친다(미검출 방향 회귀). 최초 판의
        이 테스트는 `x=10`·`x=20`만 봐서 **그 경계를 한 번도 밟지 않는 위장**이었다 —
        뮤테이션(경계 제거)이 살아남아 드러났다. 조사가 붙은 형태여야 그 절을 실제로 통과한다.
        """
        for text in self.BOUNDARY_MISCONCEPTIONS:
            ids = [m.misconception.id for m in diagnose(text)]
            assert "root-loss-by-dividing" in ids, text

    def test_plain_numeric_answers_still_detected(self) -> None:
        """조사_없는_끝자리0_수도_검출된다"""
        for text in ("x²=10x 양변을 x로 나누면 x=10", "양변을 x로 나누어 x=20 을 얻었다"):
            ids = [m.misconception.id for m in diagnose(text)]
            assert "root-loss-by-dividing" in ids, text


class TestAdditionMultiplicationRefutation:
    """반박 조건(PR #1068 Codex P1) — `addition-multiplication-rule-confused`.

    왜 필요했나
    -----------
    `signals=("합의 법칙", "곱의 법칙")` 공출현(AND)은 두 법칙을 *뒤섞어 쓴* 오답에도, 두
    법칙을 *정확히 구분해 설명한* 정답에도 똑같이 발화한다 — 둘 다 두 법칙 이름을 함께
    언급하기 때문이다. judge(`misconception_judge_enabled`)가 비활성인 기본 상태에서
    "합의 법칙과 곱의 법칙을 구분해서 써야 한다"가 confidence 1.0으로 품질 게이트(0.65)를
    넘어 정답에 반례 개입이 나갈 뻔했다(실측).
    """

    #: 전부 **정답**이다 — 두 법칙을 명시적으로 구분·구별하는 서술.
    CORRECT_ANSWERS = (
        "합의 법칙과 곱의 법칙을 구분해서 써야 한다",
        "합의 법칙과 곱의 법칙을 구별해야 헷갈리지 않는다",
        "동시에 일어나면 곱의 법칙, 아니면 합의 법칙으로 구분한다",
    )

    #: 전부 **오개념**이다 — 두 법칙을 혼동해 틀리게 계산했다("구분"·"구별" 미포함).
    ACTUAL_MISCONCEPTIONS = (
        "동전과 주사위를 던지는 경우의 수는 합의 법칙과 곱의 법칙이 헷갈려서 6+2=8로 계산했다",
        "합의 법칙과 곱의 법칙 중 뭘 써야 할지 몰라서 그냥 6+2로 풀었다",
    )

    def test_correct_answers_are_refuted(self) -> None:
        """정답은_반박돼_후보에서_빠진다"""
        for text in self.CORRECT_ANSWERS:
            ids = [m.misconception.id for m in diagnose(text)]
            assert "addition-multiplication-rule-confused" not in ids, text

    def test_actual_misconceptions_still_detected(self) -> None:
        """진짜_혼동은_여전히_검출된다 — 반박을 넓히다 오개념을 죽이지 않았는지"""
        for text in self.ACTUAL_MISCONCEPTIONS:
            ids = [m.misconception.id for m in diagnose(text)]
            assert "addition-multiplication-rule-confused" in ids, text

    def test_refuted_answers_do_not_reach_the_serving_gate(self) -> None:
        """반박된_정답은_서빙_품질_게이트에_도달하지_않는다 — 실제 해악 지점의 대조"""
        for text in self.CORRECT_ANSWERS:
            gated = apply_match_quality_gate(diagnose(text))
            surfaced = [m.misconception.id for m in gated.matches]
            assert "addition-multiplication-rule-confused" not in surfaced, text

    def test_refutation_is_checked_before_signal_counting(self) -> None:
        """반박은_신호를_세기_전에_판정된다 — 감점이 아니라 거부임을 계약으로 고정"""
        text = "합의 법칙과 곱의 법칙을 구분해서 써야 한다"
        entry = CATALOG_BY_ID["addition-multiplication-rule-confused"]
        norm = _normalize(text)
        assert all(_signal_hit(s, norm) for s in entry.signals), "전제: 두 신호가 다 맞는 문장"
        assert not [m for m in diagnose(text) if m.misconception.id == entry.id]


class TestRefutingRegexGovernance:
    """반박 조건을 *가진* 항목의 동결 — 조용히 늘거나 줄지 않게.

    반박은 탐지를 **끄는** 방향이라 잘못 붙으면 오개념을 통째로 놓치고, 그 미검출은 오검출과
    달리 아무도 소리내지 않는다. 그래서 부여 항목을 명시 목록으로 묶는다.
    """

    _REFUTING_IDS = {"root-loss-by-dividing", "addition-multiplication-rule-confused"}

    def test_only_listed_entries_have_refuting_regex(self) -> None:
        """목록_밖_항목은_반박_조건이_없다"""
        for m in CATALOG:
            assert isinstance(m.refuting_regex, tuple)
            if m.id not in self._REFUTING_IDS:
                assert m.refuting_regex == (), m.id

    def test_listed_entries_actually_have_one(self) -> None:
        """목록에_적힌_항목은_실제로_갖고_있다 — 선언과 사실의 대조"""
        for mid in self._REFUTING_IDS:
            assert CATALOG_BY_ID[mid].refuting_regex, mid

    def test_all_refuting_patterns_compile(self) -> None:
        """반박_정규식은_전부_컴파일된다 — 런타임 re.error 회귀 가드"""
        seen = 0
        for m in CATALOG:
            for pat in m.refuting_regex:
                re.compile(pat)
                seen += 1
        assert seen > 0, "스캔 0건 — 이 가드가 공허하게 통과했다"

    def test_shared_zero_root_definition_feeds_both_enforcement_points(self) -> None:
        """제로근_정의가_반박과_전방탐색_양쪽에_쓰인다 — 두 곳이 갈라지지 않게

        같은 개념을 두 번 적었던 것이 PR #1032 Codex P1의 자리였다(한쪽만 넓혀 정답이 샜다).
        """
        entry = CATALOG_BY_ID["root-loss-by-dividing"]
        assert entry.refuting_regex == (ZERO_ROOT_MENTION,)
        assert ZERO_ROOT_MENTION in entry.regex_signals[0]
