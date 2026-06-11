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
        # (정밀 해법은 semantic/judge 계층 — 슬104~108·측정 대기)라 여기선 "단정 개입 소멸"만 잠근다.
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
        # 'b'가 'ab' 내부(다른 식별자의 일부)면 미매칭 — 임의 텍스트의 b 오매칭 차단.
        m = self._by_id("ab를 전개해서 정리했어요", "fraction-cancellation")
        assert m is None or "b" not in m.matched_signals

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
        assert short_or_digit == {
            ("sign-flip-in-inequality", "곱"),  # 한글 형태소 — substring 유지(내용성)
            ("division-by-zero", "0"),  # 경계 매칭
            ("square-root-positivity", "√"),  # 연산자 기호 — substring 유지(내용성)
            ("exponent-zero", "0"),  # 경계 매칭
            ("fraction-cancellation", "b"),  # 경계 매칭(단일 ASCII)
            ("angle-sum-non-triangle", "180"),  # 경계 매칭(숫자-only)
        }
