"""L3 수식 음성화 — 학년 프로파일 차이·구조 게이팅. 음성 슬라이스 S1.

"같은 구조를 학년에 맞게 다르게 읽는다"의 검증. S1은 고등을 완비하고, 초등/중등 차이로 프로파일
*메커니즘*이 동작함을 단언한다(전 학년 완성은 S3).
"""

from __future__ import annotations

import pytest

from whymath_backend.l4.speech import speak_latex


def test_power_reading_differs_by_grade() -> None:
    """x²: 초등은 '엑스 곱하기 엑스'로 전개, 중등+는 '엑스의 제곱'."""
    assert speak_latex(r"x^2", "초등").plain_text == "엑스 곱하기 엑스"
    assert speak_latex(r"x^2", "중등").plain_text == "엑스 제곱"
    assert speak_latex(r"x^2", "고등").plain_text == "엑스 제곱"
    assert speak_latex(r"x^3", "초등").plain_text == "엑스 곱하기 엑스 곱하기 엑스"


def test_fraction_order_denominator_first_all_grades() -> None:
    """분수는 모든 학년에서 한국 표준 '분모 먼저'(2분의 1) 불변."""
    for band in ("초등", "중등", "고등", "대학"):
        assert speak_latex(r"\frac{1}{2}", band).plain_text == "이 분의 일"


def test_integral_gated_by_grade() -> None:
    """적분은 중등 미도입 → unresolved 표시, 고등 도입 → 미해결 0(같은 입력·다른 정책)."""
    assert "\\int" in speak_latex(r"\int_a^b f", "중등").unresolved_symbols
    assert "\\int" not in speak_latex(r"\int_a^b f", "고등").unresolved_symbols


def test_root_not_introduced_in_elementary_is_surfaced() -> None:
    """근호는 초등 미도입 → unresolved로 정직 표시(읽기는 폴백 라벨로 계속)."""
    spec = speak_latex(r"\sqrt{2}", "초등")
    assert "\\sqrt" in spec.unresolved_symbols
    assert spec.plain_text  # 빈 낭독이 아니라 폴백으로 읽는다


@pytest.mark.parametrize("band", ["초등", "중등", "고등", "대학"])
def test_all_bands_round_trip(band: str) -> None:
    """네 밴드 모두 기본 사칙연산을 정상 낭독(프로파일 로드·엔진 배선 smoke)."""
    spec = speak_latex(r"1 + 2", band)
    assert spec.plain_text == "일 더하기 이"
    assert spec.grade_band == band
