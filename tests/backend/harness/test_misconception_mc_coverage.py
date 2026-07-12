"""오개념 MC 코퍼스의 crosswalk 커버리지 기여 — machine-decidable 상승 봉인(순수·결정론·LLM 0).

`crosslink_demotion_eval`의 커버리지 회계는 kebab이 문항 `distractor_map`에 등장할 때 그 문항의
성취기준으로부터 kebab 성취기준을 역유도한다(`derive_kebab_standards`). 이 배치의 3 서브밴드가
각 kebab을 ≥24문항으로 등장시켜 그 3 kebab을 machine-decidable로 만든다(no_signal→구조 신호 有).

핵심 봉인: ① 3 kebab이 전부 정본 카탈로그(CATALOG_BY_ID)의 실재 오개념(회계 분모에 포함) ②
배치 산출 코퍼스에서 각 kebab이 count≥24로 등장하고 성취기준이 역유도됨 ③ 커밋 코퍼스 전체에
대해 machine-decidable이 ≥8(5→8 상승·회귀 아님) + 정답 오거부 0.
"""

from __future__ import annotations

from pathlib import Path

from whymath_backend.harness.crosslink_demotion_eval import (
    _default_misconceptions,
    _default_problem_corpora,
    run,
)
from whymath_backend.harness.misconception_mc_batch import run_misconception_mc_batch
from whymath_backend.l1.problem_bank.populate import load_problem_bank_records
from whymath_backend.l4.misconception.catalog import CATALOG_BY_ID
from whymath_backend.l4.misconception.crosslink_standard_signal import (
    derive_kebab_problem_counts,
    derive_kebab_standards,
)

_NEW_KEBABS: dict[str, str] = {
    "distribution-over-power": "[9수02-19]",
    "chain-rule-inner-derivative-omitted": "[12미적Ⅰ-02-01]",
    "sine-distributes-over-sum": "[12미적Ⅱ-02-02]",
    # 신규 5종(op-code 부재) — 커버리지 8→13.
    "exponent-zero": "[9수02-08]",
    "square-root-positivity": "[9수01-07]",
    "log-distribution": "[12대수01-05]",
    "composite-function-commutes": "[10공수2-03-02]",
    "period-of-scaled-sine": "[12미적Ⅱ-02-02]",
    # Tier B 계산가능(값형) 4종.
    "fraction-cancellation": "[9수01-04]",
    "angle-sum-non-triangle": "[9수03-05]",
    "area-perimeter-confusion": "[6수03-11]",
    "circle-radius-squared": "[10공수2-01-04]",
}


class TestKebabsAreCatalogued:
    def test_kebabs_in_catalog(self) -> None:
        # ① 회계 분모(CATALOG_BY_ID)에 실재해야 decidable 카운트에 잡힌다.
        for kebab in _NEW_KEBABS:
            assert kebab in CATALOG_BY_ID


class TestBatchCoverageContribution:
    def test_new_kebabs_decidable_with_count_ge_24(self, tmp_path: Path) -> None:
        # ② 배치 산출 코퍼스에서 8 kebab이 각각 count≥24·성취기준 역유도됨(derive_kebab_standards).
        out = tmp_path / "problems.jsonl"
        run_misconception_mc_batch(n_per_band=24, out_path=out, write=True)
        records = load_problem_bank_records(out)

        standards = derive_kebab_standards(records)
        counts = derive_kebab_problem_counts(records)
        for kebab, code in _NEW_KEBABS.items():
            assert counts.get(kebab, 0) >= 24  # 오답 귀인 문항 ≥24
            assert code in standards.get(kebab, frozenset())  # 성취기준 역유도

        # 이 코퍼스만으로도 신규 kebab들이 machine-decidable(구조 신호 有).
        decidable = sum(1 for k in CATALOG_BY_ID if standards.get(k))
        assert decidable >= 12


class TestCommittedCorpusCoverageRise:
    def test_committed_corpora_decidable_at_least_27(self) -> None:
        # ③ 커밋 코퍼스 전체 회계 — machine-decidable ≥27(수치평가 15+개념형 7+Tier B 5)·오거부 0.
        report, _ = run(
            problem_corpora=_default_problem_corpora(),
            misconceptions=_default_misconceptions(),
            cross_per_positive=60,
            same_per_positive=60,
        )
        assert report.kebabs_decidable >= 27
        assert report.positive_false_reject == 0
