"""개념형 개수 MC 배치 테스트 — 수율·라운드트립(answer_kind 보존)·결정론·S6·커버리지(hermetic).

배치가 게이트(개수 SymPy 검증) 통과분만 적재하고, answer_kind가 로더·재검증에 보존되며, 2 kebab이
machine-decidable로 승격됨을 동결한다.
"""

from __future__ import annotations

from pathlib import Path

from whymath_backend.harness import corpus_reverify as cr
from whymath_backend.harness.conceptual_count_mc_batch import run_conceptual_count_mc_batch
from whymath_backend.harness.crosslink_demotion_eval import (
    _default_misconceptions,
    _default_problem_corpora,
    run,
)
from whymath_backend.l1.problem_bank.populate import load_problem_bank_records
from whymath_backend.l4.misconception.crosslink_standard_signal import derive_kebab_standards

_KEBABS = {"discriminant-negative-no-real-root", "critical-point-implies-extremum"}


def test_dry_run_full_yield() -> None:
    report = run_conceptual_count_mc_batch(
        n_per_band=24, out_path=Path("/nonexistent/never.jsonl"), write=False
    )
    assert report.fulfilled
    assert [(b.name, b.stored) for b in report.bands] == [
        ("discriminant-negative-no-real-root", 24),
        ("critical-point-implies-extremum", 24),
    ]


def test_roundtrip_preserves_answer_kind(tmp_path: Path) -> None:
    out = tmp_path / "problems.jsonl"
    report = run_conceptual_count_mc_batch(n_per_band=24, out_path=out, write=True)
    assert report.fulfilled and report.written == 48
    records = load_problem_bank_records(out)
    kinds = {r.verify.answer_kind for r in records}
    assert kinds == {"real_root_count", "extremum_count"}
    for r in records:
        assert r.verify.answer_kind in ("real_root_count", "extremum_count")
        assert r.verify.answer_map == {}  # 개수는 근 대입 아님
        assert r.problem.choices == ["0", "1", "2", "3"]
        assert r.problem.answer in r.problem.choices


def test_rerun_byte_identical(tmp_path: Path) -> None:
    a, b = tmp_path / "a.jsonl", tmp_path / "b.jsonl"
    run_conceptual_count_mc_batch(n_per_band=24, out_path=a, write=True)
    run_conceptual_count_mc_batch(n_per_band=24, out_path=b, write=True)
    assert a.read_bytes() == b.read_bytes()


def test_s6_reverify_zero_fail(tmp_path: Path) -> None:
    # 개수 문항이 S6 재검증에서 SymPy 독립 계산으로 전건 pass(콘텐츠 무결성).
    out = tmp_path / "problems.jsonl"
    run_conceptual_count_mc_batch(n_per_band=24, out_path=out, write=True)
    records = cr._iter_records(out.read_text(encoding="utf-8"))
    report = cr.reverify_corpus(records, use_fuzz=False)
    assert report.failed == 0 and report.passed == 48


def test_committed_corpus_covers_two_kebabs() -> None:
    # 커밋 코퍼스 전체 — 2 개념형 kebab이 machine-decidable(구조 신호 有)·정답 오거부 0.
    records = []
    for path in _default_problem_corpora():
        records.extend(load_problem_bank_records(path))
    derived = derive_kebab_standards(records)
    for kebab in _KEBABS:
        assert kebab in derived  # 문항 등장 → 성취기준 역유도됨
    report, _ = run(
        problem_corpora=_default_problem_corpora(),
        misconceptions=_default_misconceptions(),
        cross_per_positive=60,
        same_per_positive=60,
    )
    assert report.kebabs_decidable >= 17
    assert report.positive_false_reject == 0
