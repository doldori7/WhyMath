"""OPS-06 — api 계층 Redis 소비처 2곳의 장애 강등·소켓 타임아웃 동결 (hermetic).

이 파일이 막는 것
-----------------
OPS-05는 Redis 클라이언트 생성 지점 **3곳 중 1곳**(`l3/cache/redis_cache.py`)만 닫았다.
나머지 둘 — `api/_device_store.py`의 verify/count 캐시, `api/_rate_limit.py`의 RedisBackend —
은 무가드·무타임아웃이라 Redis가 죽으면 학생 대면 요청이 5xx가 됐다
(`docs/standards/incident_response_slo.md` 함정 ④). 이 테스트가 그 간극을 동결한다.

**강등 판정이 연산마다 다르다는 것**이 이 태스크의 핵심이고, 그래서 테스트도 두 방향을
동시에 못 박는다:
  - 조회·적재(`get`/`setex`/`hit`)는 **흡수**한다 → 예외가 새면 실패하는 테스트.
  - 무효화(`delete`)는 **절대 흡수하지 않는다** → 예외가 새지 *않으면* 실패하는 테스트
    (`TestRevokedDeviceMustNotSurviveInCache` — 조용히 삼키도록 코드를 바꾸면 깨진다).

파일을 새로 두는 이유: 대상이 두 모듈에 걸쳐 있고(device store + rate limit) 주제가 하나
(Redis 강등)라, 3,300줄짜리 `test_devices.py`와 2,300줄짜리 `test_coach.py`에 절반씩
흩뿌리면 계약이 읽히지 않는다. 스타일(한국어 docstring·가짜 클라이언트 시임·caplog 타입명
단정·변별력 주석)은 두 파일과 `tests/backend/l3/test_redis_cache.py`를 그대로 따른다.
"""

from __future__ import annotations

import asyncio
import hmac
import logging
import uuid
from collections.abc import Iterator
from hashlib import sha256
from typing import Any

import pytest
from pydantic import SecretStr

from whymath_backend.api._degradation import DegradationCounter
from whymath_backend.api._device_store import (
    CachedDeviceStore,
    DeviceCredentialStore,
    InMemoryDeviceStore,
    _build_redis_for_cache,
    build_device_store_from_settings,
    device_cache_degradation_snapshot,
    reset_device_cache_degradation,
)
from whymath_backend.api._rate_limit import (
    _LUA_HIT_MANY_SHA1,
    InMemoryBackend,
    RedisBackend,
    Subject,
    _build_default_redis_client,
    rate_limit_degradation_snapshot,
    reset_rate_limit_degradation,
)
from whymath_backend.config import Settings

# 강등 로그를 내는 실제 모듈 로거 — caplog는 이 이름으로 잡는다(프로덕션 경로 그대로 검증).
_DEGRADATION_LOGGER = "whymath_backend.api._degradation"

_UID = uuid.uuid4()


def _sign(secret: str, device_id: str) -> str:
    """HMAC-SHA256(secret, device_id) hex digest — store가 verify에서 재계산하는 식."""
    return hmac.new(secret.encode("utf-8"), device_id.encode("utf-8"), sha256).hexdigest()


def _settings(**overrides: Any) -> Settings:
    """테스트용 Settings — jwt secret만 채우고 나머지는 기본값(hermetic)."""
    return Settings(jwt_secret_key=SecretStr("test-secret-0123456789abcdef"), **overrides)


@pytest.fixture(autouse=True)
def _isolate_process_degradation() -> Iterator[None]:
    """프로세스 전역 강등 회계를 테스트마다 초기화 — 전역 상태 누수 차단.

    기본 생성자는 전역 카운터를 쓰므로, 초기화 없이는 앞 테스트의 실패가 뒤 테스트의 단정을
    오염시킨다(테스트 순서 의존 = 위장된 통과).
    """
    reset_device_cache_degradation()
    reset_rate_limit_degradation()
    yield
    reset_device_cache_degradation()
    reset_rate_limit_degradation()


# ══════════════════════════════════════════════════════════════════════════
# 1) device store — 가짜 캐시 클라이언트 시임
# ══════════════════════════════════════════════════════════════════════════
class DeviceCacheBoomError(RuntimeError):
    """폭발용 커스텀 예외 — 프로덕션 코드 어디에도 없는 이름이라 로그 단정의 변별력이 된다."""


class _WorkingCache:
    """정상 동작 캐시 — 인메모리 dict + 호출 횟수(양성 대조용). `_CacheClient` 구조 충족."""

    def __init__(self) -> None:
        self.store: dict[str, str] = {}
        self.ttls: dict[str, int] = {}
        self.get_calls = 0
        self.setex_calls = 0
        self.delete_calls = 0

    async def get(self, key: str) -> str | None:
        self.get_calls += 1
        return self.store.get(key)

    async def setex(self, key: str, seconds: int, value: str) -> None:
        self.setex_calls += 1
        self.store[key] = value
        self.ttls[key] = seconds

    async def delete(self, *keys: str) -> int:
        self.delete_calls += 1
        removed = 0
        for key in keys:
            if self.store.pop(key, None) is not None:
                self.ttls.pop(key, None)
                removed += 1
        return removed

    async def ping(self) -> bool:
        return True


