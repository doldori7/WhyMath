"""RedisCache 단위테스트 — 인메모리 가짜 redis 클라이언트 주입 (라이브 서비스 없음).

ollama.py 단위테스트(FakeOllamaClient를 `_OllamaClient` 시임으로 주입)를 미러링한다.
실제 redis 데몬·`redis.asyncio`에 의존하지 않는다 → CI hermetic.

가짜 클라이언트(`FakeRedisClient`)는 `ex` 인자를 *기록*하므로, ttl<=0 무기한 폴백
경로(set에 ex를 *전달하지 않음*)를 직접 검증할 수 있다 — 이 슬라이스의 핵심 엣지케이스.

설계 정본: docs/architecture/03a_l3_router_design.md §F.1(캐시 키 의미).
"""

from __future__ import annotations

from typing import Any

import pytest

from whymath_backend.l3.cache import RedisCache
from whymath_backend.l3.cache.redis_cache import _decode, _RedisClient


class FakeRedisClient:
    """가짜 redis.asyncio 클라이언트 — 인메모리 dict + `ex` 기록 + 호출 기록.

    `_RedisClient` Protocol을 구조적으로 충족한다. 저장 시 전달된 `ex`(만료 초 또는
    None)를 키별로 기록해 ttl<=0 무기한 폴백 경로(ex 미전달)를 단정할 수 있게 한다.
    `return_bytes=True`면 get이 bytes를 돌려줘 `_decode` 디코딩 경로를 탄다(실제
    decode_responses=False 클라이언트 모사). `ping_raises`로 도달 실패도 모사한다.
    """

    def __init__(
        self,
        *,
        return_bytes: bool = False,
        ping_result: Any = True,
        ping_raises: Exception | None = None,
    ) -> None:
        self._return_bytes = return_bytes
        self._ping_result = ping_result
        self._ping_raises = ping_raises
        # 키 → 저장된 값(원본 str)
        self._store: dict[str, str] = {}
        # 호출 기록: set은 (key, value, ex) 튜플 — ex는 None일 수 있음
        self.set_calls: list[tuple[str, str, int | None]] = []
        self.get_calls: list[str] = []
        self.ping_calls: int = 0

    async def get(self, name: str) -> Any:
        self.get_calls.append(name)
        value = self._store.get(name)
        if value is None:
            return None
        # decode_responses=False 클라이언트 모사 — bytes 반환으로 _decode 경로 검증
        return value.encode("utf-8") if self._return_bytes else value

    async def set(
        self,
        name: str,
        value: str,
        *,
        ex: int | None = None,
    ) -> Any:
        # 핵심: ex가 무엇으로 전달됐는지(또는 안 됐는지) 그대로 기록한다.
        self.set_calls.append((name, value, ex))
        self._store[name] = value
        return True

    async def ping(self) -> Any:
        self.ping_calls += 1
        if self._ping_raises is not None:
            raise self._ping_raises
        return self._ping_result


class TestGet:
    async def test_miss_returns_none(self) -> None:
        """미스 시 None — 빈 저장소 조회."""
        cache = RedisCache(client=FakeRedisClient())
        assert await cache.get("absent") is None

    async def test_hit_returns_str(self) -> None:
        """저장 후 조회 시 디코드된 str 반환."""
        client = FakeRedisClient()
        cache = RedisCache(client=client)
        await cache.set("k", "원시출력", ttl_seconds=60)
        assert await cache.get("k") == "원시출력"
        assert client.get_calls == ["k"]

    async def test_hit_decodes_bytes(self) -> None:
        """redis가 bytes를 돌려줘도(decode_responses=False) str로 디코딩한다."""
        client = FakeRedisClient(return_bytes=True)
        cache = RedisCache(client=client)
        await cache.set("k", "한글값", ttl_seconds=60)
        result = await cache.get("k")
        assert result == "한글값"
        assert isinstance(result, str)


class TestSet:
    async def test_set_with_positive_ttl_passes_ex(self) -> None:
        """양수 TTL → redis SET ... EX ttl 로 만료를 전달한다."""
        client = FakeRedisClient()
        cache = RedisCache(client=client)
        await cache.set("k", "v", ttl_seconds=120)
        assert client.set_calls == [("k", "v", 120)]

    async def test_set_with_zero_ttl_omits_ex(self) -> None:
        """엣지케이스: ttl=0 → EX 0를 전달하지 않고 무기한 저장(redis가 EX 0 거부)."""
        client = FakeRedisClient()
        cache = RedisCache(client=client)
        await cache.set("k", "v", ttl_seconds=0)
        # ex는 None(미전달)이어야 한다 — EX 0/음수는 redis가 거부하므로.
        assert client.set_calls == [("k", "v", None)]
        # 값 자체는 저장돼 조회 가능(무기한 폴백).
        assert await cache.get("k") == "v"

    async def test_set_with_negative_ttl_omits_ex(self) -> None:
        """엣지케이스: 음수 TTL도 ttl<=0 분기 → ex 미전달(무기한 폴백)."""
        client = FakeRedisClient()
        cache = RedisCache(client=client)
        await cache.set("k", "v", ttl_seconds=-5)
        assert client.set_calls == [("k", "v", None)]

    async def test_overwrite(self) -> None:
        """같은 키 재저장 시 덮어쓰기."""
        client = FakeRedisClient()
        cache = RedisCache(client=client)
        await cache.set("k", "v1", ttl_seconds=60)
        await cache.set("k", "v2", ttl_seconds=60)
        assert await cache.get("k") == "v2"


