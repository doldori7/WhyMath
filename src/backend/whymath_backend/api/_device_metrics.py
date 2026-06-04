"""디바이스 서명 검증 실패 metric — 슬라이스 28 (production spoofing 가시성).

`_client_device_id`의 fail-safe None 분기는 *조용히 device 차원을 비활성*시켜 정상 사용자
경험을 보존(요청 자체는 user+IP만 적용해 통과)하지만, 그 자체로는 *공격 시도 가시성 0*이다.
본 모듈은 *왜* fail-safe가 발동했는지(서명 누락·잘못된 sig·미등록 device 등) 분기별 카운터로
기록 — 운영자가 spoofing 폭주·앱 버그·중간 인증서 인터셉트 등을 *조기 감지*할 수 있다.

**범위 v1**: 인메모리 카운터(단일 프로세스). 다중 워커/HA 시 워커별 분리(rate_limit 인메모리
backend와 같은 한계). production OTel/Langfuse 결선은 후속 슬라이스 — 본 슬라이스는 *hook
도입*만(카운터 추가는 후속에서 OTel exporter로 매핑 가능).

**카운터 카테고리**:
  - `store_no_sig` — store 활성, X-Device-Sig 헤더 누락(앱 버전 mismatch 의심)
  - `store_verify_failed` — store 활성, sig 검증 실패(잘못된/위조 sig·미등록 device·폐기 device)
  - `shared_no_sig` — store 미설정·공유 secret 활성, sig 누락
  - `shared_invalid_sig` — store 미설정·공유 secret 활성, sig 불일치

**관측 패턴**: 정상 트래픽은 *모든 카운터 0*. spoofing 시도 시 해당 카운터 증가 → 운영
대시보드/alerting에서 임계 초과 시 알림.
"""

from __future__ import annotations

from collections import Counter
from typing import Literal

DeviceSigFailureReason = Literal[
    "store_no_sig",
    "store_verify_failed",
    "shared_no_sig",
    "shared_invalid_sig",
]

# 모듈 전역 카운터 — 단일 프로세스 인메모리.
_FAILURE_COUNTS: Counter[str] = Counter()


def record_device_sig_failure(reason: DeviceSigFailureReason) -> None:
    """`_client_device_id`의 fail-safe 분기에서 호출 — 사유별 카운터 +1."""
    _FAILURE_COUNTS[reason] += 1


def get_device_sig_failures() -> dict[str, int]:
    """현재 카운터 스냅샷 — 운영자/테스트 조회. 빈 사유는 키 0(Counter 의미)."""
    return dict(_FAILURE_COUNTS)


def reset_device_sig_failures() -> None:
    """테스트 격리·운영 reset(예: 시간창 rollover) — 모든 카운터 0."""
    _FAILURE_COUNTS.clear()
