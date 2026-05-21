"""Redis 응답 캐시 — interfaces.CacheBackend 구현 (M1.2-live S2).

라우터가 만든 캐시 키(03a §F.1, `cache_key_for` — `{cost_tier}:{local_family}:
{local_model}`이 포함된 불투명 키)로 응답을 Redis에 저장·조회한다. *키 의미는
라우터가 책임지고*, 이 백엔드는 키-값 + TTL 저장이라는 *영속 계층*만 담당한다
(L5 다중 저장소 운영 책임 — Redis는 세션·핫 데이터 캐시).

설계 정본: `docs/architecture/03a_l3_router_design.md` §F.1(캐시 키 의미). 테스트
주입·지연 import 패턴은 providers/ollama.py(`_OllamaClient` 시임 + `_build_default_client`)
를 미러링한다. S1이 세운 패턴을 그대로 따른다.

경계 메모 (CLAUDE.md): 캐시에 저장되는 텍스트는 *검증 전 원시 모델 출력*이다 —
캐시 적중으로 반환된 값도 03 환각 방어 파이프라인 통과 전에는 학생 직접 노출 금지.
캐시 키는 학생 ID를 포함하지 않으므로(03a §F.1) 캐시 자체에 PII는 들어가지 않는다.
"""

from __future__ import annotations

from typing import Any, Protocol, cast, runtime_checkable

from whymath_backend.config import Settings, get_settings


# ──────────────────────────────────────────────────────────────────────────
# Redis 클라이언트 추상화 (테스트 주입용) — ollama.py `_OllamaClient` 패턴 미러링.
# 실제 `redis.asyncio.Redis`와 동형이지만 테스트는 인메모리 가짜로 대체한다.
# 우리가 *실제로 쓰는* 메서드(get·set(ex=)·ping)만 좁게 선언한다.
# ──────────────────────────────────────────────────────────────────────────
@runtime_checkable
class _RedisClient(Protocol):
    """redis.asyncio.Redis의 최소 인터페이스 (구조적 타이핑).

    `redis.asyncio.Redis`의 부분집합. 반환 타입은 클라이언트의 `decode_responses`
    설정에 따라 bytes 또는 str일 수 있어 `Any`로 두고, 캐시 쪽에서 방어적으로
    정규화한다(get_default 클라이언트는 decode_responses=True로 str을 받지만,
    주입된 가짜·다른 설정이 bytes를 줄 수 있어 양쪽을 흡수한다).
    """

    async def get(self, name: str) -> Any:
        """키로 값 조회 (없으면 None)."""
        ...

    async def set(
        self,
        name: str,
        value: str,
        *,
        ex: int | None = None,
    ) -> Any:
        """키-값 저장. `ex`는 만료 초(None이면 무기한). redis SET name value EX ex."""
        ...

    async def ping(self) -> Any:
        """연결 도달성 확인 (redis PING). 도달 시 True/PONG, 실패 시 예외."""
        ...


def _decode(value: Any) -> str | None:
    """Redis get 응답을 str | None으로 방어적 정규화.

    클라이언트가 `decode_responses=True`면 str, 아니면 bytes를 돌려준다. 키 미스는
    None이다. bytes는 UTF-8로 디코드하고, 그 외 예기치 못한 타입은 None으로 본다
    (캐시는 우리가 set한 str만 들어 있어야 하므로, 비정상 값은 미스로 처리해 안전).
    """
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, (bytes, bytearray)):
        return bytes(value).decode("utf-8")
    return None


def _build_default_client(settings: Settings) -> _RedisClient:
    """기본 redis.asyncio 클라이언트 생성 (지연 import).

    `redis` 라이브러리/데몬이 없는 환경(CI 단위테스트)에서도 모듈 import가 깨지지
    않도록 *호출 시점에만* import한다 (ollama.py `_build_default_client` 패턴). 앱
    구성만으로는 라이브 Redis가 필요 없고, 첫 캐시 접근 때 비로소 연결을 만든다.

    `decode_responses=True`로 만들어 get이 str을 돌려주게 한다(디코딩 일관성 — 코드
    쪽 `_decode`는 주입 가짜가 bytes를 줄 경우의 방어선이다). URL은 설정에서 받으며
    인증이 필요하면 URL 자체에 환경변수로 주입한다(CLAUDE.md 보안 금기: 하드코딩 X).
    """
    try:
        from redis.asyncio import Redis
    except ImportError as exc:  # pragma: no cover — 환경 의존(라이브러리 미설치)
        raise RuntimeError(
            "redis Python 클라이언트가 설치되지 않았습니다. "
            "`pip install redis[hiredis]` 후 다시 시도하세요."
        ) from exc
    # cast 사유: redis-py의 from_url은 동기/비동기 공용 시그니처라 정밀 스텁이 우리의
    # 좁은 구조적 시임 `_RedisClient`와 형태가 어긋난다. 우리가 실제로 쓰는 호출 규약
    # (get·set(ex=)·ping)은 Redis가 런타임에 충족하므로 스텁 정밀도 차이만 cast로
    # 좁힌다(타입 무시 X — ollama.py가 AsyncClient를 다룬 방식과 동일).
    client = Redis.from_url(settings.redis_url, decode_responses=True)
    return cast(_RedisClient, client)


