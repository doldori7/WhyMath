"""Sliding window rate limiter — L4 코치 엔드포인트 사용자당 분당 상한.

**백엔드 2종**(`Settings.coach_rate_limit_backend`로 선택):
- `"memory"` (기본): 단일 프로세스 인메모리 deque. 사이드카·로컬·테스트.
- `"redis"`: Redis 정렬 집합(ZSET) + Lua 원자성. **분산/HA 환경 정합** — 다중 워커·
  다중 인스턴스에서 사용자당 카운트가 *전역* 공유. `l3/cache/redis_cache.py`의 lazy
  + 주입 가능(`_RedisClient` Protocol) 패턴 답습.

**경계**:
- 키 = `user_id`(인증된 사용자 단위). IP·세션 단위는 후속(미인증 표면 노출 시).
- 시계 = `time.monotonic()`(단조 — DST·NTP 조정 무관)·Redis 백엔드도 동일 시계 사용해
  *프로세스 간 시계 차이는 무관*(각 워커가 자기 시계로 ZADD; ±수ms 정합 충분).
- 동시성 = 인메모리는 FastAPI 단일 이벤트 루프 + GIL로 충분. **Redis는 Lua 스크립트로
  원자성 보장**(ZREMRANGEBYSCORE → ZCARD → ZADD/EXPIRE 한 트랜잭션).
- 미성년 PII 정합: 키는 UUID, 값은 타임스탬프 + UUID 토큰만(학생 발화 내용 0).
"""

from __future__ import annotations

import time
import uuid
from collections import deque
from typing import Annotated, Any, Protocol, cast, runtime_checkable

from fastapi import Depends, HTTPException, status

from whymath_backend.api._auth import ConsentedUser
from whymath_backend.config import Settings, get_settings

_WINDOW_SECONDS = 60.0


@runtime_checkable
class RateLimitBackend(Protocol):
    """rate limit 백엔드 — sliding window 카운트의 저장·검사 추상."""

    async def hit(self, user_id: uuid.UUID, *, limit: int, now: float) -> bool:
        """요청을 기록하고 *제한 내*면 True, 초과면 False(요청 미기록)."""
        ...

    async def reset(self) -> None:
        """모든 카운트 초기화 — 테스트 격리용. production 미호출."""
        ...


class InMemoryBackend:
    """프로세스-로컬 deque per user_id — 단일 인스턴스 한정.

    분산 환경에서는 워커별 별도 카운트 → 효과 ÷ N. 그 경우 `RedisBackend` 사용.
    """

    def __init__(self) -> None:
        self._by_user: dict[uuid.UUID, deque[float]] = {}

    async def hit(self, user_id: uuid.UUID, *, limit: int, now: float) -> bool:
        cutoff = now - _WINDOW_SECONDS
        bucket = self._by_user.setdefault(user_id, deque())
        while bucket and bucket[0] < cutoff:
            bucket.popleft()
        if len(bucket) >= limit:
            return False
        bucket.append(now)
        return True

    async def reset(self) -> None:
        self._by_user.clear()


# Redis 클라이언트 추상화 — l3/cache/redis_cache.py `_RedisClient` 패턴 답습.
# 우리가 실제로 쓰는 메서드만 좁게 선언(eval·ping).
@runtime_checkable
class _RedisClient(Protocol):
    async def eval(self, script: str, numkeys: int, *args: Any) -> Any:
        """Lua 스크립트 실행 — ZSET sliding window 원자 연산용."""
        ...

    async def ping(self) -> Any:
        """연결 도달성 확인."""
        ...

    async def delete(self, *names: str) -> Any:
        """키 삭제 — 테스트 reset용."""
        ...

    async def keys(self, pattern: str) -> Any:
        """패턴 매칭 키 목록 — 테스트 reset 보조."""
        ...


# Lua 스크립트 — *원자성* 핵심. ZREMRANGEBYSCORE → ZCARD → 조건부 ZADD/EXPIRE를
# 한 명령으로 묶어 race window 0. `now` 동일 타임스탬프 충돌 대비 멤버는 `now:uuid`.
_LUA_HIT = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local limit = tonumber(ARGV[2])
local cutoff = now - 60
redis.call('ZREMRANGEBYSCORE', key, '-inf', cutoff)
local count = redis.call('ZCARD', key)
if count < limit then
    redis.call('ZADD', key, now, ARGV[3])
    redis.call('EXPIRE', key, 60)
    return 1
