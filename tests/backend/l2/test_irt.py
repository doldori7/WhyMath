"""L2 IRT(문항반응이론) 단위테스트 (hermetic·순수 알고리즘).

2PL 정답확률 수식·능력 θ MLE 추정(Newton·경계·수렴)을 결정론적으로 검증한다.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from whymath_backend.l2.irt import (
    IrtItem,
    estimate_ability,
    item_information,
    probability_correct,
    select_next_item,
)


class TestIrtItem:
    def test_defaults_rasch(self) -> None:
        """discrimination 기본 1.0(Rasch/1PL)."""
        item = IrtItem(difficulty=0.5)
        assert item.difficulty == 0.5
        assert item.discrimination == 1.0

    def test_discrimination_must_be_positive(self) -> None:
        with pytest.raises(ValidationError):
            IrtItem(difficulty=0.0, discrimination=0.0)
        with pytest.raises(ValidationError):
            IrtItem(difficulty=0.0, discrimination=-1.0)

    def test_frozen(self) -> None:
        with pytest.raises(ValidationError):
            IrtItem(difficulty=0.0).difficulty = 1.0  # type: ignore[misc]


class TestProbabilityCorrect:
    def test_half_at_theta_equals_difficulty(self) -> None:
        assert probability_correct(0.0, IrtItem(difficulty=0.0)) == pytest.approx(0.5)
        assert probability_correct(1.5, IrtItem(difficulty=1.5)) == pytest.approx(0.5)

    def test_monotone_in_theta(self) -> None:
        item = IrtItem(difficulty=0.0)
        assert (
            probability_correct(-2.0, item)
            < probability_correct(0.0, item)
            < probability_correct(2.0, item)
        )

    def test_harder_item_lower_probability(self) -> None:
        """같은 θ에서 난이도 높을수록 정답 확률 낮음."""
        assert probability_correct(0.0, IrtItem(difficulty=2.0)) < probability_correct(
            0.0, IrtItem(difficulty=-2.0)
        )

    def test_discrimination_steepness(self) -> None:
        """변별도 높으면 b 위/아래에서 더 극단적(가파른 곡선)."""
        easy_disc = IrtItem(difficulty=0.0, discrimination=0.5)
        sharp_disc = IrtItem(difficulty=0.0, discrimination=2.0)
        # θ=1(>b)에서 변별도 높은 문항이 더 높은 확률
        assert probability_correct(1.0, sharp_disc) > probability_correct(
            1.0, easy_disc
        )
        # θ=-1(<b)에서는 더 낮은 확률
        assert probability_correct(-1.0, sharp_disc) < probability_correct(
            -1.0, easy_disc
        )

    def test_bounds(self) -> None:
        item = IrtItem(difficulty=0.0)
        assert 0.0 < probability_correct(-10.0, item) < 0.01
        assert 0.99 < probability_correct(10.0, item) < 1.0


_ITEMS = [IrtItem(difficulty=0.0), IrtItem(difficulty=1.0), IrtItem(difficulty=-1.0)]


class TestEstimateAbility:
    def test_empty_returns_initial(self) -> None:
        assert estimate_ability([], initial=0.7) == 0.7

    def test_all_correct_returns_upper(self) -> None:
        assert estimate_ability([(it, True) for it in _ITEMS]) == 4.0

    def test_all_incorrect_returns_lower(self) -> None:
        assert estimate_ability([(it, False) for it in _ITEMS]) == -4.0

    def test_symmetric_responses_near_zero(self) -> None:
        """난이도 0 문항에 1정답·1오답 → MLE θ=0(대칭)."""
        item = IrtItem(difficulty=0.0)
        assert estimate_ability([(item, True), (item, False)]) == pytest.approx(
            0.0, abs=1e-6
        )

    def test_more_correct_higher_theta(self) -> None:
        easy = IrtItem(difficulty=-1.0)
        hard = IrtItem(difficulty=1.0)
        low = estimate_ability([(easy, True), (hard, False)])
        high = estimate_ability(
            [(easy, True), (hard, True), (IrtItem(difficulty=0.0), True)]
        )
        assert high > low

    def test_correct_on_hard_item_raises_theta(self) -> None:
        """어려운 문항을 맞히면 능력 추정이 더 높아짐(같은 정답 수라도)."""
        theta_hard = estimate_ability(
            [(IrtItem(difficulty=2.0), True), (IrtItem(difficulty=0.0), False)]
        )
        theta_easy = estimate_ability(
            [(IrtItem(difficulty=-2.0), True), (IrtItem(difficulty=0.0), False)]
        )
        assert theta_hard > theta_easy

    def test_clamped_to_bounds(self) -> None:
        """경계 인자 적용 — 추정 θ는 [lower, upper] 내."""
        theta = estimate_ability(
            [(IrtItem(difficulty=0.0), True), (IrtItem(difficulty=0.0), False)],
            lower=-2.0,
            upper=2.0,
        )
        assert -2.0 <= theta <= 2.0

    def test_deterministic(self) -> None:
        resp = [(_ITEMS[0], True), (_ITEMS[1], False), (_ITEMS[2], True)]
        assert estimate_ability(resp) == estimate_ability(resp)

    def test_discrimination_weights_evidence(self) -> None:
        """변별도 높은 문항의 응답이 θ 추정에 더 큰 영향."""
        # 고변별 문항 정답 + 저변별 문항 오답 → θ가 정답 쪽으로 더 끌림
        theta = estimate_ability(
            [
                (IrtItem(difficulty=0.0, discrimination=3.0), True),
                (IrtItem(difficulty=0.0, discrimination=0.3), False),
            ]
        )
        assert theta > 0.0  # 고변별 정답이 우세

    def test_max_iter_caps_iterations(self) -> None:
        """max_iter로 반복 상한 — 비대칭 응답이 1회 내 미수렴해도 종료(루프 소진 경로)."""
        resp = [
            (IrtItem(difficulty=0.0), True),
            (IrtItem(difficulty=1.0), True),
            (IrtItem(difficulty=-1.0), False),
        ]
        theta = estimate_ability(resp, max_iter=1)
        assert -4.0 <= theta <= 4.0  # 유효 범위·예외 없이 종료


class TestItemInformation:
    def test_max_at_theta_equals_difficulty(self) -> None:
        """정보는 θ=b(P=0.5)에서 최대 — 능력과 난이도 일치 시."""
        item = IrtItem(difficulty=0.0)
        at_b = item_information(0.0, item)
        assert at_b == pytest.approx(0.25)  # a²·0.5·0.5
        assert item_information(2.0, item) < at_b
        assert item_information(-2.0, item) < at_b

    def test_symmetric_around_difficulty(self) -> None:
        item = IrtItem(difficulty=1.0)
        assert item_information(0.0, item) == pytest.approx(item_information(2.0, item))

    def test_discrimination_squared_weight(self) -> None:
        """변별도 2배면 θ=b 정보는 4배(a² 가중)."""
        low = item_information(0.0, IrtItem(difficulty=0.0, discrimination=1.0))
        high = item_information(0.0, IrtItem(difficulty=0.0, discrimination=2.0))
        assert high == pytest.approx(4.0 * low)

    def test_non_negative(self) -> None:
        item = IrtItem(difficulty=0.0)
        assert item_information(-5.0, item) >= 0.0
        assert item_information(5.0, item) >= 0.0


class TestSelectNextItem:
    _POOL = [IrtItem(difficulty=-2.0), IrtItem(difficulty=0.0), IrtItem(difficulty=2.0)]

    def test_picks_difficulty_near_theta(self) -> None:
        assert select_next_item(0.0, self._POOL) == 1  # b=0
        assert select_next_item(2.0, self._POOL) == 2  # b=2
        assert select_next_item(-2.0, self._POOL) == 0  # b=-2

    def test_excludes_administered(self) -> None:
        # b=0 제외 → θ=0에서 b=-2·b=2 동률 → 낮은 인덱스 0
        assert select_next_item(0.0, self._POOL, administered={1}) == 0

    def test_all_administered_returns_none(self) -> None:
        assert select_next_item(0.0, self._POOL, administered={0, 1, 2}) is None

    def test_empty_pool_returns_none(self) -> None:
        assert select_next_item(0.0, []) is None

    def test_ties_lowest_index(self) -> None:
        """동일 정보량(같은 난이도)이면 낮은 인덱스."""
        pool = [IrtItem(difficulty=0.0), IrtItem(difficulty=0.0)]
        assert select_next_item(0.0, pool) == 0

    def test_discrimination_breaks_proximity(self) -> None:
        """난이도 같아도 변별도 높은 문항이 정보 많아 선택."""
        pool = [
            IrtItem(difficulty=0.0, discrimination=0.5),
            IrtItem(difficulty=0.0, discrimination=2.0),
        ]
        assert select_next_item(0.0, pool) == 1
