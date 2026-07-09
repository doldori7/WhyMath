"""crosswalk 독립 구조 신호 테스트 — kebab 성취기준 역유도 + 대조(순수·hermetic·DB 0).

`standard_agreement` 3판정 순수 로직 + 커밋 문항 코퍼스에서 `derive_kebab_standards`의 실측
(극값·이차 kebab → 성취기준·미등장 kebab no_signal)을 동결한다.
"""

from __future__ import annotations

from pathlib import Path

from whymath_backend.l1.problem_bank.populate import load_problem_bank_records
from whymath_backend.l4.misconception.crosslink_standard_signal import (
    derive_kebab_standards,
    standard_agreement,
)

_REPO_ROOT = Path(__file__).resolve().parents[3]


def _all_problem_records() -> list[object]:
    records: list[object] = []
    for path in sorted((_REPO_ROOT / "data" / "corpus").glob("problem_bank_*/problems.jsonl")):
        records.extend(load_problem_bank_records(path))
    return records


class TestStandardAgreement:
    def test_agree_when_mid_standard_in_kebab_set(self) -> None:
        assert standard_agreement({"[12미적Ⅰ-02-07]"}, "[12미적Ⅰ-02-07]") == "agree"

    def test_disagree_when_no_overlap(self) -> None:
        assert standard_agreement({"[10공수1-02-02]"}, "[12미적Ⅰ-02-07]") == "disagree"

    def test_no_signal_when_kebab_empty(self) -> None:
        # 문항 미등장 kebab — 판정 불가(인간 폴백)·disagree로 위장 금지.
        assert standard_agreement(frozenset(), "[12미적Ⅰ-02-07]") == "no_signal"

    def test_no_signal_when_mid_standard_none(self) -> None:
        assert standard_agreement({"[10공수1-02-02]"}, None) == "no_signal"


class TestDeriveKebabStandards:
    def test_covered_kebabs_map_to_expected_standards(self) -> None:
        # 커밋 문항 코퍼스에서 역유도 — 극값 2·이차근 선택 3 kebab의 성취기준 실측 동결.
        derived = derive_kebab_standards(_all_problem_records())  # type: ignore[arg-type]
        assert derived["extremum-max-min-confused"] == frozenset({"[12미적Ⅰ-02-07]"})
        assert derived["extremum-value-vs-point-confused"] == frozenset({"[12미적Ⅰ-02-07]"})
        assert derived["opposite-root-selected"] == frozenset({"[10공수1-02-02]"})
        assert derived["factor-sign-flip"] == frozenset({"[10공수1-02-02]"})

    def test_uncovered_kebab_absent(self) -> None:
        # 문항에 오답 귀인으로 안 쓰이는 kebab은 유도 집합에 없음(→ no_signal·인간 전용).
        derived = derive_kebab_standards(_all_problem_records())  # type: ignore[arg-type]
        assert "square-root-positivity" not in derived
        # 커버는 소수(현 5)뿐 — 정직한 경계.
        assert len(derived) <= 10
