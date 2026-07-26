"""[OPS-07] 전역 상태 오염 가드의 *변별력* 동결 — 가드가 위장이 아님을 실측한다.

CLAUDE.md "변별력 없는 검증 스텝 금지": 성공/실패 양쪽에서 같은 값을 내는 검사는 검증이
아니라 위장이다. 그래서 이 파일은 가드를 *말로* 설명하지 않고 **깨뜨려서** 확인한다:

  1. 오염 테스트를 주입하면 가드가 **그 테스트를** 실패시키는가 (검출)
  2. 가드를 무력화(autouse=False)하면 그 오염이 **통과해버리고 엉뚱한 후속 테스트가**
     깨지는가 — 즉 검출의 원인이 가드임 + 2026-07-26 사고의 재현 (음성 대조)
  3. 정상 테스트(전역 미접촉·정상 정리)는 통과하는가 (양성 대조 — 무차별 실패 아님)
  4. 허용 목록이 *사유 없이는* 빠져나가지 못하는가 (우회 차단)
  5. 감시 축 배선이 실재하는가 — 전역 이름이 바뀌면 가드가 조용히 무력화되므로 (침묵 실패
     차단)

실측 방법: `tests/backend/conftest.py`를 임시 디렉터리에 **그대로 복사**해 실제와 같은
레이아웃(`<tmp>/tests/backend/`)의 1회용 스위트를 만들고, 거기에 오염/정상 테스트를 넣어
**서브프로세스 pytest**로 돌린다. 현재 프로세스의 수집 순서를 건드리지 않으면서 가드의
end-to-end 동작(픽스처 등록 → teardown 검사 → 실패 보고)을 그대로 관측한다.
"""

from __future__ import annotations

import asyncio
import importlib
import importlib.util
import os
import subprocess
import sys
from collections.abc import Callable
from functools import lru_cache
from pathlib import Path
from types import ModuleType

import pytest

_THIS_DIR = Path(__file__).resolve().parent
_CONFTEST_PATH = _THIS_DIR / "conftest.py"
_PROJECT_ROOT = _THIS_DIR.parents[1]
_SRC_BACKEND = _PROJECT_ROOT / "src" / "backend"

# 임시 스위트에서 가드가 계산할 안정 ID(파일 경로가 실제 레이아웃과 같으므로 결정적).
_INJECTED_POLLUTER_ID = "tests/backend/test_injected.py::test_pollutes_engine_global"

# ──────────────────────────────────────────────────────────────────────────
# 주입할 테스트 소스 — 오염은 *실제 사고와 같은 형태*로 만든다:
# 테스트가 `get_engine()`을 직접 부르는 게 아니라, 프로덕션 헬퍼
# (`build_device_store_from_settings`)가 내부에서 전역을 채운다. 사고가 어려웠던 이유가
# 바로 이 간접성이었다.
# ──────────────────────────────────────────────────────────────────────────
_POLLUTER_SOURCE = '''\
"""주입된 오염 테스트 — dispose_engine() 없이 db.session 전역을 채운다."""

from pydantic import SecretStr

from whymath_backend.api._device_store import build_device_store_from_settings
from whymath_backend.config import Settings


def test_pollutes_engine_global() -> None:
    settings = Settings(
        jwt_secret_key=SecretStr("test-secret-0123456789abcdef"),
        device_store_mode="pg",
    )
    store, _cleanup = build_device_store_from_settings(settings)
    assert store is not None
    # dispose_engine() 호출 없음 — 모듈 전역이 남는다(2026-07-26 사고 형태)
'''

_FOLLOWER_SOURCE = '''\


def test_next_test_sees_clean_globals() -> None:
    """오염 다음에 실행되는 *무고한* 테스트 — 사고 당시 실제로 깨진 쪽이다."""
    from whymath_backend.db import session as session_mod

    assert session_mod._engine is None
    assert session_mod._sessionmaker is None
'''

