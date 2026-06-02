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

import hashlib
import math
import time
import uuid
from collections import deque
from typing import (
    Annotated,
    Any,
    Literal,
    NamedTuple,
    Protocol,
    cast,
    runtime_checkable,
)

from fastapi import Depends, HTTPException, Request, Response, status

from whymath_backend.api._auth import ConsentedUser
from whymath_backend.config import Settings, get_settings

# redis-py의 NoScriptError를 지연 import — 라이브러리 미설치 환경(CI 단위테스트)에서도
# 모듈 import가 깨지지 않게 한다(`_build_default_redis_client` 패턴 정합). 미설치 환경
# 에서는 RedisBackend 자체가 사용되지 않으므로 fallback 클래스는 실제로 raise되지 않는다.
try:
    from redis.exceptions import NoScriptError
except ImportError:  # pragma: no cover — 라이브러리 미설치 환경

    class NoScriptError(Exception):  # type: ignore[no-redef]
        """fallback — redis 라이브러리 미설치 시 미사용 placeholder."""


_WINDOW_SECONDS = 60.0

RateCategory = Literal["read", "write"]
"""POST/GET 차등 한도 — 읽기/쓰기 분리 버킷(상호 영향 차단)."""


class RateLimitResult(NamedTuple):
    """`hit()` 반환 — 허용 여부 + 클라이언트 throttle 정보(X-RateLimit-* 헤더 입력).

    - `allowed`: 한도 내면 True(요청 기록됨), 초과면 False(요청 미기록).
    - `remaining`: 이 호출 후 *남은 슬롯* 수(0 이상). 거부 시 0.
    - `reset_seconds`: 가장 오래된 항목이 만료되어 슬롯이 *하나 더 비기까지* 남은 초.
      윈도우가 비어있으면 0(즉시 사용 가능 — 첫 요청). 거부 시에도 의미 있음.
    """

    allowed: bool
    remaining: int
    reset_seconds: int


@runtime_checkable
class RateLimitBackend(Protocol):
    """rate limit 백엔드 — sliding window 카운트의 저장·검사 추상.

    `category`(`"read"`/`"write"`)로 별도 버킷 — 한 카테고리 소진이 다른 카테고리에
    영향 주지 않는다(읽기 폭주가 쓰기를 막거나, 그 반대 차단). 슬라이스 16: `hit_by_ip`로
    IP 단위 한도(미인증 표면)도 같은 backend로 처리 — 사용자 키와 IP 키는 *네임스페이스
    분리*되어 충돌 없음(`user:<uid>` vs `ip:<addr>` 접두).
    """

    async def hit(
        self,
        user_id: uuid.UUID,
        *,
        category: RateCategory,
        limit: int,
        now: float,
    ) -> RateLimitResult:
        """*사용자 단위* 요청 기록 시도 — `RateLimitResult` 반환."""
        ...

    async def hit_by_ip(
        self,
        ip: str,
        *,
        category: RateCategory,
        limit: int,
        now: float,
    ) -> RateLimitResult:
        """*IP 단위* 요청 기록 시도 — 미인증 표면용. `RateLimitResult` 반환."""
        ...

    async def reset(self) -> None:
        """모든 카테고리·모든 카운트 초기화 — 테스트 격리용. production 미호출."""
        ...


def _result_from_window(
    *,
    allowed: bool,
    count_after: int,
    limit: int,
    oldest_ts: float | None,
    now: float,
) -> RateLimitResult:
    """sliding window 상태에서 표준 결과 객체 구성 — 인메모리·Redis 백엔드 공통.

    `allowed`는 호출자가 *명시*한다(`count_after ≤ limit`만으로는 *at-limit 미추가* 케이스를
    구분 못 함 — bucket이 limit로 가득 차고 추가 안 한 경우와 추가 후 limit 도달이 같은
    `count_after`로 보이기 때문).
    """
    remaining = max(0, limit - count_after)
    if (
        oldest_ts is None
    ):  # pragma: no cover — 정상 경로는 항상 oldest 존재(at-limit 시 bucket 비공)
        reset_seconds = 0
    else:
        reset_seconds = max(0, math.ceil(_WINDOW_SECONDS - (now - oldest_ts)))
    return RateLimitResult(allowed=allowed, remaining=remaining, reset_seconds=reset_seconds)


