"""선수 traversal 계기화 hook — 파티션 트리거 지표 관측 (math_dsl_risk_register ④).

부채 ④(graph partition) 처방은 "도메인 파티션은 *마지막*·관측 트리거값을 **먼저 계기화**(노드 수·
p95 latency)". 이 모듈이 그 계기화의 *hook*이다 — `fetch_prerequisites`(프로덕션 선수 traversal)가
순회 규모(dedup 전 행 수)·결과 수·최대 깊이·소요 latency를 방출해, 운영자가 "수만 노드·순회 p95
상승·hub 오염"이 임계에 접근하는지 *실측*으로 본다(파티션 시점 판단 근거).

**범위 v1**(`api/_device_metrics.py` 관용 계승): 인메모리 히스토그램(단일 프로세스). 다중 워커/HA 시
워커별 분리(rate_limit·device 인메모리 backend와 같은 한계). **production OTel/Langfuse exporter
결선은 후속 슬라이스** — 본 슬라이스는 *hook 도입*만(버킷 카운터는 후속에서 OTel histogram
exporter로 매핑 가능). p95 HTTP 미들웨어·도메인 파티션 자체는 범위 밖(④ "파티션은 마지막").

**관측 패턴**: opt-in(`prerequisite_traversal_metrics_enabled`·기본 off)이라 켜기 전엔 방출 0(비용·
행동 불변). 켜면 traversal 1회 = 관측 1건이 버킷에 누적된다. 정상 규모는 낮은 버킷에 몰리고, 규모
도달 시 상위 버킷(노드 수·latency 꼬리)이 채워지며 p95가 우측 이동 → 파티션 트리거.
"""

from __future__ import annotations

from collections import Counter
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from whymath_backend.config import Settings

# 버킷 경계(상한·Prometheus le 식) — 관측값이 속하는 *첫* 버킷에 +1. 마지막 "+inf"는 초과 꼬리.
# 결과/순회 노드 수: 현재 규모(선수 소수)는 1~4에 몰리고, hub·다단계 폭증은 상위 버킷을 채운다.
_COUNT_BUCKETS: tuple[int, ...] = (1, 2, 4, 8, 16, 32, 64, 128)
# latency(ms): 로컬 PG 재귀 CTE는 수 ms가 정상. 파티션 임계는 p95가 100ms+ 꼬리로 이동할 때.
_LATENCY_BUCKETS_MS: tuple[float, ...] = (1.0, 5.0, 10.0, 25.0, 50.0, 100.0, 250.0, 500.0, 1000.0)

# 모듈 전역 인메모리 상태 — 단일 프로세스. 버킷 카운터 + running max/총건수.
_HISTOGRAMS: dict[str, Counter[str]] = {
    "result_count": Counter(),
    "visited_count": Counter(),
    "latency_ms": Counter(),
}
_MAX_DEPTH_SEEN: dict[str, int] = {"max_depth": 0}
_TOTAL: Counter[str] = Counter()


def _bucket_label(value: float, edges: tuple[float, ...] | tuple[int, ...]) -> str:
    """관측값이 속하는 첫 버킷(<= edge)의 라벨. 모든 edge 초과면 '+inf'(꼬리)."""
    for edge in edges:
        if value <= edge:
            # 정수 경계는 정수 라벨로(가독성) — count 버킷은 int, latency는 float.
            return f"<={int(edge)}" if float(edge).is_integer() else f"<={edge}"
    return "+inf"


def record_traversal(*, visited: int, result: int, max_depth: int, elapsed_ms: float) -> None:
    """traversal 1회 관측을 버킷에 기록 — visited(dedup 전 행)·result(cap 후)·max_depth·latency.

    순수 기록(부수효과=모듈 카운터). 게이팅은 `observe_traversal`이 담당하므로 여기선 무조건 기록
    한다(테스트가 직접 호출·결정론). `visited`는 재귀 CTE가 실제 훑은 행 수(hub/다단계 폭증의 1차
    신호), `result`는 dedup+cap 후 최종 크기다.
    """
    _HISTOGRAMS["result_count"][_bucket_label(result, _COUNT_BUCKETS)] += 1
    _HISTOGRAMS["visited_count"][_bucket_label(visited, _COUNT_BUCKETS)] += 1
    _HISTOGRAMS["latency_ms"][_bucket_label(elapsed_ms, _LATENCY_BUCKETS_MS)] += 1
    _MAX_DEPTH_SEEN["max_depth"] = max(_MAX_DEPTH_SEEN["max_depth"], max_depth)
    _TOTAL["traversals"] += 1


def observe_traversal(
    settings: Settings,
    *,
    visited: int,
    result: int,
    max_depth: int,
    elapsed_ms: float,
) -> None:
    """게이트+기록 — `prerequisite_traversal_metrics_enabled`가 True일 때만 `record_traversal`.

    `fetch_prerequisites`가 이 함수를 호출한다. 게이트 off(기본)면 no-op이라 방출 0·비용 불변
    (현행 비트동일). settings 주입이라 순수·hermetic 테스트 가능(fake settings로 on/off 검증).
    """
    if not settings.prerequisite_traversal_metrics_enabled:
        return
    record_traversal(visited=visited, result=result, max_depth=max_depth, elapsed_ms=elapsed_ms)


def get_traversal_metrics() -> dict[str, object]:
    """현재 관측 스냅샷 — 운영자/테스트 조회(후속 OTel exporter 매핑 지점).

    반환: 버킷별 카운트(result_count·visited_count·latency_ms)·max_depth(관측 최대)·총 traversal 수.
    빈 상태(미방출)면 히스토그램은 빈 dict·max_depth 0·total 0.
    """
    return {
        "result_count": dict(_HISTOGRAMS["result_count"]),
        "visited_count": dict(_HISTOGRAMS["visited_count"]),
        "latency_ms": dict(_HISTOGRAMS["latency_ms"]),
        "max_depth": _MAX_DEPTH_SEEN["max_depth"],
        "total": _TOTAL["traversals"],
    }


def reset_traversal_metrics() -> None:
    """테스트 격리·운영 reset(시간창 rollover) — 모든 관측 0."""
    for hist in _HISTOGRAMS.values():
        hist.clear()
    _MAX_DEPTH_SEEN["max_depth"] = 0
    _TOTAL.clear()