class _ExplodingCache(_WorkingCache):
    """지정한 연산만 폭발하는 캐시 — 나머지는 정상 동작(연산별 판정을 따로 검증하기 위함).

    `fail_first_n_deletes`는 *일시적* DEL 실패(재시도로 흡수되는 깜빡임)를 재현한다.
    """

    def __init__(
        self,
        *,
        explode: frozenset[str] = frozenset(),
        fail_first_n_deletes: int = 0,
    ) -> None:
        super().__init__()
        self._explode = explode
        self._remaining_delete_failures = fail_first_n_deletes

    async def get(self, key: str) -> str | None:
        self.get_calls += 1
        if "get" in self._explode:
            raise DeviceCacheBoomError("redis get 폭발")
        return self.store.get(key)

    async def setex(self, key: str, seconds: int, value: str) -> None:
        self.setex_calls += 1
        if "setex" in self._explode:
            raise DeviceCacheBoomError("redis setex 폭발")
        await super().setex(key, seconds, value)

    async def delete(self, *keys: str) -> int:
        if "delete" in self._explode:
            self.delete_calls += 1
            raise DeviceCacheBoomError("redis delete 폭발")
        if self._remaining_delete_failures > 0:
            self._remaining_delete_failures -= 1
            self.delete_calls += 1
            raise DeviceCacheBoomError("redis delete 일시 폭발")
        return await super().delete(*keys)


class _CountingInner:
    """`DeviceCredentialStore` 위임 래퍼 — DB 폴백이 *실제로* 일어났는지 세는 축."""

    def __init__(self, inner: InMemoryDeviceStore) -> None:
        self._inner = inner
        self.verify_calls = 0
        self.count_calls = 0

    async def register(self, user_id: uuid.UUID) -> tuple[str, str]:
        return await self._inner.register(user_id)

    async def verify(self, device_id: str, signature_hex: str) -> bool:
        self.verify_calls += 1
        return await self._inner.verify(device_id, signature_hex)

    async def revoke(self, device_id: str, owner_id: uuid.UUID) -> bool:
        return await self._inner.revoke(device_id, owner_id)

    async def list_for_user(self, owner_id: uuid.UUID, **kwargs: Any) -> Any:
        return await self._inner.list_for_user(owner_id, **kwargs)

    async def count_for_user(self, owner_id: uuid.UUID, **kwargs: Any) -> int:
        self.count_calls += 1
        return await self._inner.count_for_user(owner_id, **kwargs)

    async def cleanup_stale(self, max_age_days: int, *, dry_run: bool = False) -> list[str]:
        return await self._inner.cleanup_stale(max_age_days, dry_run=dry_run)


async def _registered_store(
    cache: _WorkingCache,
    *,
    counter: DegradationCounter | None = None,
    **kwargs: Any,
) -> tuple[CachedDeviceStore, _CountingInner, str, str]:
    """(store, inner, device_id, signature) — 등록까지 끝난 상태를 만든다.

    등록은 *정상 캐시*로 수행한다(등록 경로의 DEL 실패는 별도 테스트에서 다룬다).
    """
    real_inner = InMemoryDeviceStore()
    device_id, secret_plain = await real_inner.register(_UID)
    inner = _CountingInner(real_inner)
    store = CachedDeviceStore(
        inner,
        cache,
        ttl_seconds=60,
        degradation=counter if counter is not None else DegradationCounter("테스트"),
        invalidate_backoff_seconds=0.0,
        **kwargs,
    )
    return store, inner, device_id, _sign(secret_plain, device_id)


