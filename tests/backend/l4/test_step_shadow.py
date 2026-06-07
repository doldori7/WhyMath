"""L4 step_shadow 단위테스트 — 중간 step 등가성 shadow 관측(비노출·비차단·게이트).

워커 shadow(`test_celery_tasks.py::TestWorkerShadowValidation`)와 동형: 게이트 on/off를
`monkeypatch.setenv` + `get_settings.cache_clear()`로 격리하고 caplog로 로그를 단언한다.
"""

from __future__ import annotations

import logging
import uuid

import pytest

from whymath_backend.config import get_settings
from whymath_backend.l4 import step_shadow
from whymath_backend.l4.step_shadow import observe_step_breaks

# 단계 비보존(해 {3}≠{4}) + 순차유도 마커(따라서) → detect_step_breaks가 검출하는 입력.
_NONPRESERVING = "2x = 6 따라서 3x = 12"


def _shadow_messages(caplog: pytest.LogCaptureFixture) -> list[str]:
    """step_shadow 로거가 낸 메시지만(다른 로거 노이즈 배제)."""
    return [r.getMessage() for r in caplog.records if r.name == "whymath.l4.step_shadow"]


class TestObserveStepBreaks:
    def test_gate_on_logs_break(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        # 게이트 on + 비보존+마커 → INFO 로그(신호 var·해집합 포함).
        monkeypatch.setenv("WHYMATH_L4_STEP_SHADOW_ENABLED", "true")
        get_settings.cache_clear()
        try:
            with caplog.at_level(logging.INFO, logger="whymath.l4.step_shadow"):
                observe_step_breaks(_NONPRESERVING)
            msgs = _shadow_messages(caplog)
            assert any("단계 비보존 의심" in m for m in msgs)
            assert any("var=x" in m for m in msgs)
        finally:
            get_settings.cache_clear()

    def test_gate_on_logs_problem_context(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        # slice 64: 문항 맥락(problem_id·expected_answer)이 shadow 로그에 주입된다(진단 라벨용).
        monkeypatch.setenv("WHYMATH_L4_STEP_SHADOW_ENABLED", "true")
        get_settings.cache_clear()
        pid = uuid.UUID("00000000-0000-0000-0000-0000000000aa")
        try:
            with caplog.at_level(logging.INFO, logger="whymath.l4.step_shadow"):
                observe_step_breaks(_NONPRESERVING, problem_id=pid, expected_answer="x = 3")
            msgs = _shadow_messages(caplog)
            assert any(str(pid) in m for m in msgs)
            assert any("expected='x = 3'" in m for m in msgs)  # %r → repr(정답)
        finally:
            get_settings.cache_clear()

    def test_context_defaults_none_backward_compat(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        # slice 63 호출(맥락 인자 없음)도 그대로 동작 — problem_id=None expected=None으로 로그.
        monkeypatch.setenv("WHYMATH_L4_STEP_SHADOW_ENABLED", "true")
        get_settings.cache_clear()
        try:
            with caplog.at_level(logging.INFO, logger="whymath.l4.step_shadow"):
                observe_step_breaks(_NONPRESERVING)
            msgs = _shadow_messages(caplog)
            assert any("problem_id=None" in m for m in msgs)
            assert any("expected=None" in m for m in msgs)
        finally:
            get_settings.cache_clear()

    def test_gate_off_no_log(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        # 게이트 off(기본) → 검출조차 안 돌고 로그 0.
        monkeypatch.setenv("WHYMATH_L4_STEP_SHADOW_ENABLED", "false")
        get_settings.cache_clear()
        try:
            with caplog.at_level(logging.INFO, logger="whymath.l4.step_shadow"):
                observe_step_breaks(_NONPRESERVING)
            assert _shadow_messages(caplog) == []
        finally:
            get_settings.cache_clear()

    def test_no_marker_no_log(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        # 게이트 on이나 마커 없음 → 검출 0 → 로그 0.
        monkeypatch.setenv("WHYMATH_L4_STEP_SHADOW_ENABLED", "true")
        get_settings.cache_clear()
        try:
            with caplog.at_level(logging.INFO, logger="whymath.l4.step_shadow"):
                observe_step_breaks("2x = 6\n3x = 12")  # 마커 없음
            assert _shadow_messages(caplog) == []
        finally:
            get_settings.cache_clear()

    def test_exception_swallowed(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        # detect_step_breaks가 던져도 observe_step_breaks는 조용히 반환(본류 비차단).
        monkeypatch.setenv("WHYMATH_L4_STEP_SHADOW_ENABLED", "true")
        get_settings.cache_clear()

        def _boom(*_args: object, **_kwargs: object) -> list[object]:
            raise RuntimeError("의도적 예외")

        monkeypatch.setattr(step_shadow, "detect_step_breaks", _boom)
        try:
            with caplog.at_level(logging.INFO, logger="whymath.l4.step_shadow"):
                observe_step_breaks(_NONPRESERVING)  # 예외 없이 반환해야
            assert _shadow_messages(caplog) == []
        finally:
            get_settings.cache_clear()

    def test_returns_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # 반환 None — 호출자가 신호 받을 변수 없음(student-facing 누출 구조적 차단).
        monkeypatch.setenv("WHYMATH_L4_STEP_SHADOW_ENABLED", "true")
        get_settings.cache_clear()
        try:
            assert observe_step_breaks(_NONPRESERVING) is None
        finally:
            get_settings.cache_clear()

    def test_logs_diverged_candidate_a(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        # slice 65: _NONPRESERVING은 before {3}·after {4} → expected "3"이면 정답서 이탈 = (A) 후보.
        monkeypatch.setenv("WHYMATH_L4_STEP_SHADOW_ENABLED", "true")
        get_settings.cache_clear()
        try:
            with caplog.at_level(logging.INFO, logger="whymath.l4.step_shadow"):
                observe_step_breaks(_NONPRESERVING, expected_answer="3")
            msgs = _shadow_messages(caplog)
            assert any("verdict=diverged_from_answer" in m for m in msgs)
            assert any("candidate=A" in m for m in msgs)
        finally:
            get_settings.cache_clear()

    def test_logs_reached_candidate_not_a(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        # after {4}가 기대정답이면 정답 도달 → candidate not_A(양성 아님).
        monkeypatch.setenv("WHYMATH_L4_STEP_SHADOW_ENABLED", "true")
        get_settings.cache_clear()
        try:
            with caplog.at_level(logging.INFO, logger="whymath.l4.step_shadow"):
                observe_step_breaks(_NONPRESERVING, expected_answer="4")
            msgs = _shadow_messages(caplog)
            assert any("verdict=reached_answer" in m for m in msgs)
            assert any("candidate=not_A" in m for m in msgs)
        finally:
            get_settings.cache_clear()

    def test_logs_indeterminate_without_expected(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        # expected_answer 없음(slice 63 호출 형태) → verdict=indeterminate·candidate=unknown.
        monkeypatch.setenv("WHYMATH_L4_STEP_SHADOW_ENABLED", "true")
        get_settings.cache_clear()
        try:
            with caplog.at_level(logging.INFO, logger="whymath.l4.step_shadow"):
                observe_step_breaks(_NONPRESERVING)
            msgs = _shadow_messages(caplog)
            assert any("verdict=indeterminate" in m for m in msgs)
            assert any("candidate=unknown" in m for m in msgs)
        finally:
            get_settings.cache_clear()
