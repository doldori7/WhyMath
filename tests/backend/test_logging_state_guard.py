"""로거 상태 오염 가드의 변별력 실측 (OPS-15 acceptance ②).

가드가 *실패 상태에서 실제로 실패 신호를 내는지*를 오염 주입으로 측정한다 — "가드가 있다"는
사실만 확인하고 그것이 실패를 실패로 만드는지는 안 재는 위장 검증을 배제한다(CLAUDE.md
"변별력 없는 검증 스텝 금지"). `test_db_leak_guard.py`(OPS-07)와 동일한 세 층위:

  ① **탐지·격리 로직 직접**(`_logging_state_guard`) — 깨끗하면 None(음성 대조), propagate·
     disabled·전역 disable 오염 주입 시 사유 문자열(양성), contain 후 원상 복원(격리),
     테스트 중 생성된 *외부* 로거는 판정 제외·*whymath**는 신생도 판정(오검출/미검출 경계).
  ② **실 세션에서 가드가 활성**인지 — 이 테스트 자신에게 autouse 가드가 붙어 있다.
  ③ **오염 테스트 주입 end-to-end** — 하위 pytest에 propagate를 남기는 테스트를 주입하면
     스위트가 *실제로* 비0으로 끝나고(귀책), 깨끗한 테스트는 통과한다(오검출 없음).

배경 사고(OPS-15): dictConfig 테스트가 record 로거에 propagate=False를 남겨, pytest 8.x
caplog(root 전용 캡처·전파 의존)을 쓰는 WH-1 테스트 13건이 무작위 순서에서만 '관측 0건'
으로 깨졌다(시드 442243680 실측). pytest 9+는 같은 오염을 위장한다 — 가드가 러너 버전과
실행 순서에 무관하게 오염 테스트 자체를 결정론적 실패로 바꾼다.
"""

from __future__ import annotations

import logging
import subprocess
import sys
import textwrap
import uuid
from collections.abc import Iterator
from pathlib import Path

import _logging_state_guard as guard
import pytest

_TESTS_BACKEND = Path(__file__).resolve().parent
_SRC_BACKEND = Path(__file__).resolve().parents[2] / "src" / "backend"

# import(수집) 시점에 만들어 두는 프로브 로거 — 각 테스트의 가드 스냅샷에 '기존 로거'로
# 잡히므로, 이 로거를 흘려 양성 대조를 구성할 수 있다.
_PROBE = logging.getLogger("whymath.tests.logging_guard.probe")


@pytest.fixture
def _restore_probe_state() -> Iterator[None]:
    """주입 실험이 새지 않도록 각 테스트 후 프로브 로거·전역 disable을 원복한다.

    명시 요청 fixture는 conftest의 autouse 가드보다 *나중에* 셋업되므로 *먼저* teardown된다
    → 가드가 검사하기 전에 상태가 이미 깨끗해, 주입 테스트가 가드에 걸리지 않는다
    (test_db_leak_guard._restore_db_globals 선례).
    """
    original = (_PROBE.propagate, _PROBE.disabled, logging.Logger.manager.disable)
    yield
    _PROBE.propagate = original[0]
    _PROBE.disabled = original[1]
    logging.Logger.manager.disable = original[2]


# ── ① 탐지·격리 로직 직접 ────────────────────────────────────────────────
def test_reason_is_none_when_clean() -> None:
    """음성 대조 — 아무것도 안 바꾸면 사유 None(가드가 정상 테스트를 실패시키지 않는 근거)."""
    snapshot = guard.snapshot_logging_state()
    assert guard.logging_state_leak_reason(snapshot) is None


def test_reason_detects_propagate_flip(_restore_probe_state: object) -> None:
    """양성 — 기존 로거의 propagate 플립(OPS-15 사고의 실제 오염 상태)을 탐지한다."""
    snapshot = guard.snapshot_logging_state()
    _PROBE.propagate = False
    reason = guard.logging_state_leak_reason(snapshot)
    assert reason is not None
    assert _PROBE.name in reason
    assert "propagate" in reason