# ══════════════════════════════════════════════════════════════════════════
# 2) device store — get/setex는 강등, DB가 학생을 구한다
# ══════════════════════════════════════════════════════════════════════════
class TestDeviceCacheGetDegradesToDbFallback:
    """캐시 GET 실패 = 미스 강등 — 인증 검증은 DB로 계속된다(승인이 느슨해지지 않는다)."""

    async def test_verify_still_succeeds_via_db_when_get_explodes(self) -> None:
        counter = DegradationCounter("테스트")
        cache = _ExplodingCache(explode=frozenset({"get"}))
        store, inner, device_id, sig = await _registered_store(cache, counter=counter)

        # pytest.raises로 감싸지 않는다 — 예외가 새면 이 줄에서 테스트가 그대로 실패한다.
        assert await store.verify(device_id, sig) is True
        # 그리고 그것은 캐시가 아니라 *DB 검증*의 결과여야 한다.
        assert inner.verify_calls == 1
        assert counter.snapshot().failures_for("get") == 1

    async def test_wrong_signature_still_rejected_during_outage(self) -> None:
        """강등이 검증을 *느슨하게* 만들지 않는다 — 잘못된 서명은 여전히 False."""
        cache = _ExplodingCache(explode=frozenset({"get"}))
        store, _inner, device_id, _sig = await _registered_store(cache)

        assert await store.verify(device_id, "0" * 64) is False

    async def test_get_failure_logs_exception_type_name(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """흡수 로그에 *커스텀 예외 타입명*이 실린다(무타입 경고면 이 단정이 깨진다)."""
        cache = _ExplodingCache(explode=frozenset({"get"}))
        store, _inner, device_id, sig = await _registered_store(cache)

        with caplog.at_level(logging.WARNING, logger=_DEGRADATION_LOGGER):
            await store.verify(device_id, sig)

        assert "DeviceCacheBoomError" in caplog.text
        assert "operation=get" in caplog.text
        assert any(record.levelno == logging.WARNING for record in caplog.records)

    async def test_get_failure_does_not_log_device_id(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """캐시 키에는 device_id가 들어간다 — 로그에 남기지 않는다(미성년자 PII 인접 표면)."""
        cache = _ExplodingCache(explode=frozenset({"get"}))
        store, _inner, device_id, sig = await _registered_store(cache)

        with caplog.at_level(logging.DEBUG, logger=_DEGRADATION_LOGGER):
            await store.verify(device_id, sig)

        assert device_id not in caplog.text
        assert sig not in caplog.text  # 디바이스 서명도 로그 금지

    async def test_count_for_user_falls_back_to_db_when_get_explodes(self) -> None:
        counter = DegradationCounter("테스트")
        cache = _ExplodingCache(explode=frozenset({"get"}))
        store, inner, _device_id, _sig = await _registered_store(cache, counter=counter)

        assert await store.count_for_user(_UID) == 1
        assert inner.count_calls == 1
        assert counter.snapshot().failures_for("get") == 1

    async def test_corrupted_count_value_degrades_to_miss(self) -> None:
        """캐시에 정수 아닌 값이 들어 있어도 5xx가 아니라 DB 재조회로 간다."""
        counter = DegradationCounter("테스트")
        cache = _WorkingCache()
        store, inner, _device_id, _sig = await _registered_store(cache, counter=counter)
        cache.store[f"device_count:{_UID}:active"] = "손상된값"

        assert await store.count_for_user(_UID) == 1
        assert inner.count_calls == 1
        # 침묵하지 않는다 — 파싱 실패의 예외 타입이 회계에 남는다.
        assert counter.snapshot().last_error_type == "ValueError"


class TestDeviceCacheSetexDegradesToNoop:
    """캐시 적재 실패 = no-op 강등 — 이미 검증에 성공한 요청을 죽이지 않는다."""

    async def test_setex_failure_does_not_propagate(self) -> None:
        counter = DegradationCounter("테스트")
        cache = _ExplodingCache(explode=frozenset({"setex"}))
        store, _inner, device_id, sig = await _registered_store(cache, counter=counter)

        assert await store.verify(device_id, sig) is True  # 예외가 새면 여기서 실패

        # 호출은 *시도*됐다(가드가 조용히 건너뛴 게 아니라 흡수한 것).
        assert cache.setex_calls == 1
        assert counter.snapshot().failures_for("setex") == 1

    async def test_setex_failure_logs_exception_type_name(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        cache = _ExplodingCache(explode=frozenset({"setex"}))
        store, _inner, device_id, sig = await _registered_store(cache)

        with caplog.at_level(logging.WARNING, logger=_DEGRADATION_LOGGER):
            await store.verify(device_id, sig)

        assert "DeviceCacheBoomError" in caplog.text
        assert "operation=setex" in caplog.text


# ══════════════════════════════════════════════════════════════════════════
# 3) device store — 무효화(DEL)는 강등 금지 (보안 계약)
# ══════════════════════════════════════════════════════════════════════════
class TestDeviceCacheDeleteIsNeverSilentlyDegraded:
    """DEL 실패는 **전파**된다 — 조용히 삼키면 폐기가 폐기되지 않는다."""

    async def test_revoke_propagates_delete_failure(self) -> None:
        cache = _ExplodingCache(explode=frozenset({"delete"}))
        store, _inner, device_id, sig = await _registered_store(cache)
        await store.verify(device_id, sig)  # 캐시 warm

        with pytest.raises(DeviceCacheBoomError):
            await store.revoke(device_id, _UID)

    async def test_register_propagates_delete_failure(self) -> None:
        """register의 count 캐시 무효화도 현행 fail-loud 유지(동작 변경 없음·재시도만 추가)."""
        cache = _ExplodingCache(explode=frozenset({"delete"}))
        inner = _CountingInner(InMemoryDeviceStore())
        store = CachedDeviceStore(
            inner,
            cache,
            ttl_seconds=60,
            degradation=DegradationCounter("테스트"),
            invalidate_backoff_seconds=0.0,
        )

        with pytest.raises(DeviceCacheBoomError):
            await store.register(_UID)

    async def test_cleanup_stale_propagates_delete_failure(self) -> None:
        """배치 폐기도 같은 보안 계약 — 여기만 삼키면 배치 경로에 stale 승인이 남는다."""
        cache = _ExplodingCache(explode=frozenset({"delete"}))
        store, _inner, _device_id, _sig = await _registered_store(cache)

        with pytest.raises(DeviceCacheBoomError):
            await store.cleanup_stale(0)

    async def test_delete_failure_is_retried_before_raising(self) -> None:
        """강등 대신 *복원력*만 추가했다 — 유한 재시도 후 그래도 실패하면 전파."""
        cache = _ExplodingCache(explode=frozenset({"delete"}))
        store, _inner, device_id, _sig = await _registered_store(
            cache, invalidate_max_retries=3, invalidate_timeout_seconds=1.0
        )

        with pytest.raises(DeviceCacheBoomError):
            await store.revoke(device_id, _UID)

        assert cache.delete_calls == 3  # 무한 재시도도, 단발 포기도 아니다

    async def test_transient_delete_failure_is_absorbed_by_retry(self) -> None:
        """일시적 깜빡임은 재시도로 흡수 — 성공하면 캐시가 실제로 비워진다."""
        counter = DegradationCounter("테스트")
        cache = _ExplodingCache(fail_first_n_deletes=1)
        store, _inner, device_id, sig = await _registered_store(
            cache, counter=counter, invalidate_max_retries=3, invalidate_timeout_seconds=1.0
        )
        await store.verify(device_id, sig)  # 캐시 warm
        assert f"device_verify:{device_id}" in cache.store

        assert await store.revoke(device_id, _UID) is True
        assert f"device_verify:{device_id}" not in cache.store
        # 재시도로 성공했으므로 *강등 회계에는 잡히지 않는다*(실패가 아니라 복원).
        assert counter.snapshot().failures_for("delete") == 0

    async def test_delete_failure_logs_error_level_with_exception_type(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """전파하는 실패는 ERROR — 흡수하는 강등(WARNING)과 심각도가 다르다."""
        cache = _ExplodingCache(explode=frozenset({"delete"}))
        store, _inner, device_id, sig = await _registered_store(cache)
        await store.verify(device_id, sig)

        with caplog.at_level(logging.WARNING, logger=_DEGRADATION_LOGGER):
            with pytest.raises(DeviceCacheBoomError):
                await store.revoke(device_id, _UID)

        assert "DeviceCacheBoomError" in caplog.text
        assert "operation=delete" in caplog.text
        assert any(record.levelno == logging.ERROR for record in caplog.records)


class TestRevokedDeviceMustNotSurviveInCache:
    """**보안 회귀 동결** — "revoke 후 캐시가 안 지워지면 폐기된 디바이스가 통과한다".

    이 클래스가 증명하는 인과는 두 줄이다:
      1. 무효화가 안 된 상태에서 stale 캐시는 *실제로* 통과를 만든다(DB는 이미 폐기했는데도).
      2. 따라서 DEL 실패를 조용히 삼키면 안 된다 — 지금 그 유일한 방어선은 **전파되는 예외**다.

    `_cache_invalidate`를 no-op으로 바꾸거나 `except: pass`로 삼키면 이 테스트가 깨진다.
    """

    async def test_stale_cache_authenticates_revoked_device_so_del_must_not_be_swallowed(
        self,
    ) -> None:
        cache = _ExplodingCache(explode=frozenset({"delete"}))
        store, inner, device_id, sig = await _registered_store(cache)
        assert await store.verify(device_id, sig) is True  # 캐시 warm

        # ① 폐기를 시도한다 — DB는 폐기되지만 캐시 무효화는 실패한다.
        with pytest.raises(DeviceCacheBoomError):
            await store.revoke(device_id, _UID)

        # ② DB(권위)는 이미 이 디바이스를 거부한다.
        assert await inner.verify(device_id, sig) is False
        # ③ 그런데 캐시에는 과거의 승인이 남아 있고 —
        assert cache.store[f"device_verify:{device_id}"] == sig.lower()
        # ④ 그 캐시를 읽는 verify는 **True를 돌려준다**(= 폐기된 디바이스가 통과한다).
        #    즉 ①의 예외가 사라지면 이 상태가 *조용히* 성립한다. 그래서 강등 금지다.
        assert await store.verify(device_id, sig) is True

    async def test_healthy_revoke_actually_stops_the_device(self) -> None:
        """양성 대조 — 정상 Redis에서는 폐기가 즉시 효력을 갖는다(캐시 hit가 사라진다)."""
        cache = _WorkingCache()
        store, _inner, device_id, sig = await _registered_store(cache)
        await store.verify(device_id, sig)

        assert await store.revoke(device_id, _UID) is True
        assert f"device_verify:{device_id}" not in cache.store
        assert await store.verify(device_id, sig) is False


# ══════════════════════════════════════════════════════════════════════════
# 4) device store — 양성 대조(가드가 정상 경로를 바꾸지 않는다)
# ══════════════════════════════════════════════════════════════════════════
class TestDeviceCacheHealthyPathUnchanged:
    """회귀 동결 — 캐시 hit·상수시간 비교·실패 비캐시가 그대로다."""

    async def test_cache_hit_skips_db(self) -> None:
        cache = _WorkingCache()
        store, inner, device_id, sig = await _registered_store(cache)
        await store.verify(device_id, sig)  # warm(DB 1회)

        assert await store.verify(device_id, sig) is True
        assert inner.verify_calls == 1  # 두 번째는 DB 왕복 0

    async def test_invalid_signature_falls_through_and_is_not_cached(self) -> None:
        """캐시 hit 경로의 상수시간 비교 유지 — 불일치는 DB 위임, 실패는 캐시 안 함."""
        cache = _WorkingCache()
        store, inner, device_id, sig = await _registered_store(cache)
        await store.verify(device_id, sig)  # warm
        setex_before = cache.setex_calls

        assert await store.verify(device_id, "0" * 64) is False
        assert inner.verify_calls == 2  # 불일치는 DB로 내려간다
        assert cache.setex_calls == setex_before  # 실패는 캐시에 자리를 못 잡는다

    async def test_bytes_response_still_decoded(self) -> None:
        """decode_responses=False 클라이언트(bytes 반환)도 캐시 hit로 인정된다."""
        cache = _WorkingCache()
        store, inner, device_id, sig = await _registered_store(cache)
        await store.verify(device_id, sig)
        # 실코드의 bytes 분기 검증 — 캐시에 bytes를 직접 주입
        cache.store[f"device_verify:{device_id}"] = sig.lower().encode("utf-8")  # type: ignore[assignment]

        assert await store.verify(device_id, sig) is True
        assert inner.verify_calls == 1  # DB로 내려가지 않았다 = 캐시 hit

    async def test_healthy_path_records_no_degradation(self) -> None:
        counter = DegradationCounter("테스트")
        cache = _WorkingCache()
        store, _inner, device_id, sig = await _registered_store(cache, counter=counter)

        await store.verify(device_id, sig)
        await store.verify(device_id, sig)
        await store.count_for_user(_UID)
        await store.revoke(device_id, _UID)

        snapshot = counter.snapshot()
        assert snapshot.total_failures == 0
        assert snapshot.degraded is False
        assert snapshot.last_error_type is None

    async def test_process_wide_counter_is_the_default(self) -> None:
        """주입하지 않으면 프로세스 전역 회계에 합산된다(운영 판정 단위 = 프로세스)."""
        cache = _ExplodingCache(explode=frozenset({"get"}))
        real_inner = InMemoryDeviceStore()
        device_id, secret_plain = await real_inner.register(_UID)
        store = CachedDeviceStore(real_inner, cache, ttl_seconds=60)  # degradation 주입 X

        await store.verify(device_id, _sign(secret_plain, device_id))

        assert device_cache_degradation_snapshot().failures_for("get") == 1


# ══════════════════════════════════════════════════════════════════════════
# 5) device store — 소켓 타임아웃(실물 redis-py 객체로 검증)
# ══════════════════════════════════════════════════════════════════════════
class TestDeviceCacheSocketTimeout:
    """무응답 Redis 방어 — 시임이 아니라 진짜 `redis.asyncio.Redis`의 kwargs를 읽는다.

    CLAUDE.md: 외부 SDK 표면을 가짜 테스트만으로 정합 선언 금지. 네트워크는 타지 않는다
    (`from_url`은 연결 풀만 구성한다).
    """

    def test_build_receives_both_timeouts(self) -> None:
        client = _build_redis_for_cache(_settings(redis_socket_timeout_s=2.0))

        kwargs = client.connection_pool.connection_kwargs  # type: ignore[attr-defined]
        # 변별력: 인자를 넘기지 *않으면* redis-py는 이 키들을 아예 넣지 않는다(8.0.1 실측)
        # → 아래 두 단정은 가드 제거 시 KeyError로 즉시 깨진다.
        assert kwargs["socket_timeout"] == 2.0
        assert kwargs["socket_connect_timeout"] == 2.0

    def test_timeout_value_follows_settings(self) -> None:
        """하드코딩이 아니라 운영이 조절 가능한 축이며, OPS-05가 만든 키를 재사용한다."""
        client = _build_redis_for_cache(_settings(redis_socket_timeout_s=0.25))

        kwargs = client.connection_pool.connection_kwargs  # type: ignore[attr-defined]
        assert kwargs["socket_timeout"] == 0.25
        assert kwargs["socket_connect_timeout"] == 0.25

    def test_effective_connection_carries_timeout(self) -> None:
        """풀이 만드는 *실제 Connection*에 값이 실린다(kwargs만 맞고 무효인 경우 배제)."""
        client = _build_redis_for_cache(_settings(redis_socket_timeout_s=1.5))

        conn = client.connection_pool.make_connection()  # type: ignore[attr-defined]
        assert conn.socket_timeout == 1.5
        assert conn.socket_connect_timeout == 1.5

    async def test_lifespan_binds_invalidate_timeout_to_the_same_setting(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """무효화 재시도의 시도별 상한도 같은 설정 축에 묶인다(손잡이 1개)."""
        import whymath_backend.api._device_store as ds_mod

        monkeypatch.setattr(ds_mod, "_build_redis_for_cache", lambda settings: _WorkingCache())
        settings = _settings(device_store_mode="pg_cached", redis_socket_timeout_s=0.75)

        store, _cleanup = build_device_store_from_settings(settings)

        assert isinstance(store, CachedDeviceStore)
        assert store._invalidate_timeout == 0.75


# ══════════════════════════════════════════════════════════════════════════
# 6) rate limit — 가짜 Redis 시임
# ══════════════════════════════════════════════════════════════════════════
class RateLimitBoomError(RuntimeError):
    """폭발용 커스텀 예외 — 로그 단정의 변별력."""


class _WorkingRateLimitRedis:
    """`_LUA_HIT`·`_LUA_HIT_MANY`의 *의미*를 인메모리 ZSET으로 재현(양성 대조용).

    Lua 스크립트 자체의 정확성은 `test_rate_limit_integration.py`가 실 Redis로 검증한다.
    여기서는 "정상 Redis에서 폴백이 발동하지 않는다"만 확인한다.
    """

    def __init__(self, *, require_script_load: bool = False) -> None:
        self.zsets: dict[str, list[tuple[float, str]]] = {}
        self.script_loads: list[str] = []
        self._loaded: set[str] = set()
        self._require_script_load = require_script_load

    async def evalsha(self, sha: str, numkeys: int, *args: Any) -> Any:
        if self._require_script_load and sha not in self._loaded:
            from redis.exceptions import NoScriptError

            raise NoScriptError("NOSCRIPT No matching script. Use SCRIPT LOAD.")
        if sha == _LUA_HIT_MANY_SHA1:
            return self._apply_many(numkeys, args)
        return self._apply_hit(args)

    def _prune(self, key: str, cutoff: float) -> list[tuple[float, str]]:
        bucket = self.zsets.setdefault(key, [])
        bucket[:] = [(s, m) for (s, m) in bucket if s >= cutoff]
        return bucket

    def _apply_hit(self, args: tuple[Any, ...]) -> list[int]:
        key, now, limit, member = args[0], float(args[1]), int(args[2]), args[3]
        bucket = self._prune(key, now - 60)
        allowed = 1 if len(bucket) < limit else 0
        if allowed:
            bucket.append((now, member))
        return [allowed, len(bucket), int(bucket[0][0] * 1_000_000) if bucket else -1]

    def _apply_many(self, numkeys: int, args: tuple[Any, ...]) -> list[int]:
        keys = list(args[:numkeys])
        now = float(args[numkeys])
        member = args[numkeys + 1]
        limits = [int(x) for x in args[numkeys + 2 : numkeys + 2 + numkeys]]
        buckets = [self._prune(k, now - 60) for k in keys]
        all_ok = all(len(b) < lim for b, lim in zip(buckets, limits, strict=True))
        if all_ok:
            for bucket in buckets:
                bucket.append((now, member))
        response: list[int] = [1 if all_ok else 0]
        for bucket in buckets:
            response.append(len(bucket))
            response.append(int(bucket[0][0] * 1_000_000) if bucket else -1)
        return response

    async def script_load(self, script: str) -> str:
        import hashlib

        self.script_loads.append(script)
        sha = hashlib.sha1(script.encode("utf-8")).hexdigest()
        self._loaded.add(sha)
        return sha

    async def ping(self) -> bool:
        return True

    async def delete(self, *names: str) -> int:
        for name in names:
            self.zsets.pop(name, None)
        return len(names)

    async def keys(self, pattern: str) -> list[str]:
        prefix = pattern.rstrip("*")
        return [k for k in self.zsets if k.startswith(prefix)]


class _ExplodingRateLimitRedis:
    """모든 Redis 접근이 폭발 — 완전 장애 재현."""

    def __init__(self) -> None:
        self.evalsha_calls = 0

    async def evalsha(self, sha: str, numkeys: int, *args: Any) -> Any:
        self.evalsha_calls += 1
        raise RateLimitBoomError("redis evalsha 폭발")

    async def script_load(self, script: str) -> str:
        raise RateLimitBoomError("redis script_load 폭발")

    async def ping(self) -> bool:
        raise RateLimitBoomError("redis ping 폭발")

    async def delete(self, *names: str) -> int:
        raise RateLimitBoomError("redis delete 폭발")

    async def keys(self, pattern: str) -> list[str]:
        raise RateLimitBoomError("redis keys 폭발")


class _CountingFallback(InMemoryBackend):
    """폴백이 *실제로* 쓰였는지 세는 인메모리 백엔드."""

    def __init__(self) -> None:
        super().__init__()
        self.calls = 0

    async def _hit_by_key(self, subject_key: str, **kwargs: Any) -> Any:
        self.calls += 1
        return await super()._hit_by_key(subject_key, **kwargs)


# ══════════════════════════════════════════════════════════════════════════
# 7) rate limit — Redis 장애 시 인메모리 폴백(fail-open도 fail-closed도 아니다)
# ══════════════════════════════════════════════════════════════════════════
class TestRateLimitFallsBackToMemory:
    """Redis가 죽어도 ①요청은 살고 ②한도는 남는다."""

    async def test_hit_still_enforces_limit_during_outage(self) -> None:
        """**핵심 단정** — 폴백이 fail-open이 아니다. 3번째는 여전히 거부된다."""
        counter = DegradationCounter("테스트")
        backend = RedisBackend(client=_ExplodingRateLimitRedis(), degradation=counter)
        uid = uuid.uuid4()

        # 예외가 새면 이 줄들에서 그대로 실패한다(fail-closed 방지 축).
        assert (await backend.hit(uid, category="read", limit=2, now=0.0)).allowed is True
        assert (await backend.hit(uid, category="read", limit=2, now=0.1)).allowed is True
        # 무제한이면 아래가 True가 된다 — 이 한 줄이 fail-open 회귀를 잡는다.
        assert (await backend.hit(uid, category="read", limit=2, now=0.2)).allowed is False
        assert counter.snapshot().failures_for("hit") == 3

    async def test_fallback_backend_actually_receives_the_calls(self) -> None:
        """'예외를 삼키고 아무 데도 안 센다'와 구분한다 — 인메모리가 실제로 계수한다."""
        fallback = _CountingFallback()
        backend = RedisBackend(
            client=_ExplodingRateLimitRedis(),
            fallback=fallback,
            degradation=DegradationCounter("테스트"),
        )

        await backend.hit(uuid.uuid4(), category="read", limit=5, now=0.0)

        assert fallback.calls == 1

    async def test_hit_many_falls_back_and_enforces(self) -> None:
        """학생 코치 경로가 실제로 타는 3차원 검사도 폴백된다."""
        counter = DegradationCounter("테스트")
        backend = RedisBackend(client=_ExplodingRateLimitRedis(), degradation=counter)
        subjects = [
            Subject(kind="user", id=str(uuid.uuid4()), limit=1),
            Subject(kind="ip", id="203.0.113.7", limit=5),
            Subject(kind="device", id="dev-1", limit=5),
        ]

        first = await backend.hit_many(subjects, category="write", now=0.0)
        second = await backend.hit_many(subjects, category="write", now=0.1)

        assert first["user"].allowed is True
        assert second["user"].allowed is False  # user limit=1 소진 → 원자 거부
        assert second["ip"].allowed is False
        assert counter.snapshot().failures_for("hit_many") == 2

    async def test_hit_both_falls_back_and_enforces(self) -> None:
        counter = DegradationCounter("테스트")
        backend = RedisBackend(client=_ExplodingRateLimitRedis(), degradation=counter)
        uid = uuid.uuid4()

        first = await backend.hit_both(
            uid, "203.0.113.7", category="write", user_limit=1, ip_limit=5, now=0.0
        )
        second = await backend.hit_both(
            uid, "203.0.113.7", category="write", user_limit=1, ip_limit=5, now=0.1
        )

        assert first.allowed is True
        assert second.allowed is False
        assert counter.snapshot().failures_for("hit_both") == 2

    async def test_fallback_logs_exception_type_name(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        backend = RedisBackend(
            client=_ExplodingRateLimitRedis(), degradation=DegradationCounter("rate limit")
        )

        with caplog.at_level(logging.WARNING, logger=_DEGRADATION_LOGGER):
            await backend.hit(uuid.uuid4(), category="read", limit=5, now=0.0)

        assert "RateLimitBoomError" in caplog.text
        assert "operation=hit" in caplog.text
        # 운영자가 로그 한 줄로 "지금 한도가 워커별로 갈라져 있다"를 읽을 수 있어야 한다.
        assert "인메모리" in caplog.text

    async def test_fallback_does_not_log_user_id_or_ip(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """rate limit 키에는 user_id·IP가 들어간다 — 로그에 남기지 않는다."""
        backend = RedisBackend(
            client=_ExplodingRateLimitRedis(), degradation=DegradationCounter("테스트")
        )
        uid = uuid.uuid4()

        with caplog.at_level(logging.DEBUG, logger=_DEGRADATION_LOGGER):
            await backend.hit_by_ip("198.51.100.42", category="read", limit=5, now=0.0)
            await backend.hit(uid, category="read", limit=5, now=0.1)

        assert "198.51.100.42" not in caplog.text
        assert str(uid) not in caplog.text

    async def test_process_wide_counter_is_the_default(self) -> None:
        backend = RedisBackend(client=_ExplodingRateLimitRedis())  # degradation 주입 X

        await backend.hit(uuid.uuid4(), category="read", limit=5, now=0.0)

        assert rate_limit_degradation_snapshot().failures_for("hit") == 1


class TestRateLimitHealthyPathUnchanged:
    """양성 대조 — 정상 Redis에서는 종전 동작 그대로이고 폴백은 잠자코 있다."""

    async def test_healthy_hit_uses_redis_and_never_touches_fallback(self) -> None:
        counter = DegradationCounter("테스트")
        fake = _WorkingRateLimitRedis()
        fallback = _CountingFallback()
        backend = RedisBackend(client=fake, fallback=fallback, degradation=counter)
        uid = uuid.uuid4()

        assert (await backend.hit(uid, category="read", limit=2, now=0.0)).allowed is True
        assert (await backend.hit(uid, category="read", limit=2, now=0.1)).allowed is True
        assert (await backend.hit(uid, category="read", limit=2, now=0.2)).allowed is False

        assert f"rate:coach:read:user:{uid}" in fake.zsets  # 키 네이밍 회귀 동결
        assert fallback.calls == 0
        assert counter.snapshot().total_failures == 0

    async def test_noscript_reload_is_not_counted_as_degradation(self) -> None:
        """`NoScriptError` → SCRIPT LOAD 재시도는 *정상 동작*이다(폴백 아님)."""
        counter = DegradationCounter("테스트")
        fake = _WorkingRateLimitRedis(require_script_load=True)
        fallback = _CountingFallback()
        backend = RedisBackend(client=fake, fallback=fallback, degradation=counter)

        result = await backend.hit(uuid.uuid4(), category="read", limit=5, now=0.0)

        assert result.allowed is True
        assert len(fake.script_loads) == 1  # 적재 후 재시도로 복구
        assert fallback.calls == 0
        assert counter.snapshot().total_failures == 0

    async def test_sliding_window_prunes_on_healthy_redis(self) -> None:
        backend = RedisBackend(
            client=_WorkingRateLimitRedis(), degradation=DegradationCounter("테스트")
        )
        uid = uuid.uuid4()

        assert (await backend.hit(uid, category="read", limit=1, now=0.0)).allowed is True
        assert (await backend.hit(uid, category="read", limit=1, now=0.5)).allowed is False
        assert (await backend.hit(uid, category="read", limit=1, now=61.0)).allowed is True

    async def test_reset_clears_both_backends(self) -> None:
        """테스트 격리 도구 — 폴백 버킷이 남으면 다음 테스트가 오염된다."""
        fake = _WorkingRateLimitRedis()
        fallback = _CountingFallback()
        backend = RedisBackend(client=fake, fallback=fallback, degradation=DegradationCounter("t"))
        uid = uuid.uuid4()
        await backend.hit(uid, category="read", limit=5, now=0.0)
        await fallback.hit(uid, category="read", limit=5, now=0.0)

        await backend.reset()

        assert fake.zsets == {}
        assert fallback._by_key == {}


class TestRateLimitSocketTimeout:
    """실물 redis-py 객체로 타임아웃 결선 확인(시임만으로 판정 금지)."""

    def test_build_receives_both_timeouts(self) -> None:
        client = _build_default_redis_client(_settings(redis_socket_timeout_s=2.0))

        kwargs = client.connection_pool.connection_kwargs  # type: ignore[attr-defined]
        assert kwargs["socket_timeout"] == 2.0
        assert kwargs["socket_connect_timeout"] == 2.0

    def test_timeout_value_follows_settings(self) -> None:
        client = _build_default_redis_client(_settings(redis_socket_timeout_s=0.5))

        kwargs = client.connection_pool.connection_kwargs  # type: ignore[attr-defined]
        assert kwargs["socket_timeout"] == 0.5
        assert kwargs["socket_connect_timeout"] == 0.5

    def test_effective_connection_carries_timeout(self) -> None:
        client = _build_default_redis_client(_settings(redis_socket_timeout_s=1.25))

        conn = client.connection_pool.make_connection()  # type: ignore[attr-defined]
        assert conn.socket_timeout == 1.25
        assert conn.socket_connect_timeout == 1.25

    def test_three_client_builders_share_one_timeout_setting(self) -> None:
        """OPS-06의 목적 자체 — 세 생성 지점이 *같은* 설정 키를 읽는다(3분기 통일).

        새 키를 만들었거나 한 곳이 하드코딩으로 남으면 이 단정이 깨진다.
        """
        from whymath_backend.l3.cache.redis_cache import _build_default_client as l3_build

        settings = _settings(redis_socket_timeout_s=0.875)
        clients = [
            l3_build(settings),
            _build_redis_for_cache(settings),
            _build_default_redis_client(settings),
        ]

        for client in clients:
            kwargs = client.connection_pool.connection_kwargs  # type: ignore[attr-defined]
            assert kwargs["socket_timeout"] == 0.875
            assert kwargs["socket_connect_timeout"] == 0.875


# ══════════════════════════════════════════════════════════════════════════
# 8) 테스트 위생 — 시임이 프로덕션 Protocol을 실제로 충족하는가
# ══════════════════════════════════════════════════════════════════════════
def test_fakes_satisfy_production_protocols() -> None:
    """가짜가 계약을 벗어나면 이 파일의 모든 단정이 허구가 된다."""
    from whymath_backend.api._device_store import _CacheClient
    from whymath_backend.api._rate_limit import RateLimitBackend, _RedisClient

    assert isinstance(_WorkingCache(), _CacheClient)
    assert isinstance(_ExplodingCache(), _CacheClient)
    assert isinstance(_CountingInner(InMemoryDeviceStore()), DeviceCredentialStore)
    assert isinstance(_WorkingRateLimitRedis(), _RedisClient)
    assert isinstance(_ExplodingRateLimitRedis(), _RedisClient)
    assert isinstance(RedisBackend(client=_WorkingRateLimitRedis()), RateLimitBackend)


def test_event_loop_is_not_required_for_builders() -> None:
    """빌더는 순수 구성이라 이벤트 루프 없이도 만들어진다(네트워크 미접속 확인 보조)."""
    assert asyncio.get_event_loop_policy() is not None
    _build_redis_for_cache(_settings())
    _build_default_redis_client(_settings())