class InMemoryBackend:
    """프로세스-로컬 deque per (subject_key, category) — 단일 인스턴스 한정.

    `subject_key`는 `f"user:{uid}"` 또는 `f"ip:{addr}"` 접두로 네임스페이스 분리. 분산
    환경에서는 워커별 별도 카운트 → 효과 ÷ N. 그 경우 `RedisBackend` 사용.
    """

    def __init__(self) -> None:
        self._by_key: dict[tuple[str, str], deque[float]] = {}

    async def _hit_by_key(
        self, subject_key: str, *, category: RateCategory, limit: int, now: float
    ) -> RateLimitResult:
        cutoff = now - _WINDOW_SECONDS
        bucket = self._by_key.setdefault((subject_key, category), deque())
        while bucket and bucket[0] < cutoff:
            bucket.popleft()
        allowed = len(bucket) < limit
        if allowed:
            bucket.append(now)
        oldest = bucket[0] if bucket else None
        return _result_from_window(
            allowed=allowed,
            count_after=len(bucket),
            limit=limit,
            oldest_ts=oldest,
            now=now,
        )

    async def hit(
        self,
        user_id: uuid.UUID,
        *,
        category: RateCategory,
        limit: int,
        now: float,
    ) -> RateLimitResult:
        return await self._hit_by_key(f"user:{user_id}", category=category, limit=limit, now=now)

    async def hit_by_ip(
        self, ip: str, *, category: RateCategory, limit: int, now: float
    ) -> RateLimitResult:
        return await self._hit_by_key(f"ip:{ip}", category=category, limit=limit, now=now)

    async def reset(self) -> None:
        self._by_key.clear()


# Redis 클라이언트 추상화 — l3/cache/redis_cache.py `_RedisClient` 패턴 답습.
# 우리가 실제로 쓰는 메서드만 좁게 선언(evalsha·script_load·eval 폴백·ping·delete·keys).
@runtime_checkable
class _RedisClient(Protocol):
    async def evalsha(self, sha: str, numkeys: int, *args: Any) -> Any:
        """EVALSHA — 캐시된 Lua 스크립트 실행(스크립트 SHA1 기준)."""
        ...

    async def script_load(self, script: str) -> Any:
        """SCRIPT LOAD — Lua 스크립트를 Redis 캐시에 적재, SHA1 반환."""
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
# 반환 = {count_after, oldest_score_int_micros}. 백엔드가 RateLimitResult로 변환.
# (oldest는 micros 정수로 직렬화 — Redis Lua의 정수 반환 제약 + Python float 복원.)
_LUA_HIT = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local limit = tonumber(ARGV[2])
local cutoff = now - 60
redis.call('ZREMRANGEBYSCORE', key, '-inf', cutoff)
local count = redis.call('ZCARD', key)
local allowed = 0
if count < limit then
    redis.call('ZADD', key, now, ARGV[3])
    redis.call('EXPIRE', key, 60)
    count = count + 1
    allowed = 1
end
local oldest_micros = -1
local oldest_range = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
if #oldest_range >= 2 then
    oldest_micros = math.floor(tonumber(oldest_range[2]) * 1000000)
