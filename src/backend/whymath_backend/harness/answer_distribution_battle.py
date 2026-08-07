"""⑧ 정답 위치 분포 편향 — 실 코퍼스 스캔 + 결함(쏠림) 주입 강등전 CLI (품질 15축 ⑧, ARCH-19).

정본: `docs/architecture/problem_bank_gap_review.md` §3 D5. `l1/problem_bank/answer_distribution`
(순수 카이제곱 적합도 검정)을 두 방식으로 구동한다:

  1. **실 코퍼스 스캔(기본)**: `data/corpus/problem_bank*/problems.jsonl`의 객관식 문항 전량에서
     정답 위치를 집계해 균등분포 대비 카이제곱 검정 리포트를 낸다. `problem_bank_coverage.py`와
     동형으로 **관측 리포트**다 — 임계 미지정이면 exit 0(입력 오류만 exit 2). 실측 없이 "균등"을
     선언하지 않으므로 malformed(선택지 수 불일치·정답 미소속)를 조용히 버리지 않고 별도 집계한다.
  2. **결함 주입 강등전**(`--battle`): defect_seeder(문항 개별 결함)와 달리 이 축은 *배치* 수준
     결함이라 합성 방식이 다르다 — 균형 배치(위치 균등 난수)와 쏠림 배치(위치 0에 가중치 편중)를
     각 N회 생성해, 카이제곱 게이트가 쏠림 배치를 검출하는 비율(Wilson 하한)과 균형 배치를
     오검출하는 비율(Wilson 상한)을 측정한다. `--min-detection-lower`/`--max-false-alarm-upper`
     지정 시 게이트(exit 0/1) — 미지정이면 리포트만.

사용:
    python -m whymath_backend.harness.answer_distribution_battle
    python -m whymath_backend.harness.answer_distribution_battle --battle \\
        --min-detection-lower 0.90 --max-false-alarm-upper 0.10

계층 메모(CLAUDE.md 7계층): harness는 계약 밖(config·db·privacy·harness·whs·ops)이라 L1
(`l1.problem_bank.answer_distribution`)을 자유로이 import한다(L1→harness 역방향은 금지 —
Wilson 경계 계산이 harness에 있는 이유와 동일).
"""

from __future__ import annotations

import argparse
import json
import math
import random
import sys
from collections import Counter
from pathlib import Path

from whymath_backend.harness.wilson import wilson_lower_bound, wilson_upper_bound
from whymath_backend.l1.problem_bank.answer_distribution import (
    AnswerDistributionResult,
    chi_square_uniform_test,
    tally_positions,
)

__all__ = [
    "format_battle_report",
    "format_corpus_report",
    "main",
    "run_battle",
    "scan_corpus_mc_pairs",
]

_EXIT_OK = 0
_EXIT_GATE_FAIL = 1
_EXIT_INPUT_ERROR = 2

# harness→whymath_backend→backend→src→repo 루트(problem_bank_coverage.py와 동일 관례).
_REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_CORPUS_ROOT = _REPO_ROOT / "data" / "corpus"
CORPUS_DIR_GLOB = "problem_bank*"
CORPUS_FILE_NAME = "problems.jsonl"


# ──────────────────────────────────────────────────────────────────────────
# 실 코퍼스 스캔
# ──────────────────────────────────────────────────────────────────────────
def scan_corpus_mc_pairs(corpus_root: Path) -> list[tuple[list[str], str | None]]:
    """`data/corpus/problem_bank*/problems.jsonl`에서 (choices, answer) 쌍 수집(choices 有만)."""
    pairs: list[tuple[list[str], str | None]] = []
    for corpus_dir in sorted(corpus_root.glob(CORPUS_DIR_GLOB)):
        path = corpus_dir / CORPUS_FILE_NAME
        if not path.is_file():
            continue
        with path.open(encoding="utf-8") as fh:
            for line in fh:
                stripped = line.strip()
                if not stripped:
                    continue
                record = json.loads(stripped)
                choices = record.get("choices")
                if choices:
                    pairs.append((choices, record.get("answer")))
    return pairs


def _modal_choice_length(pairs: list[tuple[list[str], str | None]]) -> int:
    """가장 흔한 choices 길이 — 균등분포 가정의 카테고리 수(다른 길이는 malformed로 분리)."""
    lengths = Counter(len(choices) for choices, _ in pairs)
    return lengths.most_common(1)[0][0]


