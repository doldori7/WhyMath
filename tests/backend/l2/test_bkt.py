"""L2 BKT 숙달 확률 추정 단위테스트 (hermetic·순수 알고리즘).

파라미터 검증(범위·비퇴화)·사후/학습/갱신/예측 수식·시퀀스 수렴을 결정론적으로 검증한다.
"""

from __future__ import annotations

import math

import pytest
from pydantic import ValidationError
from whymath_backend.l2.bkt import (
    DEFAULT_BKT_PARAMETERS,
    BktModel,
    BktParameters,
    apply_forgetting,
    apply_learning,
    posterior_mastery,
    probability_correct,
    update_mastery,
)

# 기본 파라미터: p_init=0.3·p_transit=0.1·p_slip=0.1·p_guess=0.2
_P = DEFAULT_BKT_PARAMETERS


class TestBktParameters:
    def test_defaults_valid(self) -> None:
        assert _P.p_init == 0.3
        assert _P.p_slip + _P.p_guess < 1.0

    def test_custom_valid(self) -> None:
        p = BktParameters(p_init=0.5, p_transit=0.2, p_slip=0.05, p_guess=0.25)
        assert p.p_init == 0.5

    @pytest.mark.parametrize("field", ["p_init", "p_transit", "p_slip", "p_guess"])
    def test_out_of_range_rejected(self, field: str) -> None:
        with pytest.raises(ValidationError):
            BktParameters(**{field: 1.5})
        with pytest.raises(ValidationError):
            BktParameters(**{field: -0.1})

    def test_degenerate_slip_plus_guess_rejected(self) -> None:
        """p_slip + p_guess >= 1 → 비식별(정답이 믿음을 낮춤) → ValueError."""
        with pytest.raises(ValidationError, match="비퇴화"):
            BktParameters(p_slip=0.6, p_guess=0.5)
        # 경계: 정확히 1.0도 거부
        with pytest.raises(ValidationError, match="비퇴화"):
            BktParameters(p_slip=0.5, p_guess=0.5)

    def test_frozen(self) -> None:
        with pytest.raises(ValidationError):
            _P.p_init = 0.9  # type: ignore[misc]


class TestPosteriorMastery:
    def test_correct_raises_belief(self) -> None:
        """정답 관측은 사후 숙달 확률을 사전보다 *높인다*(비퇴화 파라미터)."""
        assert posterior_mastery(0.3, True, _P) == pytest.approx(0.27 / 0.41)
        assert posterior_mastery(0.3, True, _P) > 0.3

    def test_incorrect_lowers_belief(self) -> None:
        """오답 관측은 사후를 사전보다 *낮춘다*."""
        assert posterior_mastery(0.3, False, _P) == pytest.approx(0.03 / 0.59)
        assert posterior_mastery(0.3, False, _P) < 0.3

    def test_prior_out_of_range_rejected(self) -> None:
        with pytest.raises(ValueError, match="prior"):
            posterior_mastery(1.5, True, _P)
        with pytest.raises(ValueError, match="prior"):
            posterior_mastery(-0.1, False, _P)

    def test_zero_denominator_returns_prior(self) -> None:
        """prior=0·guess=0·정답 → 분모 0(정보 없음) → 사전 그대로."""
        params = BktParameters(p_guess=0.0, p_slip=0.1)
        assert posterior_mastery(0.0, True, params) == 0.0


class TestApplyLearning:
    def test_transit_zero_unchanged(self) -> None:
        params = BktParameters(p_transit=0.0)
        assert apply_learning(0.4, params) == 0.4

    def test_transit_one_reaches_full(self) -> None:
        params = BktParameters(p_transit=1.0)
        assert apply_learning(0.4, params) == pytest.approx(1.0)

    def test_monotone_increase(self) -> None:
        """학습 전이는 숙달 확률을 (전이>0이면) 올린다."""
        assert apply_learning(0.4, _P) > 0.4


class TestUpdateMastery:
    def test_correct_increases(self) -> None:
        assert update_mastery(0.3, True, _P) == pytest.approx(0.6927, abs=1e-4)

    def test_incorrect_decreases(self) -> None:
        assert update_mastery(0.3, False, _P) == pytest.approx(0.1458, abs=1e-4)
        assert update_mastery(0.3, False, _P) < 0.3