end
return {allowed, count, oldest_micros}
"""

# 결정론적 SHA1 — 모듈 로드 시 1회 계산. Redis의 SCRIPT LOAD 결과(40-char hex)와 *정확히
# 일치*해야 EVALSHA가 캐시 적중한다(Redis는 같은 알고리즘 사용).
_LUA_HIT_SHA1 = hashlib.sha1(_LUA_HIT.encode("utf-8")).hexdigest()


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
    """Redis ZSET sliding window — 분산/HA 정합 + EVALSHA 최적화.

    Lua 스크립트 `_LUA_HIT`가 ZREMRANGEBYSCORE→ZCARD→조건부 ZADD/EXPIRE를 원자로
    수행해 race window 0. 키 prefix `rate:coach:` + user_id(UUID). 60초 TTL 자동 만료로
    유휴 사용자 키 누수 방지.

    **EVALSHA 최적화**(슬라이스 13): EVAL 대신 EVALSHA(SHA1) 사용 — 매 호출 풀 스크립트
    바이트 전송 회피(분산 환경 네트워크·Redis 파싱 비용 절감). `_LUA_HIT_SHA1`은 모듈 로드
    시 결정론적으로 계산되며, Redis SCRIPT LOAD 결과와 *반드시 일치*한다(같은 SHA1 알고리즘).
    `NoScriptError`(SCRIPT FLUSH·Redis 재시작 등으로 캐시에서 사라진 경우) 시 한 번
    `script_load` + 재시도. 정상 경로는 EVALSHA 1회.
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

    def _key(self, subject_key: str, category: RateCategory) -> str:
        # 카테고리·subject(user:/ip:)별 키 분리 — 예: `rate:coach:read:user:{uid}` /
        # `rate:coach:write:ip:{addr}`. 사용자·IP 네임스페이스 충돌 없음.
        return f"{self._KEY_PREFIX}{category}:{subject_key}"

    async def _hit_by_key(
        self, subject_key: str, *, category: RateCategory, limit: int, now: float
    ) -> RateLimitResult:
        client = self._get_client()
        key = self._key(subject_key, category)
        unique_member = f"{now}:{uuid.uuid4().hex}"
        try:
            raw = await client.evalsha(_LUA_HIT_SHA1, 1, key, now, limit, unique_member)
        except NoScriptError:
            # 스크립트가 Redis 캐시에 없음(SCRIPT FLUSH·재시작 후 첫 호출). 적재 후 재시도.
            await client.script_load(_LUA_HIT)
            raw = await client.evalsha(_LUA_HIT_SHA1, 1, key, now, limit, unique_member)
        allowed = int(raw[0]) == 1
        count_after = int(raw[1])
        oldest_micros = int(raw[2])
        oldest_ts = None if oldest_micros < 0 else oldest_micros / 1_000_000
        return _result_from_window(
            allowed=allowed,
            count_after=count_after,
            limit=limit,
            oldest_ts=oldest_ts,
            now=now,
        )

    async def hit(
        self,
        user_id: uuid.UUID,
        *,
        category: RateCategory,
        limit: int,
        now: float,
    ) -> RateLimitResult:
        return await self._hit_by_key(f"user:{user_id}", category=category, limit=limit, now=now)

    async def hit_by_ip(
        self, ip: str, *, category: RateCategory, limit: int, now: float
    ) -> RateLimitResult:
        return await self._hit_by_key(f"ip:{ip}", category=category, limit=limit, now=now)

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


def _rate_headers(limit: int, result: RateLimitResult) -> dict[str, str]:
    """표준 IETF 드래프트 RateLimit 헤더(GitHub-style 변형) — 클라이언트 자체 throttle 입력.

    - `X-RateLimit-Limit`: 윈도우당 최대 요청 수.
    - `X-RateLimit-Remaining`: *이 응답 시점* 남은 슬롯 수(0=다음 호출은 429 가능).
    - `X-RateLimit-Reset`: 다음 슬롯이 비기까지 *남은 초*(0=즉시 가능). 거부 시에도 의미.
    """
    return {
        "X-RateLimit-Limit": str(limit),
        "X-RateLimit-Remaining": str(result.remaining),
        "X-RateLimit-Reset": str(result.reset_seconds),
    }


