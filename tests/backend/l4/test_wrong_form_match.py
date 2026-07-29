"""오개념 거짓 항등식 SymPy 탐지 단위테스트 — Wild 정합·등식 추출·shadow(감사 §7).

`matches_wrong_form`(기호 인스턴스 정합·정답/수치/degenerate 비정합)·`extract_equations`(prose
무관 추출)·`detect_wrong_forms`·`observe_wrong_form_shadow`(off no-op·shadow 로그·never-break·
프라이버시)를 라이브 의존 없이 검증한다. SymPy는 수치(`(3+4)²`)를 평가해 못 잡고 *기호*(`(x+y)²`)를
잡는다는 스코프를 못 박는다.
"""

from __future__ import annotations

import logging

import pytest
from whymath_backend.config import get_settings
from whymath_backend.l4.misconception import wrong_form_match
from whymath_backend.l4.misconception.wrong_form_match import (
    WrongFormShadowObservation,
    detect_wrong_forms,
    extract_equations,
    matches_wrong_form,
    observe_wrong_form_shadow,
)

# distribution-over-power의 canonical_wrong_form(카탈로그 정본과 동일).
_DISTRIBUTION = ("(a+b)**2", "a**2 + b**2")
_RECORD_LOGGER = "whymath.l4.misconception.wrong_form_shadow.record"
_ENV = "WHYMATH_MISCONCEPTION_WRONG_FORM_MODE"


class TestExtractEquations:
    def test_extracts_around_korean_prose(self) -> None:
        eqs = extract_equations("학생 풀이: (x+y)² = x²+y² 이므로 답은...")
        assert ("(x+y)²", "x²+y²") in eqs

    def test_no_equation(self) -> None:
        assert extract_equations("등식이 전혀 없는 한글 문장") == []

    def test_multiple(self) -> None:
        eqs = extract_equations("a = b 그리고 c = d")
        assert ("a", "b") in eqs and ("c", "d") in eqs


class TestMatchesWrongForm:
    def test_symbolic_instance_different_vars(self) -> None:
        # substring이 놓치는 변수명 변이 — SymPy가 잡는 순기여.
        assert matches_wrong_form("(x+y)**2", "x**2+y**2", _DISTRIBUTION) is True
        assert matches_wrong_form("(p+q)**2", "p**2+q**2", _DISTRIBUTION) is True

    def test_unicode_superscript_instance(self) -> None:
        assert matches_wrong_form("(x+y)²", "x²+y²", _DISTRIBUTION) is True

    def test_correct_form_not_matched(self) -> None:
        # 올바른 완전제곱 → 거짓 규칙 아님(기대 거짓 rhs와 동치 아님).
        assert matches_wrong_form("(x+y)**2", "x**2+2*x*y+y**2", _DISTRIBUTION) is False

    def test_numeric_instance_matched(self) -> None:
        # evaluate=False 구조 보존 → 수치 인스턴스도 잡는다(regex_signals 일반화).
        assert matches_wrong_form("(3+4)**2", "3**2+4**2", _DISTRIBUTION) is True

    def test_numeric_correct_answer_not_matched(self) -> None:
        # (3+4)²=49는 올바른 값 → 기대 거짓 rhs(25)와 불일치 → 미정합.
        assert matches_wrong_form("(3+4)**2", "49", _DISTRIBUTION) is False

    def test_numeric_coincidental_true_not_matched(self) -> None:
        # (3+0)²=3²+0²=9는 *우연히 참* → 거짓 등식 가드가 제외(거짓 낙인 차단·RS2).
        assert matches_wrong_form("(3+0)**2", "3**2+0**2", _DISTRIBUTION) is False

    def test_garbage_not_matched(self) -> None:
        assert matches_wrong_form("선생님", "안녕", _DISTRIBUTION) is False

    def test_degenerate_constant_template_not_matched(self) -> None:
        # a**0 → 1(상수 평가·구조 소실) → 구조 정합 불가(거짓 주장 금지).
        assert matches_wrong_form("x**0", "0", ("a**0", "0")) is False


class TestDetectWrongForms:
    def test_detects_distribution_symbolic(self) -> None:
        assert detect_wrong_forms("(x+y)² = x²+y²") == ["distribution-over-power"]

    def test_correct_solution_no_detection(self) -> None:
        assert detect_wrong_forms("(x+y)² = x²+2xy+y²") == []

    def test_no_equation_no_detection(self) -> None:
        assert detect_wrong_forms("등식 없는 서술") == []


class TestObserveWrongFormShadow:
    def test_off_is_noop(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        monkeypatch.setenv(_ENV, "off")
        get_settings.cache_clear()
        try:
            with caplog.at_level(logging.INFO, logger=_RECORD_LOGGER):
                observe_wrong_form_shadow("(x+y)² = x²+y²")
            assert [r for r in caplog.records if r.name == _RECORD_LOGGER] == []
        finally:
            get_settings.cache_clear()

    def test_shadow_logs_sympy_only(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        monkeypatch.setenv(_ENV, "shadow")
        get_settings.cache_clear()
        try:
            with caplog.at_level(logging.INFO, logger=_RECORD_LOGGER):
                observe_wrong_form_shadow("(x+y)² = x²+y²")
            records = [r.getMessage() for r in caplog.records if r.name == _RECORD_LOGGER]
            assert len(records) == 1
            obs = WrongFormShadowObservation.model_validate_json(records[0])
            # substring은 변수명 변이를 놓치고 SymPy만 잡는다(순기여).
            assert "distribution-over-power" in obs.sympy_detected_ids
            assert "distribution-over-power" in obs.sympy_only_ids
        finally:
            get_settings.cache_clear()

    def test_shadow_never_breaks(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(_ENV, "shadow")
        get_settings.cache_clear()

        def _boom(_text: str) -> list[str]:
            raise RuntimeError("탐지 실패")

        monkeypatch.setattr(wrong_form_match, "detect_wrong_forms", _boom)
        try:
            # 예외 전파 0(반환 None) — 본류(코칭) 보호.
            observe_wrong_form_shadow("(x+y)² = x²+y²")
        finally:
            get_settings.cache_clear()

    def test_record_has_no_student_text(self) -> None:
        # extra='forbid'·모델 필드 한정 — 학생 풀이 원문이 구조적으로 못 들어간다(미성년 PII).
        obs = WrongFormShadowObservation(
            sympy_detected_ids=["distribution-over-power"],
            substring_detected_ids=[],
            sympy_only_ids=["distribution-over-power"],
        )
        keys = set(obs.model_dump().keys())
        assert keys == {
            "sympy_detected_ids",
            "substring_detected_ids",
            "sympy_only_ids",
            "observed_at",
        }
