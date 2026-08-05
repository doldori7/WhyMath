"""`l4/polya/prompts.py` 순수 함수 단위테스트 — 학년 register 치환 (W0 — S-2).

학년축 최단경로 계획(`docs/strategy/grade_axis_mvp_shortest_path_v1.md`) §2.3·§3 W0.
`_grade_register`·`base_system_for_grade`는 결정론적 문구 치환 함수(LLM 0회) — 여기서
매핑표 전체와 회귀 0 계약(grade=None → `_BASE_SYSTEM`과 바이트 동일)을 못 박는다.
"""

from __future__ import annotations

import pytest

from whymath_backend.l4.polya.prompts import (
    _BASE_SYSTEM,
    _grade_register,
    base_system_for_grade,
)


class TestGradeRegister:
    def test_none_falls_back_to_default(self) -> None:
        assert _grade_register(None) == "중·고등학생"

    @pytest.mark.parametrize(
        ("grade", "expected"),
        [
            (1, "초등학생"),
            (6, "초등학생"),
            (7, "중학생"),
            (9, "중학생"),
            (10, "고등학생"),
            (12, "고등학생"),
            (13, "대학생"),
            (16, "대학생"),
        ],
    )
    def test_grade_band_boundaries(self, grade: int, expected: str) -> None:
        assert _grade_register(grade) == expected

    @pytest.mark.parametrize("grade", [0, -1, 17, 100])
    def test_out_of_range_falls_back_to_default(self, grade: int) -> None:
        assert _grade_register(grade) == "중·고등학생"


class TestBaseSystemForGrade:
    def test_none_is_byte_identical_to_base_system_constant(self) -> None:
        assert base_system_for_grade(None) == _BASE_SYSTEM

    def test_high_school_range_uses_high_school_register_not_legacy_combined(self) -> None:
        # grade=11(현재 UserProfile 실호출 범위 10~14 안)은 "고등학생"이지 구 결합 표현
        # "중·고등학생"이 아니다 — 그 표현은 grade=None(미상) 폴백 전용.
        out = base_system_for_grade(11)
        assert "너는 한국 고등학생을 돕는" in out
        assert out != _BASE_SYSTEM

    def test_elementary_register_appears_verbatim(self) -> None:
        out = base_system_for_grade(3)
        assert "너는 한국 초등학생을 돕는" in out
        assert "중·고등학생" not in out

    def test_university_register_appears_verbatim(self) -> None:
        out = base_system_for_grade(14)
        assert "너는 한국 대학생을 돕는" in out

    def test_only_identity_clause_varies_rest_is_grade_invariant(self) -> None:
        """5원칙·톤 본문은 register와 무관하게 4축 공용(구조 분기 아님) — 문구만 다르다."""
        elementary = base_system_for_grade(3)
        university = base_system_for_grade(14)
        # 정체성 문구 제외 나머지 본문은 바이트 동일해야.
        elementary_rest = elementary.split("을 돕는", 1)[1]
        university_rest = university.split("을 돕는", 1)[1]
        assert elementary_rest == university_rest
