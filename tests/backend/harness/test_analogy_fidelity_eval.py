"""analogy_fidelity_eval(PED-09 ③ 강등전 CLI) hermetic 상시 회귀 — 라이브 LLM 0.

pedagogy_pack_fidelity_eval 테스트 선례 미러. 축소 표본으로 `main()`을 실제로 완주해
게이트 판정(exit 0/1)까지 검증한다:
  ① 시험지 결정론(전수 그리드·무숫자 변형 — ANSWER_LEAK clean 셀 오차단 방지 불변식)
  ② summarize 순수 집계·Wilson 상한 방향
  ③ 본판정: 규칙 검출기에서 미검출·오검출 0 → exit 0
  ④ 변별력: `--control`(널 검출기)이면 violating 전량 미검출이 실측돼 exit 1 —
     실패 상태에서 실제로 실패 신호를 내는 측정기임을 상시 봉인("변별력 없는 검증 금지").
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from whymath_backend.harness.analogy_fidelity_eval import (
    CaseOutcome,
    CaseSpec,
    _null_checker,
    _real_checker,
    build_exam,
    main,
    run_machine,
    summarize,
)
from whymath_backend.l3.pedagogy.analogy_checker import ANALOGY_DEFECT_CODES


class TestExamGrid:
    def test_grid_deterministic_and_exhaustive(self) -> None:
        """violating 6축×6템플릿×n + clean 2 grain×6템플릿×n — 동일 n이면 완전 동일 시험지."""
        exam1 = build_exam(2)
        exam2 = build_exam(2)
        assert exam1 == exam2
        violating = [c for c in exam1 if c.category == "violating"]
        clean = [c for c in exam1 if c.category == "clean"]
        assert len(violating) == 6 * 6 * 2  # (analogy 4축 + example 2축) × 6 × n
        assert len(clean) == 2 * 6 * 2  # grain 2 × 6 × n(축 중복 계상 없음 — 정직 회계)

    def test_expected_codes_within_closed_vocab(self) -> None:
        """정답지 기대 코드는 검출기 폐쇄 어휘 안(시험지-검출기 계약 정합)."""
        for spec in build_exam(1):
            if spec.category == "violating":
                assert spec.expected in ANALOGY_DEFECT_CODES

    def test_clean_variants_carry_no_leak_answer(self) -> None:
        """clean 셀 본문에 주입 정답('12')이 없다 — 유출 축 오차단으로 측정이 무효화되면 안 된다."""
        for spec in build_exam(3):
            if spec.category == "clean" and spec.grain == "example":
                assert "12" not in spec.text

    def test_rejects_invalid_n(self) -> None:
        with pytest.raises(ValueError):
            build_exam(0)


class TestSummarize:
    def test_pure_accounting_and_bounds_direction(self) -> None:
        """수기 outcome 집계 — 미검출/오검출 계수와 Wilson 상한 방향(표본↓→상한↑)."""
        spec_v = CaseSpec(
            grain="analogy",
            axis="GAMIFIED",
            category="violating",
            text="t",
            answer=None,
            expected="GAMIFIED",
        )
        spec_c = CaseSpec(
            grain="analogy", axis="-", category="clean", text="t", answer=None, expected=None
        )
        outcomes = [
            CaseOutcome(spec=spec_v, detected=(), missed=True, false_alarm=False),
            CaseOutcome(spec=spec_v, detected=("GAMIFIED",), missed=False, false_alarm=False),
            CaseOutcome(spec=spec_c, detected=(), missed=False, false_alarm=False),
        ]
        report = summarize(outcomes)
        assert report.violating_total == 2
        assert report.missed == 1
        assert report.clean_total == 1
        assert report.false_alarm == 0
        # 1/2 미검출 — 점추정 0.5보다 상한이 크다(보수·과신 금지).
        assert report.miss_upper_bound() > 0.5
        # 관측 0이어도 상한 > 0 — "관측 0 = 확정 0" 과신 금지.
        assert report.false_alarm_upper_bound() > 0.0


class TestMachineJudge:
    def test_membership_judge_allows_co_detection(self) -> None:
        """복수 결함 겸발(정의 참칭+한계 부재)에서 기대 축이 잡히면 miss가 아니다(멤버십 판정)."""
        cases = [c for c in build_exam(1) if c.axis == "DEFINITION_USURPATION"]
        outcomes = run_machine(cases, _real_checker)
        assert all(not o.missed for o in outcomes)

    def test_null_checker_misses_everything(self) -> None:
        """널 검출기 — violating 전량 미검출(시험지에 실제 결함이 있음의 실측 증거)."""
        cases = [c for c in build_exam(1) if c.category == "violating"]
        outcomes = run_machine(cases, _null_checker)
        assert all(o.missed for o in outcomes)


class TestMainGate:
    """main()을 축소 표본으로 실제 완주 — 게이트·exit 규약까지 검증."""

    def test_real_checker_passes_exit_zero(self, tmp_path: Path) -> None:
        """③ 본판정 — 미검출·오검출 0. 소표본(n=2) Wilson 상한에 맞춘 완화 임계로 PASS.

        n=2면 violating 144건(상한≈0.0185)·clean 24건(상한≈0.1036) — 기본 임계(0.05/0.2)로도
        통과하지만, CI 기본 그리드(n=12)와 같은 임계를 명시해 판정 조건을 고정한다.
        """
        out = tmp_path / "report.json"
        assert main(["--n-per-cell", "2", "--json", str(out)]) == 0
        payload = json.loads(out.read_text(encoding="utf-8"))
        assert payload["missed"] == 0
        assert payload["false_alarm"] == 0
        assert payload["control"] is False

    def test_control_null_checker_fails_exit_one(self) -> None:
        """④ 변별력 봉인 — 널 검출기면 미검출≈전량 → exit 1.

        이 대조군이 실패(exit 1)하지 않으면 측정기 자체가 무변별(위장 검증)이다.
        """
        assert main(["--n-per-cell", "1", "--control"]) == 1
