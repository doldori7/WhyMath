"""베이스라인 풀이율 측정 하네스 `run_baseline` 단위테스트 — WH-S S0(§9 게이트·§5 사다리·hermetic).

`baseline.py`는 검증기 스택(`verify_answer` Tier1 + `verify_solution` Tier2 + `final_verdict`
combiner)을 *문제셋*에 돌려 난이도 사다리(§5)별 풀이율(verified 비율)을 집계한다. 본 테스트는
**실제 검증기 스택의 조합 결과**로 집계가 정확한지 확인한다(canned 주입이 아니라 진짜 verify
호출 — 조합·결정론 회귀 방지).

검증되는 동작:
  - 밴드별 verified/unverified/failed 카운트·solve_rate(=verified/n) 정확.
  - 여러 밴드 혼합·답만(steps 없음) 항목·틀린 단계→failed→solve_rate 반영.
  - 빈 items → 5밴드 전부 n=0 + overall n=0의 빈 리포트(에러 아님).
  - 결정론(동일 입력 동일 리포트)·overall total 합산·밴드 순서(§5 사다리).
  - 정직성: solve_rate는 *verified만* 풀이로 셈(unverified/failed는 미해결).

검증기 스택의 실제 등급(probe 확인·고정 시드 결정론):
  - 등식 답 pass + correct 단계(예 ['2*x+2','2*(x+1)']) → verified.
  - 답 pass + 단계 없음 → verified(Tier1 pass·전이 0). 부등식·연립 답 pass도 verified.
  - 답 fail(틀린 답) → failed. 답 pass + incorrect 단계(['x+1','x+2']) → failed(틀린 과정 차단).
  - 파싱 불가 조건 → unverifiable answer → unverified(§3 격리).
"""

from __future__ import annotations

from whymath_backend.whs import (
    BandResult,
    BaselineReport,
    DifficultyBand,
    EvalItem,
    run_baseline,
)

# ──────────────────────────────────────────────────────────────────────────
# 등급별 EvalItem 팩토리 — 실제 verify 스택이 각 등급을 내도록 구성된 항목(probe 확인).
# ──────────────────────────────────────────────────────────────────────────


def _verified_with_steps(band: DifficultyBand) -> EvalItem:
    """등식 답 pass + correct 단계 → verified(Tier1 통과 + 전 단계 correct)."""
    return EvalItem(
        band=band,
        conditions="x**2 - 5*x + 6 = 0",
        answer={"x": "2"},
        steps=["2*x+2", "2*(x+1)"],  # 동치 변형 → correct 전이.
    )


def _verified_answer_only(band: DifficultyBand) -> EvalItem:
    """등식 답 pass + 단계 없음 → verified(Tier1 pass·전이 0이라 unverifiable 0)."""
    return EvalItem(
        band=band,
        conditions="x**2 - 5*x + 6 = 0",
        answer={"x": "3"},
    )


def _verified_inequality(band: DifficultyBand) -> EvalItem:
    """부등식 답 pass + 단계 없음 → verified."""
    return EvalItem(band=band, conditions="x > 0", answer={"x": "3"})


def _verified_system(band: DifficultyBand) -> EvalItem:
    """연립 답 pass + 단계 없음 → verified."""
    return EvalItem(
        band=band,
        conditions=["x+y=3", "x-y=1"],
        answer={"x": "2", "y": "1"},
    )


def _failed_wrong_answer(band: DifficultyBand) -> EvalItem:
    """틀린 답(Tier1 fail) → failed."""
    return EvalItem(
        band=band,
        conditions="x**2 - 5*x + 6 = 0",
        answer={"x": "5"},
    )


def _failed_wrong_step(band: DifficultyBand) -> EvalItem:
    """답 pass + incorrect 단계 → failed(틀린 과정 차단·§4 이중 체크)."""
    return EvalItem(
        band=band,
        conditions="x**2 - 5*x + 6 = 0",
        answer={"x": "2"},
        steps=["x+1", "x+2"],  # 비동치 → incorrect 전이.
    )


def _unverified(band: DifficultyBand) -> EvalItem:
    """파싱 불가 조건 → Tier1 unverifiable → unverified(§3 격리)."""
    return EvalItem(band=band, conditions="foobar(((", answer={"x": "1"})


# ──────────────────────────────────────────────────────────────────────────
# 헬퍼
# ──────────────────────────────────────────────────────────────────────────