def test_reason_detects_disabled_flip(_restore_probe_state: object) -> None:
    """양성 — disabled=True 잔존(dictConfig disable_existing_loggers 유형)도 별도 탐지."""
    snapshot = guard.snapshot_logging_state()
    _PROBE.disabled = True
    reason = guard.logging_state_leak_reason(snapshot)
    assert reason is not None
    assert _PROBE.name in reason
    assert "disabled" in reason


def test_reason_detects_global_disable(_restore_probe_state: object) -> None:
    """양성 — 전역 logging.disable() 잔존(모든 caplog을 죽이는 상태)을 탐지한다."""
    snapshot = guard.snapshot_logging_state()
    logging.disable(logging.CRITICAL)
    reason = guard.logging_state_leak_reason(snapshot)
    assert reason is not None
    assert "logging.disable" in reason


def test_reason_detects_real_root_disabled_flip() -> None:
    """양성 — *진짜* root 로거의 disabled 플립을 탐지한다(전 로깅을 죽이는 상태).

    함정 봉인: `getLogger("root")`는 root가 아니라 'root'라는 이름의 새 로거를 만든다 —
    스냅샷이 root를 빈 키("")로 다뤄야 비교·복원이 진짜 root를 향한다(아래 설계 동결 테스트
    와 쌍). 이 테스트는 실제 root를 흘렸을 때 가드가 잡는지를 직접 실측한다.
    """
    snapshot = guard.snapshot_logging_state()
    root = logging.getLogger()
    original = root.disabled
    root.disabled = True
    try:
        reason = guard.logging_state_leak_reason(snapshot)
        assert reason is not None
        assert "'root'" in reason
        assert "disabled" in reason

        guard.contain_logging_state_leak(snapshot)
        assert root.disabled is original  # 격리 — 진짜 root가 복원된다
    finally:
        root.disabled = original  # 방어적 원복 — 단언 실패 시에도 세션 오염 0


def test_snapshot_keys_root_by_empty_string() -> None:
    """설계 동결 — 스냅샷은 root를 빈 키("")로 담는다('root' 이름 키 금지).

    'root' 문자열 키를 쓰면 reason/contain의 `getLogger(name)`이 root가 아닌 동명의 새
    로거를 만들어(표준 라이브러리 함정) 진짜 root 오염을 놓치고 잡음 로거를 남긴다.
    """
    snapshot = guard.snapshot_logging_state()
    assert "" in snapshot.loggers
    root = logging.getLogger()
    assert snapshot.loggers[""] == (root.propagate, root.disabled)


def test_new_external_logger_created_during_test_not_flagged() -> None:
    """경계 — 테스트 중 생성된 *외부* 로거의 초기 비전파는 판정하지 않는다(오검출 방지).

    라이브러리가 import 시점에 propagate=False 로거를 만드는 것은 정상 설계다 — 스냅샷에
    없던 외부 로거는 비교 대상이 아니어야 가드가 무고한 첫-import 테스트를 잡지 않는다.
    """
    snapshot = guard.snapshot_logging_state()
    fresh = logging.getLogger(f"thirdparty.libx.{uuid.uuid4().hex}")
    fresh.propagate = False
    try:
        assert guard.logging_state_leak_reason(snapshot) is None
    finally:
        fresh.propagate = True  # 위생 — 다음 테스트 스냅샷의 초기 상태를 깨끗하게


def test_new_whymath_logger_left_nonpropagating_is_flagged() -> None:
    """양성 — 테스트 중 생성된 whymath* 로거의 비전파 잔존은 잡는다(격리 실행 갭 봉쇄).

    실측 근거: 단독 파일 실행에서는 record 로거가 dictConfig로 *테스트 중 생성*돼 스냅샷에
    없다 — 기존-로거 비교만으로는 원본 사고 코드를 단독 실행에서 놓쳤다(가드 개발 중 프로브
    실측). 우리 네임스페이스는 비전파 로거를 정당하게 만들지 않으므로(소스 grep 0건) 신생
    이라도 판정하고, contain은 기본값(propagate=True)으로 되돌린다.
    """
    snapshot = guard.snapshot_logging_state()
    fresh = logging.getLogger(f"whymath.tests.logging_guard.owned.{uuid.uuid4().hex}")
    fresh.propagate = False
    try:
        reason = guard.logging_state_leak_reason(snapshot)
        assert reason is not None
        assert fresh.name in reason

        guard.contain_logging_state_leak(snapshot)
        assert fresh.propagate is True  # 격리 — 신생 오염도 기본값으로 복원
        assert guard.logging_state_leak_reason(snapshot) is None
    finally:
        fresh.propagate = True  # 방어적 원복 — 단언 실패 시에도 세션 오염 0


