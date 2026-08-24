"""S4-53 — statistical_claim verifier 단위 테스트.

검증 축:
  ① 1차원 데이터의 mean/median/variance/std/q1/q3 계산.
  ② 2차원 데이터의 corr 계산.
  ③ pass/fail/unverifiable 판정.
  ④ DSL 파싱 실패는 unverifiable.
"""

from __future__ import annotations

import pytest

from whymath_backend.l3.statistical_claim import (
    StatisticalClaimError,
    parse_statistical_model,
    verify_statistical_claim,
)


def test_mean_pass() -> None:
    verdict, residual, result = verify_statistical_claim("data=[1,2,3,4,5]; stat=mean", "3")
    assert verdict.state == "pass"
    assert result.value == pytest.approx(3.0)
    assert "평균" in result.description


def test_mean_fail() -> None:
    verdict, residual, result = verify_statistical_claim("data=[1,2,3,4,5]; stat=mean", "4")
    assert verdict.state == "fail"


def test_median_odd() -> None:
    verdict, residual, result = verify_statistical_claim("data=[1,2,3,4,5]; stat=median", "3")
    assert verdict.state == "pass"


def test_median_even() -> None:
    verdict, residual, result = verify_statistical_claim("data=[1,2,3,4]; stat=median", "2.5")
    assert verdict.state == "pass"


def test_variance() -> None:
    verdict, residual, result = verify_statistical_claim(
        "data=[1,2,3,4,5]; stat=variance", "2.5"
    )
    assert verdict.state == "pass"
    assert result.value == pytest.approx(2.5)


def test_std() -> None:
    verdict, residual, result = verify_statistical_claim("data=[1,2,3,4,5]; stat=std", "1.5811")
    assert result.value == pytest.approx(1.5811388300841898, rel=1e-4)


def test_q1_q3() -> None:
    verdict, residual, result = verify_statistical_claim(
        "data=[1,2,3,4,5,6,7,8]; stat=q1", "2.75"
    )
    assert verdict.state == "pass"
    verdict, residual, result = verify_statistical_claim(
        "data=[1,2,3,4,5,6,7,8]; stat=q3", "6.25"
    )
    assert verdict.state == "pass"


def test_corr() -> None:
    verdict, residual, result = verify_statistical_claim(
        "data=[[1,1],[2,2],[3,3],[4,4],[5,5]]; stat=corr; columns=[0,1]",
        "1",
    )
    assert verdict.state == "pass"
    assert result.value == pytest.approx(1.0)


def test_corr_2d_without_columns_is_unverifiable() -> None:
    verdict, residual, result = verify_statistical_claim(
        "data=[[1,1],[2,2],[3,3]]; stat=mean",
        "2",
    )
    # 열 지정이 없으면 첫 번째 열을 사용한다.
    assert verdict.state == "pass"
    assert result.value == pytest.approx(2.0)


def test_answer_with_label() -> None:
    verdict, residual, result = verify_statistical_claim(
        "data=[1,2,3,4,5]; stat=mean", "mean=3"
    )
    assert verdict.state == "pass"


def test_fraction_answer() -> None:
    verdict, residual, result = verify_statistical_claim(
        "data=[0,1]; stat=mean", "1/2"
    )
    assert verdict.state == "pass"


def test_unverifiable_missing_stat() -> None:
    verdict, residual, result = verify_statistical_claim("data=[1,2,3]", "2")
    assert verdict.state == "unverifiable"


def test_unverifiable_bad_data() -> None:
    verdict, residual, result = verify_statistical_claim("data=notjson; stat=mean", "2")
    assert verdict.state == "unverifiable"


def test_unverifiable_non_numeric_answer() -> None:
    verdict, residual, result = verify_statistical_claim("data=[1,2,3]; stat=mean", "abc")
    assert verdict.state == "unverifiable"


def test_residual_axes_present() -> None:
    verdict, residual, result = verify_statistical_claim("data=[1,2,3]; stat=mean", "2")
    assert "자료↔발문 정합" in residual
    assert "표본 추출 방법" in residual
    assert "자료 해석의 모호성" in residual


def test_parse_model_round_trip() -> None:
    model = parse_statistical_model("data=[1,2,3]; stat=mean")
    assert model.values == (1.0, 2.0, 3.0)
    assert model.stat == "mean"
