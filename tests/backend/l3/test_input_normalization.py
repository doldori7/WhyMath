"""입력 정규화 단위테스트 — 표기(notation) 정규화가 SymPy 진입 전에 messy 입력을 접는가.

Part 4(AST 의미 엔진) 항목4 — implicit multiplication · unary minus · chained equality ·
전각/Unicode 입력정규화 — 를 검증한다. `to_sympy_source`(단일 정규화 권위)와 `identity_status`
(동치 권위·`_parse` 암묵곱)가 학생/LLM/OCR의 비canonical 표기를 올바로 canonical로 접어 판정함을
못 박는다. **경계**: 여기는 *표기* 정규화(implicit `*`·전각·연산자·유니코드)만이다 — canonical
정규화(교환·약분)·CAS는 범위 밖(그 경계는 `identity_status`의 undecidable 보수성이 지킨다).

`pregenerate/validator.py`와 *동일한 보수 파싱*(`implicit_multiplication`만·`_application` 아님):
계수 병치(`2x`)·괄호 병치(`(x+1)(x-1)`)는 접지만, 함수 적용 병치(`sin x`)·순수 문자 병치(`xy`)는
추정하지 않는다(CLAUDE.md "확실하지 않으면 모른다").
"""

from __future__ import annotations

import pytest

from whymath_backend.l3.symbolic_equivalence import (
    IdentityVerdict,
    identity_status,
    split_relation_chain,
    to_sympy_source,
    verify_relation_chain,
)


class TestImplicitMultiplication:
    """암묵적 곱셈 — 계수·괄호 병치를 explicit `*`로 접어 동치 판정."""

    @pytest.mark.parametrize(
        ("lhs", "rhs"),
        [
            ("2x", "2*x"),  # 계수 병치
            ("2x(x+1)", "2*x**2 + 2*x"),  # 계수 + 괄호 병치(정규화 전엔 unverifiable)
            ("(x+1)(x-1)", "x^2-1"),  # 괄호-괄호 병치
            ("2sin(x)", "2*sin(x)"),  # 계수 + 함수(괄호 있음) 병치
            ("3x^2", "3*x**2"),  # 병치 + caret
        ],
    )
    def test_implicit_mult_identity(self, lhs: str, rhs: str) -> None:
        assert identity_status(lhs, rhs) is IdentityVerdict.identity

    def test_pure_letter_juxtaposition_not_split(self) -> None:
        # `xy`는 단일 심볼로 남는다(x*y로 *추정 안 함* — 보수). 따라서 x*y와 동치가 아님(미결정).
        assert to_sympy_source("xy") == "xy"
        assert identity_status("xy", "x*y") is not IdentityVerdict.identity


class TestUnaryMinus:
    @pytest.mark.parametrize(
        ("lhs", "rhs"),
        [
            ("-x", "0 - x"),  # 단항 마이너스
            ("--x", "x"),  # 이중 단항
            ("-(x+1)", "-x-1"),  # 괄호 분배
        ],
    )
    def test_unary_minus_identity(self, lhs: str, rhs: str) -> None:
        assert identity_status(lhs, rhs) is IdentityVerdict.identity


class TestNonAsciiOperators:
    """NFKC가 안 접는 유니코드 수학 연산자를 ASCII로 접는다(가장 흔한 함정: U+2212 마이너스)."""

    @pytest.mark.parametrize(
        ("raw", "expected_src"),
        [
            ("x−1", "x-1"),  # U+2212 MINUS SIGN → '-'
            ("2×3", "2*3"),  # U+00D7 → '*'
            ("a·b", "a*b"),  # U+00B7 MIDDLE DOT → '*'
            ("a⋅b", "a*b"),  # U+22C5 DOT OPERATOR → '*'
            ("6÷2", "6/2"),  # U+00F7 → '/'
        ],
    )
    def test_operator_map(self, raw: str, expected_src: str) -> None:
        assert to_sympy_source(raw) == expected_src

    def test_minus_sign_identity(self) -> None:
        # U+2212를 안 접으면 SymPy가 파싱 못 해 parse_error였을 케이스가 이제 판정된다.
        assert identity_status("x−1", "x-1") is IdentityVerdict.identity
        assert identity_status("2×3", "6") is IdentityVerdict.identity


