"""Wilson 단측 신뢰경계 — 값 동결 + **docstring 예시와 구현의 정합**.

이 파일이 생긴 경위(2026-09-01): `wilson.py` docstring이 "5/5·95% → ≈0.565"라고 적어
왔는데 구현은 0.6489를 낸다. 0.565는 **양측** z=1.96의 값이고 이 모듈은 이름대로
**단측**(z=Φ⁻¹(0.95)=1.645)이다. 판정은 늘 구현이 했으므로 게이트 결과는 정확했고
틀린 것은 설명이었다 — 그런데 **아무 테스트도 그 불일치를 잡지 않았다**. 이 모듈은
저장소 전 게이트의 판정 권위인데 값을 동결하는 테스트가 0건이었기 때문이다.

그래서 두 가지를 동결한다:
  1. 두 경계의 **실제 값**(회귀 시 즉시 적색)
  2. **docstring 예시와 구현의 정합** — 설명이 구현에서 미끄러지면 미래 세션이 구현
     쪽을 결함으로 오판한다. 산문을 사람이 관리하면 다시 미끄러지므로 기계가 대조한다.
"""

from __future__ import annotations

import re

import pytest

from whymath_backend.harness import wilson
from whymath_backend.harness.wilson import wilson_lower_bound, wilson_upper_bound

_CONFIDENCE = 0.95


class TestFrozenValues:
    """경계값 동결 — 산술이 바뀌면 저장소의 모든 게이트 판정이 함께 움직인다."""

    def test_perfect_small_sample_is_heavily_discounted(self) -> None:
        """5/5=1.0 점추정이 0.65 근처로 깎인다 — "작은 시험으로 거짓 통과"를 막는 핵심."""
        assert wilson_lower_bound(5, 5, _CONFIDENCE) == pytest.approx(0.6489, abs=5e-4)

    def test_zero_observations_still_leaves_room_above_zero(self) -> None:
        """0/5의 상한은 0이 아니다 — "관측 0 = 확정 0"으로 과신하지 않는다(모르면 모른다)."""
        upper = wilson_upper_bound(0, 5, _CONFIDENCE)
        assert upper > 0.0, "관측 0을 확정 0으로 접었다"
        assert upper == pytest.approx(0.3511, abs=5e-4)

    def test_larger_samples_are_discounted_less(self) -> None:
        """같은 비율이면 표본이 클수록 경계가 점추정에 가까워진다 — 보정의 방향성."""
        small = wilson_lower_bound(50, 100, _CONFIDENCE)
        large = wilson_lower_bound(500, 1000, _CONFIDENCE)
        assert small < large < 0.5, f"표본이 커져도 덜 깎이지 않았다: {small} → {large}"

    def test_bounds_bracket_the_point_estimate(self) -> None:
        """하한 ≤ 점추정 ≤ 상한 — 방향을 뒤집어 쓰면 여기서 걸린다."""
        for hits, trials in ((3, 10), (40, 4000), (700, 1000)):
            point = hits / trials
            assert wilson_lower_bound(hits, trials, _CONFIDENCE) <= point
            assert wilson_upper_bound(hits, trials, _CONFIDENCE) >= point


class TestDocstringMatchesImplementation:
    """**설명이 구현에서 미끄러지지 않는가** — 이 파일이 생긴 이유 그 자체.

    docstring의 예시 수치를 파싱해 구현과 대조한다. 산문을 사람이 관리하면 다시
    미끄러지므로(실제로 미끄러져 있었다) 기계가 붙든다.
    """

    def test_the_documented_example_is_what_the_code_actually_returns(self) -> None:
        doc = wilson.__doc__ or ""
        match = re.search(r"5/5·95%\s*\n?\s*→\s*≈([0-9.]+)", doc)
        assert (
            match
        ), "docstring의 '5/5·95% → ≈X' 예시를 찾지 못했다 — 형식이 바뀌었으면 이 테스트도 함께 고친다"
        documented = float(match.group(1))
        actual = wilson_lower_bound(5, 5, _CONFIDENCE)
        assert documented == pytest.approx(actual, abs=1e-3), (
            f"docstring 예시({documented})와 구현({actual:.4f})이 어긋난다. "
            "판정은 구현이 하므로 게이트는 정확하지만, 설명이 틀리면 미래 세션이 "
            "구현 쪽을 결함으로 오판한다"
        )

    def test_this_module_is_one_sided_not_two_sided(self) -> None:
        """단측임을 못박는다 — 양측(z=1.96) 값을 적어 넣던 것이 이 파일의 발단이다.

        양측이었다면 5/5 하한이 ≈0.565다. 구현이 그 값을 내면 모듈 이름과 docstring의
        '단측' 주장이 거짓이 된다.
        """
        actual = wilson_lower_bound(5, 5, _CONFIDENCE)
        two_sided_value = 0.565
        assert actual != pytest.approx(
            two_sided_value, abs=5e-3
        ), "단측이라고 선언한 모듈이 양측 값을 냈다"
