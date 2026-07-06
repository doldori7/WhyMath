"""스켈레톤 rule-based 난이도 추정(S2-p) — 공식 표·클램프·결정론 단위테스트."""

from __future__ import annotations

import pytest

from whymath_backend.l3.equivalent.difficulty import RootKind, estimate_difficulty


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