class TestFullwidthNfkc:
    """전각(Fullwidth) → ASCII 접기(NFKC) — 한국어 IME 입력에서 흔함."""

    @pytest.mark.parametrize(
        ("raw", "expected_src"),
        [
            ("２ｘ", "2x"),  # 전각 숫자·문자 → ASCII(이후 파싱서 2*x)
            ("（x＋1）", "(x+1)"),  # 전각 괄호·플러스
            ("ｘ＊＊２", "x**2"),  # 전각 별표·숫자
        ],
    )
    def test_fullwidth_folds(self, raw: str, expected_src: str) -> None:
        assert to_sympy_source(raw) == expected_src

    def test_fullwidth_identity(self) -> None:
        assert identity_status("２ｘ", "2*x") is IdentityVerdict.identity
        assert identity_status("（x＋1）（x－1）", "x**2-1") is IdentityVerdict.identity


class TestGreekLetters:
    @pytest.mark.parametrize(
        ("raw", "expected_src"),
        [("2π", "2pi"), ("θ", "theta"), ("α+β", "alpha+beta")],
    )
    def test_greek_map(self, raw: str, expected_src: str) -> None:
        assert to_sympy_source(raw) == expected_src

    def test_greek_pi_identity(self) -> None:
        assert identity_status("2π", "2*pi") is IdentityVerdict.identity


class TestSuperscriptOrderingWithNfkc:
    """위첨자 치환이 NFKC보다 *먼저* 일어나야 지수 의미가 보존된다(순서 회귀 잠금)."""

    def test_superscript_survives_nfkc(self) -> None:
        # NFKC 단독이면 `²`→`2`로 분해돼 `x2`(곱)로 오독. 위첨자 선치환으로 `x**2` 보존.
        assert to_sympy_source("x²") == "x**2"

    def test_superscript_followed_by_factor_binds_correctly(self) -> None:
        # `x²y` → `x**2y` → 파싱 시 암묵곱으로 `x**2*y`(‘**’가 더 강하게 결합) — 오결합 회귀.
        assert to_sympy_source("x²y") == "x**2y"
        assert identity_status("x²y", "x**2*y") is IdentityVerdict.identity


class TestNormalizationIdempotent:
    def test_idempotent(self) -> None:
        for raw in ["2×x²", "（x＋1）", "2π−1", "x**2 + 3"]:
            once = to_sympy_source(raw)
            assert to_sympy_source(once) == once


class TestChainedEquality:
    """등식 체인 `a=b=c` 처리 — 인접 쌍 분해 + 동치 권위(`identity_status`) 재사용."""

    def test_split_three_term(self) -> None:
        assert split_relation_chain("a=b=c") == [("a", "b"), ("b", "c")]

    def test_split_single_equation(self) -> None:
        assert split_relation_chain("x+1=1+x") == [("x+1", "1+x")]

    def test_split_no_equals_returns_empty(self) -> None:
        assert split_relation_chain("x+1") == []

    @pytest.mark.parametrize("src", ["a<=b", "a==b", "a<b", "a!=b", "a>=b"])
    def test_split_rejects_comparison(self, src: str) -> None:
        with pytest.raises(ValueError, match="등식"):
            split_relation_chain(src)

    @pytest.mark.parametrize("src", ["a=", "=b", "a==b=c"])
    def test_split_rejects_malformed(self, src: str) -> None:
        with pytest.raises(ValueError):
            split_relation_chain(src)

    def test_verify_true_chain(self) -> None:
        assert verify_relation_chain("x+1=1+x=x+1") is IdentityVerdict.identity

    def test_verify_false_chain(self) -> None:
        # 한 링크라도 거짓이면 체인 전체가 not_identity로 *증명*된다.
        assert verify_relation_chain("x=x+1") is IdentityVerdict.not_identity
        assert verify_relation_chain("x+1=x+1=x+2") is IdentityVerdict.not_identity

    def test_verify_undecidable_chain(self) -> None:
        # 정의역 의존 링크는 undecidable로 보수(위장 없음).
        assert verify_relation_chain("sqrt(x^2)=x") is IdentityVerdict.undecidable

    def test_verify_empty_chain_parse_error(self) -> None:
        assert verify_relation_chain("x+1") is IdentityVerdict.parse_error
