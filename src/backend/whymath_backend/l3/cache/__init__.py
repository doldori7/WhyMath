"""L3 응답 캐시 구현 — interfaces.CacheBackend Protocol의 실제 구현체.

범위 메모 (M1.2-live S2): Redis 구현만 둔다. 인메모리 스텁(InMemoryCache)은
테스트용으로 interfaces.py에 그대로 남는다(완벽한 hermetic 테스트 더블). 다층
캐시(L1 로컬 + L2 Redis)·캐시 무효화 정책 등은 후속 슬라이스 범위다.
"""

from whymath_backend.l3.cache.redis_cache import (
    CacheDegradationCounter,
    CacheDegradationSnapshot,
    RedisCache,
    cache_degradation_snapshot,
    reset_cache_degradation,
)

__all__ = [
    "CacheDegradationCounter",
    "CacheDegradationSnapshot",
    "RedisCache",
    "cache_degradation_snapshot",
    "reset_cache_degradation",
]
