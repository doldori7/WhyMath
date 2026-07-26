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

장애 강등 (OPS-05 — 왜 이 백엔드가 예외를 삼키는가)
--------------------------------------------------
캐시는 *성능 보완재*지 정답의 원천이 아니다. 그래서 `/health/ready`는 Redis를
`required=false`로 두고 미도달을 "강등"으로 본다. 그런데 OPS-04 조사에서 그 *정책*과
실제 *동작*이 어긋나 있었다: get/set이 예외를 그대로 올려 보내 Redis 다운 시
`l3/pipeline.generate`의 `cache.get`이 터지고 **학생 대면 생성 경로가 5xx**로 죽었다
(`docs/standards/incident_response_slo.md` 함정 ④). 이 모듈은 그 간극을 닫는다 —
네트워크 실패의 *발원지*에서 한 번에 막아, 소비처(파이프라인·L4 DSL 캐시·OCR 등)가
각자 try/except를 흩뿌리지 않게 한다.

강등 의미론은 CLAUDE.md 의사결정 우선순위(#1 학생 안전·웰빙 ≫ #6 비용·효율)의 직접
구현이다: **get 실패 → None(미스와 동일)** 이면 재생성되어 학생은 서비스를 받고, 대가는
LLM 재호출 비용뿐이다. **set 실패 → no-op(best-effort)** 이면 다음 요청이 재생성할 뿐이다.
둘 다 "비용을 더 쓰고 학생을 지킨다"는 교환이며, 그 반대(비용을 아끼려 학생 요청을
5xx로 죽임)는 우선순위 위반이다.

삼키되 침묵하지 않는다 (CLAUDE.md 침묵 실패 금지): 흡수 지점마다 **예외 타입명**을
warning 로그에 남기고(`type(exc).__name__` — 키·값·시크릿은 절대 로그하지 않는다.
캐시 키는 프롬프트 해시라 민감할 수 있다), 강등 횟수를 **인프로세스 카운터**로 센다
(`CacheDegradationCounter` — 외부 관측 인프라가 죽어도 판정치가 남는 이중 회계,
`ops/service_health.ServiceMetrics` 선례).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Literal, Protocol, cast, runtime_checkable

from whymath_backend.config import Settings, get_settings

logger = logging.getLogger(__name__)

# 강등 회계의 연산 어휘 — 로그·스냅샷·테스트가 공유하는 단일 상수.
CacheOperation = Literal["get", "set"]
_OP_GET: CacheOperation = "get"
_OP_SET: CacheOperation = "set"

# 로그 스팸 방지: 연속 실패가 이어지는 동안 매 요청 warning을 찍으면 로그가 알림 가치를
# 잃는다(AlertLogNotifier의 '상태 전이 시에만' 원칙). 전이(첫 실패) + 이후 N번째마다만
# 남긴다 — N번째를 남기는 이유는 장애가 *지속 중*임을 로그만 보고도 알 수 있게 하기 위함.
_LOG_EVERY_N_FAILURES = 100


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


# ──────────────────────────────────────────────────────────────────────────
# 강등 회계 — 인프로세스 축(SaaS·외부 관측 인프라 독립).
#
# 동시성 메모: 스레드-안전 장치를 두지 않는다 — 카운터 갱신은 await 없는 순수 동기
# 구간이라 asyncio 단일 이벤트 루프에서 코루틴 인터리브로 쪼개지지 않는다(락 불요·명시적
# 결정, `ops/service_health` 동시성 메모와 동일 전제). 다중 *워커*(프로세스)는 워커별
# 독립 회계다.
# ──────────────────────────────────────────────────────────────────────────
@dataclass(frozen=True, slots=True)
class CacheDegradationSnapshot:
    """캐시 강등 회계의 불변 스냅샷 — 노출·단정은 이 스냅샷 기준(읽는 중 변형 방지).

    `last_error_type`은 *가장 최근에 흡수한* 예외의 타입명이다(값·키는 담지 않는다).
    강등이 한 번도 없었으면 None — '오류 없음'이지 '오류를 모름'이 아니다(실패 시에만
    채워지는 필드라 None-vs-0 혼동이 없다).
    """

    get_failures: int
    set_failures: int
    consecutive_failures: int
    last_error_type: str | None

    @property
    def total_failures(self) -> int:
        """누적 강등 횟수(get+set) — '이 프로세스가 캐시 없이 버틴 횟수'."""
        return self.get_failures + self.set_failures

    @property
    def degraded(self) -> bool:
        """지금 강등 중인가 = 마지막으로 *관측된* 캐시 연산이 실패였는가.

        트래픽이 없으면 마지막 관측 그대로 남는다(오래된 True는 '그 후 시도가 없었다'는
        뜻이지 '지금 확실히 죽었다'가 아니다). 실시간 도달성 판정은 `/health/ready`의
        Redis PING 딥체크가 따로 한다 — 이 플래그는 *실제 사용 경로*의 관측이다.
        """
        return self.consecutive_failures > 0


class CacheDegradationCounter:
    """강등 회계 + 로그 경로 — 실패를 세고, 상태 전이에서만 warning을 남긴다.

    로그 정책(테스트로 동결):
      - **첫 실패**(정상→강등 전이)는 반드시 warning — 예외 *타입명* 포함(침묵 실패 금지).
      - 연속 실패가 이어지면 `log_every_n_failures`번째마다만 warning(스팸 억제).
      - 성공이 다시 관측되면 info 1회(해소) 후 연속 카운터를 0으로 — 다음 장애는 다시
        첫 실패 warning을 낸다.
      - 로그에 **키·값·시크릿은 절대 싣지 않는다**(캐시 키 = 프롬프트 해시 → 민감 가능).

    logger 주입은 테스트 격리용이다(`AlertLogNotifier` 선례).
    """

    def __init__(
        self,
        *,
        log_every_n_failures: int = _LOG_EVERY_N_FAILURES,
        target_logger: logging.Logger | None = None,
    ) -> None:
        self._logger = target_logger if target_logger is not None else logger
        # 0·음수는 매 실패 로그(스팸)를 뜻하므로 최소 1로 클램프 — 설정 실수 방어.
        self._log_every_n = max(1, log_every_n_failures)
        self._get_failures = 0
        self._set_failures = 0
        self._consecutive_failures = 0
        self._last_error_type: str | None = None

    def record_failure(self, operation: CacheOperation, exc: BaseException) -> None:
        """강등 1건 기록 + 정책에 따라 warning 로그(예외 타입명 포함)."""
        error_type = type(exc).__name__
        if operation == _OP_GET:
            self._get_failures += 1
        else:
            self._set_failures += 1
        self._consecutive_failures += 1
        self._last_error_type = error_type
        if self._consecutive_failures == 1 or self._consecutive_failures % self._log_every_n == 0:
            self._logger.warning(
                "Redis 캐시 강등 — operation=%s 예외 타입: %s (연속 %d회·누적 %d회). "
                "요청은 캐시 미스로 계속 처리됩니다(학생 노출 없음).",
                operation,
                error_type,
                self._consecutive_failures,
                self._get_failures + self._set_failures,
            )

    def record_success(self) -> None:
        """정상 캐시 연산 1건 관측 — 강등 중이었다면 해소를 info로 남기고 연속을 0으로."""
        if self._consecutive_failures:
            self._logger.info(
                "Redis 캐시 강등 해소 — 직전 연속 실패 %d회(마지막 예외 타입: %s)",
                self._consecutive_failures,
                self._last_error_type,
            )
            self._consecutive_failures = 0

    def snapshot(self) -> CacheDegradationSnapshot:
        """현재 회계의 불변 스냅샷."""
        return CacheDegradationSnapshot(
            get_failures=self._get_failures,
            set_failures=self._set_failures,
            consecutive_failures=self._consecutive_failures,
            last_error_type=self._last_error_type,
        )

    def reset(self) -> None:
        """회계 초기화 — 테스트 격리용(프로덕션 경로는 호출하지 않는다)."""
        self._get_failures = 0
        self._set_failures = 0
        self._consecutive_failures = 0
        self._last_error_type = None


# 프로세스 전역 회계 — RedisCache 인스턴스가 여럿(app.state 기본 캐시·사전적재 CLI 등)이어도
# "이 프로세스가 캐시 없이 버틴 횟수"는 하나로 합산돼야 운영 판정이 된다. 인스턴스별 격리가
# 필요한 테스트는 `RedisCache(degradation=CacheDegradationCounter())`로 새 카운터를 주입한다.
_PROCESS_DEGRADATION = CacheDegradationCounter()


def cache_degradation_snapshot() -> CacheDegradationSnapshot:
    """프로세스 전역 캐시 강등 회계 스냅샷 — 운영 노출·진단의 읽기 표면.

    아직 `/health/ready` body에는 싣지 않는다(배선은 후속 — app.py 응답 스키마 변경이
    이 태스크 범위 밖). 지금은 이 접근자로 인프로세스 판정치가 *존재*하며, 관측 SaaS
    없이도 읽을 수 있다는 점만 보장한다.
    """
    return _PROCESS_DEGRADATION.snapshot()


def reset_cache_degradation() -> None:
    """프로세스 전역 회계 초기화 — 테스트 격리용."""
    _PROCESS_DEGRADATION.reset()


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

    **소켓 타임아웃을 명시한다** (OPS-05): 무응답 Redis(패킷 블랙홀·방화벽 drop)는
    연결 거부(즉시 예외)보다 나쁘다 — 요청이 응답을 기다리며 매달리고, asyncio 워커가
    고갈되면 캐시 한 컴포넌트의 장애가 서비스 전체 마비로 번진다. 실측(설치본 redis-py
    8.0.1): `Redis.from_url(...)`에 타임아웃을 주지 않으면 connection_kwargs에 키 자체가
    들어가지 않고 Connection 기본값(5초)이 적용된다 — 즉 **값이 라이브러리 버전 기본값에
    종속**된다(pin `redis>=5.1.0`은 상한이 없어 버전에 따라 달라질 수 있다). 명시
    지정으로 버전 비의존이 되고, 값도 학생 요청 예산에 맞게(기본 2.0초) 좁힌다.
    타임아웃은 예외로 드러나 `RedisCache.get/set`이 캐시 미스로 강등한다 — 즉 이 설정의
    효과는 '요청 실패'가 아니라 '캐시 없이 계속 진행'이다.
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
    timeout_s = settings.redis_socket_timeout_s
    client = Redis.from_url(
        settings.redis_url,
        decode_responses=True,
        # 응답 대기(socket_timeout)·연결 수립(socket_connect_timeout) 둘 다 건다 — 하나만
        # 걸면 나머지 축에서 무한 대기가 그대로 남는다(연결은 되는데 응답이 없는 블랙홀,
        # 반대로 SYN이 drop되는 방화벽 — 두 실패 양상이 서로 다른 인자에 걸린다).
        socket_timeout=timeout_s,
        socket_connect_timeout=timeout_s,
    )
    return cast(_RedisClient, client)


class RedisCache:
    """Redis 기반 응답 캐시 — interfaces.CacheBackend 충족.

    파이프라인은 라우터가 만든 키로 get/set만 호출하고(03a §F.1), 이 백엔드는 그 키를
    *불투명하게* Redis에 저장·조회한다. TTL은 redis 네이티브 만료(SET ... EX)로
    실제 적용된다(InMemoryCache는 기록만 했던 것과 대비 — S2의 핵심 차이).

    클라이언트는 지연 생성(lazy)·주입 가능(injectable)하다 — 테스트는 인메모리 가짜
    클라이언트를 `client=`로 넣고, 프로덕션은 기본 redis.asyncio 클라이언트를 첫
    사용 시 생성한다(라이브 Redis 없이도 앱 구성·단위테스트가 가능하도록).

    **장애 강등(OPS-05)**: get/set은 어떤 예외도 호출자에게 전파하지 않는다 — get 실패는
    미스(None), set 실패는 no-op으로 강등하고 예외 타입명을 로그·카운터에 남긴다. 근거와
    우선순위 해석은 모듈 docstring '장애 강등' 절 참조.
    """

    def __init__(
        self,
        *,
        client: _RedisClient | None = None,
        settings: Settings | None = None,
        degradation: CacheDegradationCounter | None = None,
    ) -> None:
        # 주입된 클라이언트가 있으면 그것을 쓰고, 없으면 첫 사용 시 기본 생성(지연).
        self._client = client
        self._settings = settings
        # 기본은 프로세스 전역 회계(인스턴스가 여럿이어도 합산) — 테스트는 새 카운터 주입.
        self._degradation = degradation if degradation is not None else _PROCESS_DEGRADATION

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

    @property
    def degradation_count(self) -> int:
        """이 캐시가 쓰는 회계의 누적 강등 횟수(get+set) — 인프로세스 판정치."""
        return self._degradation.snapshot().total_failures

    def degradation_snapshot(self) -> CacheDegradationSnapshot:
        """이 캐시가 쓰는 회계의 불변 스냅샷(연산별 실패·연속 실패·마지막 예외 타입)."""
        return self._degradation.snapshot()

    async def get(self, key: str) -> str | None:
        """키로 캐시 조회. 미스면 None (CacheBackend 구현).

        반환값은 디코드된 str이다. redis가 bytes를 줄 수 있어 `_decode`로 방어적
        정규화한다(기본 클라이언트는 decode_responses=True라 보통 str). 반환 텍스트는
        *검증 전 원시 출력*이다(모듈 docstring 경계 메모 참조).

        **장애 강등(OPS-05)**: 연결 실패·타임아웃·프로토콜 오류 등 *어떤* 예외도 전파하지
        않고 **None(=캐시 미스)** 으로 강등한다. 미스는 파이프라인이 이미 아는 정상 상태라
        (재생성) 학생은 그대로 서비스받고, 비용만 더 든다 — CLAUDE.md 우선순위 #1(학생
        안전·웰빙) ≫ #6(비용·효율)의 직접 구현이다. 흡수해도 침묵하지 않는다: 예외
        타입명이 warning 로그와 강등 카운터에 남는다(키·값은 로그하지 않는다).

        try 범위에 클라이언트 지연 생성과 `_decode`까지 넣는 이유: 잘못된 redis_url·
        라이브러리 미설치(생성 단계 RuntimeError)·손상된 값(UnicodeDecodeError)도 결국
        "캐시를 못 쓰는 상태"라 같은 강등으로 다뤄야 학생 경로가 안 깨진다.
        """
        try:
            raw = await self._get_client().get(key)
            decoded = _decode(raw)
        except Exception as exc:  # noqa: BLE001 — 캐시 장애를 학생 대면 실패로 전파 금지
            self._degradation.record_failure(_OP_GET, exc)
            return None
        self._degradation.record_success()
        return decoded

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

        **장애 강등(OPS-05)**: 저장 실패는 예외를 전파하지 않고 **no-op**으로 강등한다
        (best-effort). 적재 실패의 유일한 대가는 다음 동일 요청의 재생성 비용이며, 그것
        때문에 지금 응답을 이미 만들어 낸 학생 요청을 5xx로 죽이는 것은 우선순위 위반이다
        (#1 학생 ≫ #6 비용). get과 마찬가지로 예외 타입명을 로그·카운터에 남긴다.
        """
        try:
            client = self._get_client()
            if ttl_seconds <= 0:
                # EX 0/음수는 redis가 거부 → 만료 없이 저장(무기한 폴백).
                await client.set(key, value)
            else:
                await client.set(key, value, ex=ttl_seconds)
        except Exception as exc:  # noqa: BLE001 — 캐시 장애를 학생 대면 실패로 전파 금지
            self._degradation.record_failure(_OP_SET, exc)
            return
        self._degradation.record_success()

    async def ping(self) -> bool:
        """Redis 도달성 확인 — 도달 True, 실패 False (예외 흡수).

        향후 레디니스(/status)용으로 제공한다. ollama의 check_status가 도달 불가를
        비크래시 상태로 흡수하듯, 연결 오류를 예외로 던지지 않고 False로 보고한다.

        반환 계약은 종전 그대로다(bool). OPS-05가 바꾼 것은 둘: ①이 호출도 기본
        클라이언트의 소켓 타임아웃 적용 대상이라 무응답 Redis에서 무한 대기하지 않는다
        ②흡수하되 예외 *타입명*을 debug 로그에 남긴다(침묵 실패 금지 — 값·키는 제외).
        warning이 아니라 debug인 이유: 레디니스 폴링 경로의 *정식* 보고 표면은
        `ops/service_health.check_redis`(타입명을 `/health/ready` body에 싣는다)이고,
        여기서 warning을 또 찍으면 같은 사건이 이중으로 시끄러워진다. 강등 카운터에도
        넣지 않는다 — 이 메서드는 *캐시 사용 경로*가 아니라 도달성 조회다(회계 오염 방지).
        """
        try:
            result = await self._get_client().ping()
        except Exception as exc:  # noqa: BLE001 — 도달 불가를 비크래시 False로 흡수
            logger.debug("Redis ping 실패 — 예외 타입: %s", type(exc).__name__)
            return False
        # redis ping은 보통 True(또는 b"PONG")를 돌려준다. 도달했으면 truthy.
        return bool(result)
