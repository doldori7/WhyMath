"""RedisCache 단위테스트 — 인메모리 가짜 redis 클라이언트 주입 (라이브 서비스 없음).

ollama.py 단위테스트(FakeOllamaClient를 `_OllamaClient` 시임으로 주입)를 미러링한다.
실제 redis 데몬·`redis.asyncio`에 의존하지 않는다 → CI hermetic.

가짜 클라이언트(`FakeRedisClient`)는 `ex` 인자를 *기록*하므로, ttl<=0 무기한 폴백
경로(set에 ex를 *전달하지 않음*)를 직접 검증할 수 있다 — 이 슬라이스의 핵심 엣지케이스.

OPS-05(장애 강등) 테스트 설계 — *변별력*이 핵심이다:
  - 폭발하는 가짜(`ExplodingRedisClient`)는 **테스트 전용 커스텀 예외**(`CacheBoomError`)를
    던진다. 로그 단정이 그 *타입명 문자열*을 찾으므로, 구현이 무타입 경고("캐시 실패")만
    남기면 테스트가 실패한다 — 성공/실패 양쪽에서 통과하는 위장 검사가 아니다.
  - 반대 축(**양성 대조**)으로 정상 클라이언트에서 값 반환·ex 전달·강등 0을 동결한다 —
    가드가 정상 경로를 망가뜨리지 않음을 함께 잡는다.
  - 키 미노출도 단정한다(캐시 키 = 프롬프트 해시 → 민감 가능·CLAUDE.md 보안).
  - 타임아웃은 시임이 아니라 **실물 redis-py 객체**의 connection_kwargs로 확인한다
    (CLAUDE.md: 외부 SDK 표면을 가짜 테스트만으로 정합 선언 금지).

설계 정본: docs/architecture/03a_l3_router_design.md §F.1(캐시 키 의미),
docs/standards/incident_response_slo.md 함정 ④(Redis 장애의 학생 경로 전파).
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from typing import Any

import pytest
from whymath_backend.l3.cache import RedisCache
from whymath_backend.l3.cache.redis_cache import (
    CacheDegradationCounter,
    _decode,
    _RedisClient,
    cache_degradation_snapshot,
    reset_cache_degradation,
)

# 강등 로그를 내는 실제 모듈 로거 — caplog는 이 이름으로 잡는다(프로덕션 경로 그대로 검증).
_CACHE_LOGGER = "whymath_backend.l3.cache.redis_cache"


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


class CacheBoomError(RuntimeError):
    """테스트 전용 커스텀 예외 — 로그 단정의 *변별력*을 만드는 장치.

    이름이 프로덕션 코드 어디에도 없으므로, caplog에서 "CacheBoomError"가 발견된다는 것은
    구현이 `type(exc).__name__`을 실제로 실었다는 뜻이다(무타입 경고면 발견되지 않는다).
    """


class ExplodingRedisClient:
    """죽은 Redis 모사 — get/set이 즉시 예외를 던진다(`_RedisClient` 구조적 충족).

    `explode_get`/`explode_set`을 따로 끌 수 있어 "get만 죽은" 부분 장애도 모사한다.
    호출 기록을 남겨 '가드가 호출 자체를 건너뛴 것'과 '호출했지만 흡수한 것'을 구분한다.
    """

    def __init__(
        self,
        *,
        exc: Exception | None = None,
        explode_get: bool = True,
        explode_set: bool = True,
    ) -> None:
        self._exc = exc if exc is not None else CacheBoomError("redis 연결 실패(모사)")
        self._explode_get = explode_get
        self._explode_set = explode_set
        self.get_calls: list[str] = []
        self.set_calls: list[tuple[str, str, int | None]] = []

    async def get(self, name: str) -> Any:
        self.get_calls.append(name)
        if self._explode_get:
            raise self._exc
        return None

    async def set(self, name: str, value: str, *, ex: int | None = None) -> Any:
        self.set_calls.append((name, value, ex))
        if self._explode_set:
            raise self._exc
        return True

    async def ping(self) -> Any:
        raise self._exc


@pytest.fixture(autouse=True)
def _isolate_process_degradation() -> Iterator[None]:
    """프로세스 전역 강등 회계를 테스트마다 초기화 — 전역 상태 누수 차단.

    기본 `RedisCache(...)`는 전역 카운터를 쓰므로, 초기화 없이는 앞 테스트의 실패가 뒤
    테스트의 단정을 오염시킨다(테스트 순서 의존 = 위장된 통과).
    """
    reset_cache_degradation()
    yield
    reset_cache_degradation()


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


# ──────────────────────────────────────────────────────────────────────────
# OPS-05 — 장애 강등(get→미스·set→no-op) + 침묵 실패 금지 + 인프로세스 회계
# ──────────────────────────────────────────────────────────────────────────
class TestGetDegradesToMiss:
    """get 실패 = 캐시 미스 강등 — 학생 대면 경로가 깨지지 않는다."""

    async def test_get_returns_none_instead_of_raising(self) -> None:
        """폭발하는 클라이언트에서도 get은 예외를 던지지 않고 None(미스)을 준다."""
        counter = CacheDegradationCounter()
        cache = RedisCache(client=ExplodingRedisClient(), degradation=counter)

        # pytest.raises로 감싸지 않는다 — 예외가 새면 이 줄에서 테스트가 그대로 실패한다.
        assert await cache.get("어떤키") is None

    async def test_get_failure_logs_exception_type_name(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """흡수 로그에 *커스텀 예외 타입명*이 실린다(무타입 경고면 이 단정이 깨진다)."""
        cache = RedisCache(client=ExplodingRedisClient(), degradation=CacheDegradationCounter())

        with caplog.at_level(logging.WARNING, logger=_CACHE_LOGGER):
            await cache.get("어떤키")

        # 변별력의 핵심: 프로덕션 코드 어디에도 없는 이름이 로그에 있어야 한다.
        assert "CacheBoomError" in caplog.text
        # 어떤 연산이 강등됐는지도 남아야 진단이 된다(운영 런북이 읽는 축).
        assert "operation=get" in caplog.text
        assert any(record.levelno == logging.WARNING for record in caplog.records)

    async def test_get_failure_does_not_log_key(self, caplog: pytest.LogCaptureFixture) -> None:
        """캐시 키는 로그에 남기지 않는다 — 키는 프롬프트 해시라 민감할 수 있다(CLAUDE.md)."""
        sensitive_key = "local:qwen:프롬프트해시_민감값_ABCDEF"
        cache = RedisCache(client=ExplodingRedisClient(), degradation=CacheDegradationCounter())

        with caplog.at_level(logging.DEBUG, logger=_CACHE_LOGGER):
            await cache.get(sensitive_key)

        assert sensitive_key not in caplog.text
        assert "프롬프트해시_민감값_ABCDEF" not in caplog.text

    async def test_get_failure_from_client_construction_also_degrades(self) -> None:
        """클라이언트 *생성* 실패(잘못된 redis_url 등)도 같은 강등으로 흡수된다.

        try 범위가 지연 생성까지 덮는지 확인 — 덮지 않으면 첫 요청이 5xx가 된다.
        """
        from whymath_backend.config import Settings

        counter = CacheDegradationCounter()
        # 스킴이 redis/rediss/unix가 아니면 redis-py가 생성 시점에 거부한다.
        cache = RedisCache(
            settings=Settings(redis_url="http://잘못된-스킴:1/0"), degradation=counter
        )

        assert await cache.get("k") is None
        assert counter.snapshot().get_failures == 1


class TestSetDegradesToNoop:
    """set 실패 = no-op 강등 — best-effort 적재가 응답을 죽이지 않는다."""

    async def test_set_failure_does_not_propagate(self) -> None:
        counter = CacheDegradationCounter()
        client = ExplodingRedisClient()
        cache = RedisCache(client=client, degradation=counter)

        await cache.set("어떤키", "생성된 응답", ttl_seconds=60)  # 예외가 새면 여기서 실패

        # 호출은 *시도*됐다(가드가 조용히 건너뛴 게 아니라 흡수한 것).
        assert len(client.set_calls) == 1
        assert counter.snapshot().set_failures == 1

    async def test_set_failure_logs_exception_type_name(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        cache = RedisCache(client=ExplodingRedisClient(), degradation=CacheDegradationCounter())

        with caplog.at_level(logging.WARNING, logger=_CACHE_LOGGER):
            await cache.set("k", "v", ttl_seconds=60)

        assert "CacheBoomError" in caplog.text
        assert "operation=set" in caplog.text

    async def test_set_failure_does_not_log_value(self, caplog: pytest.LogCaptureFixture) -> None:
        """저장 값(검증 전 원시 생성물)도 로그에 남기지 않는다."""
        cache = RedisCache(client=ExplodingRedisClient(), degradation=CacheDegradationCounter())

        with caplog.at_level(logging.DEBUG, logger=_CACHE_LOGGER):
            await cache.set("k", "학생에게 갈 원시 생성물 XYZZY", ttl_seconds=60)

        assert "XYZZY" not in caplog.text


class TestHealthyPathUnchanged:
    """양성 대조 — 가드가 정상 경로를 바꾸지 않는다(회귀 동결)."""

    async def test_normal_get_set_still_work(self) -> None:
        counter = CacheDegradationCounter()
        client = FakeRedisClient()
        cache = RedisCache(client=client, degradation=counter)

        await cache.set("k", "정상값", ttl_seconds=120)
        assert await cache.get("k") == "정상값"
        # 기존 계약 그대로: ex가 전달되고, 미스는 None이다.
        assert client.set_calls == [("k", "정상값", 120)]
        assert await cache.get("없는키") is None

    async def test_healthy_path_never_increments_counter(self) -> None:
        """정상 동작에서는 강등 계수가 오르지 않는다 — 카운터가 항상 증가하면 무의미하다."""
        counter = CacheDegradationCounter()
        cache = RedisCache(client=FakeRedisClient(), degradation=counter)

        await cache.set("k", "v", ttl_seconds=60)
        await cache.get("k")
        await cache.get("없는키")

        snapshot = counter.snapshot()
        assert snapshot.total_failures == 0
        assert snapshot.degraded is False
        assert snapshot.last_error_type is None
        assert cache.degradation_count == 0

    async def test_healthy_path_logs_no_warning(self, caplog: pytest.LogCaptureFixture) -> None:
        """정상 경로는 warning을 남기지 않는다(경고 인플레이션 방지)."""
        cache = RedisCache(client=FakeRedisClient(), degradation=CacheDegradationCounter())

        with caplog.at_level(logging.WARNING, logger=_CACHE_LOGGER):
            await cache.set("k", "v", ttl_seconds=60)
            await cache.get("k")

        assert [r for r in caplog.records if r.levelno >= logging.WARNING] == []

    async def test_partial_outage_counts_only_failing_operation(self) -> None:
        """get만 죽은 부분 장애 — 실패한 연산만 계수된다(연산별 분해가 실제로 작동)."""
        counter = CacheDegradationCounter()
        cache = RedisCache(
            client=ExplodingRedisClient(explode_get=True, explode_set=False),
            degradation=counter,
        )

        assert await cache.get("k") is None
        await cache.set("k", "v", ttl_seconds=60)

        snapshot = counter.snapshot()
        assert (snapshot.get_failures, snapshot.set_failures) == (1, 0)
        # set 성공이 마지막 관측이므로 '지금 강등 중' 플래그는 내려간다.
        assert snapshot.degraded is False


class TestDegradationCounter:
    """강등 회계·로그 정책 단위 검증 — 인프로세스 이중 회계 축."""

    def test_snapshot_totals_and_last_error_type(self) -> None:
        counter = CacheDegradationCounter()
        counter.record_failure("get", CacheBoomError("x"))
        counter.record_failure("set", TimeoutError("y"))

        snapshot = counter.snapshot()
        assert (snapshot.get_failures, snapshot.set_failures) == (1, 1)
        assert snapshot.total_failures == 2
        # 마지막 예외 타입만 남는다(값·메시지는 담지 않는다).
        assert snapshot.last_error_type == "TimeoutError"
        assert snapshot.degraded is True

    def test_first_failure_logs_then_suppressed_until_threshold(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """전이(첫 실패)만 warning, 이후 N번째까지 억제 — 장애 중 매 요청 로그 스팸 방지."""
        counter = CacheDegradationCounter(log_every_n_failures=5)

        with caplog.at_level(logging.WARNING, logger=_CACHE_LOGGER):
            for _ in range(5):
                counter.record_failure("get", CacheBoomError("boom"))

        warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
        # 1번째(전이) + 5번째(지속 알림) = 2건. 억제가 없으면 5건이라 이 단정이 깨진다.
        assert len(warnings) == 2

    def test_recovery_then_new_outage_logs_again(self, caplog: pytest.LogCaptureFixture) -> None:
        """해소 후 재장애는 다시 warning — 억제가 새 사건을 삼키지 않는다."""
        counter = CacheDegradationCounter(log_every_n_failures=100)

        with caplog.at_level(logging.INFO, logger=_CACHE_LOGGER):
            counter.record_failure("get", CacheBoomError("boom"))  # 전이 warning
            counter.record_success()  # 해소 info
            counter.record_failure("get", CacheBoomError("boom"))  # 재전이 warning

        warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
        infos = [r for r in caplog.records if r.levelno == logging.INFO]
        assert len(warnings) == 2
        assert len(infos) == 1
        assert "해소" in infos[0].getMessage()

    def test_success_clears_degraded_flag_but_keeps_totals(self) -> None:
        """복구는 '지금 강등 중'만 내린다 — 누적 실패는 지워지지 않는다(사건 은폐 금지)."""
        counter = CacheDegradationCounter()
        counter.record_failure("get", CacheBoomError("boom"))
        counter.record_success()

        snapshot = counter.snapshot()
        assert snapshot.degraded is False
        assert snapshot.total_failures == 1
        assert snapshot.last_error_type == "CacheBoomError"

    def test_log_every_n_clamped_to_at_least_one(self, caplog: pytest.LogCaptureFixture) -> None:
        """0/음수 설정도 0 나눗셈 없이 동작한다(설정 실수 방어)."""
        counter = CacheDegradationCounter(log_every_n_failures=0)

        with caplog.at_level(logging.WARNING, logger=_CACHE_LOGGER):
            counter.record_failure("get", CacheBoomError("boom"))
            counter.record_failure("get", CacheBoomError("boom"))

        assert len([r for r in caplog.records if r.levelno == logging.WARNING]) == 2

    async def test_process_wide_counter_is_default(self) -> None:
        """카운터 미주입 시 프로세스 전역 회계에 합산된다 — SaaS 없이 읽는 판정치."""
        assert cache_degradation_snapshot().total_failures == 0  # autouse fixture가 초기화

        cache_a = RedisCache(client=ExplodingRedisClient())
        cache_b = RedisCache(client=ExplodingRedisClient())
        await cache_a.get("k")
        await cache_b.set("k", "v", ttl_seconds=60)

        # 인스턴스가 둘이어도 프로세스 회계는 하나로 합산된다(운영 판정 단위 = 프로세스).
        snapshot = cache_degradation_snapshot()
        assert snapshot.get_failures == 1
        assert snapshot.set_failures == 1
        assert snapshot.total_failures == 2


class TestSocketTimeout:
    """무응답 Redis 방어 — 실물 redis-py 객체에 타임아웃이 실제로 전달되는지 확인.

    시임이 아니라 진짜 `redis.asyncio.Redis`를 만들어 connection_kwargs를 읽는다
    (CLAUDE.md: 외부 SDK 표면을 가짜 테스트만으로 정합 선언 금지). 네트워크는 타지 않는다
    — from_url은 연결 풀만 구성한다.
    """

    def test_default_client_receives_both_timeouts(self) -> None:
        from whymath_backend.config import Settings

        settings = Settings(redis_url="redis://127.0.0.1:6379/0", redis_socket_timeout_s=2.0)
        cache = RedisCache(settings=settings)
        client = cache._get_client()

        kwargs = client.connection_pool.connection_kwargs  # type: ignore[attr-defined]
        # 변별력: 인자를 넘기지 *않으면* redis-py는 이 키들을 아예 넣지 않는다(8.0.1 실측)
        # → 아래 두 단정은 가드 제거 시 KeyError/실패로 즉시 깨진다.
        assert kwargs["socket_timeout"] == 2.0
        assert kwargs["socket_connect_timeout"] == 2.0

    def test_timeout_value_follows_settings(self) -> None:
        """설정값이 그대로 반영된다 — 하드코딩이 아니라 운영이 조절 가능한 축."""
        from whymath_backend.config import Settings

        cache = RedisCache(settings=Settings(redis_socket_timeout_s=0.25))
        kwargs = cache._get_client().connection_pool.connection_kwargs  # type: ignore[attr-defined]
        assert kwargs["socket_timeout"] == 0.25
        assert kwargs["socket_connect_timeout"] == 0.25

    def test_effective_connection_carries_timeout(self) -> None:
        """풀이 만드는 *실제 Connection*에 값이 실린다(kwargs만 맞고 무효인 경우 배제)."""
        from whymath_backend.config import Settings

        cache = RedisCache(settings=Settings(redis_socket_timeout_s=1.5))
        conn = cache._get_client().connection_pool.make_connection()  # type: ignore[attr-defined]
        assert conn.socket_timeout == 1.5
        assert conn.socket_connect_timeout == 1.5

    def test_settings_rejects_nonpositive_timeout(self) -> None:
        """0·음수 타임아웃은 설정 단계에서 거부한다(무한 대기로의 우회 차단)."""
        import pydantic
        from whymath_backend.config import Settings

        with pytest.raises(pydantic.ValidationError):
            Settings(redis_socket_timeout_s=0)


class TestPipelineSurvivesRedisOutage:
    """이 태스크의 진짜 목적 — Redis가 죽어도 학생 대면 생성 경로가 완주한다.

    OPS-04 발견: `/health/ready`는 Redis를 `required=false`(강등)로 *보고*하는데, 실제로는
    `l3/pipeline.generate`의 `cache.get`이 터져 5xx가 났다(정책 ≠ 동작). 이 테스트가 그
    간극을 동결한다(`docs/standards/incident_response_slo.md` 함정 ④).
    """

    async def test_generate_completes_when_redis_is_dead(self) -> None:
        from whymath_backend.l3.interfaces import RecordingTraceSink
        from whymath_backend.l3.models import GenerationResult as ProviderResult
        from whymath_backend.l3.models import RoutingDecision, RoutingRequest
        from whymath_backend.l3.pipeline import generate

        class RecordingProvider:
            """가짜 LLMProvider — 캐시가 죽어도 생성이 호출되는지 확인용."""

            def __init__(self) -> None:
                self.calls: list[tuple[str, str, RoutingDecision]] = []

            async def generate(
                self, prompt: str, system: str, decision: RoutingDecision
            ) -> ProviderResult:
                self.calls.append((prompt, system, decision))
                return ProviderResult("정상 생성물")

        counter = CacheDegradationCounter()
        provider = RecordingProvider()
        dead_cache = RedisCache(client=ExplodingRedisClient(), degradation=counter)

        result = await generate(
            RoutingRequest(
                task_type="explain",
                difficulty="easy",
                requires_reasoning=False,
                student_subscription="free",
                sync=True,
            ),
            "학생 질문",
            "시스템",
            provider=provider,
            cache=dead_cache,
            trace=RecordingTraceSink(),
            cache_ttl_s=60,
        )

        # 학생은 서비스를 받는다 — 예외(→ 5xx)가 아니라 정상 생성 응답.
        assert result.text == "정상 생성물"
        assert result.cache_hit is False
        assert len(provider.calls) == 1
        # 그리고 그 사실이 회계에 남는다: get 미스 강등 1 + set 적재 실패 1.
        snapshot = counter.snapshot()
        assert (snapshot.get_failures, snapshot.set_failures) == (1, 1)
        assert snapshot.last_error_type == "CacheBoomError"
