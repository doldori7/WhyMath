"""오개념 진단 매처 단위테스트 — top-K · confidence · 동률 안정 정렬."""

from __future__ import annotations

from whymath_backend.l4.misconception import MisconceptionMatch, diagnose


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
        m = next(
            x
            for x in diagnose("(a+b)/a = b 로 약분")
            if x.misconception.id == "fraction-cancellation"
        )
        assert m.confidence == 1.0
        assert set(m.matched_signals) == {"(a+b)/a", "b"}
        assert m.matched_regex_signals == ()