def _fmt(value: float) -> str:
    return "n/a" if math.isnan(value) else f"{value:.6g}"


def format_corpus_report(result: AnswerDistributionResult, *, alpha: float) -> str:
    """사람 가독 리포트 — 위치별 관측/기대 + 카이제곱 통계량·p-value + 쏠림 판정."""
    lines = ["=" * 64, "⑧ 정답 위치 분포 — 실 코퍼스 카이제곱 적합도 검정", "=" * 64]
    lines.append(
        f"객관식 문항: {result.n_items}건(선택지 {result.n_positions}지) "
        f"· malformed {result.malformed}건(선택지 수 불일치·정답 미소속)"
    )
    expected = result.n_items / result.n_positions if result.n_items else 0.0
    for pos in range(result.n_positions):
        count = result.position_counts.get(pos, 0)
        lines.append(f"  위치 {pos}: {count:>5d}건 (기대 {expected:.1f})")
    lines.append(f"카이제곱 통계량: {_fmt(result.statistic)} · p-value: {_fmt(result.p_value)}")
    if result.n_items == 0:
        lines.append("판정: 대상 부재(객관식 문항 0건) — 균등 여부 판정 불가.")
    else:
        verdict = "⚠ 쏠림 검출(귀무가설 기각)" if result.is_skewed(alpha) else "쏠림 미검출"
        lines.append(f"판정(α={alpha}): {verdict}")
    lines.append("=" * 64)
    return "\n".join(lines)


# ──────────────────────────────────────────────────────────────────────────
# 결함(쏠림) 주입 강등전 — 배치 수준 결함이라 문항별 mutator가 아니라 합성 배치 생성.
# ──────────────────────────────────────────────────────────────────────────
def _synthesize_positions(
    rng: random.Random, *, n_positions: int, batch_size: int, weights: list[float] | None
) -> list[int]:
    """배치 1개의 정답 위치 리스트 합성 — weights=None이면 균등, 지정 시 그 가중 분포로."""
    return rng.choices(range(n_positions), weights=weights, k=batch_size)


def run_battle(
    *,
    n_positions: int = 4,
    batch_size: int = 200,
    n_trials: int = 300,
    seed: int = 20260729,
    alpha: float = 0.05,
    skew_primary_weight: float = 0.40,
) -> tuple[int, int, int]:
    """균형/쏠림 배치 각 n_trials개 생성 → (쏠림 배치 검출 수, 균형 배치 오검출 수, n_trials).

    쏠림 배치: 위치 0에 `skew_primary_weight`, 나머지 위치는 잔여를 균등 분배(합성 편향 —
    실 코퍼스가 겪을 수 있는 "생성기가 정답을 특정 위치에 자주 두는" 결함을 흉내낸다).
    균형 배치: 전 위치 균등 확률(카이제곱 검정이 진짜 H0 아래서 보정됐는지의 대조군).
    """
    rng = random.Random(seed)
    skew_weights = [skew_primary_weight] + [(1.0 - skew_primary_weight) / (n_positions - 1)] * (
        n_positions - 1
    )
    detected_skew = 0
    false_alarm_balanced = 0
    for _ in range(n_trials):
        balanced = _synthesize_positions(
            rng, n_positions=n_positions, batch_size=batch_size, weights=None
        )
        counts = Counter(balanced)
        result = chi_square_uniform_test(counts, n_positions=n_positions)
        if result.is_skewed(alpha):
            false_alarm_balanced += 1

        skewed = _synthesize_positions(
            rng, n_positions=n_positions, batch_size=batch_size, weights=skew_weights
        )
        counts = Counter(skewed)
        result = chi_square_uniform_test(counts, n_positions=n_positions)
        if result.is_skewed(alpha):
            detected_skew += 1
    return detected_skew, false_alarm_balanced, n_trials


