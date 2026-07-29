"""db.session 전역 누수 가드의 변별력 실측 (OPS-07 acceptance ②).

가드가 *실패 상태에서 실제로 실패 신호를 내는지*를 오염 주입으로 측정한다 — "가드가 있다"는
사실만 확인하고 그것이 실패를 실패로 만드는지는 안 재는 위장 검증을 배제한다(CLAUDE.md
"변별력 없는 검증 스텝 금지"). 세 층위로 본다:

  ① **탐지·격리 로직 직접**(`_db_leak_guard`) — 깨끗하면 None(음성 대조), 전역 주입 시 사유
     문자열(양성), contain 후 전역이 None으로 복원(격리).
  ② **실 세션에서 가드가 활성**인지 — 이 테스트 자신에게 autouse 가드가 붙어 있다.
  ③ **오염 테스트 주입 end-to-end** — 하위 pytest에 누수 테스트를 주입하면 스위트가 *실제로*
     비0으로 끝나고(귀책), 같은 스위트의 깨끗한 테스트는 통과한다(오검출 없음).
"""

from __future__ import annotations

import subprocess
import sys
import textwrap
from pathlib import Path

import _db_leak_guard as guard
import pytest
from whymath_backend.db import session as db_session

_TESTS_BACKEND = Path(__file__).resolve().parent
_SRC_BACKEND = Path(__file__).resolve().parents[2] / "src" / "backend"


class _FakeEngine:
    """dispose 가능한 가짜 엔진 — contain_db_session_leak()이 실 엔진처럼 dispose하는지 확인."""

    def __init__(self) -> None:
        self.disposed = False

    async def dispose(self) -> None:
        self.disposed = True


@pytest.fixture
def _restore_db_globals() -> object:
    """주입 실험이 새지 않도록 각 테스트 후 db.session 전역을 None으로 되돌린다.

    이 fixture는 conftest의 autouse 가드보다 *나중에* 셋업되므로(명시 요청 fixture) *먼저*
    teardown된다 → 가드가 검사하기 전에 전역이 이미 깨끗해, 주입 테스트가 가드에 걸리지 않는다.
    """
    yield None
    db_session._engine = None
    db_session._sessionmaker = None


# ── ① 탐지·격리 로직 직접 ────────────────────────────────────────────────
def test_reason_is_none_when_clean(_restore_db_globals: object) -> None:
    """음성 대조 — 전역이 깨끗하면 사유 None(가드가 정상 테스트를 실패시키지 않는 근거)."""
    db_session._engine = None
    db_session._sessionmaker = None
    assert guard.db_session_leak_reason() is None


def test_reason_detects_leaked_engine(_restore_db_globals: object) -> None:
    """양성 — _engine 주입 시 사유에 심볼명이 담긴다."""
    db_session._engine = _FakeEngine()
    reason = guard.db_session_leak_reason()
    assert reason is not None
    assert "db.session._engine" in reason


def test_reason_detects_leaked_sessionmaker(_restore_db_globals: object) -> None:
    """양성 — _sessionmaker 주입도 별도로 탐지된다(두 캐시 심볼 모두 감시)."""
    db_session._sessionmaker = object()
    reason = guard.db_session_leak_reason()
    assert reason is not None
    assert "db.session._sessionmaker" in reason


def test_contain_resets_globals_and_disposes(_restore_db_globals: object) -> None:
    """격리 — contain 후 두 전역 모두 None + 엔진 dispose가 실제로 호출된다."""
    fake = _FakeEngine()
    db_session._engine = fake
    db_session._sessionmaker = object()

    guard.contain_db_session_leak()

    assert db_session._engine is None
    assert db_session._sessionmaker is None
    assert fake.disposed is True


def test_failure_message_names_target_and_fix() -> None:
    """실패 메시지가 귀책 대상(nodeid)·마커·정리 방법을 담는다(원인 없는 빨간 X 방지)."""
    msg = guard.format_leak_failure("tests/backend/x.py::test_foo", "db.session._engine")
    assert guard.LEAK_MARKER in msg
    assert "test_foo" in msg
    assert "dispose_engine" in msg


# ── ② 실 세션에서 가드가 활성인지 ─────────────────────────────────────────
def test_guard_fixture_is_active_in_this_session(request: pytest.FixtureRequest) -> None:
    """이 테스트에 conftest의 autouse 가드가 실제로 붙어 있다(조용히 비활성화되면 깨진다)."""
    assert "_guard_db_session_global_leak" in request.fixturenames