def test_contain_restores_all(_restore_probe_state: object) -> None:
    """격리 — contain 후 propagate·disabled·전역 disable 모두 스냅샷 값으로 복원된다."""
    snapshot = guard.snapshot_logging_state()
    _PROBE.propagate = False
    _PROBE.disabled = True
    logging.disable(logging.CRITICAL)

    guard.contain_logging_state_leak(snapshot)

    assert _PROBE.propagate is True
    assert _PROBE.disabled is False
    assert logging.Logger.manager.disable == snapshot.global_disable
    assert guard.logging_state_leak_reason(snapshot) is None  # 복원 후 재검사도 깨끗


def test_failure_message_names_target_and_fix() -> None:
    """실패 메시지가 귀책 대상(nodeid)·마커·정리 방법을 담는다(원인 없는 빨간 X 방지)."""
    msg = guard.format_logging_leak_failure(
        "tests/backend/x.py::test_foo", "로거 'a.b' propagate True→False"
    )
    assert guard.LOGGING_LEAK_MARKER in msg
    assert "test_foo" in msg
    assert "propagate" in msg
    assert "_dictconfig_loaded" in msg  # 복원 선례 안내


# ── ② 실 세션에서 가드가 활성인지 ─────────────────────────────────────────
def test_guard_fixture_is_active_in_this_session(request: pytest.FixtureRequest) -> None:
    """이 테스트에 conftest의 autouse 가드가 실제로 붙어 있다(조용히 비활성화되면 깨진다)."""
    assert "_guard_logging_state_pollution" in request.fixturenames


def test_real_conftest_wires_guard_via_helper() -> None:
    """실 conftest가 이 헬퍼로 가드를 배선한다 — ③ 대역의 배선이 실물과 동일함을 봉인."""
    conftest_src = (_TESTS_BACKEND / "conftest.py").read_text(encoding="utf-8")
    assert "from _logging_state_guard import" in conftest_src
    assert "_guard_logging_state_pollution" in conftest_src
    assert 'get_closest_marker("integration")' in conftest_src  # 범위=hermetic(OPS-07 동형)


# ── ③ 오염 테스트 주입 end-to-end (하위 pytest) ───────────────────────────
_TMP_CONFTEST = textwrap.dedent(f"""
    import sys
    sys.path.insert(0, {str(_SRC_BACKEND)!r})
    sys.path.insert(0, {str(_TESTS_BACKEND)!r})

    import pytest

    from _logging_state_guard import (
        contain_logging_state_leak,
        format_logging_leak_failure,
        logging_state_leak_reason,
        snapshot_logging_state,
    )

    @pytest.fixture(autouse=True)
    def _guard(request):
        snapshot = snapshot_logging_state()
        yield
        if request.node.get_closest_marker("integration") is not None:
            return
        reason = logging_state_leak_reason(snapshot)
        if reason is None:
            return
        contain_logging_state_leak(snapshot)
        pytest.fail(format_logging_leak_failure(request.node.nodeid, reason), pytrace=False)
    """)

_POLLUTER_TEST = textwrap.dedent("""
    import logging

    # import(수집) 시점에 만들어 두면 각 테스트의 가드 스냅샷에 '기존 로거'로 잡힌다.
    _PRESENT_AT_SNAPSHOT = logging.getLogger("whymath.tests.guard_e2e.polluter")

    def test_flips_propagate_and_does_not_restore():
        # 오염 주입: 실제 사고(OPS-15 dictConfig propagate=False 잔존)의 최종 상태 재현.
        _PRESENT_AT_SNAPSHOT.propagate = False
        assert True  # 본문은 통과 — 실패는 오직 가드의 teardown에서 나와야 한다.
    """)

