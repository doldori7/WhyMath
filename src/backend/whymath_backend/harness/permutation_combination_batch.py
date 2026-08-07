"""고등 경우의 수 — 합의 법칙·곱의 법칙·순열 파일럿 코퍼스 배치 — W2 Phase 1 #7(결정론·LLM 0).

`quad_ineq_batch`·`sequence_sigma_batch`·`vector_operations_batch` 형제. `SumProduct
PrincipleSkeletonGenerator`([10공수1-03-01], kind=sum/product 2밴드)·`PermutationSkeleton
Generator`([10공수1-03-02])로 3밴드를 생성 → 수용 게이트(`l3/verify_answer` Tier1 경유)·
`JsonlCorpusSink`를 **재사용**해 파일럿 코퍼스를 적재한다. 두 성취기준의 첫 코퍼스다.

`kind` 필터 필수(`quad_ineq_batch`의 `direction` 관례 계승) — 미지정이면 두 밴드가 고정
시드 풀을 처음부터 재생해 같은 뼈대를 중복 방출한다.

**검증 등급 각인**: `machine_sampled`(Tier1 산술/factorial 검산).

산출물은 v0(사람 검수 전) — AI 검수 게이트는 실 LLM 필요라 이 원격 환경 밖(Kiki 머신)에서만
돈다. 그 전까지 `is_published=false`로 유지.

CLI: `python -m whymath_backend.harness.permutation_combination_batch [--sum-product-n N]
[--permutation-n N] [--out PATH] [--dry-run]`
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
from whymath_backend.l3.equivalent.orchestrator import run_equivalent_generation
from whymath_backend.l3.equivalent.permutation_combination_skeleton_generator import (
    PermutationSkeletonGenerator,
    SumProductKind,
    SumProductPrincipleSkeletonGenerator,
)
from whymath_backend.l3.verification_tier import VerificationTier

__all__ = ["CORPUS_DIR_NAME", "run_permutation_combination_batch"]

CORPUS_DIR_NAME = "problem_bank_permutation_combination_v0"
_SUM_PRODUCT_STANDARD_CODE = "[10공수1-03-01]"
_PERMUTATION_STANDARD_CODE = "[10공수1-03-02]"
_SUM_PRODUCT_SPEC_DIFFICULTY = 1.8
_PERMUTATION_SPEC_DIFFICULTY = 2.0
_DEFAULT_SUM_PRODUCT_N = 60  # 밴드당(kind별) 풀 64보다 작게 — 풀 소진 없이 안정적으로 채움.
_DEFAULT_PERMUTATION_N = 40  # 풀 42보다 작게.


def _default_out_path() -> Path:
    root = Path(__file__).resolve().parents[4]
    return root / "data" / "corpus" / CORPUS_DIR_NAME / "problems.jsonl"


def run_permutation_combination_batch(
    *,
    sum_product_n: int = _DEFAULT_SUM_PRODUCT_N,
    permutation_n: int = _DEFAULT_PERMUTATION_N,
    out_path: Path | None = None,
    write: bool = True,
) -> CorpusBatchReport:
    """3밴드(sum/product/permutation) 배치 실행 — 생성→게이트(Tier1)→적재."""
    resolved_out = out_path if out_path is not None else _default_out_path()
    sink = JsonlCorpusSink()
    bands: list[BandResult] = []

    sum_product_spec = EquivalenceSpec(
        achievement_standard_codes=frozenset({_SUM_PRODUCT_STANDARD_CODE}),
        target_misconception_ids=frozenset(),
        difficulty_overall=_SUM_PRODUCT_SPEC_DIFFICULTY,
        answer_format=None,
    )
    sum_product_kinds: tuple[SumProductKind, ...] = ("sum", "product")
    for kind in sum_product_kinds:
        bands.append(
            _run_band(
                name=kind,
                spec=sum_product_spec,
                generator=SumProductPrincipleSkeletonGenerator(kind=kind),
                n=sum_product_n,
                sink=sink,
            )
        )

    permutation_spec = EquivalenceSpec(
        achievement_standard_codes=frozenset({_PERMUTATION_STANDARD_CODE}),
        target_misconception_ids=frozenset(),
        difficulty_overall=_PERMUTATION_SPEC_DIFFICULTY,
        answer_format=None,
    )
    bands.append(
        _run_band(
            name="permutation",
            spec=permutation_spec,
            generator=PermutationSkeletonGenerator(),
            n=permutation_n,
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
        prog="python -m whymath_backend.harness.permutation_combination_batch",
        description="경우의 수(합·곱의 법칙·순열) 파일럿 코퍼스 배치(3밴드·결정론·Tier1).",
    )
    parser.add_argument(
        "--sum-product-n", type=int, default=_DEFAULT_SUM_PRODUCT_N, help="합·곱 밴드당 요청 수."
    )
    parser.add_argument(
        "--permutation-n", type=int, default=_DEFAULT_PERMUTATION_N, help="순열 요청 수."
    )
    parser.add_argument("--out", default=None, help="출력 코퍼스 경로(기본 permutation_v0).")
    parser.add_argument("--dry-run", action="store_true", help="파일 기록 없이 밴드별 수율만 출력.")
    args = parser.parse_args(argv)

    report = run_permutation_combination_batch(
        sum_product_n=args.sum_product_n,
        permutation_n=args.permutation_n,
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