class TestPing:
    async def test_ping_true_on_pong(self) -> None:
        """ping 성공(True/PONG) → True."""
        cache = RedisCache(client=FakeRedisClient(ping_result=True))
        assert await cache.ping() is True

    async def test_ping_true_on_bytes_pong(self) -> None:
        """ping이 b'PONG'(truthy)를 돌려줘도 True로 정규화."""
        cache = RedisCache(client=FakeRedisClient(ping_result=b"PONG"))
        assert await cache.ping() is True

    async def test_ping_false_on_falsy_result(self) -> None:
        """ping이 falsy(예: None)를 돌려주면 False."""
        cache = RedisCache(client=FakeRedisClient(ping_result=None))
        assert await cache.ping() is False

    async def test_ping_false_on_connection_error(self) -> None:
        """연결 오류는 예외로 던지지 않고 False로 흡수(레디니스용 비크래시)."""
        client = FakeRedisClient(ping_raises=ConnectionError("refused"))
        cache = RedisCache(client=client)
        assert await cache.ping() is False
        assert client.ping_calls == 1


class TestDecodeNormalizer:
    """_decode 방어적 정규화 — get 반환값을 str|None으로."""

    def test_none_stays_none(self) -> None:
        assert _decode(None) is None

    def test_str_passthrough(self) -> None:
        assert _decode("이미str") == "이미str"

    def test_bytes_decoded(self) -> None:
        assert _decode("값".encode("utf-8")) == "값"

    def test_bytearray_decoded(self) -> None:
        assert _decode(bytearray("값".encode("utf-8"))) == "값"

    def test_unexpected_type_returns_none(self) -> None:
        """예기치 못한 타입(int 등)은 미스로 취급(None) — 비정상 값 안전 처리."""
        assert _decode(12345) is None


class TestLazyDefaults:
    def test_default_client_built_from_settings(self) -> None:
        """클라이언트 미주입 시 Settings.redis_url로 redis.asyncio 클라이언트를 지연 생성.

        Redis.from_url(...)은 네트워크를 즉시 타지 않으므로 라이브 데몬 없이도 안전하다.
        _build_default_client·_get_client·_resolved_settings 기본 경로를 모두 통과시킨다.
        """
        from whymath_backend.config import Settings

        cache = RedisCache(settings=Settings(redis_url="redis://127.0.0.1:6379/0"))
        client = cache._get_client()
        assert isinstance(client, _RedisClient)  # runtime_checkable Protocol 충족
        # 두 번째 호출은 캐시된 같은 인스턴스를 돌려준다(지연 1회 생성).
        assert cache._get_client() is client

    def test_resolved_settings_falls_back_to_global(self) -> None:
        """settings 미주입 시 전역 get_settings()로 폴백한다."""
        from whymath_backend.config import Settings, get_settings

        get_settings.cache_clear()
        cache = RedisCache()
        assert isinstance(cache._resolved_settings, Settings)

    def test_satisfies_cache_backend_protocol(self) -> None:
        """RedisCache는 CacheBackend Protocol을 충족한다(runtime_checkable)."""
        from whymath_backend.l3.interfaces import CacheBackend

        assert isinstance(RedisCache(client=FakeRedisClient()), CacheBackend)


def test_fake_client_satisfies_seam_protocol() -> None:
    """가짜 클라이언트가 _RedisClient 시임을 구조적으로 충족하는지 확인(테스트 위생)."""
    assert isinstance(FakeRedisClient(), _RedisClient)


@pytest.mark.parametrize("ttl", [0, -1, -100])
async def test_nonpositive_ttls_never_pass_ex(ttl: int) -> None:
    """0/음수 TTL은 어떤 값이든 ex를 전달하지 않는다(엣지케이스 표 검증)."""
    client = FakeRedisClient()
    cache = RedisCache(client=client)
    await cache.set("k", "v", ttl_seconds=ttl)
    assert client.set_calls[0][2] is None
