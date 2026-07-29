"""RedisCache 통합 테스트 — 실제 Redis 데몬 호출 (Phaiakes9 전용).

기본 SKIP. 실행하려면 환경변수 `WHYMATH_RUN_INTEGRATION=1`(+ 필요 시
`WHYMATH_REDIS_URL`)를 설정한다. CI는 이 변수를 설정하지 않으므로 자동으로 빠진다
(tests/backend/conftest.py의 pytest_collection_modifyitems 게이트). ollama 통합
테스트(test_ollama_integration.py)와 동일한 게이트·패턴을 따른다.

목적: set→get 왕복, 양수 TTL의 실제 만료(SET ... EX), ttl<=0 무기한 폴백, ping
도달성이 *실 redis*에서 동작하는지 Kiki가 Phaiakes9에서 확인. 라이브러리(redis)는
이미 의존성에 있고(redis[hiredis]>=5.1.0), `redis.asyncio`로 연결한다.

설계 정본: docs/architecture/03a_l3_router_design.md §F.1(캐시 키·TTL 의미).
"""

from __future__ import annotations

import uuid

import pytest
from whymath_backend.config import Settings
from whymath_backend.l3.cache import RedisCache

pytestmark = pytest.mark.integration


def _fresh_cache() -> RedisCache:
    """기본 설정(WHYMATH_REDIS_URL 또는 로컬 루프백)으로 RedisCache 생성."""
    return RedisCache(settings=Settings())


def _unique_key(suffix: str) -> str:
    """테스트 간 충돌·잔여 방지를 위한 고유 키(네임스페이스 + uuid)."""
    return f"whymath:test:{suffix}:{uuid.uuid4().hex}"


async def test_ping_reachable_on_live_daemon() -> None:
    """실제 redis 데몬에 닿으면 ping True."""
    cache = _fresh_cache()
    reachable = await cache.ping()
    assert reachable is True, "Redis 도달 실패 — WHYMATH_REDIS_URL 확인"


async def test_set_get_roundtrip_e2e() -> None:
    """set→get 왕복이 실 redis에서 동작(디코딩 포함)."""
    cache = _fresh_cache()
    if not await cache.ping():
        pytest.skip("Redis 미도달 — 통합 테스트 건너뜀")
    key = _unique_key("roundtrip")
    await cache.set(key, "원시 출력 값", ttl_seconds=60)
    assert await cache.get(key) == "원시 출력 값"


async def test_positive_ttl_actually_expires_e2e() -> None:
    """양수 TTL은 실제 만료된다 — 1초 TTL 저장 후 만료를 대기해 미스 확인.

    InMemoryCache는 TTL을 기록만 했지만(만료 없음), RedisCache는 redis 네이티브
    만료(SET ... EX)로 실제 사라진다 — 이것이 S2의 핵심 차이다. 만료 대기는
    redis 서버 시계가 끊을 때까지 폴링한다(고정 sleep 회피).
    """
    import asyncio

    cache = _fresh_cache()
    if not await cache.ping():
        pytest.skip("Redis 미도달 — 통합 테스트 건너뜀")
    key = _unique_key("expiry")
    await cache.set(key, "곧 만료", ttl_seconds=1)
    assert await cache.get(key) == "곧 만료"  # 만료 전엔 존재

    # 만료까지 폴링(최대 5초) — redis 서버 시계 기준으로 사라질 때까지.
    deadline = asyncio.get_event_loop().time() + 5.0
    while asyncio.get_event_loop().time() < deadline:
        if await cache.get(key) is None:
            break
        await asyncio.sleep(0.2)
    assert await cache.get(key) is None, "TTL 만료 후에도 키가 남아 있음"


async def test_nonpositive_ttl_persists_without_expiry_e2e() -> None:
    """ttl<=0 무기한 폴백 — 만료 인자 없이 저장되어 (TTL이 -1) 지속된다.

    저장 후 즉시 조회되면 충분(만료 인자 미전달 검증은 단위테스트가 담당). 잔여
    방지를 위해 끝에서 짧은 TTL로 재설정해 정리한다.
    """
    cache = _fresh_cache()
    if not await cache.ping():
        pytest.skip("Redis 미도달 — 통합 테스트 건너뜀")
    key = _unique_key("noexpiry")
    await cache.set(key, "무기한", ttl_seconds=0)
    assert await cache.get(key) == "무기한"
    # 정리: 잔여 키가 무기한 남지 않도록 짧은 TTL로 재설정(만료 위임).
    await cache.set(key, "정리", ttl_seconds=1)
