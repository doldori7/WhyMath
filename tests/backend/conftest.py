"""tests/backend/conftest.py — 백엔드 테스트 임포트 경로 + 통합 테스트 게이트.

`whymath_backend`는 `pip install -e ".[dev]"`로 editable 설치되므로 보통은
import 경로 조정이 불필요하다. 다만 editable 설치 없이(예: 로컬에서 venv 미설치)
테스트를 돌릴 때도 동작하도록 소스 경로를 sys.path 앞에 둔다.

data-pipeline(tests/data_pipeline/conftest.py)과 달리 *동명 충돌이 없다*:
테스트 디렉토리는 `tests/backend`, 패키지는 `whymath_backend`로 이름이 다르다.
따라서 모듈 purge 로직은 불필요하고, 경로 보장만 한다.

통합 테스트 게이트 (M1.2-live S1 신규):
`@pytest.mark.integration`은 *라이브 서비스*(실제 Ollama 데몬 등)를 요구하므로
CI(라이브 서비스 없음)에서는 기본 *skip*한다. 실행하려면 환경변수
`WHYMATH_RUN_INTEGRATION`을 truthy(1/true/yes/on)로 설정한다 — Phaiakes9에서
Kiki가 켜고 돌린다. 프로젝트에 통합 게이트 선례가 없어 이 패턴을 여기서 확립한다.

전역 상태 오염 가드 (OPS-07 신규):
모듈 전역 캐시(`db.session._engine` 등)를 채우고 정리하지 않는 테스트를 *그 테스트
자신의 teardown에서* 잡는다. 상세는 아래 "전역 상태 오염 가드" 블록 참조.
"""

from __future__ import annotations

import asyncio
import os
import sys
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType

import pytest

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_SRC_BACKEND = _PROJECT_ROOT / "src" / "backend"

# editable 설치가 없을 때를 대비한 안전장치: 소스 경로를 가장 앞으로
_src_path_str = str(_SRC_BACKEND)
if _src_path_str in sys.path:
    sys.path.remove(_src_path_str)
sys.path.insert(0, _src_path_str)

_RUN_INTEGRATION_ENV = "WHYMATH_RUN_INTEGRATION"
_TRUTHY = frozenset({"1", "true", "yes", "on"})


def _integration_enabled() -> bool:
    """환경변수로 통합 테스트가 켜져 있는지 판정."""
    return os.environ.get(_RUN_INTEGRATION_ENV, "").strip().lower() in _TRUTHY


def pytest_collection_modifyitems(config: pytest.Config, items: Iterable[pytest.Item]) -> None:
    """`integration` 마크 테스트를 기본 skip (환경변수로만 활성화).

    CI는 `WHYMATH_RUN_INTEGRATION`을 설정하지 않으므로 통합 테스트가 자동으로
    빠진다 → 라이브 Ollama 없이도 CI green. 환경변수가 켜지면 그대로 수집·실행.
    """
    if _integration_enabled():
        return
    skip_integration = pytest.mark.skip(
        reason=f"통합 테스트는 기본 skip — 실행하려면 {_RUN_INTEGRATION_ENV}=1 설정"
    )
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip_integration)


# ══════════════════════════════════════════════════════════════════════════
# 전역 상태 오염 가드 (OPS-07 — 2026-07-26 main CI red 재발방지)
# ══════════════════════════════════════════════════════════════════════════
# 사고: `api/test_redis_degradation.py`의 한 테스트가 `device_store_mode="pg_cached"`로
# store를 만들며 내부에서 `get_engine()`을 타 `db.session._engine`(모듈 전역·지연 캐시)을
# 채우고 정리하지 않았다. 같은 프로세스의 후속 테스트
# `db/test_problem_orm.py::test_session_module_imports_without_connection`이 그 전역이
# None임을 단언하므로 *실행 순서 때문에* 깨졌다 → main CI red(1 failed, 7513 passed).
#
# 이 오염은 **파일·디렉터리 단위 실행에서는 재현되지 않는다**(오염원과 피해자가 다른 파일에
# 있어 함께 수집돼야만 터진다). 그래서 로컬 검증을 통과하고 머지됐다. 근본 원인은 개별
# 부주의가 아니라 "전역 캐시를 채우는 테스트"를 잡는 장치의 부재다 — 이 가드가 그 장치다.
#
# 동작: 매 테스트 teardown에서 감시 대상 전역을 검사해 남아 있으면 ① 즉시 정리하고(후속
# 테스트로 번지는 연쇄 실패 차단) ② *그 테스트 자신을* 실패시킨다. 나중에 엉뚱한 테스트가
# 깨지면 진단에 시간이 든다(이번 사고가 그랬다) — 원인 지점을 정확히 지목하는 것이 목적.
#
# 변별력은 `tests/backend/test_global_state_guard.py`가 동결한다(오염 테스트 주입 →
# 가드가 실패시키는지 / 가드를 끄면 통과하는지를 서브프로세스 pytest로 실측).