class TestProbabilityCorrect:
    def test_formula(self) -> None:
        # P(✓)=0.3*0.9 + 0.7*0.2 = 0.41
        assert probability_correct(0.3, _P) == pytest.approx(0.41)

    def test_bounds(self) -> None:
        # mastery=1 → 1-slip·mastery=0 → guess
        assert probability_correct(1.0, _P) == pytest.approx(1.0 - _P.p_slip)
        assert probability_correct(0.0, _P) == pytest.approx(_P.p_guess)

    def test_monotone_in_mastery(self) -> None:
        assert probability_correct(0.8, _P) > probability_correct(0.2, _P)

    def test_out_of_range_rejected(self) -> None:
        with pytest.raises(ValueError, match="mastery"):
            probability_correct(1.5, _P)


class TestBktModel:
    def test_default_model_initial_mastery(self) -> None:
        model = BktModel()
        assert model.initial_mastery == _P.p_init

    def test_update_matches_function(self) -> None:
        model = BktModel()
        assert model.update(0.3, True) == update_mastery(0.3, True, _P)

    def test_sequence_all_correct_converges_up(self) -> None:
        """연속 정답은 숙달 확률을 1에 수렴시킨다."""
        model = BktModel()
        final = model.update_sequence([True] * 8)
        assert final > 0.99
        assert final <= 1.0

    def test_sequence_all_incorrect_converges_down(self) -> None:
        """연속 오답은 숙달 확률을 낮춘다(전이 하한까지)."""
        model = BktModel()
        final = model.update_sequence([False] * 8)
        assert final < 0.2

    def test_sequence_respects_explicit_prior(self) -> None:
        model = BktModel()
        assert model.update_sequence([True], prior=0.5) == update_mastery(0.5, True, _P)

    def test_predict_correct(self) -> None:
        model = BktModel()
        assert model.predict_correct(0.3) == probability_correct(0.3, _P)

    def test_custom_params_model(self) -> None:
        params = BktParameters(p_init=0.6, p_slip=0.05, p_guess=0.1, p_transit=0.2)
        model = BktModel(params)
        assert model.initial_mastery == 0.6
        assert model.params is params


class TestForgetting:
    """slice L2-6: 망각(시간 감쇠) — 사전값 초과 숙달분을 경과일에 따라 지수 감쇠."""

    def test_default_p_forget_zero(self) -> None:
        assert _P.p_forget == 0.0

    def test_p_forget_negative_rejected(self) -> None:
        with pytest.raises(ValidationError):
            BktParameters(p_forget=-0.1)

    def test_p_forget_above_one_allowed(self) -> None:
        # 확률이 아니라 *율*이라 1 초과 허용(빠른 감쇠).
        assert BktParameters(p_forget=2.0).p_forget == 2.0

    def test_no_decay_when_rate_zero(self) -> None:
        assert apply_forgetting(0.9, 100.0, BktParameters()) == 0.9

    def test_no_decay_when_elapsed_zero(self) -> None:
        assert apply_forgetting(0.9, 0.0, BktParameters(p_forget=0.1)) == 0.9

    def test_negative_elapsed_no_decay(self) -> None:
        assert apply_forgetting(0.9, -5.0, BktParameters(p_forget=0.1)) == 0.9

    def test_decays_toward_p_init(self) -> None:
        """0.9(gain 0.6 위 p_init 0.3)·λ=0.05·10일 → 0.3 + 0.6·exp(-0.5)."""
        p = BktParameters(p_forget=0.05)
        expected = 0.3 + 0.6 * math.exp(-0.5)
        assert apply_forgetting(0.9, 10.0, p) == pytest.approx(expected)
        # 원래보다 낮고 사전보다 높음(완전 망각 아님)
        assert p.p_init < apply_forgetting(0.9, 10.0, p) < 0.9

    def test_more_elapsed_more_decay(self) -> None:
        p = BktParameters(p_forget=0.05)
        assert apply_forgetting(0.9, 30.0, p) < apply_forgetting(0.9, 10.0, p)

    def test_below_p_init_unchanged(self) -> None:
        """사전 이하(미숙달)는 망각이 건드리지 않음(얻은 것만 잃음)."""
        p = BktParameters(p_forget=0.5)
        assert apply_forgetting(0.2, 10.0, p) == 0.2  # 0.2 < p_init 0.3

    def test_model_method_matches_function(self) -> None:
        model = BktModel(BktParameters(p_forget=0.05))
        assert model.apply_forgetting(0.9, 10.0) == apply_forgetting(0.9, 10.0, model.params)
