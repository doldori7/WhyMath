"""선수 traversal 계기화 hook 단위테스트 — `l2._traversal_metrics` (④ graph partition·hermetic).

math_dsl_risk_register ④. hook(버킷 히스토그램 방출)·게이트(opt-in)·격리(reset)를 못 박는다. DB·앱
기동 불요(순수 인메모리·`api/_device_metrics.py` 패턴). 실 `fetch_prerequisites` 방출은 통합테스트
(실 PG)가 담당한다 — 여기선 hook 자체와 게이트 배선만 검증한다.
"""

from __future__ import annotations

import pytest

from whymath_backend.config import Settings
from whymath_backend.l2._traversal_metrics import (
    get_traversal_metrics,
    observe_traversal,
    record_traversal,
    reset_traversal_metrics,
)


@pytest.fixture(autouse=True)
def _isolate_metrics() -> None:
    """모듈 전역 상태를 각 테스트 전에 리셋(격리)."""
    reset_traversal_metrics()


class TestRecordTraversal:
    def test_empty_snapshot_before_any_record(self) -> None:
        """미방출 상태 — 히스토그램 빈 dict·max_depth 0·total 0."""
        snap = get_traversal_metrics()
        assert snap["result_count"] == {}
        assert snap["visited_count"] == {}
        assert snap["latency_ms"] == {}
        assert snap["max_depth"] == 0
        assert snap["total"] == 0

    def test_single_record_buckets_and_max(self) -> None:
        """1건 기록 — 각 값이 올바른 버킷에 +1·max_depth·total 반영."""
        record_traversal(visited=3, result=2, max_depth=2, elapsed_ms=7.0)
        snap = get_traversal_metrics()
        assert snap["visited_count"] == {"<=4": 1}  # 3 → 첫 버킷 <=4
        assert snap["result_count"] == {"<=2": 1}  # 2 → <=2
        assert snap["latency_ms"] == {"<=10": 1}  # 7ms → <=10
        assert snap["max_depth"] == 2
        assert snap["total"] == 1

    def test_boundary_value_lands_in_that_bucket(self) -> None:
        """경계값(<=edge)은 *그* 버킷에 — result=4 → '<=4'(다음 버킷 아님)."""
        record_traversal(visited=1, result=4, max_depth=1, elapsed_ms=1.0)
        assert get_traversal_metrics()["result_count"] == {"<=4": 1}

    def test_overflow_tail_bucket(self) -> None:
        """상위 경계 초과 — result 200(>128)·latency 2000ms(>1000) → '+inf' 꼬리 버킷."""
        record_traversal(visited=200, result=200, max_depth=9, elapsed_ms=2000.0)
        snap = get_traversal_metrics()
        assert snap["result_count"] == {"+inf": 1}
        assert snap["visited_count"] == {"+inf": 1}
        assert snap["latency_ms"] == {"+inf": 1}
        assert snap["max_depth"] == 9

    def test_accumulates_and_tracks_running_max_depth(self) -> None:
        """다건 누적 — 같은 버킷 카운트 증가·max_depth는 관측 최대 유지."""
        record_traversal(visited=2, result=2, max_depth=1, elapsed_ms=2.0)
        record_traversal(visited=2, result=2, max_depth=5, elapsed_ms=3.0)
        record_traversal(visited=2, result=2, max_depth=3, elapsed_ms=4.0)
        snap = get_traversal_metrics()
        assert snap["result_count"] == {"<=2": 3}
        assert snap["max_depth"] == 5  # running max(1,5,3)
        assert snap["total"] == 3

    def test_reset_clears_all(self) -> None:
        record_traversal(visited=5, result=5, max_depth=4, elapsed_ms=50.0)
        reset_traversal_metrics()
        snap = get_traversal_metrics()
        assert snap["total"] == 0
        assert snap["max_depth"] == 0
        assert snap["result_count"] == {}


class TestObserveGate:
    def test_disabled_is_noop(self) -> None:
        """게이트 off(기본) — observe_traversal이 아무것도 기록하지 않는다(방출 0·비용 불변)."""
        settings = Settings(prerequisite_traversal_metrics_enabled=False)
        observe_traversal(settings, visited=10, result=8, max_depth=3, elapsed_ms=42.0)
        assert get_traversal_metrics()["total"] == 0

    def test_enabled_records(self) -> None:
        """게이트 on — observe_traversal이 record_traversal로 위임해 관측 1건."""
        settings = Settings(prerequisite_traversal_metrics_enabled=True)
        observe_traversal(settings, visited=10, result=8, max_depth=3, elapsed_ms=42.0)
        snap = get_traversal_metrics()
        assert snap["total"] == 1
        assert snap["visited_count"] == {"<=16": 1}  # 10 → <=16
        assert snap["result_count"] == {"<=8": 1}  # 8 → <=8
        assert snap["latency_ms"] == {"<=50": 1}  # 42ms → <=50
        assert snap["max_depth"] == 3