@dataclass(frozen=True)
class _GlobalStateWatch:
    """감시 대상 모듈 전역 1축 — 감시 항목을 *데이터로* 선언한다(축 추가 = 항목 1개 추가).

    Attributes:
        module: 감시할 모듈의 완전한 이름. **import되지 않았으면 검사 자체를 건너뛴다**
            (import되지 않은 모듈은 전역이 채워질 수 없다 — 검사 비용 0, 부작용 0).
        attrs: "None이 아니면 오염"으로 보는 모듈 전역 이름들.
        cleanup: 같은 모듈의 *비동기 no-arg* 정리 함수 이름. 새 정리 로직을 발명하지 않고
            프로덕션·테스트가 이미 쓰는 관행을 그대로 재사용한다
            (`db/test_session.py::_reset`이 쓰는 `dispose_engine`).
        fix: 실패 메시지에 넣을 *구체적 수정 방법*. 미래 세션이 메시지만 보고 고칠 수 있어야
            한다.
    """

    module: str
    attrs: tuple[str, ...]
    cleanup: str
    fix: str


_WATCHED_GLOBALS: tuple[_GlobalStateWatch, ...] = (
    _GlobalStateWatch(
        module="whymath_backend.db.session",
        attrs=("_engine", "_sessionmaker"),
        cleanup="dispose_engine",
        fix=(
            "`from whymath_backend.db.session import dispose_engine` 후 엔진을 물리는 "
            "코드를 try/finally로 감싸라 — async 테스트면 `finally: await dispose_engine()`, "
            "sync 테스트면 `finally: asyncio.run(dispose_engine())` "
            "(`tests/backend/db/test_session.py::_reset` 관행). "
            "`build_device_store_from_settings(device_store_mode='pg'|'pg_cached')`·"
            "`get_sessionmaker()`·`get_engine()`이 이 전역을 채운다."
        ),
    ),
)
"""감시 축 목록. **실제 사고가 난 축부터** 둔다 — 투기적 확장 금지(과공학 방지)."""


_ALLOWED_GLOBAL_LEAKS: dict[str, str] = {
    # "tests/backend/xxx/test_yyy.py::test_zzz": "왜 정리할 수 없는지 — 구체적 사유",
}
"""전역 잔존이 *의도된* 테스트의 허용 목록(안정 ID → 사유).

**최후 수단이다.** 먼저 그 테스트가 스스로 정리하도록 고쳐라 — 등재는 "정리하면 테스트
의도가 깨진다"가 성립할 때만. 사유가 비어 있으면 가드는 등재를 무효로 보고 그대로
실패시킨다(빈 사유로 빠져나가는 우회 차단 — `tests/infra/test_required_checks_doc.py`의
`_INTENTIONAL_EXCLUSIONS` 선례). 허용된 항목은 가드가 정리도 하지 않는다(잔존이 의도라면
소유자가 따로 있다는 뜻).
"""


def _stable_node_id(node: pytest.Item) -> str:
    """저장소 루트 기준 파일 경로 + 클래스·테스트 이름.

    `node.nodeid`를 그대로 쓰지 않는 이유: 이 저장소는 `--rootdir=../..`와 상대 경로 인자를
    함께 쓰기 때문에 nodeid의 *경로 부분이 호출 방식에 따라 달라진다* — 전체 스위트에서는
    `api/test_devices.py::...`, 단일 파일 실행에서는 `::...`(경로 없음)로 나온다(2026-07-26
    실측). 허용 목록 키와 실패 메시지는 어떤 호출에서도 같아야 하므로 파일 경로를 직접 붙인다.
    """
    parts = node.nodeid.split("::")[1:]  # 경로 부분은 버리고 클래스·테스트 이름만 취한다
    try:
        rel = Path(node.path).resolve().relative_to(_PROJECT_ROOT).as_posix()
    except (AttributeError, ValueError):  # path 없음(비파일 노드)·루트 밖 경로
        rel = str(getattr(node, "path", "?"))
    return "::".join([rel, *parts])


