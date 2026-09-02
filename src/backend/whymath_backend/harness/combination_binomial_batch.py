"""고등 중복조합·이항정리 계수 파일럿 코퍼스 배치 — W2 Phase 3 #2(결정론·LLM 0).

`permutation_combination_batch`(S4-33, [10공수1-03-01]·[10공수1-03-02]) 형제. `Repeated
CombinationSkeletonGenerator`([12확통01-02])·`BinomialCoefficientSkeletonGenerator`
([12확통01-03])로 2밴드를 생성 → 수용 게이트(`l3/verify_answer` Tier1 경유)·`JsonlCorpusSink`
를 **재사용**해 파일럿 코퍼스를 적재한다. 두 성취기준의 첫 코퍼스다.

**검증 등급 각인**: `machine_sampled`(Tier1 산술 검산 — factorial 기반).

산출물은 v0(사람 검수 전) — AI 검수 게이트는 실 LLM 필요라 이 원격 환경 밖(Kiki 머신)에서만
돈다. 그 전까지 `is_published=false`로 유지.

CLI: `python -m whymath_backend.harness.combination_binomial_batch [--repeated-combination-n N]
[--binomial-n N] [--out PATH] [--dry-run]`
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from whymath_backend.harness.problem_corpus_batch import (
    BandResult,
    CorpusBatchReport,
    JsonlCorpusSink,
)
from whymath_backend.l3.equivalent.acceptance import EquivalenceSpec
from whymath_backend.l3.equivalent.combination_binomial_skeleton_generator import (
    BinomialCoefficientSkeletonGenerator,
    RepeatedCombinationSkeletonGenerator,
)
from whymath_backend.l3.equivalent.orchestrator import run_equivalent_generation
from whymath_backend.l3.verification_tier import VerificationTier

__all__ = ["CORPUS_DIR_NAME", "run_combination_binomial_batch"]

CORPUS_DIR_NAME = "problem_bank_combination_binomial_v0"
_REPEATED_COMBINATION_STANDARD_CODE = "[12확통01-02]"
_BINOMIAL_STANDARD_CODE = "[12확통01-03]"
_REPEATED_COMBINATION_SPEC_DIFFICULTY = 2.3
_BINOMIAL_SPEC_DIFFICULTY = 2.4
# 밴드당 요청 수 — 풀 크기(56·65)를 넉넉히 덮는다.
_DEFAULT_REPEATED_COMBINATION_N = 56
_DEFAULT_BINOMIAL_N = 65


def _default_out_path() -> Path:
    root = Path(__file__).resolve().parents[4]
    return root / "data" / "corpus" / CORPUS_DIR_NAME / "problems.jsonl"


def run_combination_binomial_batch(
    *,
    repeated_combination_n: int = _DEFAULT_REPEATED_COMBINATION_N,
    binomial_n: int = _DEFAULT_BINOMIAL_N,
    out_path: Path | None = None,
    write: bool = True,
) -> CorpusBatchReport:
    """2밴드(repeated-combination/binomial-coefficient) 배치 실행 — 생성→게이트(Tier1)→적재."""
    resolved_out = out_path if out_path is not None else _default_out_path()
    sink = JsonlCorpusSink()
    bands: list[BandResult] = []

    repeated_combination_spec = EquivalenceSpec(
        achievement_standard_codes=frozenset({_REPEATED_COMBINATION_STANDARD_CODE}),
        target_misconception_ids=frozenset(),
        difficulty_overall=_REPEATED_COMBINATION_SPEC_DIFFICULTY,
        answer_format=None,
    )
    bands.append(
        _run_band(
            name="repeated-combination",
            spec=repeated_combination_spec,
            generator=RepeatedCombinationSkeletonGenerator(),
            n=repeated_combination_n,
            sink=sink,
        )
    )

    binomial_spec = EquivalenceSpec(
        achievement_standard_codes=frozenset({_BINOMIAL_STANDARD_CODE}),
        target_misconception_ids=frozenset(),
        difficulty_overall=_BINOMIAL_SPEC_DIFFICULTY,
        answer_format=None,
    )
    bands.append(
        _run_band(
            name="binomial-coefficient",
            spec=binomial_spec,
            generator=BinomialCoefficientSkeletonGenerator(),
            n=binomial_n,
            sink=sink,
        )
    )

    total_stored = sum(b.stored for b in bands)
    written = sink.write(resolved_out) if write else None
    return CorpusBatchReport(
        bands=bands,
        total_requested=sum(b.requested for b in bands),
        total_stored=total_stored,
        written=written,
        out_path=str(resolved_out),
    )


def _run_band(
    *,
    name: str,
    spec: EquivalenceSpec,
    generator: object,
    n: int,
    sink: JsonlCorpusSink,
) -> BandResult:
    """단일 밴드 실행 — n회 시도·게이트 통과분만 적재·풀 소진은 정상 종료로 간주."""
    outcomes = [
        run_equivalent_generation(
            spec,
            generator,  # type: ignore[arg-type]
            store=sink,
            signature_index=None,
            verification_tier=VerificationTier.MACHINE_SAMPLED.value,
        )
        for _ in range(n)
    ]
    stored = 0
    produced = 0
    failures: list[str] = []
    for outcome in outcomes:
        if outcome.status == "generation_failed":
            continue  # 풀 소진 — 정상 종료 신호.
        produced += 1
        if outcome.status == "accepted_stored":
            stored += 1
        else:
            failures.extend(outcome.reasons or [f"status={outcome.status}"])
    return BandResult(name=name, requested=produced, stored=stored, failure_reasons=failures)


def main(argv: list[str] | None = None) -> int:
    """CLI — 파일럿 코퍼스 배치. 게이트 거부가 하나라도 있으면 exit 1(조용한 실패 금지)."""
    parser = argparse.ArgumentParser(
        prog="python -m whymath_backend.harness.combination_binomial_batch",
        description="고등 중복조합·이항정리 계수 파일럿 코퍼스 배치(2밴드·결정론).",
    )
    parser.add_argument(
        "--repeated-combination-n",
        type=int,
        default=_DEFAULT_REPEATED_COMBINATION_N,
        help="중복조합 밴드 요청 수.",
    )
    parser.add_argument(
        "--binomial-n", type=int, default=_DEFAULT_BINOMIAL_N, help="이항정리 밴드 요청 수."
    )
    parser.add_argument(
        "--out", default=None, help="출력 코퍼스 경로(기본 combination_binomial_v0)."
    )
    parser.add_argument("--dry-run", action="store_true", help="파일 기록 없이 밴드별 수율만 출력.")
    args = parser.parse_args(argv)

    report = run_combination_binomial_batch(
        repeated_combination_n=args.repeated_combination_n,
        binomial_n=args.binomial_n,
        out_path=Path(args.out) if args.out else None,
        write=not args.dry_run,
    )
    print(json.dumps(report.to_json(), ensure_ascii=False, indent=2))
    rejected = sum(len(b.failure_reasons) for b in report.bands)
    if rejected:
        print(f"게이트 거부 {rejected}건 — 저작 결함(조용한 통과 금지).", file=sys.stderr)
        return 1
    return 0 if report.total_stored > 0 else 1


if __name__ == "__main__":  # pragma: no cover — 엔트리포인트
    sys.exit(main())
