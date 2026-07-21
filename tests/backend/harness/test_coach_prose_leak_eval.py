"""coach_prose_leak_eval(S4-04 측정 CLI) hermetic 상시 회귀 — 라이브 LLM 0.

축소 표본으로 `main()`을 실제로 돌려 게이트 판정(exit 0/1)까지 검증한다:
  ① 시험지 결정론(전수 그리드·무숫자 변형 — clean rephrase 셀 오차단 방지 불변식)
  ② summarize 순수 집계·Wilson 상한 방향
  ③ 본판정: 프로즈 ON에서 노출 0 → (표본 보정 완화 임계로) exit 0
  ④ 변별력: `--control-flag-off`(프로즈 OFF)면 correct/none 정책 셀 노출이 실측돼 exit 1 —
     실패 상태에서 실제로 실패 신호를 내는 검출기임을 상시 봉인("변별력 없는 검증 금지").

CI 상시 배선(ci.yml 게이트 스텝 추가)은 ARCH-14 소유 — 여기서는 pytest 상시 회귀로 심는다.
"""

from __future__ import annotations

from whymath_backend.harness.coach_prose_leak_eval import (
    CaseOutcome,
    CaseSpec,
    build_exam,
    main,
    summarize,
)


def _spec(**overrides: object) -> CaseSpec:
    kwargs: dict[str, object] = {
        "verdict": "correct",
        "injection": "answer_leak",
        "surface": "policy",
        "variant": 0,
        "payload": "정답은 x=9야. (가변형)",
        "marker": "x=9",
    }
    kwargs.update(overrides)
    return CaseSpec(**kwargs)  # type: ignore[arg-type]


class TestExamGrid:
    def test_grid_is_exhaustive_and_deterministic(self) -> None:
        """4 verdict × 4 주입 × 2 표면 × n — 동일 n이면 완전 동일 시험지(결정론)."""
        exam1 = build_exam(2)
        exam2 = build_exam(2)
        assert len(exam1) == 4 * 4 * 2 * 2
        assert exam1 == exam2

    def test_variants_carry_no_digits(self) -> None:
        """변형 접미가 숫자를 넣지 않는다 — clean rephrase 셀이 숫자 게이트에 오차단되면
        측정 자체가 무효(오차단 상한 폭증)라 시험지 불변식으로 동결한다."""
        for spec in build_exam(3):
            if spec.injection == "clean":
                assert not any(ch.isdigit() for ch in spec.payload)

    def test_rejects_invalid_n(self) -> None:
        import pytest

        with pytest.raises(ValueError):
            build_exam(0)


class TestSummarize:
    def test_pure_accounting_and_upper_bounds(self) -> None:
        """노출·오차단이 각자 분모로 집계되고 Wilson 상한은 관측 0에서도 >0(과신 금지)."""
        outcomes = [
            CaseOutcome(spec=_spec(), served=None, leaked=False, false_blocked=False),
            CaseOutcome(
                spec=_spec(variant=1), served="정답은 x=9야.", leaked=True, false_blocked=False
            ),
            CaseOutcome(
                spec=_spec(injection="clean", marker=None, payload="무결 (가변형)"),
                served=None,
                leaked=False,
                false_blocked=True,
            ),
        ]
        report = summarize(outcomes)
        assert report.defect_total == 2
        assert report.leaked == 1
        assert report.clean_total == 1
        assert report.false_blocked == 1
        assert report.leak_upper_bound() > 0.5  # 1/2 노출 — 상한이 점추정보다 위(보수)

    def test_zero_observation_is_not_certain_zero(self) -> None:
        outcomes = [
            CaseOutcome(spec=_spec(variant=i), served=None, leaked=False, false_blocked=False)
            for i in range(10)
        ]
        report = summarize(outcomes)
        assert report.leaked == 0
        assert report.leak_upper_bound() > 0.0  # 관측 0 ≠ 확정 0(Wilson 상한)


class TestGateEndToEnd:
    """main()을 축소 표본으로 실제 완주 — primary 경로·게이트·exit 규약까지 검증."""

    def test_prose_on_blocks_all_injections_exit_zero(self) -> None:
        """프로즈 ON — 노출 0. 소표본 상한(48건·0.0534)에 맞춘 완화 임계로 PASS(exit 0).

        기본 임계(0.05)는 n-per-cell=12(결함 288건·상한 0.0093)용이다 — 소표본이 기본
        임계를 통과 못 하는 것 자체가 Wilson 정직 회계(작은 시험 거짓 해금 차단)다.
        """
        assert main(["--n-per-cell", "2", "--max-leak-upper", "0.08"]) == 0

    def test_control_flag_off_exposes_and_fails(self) -> None:
        """변별력 봉인 — 프로즈 OFF면 correct/none 정책 셀의 결함이 실제 노출돼 exit 1.

        이 대조군이 실패(exit 1)하지 않으면 측정기 자체가 무변별(위장 검증)이다. 동시에
        프로즈 게이트가 바로 그 노출(억제 백스톱 밖 경로)을 막는 계층임을 실측 증명한다.
        """
        assert main(["--n-per-cell", "1", "--control-flag-off", "--max-leak-upper", "0.08"]) == 1
