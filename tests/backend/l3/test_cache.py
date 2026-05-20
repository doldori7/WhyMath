"""RedisCacheBackend(cache.py) 단위 테스트 — get/set/TTL을 가짜 redis로 검증.

설계 정본: docs/architecture/03a_l3_router_design.md §F.1(캐시 키 3축·TTL).
범위 메모(M1.2): 라이브 Redis 없이, 손으로 짠 가짜 클라이언트를 주입해 *어댑터 계약*
(get→str|None, set→ex=ttl)만 검증한다. 모킹 라이브러리 미사용(pyproject 의도).
"""

from __future__ import annotations

from typing import Any

import pytest

from whymath_backend.config import Settings
from whymath_backend.l3.cache import RedisCacheBackend
from whymath_backend.l3.interfaces import CacheBackend


class _FakeRedis:
    """손으로 짠 가짜 redis.asyncio 클라이언트 — get/set 호출과 TTL을 기록한다.

    decode_responses=True 가정과 동형: get은 str|None을 돌려준다. set의 ex(TTL)도
    함께 기록하여 어댑터가 TTL을 전달하는지 검증할 수 있게 한다.
    """

    def __init__(self) -> None:
        self.store: dict[str, str] = {}
        self.ttls: dict[str, int | None] = {}
        self.get_calls: list[str] = []
        self.set_calls: list[tuple[str, str, int | None]] = []

    async def get(self, name: str) -> Any:
        self.get_calls.append(name)
        return self.store.get(name)

    async def set(self, name: str, value: str, ex: int | None = None) -> Any:
        self.set_calls.append((name, value, ex))
        self.store[name] = value
        self.ttls[name] = ex
        return True


def _backend(fake: _FakeRedis) -> RedisCacheBackend:
    """가짜 redis를 주입한 RedisCacheBackend (settings는 기본값)."""
    return RedisCacheBackend(client=fake, settings=Settings())


class TestRedisCacheBackend:
    async def test_get_miss_returns_none(self) -> None:
        """미스 시 None."""
        fake = _FakeRedis()
        assert await _backend(fake).get("absent") is None
        assert fake.get_calls == ["absent"]

    async def test_set_then_get(self) -> None:
        """저장 후 조회 — 어댑터가 redis get/set을 위임한다."""
        fake = _FakeRedis()
        backend = _backend(fake)
        await backend.set("k", "v", ttl_seconds=60)
        assert await backend.get("k") == "v"

    async def test_set_applies_ttl_as_ex(self) -> None:
        """set은 TTL을 redis `ex` 인자로 전달한다(03a §F.1 만료)."""
        fake = _FakeRedis()
        await _backend(fake).set("k", "v", ttl_seconds=86400)
        assert fake.set_calls == [("k", "v", 86400)]
        assert fake.ttls["k"] == 86400

    async def test_get_coerces_to_str(self) -> None:
        """redis가 비-str을 돌려줘도 str로 정규화한다(decode 변형 방어)."""
        fake = _FakeRedis()
        fake.store["num"] = 12345  # type: ignore[assignment]  # 의도적 비-str 주입
        result = await _backend(fake).get("num")
        assert result == "12345"
        assert isinstance(result, str)

    async def test_satisfies_protocol(self) -> None:
        """RedisCacheBackend는 CacheBackend Protocol을 충족한다(runtime_checkable)."""
        assert isinstance(_backend(_FakeRedis()), CacheBackend)

    async def test_lazy_build_uses_settings_url(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """client 미주입 시 settings.redis_url로 lazy build한다(빌더를 가짜로 가로챔)."""
        captured: dict[str, str] = {}

        def _fake_build(redis_url: str) -> _FakeRedis:
            captured["url"] = redis_url
            return _FakeRedis()

        # _build_default_redis_client를 가짜로 치환 — 라이브 Redis 생성 회피.
        monkeypatch.setattr("whymath_backend.l3.cache._build_default_redis_client", _fake_build)
        backend = RedisCacheBackend(client=None, settings=Settings(redis_url="redis://h:6379/3"))
        await backend.get("k")  # 첫 접근에서 lazy build 발동
        assert captured["url"] == "redis://h:6379/3"
