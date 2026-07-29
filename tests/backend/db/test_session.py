"""db/session 엔진 생성 단위테스트 (hermetic — 연결 없음).

`create_async_engine`는 풀만 준비하므로(첫 쿼리 전까지 connect 안 함) 살아있는 PG 없이도
엔진·풀 클래스를 검증할 수 있다. slice 30: `db_disable_pool`이 NullPool을 고르는지 확인.
"""

from __future__ import annotations

import asyncio

from sqlalchemy.pool import NullPool
from whymath_backend.config import Settings
from whymath_backend.db.session import dispose_engine, get_engine


def _reset() -> None:
    # 전역 엔진 캐시 초기화(연결 없던 엔진의 dispose는 no-op).
    asyncio.run(dispose_engine())


def test_default_settings_use_connection_pool() -> None:
    """기본(db_disable_pool=False) → NullPool 아님(풀 사용)."""
    _reset()
    try:
        engine = get_engine(Settings())
        assert not isinstance(engine.pool, NullPool)
    finally:
        _reset()


def test_disable_pool_selects_nullpool() -> None:
    """db_disable_pool=True → NullPool(매 체크아웃 새 연결·크로스 루프 충돌 회피)."""
    _reset()
    try:
        engine = get_engine(Settings(db_disable_pool=True))
        assert isinstance(engine.pool, NullPool)
    finally:
        _reset()
