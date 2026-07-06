"""스켈레톤 rule-based 난이도 추정(S2-p) — 공식 표·클램프·결정론 단위테스트."""

from __future__ import annotations

import pytest

from whymath_backend.l3.equivalent.difficulty import (
    RootKind,
    estimate_difficulty,
    estimate_difficulty_extremum,
)


class TestFormulaTable:
    """모듈 docstring 공식 표의 대표 케이스 — 항별 가산이 정확한지."""

    @pytest.mark.parametrize(
        ("root_kind", "lead", "max_abs", "expected"),
        [
            # base 2.0 — 정수근·a=1·작은 계수(인수분해 기본형).
            ("integer", 1, 8, 2.0),
            # 근 유형 가산 — double +0.3 · rational +0.6 · irrational +1.2.
            ("double", 1, 9, 2.3),
            ("rational", 1, 10, 2.6),
            ("irrational", 1, 10, 3.2),
            # 선두계수 a≥2 +0.3.
            ("integer", 2, 10, 2.3),
            ("rational", 3, 9, 2.9),
            # 계수 크기 — 10<c≤30 +0.2 · c>30 +0.4 (경계 포함 확인).
            ("integer", 1, 11, 2.2),
            ("integer", 1, 30, 2.2),
            ("integer", 1, 31, 2.4),
            # 전 항 결합(현 풀 최고 근방) — rational·a≥2·큰 계수.
            ("rational", 2, 42, 3.3),
            ("irrational", 1, 31, 3.6),
        ],
    )
    def test_representative_cases(
        self, root_kind: RootKind, lead: int, max_abs: int, expected: float
    ) -> None:
        actual = estimate_difficulty(
            root_kind=root_kind, lead_coefficient=lead, max_abs_coefficient=max_abs
        )
        assert actual == expected


class TestRangeAndDeterminism:
    def test_always_within_scale(self) -> None:
        # 어떤 조합이라도 1.0~5.0 척도 안(클램프) — 극단 입력 포함.
        kinds: tuple[RootKind, ...] = ("integer", "double", "rational", "irrational")
        for kind in kinds:
            for lead in (1, 2, 3, 99):
                for max_abs in (1, 10, 30, 10_000):
                    value = estimate_difficulty(
                        root_kind=kind, lead_coefficient=lead, max_abs_coefficient=max_abs
                    )
                    assert 1.0 <= value <= 5.0
                    # 소수 1자리 반올림(표시·비교 안정).
                    assert value == round(value, 1)

    def test_deterministic(self) -> None:
        a = estimate_difficulty(root_kind="rational", lead_coefficient=2, max_abs_coefficient=12)
        b = estimate_difficulty(root_kind="rational", lead_coefficient=2, max_abs_coefficient=12)
        assert a == b

    def test_ordering_by_root_kind(self) -> None:
        # 같은 계수면 정수근 < 중근 < 유리근 < 무리근(공식의 교수학 서열 보존).
        values = [
            estimate_difficulty(root_kind=kind, lead_coefficient=1, max_abs_coefficient=5)
            for kind in ("integer", "double", "rational", "irrational")
        ]
        assert values == sorted(values)
        assert len(set(values)) == 4


class TestExtremumFormula:
    """미적분 극값 난이도 — 공식 표·클램프·서열(base 3.0·간격·계수 가산)."""

    @pytest.mark.parametrize(
        ("root_spread", "max_abs", "expected"),
        [
            # base 3.0 — 좁은 간격·작은 계수(미적분Ⅰ 극값 기본형).
            (2, 9, 3.0),
            (4, 30, 3.0),  # 경계 포함(≤4·≤30은 가산 0).
            # 임계점 간격 — 4<spread≤8 +0.3 · >8 +0.5.
            (5, 9, 3.3),
            (8, 9, 3.3),
            (9, 9, 3.5),
            # 계수 크기 — 30<c≤80 +0.3 · >80 +0.5.
            (2, 31, 3.3),
            (2, 80, 3.3),
            (2, 81, 3.5),
            # 전 항 결합.
            (9, 81, 4.0),
        ],
    )
    def test_representative_cases(self, root_spread: int, max_abs: int, expected: float) -> None:
        assert (
            estimate_difficulty_extremum(root_spread=root_spread, max_abs_coefficient=max_abs)
            == expected
        )

    def test_always_within_scale_and_above_quadratic_base(self) -> None:
        # 어떤 조합이라도 [1.0,5.0]·1자리, 그리고 극값 base(3.0)는 이차 근 base(2.0)보다 상향.
        for spread in (1, 4, 8, 20, 10_000):
            for max_abs in (1, 30, 80, 10_000):
                value = estimate_difficulty_extremum(
                    root_spread=spread, max_abs_coefficient=max_abs
                )
                assert 1.0 <= value <= 5.0
                assert value == round(value, 1)
                assert value >= 3.0  # 미분+부호판정이 이차 근보다 어렵다(base 상향)

    def test_deterministic(self) -> None:
        a = estimate_difficulty_extremum(root_spread=6, max_abs_coefficient=40)
        b = estimate_difficulty_extremum(root_spread=6, max_abs_coefficient=40)
        assert a == b
