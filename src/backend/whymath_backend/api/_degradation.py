"""api 계층 Redis 의존 경로의 *장애 강등 회계* — OPS-06 공용 부품.

무엇을 위한 모듈인가
--------------------
OPS-05가 L3 응답 캐시(`l3/cache/redis_cache.py`)에서 확립한 규율 — **삼키되 침묵하지
않는다** — 을 api 계층의 나머지 Redis 소비처(`_device_store`의 verify/count 캐시,
`_rate_limit`의 RedisBackend)에서도 쓸 수 있게 일반화한 회계 부품이다.

왜 `l3.cache.redis_cache.CacheDegradationCounter`를 그대로 쓰지 않는가 (의도적 분리)
------------------------------------------------------------------------------------
그쪽 카운터는 연산 어휘가 캐시 전용(`Literal["get", "set"]`)으로 *타입 수준에서* 고정돼
있고, 로그 문구도 "Redis 캐시 강등 — 요청은 캐시 미스로 계속 처리됩니다"로 캐시 의미론에
결합돼 있다. api 계층의 강등은 연산 어휘(`get`/`setex`/`delete`/`hit`/`hit_many`)도,
*강등의 효과*도 다르다 — rate limit는 미스가 아니라 **인메모리 백엔드 폴백**이고, device
store의 `delete`는 아예 **강등하지 않고 예외를 전파**한다. 하나의 Literal에 다섯 어휘를
욱여넣고 효과 문구를 분기시키면 OPS-05가 동결한 테스트까지 흔들린다. 그래서 *복제*가
아니라 **일반화**를 여기 두고, L3 쪽은 건드리지 않는다(OPS-06 범위 밖).

설계 원칙 (CLAUDE.md)
---------------------
- **침묵 실패 금지**: 흡수하든 전파하든, 실패 지점마다 **예외 타입명**(`type(exc).__name__`)을
  로그에 남긴다. 키·값·시크릿은 절대 싣지 않는다(캐시 키에 device_id·user_id가 들어가고,
  값에는 디바이스 서명이 들어간다 — 미성년자 PII 인접 표면).
- **이중 회계**: 판정치를 외부 관측 SaaS에만 의존하지 않는다. 인프로세스 카운터가 항상
  남아 있어야 "측정 실패"와 "장애 0건"이 구분된다(`ops/service_health.ServiceMetrics`·
  OPS-05 `CacheDegradationCounter` 선례).
- **로그 스팸 억제**: 상태 전이(첫 실패)와 그 이후 N번째만 남긴다 — 지속 중임은 알리되
  알림 가치는 잃지 않는다.

동시성 메모: 스레드-안전 장치를 두지 않는다. 카운터 갱신은 `await` 없는 순수 동기 구간이라
단일 이벤트 루프에서 코루틴 인터리브로 쪼개지지 않는다(OPS-05와 동일 전제). 다중 *워커*
(프로세스)는 워커별 독립 회계다.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

logger = logging.getLogger(__name__)

# 연속 실패 중 로그를 남기는 주기(첫 실패는 항상 남긴다).
_LOG_EVERY_N_FAILURES = 100


@dataclass(frozen=True, slots=True)
class DegradationSnapshot:
    """강등 회계의 불변 스냅샷 — 노출·단정은 이 스냅샷 기준(읽는 중 변형 방지).

    `last_error_type`은 *가장 최근에 관측한* 실패의 예외 타입명이다(값·키는 담지 않는다).
    실패가 한 번도 없었으면 None — '오류 없음'이지 '오류를 모름'이 아니다.
    """

    failures: Mapping[str, int]
    consecutive_failures: int
    last_error_type: str | None
    last_operation: str | None

    @property
    def total_failures(self) -> int:
        """모든 연산의 누적 실패 횟수 — '이 프로세스가 Redis 없이 버틴 횟수'."""
        return sum(self.failures.values())

    @property
    def degraded(self) -> bool:
        """지금 강등 중인가 = 마지막으로 *관측된* 연산이 실패였는가.

        트래픽이 없으면 마지막 관측 그대로 남는다(오래된 True는 '그 후 시도가 없었다'는
        뜻이지 '지금 확실히 죽었다'가 아니다). 실시간 도달성 판정은 `/health/ready`의
        Redis 딥체크가 따로 한다 — 이 플래그는 *실제 사용 경로*의 관측이다.
        """
        return self.consecutive_failures > 0

    def failures_for(self, operation: str) -> int:
        """특정 연산의 누적 실패 횟수(한 번도 실패한 적 없으면 0)."""
        return self.failures.get(operation, 0)


class DegradationCounter:
    """실패를 세고, 상태 전이에서만 로그를 남기는 회계 — 하위 시스템별 1개.

    로그 정책(테스트로 동결):
      - **첫 실패**(정상→강등 전이)는 반드시 로그 — 예외 *타입명* 포함(침묵 실패 금지).
      - 연속 실패가 이어지면 `log_every_n_failures`번째마다만(스팸 억제).
      - 성공이 다시 관측되면 info 1회(해소) 후 연속 카운터를 0으로 — 다음 장애는 다시
        첫 실패 로그를 낸다.
      - 로그에 **키·값·시크릿은 절대 싣지 않는다**.

    `effect`를 호출자가 매번 명시하는 이유: 같은 하위 시스템 안에서도 연산마다 강등의
    *결과*가 다르다(캐시 미스 폴백 vs 예외 전파). 운영자가 로그 한 줄만 보고 "지금 학생에게
    무슨 일이 일어나는가"를 알 수 있어야 런북이 성립한다.
    """

    def __init__(
        self,
        subsystem: str,
        *,
        log_every_n_failures: int = _LOG_EVERY_N_FAILURES,
        target_logger: logging.Logger | None = None,
    ) -> None:
        self._subsystem = subsystem
        self._logger = target_logger if target_logger is not None else logger
        # 0·음수는 매 실패 로그(스팸)를 뜻하므로 최소 1로 클램프 — 설정 실수 방어.
        self._log_every_n = max(1, log_every_n_failures)
        self._failures: dict[str, int] = {}
        self._consecutive_failures = 0
        self._last_error_type: str | None = None
        self._last_operation: str | None = None

    def record_failure(
        self,
        operation: str,
        exc: BaseException,
        *,
        effect: str,
        level: int = logging.WARNING,
    ) -> None:
        """실패 1건 기록 + 정책에 따라 로그(예외 타입명·효과 문구 포함).

        `level`: 강등으로 흡수하는 연산은 WARNING, *전파*하는 연산(보안 계약상 강등 금지)은
        ERROR를 준다 — 후자는 학생·운영자에게 실제 오류로 드러나는 사건이다.
        """
        error_type = type(exc).__name__
        self._failures[operation] = self._failures.get(operation, 0) + 1
        self._consecutive_failures += 1
        self._last_error_type = error_type
        self._last_operation = operation
        if self._consecutive_failures == 1 or self._consecutive_failures % self._log_every_n == 0:
            self._logger.log(
                level,
                "%s 강등 — operation=%s 예외 타입: %s (연속 %d회·누적 %d회). %s",
                self._subsystem,
                operation,
                error_type,
                self._consecutive_failures,
                self.total_failures,
                effect,
            )

    def record_success(self) -> None:
        """정상 연산 1건 관측 — 강등 중이었다면 해소를 info로 남기고 연속을 0으로."""
        if self._consecutive_failures:
            self._logger.info(
                "%s 강등 해소 — 직전 연속 실패 %d회(마지막 예외 타입: %s·operation=%s)",
                self._subsystem,
                self._consecutive_failures,
                self._last_error_type,
                self._last_operation,
            )
            self._consecutive_failures = 0

    @property
    def total_failures(self) -> int:
        """누적 실패 횟수(모든 연산 합)."""
        return sum(self._failures.values())

    def snapshot(self) -> DegradationSnapshot:
        """현재 회계의 불변 스냅샷(연산별 실패·연속 실패·마지막 예외 타입)."""
        return DegradationSnapshot(
            failures=MappingProxyType(dict(self._failures)),
            consecutive_failures=self._consecutive_failures,
            last_error_type=self._last_error_type,
            last_operation=self._last_operation,
        )

    def reset(self) -> None:
        """회계 초기화 — 테스트 격리용(프로덕션 경로는 호출하지 않는다)."""
        self._failures.clear()
        self._consecutive_failures = 0
        self._last_error_type = None
        self._last_operation = None
