"""앵커 탐지 채널 변별력 측정의 계약 동결 (MISC-07).

이 파일이 있는 이유 — **배선 실재성**
-------------------------------------
측정 CLI를 만들어 두고 아무도 돌리지 않으면 "저장소에 존재함"이지 "돌아감"이 아니다
(CLAUDE.md: 검증 장치를 만들고 배선 확인 없이 완료 선언 금지). `tests/backend`는 CI backend
잡이 매 PR 실행하므로, 여기서 `main([])`을 부르는 것이 곧 **게이트의 CI 배선**이다.

무엇을 동결하는가
-----------------
  1. 게이트가 지금 통과한다(exit 0) — 채널 회귀 시 적색.
  2. 게이트가 **통과 가능**하다 — 음성 표본이 적으면 오검출 0건에서도 상한을 못 넘어 완벽한
     채널이 FAIL한다. 그 상태를 "채널 실패"로 오독하지 않도록 별도 축으로 검사한다.
  3. 커버 회계가 정직하다 — 채널을 못 붙인 2종이 리포트에서 사라지지 않는다("3종 부여"를
     "5종 커버"로 읽지 못하게).
  4. 픽스처가 비어 있지 않다 — 0건 스캔은 공허한 통과다.
"""

from __future__ import annotations

from whymath_backend.harness.anchor_detection_channel_eval import (
    DETECTION_FLOOR,
    FALSE_POSITIVE_CEILING,
    UNCHANNELABLE,
    _gate_is_reachable,
    build_fixtures,
    build_report,
    main,
)
from whymath_backend.l4.misconception.catalog import CATALOG_BY_ID


class TestGatePasses:
    def test_cli_exits_zero(self) -> None:
        """CLI_게이트_통과 — 이 단언이 곧 CI 배선이다."""
        assert main([]) == 0

    def test_report_passed_flag(self) -> None:
        """리포트_통과_플래그"""
        assert build_report().passed is True


class TestGateIsReachable:
    """통과 가능성 — 완벽한 채널도 떨어뜨리는 게이트는 변별이 아니라 위장이다."""

    def test_every_channel_gate_can_be_passed(self) -> None:
        """모든_채널의_게이트가_도달_가능"""
        for fx in build_fixtures():
            assert _gate_is_reachable(len(fx.negatives)), (
                f"{fx.kebab_id}: 음성 {len(fx.negatives)}건으로는 오검출 0건에서도 "
                f"상한 {FALSE_POSITIVE_CEILING}을 통과할 수 없다"
            )

    def test_small_sample_is_reported_unreachable(self) -> None:
        """작은_표본은_도달불가로_판정된다 — 이 검사 자체의 변별력 확인"""
        # n=20에서 Wilson 상한(0/20)=0.1192 > 0.10 이므로 도달 불가여야 한다. 이 단언이
        # 없으면 `_gate_is_reachable`이 항상 True를 돌려줘도 위 테스트가 통과한다.
        assert not _gate_is_reachable(20)
        assert _gate_is_reachable(30)


class TestFixtureIntegrity:
    def test_no_channel_has_empty_fixtures(self) -> None:
        """픽스처_공백_없음 — 0건 스캔은 실패"""
        assert build_report().empty_fixture_channels == ()
        for fx in build_fixtures():
            assert fx.positives and fx.negatives, fx.kebab_id

    def test_fixture_targets_actually_have_channels(self) -> None:
        """픽스처_대상이_실제로_채널을_가진다"""
        for fx in build_fixtures():
            assert CATALOG_BY_ID[fx.kebab_id].regex_signals, fx.kebab_id

    def test_fixtures_are_deterministic(self) -> None:
        """픽스처_결정론 — 같은 입력에 같은 출력(난수·시각 의존 0)"""
        assert build_fixtures() == build_fixtures()


class TestHonestCoverageAccounting:
    """'채널 3종 부여'가 '앵커 커버 5종 해결'로 읽히지 않게 한다."""

    def test_unchannelable_entries_are_reported_with_reasons(self) -> None:
        """채널_불가_2종이_사유와_함께_보고된다"""
        coverage = build_report().to_json()["coverage"]
        assert isinstance(coverage, dict)
        listed = {u["kebab_id"] for u in coverage["unchannelable"]}
        assert listed == {"opposite-root-selected", "extremum-max-min-confused"}
        for u in coverage["unchannelable"]:
            assert u["reason"].strip(), u["kebab_id"]

    def test_unchannelable_entries_really_have_no_channel(self) -> None:
        """채널_불가로_적은_항목은_실제로_채널이_없다 — 선언과 사실의 대조"""
        for u in UNCHANNELABLE:
            assert not CATALOG_BY_ID[u.kebab_id].regex_signals, u.kebab_id
            assert CATALOG_BY_ID[u.kebab_id].canonical_wrong_form is None, u.kebab_id

    def test_coverage_total_is_channelled_plus_unchannelable(self) -> None:
        """커버_합계가_채널+불가와_일치"""
        coverage = build_report().to_json()["coverage"]
        assert isinstance(coverage, dict)
        assert coverage["anchor_covered_total"] == len(coverage["channelled"]) + len(
            coverage["unchannelable"]
        )


class TestThresholdsAreNamed:
    def test_thresholds_appear_in_report(self) -> None:
        """임계값이_리포트에_실린다 — 판정 기준이 숨지 않게"""
        thresholds = build_report().to_json()["thresholds"]
        assert thresholds == {
            "detection_floor": DETECTION_FLOOR,
            "false_positive_ceiling": FALSE_POSITIVE_CEILING,
        }


class TestJsonMirrorsObject:
    def test_json_passed_matches_object(self) -> None:
        """JSON과_객체의_판정이_일치 — 두 출력 경로가 갈라지지 않게"""
        report = build_report()
        assert report.to_json()["passed"] is report.passed

    def test_json_channel_count_matches(self) -> None:
        """JSON_채널수가_객체와_일치"""
        report = build_report()
        channels = report.to_json()["channels"]
        assert isinstance(channels, list)
        assert len(channels) == len(report.channels)
