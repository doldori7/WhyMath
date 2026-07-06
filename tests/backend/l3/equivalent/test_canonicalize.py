"""동등문제 정규화(S2-l `canonicalize.py`) — 표현 변형이 같은 signature로 접히는지 검증.

핵심 계약: 같은 방정식의 표기 변형(등호표기·인수분해·계수 스케일·부호·발문 문구 무관)은 같은
signature, 다른 방정식·다른 근 선택은 다른 signature. 정규화 불가(비다항·pseudo DSL)는 None.
"""

from __future__ import annotations

from whymath_backend.l3.equivalent.canonicalize import (
    canonical_condition,
    canonical_signature,
)


class TestCanonicalCondition:
    def test_equation_variants_fold_to_same_key(self) -> None:
        variants = [
            "x**2 - 10*x + 24 = 0",
            "x**2 - 10*x + 24 == 0",
            "(x-4)*(x-6) = 0",
            "2*x**2 - 20*x + 48 = 0",  # 계수 스케일
            "-x**2 + 10*x - 24 = 0",  # 부호 반전
            "x**2 - 10*x + 24",  # 등호 없는 단일 식
        ]
        keys = {canonical_condition(v) for v in variants}
        assert len(keys) == 1
        assert None not in keys

    def test_different_equations_differ(self) -> None:
        assert canonical_condition("x**2 - 4*x + 3 = 0") != canonical_condition(
            "x**2 - 5*x + 6 = 0"
        )

    def test_xor_power_notation_supported(self) -> None:
        # `^`(convert_xor)도 거듭제곱으로 접어 `**`와 같은 key.
        assert canonical_condition("x^2 - 4*x + 3 = 0") == canonical_condition("x**2 - 4*x + 3 = 0")

    def test_pseudo_dsl_is_none(self) -> None:
        # LLM이 내는 pseudo-symbolic(solve/largest_root)은 정규화 밖 → None(임베딩에 위임).
        assert canonical_condition("solve(x**2 - 10*x + 24, x) == [6, 4]") is None
        assert canonical_condition("largest_root(2, 8) == 8") is None

    def test_constant_condition_is_none(self) -> None:
        assert canonical_condition("3 = 3") is None

    def test_empty_is_none(self) -> None:
        assert canonical_condition("   ") is None


class TestCanonicalSignature:
    def test_same_equation_same_selection_same_signature(self) -> None:
        a = canonical_signature("x**2 - 10*x + 24 = 0", "largest")
        b = canonical_signature("(x-4)*(x-6) == 0", "largest")
        assert a is not None
        assert a == b

    def test_same_equation_different_selection_differs(self) -> None:
        # 같은 방정식이라도 큰 근 vs 작은 근은 별개 문제 → 다른 signature.
        big = canonical_signature("x**2 - 10*x + 24 = 0", "largest")
        small = canonical_signature("x**2 - 10*x + 24 = 0", "smallest")
        assert big is not None and small is not None
        assert big != small

    def test_system_order_independent(self) -> None:
        a = canonical_signature(["x + y = 3", "x - y = 1"], "unique")
        b = canonical_signature(["x - y = 1", "x + y = 3"], "unique")
        assert a is not None
        assert a == b

    def test_none_when_any_condition_unnormalizable(self) -> None:
        # 한 조건이라도 정규화 불가면 전체 None(부분 정규화 오병합 금지).
        assert canonical_signature(["x**2 - 1 = 0", "solve(x, x) == [1]"], "largest") is None

    def test_deterministic(self) -> None:
        s1 = canonical_signature("x**2 - 5*x + 6 = 0", "largest")
        s2 = canonical_signature("x**2 - 5*x + 6 = 0", "largest")
        assert s1 == s2
        assert s1 is not None and len(s1) == 16