class RedisCache:
    """Redis 기반 응답 캐시 — interfaces.CacheBackend 충족.

    파이프라인은 라우터가 만든 키로 get/set만 호출하고(03a §F.1), 이 백엔드는 그 키를
    *불투명하게* Redis에 저장·조회한다. TTL은 redis 네이티브 만료(SET ... EX)로
    실제 적용된다(InMemoryCache는 기록만 했던 것과 대비 — S2의 핵심 차이).

    클라이언트는 지연 생성(lazy)·주입 가능(injectable)하다 — 테스트는 인메모리 가짜
    클라이언트를 `client=`로 넣고, 프로덕션은 기본 redis.asyncio 클라이언트를 첫
    사용 시 생성한다(라이브 Redis 없이도 앱 구성·단위테스트가 가능하도록).
    """

    def __init__(
        self,
        *,
        client: _RedisClient | None = None,
        settings: Settings | None = None,
    ) -> None:
        # 주입된 클라이언트가 있으면 그것을 쓰고, 없으면 첫 사용 시 기본 생성(지연).
        self._client = client
        self._settings = settings

    @property
    def _resolved_settings(self) -> Settings:
        """설정 지연 해석 — 주입 우선, 없으면 캐시된 전역 Settings."""
        if self._settings is None:
            self._settings = get_settings()
        return self._settings

    def _get_client(self) -> _RedisClient:
        """클라이언트 지연 해석 — 주입 우선, 없으면 기본 클라이언트 생성."""
        if self._client is None:
            self._client = _build_default_client(self._resolved_settings)
        return self._client

    async def get(self, key: str) -> str | None:
        """키로 캐시 조회. 미스면 None (CacheBackend 구현).

        반환값은 디코드된 str이다. redis가 bytes를 줄 수 있어 `_decode`로 방어적
        정규화한다(기본 클라이언트는 decode_responses=True라 보통 str). 반환 텍스트는
        *검증 전 원시 출력*이다(모듈 docstring 경계 메모 참조).
        """
        raw = await self._get_client().get(key)
        return _decode(raw)

    async def set(self, key: str, value: str, ttl_seconds: int) -> None:
        """키-값 저장 + TTL 만료 (CacheBackend 구현).

        TTL 처리(엣지 케이스): redis는 `EX 0`(또는 음수)를 거부한다(ERR invalid
        expire time). 따라서 `ttl_seconds <= 0`이면 만료 인자 없이 저장한다 — 즉
        *무기한 보관*으로 폴백한다. 호출자가 양수 TTL을 주면 redis 네이티브 만료를
        그대로 사용한다(InMemoryCache의 '기록만'과 달리 실제로 만료됨).

        무기한 폴백을 택한 이유: 캐시 set은 best-effort 부수효과이므로(미스 시 재생성
        가능) 비정상 TTL 때문에 호출을 실패시키기보다, 값은 저장하되 만료만 생략하는
        쪽이 파이프라인 가용성에 안전하다. 정상 운영에서 `cache_ttl_s`는 양수다
        (config 기본 3600, ge=0). ttl=0은 '캐시 비활성'이 아니라 '만료 없음'으로
        해석됨에 유의(캐시 비활성화는 상위에서 결정).
        """
        client = self._get_client()
        if ttl_seconds <= 0:
            # EX 0/음수는 redis가 거부 → 만료 없이 저장(무기한 폴백).
            await client.set(key, value)
        else:
            await client.set(key, value, ex=ttl_seconds)

    async def ping(self) -> bool:
        """Redis 도달성 확인 — 도달 True, 실패 False (예외 흡수).

        향후 레디니스(/status)용으로 제공한다. ollama의 check_status가 도달 불가를
        비크래시 상태로 흡수하듯, 연결 오류를 예외로 던지지 않고 False로 보고한다.
        S2에서는 /status를 건드리지 않으므로(Ollama 전용 유지) 호출처는 아직 없다.
        """
        try:
            result = await self._get_client().ping()
        except Exception:  # noqa: BLE001 — 도달 불가를 비크래시 False로 흡수
            return False
        # redis ping은 보통 True(또는 b"PONG")를 돌려준다. 도달했으면 truthy.
        return bool(result)