_CLEAN_SOURCE = '''\
"""양성 대조 — 가드가 무차별 실패를 내지 않음을 확인하는 정상 테스트들."""

import asyncio

from whymath_backend.config import Settings
from whymath_backend.db.session import dispose_engine, get_engine


def test_never_touches_globals() -> None:
    assert 1 + 1 == 2


def test_fills_globals_but_disposes_them() -> None:
    """전역을 채우되 try/finally로 정리 — 가드가 통과시켜야 한다."""
    try:
        assert get_engine(Settings()) is not None
    finally:
        asyncio.run(dispose_engine())
'''


def _run_isolated_suite(
    tmp_path: Path,
    test_source: str,
    *,
    conftest_transform: Callable[[str], str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """conftest를 복사한 1회용 스위트를 서브프로세스 pytest로 돌린다.

    `<tmp>/tests/backend/` 레이아웃을 쓰는 이유: 복사된 conftest의 `_PROJECT_ROOT`가
    `parents[2]`로 계산되므로, 이 배치라야 가드의 안정 ID가 실제와 같은
    `tests/backend/<파일>::<테스트>` 형태로 나온다.
    """
    suite = tmp_path / "tests" / "backend"
    suite.mkdir(parents=True)

    text = _CONFTEST_PATH.read_text(encoding="utf-8")
    if conftest_transform is not None:
        text = conftest_transform(text)
    (suite / "conftest.py").write_text(text, encoding="utf-8")
    (suite / "test_injected.py").write_text(test_source, encoding="utf-8")

    env = {k: v for k, v in os.environ.items() if k != "PYTEST_ADDOPTS"}
    # 서브프로세스에서도 whymath_backend를 import할 수 있게(editable 설치가 없어도 동작)
    env["PYTHONPATH"] = os.pathsep.join([str(_SRC_BACKEND), env.get("PYTHONPATH", "")]).rstrip(
        os.pathsep
    )
    return subprocess.run(
        [sys.executable, "-m", "pytest", str(suite), "-q", "-p", "no:cacheprovider"],
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
        env=env,
        timeout=300,
    )


def _disable_guard(text: str) -> str:
    """가드 픽스처를 무력화한다(autouse 해제). 앵커가 사라지면 *큰 소리로* 실패시킨다."""
    anchor = "@pytest.fixture(autouse=True)"
    if text.count(anchor) != 1:
        raise AssertionError(
            f"conftest.py에서 가드 픽스처 앵커 `{anchor}`를 정확히 1개 찾지 못했다 "
            f"(발견 {text.count(anchor)}개) — 무력화 대조가 조용히 무효가 되는 것을 막기 "
            "위해 실패시킨다. 픽스처를 옮겼다면 이 앵커도 함께 고쳐라."
        )
    return text.replace(anchor, "@pytest.fixture(autouse=False)")


def _allowlist_with(reason: str) -> Callable[[str], str]:
    """주입된 오염 테스트를 허용 목록에 `reason` 사유로 등재하는 변환기."""

    def _transform(text: str) -> str:
        anchor = "_ALLOWED_GLOBAL_LEAKS: dict[str, str] = {"
        if text.count(anchor) != 1:
            raise AssertionError(
                f"conftest.py에서 허용 목록 앵커 `{anchor}`를 정확히 1개 찾지 못했다 "
                f"(발견 {text.count(anchor)}개)."
            )
        return text.replace(
            anchor,
            f'{anchor}\n    "{_INJECTED_POLLUTER_ID}": "{reason}",',
        )

    return _transform


# ══════════════════════════════════════════════════════════════════════════
# 1) 검출 — 오염 테스트를 주입하면 *그 테스트가* 실패한다
# ══════════════════════════════════════════════════════════════════════════
def test_guard_fails_the_polluting_test_and_spares_the_next(tmp_path: Path) -> None:
    """오염원을 정확히 지목하고, 후속 테스트로 번지지 않게 정리까지 한다."""
    result = _run_isolated_suite(tmp_path, _POLLUTER_SOURCE + _FOLLOWER_SOURCE)
    output = result.stdout + result.stderr

    assert result.returncode != 0, f"가드가 오염을 잡지 못했다(exit 0):\n{output}"
    # 원인 지점을 정확히 지목 — 실패 보고에 *오염을 만든* 테스트 이름이 찍힌다
    assert "ERROR at teardown of test_pollutes_engine_global" in output, output
    assert _INJECTED_POLLUTER_ID in output, output
    assert "_engine" in output and "_sessionmaker" in output, output
    # 수정 방법이 메시지에 있다 — 미래 세션이 메시지만 보고 고칠 수 있어야 한다
    assert "dispose_engine" in output, output
    # 연쇄 차단: 무고한 후속 테스트는 통과했다(가드가 전역을 정리했으므로 "2 passed, 1 error")
    assert "2 passed" in output, f"후속 테스트가 함께 깨졌다(연쇄 차단 실패):\n{output}"


# ══════════════════════════════════════════════════════════════════════════
# 2) 음성 대조 — 가드를 끄면 오염은 통과하고 *엉뚱한* 테스트가 깨진다 (사고 재현)
# ══════════════════════════════════════════════════════════════════════════
def test_without_the_guard_the_pollution_passes_and_breaks_an_innocent_test(
    tmp_path: Path,
) -> None:
    """가드가 *검출의 원인*임을 증명한다 — 같은 코드, 가드만 끈 상태.

    이 실행이 실패하면(=가드 없이도 오염원이 잡히면) 가드는 검출에 기여하지 않는
    장식이라는 뜻이다. 동시에 이것이 2026-07-26 사고의 형태 그 자체다: 오염을 만든
    테스트는 초록, 무고한 후속 테스트가 빨강.
    """
    result = _run_isolated_suite(
        tmp_path, _POLLUTER_SOURCE + _FOLLOWER_SOURCE, conftest_transform=_disable_guard
    )
    output = result.stdout + result.stderr

    assert result.returncode != 0, f"오염이 아무 증상도 내지 않았다(주입 실패):\n{output}"
    # 오염원은 멀쩡히 통과 — 가드 없이는 아무도 그를 탓하지 않는다
    assert "ERROR at teardown of test_pollutes_engine_global" not in output, output
    # 대신 무고한 후속 테스트가 깨진다(실행 순서 의존 사고)
    assert "test_next_test_sees_clean_globals" in output, output
    assert "1 failed" in output and "1 passed" in output, output


# ══════════════════════════════════════════════════════════════════════════
# 3) 양성 대조 — 정상 테스트는 통과한다(가드가 무차별 실패를 내지 않는다)
# ══════════════════════════════════════════════════════════════════════════
def test_guard_is_silent_for_clean_tests(tmp_path: Path) -> None:
    """전역 미접촉 + try/finally로 정리하는 테스트는 그대로 통과해야 한다."""
    result = _run_isolated_suite(tmp_path, _CLEAN_SOURCE)
    output = result.stdout + result.stderr

    assert result.returncode == 0, f"가드가 정상 테스트를 실패시켰다:\n{output}"
    assert "2 passed" in output, output


# ══════════════════════════════════════════════════════════════════════════
# 4) 허용 목록 — 사유가 있어야만 빠져나간다
# ══════════════════════════════════════════════════════════════════════════
def test_allowlist_without_reason_is_rejected(tmp_path: Path) -> None:
    """빈 사유 등재는 허용이 아니다 — 우회 차단(`_INTENTIONAL_EXCLUSIONS` 선례)."""
    result = _run_isolated_suite(tmp_path, _POLLUTER_SOURCE, conftest_transform=_allowlist_with(""))
    output = result.stdout + result.stderr

    assert result.returncode != 0, f"빈 사유로 가드를 빠져나갔다:\n{output}"
    assert "허용 목록 무효" in output, output


def test_allowlist_with_reason_permits_the_leak(tmp_path: Path) -> None:
    """사유를 적으면 통과한다 — 허용 경로가 실제로 동작함(4번 검사의 변별력 근거)."""
    result = _run_isolated_suite(
        tmp_path,
        _POLLUTER_SOURCE,
        conftest_transform=_allowlist_with("의도된 잔존 — 변별력 실측용"),
    )
    output = result.stdout + result.stderr

    assert result.returncode == 0, f"사유 있는 허용 등재가 통과하지 못했다:\n{output}"
    assert "1 passed" in output, output


# ══════════════════════════════════════════════════════════════════════════
# 5) 배선 실재성 — 감시 축이 실제 모듈·전역·정리함수를 가리키는가
# ══════════════════════════════════════════════════════════════════════════
@lru_cache(maxsize=1)
def _load_conftest() -> ModuleType:
    """conftest.py를 별도 모듈로 로드(가드의 데이터·헬퍼를 직접 읽기 위해).

    `exec_module` 동안 `sys.modules`에 등록해야 한다 — `from __future__ import annotations`
    아래의 `@dataclass`가 문자열 애노테이션을 풀 때 자기 모듈을 sys.modules에서 찾기
    때문이다. exec가 끝나면 바로 걷어내 전역을 남기지 않는다(이 파일이 강제하는 규칙과
    같은 규율).
    """
    name = "_ops07_conftest"
    spec = importlib.util.spec_from_file_location(name, _CONFTEST_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop(name, None)
    return module


def test_watched_globals_wiring_is_real() -> None:
    """감시 대상 모듈·전역 이름·정리 함수가 실재한다.

    전역 이름이 바뀌었는데 감시 목록이 그대로면 `getattr(module, name, None)`이 늘 None을
    돌려줘 가드가 *조용히* 무력화된다 — 침묵 실패 금지. 여기서 이름을 못 박는다.
    """
    conftest = _load_conftest()
    watches = conftest._WATCHED_GLOBALS
    assert watches, "감시 축이 하나도 없다 — 가드가 아무것도 검사하지 않는다"

    for watch in watches:
        module = importlib.import_module(watch.module)
        for name in watch.attrs:
            assert hasattr(module, name), (
                f"{watch.module}에 전역 `{name}`이 없다 — 이름이 바뀌었다면 "
                "conftest의 `_WATCHED_GLOBALS`도 함께 고쳐라(안 고치면 가드가 조용히 꺼진다)."
            )
        cleanup = getattr(module, watch.cleanup, None)
        assert asyncio.iscoroutinefunction(cleanup), (
            f"{watch.module}.{watch.cleanup}가 async 함수가 아니다 — 가드는 "
            "`asyncio.run(cleanup())`으로 호출한다."
        )


def test_db_session_axis_is_watched() -> None:
    """사고가 난 축을 이름으로 못 박는다(리팩터로 목록이 느슨해져도 이 줄은 남는다)."""
    conftest = _load_conftest()
    axes = {watch.module: watch for watch in conftest._WATCHED_GLOBALS}
    assert (
        "whymath_backend.db.session" in axes
    ), "2026-07-26 main red의 직접 원인 축이 감시 목록에서 빠졌다."
    assert set(axes["whymath_backend.db.session"].attrs) >= {"_engine", "_sessionmaker"}


def test_allowlist_entries_all_have_reasons() -> None:
    """저장소의 실제 허용 목록에 빈 사유 등재가 없다."""
    conftest = _load_conftest()
    blank = [key for key, reason in conftest._ALLOWED_GLOBAL_LEAKS.items() if not reason.strip()]
    assert not blank, f"사유 없이 등재된 허용 항목: {blank}"


def test_stable_node_id_is_repo_relative(request: pytest.FixtureRequest) -> None:
    """안정 ID 형식 동결 — 허용 목록 키가 호출 방식(전체 스위트/단일 파일)에 흔들리지 않는다."""
    conftest = _load_conftest()
    assert (
        conftest._stable_node_id(request.node)
        == "tests/backend/test_global_state_guard.py::test_stable_node_id_is_repo_relative"
    )