end
return 0
"""


def _build_default_redis_client(settings: Settings) -> _RedisClient:  # pragma: no cover
    """기본 redis.asyncio 클라이언트 — 지연 import(라이브러리 없는 환경 보호).

    Redis 라이브러리·연결 의존성은 라이브 통합 테스트(@integration·실 Redis 데몬)에서
    검증한다 — hermetic 테스트는 `client=`로 가짜 주입(테스트 패턴 정합).
    """
    try:
        from redis.asyncio import Redis
    except ImportError as exc:
        raise RuntimeError(
            "redis Python 클라이언트가 설치되지 않았습니다. "
            "`pip install redis[hiredis]` 후 다시 시도하세요."
        ) from exc
    client = Redis.from_url(settings.redis_url, decode_responses=True)
    return cast(_RedisClient, client)


class RedisBackend:
    """Redis ZSET sliding window — 분산/HA 정합.

    Lua 스크립트 `_LUA_HIT`가 ZREMRANGEBYSCORE→ZCARD→조건부 ZADD/EXPIRE를 원자로
    수행해 race window 0. 키 prefix `rate:` + user_id(UUID). 60초 TTL 자동 만료로
    유휴 사용자 키 누수 방지.
    """

    _KEY_PREFIX = "rate:coach:"

    def __init__(
        self,
        *,
        client: _RedisClient | None = None,
        settings: Settings | None = None,
    ) -> None:
        self._client = client
        self._settings = settings

    @property
    def _resolved_settings(self) -> Settings:
        if self._settings is None:
            self._settings = get_settings()
        return self._settings

    def _get_client(self) -> _RedisClient:
        if self._client is None:
            self._client = _build_default_redis_client(self._resolved_settings)
        return self._client

    def _key(self, user_id: uuid.UUID) -> str:
        return f"{self._KEY_PREFIX}{user_id}"

    async def hit(self, user_id: uuid.UUID, *, limit: int, now: float) -> bool:
        client = self._get_client()
        unique_member = f"{now}:{uuid.uuid4().hex}"
        raw = await client.eval(_LUA_HIT, 1, self._key(user_id), now, limit, unique_member)
        return int(raw) == 1

    async def reset(self) -> None:
        """패턴 매칭 키 일괄 삭제 — 테스트 격리용. production 미호출."""
        client = self._get_client()
        keys = await client.keys(f"{self._KEY_PREFIX}*")
        if keys:
            await client.delete(*keys)


# 모듈 전역 — FastAPI 단일 프로세스 가정에서 backend 인스턴스 1개 재사용.
# 테스트는 `set_backend()`로 가짜 주입.
_BACKEND: RateLimitBackend = InMemoryBackend()


def set_backend(backend: RateLimitBackend) -> None:
    """전역 백엔드 교체 — 테스트·런타임 전환용."""
    global _BACKEND
    _BACKEND = backend


def get_backend() -> RateLimitBackend:
    """현재 백엔드 반환 — 테스트 단언용."""
    return _BACKEND


def configure_backend_from_settings(settings: Settings) -> None:
    """설정에 따라 백엔드 선택·설치. 앱 lifespan 시작 시 호출(또는 첫 사용 전)."""
    if settings.coach_rate_limit_backend == "redis":
        set_backend(RedisBackend(settings=settings))
    else:
        set_backend(InMemoryBackend())


async def reset_store() -> None:
    """테스트 격리용 — 현재 백엔드의 카운트 리셋. production 미호출."""
    await _BACKEND.reset()


async def rate_limit_user(
    user: ConsentedUser,
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    """사용자당 분당 상한 검사. 초과 시 429 + Retry-After: 60.

    `coach_rate_limit_per_minute=0`이면 비활성(테스트·개발). 인증된 사용자에만 적용.
    """
    limit = settings.coach_rate_limit_per_minute
    if limit == 0:
        return
    if not await _BACKEND.hit(user.user_id, limit=limit, now=time.monotonic()):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="요청이 너무 많습니다(분당 한도 초과). 잠시 후 다시 시도하세요.",
            headers={"Retry-After": "60"},
        )


RateLimited = Depends(rate_limit_user)
"""의존성 별칭 — coach 엔드포인트에 `dependencies=[RateLimited]`로 부착."""