def format_battle_report(
    *, detected_skew: int, false_alarm_balanced: int, n_trials: int, confidence: float
) -> str:
    """사람 가독 리포트 — 쏠림 배치 검출률 Wilson 하한 + 균형 배치 오검출률 Wilson 상한."""
    pct = round(confidence * 100)
    dlb = wilson_lower_bound(detected_skew, n_trials, confidence)
    fau = wilson_upper_bound(false_alarm_balanced, n_trials, confidence)
    lines = ["=" * 64, "⑧ 정답 위치 분포 — 결함(쏠림) 주입 강등전", "=" * 64]
    lines.append(
        f"쏠림 배치 검출   : {detected_skew}/{n_trials} "
        f"(점추정 {detected_skew / n_trials:.3f}·{pct}% 하한 {dlb:.3f})"
    )
    lines.append(
        f"균형 배치 오검출 : {false_alarm_balanced}/{n_trials} " f"({pct}% 상한 {fau:.3f})"
    )
    lines.append("=" * 64)
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """CLI — 실 코퍼스 스캔(기본)·결함 주입 강등전(`--battle`). exit 0(통과)/1(미달)/2(입력오류)."""
    parser = argparse.ArgumentParser(
        prog="python -m whymath_backend.harness.answer_distribution_battle",
        description="⑧ 정답 위치 분포 편향 — 실 코퍼스 스캔·결함(쏠림) 주입 강등전.",
    )
    parser.add_argument(
        "--corpus-root", default=str(DEFAULT_CORPUS_ROOT), help="문제 코퍼스 루트 디렉터리."
    )
    parser.add_argument("--alpha", type=float, default=0.05, help="카이제곱 유의수준(기본 0.05).")
    parser.add_argument(
        "--battle", action="store_true", help="실 코퍼스 스캔 대신 결함(쏠림) 주입 강등전 실행."
    )
    parser.add_argument("--batch-size", type=int, default=200, help="강등전 배치당 문항 수.")
    parser.add_argument("--n-trials", type=int, default=300, help="강등전 배치 종류별 시행 수.")
    parser.add_argument("--seed", type=int, default=20260729, help="강등전 합성 시드(결정론).")
    parser.add_argument(
        "--skew-primary-weight",
        type=float,
        default=0.40,
        help="강등전 쏠림 배치의 위치 0 가중치(나머지는 균등 분배·기본 0.40).",
    )
    parser.add_argument("--confidence", type=float, default=0.95, help="Wilson 신뢰수준(단측).")
    parser.add_argument(
        "--min-detection-lower",
        type=float,
        default=0.0,
        help="(--battle 전용) 쏠림 검출률 Wilson 하한 임계 — 미만이면 exit 1(기본 0=off).",
    )
    parser.add_argument(
        "--max-false-alarm-upper",
        type=float,
        default=1.0,
        help="(--battle 전용) 균형 오검출률 Wilson 상한 임계 — 초과면 exit 1(기본 1.0=off).",
    )
    args = parser.parse_args(argv)

    if args.battle:
        detected_skew, false_alarm_balanced, n_trials = run_battle(
            batch_size=args.batch_size,
            n_trials=args.n_trials,
            seed=args.seed,
            alpha=args.alpha,
            skew_primary_weight=args.skew_primary_weight,
        )
        print(
            format_battle_report(
                detected_skew=detected_skew,
                false_alarm_balanced=false_alarm_balanced,
                n_trials=n_trials,
                confidence=args.confidence,
            )
        )
        exit_code = _EXIT_OK
        dlb = wilson_lower_bound(detected_skew, n_trials, args.confidence)
        if args.min_detection_lower > 0.0 and dlb < args.min_detection_lower:
            exit_code = _EXIT_GATE_FAIL
        fau = wilson_upper_bound(false_alarm_balanced, n_trials, args.confidence)
        if args.max_false_alarm_upper < 1.0 and fau > args.max_false_alarm_upper:
            exit_code = _EXIT_GATE_FAIL
        return exit_code

    corpus_root = Path(args.corpus_root)
    if not corpus_root.is_dir():
        print(f"오류 — 코퍼스 루트 디렉터리 없음: {corpus_root}", file=sys.stderr)
        return _EXIT_INPUT_ERROR
    pairs = scan_corpus_mc_pairs(corpus_root)
    if not pairs:
        print(format_corpus_report(chi_square_uniform_test({}, n_positions=1), alpha=args.alpha))
        return _EXIT_OK
    n_positions = _modal_choice_length(pairs)
    counts, malformed = tally_positions(pairs, n_positions=n_positions)
    result = chi_square_uniform_test(counts, n_positions=n_positions, malformed=malformed)
    print(format_corpus_report(result, alpha=args.alpha))
    return _EXIT_OK


if __name__ == "__main__":  # pragma: no cover — 엔트리포인트
    sys.exit(main())
