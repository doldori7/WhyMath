"""L4 정서 안전 톤필터 단위테스트 — 금지 6패턴 치환·멱등·보고."""

from __future__ import annotations

from whymath_backend.l4.tone_filter import filter_tone


class TestForbiddenPatterns:
    def test_all_six_patterns_replaced(self) -> None:
        # 스펙 §"금지 패턴": 틀렸·못 하·잘못된·실수·바보·포기
        for banned in ("틀렸", "못 하", "잘못된", "실수", "바보", "포기"):
            filtered, report = filter_tone(f"이건 {banned}이야")
            assert banned not in filtered, banned
            assert banned in report.violations, banned
            assert report.rewritten is True

    def test_recommended_replacements_inserted(self) -> None:
        # 권장 표현이 들어갔는지 — 스펙 §"권장 표현"
        filtered, _ = filter_tone("이건 틀렸어")
        assert "다시 봐도 좋아" in filtered

        filtered, _ = filter_tone("포기하지 마")
        assert "다른 각도로 봐볼까" in filtered

    def test_longer_pattern_first(self) -> None:
        # "잘못된"이 "못 하"보다 먼저 처리되어 부분 충돌 방지
        filtered, report = filter_tone("잘못된 시도였어")
        assert "잘못된" not in filtered
        assert "다시 봐도 좋을" in filtered
        # "못 하"는 이 텍스트엔 *원래* 없으니 violations에 포함 안 됨
        assert report.violations == ["잘못된"]


class TestCleanPassthrough:
    def test_clean_text_untouched(self) -> None:
        clean = "정말 좋은 시도였어. 더 깊이 가볼까?"
        filtered, report = filter_tone(clean)
        assert filtered == clean
        assert report.violations == []
        assert report.rewritten is False


class TestIdempotent:
    def test_double_application_same(self) -> None:
        # 권장 표현엔 금지 패턴이 없으므로 두 번째 호출은 무변경
        first, r1 = filter_tone("이건 틀렸고 실수야")
        second, r2 = filter_tone(first)
        assert second == first
        assert r1.rewritten is True
        assert r2.rewritten is False


class TestMultipleViolations:
    def test_records_all_violations_in_order(self) -> None:
        filtered, report = filter_tone("틀렸어. 또 틀렸어. 포기하자")
        # "틀렸" 2회 + "포기" 1회
        assert report.violations.count("틀렸") == 2
        assert report.violations.count("포기") == 1
        assert "틀렸" not in filtered
        assert "포기" not in filtered
