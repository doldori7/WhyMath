"""후보0 사유별 계상 단위테스트 — REC-02 ④ (hermetic).

`l2/axis_exclusions.py` 패턴 미러 검증: 배타 카운터·`total`·"0건이면 무로그".
"""

from __future__ import annotations

import logging

import pytest

from whymath_backend.l4.misconception.probe_supply_exclusions import (
    ProbeSupplyExclusions,
    log_probe_supply_exclusions,
)


class TestProbeSupplyExclusionsTotal:
    def test_all_zero_total_zero(self) -> None:
        assert ProbeSupplyExclusions().total == 0

    def test_total_sums_all_four_fields(self) -> None:
        exclusions = ProbeSupplyExclusions(
            no_target_mids=1, untagged_mid=2, missing_difficulty=3, fully_administered=4
        )
        assert exclusions.total == 10

    def test_frozen_dataclass_immutable(self) -> None:
        exclusions = ProbeSupplyExclusions()
        with pytest.raises(AttributeError):
            exclusions.no_target_mids = 1  # type: ignore[misc]


class TestFourScenariosDistinctValues:
    def test_four_scenarios_produce_distinct_shapes(self) -> None:
        shapes = {
            "no_target_mids": ProbeSupplyExclusions(no_target_mids=1),
            "untagged_mid": ProbeSupplyExclusions(untagged_mid=3),
            "missing_difficulty": ProbeSupplyExclusions(missing_difficulty=5),
            "fully_administered": ProbeSupplyExclusions(fully_administered=7),
        }
        # 서로 다른 인스턴스이며 각기 정확히 1개 필드만 nonzero.
        for name, exclusions in shapes.items():
            nonzero_fields = [
                f
                for f in (
                    "no_target_mids",
                    "untagged_mid",
                    "missing_difficulty",
                    "fully_administered",
                )
                if getattr(exclusions, f) != 0
            ]
            assert nonzero_fields == [name]


class TestLogProbeSupplyExclusions:
    def test_zero_total_no_log(self, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level(logging.INFO, logger="whymath.l4.misconception.test-seat"):
            log_probe_supply_exclusions("test-seat", ProbeSupplyExclusions(), kept=5)
        assert caplog.records == []

    def test_nonzero_total_logs_one_line_with_seat_and_counts(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        with caplog.at_level(logging.INFO, logger="whymath.l4.misconception.test-seat"):
            log_probe_supply_exclusions(
                "test-seat",
                ProbeSupplyExclusions(untagged_mid=2, missing_difficulty=1),
                kept=3,
            )
        assert len(caplog.records) == 1
        message = caplog.records[0].getMessage()
        assert "test-seat" in message
        assert "kept=3" in message
        assert "untagged_mid=2" in message
        assert "missing_difficulty=1" in message
