"""L3 응답 캐시 — `CacheBackend` Protocol의 Redis 구현.

설계 정본: docs/architecture/03a_l3_router_design.md §F.1(캐시 키 3축·TTL).
캐시 키 생성은 라우터의 cache_key_for()가 책임지고(세 축 포함), 본 모듈은 *저장소*
(Redis)만 담당한다 — 키-값 get/set + TTL.

테스트 가능성(bench_latency.py 패턴 미러링):
  - `redis.asyncio` import는 *함수 안에서만*(lazy) — 모듈은 stdlib만으로 로드 가능.
  - 클라이언트 주입 가능 — 테스트는 손으로 짠 가짜 Redis(get/set)를 주입한다.
"""

from __future__ import annotations

from typing import Any, Protocol, cast

from whymath_backend.config import Settings, get_settings


class _RedisClientProtocol(Protocol):
    """redis.asyncio 클라이언트의 최소 인터페이스 (get/set).

    실제 `redis.asyncio.Redis`와 동형이지만, 테스트에서는 임의 객체로 대체 가능.
    `set`의 `ex`는 만료 초(TTL). `get`은 decode_responses=True 가정 시 str|None.
    """

    async def get(self, name: str) -> Any: ...

    async def set(  # noqa: A003 — redis 시그니처 보존(내장 set과 무관)
        self,
        name: str,
        value: str,
        ex: int | None = None,
    ) -> Any: ...


def _build_default_redis_client(redis_url: str) -> _RedisClientProtocol:  # pragma: no cover
    """기본 redis.asyncio 클라이언트 생성. import 실패 시 명확한 에러.

    라이브 SDK 생성 shim — 라이브 Redis 없이는 실행 불가하므로 커버리지 제외(테스트는
    monkeypatch로 치환해 lazy build 경로만 검증한다, test_cache.py).
    `redis.asyncio` import는 *이 함수 안에서만* 한다(lazy). importlib 동적 로드 + cast로
    mypy --strict를 통과한다(quality_eval.py 패턴). decode_responses=True로 생성해
    get이 str을 돌려주게 한다(캐시 값은 텍스트).
    """
    import importlib

    try:
        redis_asyncio = importlib.import_module("redis.asyncio")
    except ImportError as exc:
        raise RuntimeError(
            "redis 클라이언트가 설치되지 않았습니다. `pip install redis` 후 재시도."
        ) from exc
    client = redis_asyncio.from_url(redis_url, decode_responses=True)
    return cast("_RedisClientProtocol", client)


class RedisCacheBackend:
    """Redis 응답 캐시 — `CacheBackend` 충족 (03a §F.1).

    클라이언트 주입 가능 — 기본 None이면 첫 접근 시 settings.redis_url로 lazy build.
    InMemoryCache(interfaces.py)의 프로덕션 대체물 — 동일 Protocol을 구현한다.
    """

    def __init__(
        self,
        *,
        client: _RedisClientProtocol | None = None,
        settings: Settings | None = None,
    ) -> None:
        self._client = client
        self._settings = settings if settings is not None else get_settings()

    def _ensure_client(self) -> _RedisClientProtocol:
        """주입된 클라이언트가 없으면 settings.redis_url로 lazy 생성."""
        if self._client is None:
            self._client = _build_default_redis_client(self._settings.redis_url)
        return self._client

    async def get(self, key: str) -> str | None:
        """키로 캐시 조회. 미스면 None."""
        value = await self._ensure_client().get(key)
        return None if value is None else str(value)

    async def set(self, key: str, value: str, ttl_seconds: int) -> None:
        """키-값 저장(TTL 초). redis SET ... EX ttl_seconds로 만료를 적용한다."""
        await self._ensure_client().set(key, value, ex=ttl_seconds)
