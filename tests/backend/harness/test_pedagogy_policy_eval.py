"""교수법 policy 승격 게이트 CLI — 안전제약·측정 미달 판정 (PED-03·hermetic).

이 게이트는 **지금 통과하지 않는 것이 정상**이다(실 트래픽 0 → 표본 미달). 테스트가 못 박는 것은
"실패한다"가 아니라 **"올바른 이유로 실패하고, 조건이 바뀌면 판정이 뒤집힌다"** 이다:

  - 안전제약 축: 제약 ON이면 위반 0, **끄면 위반 > 0**(변별력 — 제약이 장식이 아님).
  - 성과 축: 표본 미달이면 추정치를 내지 않고(`None`) exit 1, **표본을 채우면 뒤집힌다**
    (항상 실패하는 죽은 게이트가 아님).
"""

from __future__ import annotations

import json
from pathlib import Path

from whymath_backend.harness.pedagogy_policy_eval import (
    evaluate_performance,
    evaluate_safety,
    main,
)


class TestSafetyAxis:
    def test_no_violation_with_constraint_on(self) -> None:
        verdict = evaluate_safety(samples_per_cell=40, seed=11)
        assert verdict.trials > 0
        assert verdict.violations == 0
        assert verdict.passed

    def test_control_off_produces_violations(self) -> None:
        """**변별력** — 안전제약을 끄면 배제 대상이 실제로 뽑힌다.

        위 테스트의 "위반 0"이 "아무것도 검사하지 않아서 0"이 아님을 증명한다. 대조군에서 잡히는
        전략은 게이트가 시도 전 막는 완전예제다.
        """
        verdict = evaluate_safety(samples_per_cell=40, seed=11, safety_on=False)
        assert verdict.violations > 0
        assert not verdict.passed
        assert any("WORKED_EXAMPLE" in ex for ex in verdict.examples)


class TestPerformanceAxis:
    def test_empty_log_is_unmeasurable_not_failing_score(self) -> None:
        """표본 0은 "성과 0"이 아니라 **미상** — 추정치를 내지 않는다."""
        verdict = evaluate_performance([], min_samples=10)
        assert verdict.samples == 0
        assert not verdict.measurable
        assert verdict.snips_estimate is None
        assert verdict.snips_lower is None

    def test_becomes_measurable_with_enough_matched_samples(self) -> None:
        """**변별력** — 표본을 채우면 측정 가능으로 뒤집힌다(죽은 게이트가 아님).

        행동 policy가 결정론 규칙표이므로, 로그의 전략이 목표 policy 선택과 일치하는 표본만
        가중치를 받는다. "회고" 상황의 규칙표 선택을 그대로 로그로 만들어 일치시킨다.
        """
        from whymath_backend.harness.pedagogy_policy_eval import _SIGNAL_GRID
        from whymath_backend.l4.pedagogy.runtime_selector import decide

        label, signals = _SIGNAL_GRID[0]
        logged_strategy = decide(signals).strategy.value
        logged = [(label, logged_strategy, i % 2 == 0) for i in range(20)]
        verdict = evaluate_performance(logged, min_samples=10)
        assert verdict.measurable
        assert verdict.samples == 20
        assert verdict.snips_estimate == 0.5
        assert verdict.snips_lower is not None
        assert verdict.snips_lower < verdict.snips_estimate  # 하한이 점추정보다 보수적

    def test_mismatched_strategy_gets_zero_weight(self) -> None:
        """목표 policy가 고르지 않는 전략의 로그는 가중치 0(결정론 행동 policy의 귀결)."""
        logged = [("회고", "NOT_THE_RULE_CHOICE", True) for _ in range(50)]
        assert evaluate_performance(logged, min_samples=1).samples == 0


class TestCliExit:
    def test_exits_1_on_sample_starvation(self, capsys: object) -> None:
        """현재 상태 — 안전제약은 통과하나 표본 미달로 exit 1(정직한 미승격)."""
        assert main(["--samples-per-cell", "20"]) == 1

    def test_exits_1_on_safety_violation(self) -> None:
        assert main(["--samples-per-cell", "20", "--control-safety-off"]) == 1

    def test_exits_0_when_both_axes_pass(self, tmp_path: Path) -> None:
        """**변별력** — 두 축이 모두 충족되면 exit 0. 게이트가 뒤집힐 수 있음을 증명한다."""
        from whymath_backend.harness.pedagogy_policy_eval import _SIGNAL_GRID
        from whymath_backend.l4.pedagogy.runtime_selector import decide

        label, signals = _SIGNAL_GRID[0]
        strategy = decide(signals).strategy.value
        log_path = tmp_path / "logged.json"
        log_path.write_text(
            json.dumps([[label, strategy, True] for _ in range(30)]), encoding="utf-8"
        )
        argv = ["--samples-per-cell", "20", "--min-samples", "10", "--logged-json", str(log_path)]
        assert main(argv) == 0
