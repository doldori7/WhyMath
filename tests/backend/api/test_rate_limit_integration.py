"""RedisBackend rate limiter 통합테스트 — 실 Redis로 분산 정합 검증 (기본 SKIP).

`_LUA_HIT` 스크립트의 *원자성*과 ZSET sliding window 의미를 실 Redis 데몬에서 검증
(fake는 의미는 재현하나 Lua 실행은 통과만 함). 다중 인스턴스 정합의 핵심은 "두 백엔드
인스턴스가 같은 키를 공유하면 카운트가 누적된다"는 점 — 테스트로 시뮬레이션.

이벤트 루프 메모: redis-py async client는 이벤트 루프 바인딩이라 `asyncio.run()`을
테스트 안에서 *한 번만* 호출해야 한다(루프 재생성 → 'Event loop is closed' 에러 회피).
"""

from __future__ import annotations

import asyncio
import time
import uuid

import pytest

pytestmark = pytest.mark.integration


async def _redis_reachable() -> bool:
    try:
        from redis.asyncio import Redis
    except ImportError:
        return False
    client = Redis.from_url("redis://127.0.0.1:6379/0", decode_responses=True)
    try:
        await client.ping()
        return True
    except Exception:
        return False
    finally:
        await client.aclose()


def test_redis_backend_enforces_limit_on_live_daemon() -> None:
    """실 Redis에서 단일 인스턴스 sliding window — limit=2, 3회째 차단."""
    if not asyncio.run(_redis_reachable()):
        pytest.skip("Redis 미도달 — redis://127.0.0.1:6379 확인")

    async def _run() -> None:
        from pydantic import SecretStr

        from whymath_backend.api._rate_limit import RedisBackend
        from whymath_backend.config import Settings

        settings = Settings(
            jwt_secret_key=SecretStr("integration-jwt-secret-0123456789abcdef"),
            redis_url="redis://127.0.0.1:6379/0",
        )
        backend = RedisBackend(settings=settings)
        uid = uuid.uuid4()
        try:
            now = time.monotonic()
            assert (await backend.hit(uid, category="read", limit=2, now=now)).allowed is True
            assert (await backend.hit(uid, category="read", limit=2, now=now + 0.1)).allowed is True
            assert (
                await backend.hit(uid, category="read", limit=2, now=now + 0.2)
            ).allowed is False
        finally:
            await backend.reset()

    asyncio.run(_run())


def test_evalsha_recovers_from_script_flush_on_live_daemon() -> None:
    """슬라이스 13 — 실 Redis에서 SCRIPT FLUSH 후에도 자동 복구.

    NOSCRIPT 시 backend가 SCRIPT LOAD + EVALSHA 재시도로 자동 복구하는지 검증
    (Redis 재시작·SCRIPT FLUSH의 운영 시나리오 정합).
    """
    if not asyncio.run(_redis_reachable()):
        pytest.skip("Redis 미도달 — redis://127.0.0.1:6379 확인")

    async def _run() -> None:
        from pydantic import SecretStr
        from redis.asyncio import Redis

        from whymath_backend.api._rate_limit import RedisBackend
        from whymath_backend.config import Settings

        settings = Settings(
            jwt_secret_key=SecretStr("integration-jwt-secret-0123456789abcdef"),
            redis_url="redis://127.0.0.1:6379/0",
        )
        backend = RedisBackend(settings=settings)
        uid = uuid.uuid4()
        try:
            # 첫 hit — 자동 SCRIPT LOAD + EVALSHA(NOSCRIPT 폴백)
            assert (
                await backend.hit(uid, category="read", limit=10, now=time.monotonic())
            ).allowed is True
            # Redis SCRIPT FLUSH로 캐시 강제 비움(운영 시 SCRIPT FLUSH·재시작 시나리오)
            admin = Redis.from_url("redis://127.0.0.1:6379/0", decode_responses=True)
            try:
                await admin.script_flush()
            finally:
                await admin.aclose()
            # 다음 hit — backend가 NoScriptError 잡아 자동 복구
            assert (
                await backend.hit(uid, category="read", limit=10, now=time.monotonic())
            ).allowed is True
        finally:
            await backend.reset()

    asyncio.run(_run())


def test_redis_backend_distributed_consistency_on_live_daemon() -> None:
    """**분산 정합 핵심 검증** — 별도 `RedisBackend` 인스턴스가 같은 키 공간 공유.

    인메모리는 워커별 별도 카운트라 N워커 × limit 만큼 허용된다. Redis는 ZSET을 공유해
    전역 카운트가 limit로 묶인다 — 본 테스트가 그 차이를 *증명*.
    """
    if not asyncio.run(_redis_reachable()):
        pytest.skip("Redis 미도달 — redis://127.0.0.1:6379 확인")

    async def _run() -> None:
        from pydantic import SecretStr

        from whymath_backend.api._rate_limit import RedisBackend
        from whymath_backend.config import Settings

        settings = Settings(
            jwt_secret_key=SecretStr("integration-jwt-secret-0123456789abcdef"),
            redis_url="redis://127.0.0.1:6379/0",
        )
        worker_a = RedisBackend(settings=settings)
        worker_b = RedisBackend(settings=settings)
        uid = uuid.uuid4()
        try:
            now = time.monotonic()
            assert (await worker_a.hit(uid, category="read", limit=2, now=now)).allowed is True
            # worker_b — 같은 사용자·같은 limit·다른 인스턴스. ZSET 공유라 카운트 누적
            assert (
                await worker_b.hit(uid, category="read", limit=2, now=now + 0.1)
            ).allowed is True
            # 세번째 — 글로벌 한도 초과로 거부(어느 워커든)
            assert (
                await worker_a.hit(uid, category="read", limit=2, now=now + 0.2)
            ).allowed is False
            assert (
                await worker_b.hit(uid, category="read", limit=2, now=now + 0.3)
            ).allowed is False
        finally:
            await worker_a.reset()

    asyncio.run(_run())