# integration 마크 오염 테스트 — 가드가 hermetic 전용이므로 이건 *제외*돼 통과해야 한다.
_INTEGRATION_POLLUTER_TEST = textwrap.dedent("""
    import logging

    import pytest

    _PRESENT_AT_SNAPSHOT = logging.getLogger("whymath.tests.guard_e2e.integration")

    @pytest.mark.integration
    def test_integration_flip_is_not_flagged():
        # 통합 테스트가 로거 상태를 남겨도 가드는 건드리지 않는다(범위=hermetic).
        _PRESENT_AT_SNAPSHOT.propagate = False
        assert True
    """)

_CLEAN_TEST = textwrap.dedent("""
    import logging

    def test_clean_logs_without_leaving_state():
        # 로그를 찍기만 하는 정상 테스트 — 상태 변경 0.
        logging.getLogger("whymath.tests.guard_e2e.clean").info("clean")
        assert 1 + 1 == 2
    """)


def _run_subpytest(
    tmp_path: Path, test_filename: str, test_src: str
) -> subprocess.CompletedProcess[str]:
    """가드를 실은 conftest와 함께 단일 테스트 파일을 하위 pytest로 실행한다."""
    (tmp_path / "conftest.py").write_text(_TMP_CONFTEST, encoding="utf-8")
    (tmp_path / test_filename).write_text(test_src, encoding="utf-8")
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            str(tmp_path / test_filename),
            "-p",
            "no:cacheprovider",
            "-o",
            "asyncio_mode=auto",
            "-q",
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )


def test_guard_fails_injected_polluter_end_to_end(tmp_path: Path) -> None:
    """양성 대조 — 오염 테스트를 주입하면 하위 스위트가 *실제로* 비0으로 끝나고 마커가 찍힌다.

    "가드가 있다"가 아니라 "가드가 실패를 실패로 만든다"를 실측한다 — 가드가 위장이면 오염
    테스트도 returncode 0으로 통과할 것이다.
    """
    result = _run_subpytest(tmp_path, "test_polluter.py", _POLLUTER_TEST)
    out = result.stdout + result.stderr

    assert (
        result.returncode != 0
    ), f"오염 테스트를 주입했는데 스위트가 통과했다 — 가드가 위장이다\n{out}"
    assert (
        guard.LOGGING_LEAK_MARKER in out
    ), f"가드 오염 마커가 출력에 없다 — 다른 이유로 실패했을 수 있다\n{out}"
    assert (
        "test_flips_propagate_and_does_not_restore" in out
    ), f"오염 테스트가 귀책 대상으로 지목되지 않았다\n{out}"


def test_guard_passes_clean_test_end_to_end(tmp_path: Path) -> None:
    """음성 대조 — 같은 가드 아래 깨끗한 테스트는 통과한다(항상 실패하는 장식이 아님)."""
    result = _run_subpytest(tmp_path, "test_clean.py", _CLEAN_TEST)
    out = result.stdout + result.stderr

    assert result.returncode == 0, f"깨끗한 테스트가 가드에 걸렸다 — 오검출(false positive)\n{out}"
    assert guard.LOGGING_LEAK_MARKER not in out, f"깨끗한 실행에 오염 마커가 떴다 — 오검출\n{out}"
    assert "1 passed" in out, f"깨끗한 테스트가 통과로 집계되지 않았다\n{out}"


def test_guard_skips_integration_marked_flip_end_to_end(tmp_path: Path) -> None:
    """범위 대조 — integration 마크 테스트는 상태를 남겨도 가드가 제외한다(hermetic 전용).

    통합 테스트는 별도 잡(-m integration)에서 별도 프로세스로 돌므로 hermetic 스위트로의
    교차 오염이 없고, 라이브 서비스 로깅 구성은 로컬 검증 불가 구간이라 가드가 침범하지
    않음을 봉인한다(OPS-07 범위 대조 동형).
    """
    result = _run_subpytest(tmp_path, "test_integration_flip.py", _INTEGRATION_POLLUTER_TEST)
    out = result.stdout + result.stderr

    assert result.returncode == 0, f"integration 마크 오염을 가드가 잡았다 — 범위 초과\n{out}"
    assert (
        guard.LOGGING_LEAK_MARKER not in out
    ), f"integration 실행에 오염 마커가 떴다 — 범위 초과\n{out}"
