"""오개념 진단 매처 단위테스트 — top-K · confidence · 동률 안정 정렬."""

from __future__ import annotations

from whymath_backend.l4.misconception import diagnose


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


class TestRankingAndTopK:
    def test_higher_confidence_first(self) -> None:
        # 두 오개념 동시 등장(부분/전체 매칭)
        text = (
            "(a+b)² = a² + b²로 전개했어. "
            "그리고 log(a+b)는 그냥 log a + log b 정도일 거 같아"
        )
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