# 슬라이스 11-15의 user-only `rate_limit_read/write` 및 헬퍼 `_enforce`는 슬라이스 17의
# Defense(사용자+IP) 도입으로 *모두 대체*됨(clean cut). 호출자 0 — 죽은 코드 제거(CLAUDE.md
# "범위 밖 기능 금지"). 사용자 한도만 원하면 `ip_limit=0` 설정으로 Defense가 동등하게 동작.


def _client_ip(request: Request) -> str | None:
    """요청에서 IP 추출 — `X-Forwarded-For` 첫 항목 우선(LB 뒤 운영), 없으면 직접 연결.

    프록시 신뢰 모델: 본 함수는 *직전 신뢰 가능한 프록시*가 `X-Forwarded-For`를 설정했다는
    *가정*에 의존한다(LB·CDN). 신뢰 없는 환경에선 클라이언트가 임의 헤더 주입 가능 — 운영
    시 `uvicorn --proxy-headers` + 신뢰 IP 화이트리스트 필수. 헤더 미설정·`request.client`
    None 이면 None 반환(rate limit 비활성 — 알 수 없는 IP는 차단도 통과도 안전한 fallback
    선택, 본 함수는 None 시 호출자가 한도 미적용으로 처리).
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        # 콤마 구분 — 가장 좌측이 원본 클라이언트, 우측은 프록시 체인
        head = forwarded.split(",")[0].strip()
        if head:
            return head
    if request.client is not None:
        return request.client.host
    return None


async def _enforce_by_ip(
    ip: str,
    *,
    category: RateCategory,
    limit: int,
    response: Response,
) -> None:
    """IP 단위 한도 검사. 사용자 한도와 동일 시맨틱(429 + 헤더). limit=0이면 비활성."""
    if limit == 0:
        return
    result = await _BACKEND.hit_by_ip(ip, category=category, limit=limit, now=time.monotonic())
    headers = _rate_headers(limit, result)
    if not result.allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="요청이 너무 많습니다(분당 한도 초과). 잠시 후 다시 시도하세요.",
            headers={"Retry-After": str(result.reset_seconds or 60), **headers},
        )
    for key, value in headers.items():
        response.headers[key] = value


async def rate_limit_ip_read(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    response: Response,
) -> None:
    """*IP 단위 읽기* 한도 — 미인증 GET 엔드포인트용. IP 추출 실패 시 적용 안 함."""
    ip = _client_ip(request)
    if ip is None:
        return
    await _enforce_by_ip(
        ip,
        category="read",
        limit=settings.coach_rate_limit_ip_read_per_minute,
        response=response,
    )


async def rate_limit_ip_write(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    response: Response,
) -> None:
    """*IP 단위 쓰기* 한도 — 미인증 POST 엔드포인트용. IP 추출 실패 시 적용 안 함."""
    ip = _client_ip(request)
    if ip is None:
        return
    await _enforce_by_ip(
        ip,
        category="write",
        limit=settings.coach_rate_limit_ip_write_per_minute,
        response=response,
    )


RateLimitedIpRead = Depends(rate_limit_ip_read)
"""*미인증* GET 엔드포인트용 의존성(IP 단위) — `dependencies=[RateLimitedIpRead]`."""

RateLimitedIpWrite = Depends(rate_limit_ip_write)
"""*미인증* POST 엔드포인트용 의존성(IP 단위) — `dependencies=[RateLimitedIpWrite]`."""


# ──────────────────────────────────────────────────────────────────────────
# 슬라이스 17 — 사용자 + IP 동시 적용(방어 심층)
# 인증된 엔드포인트에 둘 다 부착해 ① 단일 사용자 학대 ② 공유 NAT의 단일 IP 학대 모두 차단.
# 429는 *먼저 실패*한 쪽 헤더로(사용자 우선). 200 헤더는 *더 엄격한* 쪽 노출(클라이언트가
# 가장 가까운 한도를 인식).
# ──────────────────────────────────────────────────────────────────────────


def _tightest_headers(
    user_pair: tuple[int, RateLimitResult] | None,
    ip_pair: tuple[int, RateLimitResult] | None,
) -> dict[str, str]:
    """두 검사 중 *더 엄격한*(remaining 작은) 쪽의 X-RateLimit 헤더 반환.

    한쪽만 있으면 그쪽. 둘 다 있으면 remaining 작은 쪽(동률은 user 우선).
    둘 다 None이면 빈 dict(헤더 미세팅).
    """
    if user_pair is None and ip_pair is None:
        return {}
    if ip_pair is None:
        assert user_pair is not None
        return _rate_headers(*user_pair)
    if user_pair is None:
        return _rate_headers(*ip_pair)
    user_limit, user_result = user_pair
    ip_limit, ip_result = ip_pair
    if user_result.remaining <= ip_result.remaining:
        return _rate_headers(user_limit, user_result)
    return _rate_headers(ip_limit, ip_result)


async def _enforce_defense(
    user_id: uuid.UUID,
    ip: str | None,
    *,
    category: RateCategory,
    user_limit: int,
    ip_limit: int,
    response: Response,
) -> None:
    """사용자 + IP 한도 *둘 다* 검사. 사용자 먼저 — 둘 다 통과해야 200."""
    user_pair: tuple[int, RateLimitResult] | None = None
    if user_limit > 0:
        user_result = await _BACKEND.hit(
            user_id, category=category, limit=user_limit, now=time.monotonic()
        )
        if not user_result.allowed:
            headers = _rate_headers(user_limit, user_result)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="요청이 너무 많습니다(분당 한도 초과). 잠시 후 다시 시도하세요.",
                headers={"Retry-After": str(user_result.reset_seconds or 60), **headers},
            )
        user_pair = (user_limit, user_result)

    ip_pair: tuple[int, RateLimitResult] | None = None
    if ip_limit > 0 and ip is not None:
        ip_result = await _BACKEND.hit_by_ip(
            ip, category=category, limit=ip_limit, now=time.monotonic()
        )
        if not ip_result.allowed:
            headers = _rate_headers(ip_limit, ip_result)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="요청이 너무 많습니다(분당 한도 초과). 잠시 후 다시 시도하세요.",
                headers={"Retry-After": str(ip_result.reset_seconds or 60), **headers},
            )
        ip_pair = (ip_limit, ip_result)

    for key, value in _tightest_headers(user_pair, ip_pair).items():
        response.headers[key] = value


async def rate_limit_defense_read(
    user: ConsentedUser,
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    response: Response,
) -> None:
    """*사용자 + IP* 읽기 한도 동시 적용 — 인증 GET 엔드포인트의 방어 심층."""
    await _enforce_defense(
        user.user_id,
        _client_ip(request),
        category="read",
        user_limit=settings.coach_rate_limit_read_per_minute,
        ip_limit=settings.coach_rate_limit_ip_read_per_minute,
        response=response,
    )


async def rate_limit_defense_write(
    user: ConsentedUser,
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    response: Response,
) -> None:
    """*사용자 + IP* 쓰기 한도 동시 적용 — 인증 POST 엔드포인트의 방어 심층."""
    await _enforce_defense(
        user.user_id,
        _client_ip(request),
        category="write",
        user_limit=settings.coach_rate_limit_write_per_minute,
        ip_limit=settings.coach_rate_limit_ip_write_per_minute,
        response=response,
    )


RateLimitedDefenseRead = Depends(rate_limit_defense_read)
"""인증 GET용 *사용자 + IP* 동시 의존성 — `dependencies=[RateLimitedDefenseRead]`."""

RateLimitedDefenseWrite = Depends(rate_limit_defense_write)
"""인증 POST용 *사용자 + IP* 동시 의존성 — `dependencies=[RateLimitedDefenseWrite]`."""
