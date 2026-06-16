"""미성년 동의 게이트 *서버측 연령 파생* 단위테스트 — consent.derive_is_minor.

PIPA 만14세 미만 게이트 실효화(P4)의 순수 파생 함수를 검증한다. 핵심 계약:
  - birth_year None → None(미상 보존 — 게이트는 *알려진* 미성년만 차단).
  - 보수적 연나이 경계: 연나이 == threshold도 미성년(`<=`·생일 전 만(threshold-1) 과보호).
  - threshold가 반영된다(설정 가능).
`current_year`는 명시 주입해 *결정론*으로 검증한다(시스템 시계 비의존).
"""

from __future__ import annotations

from datetime import datetime, timezone

from whymath_backend.consent import current_year_kst, derive_is_minor


class TestDeriveIsMinor:
    def test_none_birth_year_returns_none(self) -> None:
        """birth_year 미상 → None(강제 차단 안 함 — 기존 게이트 '미상은 통과' 설계 유지)."""
        assert derive_is_minor(None, current_year=2026, threshold=14) is None

    def test_clearly_minor_returns_true(self) -> None:
        """연나이 10(2026-2016) ≤ 14 → 미성년 True."""
        assert derive_is_minor(2016, current_year=2026, threshold=14) is True

    def test_clearly_adult_returns_false(self) -> None:
        """연나이 26(2026-2000) > 14 → 비미성년 False."""
        assert derive_is_minor(2000, current_year=2026, threshold=14) is False

    def test_boundary_year_age_below_threshold_true(self) -> None:
        """연나이 13(< 14) → True."""
        assert derive_is_minor(2013, current_year=2026, threshold=14) is True

    def test_boundary_year_age_equals_threshold_true_conservative(self) -> None:
        """연나이 14(== threshold) → True(보수적 — 생일 전이면 실제 만13세일 수 있어 과보호).

        이 칸이 P4 보안 결정의 핵심: 월일 미수집이라 만나이가 13일 가능성을 차단(under-gate=위반).
        """
        assert derive_is_minor(2012, current_year=2026, threshold=14) is True

    def test_boundary_year_age_above_threshold_false(self) -> None:
        """연나이 15(> 14) → False(생일 전이라도 최소 만14세 — 게이트 불요)."""
        assert derive_is_minor(2011, current_year=2026, threshold=14) is False

    def test_threshold_is_respected(self) -> None:
        """threshold가 파생을 좌우한다 — 같은 연나이(14)도 임계 13이면 비미성년, 15면 미성년."""
        # 연나이 14 = 2026 - 2012
        assert derive_is_minor(2012, current_year=2026, threshold=13) is False
        assert derive_is_minor(2012, current_year=2026, threshold=14) is True
        assert derive_is_minor(2012, current_year=2026, threshold=15) is True

    def test_zero_threshold_only_future_and_current_year_birth_minor(self) -> None:
        """threshold 0 → 연나이 0(올해 출생)만 미성년, 1살 이상은 비미성년(임계 경계 검증)."""
        assert derive_is_minor(2026, current_year=2026, threshold=0) is True
        assert derive_is_minor(2025, current_year=2026, threshold=0) is False

    def test_future_birth_year_treated_as_minor_safe(self) -> None:
        """미래 출생연도(비정상 입력) → 연나이 음수 ≤ threshold라 True(보호 쪽으로 안전 처리)."""
        assert derive_is_minor(2030, current_year=2026, threshold=14) is True


class TestCurrentYearKst:
    def test_returns_int_close_to_now(self) -> None:
        """current_year_kst는 정수 연도를 반환(시스템 시계 기반·UTC). UTC 연도와 일치."""
        year = current_year_kst()
        assert isinstance(year, int)
        assert year == datetime.now(tz=timezone.utc).year
