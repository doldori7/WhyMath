"""기호 항등성 primitive 단위테스트 — `identity_status` 4상태(동치 권위 단일·감사 §7).

`verify_step`이 위임하는 SymPy 관용구를 *직접* 검증한다 — identity(항등 확정)·not_identity(거짓
증명)·undecidable(정의역 의존·초월·미결정)·parse_error(빈/파싱 불가). 카탈로그
`canonical_wrong_form` 무결성과 verify_step 3상태가 *같은 권위*를 거치게 됐음을 못 박는다.
"""

from __future__ import annotations

import pytest

from whymath_backend.l3.symbolic_equivalence import (
    IdentityVerdict,
    identity_status,
    to_sympy_source,
)


class TestIdentity:
    @pytest.mark.parametrize(
        ("lhs", "rhs"),
        [
            ("2*(x+1)", "2*x + 2"),  # 다항 항등식(자유변수 OK)
            ("(a+b)**2", "a**2 + 2*a*b + b**2"),  # 완전제곱(올바른 전개)
            ("sin(x)**2 + cos(x)**2", "1"),  # 삼각 항등식(비다항·simplify 보강)
            ("x^2", "x*x"),  # convert_xor=True → ^=거듭제곱
        ],
    )
    def test_identity(self, lhs: str, rhs: str) -> None:
        assert identity_status(lhs, rhs) is IdentityVerdict.identity


class TestNotIdentity:
    @pytest.mark.parametrize(
        ("lhs", "rhs"),
        [
            ("(a+b)**2", "a**2 + b**2"),  # freshman's dream(diff=2ab·다항 비항등)
            ("a**0", "0"),  # a**0=1 ≠ 0(상수 차)
            ("2 + 3", "6"),  # 수치 오답(상수 차 확정)
            ("x + 1", "x + 2"),  # 같은 변수 다항 비항등
        ],
    )
    def test_not_identity(self, lhs: str, rhs: str) -> None:
        assert identity_status(lhs, rhs) is IdentityVerdict.not_identity


class TestUndecidable:
    @pytest.mark.parametrize(
        ("lhs", "rhs"),
        [
            ("sqrt(x**2)", "x"),  # 정의역 의존(|x| vs x) — 가정 없이 미결정
            ("log(a+b)", "log(a) + log(b)"),  # 초월·미결정
        ],
    )
    def test_undecidable(self, lhs: str, rhs: str) -> None:
        assert identity_status(lhs, rhs) is IdentityVerdict.undecidable


class TestParseError:
    @pytest.mark.parametrize(
        ("lhs", "rhs"),
        [
            ("", "x"),  # 빈 입력
            ("x", "   "),  # 공백
            ("2 +* 3", "5"),  # 파싱 불가(SympifyError)
        ],
    )
    def test_parse_error(self, lhs: str, rhs: str) -> None:
        assert identity_status(lhs, rhs) is IdentityVerdict.parse_error


class TestSuperscriptNormalization:
    """유니코드 위첨자 정규화 — `identity_status`가 `to_sympy_source`를 내부 적용(감사 §7 해소).

    과거엔 위첨자 치환이 L4에만 있어 `identity_status`가 `x²`를 parse_error로 떨궜다 — 이제 동치
    권위가 위첨자를 직접 정규화하므로 학생 손글씨·MathLive 위첨자 입력이 올바로 판정된다.
    """

    def test_superscript_identity(self) -> None:
        # `x²` 위첨자가 `x**2`와 항등(과거엔 parse_error였음 — strict 개선).
        assert identity_status("x²", "x**2") is IdentityVerdict.identity

    def test_superscript_expansion_identity(self) -> None:
        assert identity_status("(a+b)²", "a²+2*a*b+b²") is IdentityVerdict.identity

    def test_superscript_freshman_dream_not_identity(self) -> None:
        # (a+b)² ≠ a²+b² — 위첨자 입력도 거짓이 *증명*된다(같은 변수 0-아닌 다항).
        assert identity_status("(a+b)²", "a²+b²") is IdentityVerdict.not_identity

    def test_to_sympy_source_maps_all_digits_and_strips(self) -> None:
        assert to_sympy_source("  x²  ") == "x**2"
        assert to_sympy_source("a⁵+b⁰") == "a**5+b**0"

    def test_to_sympy_source_idempotent_on_ascii(self) -> None:
        # 이미 ASCII면 무변화(멱등) — caret(^)은 건드리지 않는다(convert_xor 담당).
        assert to_sympy_source("x**2 + 3") == "x**2 + 3"
        assert to_sympy_source("x^2") == "x^2"


class TestUnicodeOperatorNormalization:
    """비ASCII 수학 연산자(−·×·÷) 정규화 — S3-06 실측 동결(이미 `_OPERATOR_MAP`이 처리).

    2026-07-19 자연 사용 재측정에서 학생 제출이 U+2212 마이너스를 담았다 — `to_sympy_source`가
    이를 ASCII로 접음을 실측 확인했고(추가 구현 불요), 회귀 방지를 위해 여기 동결한다.
    """

    def test_unicode_minus_folded(self) -> None:
        # U+2212 MINUS SIGN → ASCII 하이픈(실측: Kiki 제출 원문 표기).
        assert to_sympy_source("x−2") == "x-2"

    def test_unicode_multiplication_division_folded(self) -> None:
        # U+00D7(×) → * · U+00F7(÷) → /.
        assert to_sympy_source("2×x") == "2*x"
        assert to_sympy_source("6÷2") == "6/2"

    def test_unicode_minus_identity_judged(self) -> None:
        # 정규화 경유로 동치 판정까지 도달 — x−2 ≡ x-2.
        assert identity_status("x−2", "x-2") is IdentityVerdict.identity
