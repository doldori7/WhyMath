"""db.session 전역 누수 가드 — 탐지·격리 로직 (OPS-07).

`tests/backend/conftest.py`의 autouse 픽스처 `_guard_db_session_global_leak`이 이 모듈을
소비한다. 로직을 여기로 뽑아낸 이유: **가드 자체의 변별력**을 별도 테스트
(`test_db_leak_guard.py`)에서 *직접* 실측하기 위해서다(오염 주입 → 실제 실패 신호 확인).

배경 사고(2026-07-26): OPS-06의 한 테스트가 pg_cached store 생성으로 `db.session._engine`
(모듈 전역·지연 캐시)을 채우고 정리하지 않아, 같은 프로세스의 후속 테스트
`db/test_problem_orm.py::test_session_module_imports_without_connection`(전역이 None임을 단언)가
*실행 순서 때문에* 깨졌다 → main CI red. 파일 단위 실행에서는 재현되지 않고 전체 스위트에서만
터지는 오염이었다. 이 가드는 그 오염을 *그 테스트 자체*의 결정론적 실패로 바꾼다.
"""

from __future__ import annotations

import asyncio

# db.session 모듈 전역 중 '테스트 간 None이어야 하는' 지연 캐시 심볼.
# (test_session_module_imports_without_connection이 단언하는 불변식.)
DB_SESSION_LEAK_SYMBOLS: tuple[str, ...] = ("_engine", "_sessionmaker")

# 누수 실패 메시지의 고정 접두 — 테스트가 이 마커로 실패 신호를 판별한다(변별력 grep).
LEAK_MARKER: str = "[db.session 전역 누수]"


def db_session_leak_reason() -> str | None:
    """db.session 모듈 전역이 남아 있으면 사유 문자열, 깨끗하면 None.

    import를 함수 안에서 한다 — 모듈 로드 시점의 부작용을 피하고, 테스트가 db.session을
    전혀 건드리지 않는 흔한 경우에 불필요한 로드를 만들지 않는다.
    """
    from whymath_backend.db import session as _sess

    leaked = [name for name in DB_SESSION_LEAK_SYMBOLS if getattr(_sess, name) is not None]
    if not leaked:
        return None
    return ", ".join(f"db.session.{name}" for name in leaked)


def contain_db_session_leak() -> None:
    """누수된 전역을 되돌려 다음 테스트를 격리한다(dispose_engine 관행 재사용).

    연결 없는 hermetic 엔진의 dispose는 no-op이지만, 실 연결이 열렸을 수 있는 경우까지
    안전하게 반납하려면 dispose_engine()이 정답이다. 실행 중 루프가 있어 asyncio.run이
    거부되는 드문 경우에만 전역을 직접 되돌린다(격리가 목적이므로 이것으로 충분).
    """
    from whymath_backend.db import session as _sess

    try:
        asyncio.run(_sess.dispose_engine())
    except RuntimeError:
        _sess._engine = None
        _sess._sessionmaker = None


def format_leak_failure(nodeid: str, reason: str) -> str:
    """누수 테스트에 붙일 실패 메시지 — 귀책 대상(nodeid)·정리 방법을 함께 안내한다."""
    return (
        f"{LEAK_MARKER} 테스트 '{nodeid}' 가 {reason} 을(를) 남겼다 — 같은 프로세스의 후속 "
        "테스트가 '전역이 None'임을 단언하면 실행 순서 때문에 깨진다(2026-07-26 main CI red 사고). "
        "get_engine()/get_session()을 (직접 또는 lifespan·pg_cached store 경유로) 부른 뒤에는 "
        "try/finally에서 `await dispose_engine()`으로 정리하라(db/test_session.py::_reset 선례). "
        "HTTP 경로 테스트는 app.dependency_overrides[get_session]=<fake>로 실 엔진 진입 자체를 "
        "막을 수 있다(api/test_ocr_endpoint.py 선례)."
    )