def _band(report: BaselineReport, band: DifficultyBand) -> BandResult:
    """리포트에서 특정 밴드의 BandResult를 뽑는다."""
    matches = [b for b in report.bands if b.band == band]
    assert len(matches) == 1, f"밴드 {band}는 정확히 1개여야 함(5밴드 고정)"
    return matches[0]


# ──────────────────────────────────────────────────────────────────────────
# 빈 입력 — 빈 리포트(에러 아님)
# ──────────────────────────────────────────────────────────────────────────


def test_empty_items_returns_empty_report() -> None:
    """빈 items → 5밴드 전부 n=0 + overall n=0(정직한 빈 집계·에러 아님)."""
    report = run_baseline([])

    assert len(report.bands) == 5  # §5 사다리 5밴드 항상 포함.
    for band_result in report.bands:
        assert band_result.n == 0
        assert band_result.n_verified == 0
        assert band_result.n_unverified == 0
        assert band_result.n_failed == 0
        assert band_result.solve_rate == 0.0  # n=0 → 0.0(0 나눗셈 회피).

    assert report.overall.band is None
    assert report.overall.n == 0
    assert report.overall.solve_rate == 0.0


def test_bands_always_in_ladder_order() -> None:
    """bands는 §5 사다리 순서(교과기본→준킬러→킬러→KMO1차→KMO2차)로 고정 정렬."""
    report = run_baseline([])
    assert [b.band for b in report.bands] == [
        DifficultyBand.교과기본,
        DifficultyBand.준킬러,
        DifficultyBand.킬러,
        DifficultyBand.KMO1차,
        DifficultyBand.KMO2차,
    ]


# ──────────────────────────────────────────────────────────────────────────
# 단일 밴드 집계 — 등급별 카운트·solve_rate
# ──────────────────────────────────────────────────────────────────────────


def test_single_band_all_verified() -> None:
    """한 밴드에 verified 항목만 → n_verified=n·solve_rate=1.0."""
    band = DifficultyBand.교과기본
    items = [
        _verified_with_steps(band),
        _verified_answer_only(band),
        _verified_inequality(band),
        _verified_system(band),
    ]
    report = run_baseline(items)

    result = _band(report, band)
    assert result.n == 4
    assert result.n_verified == 4
    assert result.n_unverified == 0
    assert result.n_failed == 0
    assert result.solve_rate == 1.0


def test_single_band_mixed_grades_solve_rate() -> None:
    """한 밴드에 verified 2·unverified 1·failed 1 혼합 → solve_rate=2/4=0.5(verified만)."""
    band = DifficultyBand.킬러
    items = [
        _verified_with_steps(band),
        _verified_answer_only(band),
        _unverified(band),
        _failed_wrong_answer(band),
    ]
    report = run_baseline(items)

    result = _band(report, band)
    assert result.n == 4
    assert result.n_verified == 2
    assert result.n_unverified == 1
    assert result.n_failed == 1
    # 정직성: verified만 풀이로 셈(unverified·failed는 미해결).
    assert result.solve_rate == 0.5


def test_wrong_step_counts_as_failed() -> None:
    """답 pass라도 incorrect 단계 → failed(틀린 과정 차단)·solve_rate에 미반영."""
    band = DifficultyBand.준킬러
    items = [_failed_wrong_step(band)]
    report = run_baseline(items)

    result = _band(report, band)
    assert result.n == 1
    assert result.n_verified == 0
    assert result.n_failed == 1
    assert result.solve_rate == 0.0  # 틀린 과정은 풀이로 인정 안 함.


def test_answer_only_item_verified() -> None:
    """steps 없는(답만) 항목도 Tier1 pass면 verified로 집계."""
    band = DifficultyBand.KMO1차
    report = run_baseline([_verified_answer_only(band)])

    result = _band(report, band)
    assert result.n == 1
    assert result.n_verified == 1
    assert result.solve_rate == 1.0


def test_unverified_isolated_not_counted_as_solved() -> None:
    """unverified(§3 격리) 항목은 미해결로 셈 — solve_rate 0.0."""
    band = DifficultyBand.KMO2차
    report = run_baseline([_unverified(band)])

    result = _band(report, band)
    assert result.n == 1
    assert result.n_unverified == 1
    assert result.n_verified == 0
    assert result.solve_rate == 0.0


# ──────────────────────────────────────────────────────────────────────────
# 여러 밴드 혼합 — 밴드 격리·overall 합산
# ──────────────────────────────────────────────────────────────────────────


