"""⑧ 정답 위치 분포 카이제곱 검정 단위테스트(품질 15축 ⑧·ARCH-19) — 순수·결정론·hermetic.

`answer_position`(단일 항목 위치 판정)·`tally_positions`(배치 집계+malformed 정직 회계)·
`chi_square_uniform_test`(균등분포 대비 적합도 검정)를 검증한다.
"""

from __future__ import annotations

import math

from whymath_backend.l1.problem_bank.answer_distribution import (
    answer_position,
    chi_square_uniform_test,
    tally_positions,
)


class TestAnswerPosition:
    def test_found_returns_index(self) -> None:
        assert answer_position(["0", "1", "2", "3"], "2") == 2

    def test_not_found_returns_none(self) -> None:
        assert answer_position(["0", "1", "2", "3"], "9") is None

    def test_none_answer_returns_none(self) -> None:
        assert answer_position(["0", "1", "2", "3"], None) is None


class TestTallyPositions:
    def test_counts_matching_length_items(self) -> None:
        pairs = [(["0", "1", "2", "3"], "0"), (["0", "1", "2", "3"], "2")]
        counts, malformed = tally_positions(pairs, n_positions=4)
        assert counts == {0: 1, 2: 1}
        assert malformed == 0

    def test_mismatched_choice_length_counted_as_malformed(self) -> None:
        # 조용히 버리지 않고 별도 집계(정직 회계) — 다른 카테고리 수는 같은 검정에 섞을 수 없다.
        pairs = [(["0", "1", "2", "3"], "0"), (["0", "1", "2"], "1")]
        counts, malformed = tally_positions(pairs, n_positions=4)
        assert counts == {0: 1}
        assert malformed == 1

    def test_answer_not_in_choices_counted_as_malformed(self) -> None:
        pairs = [(["0", "1", "2", "3"], "9")]
        counts, malformed = tally_positions(pairs, n_positions=4)
        assert counts == {}
        assert malformed == 1


class TestChiSquareUniformTest:
    def test_perfectly_uniform_not_skewed(self) -> None:
        counts = {0: 25, 1: 25, 2: 25, 3: 25}
        result = chi_square_uniform_test(counts, n_positions=4)
        assert result.n_items == 100
        assert not result.is_skewed(0.05)
        assert result.p_value == 1.0

    def test_extreme_skew_detected(self) -> None:
        # 전량이 위치 0 — 카이제곱이 최댓값으로 반응, p→0.
        counts = {0: 100, 1: 0, 2: 0, 3: 0}
        result = chi_square_uniform_test(counts, n_positions=4)
        assert result.is_skewed(0.05)
        assert result.p_value < 1e-10

    def test_zero_items_not_skewed_and_marked(self) -> None:
        # 대상 부재를 "균등"으로 위장하지 않는다 — n_items=0이 리포트에 그대로 남는다.
        result = chi_square_uniform_test({}, n_positions=4)
        assert result.n_items == 0
        assert math.isnan(result.statistic)
        assert math.isnan(result.p_value)
        assert not result.is_skewed(0.05)

    def test_malformed_passthrough(self) -> None:
        result = chi_square_uniform_test({0: 10, 1: 10, 2: 10, 3: 10}, n_positions=4, malformed=3)
        assert result.malformed == 3

    def test_real_corpus_snapshot_is_skewed(self) -> None:
        # ARCH-19 실측(2026-07-29) — 실 코퍼스 1,631문 스냅샷 재현(회귀 앵커, 원본 통계와 대조).
        counts = {0: 511, 1: 410, 2: 349, 3: 361}
        result = chi_square_uniform_test(counts, n_positions=4)
        assert result.n_items == 1631
        assert result.is_skewed(0.05)
        assert result.p_value < 1e-6
