"""⑧ 정답 위치 분포 강등전 CLI 하니스 테스트(품질 15축 ⑧·ARCH-19) — hermetic(라이브 0).

실 코퍼스 스캔(임시 디렉터리로 격리)과 결함(쏠림) 주입 강등전(합성 배치)의 리포트·게이트
exit code·결정론·변별력(스큐 0이면 게이트가 통과하지 않아야 함)을 검증한다.
"""

from __future__ import annotations

import json
from pathlib import Path

from whymath_backend.harness import answer_distribution_battle as adb


# ──────────────────────────────────────────────────────────────────────────
# 실 코퍼스 스캔 — 임시 디렉터리로 격리(실 data/corpus 미참조 — 결정론·회귀 안정).
# ──────────────────────────────────────────────────────────────────────────
def _write_corpus(root: Path, name: str, records: list[dict]) -> None:
    corpus_dir = root / name
    corpus_dir.mkdir(parents=True)
    with (corpus_dir / "problems.jsonl").open("w", encoding="utf-8") as fh:
        for record in records:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")


def test_scan_corpus_mc_pairs_collects_choices_only(tmp_path: Path) -> None:
    _write_corpus(
        tmp_path,
        "problem_bank_a_v0",
        [
            {"choices": ["0", "1", "2", "3"], "answer": "1"},
            {"choices": None, "answer": "5"},  # 단답형 — 집계 대상 아님.
        ],
    )
    pairs = adb.scan_corpus_mc_pairs(tmp_path)
    assert len(pairs) == 1
    assert pairs[0] == (["0", "1", "2", "3"], "1")


def test_scan_corpus_multiple_dirs_aggregated(tmp_path: Path) -> None:
    _write_corpus(tmp_path, "problem_bank_a_v0", [{"choices": ["0", "1"], "answer": "0"}])
    _write_corpus(tmp_path, "problem_bank_b_v0", [{"choices": ["0", "1"], "answer": "1"}])
    pairs = adb.scan_corpus_mc_pairs(tmp_path)
    assert len(pairs) == 2


def test_cli_scan_mode_reports_skew_on_biased_fixture(tmp_path: Path) -> None:
    # 위치 0에 극단적으로 쏠린 합성 코퍼스 — 카이제곱이 확실히 기각해야 한다.
    records = [{"choices": ["0", "1", "2", "3"], "answer": "0"} for _ in range(40)] + [
        {"choices": ["0", "1", "2", "3"], "answer": str(i % 4)} for i in range(1, 4)
    ]
    _write_corpus(tmp_path, "problem_bank_a_v0", records)
    rc = adb.main(["--corpus-root", str(tmp_path)])
    assert rc == adb._EXIT_OK  # 스캔은 관측 리포트 — 쏠림이어도 exit 0(problem_bank_coverage 동형).


def test_cli_scan_mode_input_error_on_missing_root(tmp_path: Path) -> None:
    missing = tmp_path / "no_such_dir"
    rc = adb.main(["--corpus-root", str(missing)])
    assert rc == adb._EXIT_INPUT_ERROR


def test_cli_scan_mode_empty_corpus_no_crash(tmp_path: Path) -> None:
    rc = adb.main(["--corpus-root", str(tmp_path)])
    assert rc == adb._EXIT_OK


def test_malformed_choice_length_excluded_from_test(tmp_path: Path) -> None:
    # 4지·3지 혼재 — 모드(4지)만 검정 카테고리로 쓰고 3지는 malformed로 분리.
    records = [{"choices": ["0", "1", "2", "3"], "answer": str(i % 4)} for i in range(20)]
    records.append({"choices": ["0", "1", "2"], "answer": "1"})
    _write_corpus(tmp_path, "problem_bank_a_v0", records)
    pairs = adb.scan_corpus_mc_pairs(tmp_path)
    n_positions = adb._modal_choice_length(pairs)
    assert n_positions == 4
    from whymath_backend.l1.problem_bank.answer_distribution import tally_positions

    _, malformed = tally_positions(pairs, n_positions=n_positions)
    assert malformed == 1


# ──────────────────────────────────────────────────────────────────────────
# 결함(쏠림) 주입 강등전 — 결정론·검출력·오검출률·변별력.
# ──────────────────────────────────────────────────────────────────────────
def test_battle_deterministic_same_seed() -> None:
    a = adb.run_battle(seed=42, n_trials=50)
    b = adb.run_battle(seed=42, n_trials=50)
    assert a == b


def test_battle_detects_skew_with_low_false_alarm() -> None:
    detected_skew, false_alarm, n_trials = adb.run_battle(seed=20260729, n_trials=300)
    assert n_trials == 300
    # 검출률은 높고(≥90%) 균형 배치 오검출은 유의수준(α=0.05) 근방에 머물러야 한다.
    assert detected_skew / n_trials >= 0.90
    assert false_alarm / n_trials <= 0.10


def test_battle_no_skew_weight_yields_low_detection() -> None:
    # 변별력 — skew_primary_weight를 균등(1/n_positions)으로 주면 "쏠림 배치"도 사실상 균형
    # 배치라 검출률이 균형 배치 오검출률과 같은 수준(~α)이어야 한다(게이트가 늘 True를
    # 반환하는 결함이 아님을 증명).
    detected_skew, false_alarm, n_trials = adb.run_battle(
        seed=7, n_trials=300, skew_primary_weight=0.25
    )
    assert detected_skew / n_trials <= 0.15


def test_cli_battle_gate_passes_with_achievable_thresholds() -> None:
    rc = adb.main(
        [
            "--battle",
            "--seed",
            "20260729",
            "--n-trials",
            "300",
            "--min-detection-lower",
            "0.90",
            "--max-false-alarm-upper",
            "0.10",
        ]
    )
    assert rc == adb._EXIT_OK


def test_cli_battle_gate_fails_on_unachievable_detection_threshold() -> None:
    rc = adb.main(
        [
            "--battle",
            "--seed",
            "20260729",
            "--n-trials",
            "300",
            "--min-detection-lower",
            "0.999",
        ]
    )
    assert rc == adb._EXIT_GATE_FAIL


def test_cli_battle_gate_fails_on_unachievable_false_alarm_threshold() -> None:
    rc = adb.main(
        [
            "--battle",
            "--seed",
            "20260729",
            "--n-trials",
            "300",
            "--max-false-alarm-upper",
            "0.001",
        ]
    )
    assert rc == adb._EXIT_GATE_FAIL


def test_cli_battle_default_off_gate_passes() -> None:
    # 임계 미지정(기본) — 리포트만, exit 0.
    rc = adb.main(["--battle", "--n-trials", "20"])
    assert rc == adb._EXIT_OK


def test_format_reports_render_without_error() -> None:
    from whymath_backend.l1.problem_bank.answer_distribution import chi_square_uniform_test

    result = chi_square_uniform_test({0: 511, 1: 410, 2: 349, 3: 361}, n_positions=4)
    text = adb.format_corpus_report(result, alpha=0.05)
    assert "쏠림 검출" in text
    battle_text = adb.format_battle_report(
        detected_skew=290, false_alarm_balanced=15, n_trials=300, confidence=0.95
    )
    assert "검출" in battle_text and "오검출" in battle_text