def test_real_conftest_wires_guard_via_helper() -> None:
    """실 conftest가 이 헬퍼로 가드를 배선한다 — ③ 대역의 배선이 실물과 동일함을 봉인."""
    conftest_src = (_TESTS_BACKEND / "conftest.py").read_text(encoding="utf-8")
    assert "from _db_leak_guard import" in conftest_src
    assert "autouse=True" in conftest_src
    assert "_guard_db_session_global_leak" in conftest_src


# ── ③ 오염 테스트 주입 end-to-end (하위 pytest) ───────────────────────────
_TMP_CONFTEST = textwrap.dedent(f"""
    import sys
    sys.path.insert(0, {str(_SRC_BACKEND)!r})
    sys.path.insert(0, {str(_TESTS_BACKEND)!r})

    from collections.abc import Iterator

    import pytest

    from _db_leak_guard import (
        contain_db_session_leak,
        db_session_leak_reason,
        format_leak_failure,
    )

    @pytest.fixture(autouse=True)
    def _guard(request):
        yield
        if request.node.get_closest_marker("integration") is not None:
            return
        reason = db_session_leak_reason()
        if reason is None:
            return
        contain_db_session_leak()
        pytest.fail(format_leak_failure(request.node.nodeid, reason), pytrace=False)
    """)

_POLLUTER_TEST = textwrap.dedent("""
    from whymath_backend.db import session as db_session

    class _FakeEngine:
        async def dispose(self):
            pass

    def test_leaks_engine_and_does_not_clean_up():
        # 오염 주입: 전역 엔진 캐시를 채우고 정리하지 않는다(실 누수 테스트의 최종 상태 재현).
        db_session._engine = _FakeEngine()
        assert True  # 테스트 본문 자체는 통과 — 실패는 오직 가드의 teardown에서 나와야 한다.
    """)

# integration 마크 오염 테스트 — 가드가 hermetic 전용이므로 이건 *제외*돼 통과해야 한다.
_INTEGRATION_POLLUTER_TEST = textwrap.dedent("""
    import pytest

    from whymath_backend.db import session as db_session

    class _FakeEngine:
        async def dispose(self):
            pass

    @pytest.mark.integration
    def test_integration_leak_is_not_flagged():
        # 통합 테스트가 엔진 전역을 남겨도 가드는 건드리지 않는다(범위=hermetic).
        db_session._engine = _FakeEngine()
        assert True
    """)

_CLEAN_TEST = textwrap.dedent("""
    def test_clean_touches_nothing():
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
        guard.LEAK_MARKER in out
    ), f"가드 누수 마커가 출력에 없다 — 다른 이유로 실패했을 수 있다\n{out}"
    assert (
        "test_leaks_engine_and_does_not_clean_up" in out
    ), f"누수 테스트가 귀책 대상으로 지목되지 않았다\n{out}"


def test_guard_passes_clean_test_end_to_end(tmp_path: Path) -> None:
    """음성 대조 — 같은 가드 아래 깨끗한 테스트는 통과한다(항상 실패하는 장식이 아님)."""
    result = _run_subpytest(tmp_path, "test_clean.py", _CLEAN_TEST)
    out = result.stdout + result.stderr

    assert result.returncode == 0, f"깨끗한 테스트가 가드에 걸렸다 — 오검출(false positive)\n{out}"
    assert guard.LEAK_MARKER not in out, f"깨끗한 실행에 누수 마커가 떴다 — 오검출\n{out}"
    assert "1 passed" in out, f"깨끗한 테스트가 통과로 집계되지 않았다\n{out}"


def test_guard_skips_integration_marked_leak_end_to_end(tmp_path: Path) -> None:
    """범위 대조 — integration 마크 테스트는 엔진을 남겨도 가드가 제외한다(hermetic 전용).

    통합 테스트는 별도 잡(-m integration·실 PG)에서 각자의 엔진 수명주기로 돌므로, 함수 단위
    '엔진=None' 불변식을 적용하지 않는다(로컬 검증 불가 구간을 가드가 침범하지 않음을 봉인).
    """
    result = _run_subpytest(tmp_path, "test_integration_leak.py", _INTEGRATION_POLLUTER_TEST)
    out = result.stdout + result.stderr

    assert result.returncode == 0, f"integration 마크 누수를 가드가 잡았다 — 범위 초과\n{out}"
    assert guard.LEAK_MARKER not in out, f"integration 실행에 누수 마커가 떴다 — 범위 초과\n{out}"


def test_real_conftest_scopes_guard_to_hermetic() -> None:
    """실 conftest 가드가 integration 마크를 제외하도록 배선됐는지 봉인(범위=hermetic)."""
    conftest_src = (_TESTS_BACKEND / "conftest.py").read_text(encoding="utf-8")
    assert 'get_closest_marker("integration")' in conftest_src