def test_multiple_bands_isolated_and_overall_totals() -> None:
    """여러 밴드 혼합 — 밴드별 격리 집계 + overall이 전체 합산과 일치."""
    items = [
        # 교과기본: verified 2 (solve_rate 1.0)
        _verified_with_steps(DifficultyBand.교과기본),
        _verified_answer_only(DifficultyBand.교과기본),
        # 킬러: verified 1·failed 1 (solve_rate 0.5)
        _verified_inequality(DifficultyBand.킬러),
        _failed_wrong_answer(DifficultyBand.킬러),
        # KMO2차: unverified 1·failed 1 (solve_rate 0.0)
        _unverified(DifficultyBand.KMO2차),
        _failed_wrong_step(DifficultyBand.KMO2차),
    ]
    report = run_baseline(items)

    base = _band(report, DifficultyBand.교과기본)
    assert (base.n, base.n_verified, base.n_failed, base.solve_rate) == (2, 2, 0, 1.0)

    killer = _band(report, DifficultyBand.킬러)
    assert (killer.n, killer.n_verified, killer.n_failed, killer.solve_rate) == (2, 1, 1, 0.5)

    kmo2 = _band(report, DifficultyBand.KMO2차)
    assert (kmo2.n, kmo2.n_verified, kmo2.n_unverified, kmo2.n_failed) == (2, 0, 1, 1)
    assert kmo2.solve_rate == 0.0

    # 항목 없는 밴드(준킬러·KMO1차)는 n=0 포함.
    assert _band(report, DifficultyBand.준킬러).n == 0
    assert _band(report, DifficultyBand.KMO1차).n == 0

    # overall — 전체 합산(verified 3·unverified 1·failed 2·n 6·solve_rate 3/6=0.5).
    assert report.overall.band is None
    assert report.overall.n == 6
    assert report.overall.n_verified == 3
    assert report.overall.n_unverified == 1
    assert report.overall.n_failed == 2
    assert report.overall.solve_rate == 0.5


def test_overall_equals_sum_of_bands() -> None:
    """overall의 등급별 카운트는 모든 밴드 카운트의 합과 항상 일치(불변식)."""
    items = [
        _verified_with_steps(DifficultyBand.교과기본),
        _failed_wrong_answer(DifficultyBand.준킬러),
        _unverified(DifficultyBand.킬러),
        _verified_system(DifficultyBand.KMO1차),
        _failed_wrong_step(DifficultyBand.KMO2차),
    ]
    report = run_baseline(items)

    assert report.overall.n == sum(b.n for b in report.bands)
    assert report.overall.n_verified == sum(b.n_verified for b in report.bands)
    assert report.overall.n_unverified == sum(b.n_unverified for b in report.bands)
    assert report.overall.n_failed == sum(b.n_failed for b in report.bands)
    # 등급 카운트 합 = n(누락 없음).
    for b in report.bands:
        assert b.n == b.n_verified + b.n_unverified + b.n_failed
    assert report.overall.n == (
        report.overall.n_verified + report.overall.n_unverified + report.overall.n_failed
    )


# ──────────────────────────────────────────────────────────────────────────
# 결정론
# ──────────────────────────────────────────────────────────────────────────


def test_deterministic_same_input_same_report() -> None:
    """동일 입력 → 동일 리포트(검증기 스택 고정 시드 상속·재현·회귀)."""
    items = [
        _verified_with_steps(DifficultyBand.교과기본),
        _failed_wrong_step(DifficultyBand.킬러),
        _unverified(DifficultyBand.KMO2차),
    ]
    report1 = run_baseline(items)
    report2 = run_baseline(items)
    assert report1 == report2


# ──────────────────────────────────────────────────────────────────────────
# 패키지 인식 — whs.__init__ export
# ──────────────────────────────────────────────────────────────────────────


def test_package_exports() -> None:
    """whs 패키지가 베이스라인 심볼을 export하는지(패키지 인식)."""
    import whymath_backend.whs as whs

    for name in ("BandResult", "BaselineReport", "DifficultyBand", "EvalItem", "run_baseline"):
        assert name in whs.__all__
        assert hasattr(whs, name)


def test_difficulty_band_korean_values() -> None:
    """DifficultyBand 값은 §5 한국어 라벨(직렬화 보존)."""
    assert DifficultyBand.교과기본.value == "교과기본"
    assert DifficultyBand.KMO2차.value == "KMO2차"
