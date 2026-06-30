"""기호 항등성 primitive 단위테스트 — `identity_status` 4상태(동치 권위 단일·감사 §7).

`verify_step`이 위임하는 SymPy 관용구를 *직접* 검증한다 — identity(항등 확정)·not_identity(거짓
증명)·undecidable(정의역 의존·초월·미결정)·parse_error(빈/파싱 불가). 카탈로그
`canonical_wrong_form` 무결성과 verify_step 3상태가 *같은 권위*를 거치게 됐음을 못 박는다.
"""

from __future__ import annotations

import pytest

from whymath_backend.l3.symbolic_equivalence import IdentityVerdict, identity_status


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
