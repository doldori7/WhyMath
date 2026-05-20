"""L3 외부 의존 경계 테스트 — Protocol 충족성 + 인메모리 스텁 동작.

설계 정본: docs/architecture/03a_l3_router_design.md §F(캐시·관측성)·§D.3(비동기 큐).
범위 메모(M1.2): 라이브 서비스 없이 *경계(Protocol)*와 *테스트용 스텁*만 검증한다.
"""

from __future__ import annotations

from whymath_backend.l3.interfaces import (
    CacheBackend,
    InMemoryCache,
    RecordingTraceSink,
    TraceSink,
)


class TestInMemoryCache:
    async def test_get_miss_returns_none(self) -> None:
        """미스 시 None."""
        cache = InMemoryCache()
        assert await cache.get("absent") is None

    async def test_set_then_get(self) -> None:
        """저장 후 조회."""
        cache = InMemoryCache()
        await cache.set("k", "v", ttl_seconds=60)
        assert await cache.get("k") == "v"

    async def test_overwrite(self) -> None:
        """같은 키 재저장 시 덮어쓰기."""
        cache = InMemoryCache()
        await cache.set("k", "v1", ttl_seconds=60)
        await cache.set("k", "v2", ttl_seconds=60)
        assert await cache.get("k") == "v2"

    def test_satisfies_protocol(self) -> None:
        """InMemoryCache는 CacheBackend Protocol을 충족한다(runtime_checkable)."""
        assert isinstance(InMemoryCache(), CacheBackend)


class TestRecordingTraceSink:
    def test_records_appended(self) -> None:
        """record 호출이 누적된다."""
        sink = RecordingTraceSink()
        sink.record({"cost_tier": "local"})
        sink.record({"cost_tier": "cloud_mid"})
        assert len(sink.records) == 2
        assert sink.records[0]["cost_tier"] == "local"

    def test_satisfies_protocol(self) -> None:
        """RecordingTraceSink는 TraceSink Protocol을 충족한다."""
        assert isinstance(RecordingTraceSink(), TraceSink)
