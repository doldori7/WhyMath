"""`Role` enum 동결 테스트 — SEC-07 D1.

v0 2값(STUDENT/CONTENT_ADMIN)·서열 비교 부재를 동결한다. `docs/architecture/
account_security_gap_review.md` §2-①이 반증하듯(`docs/legal/pipa_data_matrix.md:33-47` —
부모의 데이터 가시성은 학생 본인의 *부분집합*이지 상위집합이 아님) 7단 선형 서열은 이 앱의
데이터 모델과 구조적으로 모순된다. 이 테스트는 미래 세션이 그 서열을 조용히 되살리지
못하도록 멤버 수와 비교 연산 부재를 고정한다.
"""

from __future__ import annotations

from collections.abc import Callable
from enum import Enum, IntEnum

import pytest

from whymath_backend.schema.enums import Role


class TestExactlyTwoMembers:
    def test_role_has_exactly_two_members(self) -> None:
        """v0 확정 — STUDENT·CONTENT_ADMIN 2값뿐(PARENT/TEACHER/SCHOOL_ADMIN 등 미도입)."""
        assert len(list(Role)) == 2

    def test_role_members_are_student_and_content_admin(self) -> None:
        assert {member.value for member in Role} == {"student", "content_admin"}
        assert Role.STUDENT.value == "student"
        assert Role.CONTENT_ADMIN.value == "content_admin"


class TestNoOrderingSupport:
    """7단 선형 서열 재도입 방지 — `<`/`>`/`<=`/`>=`가 TypeError를 던져야 한다.

    `Role`은 다른 `schema/enums.py` enum과 달리 `str` mixin을 쓰지 않는다(house style
    이탈은 의도적 — enums.py `Role` docstring 참조). str mixin이면 멤버가 사전식으로
    비교 가능해져(`"content_admin" < "student"`) 서열 연산 자체가 *존재*하게 되고, 값 자체가
    무의미한 사전순이라도 미래 세션이 실수로 등급 비교 코드를 짤 여지를 준다.
    """

    def test_role_is_not_int_enum(self) -> None:
        """IntEnum이면 정의상 서열이 생긴다 — 채택 금지를 타입으로 고정."""
        assert not issubclass(Role, IntEnum)

    def test_role_does_not_mix_in_str(self) -> None:
        """str mixin이면 사전식 비교가 열린다 — Role은 순수 Enum이어야 한다."""
        assert not issubclass(Role, str)
        assert issubclass(Role, Enum)

    @pytest.mark.parametrize(
        "op",
        [
            lambda a, b: a < b,
            lambda a, b: a > b,
            lambda a, b: a <= b,
            lambda a, b: a >= b,
        ],
    )
    def test_comparison_operators_raise_type_error(self, op: Callable[[Role, Role], bool]) -> None:
        with pytest.raises(TypeError):
            op(Role.STUDENT, Role.CONTENT_ADMIN)