def _dirty_attrs(module: ModuleType, attrs: Iterable[str]) -> list[str]:
    """`attrs` 중 값이 남아 있는(None이 아닌) 전역 이름들."""
    return [name for name in attrs if getattr(module, name, None) is not None]


def _run_cleanup(module: ModuleType, watch: _GlobalStateWatch) -> str | None:
    """정리 함수를 호출한다. 실패하면 예외 *타입명*을 돌려준다(침묵 실패 금지).

    정리 함수가 터져도 전역이 남으면 오염이 후속 테스트로 번지므로, 실패 시에는 전역을
    직접 비워 연쇄를 끊는다(`dispose_engine`도 성공 경로에서 같은 일을 한다 — 새 정리
    로직이 아니라 그 함수의 마지막 두 줄과 동일한 처리).
    """
    try:
        asyncio.run(getattr(module, watch.cleanup)())
    except Exception as exc:
        for name in watch.attrs:
            setattr(module, name, None)
        return type(exc).__name__
    return None


def _leak_message(
    node_id: str,
    watch: _GlobalStateWatch,
    dirty: list[str],
    cleanup_error: str | None,
) -> str:
    """무엇이·왜 문제이며·어떻게 고치는지를 담은 실패 메시지."""
    cleaned = (
        f"가드가 `{watch.cleanup}()`로 정리했다(후속 테스트는 무사)."
        if cleanup_error is None
        else (
            f"가드의 `{watch.cleanup}()` 정리가 {cleanup_error} 예외로 실패해 전역을 직접 "
            "비웠다 — 정리 함수도 함께 살펴라."
        )
    )
    return (
        f"[전역 상태 오염] {node_id}\n"
        f"  남긴 전역: {watch.module}." + f", {watch.module}.".join(dirty) + "\n"
        "  왜 문제인가: 같은 프로세스의 후속 테스트가 이 전역이 비어 있다고 단언하므로 "
        "*실행 순서에 따라 엉뚱한 테스트*가 깨진다 — 파일 단위 실행에서는 재현되지 않아 "
        "로컬 검증을 통과하고 CI에서만 터진다(2026-07-26 main red 실측).\n"
        f"  고치는 법: {watch.fix}\n"
        f"  {cleaned}\n"
        "  정리가 불가능한 *의도된* 잔존이라면 tests/backend/conftest.py의 "
        f'`_ALLOWED_GLOBAL_LEAKS`에 "{node_id}": "사유"로 등재하라(사유 필수·최후 수단).'
    )


@pytest.fixture(autouse=True)
def _guard_global_state_leaks(request: pytest.FixtureRequest) -> Iterator[None]:
    """[OPS-07] 테스트가 남긴 모듈 전역 캐시를 teardown에서 잡아 *그 테스트를* 실패시킨다.

    autouse·function 스코프라 가장 먼저 setup되고 → 가장 나중에 teardown된다. 즉 다른
    함수 스코프 픽스처의 정리(monkeypatch 복구·`dispose_engine` 호출 등)가 *끝난 뒤*에
    검사하므로, 제대로 정리하는 테스트를 거짓 실패시키지 않는다(양성 대조는
    `test_global_state_guard.py`가 동결).

    teardown에서 실패시키므로 pytest는 "ERROR at teardown of <test>"로 보고한다 —
    실패로 집계되고(exit 1) *오염을 만든 테스트의 nodeid*가 그대로 찍힌다.
    """
    yield

    problems: list[str] = []
    for watch in _WATCHED_GLOBALS:
        module = sys.modules.get(watch.module)
        if module is None:  # import조차 안 됐으면 전역이 채워질 수 없다
            continue
        dirty = _dirty_attrs(module, watch.attrs)
        if not dirty:
            continue

        node_id = _stable_node_id(request.node)
        if node_id in _ALLOWED_GLOBAL_LEAKS:
            if _ALLOWED_GLOBAL_LEAKS[node_id].strip():
                continue  # 사유 있는 의도된 잔존 — 손대지 않는다
            problems.append(
                f"[허용 목록 무효] {node_id}: `_ALLOWED_GLOBAL_LEAKS`에 *사유 없이* "
                "등재됐다. 빈 사유는 허용이 아니다 — 왜 정리할 수 없는지 적거나, "
                "등재를 지우고 테스트가 스스로 정리하게 고쳐라."
            )
            continue

        cleanup_error = _run_cleanup(module, watch)
        problems.append(_leak_message(node_id, watch, dirty, cleanup_error))

    if problems:
        pytest.fail("\n\n".join(problems), pytrace=False)
